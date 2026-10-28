# jvm-perf-lab

JMH profilers, a Java agent and a command-line tool for finding out what a change did to a JVM program's performance, and why:

- default profilers for allocation and JIT activity
- variants compared within one fork, by iteration
- Apple Silicon PMU counters per thread, via `xctrace`, and flame graphs of PMU events via async-profiler ([doc/pmu-counters.md](doc/pmu-counters.md): which to use when)
- an agent that counts the callers reaching a method
- spans a program marks around its own units of work, to break a flame graph down by them
- `perflab`, which runs all of this through a project's build and shows the results on one page, live as they arrive

Requires Java 17. Design and plan: [doc/design.md](doc/design.md).

## Sample results

[retronym.github.io/jvm-perf-lab](https://retronym.github.io/jvm-perf-lab/): the results of [examples/sample](examples/sample), built with `mise run site`. It is the same page `perflab serve` shows while benchmarks run: an overview, campaigns, PMU counters by run, and runs, with flame graphs, timelines and reports.

| | |
|---|---|
| [![The results page](doc/screenshots/dashboard.png)](https://retronym.github.io/jvm-perf-lab/) | [![A paired fork's timeline](doc/screenshots/timeline.png)](https://retronym.github.io/jvm-perf-lab/campaigns/maps-counters/100000/paired/1/timeline.html) |
| The results page: overview, campaigns, counters and runs, filtered by benchmark, tool and corpus | One fork's timeline: three map variants interleaved by iteration, the benchmark thread's cycles and IPC, GC pauses beside the GC threads' cycles |
| [![Flame graph with the span panel](doc/screenshots/flamegraph.png)](https://retronym.github.io/jvm-perf-lab/runs/wordcount-async/sample.WordCountBenchmark.countAndLookUp-AverageTime-map-hash-size-100000-variants-/jfr-cpu-cpu.html) | [![Audit report](doc/screenshots/audit.png)](https://retronym.github.io/jvm-perf-lab/runs/audit-normalize/report.html) |
| async-profiler, benchmark threads, with the span panel: samples by the spans the benchmark marks | A caller audit: calls to `normalize`, by caller |
| [![PMU counters by run](doc/screenshots/counters.png)](https://retronym.github.io/jvm-perf-lab/#counters) | [![Paired memory benchmark timeline](doc/screenshots/memory-timeline.png)](https://retronym.github.io/jvm-perf-lab/campaigns/memory-paired/4194304/paired/1/timeline.html) |
| PMU counters by run (xctrace): IPC, branch mispredicts per 1000 instructions, instructions and cycles per op | Pointer chase over a sequential vs shuffled array in one fork: IPC drops from about 4.5 to under 0.1 in the shuffled iterations |

## Modules

**`perflab-jmh`**: depend on it from the benchmarks (JMH itself is `provided`, so your build picks the version).

- `io.github.retronym.perflab.jmh.Main`: `org.openjdk.jmh.Main` with default profilers (`gc`, `JitProfiler`, `PairedProfiler`). Use it as the benchmark's main class. It takes `@file` arguments (the file's lines, one argument each, unquoted) and `&` between a profiler's options, for build tools that split a command at `;` (sbt).
- `JitProfiler`: compilations, compile time and deoptimizations while measuring and in the last warmup iteration.
- `Variants`, `IterationLog`, `PairedProfiler`: compare variants that a benchmark can switch between iterations (e.g. compiler settings) within one fork, in a Williams design, so they share the fork's compiled code. Reports time per variant and paired differences ([doc/paired-ab.md](doc/paired-ab.md)).
- `xctrace.XctraceProfiler`: Apple Silicon PMU counters through `xctrace`, for the benchmark thread separately from JIT, GC and other threads, per variant when variants alternate, plus per-method attribution and a 50 ms timeline. Bundled templates: `template=ipc`, `frontend`, `mem-l1d`.

**`perflab-agent`**: a `-javaagent` jar for caller audits ([doc/caller-audit.md](doc/caller-audit.md)): probes woven into the program as it loads, from a spec, counting hits, distinct call sites and creation-site tags.

```
java -javaagent:perflab-agent.jar=spec=envelope.audit,out=audit-{pid}.json ...
```

**`perflab-spans`**: async-profiler's Span API (`one.profiler.Span`, `Recording`), vendored, for a program that marks its own units of work (a compiler's phases and definitions) as spans. With retronym/async-profiler's integration branch recording JFR, `jfrconv --spans` gives the flame graph a panel that breaks samples down by the spans enclosing them (`[async] spans` and `span_config` in `perflab.toml`). Without a recording, a span costs a check of a static field.

**`perflab`** (Python 3.11+, `python/`): runs and analyses benchmarks through a project's build.

| command | |
|---|---|
| `perflab run --profile <p> -- <jmh args>` | one run under a profile: `none`, `xctrace:<template>`, `async:<events>`, `audit:<spec>`; flame graphs or an audit report afterwards; serves the index first and shows the run there live |
| `perflab ab run\|report <spec>` | campaigns: variants over corpora, interleaved by round or paired within forks, each run checked; the summary shows every counter the cells recorded, per op or per unit of work |
| `perflab trees <spec>` | campaigns across checkouts |
| `perflab serve` | serve the results page (one server per checkout) on 127.0.0.1 and print its URL, the same every time; the page updates itself as results arrive and follows the running fork's timeline (`run` and `ab run` do this first) |
| `perflab index`, `timeline` | rebuild the results page, or one run's or cell's timeline |
| `perflab site` | the results page as a static site, with an intro, for publishing |
| `perflab regraph`, `profdiff`, `frameweight`, `subtree`, `analyze` | flame graphs and analysis of async-profiler runs |
| `perflab inlinetree <label>=<cell>...` | JIT compilation units of async-profiler runs against a baseline: what C2 inlined where, which callees became real calls, how compile boundaries moved; one page beside the campaign, linked from its card |
| `perflab auditfold` | merging and folding audit reports |
| `perflab defcosts` | cost per definition from a compiler's `-Yprofile-defs` table: histograms, outliers, comparisons |
| `perflab loadgate` | waiting for a quiet machine, shown live on the results page while it waits; sampling competing load |
| `[build] mode = "launch"` (or `PERFLAB_BUILD_MODE=launch`) | perflab builds once per run or campaign with `[build] launch`, snapshots the build, and starts JMH itself: no build tool server during the measurement, and a campaign measures the build it took ([doc/direct-launch.md](doc/direct-launch.md)) |
| `perflab --transcript <file> <command>` | appends progress (cells, loadgate waits) and the build's output as it comes (the build tool compiling, JMH's log) to `<file>`, for a caller to follow with `tail -f`; `trees` passes it to each checkout |

A campaign's summary (on its card in the index, and `perflab ab report`) shows what its cells recorded, without naming events: the score; the benchmark threads' cycles, instructions and IPC; allocation; every counter of the xctrace template or of an async kperf profile, per op and per 1,000 instructions or as % of cycles; the JIT, GC and other threads' share of cycles and IPC, and the cycles, instructions and IPC of all threads (in the pivot and chart). XctraceProfiler counts the benchmark threads only, so JIT and GC don't distort the per-op counts; their share shows beside them. When variants do different amounts of work per op (a benchmark that types the same files once per reader, say), name an `@AuxCounters` events counter of the benchmark in the spec, `"perUnit": "files"`: every count, allocation and the score are divided by its units per op (cycles/file), the card toggles between per file and per op, and `perflab ab report` is per file unless `--per-op`.

## In a build

The build passes perflab's arguments to the driver as an `@file`. A project's `perflab.toml` names the command, e.g. for sbt with sbt-jmh:

```toml
[build]
jmh = "sbt --client 'bench/Jmh/run {args}'"
server = "sbt"
```

```scala
libraryDependencies += "io.github.retronym.perflab" % "perflab-jmh" % "0.1.0-SNAPSHOT"   // resolvers += Resolver.mavenLocal; `mise run install` here
Jmh / run / mainClass := Some("io.github.retronym.perflab.jmh.Main")
```

There is no release yet: build a snapshot into `~/.m2` with `mise run install`. Once tagged, JitPack serves a tag as `com.github.retronym.jvm-perf-lab:perflab-jmh:<tag>`.

[examples/sample](examples/sample) is a Maven project set up this way, with campaign and audit specs.

## Compiler labs

[labs/](labs/README.md) holds two labs built on perflab: [labs/scala3](labs/scala3/README.md) for a scala/scala3 checkout and [labs/scala2](labs/scala2/README.md) for a scala/scala checkout. Each is an sbt build that loads the compiler checkout as a source dependency, so the compiler branch being measured carries no lab commits.

## Building

`mise run build` (Java 21 builds the Java 17 release), `mise run test`, `mise run install` for a snapshot in `~/.m2`, `mise run cli` to install `perflab`, `mise run tools:async-profiler` for retronym/async-profiler's integration branch (kperf events, `jfrconv --spans`), `mise run site` and `mise run publish-site` for the sample results.

Licensed under the Apache License 2.0.
