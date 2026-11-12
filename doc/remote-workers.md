# Workers on other machines

Design for [branch-explore.md](branch-explore.md) §7. Plan and state: [remote-workers-PLAN.md](remote-workers-PLAN.md).

## Problem

A 0.5–2% effect needs a quiet machine. The main machine is not one: endpoint security scanning (ESET, JumpCloud) puts it, for minutes at a time, in a state that costs 7–8% more cycles at equal instructions and L2 misses, below what the load gate can see. An older laptop without that software is quiet, but campaigns are queued, built and read on the main machine: its server holds the queue and the index, its checkouts hold the commits, and its specs name its paths (`jvm`, corpora, jars in the Coursier cache). Running there by hand means copying all of that, and copying the results back.

Two machines' numbers are not comparable: an M4 and an M5 Pro differ in caches and clocks, so the same build differs by more than the effects being measured. Nothing today stops a summary from averaging, or a Δ from comparing, cells from both.

## Key decisions

### 1. A testbed is a machine, named; a campaign runs on one

A **testbed** is the machine a cell ran on: a name (`m5-pro`, `m4`), and what identifies the hardware (`hw.model`, the CPU, cores, memory) and the OS. Its name comes from `PERFLAB_TESTBED` or `~/.perflab/testbed`, else from the CPU (`Apple M4 Pro` → `m4-pro`).

- Every cell records it in `<cell>/testbed.json`.
- A spec may say `"testbed": "<name>"`. A campaign without one runs on the coordinator's own testbed.
- **A campaign has one testbed.** Its summary, compare, branch view, change detection and the API's statistics count only cells of that testbed. A cell from another one (a spec whose testbed was changed) is listed with its testbed and counts for nothing, and is not "done": `ab run` measures it again on the campaign's testbed. A cell from before testbeds has no `testbed.json` and is the campaign's.
- `ab run` refuses to run a campaign on another testbed than the one it names, so a mistaken `--local` does not mix them.

Comparing across testbeds is a different question (how does the M4 rank the variants?) and stays a matter of reading two campaigns side by side.

### 2. The coordinator's queue knows where a job runs

A job gets a `testbed`, from its spec (`ab run <spec>`) when it is queued. The server's built-in worker takes only jobs of its own testbed, so a queued M4 campaign never runs on the M5, and jobs of different testbeds run at the same time, one per testbed.

`perflab worker --server <url>` on another machine is the rustc-perf collector model: it **claims** the next job of its testbed, holds a **lease** that its **heartbeat** (every 10 s) renews, and reports how the job ended. A lease not renewed for 90 s (the laptop slept, the worker died, the network went) puts the job back on the queue, with a note; the cells it uploaded stay, so the next claim resumes the campaign. A worker whose lease was taken over is told so on its next heartbeat and stops its job. Pause and cancel are answered on the heartbeat, and take effect at a cell boundary on the worker, as they do locally.

Remote jobs are `ab run <spec>`. That is where the time goes and what the queue's rerun queues; the other commands render or inspect what is on the coordinator.

### 3. A job names commits; the worker fetches them

The coordinator resolves each of the spec's checkouts when the job is claimed (a local job sees its checkouts at run time too), to a commit and the URLs of its repository's remotes. A dirty checkout is refused: the worker could not build the same tree, and a measured tree should be a commit anyway.

A branch campaign (or its profiles) is no different: the coordinator resolves its range once, as `ab run` would, into the campaign's `branch.json`, and sends the branch's repository as its tip with the resolved commits; the worker puts that `branch.json`, naming its own checkout, in its campaign, and `ab run` builds and measures the commits there as it would a resumed campaign's. The coordinator keeps its own `branch.json`.

The worker keeps one bare mirror per repository, and a worktree per commit. A commit it lacks comes from a **git bundle** the coordinator makes of that commit less what its remotes already have (`--not --remotes`), which for an unpushed branch such as `claude/ov-combo5` is a few commits. The bundle's prerequisites the mirror lacks are fetched from the remotes first; without a remote, or when the remotes do not have them, the coordinator sends the whole history.

The **harness** is a commit too: the project's repository (jvm-perf-lab) at the coordinator's HEAD, with its uncommitted diff. The worker checks it out, the same way, into a worktree of its own clone, applies the diff, and runs the job's perflab from it, so the lab's build and perflab's own code are the coordinator's. The project's ignored state (corpora under `out/`, the worker's campaign directories) stays in the worker's clone across jobs.

### 4. Paths are mapped, and checked before anything runs

