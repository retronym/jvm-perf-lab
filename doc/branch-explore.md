# Branch exploration and a central perflab server

## Problem

A campaign today compares a handful of variants that someone has already checked out and named. The question that comes up most with a performance branch is a different one: *which commits of this branch moved the numbers, by how much, and why?* retronym/scala3's `scala3-perf-integration` is the case at hand. It is `main` plus twelve merged performance PRs, each of which should show up as a step in compile time, allocation or both on some corpus. To answer it today, someone has to make a worktree per commit, write a `builds` spec by hand, wait for every cell to finish, and then read a table whose rows are not in history order.

[retronym/branch-bench](https://github.com/retronym/branch-bench) answers this for a single branch. It lists the commits, shows a score beside each, charts them with error bars and a point cloud, and diffs the profiles of two commits. But it runs commits in a fixed order, keys series by benchmark name only (so `@Param`s collapse together), and has no change detection, no queue and no cleanup. perflab already has better pieces for the measurement: launch-mode snapshots, interleaving, loadgate, per-fork timelines, profiles and their diffs. What it lacks is a commit axis.

Two operational problems come with it:
- **Runs take hours, and one machine can only measure one thing at a time.** Commands run in the foreground and contend for `jmh.lock`. A branch of 13 first-parent commits is 13 builds of about 2.7 min, then 2 min per cell per corpus per round. Pausing for something urgent, cancelling a mistaken run, or seeing what is waiting has to happen in the UI, not by killing terminals.
- **Storage grows without bound.** Snapshots are about 117 MB per build and async profiles reach 1 GB. Nothing ever deletes them.

## Key decisions

### 1. A branch is a campaign whose variants are commits

The spec gets `"branch": {"checkout": <repo>, "range": "<base>..<tip>", "firstParent": true, "env": {...}}`. perflab resolves the range with git, oldest first, base included, and writes `<campaign>/branch.json`. Every commit becomes a variant named by its short sha, with a launch-mode build of its own. Everything downstream works unchanged: cell layout `<corpus>/<variant>/<round>`, checks, timelines, profiles, the report, resume.

- **First parent by default.** On an integration branch, each first-parent commit is one merged PR, and that is the unit someone acts on. A merge row lists the commits it brought in; exploring those is a separate step (future work: "drill into a merge").
- **perflab owns one worktree per campaign** (`<campaign>/.worktree`), detached, and checks each commit out into it before that commit's build. The build tool's incremental state carries over between neighbouring commits, as in branch-bench, and the user's checkout is untouched.
- **Builds are keyed by tree, not commit.** A rebase that leaves a tree alone reuses its snapshot and its results (as branch-bench reuses them). The key also takes in what the build depends on outside the tree: the env and the `[build] launch` template.
- **Builds are lazy.** A commit is built just before its first cell, not all up front: the first number arrives after one build instead of thirteen. Builds still never overlap a measurement.

### 2. Explore coarse-first

The default for any order is the one that reveals the most, soonest.
1. **Coarse pass:** round 1 on the first corpus, endpoints first (base, tip), then the interior commits in van der Corput order over their indices (½, ¼, ¾, ⅛, …). After k cells the range is sampled at a spacing of about n/k, so the shape of the curve, and the total gain, show from the first few cells.
2. **Other corpora:** the same order, corpus by corpus.
3. **More rounds:** every corpus again, in the reverse order, so that drift over the campaign does not line up with history.

Pinpoint and asv's `find` add an adaptive stage: more forks where adjacent commits differ by more than their noise, or where intervals are wide, under a budget. It fits naturally as `"explore": "adaptive"` once the server can re-plan between cells, and is future work.

### 3. One view, two shapes: history with numbers, or a chart

A branch campaign's card shows its history, newest first, as `git log --graph --first-parent` would show it. Each row has the short sha, subject, author and date, with one column per corpus.

- **Columns** show the primary metric as a number (mean ± CI), as a dot on a shared per-column scale with its interval as a whisker (a sparkline running down the page), or as both. A second, low-noise metric (default `gc.alloc.rate.norm`) can sit beside it.
- **Δ against the previous row** shows in each cell, coloured only when it exceeds the combined spread, as campaigns already do.
- **The chart** turns the same data around: commits on x (by index, with a gap for each unmeasured commit, never interpolated), the primary axis left (default score, i.e. wall time per op), the secondary right (default `gc.alloc.rate.norm`), and a corpus picker.
  - Each commit gets a point at its mean with CI error bars, over a jittered cloud of every measurement iteration of every fork. These come from `result.json`'s `rawData`, which is already kept and never shown.
  - Hovering a point highlights its row; clicking selects it.
- **View state lives in the URL** (shape, metrics, corpus, selected rows), so a view can be linked.

This follows what holds up across the prior art: raw samples kept, uncertainty always drawn, commit index on the x axis, low-noise measures beside wall time (CodSpeed, LNT, rustc-perf, asv).

### 4. Pairs of rows: numbers, then profiles

Selecting two rows (any two; adjacent by default, as with the "Δ vs prev" toggle) opens a comparison:
- per corpus, Δ with its interval for every metric the cells recorded (the campaign summary, for two variants);
- for profiled cells, the flame-graph diffs (`profdiff`) both ways, in the lightbox, as campaign diffs already open.

Measurement and profiling stay separate runs, because a profiler perturbs the score. A branch spec can carry a `"profile"` campaign of its own, typically async cycles+alloc with one round. The view links a commit's profile cells to its measurement row. "Profile these two commits" is a button that queues a profile-only campaign for those two commits, sharing their snapshots. Diffs are cached by their pair of cell directories.

### 5. Change points, cheaply

A row whose step from its predecessor exceeds k × the pooled noise is marked as a candidate. A pass of E-Divisive means over the commit-ordered series (Otava's method, small enough to port to stdlib Python) marks the first commit of each new regime. Triage state (accepted, noise, linked issue) is future work.

### 6. A persistent perflab server; the CLI submits

One `perflab server` per machine (per user) owns the measurement. It keeps a durable queue (SQLite in `~/.perflab/server/`), runs one job at a time, and serves the UI for every project registered with it. `perflab ab run`, `perflab run` and the branch commands submit a job, print its URL, and follow its transcript; Ctrl-C detaches, and `--local` runs one in the foreground. Without a server they run in the foreground as today, so the CLI keeps working on a laptop without setup.

- **A job is a perflab command line,** `{argv, cwd, env}`, run as a subprocess in its own process group, with its transcript in the job's directory. This keeps the server ignorant of campaigns, and means anything the CLI can do can be queued.
- **Control:**
  - **Pause** takes effect at a cell boundary. Between cells, the runner checks a control file the server writes, so pause never throws away a fork's work.
  - **Resume** clears the control file.
  - **Cancel** sends SIGTERM to the process group; 2d2d3f2 made that clean.
  - **Reorder** and **priority** apply to queued jobs.
  - A job's results are never deleted with it.
- **The index becomes the server's UI:** the queue (queued, running with its live timeline, paused, done, failed, cancelled) and the campaigns and runs of each registered project. Static `index.html` stays as an export (`perflab site`) and for `file://`.
- Because jobs are serialised, two campaigns no longer race for `jmh.lock`, though the lock check stays for runs from outside the server.

### 7. Workers on other machines

The server is a coordinator, and running jobs is the job of a worker. The local worker is built in. `perflab worker --server <url>` on another machine pulls jobs for its **testbed** (machine model, OS, JDK), holding a lease kept alive by a heartbeat, so that a worker that dies hands its job back. This is the rustc-perf collector model.

- **Source:** a job names commits, not paths. The worker fetches them from a remote the job names, or from a `git bundle` uploaded with the job for unpushed commits like `perfint-tip`. It builds into its own worktree.
- **Results:** cell directories travel back as tarballs into the coordinator's campaign directory. The fixed-name layout makes that a copy.
- **Testbeds:** every cell records its testbed. The summary, the branch view and change detection compare only within one testbed (Bencher, Conbench), and a campaign may name the testbed it needs.

### 8. Storage admin with tiered retention

An admin page lists, per project and campaign, bytes by tier:
- **results:** `result.json`, `iterations.tsv`, logs and timelines, about 120 KB per cell. Kept.
- **profiles:** `.jfr`, `.trace`, rendered flame graphs. Graphs can be re-rendered from the recording.
- **builds:** snapshots and the campaign worktree. Rebuildable from the commit.

Actions are "drop builds of finished campaigns", "drop rendered graphs", "drop profiles older than N days", and "delete campaign". Each shows the bytes it would reclaim before it runs. A pinned campaign is skipped by every bulk action. Bytes are counted as allocated blocks, hard links once. APFS clones still count once per clone, since there is no portable way to see shared extents, so the builds tier overstates what deleting reclaims.

## Supporting changes

- `metrics`/`index`: a cell's raw iterations (`rawData`) and CI reach the page's data, not just mean and sd.
- `ab.run`: an order hook (the explore order), lazy per-variant builds, and the between-cells control check.
- **Resume bug:** a cell with an empty `result.json` (interrupted) counts as done. It must be rerun.
- `launch.build`: a snapshot key beyond its directory (tree + env + template).

## Prior art

- **branch-bench:** commit rows beside scores, a Plotly chart with a second axis and a box/point cloud, reuse by tree sha, profile diffs of two selected commits, bisect-like order.
- **asv:** `--steps` and `find` over a commit range, step detection, `rm`.
- **Chromium Pinpoint:** repeat runs until a comparison is decisive.
- **Skia Perf:** commit-range triage.
- **Otava/Hunter (MongoDB):** E-Divisive change points, first commit of the new regime.
- **rustc-perf:** noise-derived thresholds, a DB-backed queue polled by collectors, expiring heavy data.
- **Bencher, Conbench:** testbed as its own dimension; compare only like with like.
- **LNT:** raw samples, Mann-Whitney.
- **Lucene nightly:** annotations on known jumps.
- **JMH Visualizer:** JMH JSON as the record.
