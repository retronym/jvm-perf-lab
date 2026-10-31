---
name: perflab
description: Run, check and report JMH benchmarks through perflab (jvm-perf-lab) - `perflab run`, `perflab ab` campaigns, profiles (async, xctrace, audit), JVM arguments, JDK choice, variants. Use before starting any benchmark, A/B comparison, campaign or profile in a project with a perflab.toml, and before reporting its results.
---

# perflab

perflab drives a project's JMH benchmarks through the build command in its `perflab.toml` (found from the working directory upward). Read that file first: it sets the benchmark, its parameters, the JVM arguments every run gets, and where results go.

## 1. Give the user the dashboard URL first

Before starting any run or campaign:

```bash
perflab serve
```

Send the user the URL it prints, in your next message, before results exist. It is the same URL every time for a checkout, and the page updates itself as results arrive: there is nothing to regenerate when a run finishes, so never offer to. `perflab run` and `perflab ab run` log the same URL as `index (updates ...): ...`; pass that line on if you didn't run `serve`. Never start another HTTP server for results.

While a `perflab server` runs (`perflab server status`), the project's page is on it (`serve` prints `http://127.0.0.1:8690/p/<project>/...`), and `perflab run` and `perflab ab run` go to its queue, one job at a time: they print `job N queued ...: <queue URL>` and the index URL, then follow the job's transcript (into `--transcript` too). Give the user both URLs. Ctrl-C (or killing the follower) only detaches: cancel a job from the queue page, not with `kill`. `--local` runs a command in the foreground instead; `--dry-run` always does.