A spec names the coordinator's paths. The worker maps each absolute path in it by the longest prefix of:
- the coordinator's project repository → the worker's harness worktree (the lab's corpora, its jars);
- the coordinator's home → the worker's home (Coursier's cache, SDKMAN's JDKs);
- `[paths]` in `~/.perflab/worker.toml`, for anything else.

A `jvm` is matched on what it is, not where: the coordinator sends its `release` file's version and vendor, and the worker uses the mapped path if that JDK is there, else `[jdks]` in worker.toml (by the coordinator's path, or by version), else fails the job saying which JDK to install (`sdk install java 25.0.4-tem`). The JDK the builds find (the job's `JAVA_HOME`, as the submitter's shell had it) is matched the same way and set for the job: a build's class files are of its JDK's version, so a worker whose default JDK is newer would build classes the benchmark's JVM cannot load. A path in the spec that still does not exist after mapping fails the job too, listing them all, before any build. The checks of `ab run` (the JVM, every JVM argument, the snapshot) then run on the mapped spec, as they do locally.

### 5. Results come back as cells

The fixed layout makes the transfer a copy. Uploads never overlap a measurement: when a cell ends, the worker pauses its job at the next cell boundary (the same checkpoint the coordinator's pause uses), uploads, and lets it go on, so the load gate's quiet period follows the upload. The worker uploads, as a tarball per unit, each finished cell (`<corpus>/<variant>/<round>`), each voided attempt (`.void/...`), and the campaign's own top-level records (`branch.json`, `unbuildable.json`, failed build logs), when the unit has changed and the running cell is not it. The coordinator replaces the unit whole, so a cell that was rerun loses the files of its earlier attempt. Builds (`.build`), worktrees and the worker's copy of the spec stay on the worker: the coordinator keeps its own spec and records the spec version once, which the worker's cells are tagged with. The coordinator rebuilds the project's index after uploads; a remote cell then shows like a local one, with its testbed.

An async cell's flame graphs are rendered on the coordinator, not the worker. When a cell with a recording is uploaded, the coordinator queues `perflab regraph <cell>`, which runs at once beside any measuring job, as `ab diff` does, and rebuilds the index when it ends. The worker's `ab run` renders none (`PERFLAB_NO_GRAPHS`). Rendering on the worker would spend the quiet machine's time and memory between cells (a reverse graph's jfrconv takes up to 24 GB), with a jfrconv that has to match the coordinator's: the graphs' `.regraph` stamp names the jfrconv build, and a worker's never matches, so the coordinator would render them again anyway. Its failures were also invisible: regraph reports them on stderr, which stays in the worker's output.log. A cell uploaded again (rerun) loses its graphs with the rest of the earlier attempt, and its upload queues a new render.

Before the job, the worker downloads the campaign's finished cells of its testbed that it does not have (`result.json` and what the summaries read), so `ab run` resumes from the same state as the coordinator's index.

### 6. A remote job is watched live through a mirror on the heartbeat

While a local job runs, the index and the queue page poll its files: `<campaigns>/running.json` (the cell being run), the cell's files that the fork timeline reads (`iterations.tsv`, `gc.log`, `load.tsv`, ...), `loadgate.json` and `build.json`. A remote job's are on its worker. Its heartbeat carries them: each beat, what was appended to the running cell's files since the last one, and the small JSON files whole when they changed, written by the coordinator into `<campaigns>/.live/<worker>/` at the paths they have on the worker. The pages read a remote job from that base as a local one from its own, and say which machine it is on.

It costs little: the running cell's files grow by about 25 KB in a 4-minute cell, plus a burst under 200 KB at a fork's end, against the transcript the heartbeat carried already. A beat carries at most 256 KB, so that a large file never delays the lease's renewal. A file that was replaced (the next fork's `gc.log`) is sent again; a coordinator that lost the mirror says so and is sent it from the start. The view lags the worker by up to a heartbeat (10 s). The mirror is never the results: those still come as cells (§5), and the mirror is removed when the job ends or its lease runs out.

### 7. The network: an SSH tunnel by default

The server listens on 127.0.0.1 only. The simplest secure link from the laptop is `ssh -R 8690:127.0.0.1:8690 <laptop>` run on the coordinator (the laptop needs no access to the coordinator, which may not accept SSH). Workers authenticate with the server's token (`--token-file`), on every request including downloads, which carry source. The worker endpoints accept any `Host` with the token, so a tunnel to another local port works too.

Not HTTPS on a LAN interface: the server's reads are unauthenticated behind its loopback bind, and the project's index carries the token, so listening on a network would hand both to anyone on it, encrypted or not. A tunnel also opens no port on the coordinator, which matters on a managed machine. Should a network listener be needed, it would serve only `/api/workers/` (mutual TLS, a client certificate per worker), never the pages. portless does not help here: its `.localhost` names resolve to the machine they are typed on.

## Prior art

- **rustc-perf collectors:** pull jobs per benchmark set from a queue in the database, keyed by the collector's machine.
- **Bencher, Conbench:** the testbed as a dimension of every result; only like with like is compared.
- **buildkite/GitHub Actions runners:** pull-based agents with a lease and heartbeat, so the coordinator needs no inbound access to the agent.