On macOS the server can run as a launchd agent, started at login and kept alive: `mise run server:install` (from a jvm-perf-lab checkout; the server then runs that checkout's code), `mise run server:uninstall`. The server reloads itself when its checkout's perflab code changes (so fast-forwarding that checkout's main deploys a change), in its own pid, after checking that the new code imports: code that doesn't is not loaded, and the queue page and `/api/status` (`reloadError`) say why. `perflab server reload` reloads at once. Check with `launchctl print gui/$(id -u)/io.github.retronym.perflab.server`; its log is `~/.perflab/server/server.log`. A reload or restart doesn't interrupt jobs: the new server adopts them. Since a reload happens mid-campaign too, land perflab changes in the server's checkout only when the user wants them live. `perflab server stop` stops the agent, and it stays stopped until `server:restart`. With portless (`portless alias perflab 8690`) the server is https://perflab.localhost/, and perflab prints its links with that name (`PERFLAB_SERVER_URL` sets another).

When reporting, link the run or campaign on that page rather than only pasting numbers.

Run long commands in the background with a transcript, and follow that file instead of waiting blind: `perflab --transcript <scratch>/t.txt ab run <spec>` (also `run`, `trees`). It gets perflab's progress, loadgate waits, the build's output as it comes (sbt compiling, a failing build or a server started without the lab's environment) and JMH's iterations. A loadgate wait also shows live on the index.

In a lab with `[build] launch` (the scala3 lab), prefer launch mode for campaigns: `PERFLAB_BUILD_MODE=launch`, with the lab's environment (`SCALA3_CHECKOUT`, `SCALA3_BENCHMARKS`, `JAVA_HOME`) set on the perflab command itself. A batch sbt builds once and perflab snapshots the build into `<campaign>/.build`, so no sbt server is needed or left running, and editing the checkout mid-campaign doesn't change what is measured.

## 2. Dry-run, then read the arguments

```bash
perflab run --dry-run --profile <profile> -- <jmh arguments>
perflab ab run <spec.json> --dry-run
perflab trees <spec.json> --dry-run
```

This prints the build command and the `jmh.args` file perflab will hand to JMH, one argument per line. Read it before the real run and check: one `-jvmArgsAppend`, the `-jvm` you meant, the `-p` values you meant. A fork that fails to start is almost always visible here.

## 3. JVM arguments: perflab owns `-jvmArgsAppend`

perflab writes exactly one `-jvmArgsAppend`: `[benchmark] jvmArgs` from `perflab.toml` (the heap settings, e.g. `-Xms4G -Xmx4G -Xss2M`) plus its own timeline flags (`-Dperflab.cell=...`, `-Xlog:gc:...`). It replaces the benchmark's `@Fork(jvmArgsAppend)`.

- **Never pass `-jvmArgsAppend` or `-jvmArgs` yourself**, and never repeat the heap flags: perflab already adds them.
- In a campaign, put flags in the spec: `"jvmArgs"` (every variant; replaces `[benchmark] jvmArgs`, so include the heap settings) or `"variants"` (per variant, added to `jvmArgs`).
- For a one-off `perflab run`, use `-jvmArgsPrepend "<flags>"`, as the labs' READMEs do for `-javaagent:`. The async profile with `--kperf` prepends its own flags; check the dry run.
- Values in `jmh.args` are not shell-quoted: `-jvmArgsPrepend` and its value are two lines, the value space-separated flags. Don't add quotes inside it.

## 4. The JDK: `-jvm`, not `JAVA_HOME`

Without `-jvm`, JMH forks the JDK running the JMH driver. With `sbt --client` that is the **already-running sbt server's** JDK: changing `JAVA_HOME`, `mise use` or the shell's `java` has no effect on it.

- `perflab run -- -jvm /path/to/jdk/bin/java ...`, or `"jvm": "/path/to/jdk/bin/java"` in a campaign spec (checked against each result).
- Find JDKs with `/usr/libexec/java_home -V` or `mise where java@<version>`; pass the `bin/java` inside.
- After a run, confirm the JDK in the index's run facts (`JVM ...`) or `result.json`'s `"jvm"`, and say which one it was when reporting.

## 5. Separators: never `;`

sbt splits a typed command at `;`, so `;` must never appear in arguments you type. perflab passes JMH arguments as an `@file`, so you rarely need one; when you do:

| Where | Separator |
|---|---|
| Several values of one JMH parameter: `-p corpus=scalaz,scalap` | `,` (JMH runs each) |
| Options of a profiler: `-prof "async:output=jfr&dir=out"` | `&` (the driver turns it into JMH's `;`) |
| Options within one compiler setting: `-p scalacOptions=-Yx -Yy` | space |
| Variants within a fork: `-p variants=base=\|new=-Yfoo -Ybar` | `\|` between variants, `name=options` each |
| A variant that names a build (scala2 lab): `base=@build=../base\|new=@build=.` | `@build=<checkout>` |

A value cannot contain `,` (JMH splits at it), so neither variants nor `paired` options can. Prefer perflab's profiles (`--profile async:cpu,alloc`, `xctrace:ipc`, `audit:<spec>`) over writing `-prof` yourself.

## 6. Campaigns over ad-hoc runs

To compare things, write a spec under the project's `campaigns/` and run `perflab ab run <spec>`, not a series of `perflab run`s or a shell loop alternating builds. A campaign interleaves variants round by round, is resumable, and checks each cell: fresh results, the JVM, every JVM argument, each variant's `-p` values, counters present. `perflab ab --help` documents the spec fields; `paired` alternates variants by iteration within one fork, which beats fork-to-fork noise (`doc/paired-ab.md`).

Say what the campaign asks and what each variant is: `"description"` and `"variantDescriptions"` (`{variant: ...}`) take Markdown (a string or a list of lines; links to PRs and issues welcome) and show in a panel atop the campaign's card and in `perflab ab report`.

To explain a difference between builds or JIT flags at the level of C2's inlining, run `perflab inlinetree <label>=<cell>... [--baseline <label>] [--event cycles] [--notes notes.json] [--strip <package>]` over an async campaign's cells. It writes `<campaign>/inlinetree-<event>.html`, linked from the campaign's card: each top compiled method, the callees it reaches marked per build as inlined, a real call or both, and cards for the largest differences. `--notes` takes `{method: Markdown}` to annotate rows with what you have found.

When variants do different amounts of work per op, set `"perUnit"` to the benchmark's aux counter of that work (`"files"`): the summary and `perflab ab report` then compare per unit (cycles/file), not per op. The summary shows every counter the cells recorded; read it there rather than from `result.json`.

Let perflab choose output directories (`--out` is optional; cells go under `[paths] campaigns`). Don't write scripts that assume a directory exists.

To explain why one build is slower than another (a campaign to establish the gap, then profiles, spot fixes with a ceiling variant, hardware counters, field layouts), follow `doc/optimising.md` in the jvm-perf-lab checkout ([on GitHub](https://github.com/retronym/jvm-perf-lab/blob/main/doc/optimising.md)): it says what to run next given what you have measured.

## 7. Read results through the API, not the files

To read a campaign's results, use perflab's API rather than parsing `result.json` or scraping the index: it computes the statistics the page shows (each metric's mean ± 99.9% CI over forks, Δ against the baseline or the previous commit by Welch's t, a verdict) and says what every field means.

- **MCP** (preferred): `claude mcp add perflab -- perflab mcp`, run in the project (or `perflab mcp --root <project>`). Every function is a tool with input and output schemas.
- **CLI**: `perflab api --list` (functions and conventions), `perflab api <function> --<param> <value>...` prints JSON, `perflab api --schema <Name>` a response's schema.
- **HTTP**, on a running server: `GET /llms.txt` (where to start), `/api/v1` (the index), `/api/v1/openapi.json`, `/api/v1/docs`; `/skill.md` serves this skill.

Start with `campaigns`, then `campaign <name>` (the summary), and for a branch campaign `branch` and `changes` (the commits that moved a metric significantly; `untested` lists steps with no spread to test, so "no changes" with a long `untested` list means "not enough forks", not "flat"). `cell` has one run's raw samples, iterations, competing load per iteration and logs; `compare` any two variants or commits; `profiles` and `diff` flame graphs and the methods whose time changed (for a curated diff, the tables by owner, by group, and of growth beyond the overall ratio); `make_diff` queues a profile diff of two variants of an A/B campaign, raw and curated (`--curate` hints: owner, groups, anchor; [doc/optimising.md](https://github.com/retronym/jvm-perf-lab/blob/main/doc/optimising.md#curated-diffs)), as a job that runs at once beside any measuring one; it also writes a `light` diff, `diff-<a>-<b>-light/` (only plumbing folded: frame kinds, one-sided frames and recursion kept), whose compare page has ⇄ pairs: both runs' graphs in the standard viewer with one layout, per op on one scale (by leaf too). On every compare page `a` and `b` show a run's graph and `t` or space flips between them, keeping the zoom, scroll, search, filters and name mode. Every diff has `flips`: methods ranked by the self events that moved into their own frames (a lost inlining's call overhead lands there), then by the call sites C2 stopped inlining them at; with the cells' `jitRecording`, also `bySites`, the callees C2 refused at the most call sites ("too big"), whatever the profile shows. The curated diff merges inlined and compiled frames and the raw graph spreads a lost inlining over hundreds of call sites, so these are the way to find one. `audit` has an `audit:` campaign's caller-audit counters and probes per variant (per fork and per op, with each counter's ratio to the first variant's); `promotion` an async cell's G1 promotion census (bytes per class to survivor or tenured), from a campaign that records the events with `"jfrsync": "+jdk.PromoteObjectInNewPLAB+jdk.PromoteObjectOutsidePLAB+jdk.TenuringDistribution"`. JitProfiler's per-fork totals are metrics like the score (`jit:compilations`, `jit:compileTime`, `jit:deopts`, `jit:lastWarmup.compilations`, `jit:lastWarmup.deopts`, kind `total`), in `cell`, `campaign` and `compare`. `jit` has a cell's JIT work (compilations per tier, the largest C2 compiles, recompilation churn, deopts by reason and method, C2's inlining failures; `--method Typer.findRef` for one method's every decision), and `jit_diff` two variants' methods whose last C2 compile grew, shrank or inlined differently (inlined in a, "hot method too big" in b). Both want a spec's `"jitRecording": true`, which records the JIT over each whole fork in `<cell>/jit-<pid>.jitrec` (any profile; large, so one fork per variant as a pilot); an async recording starts at the first measured iteration and lacks warmup's compiles and every inlining decision. Pair an A/B with a JIT pilot and an A/A one: profile pollution alone changes some decisions. Reads work without a server.

A cell disturbed by other load (see its `load`) can be voided and run again: `void` (with a reason; it moves to `<campaign>/.void/`, never deleted) and `rerun` (queues one resume of the campaign). These are actions: they need `perflab server` and change what the user is measuring, so ask the user before voiding cells or queueing jobs.

## 8. Don't route around perflab

Never write `jmh.args` yourself, call the build's `Jmh/run` directly, or patch perflab's output to get past a failure. A run that bypasses perflab gets no checks, no timeline, no index entry, and its results can't be compared with the rest.

- If a perflab feature fails, turn it off where perflab offers a switch, and say so in your report. For example, if `jfrsync` fails, set `[async] jfrsync = false` in `perflab.toml`, and the timeline then lacks the JDK's event lanes. A campaign can set its own `"jfrsync"` in its spec (a `.jfc`, `false`, or `+event...` to add JDK events to the lab's `.jfc` for that campaign only); the cell's `jfrsync.json` records what it was given and how many of each added event its recording has.
- If there is no switch, or the failure looks like a perflab bug, stop and tell the user: the command, the error from `build.log` / `jmh.log`, and the JDK and async-profiler in use. Don't work around it.

## 9. When it fails

| Symptom | Look at |
|---|---|
| Forked VM failed to start | `jmh.args` (duplicate or quoted JVM arguments), then `build.log` in the run's directory |
| `Could not start master JFR recording`, or an async run without a profile | JMH names async-profiler's output directory after the benchmark and every parameter; a long value (an absolute corpus path) takes it over 255 bytes. Shorten the value, e.g. with a symlink. jfrsync and the JDK are not the cause, so don't turn jfrsync off |
| Ran on the wrong JDK | `-jvm` missing: see section 4 |
| Parameter value cut short, or sbt reports an unknown command | a `;` in a typed argument: see section 5 |
| A campaign cell is rejected | the check's message names what differs from the spec; fix the spec, don't bypass the check |
| Profile output missing | `perflab run --help` for the profile's requirements (`--lib`, `--kperf`, `[agent] jar`) |

Each run's directory holds `run.json` (status, exit code), `build.log`, `jmh.log`, `jmh.args` and `result.json`. Read them before re-running.
