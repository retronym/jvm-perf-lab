# jvm-perf-lab

Since this was written, the compiler-specific parts left the compiler repos too: both labs now live in [labs/](../labs/README.md), loading a compiler checkout as a source dependency ([labs/PLAN.md](../labs/PLAN.md)).

## Problem

bench-lab was written inside scala3 to benchmark the compiler. About two thirds of it has nothing to do with the compiler:
- the JMH profilers (JIT stability, paired variants within a fork, xctrace counters per thread group);
- the caller-audit agent;
- the campaign runner (`ab.py`, `abtrees.py`, `loadgate.py`) and profile analysis (`regraph`, `profdiff`, `frameweight`, `subtree`);
- the live index and fork timeline.

Scala 2's compiler benchmarks, javac or any JMH project could use them, but today they are tied to the scala3 build: sbt commands in its `project/`, `dotty.tools.benchlab` packages, and scripts that assume `CompileBenchmark` and `-Ddotty.*` flags.

`retronym/jvm-perf-lab` takes the general part. scala3's bench-lab keeps what needs the compiler and depends on jvm-perf-lab as a published jar, for as long as bench-lab lives outside it.

## Key decisions

1. **Java 17 and Python, no Scala.** The profilers run inside benchmark forks, so their baseline is the oldest JDK anyone benchmarks on; nothing needs more than 17 (records, pattern `instanceof`, JFR streaming). The agent keeps weaving with ASM, shaded into its jar, which also avoids needing 24+ for the ClassFile API. The scripts stay stdlib-only Python 3.11+, runnable as `python3 -I` without a virtualenv.

2. **mise drives the build: Maven for Java, uv for Python.** `mise run build|test|install` wraps `./mvnw` and `uv build`. The Maven modules are `perflab-jmh` (profilers and the JMH driver) and `perflab-agent` (the caller-audit agent, a fat jar with `Premain-Class`). JMH is a `provided` dependency, so the user's build picks the version.

3. **No custom build commands: argument files instead of escaping.** The sbt commands existed because sbt splits a typed command at `;`, and JMH's profiler options are `;`-separated. The driver (`perflab.jmh.Main`) fixes that at the source with two features:
   - **`@file` arguments:** an argument `@path` expands to that file's lines, as javac's do, so no profiler option is ever typed at the sbt prompt.
   - **`&` between profiler options:** `-prof "async:output=jfr&dir=out"`, for when typing is easier.

   What the commands did besides building arguments moves to the Python side: choosing the output directory, rendering flame graphs after the run, putting the agent on the fork. `perflab run` writes the arguments file, runs the project's build command from a template, then post-processes.

   The template lives in a small `perflab.toml` in the user's project, e.g. `jmh = "sbt --client 'scala3-bench-lab/Jmh/run {args}'"`, or a Maven or Gradle equivalent. `ab.py` already drives builds this way, so a single profiled run becomes a campaign of one cell. The recipes for sbt, Maven and Gradle reduce to that one template line plus adding the dependency.

4. **Anything project-specific is configuration, not code:**
   - the benchmark class and its parameter names (`corpus` is today's default);
   - which JVM flags name a variant (`-Ddotty.*` today becomes a pattern in `perflab.toml`);
   - phase tables for `analyze` (scala3 supplies dotc's);
   - the categories `subtree` uses.

   Paired variants become a helper any benchmark can use. `Variants.parse` reads `name=opts|…` and `Variants.order(n, cycle)` gives the Williams design; each iteration is bracketed with `IterationLog.begin` and `end`. `CompileBenchmark` keeps only the part that turns options into a compiler.

5. **mise tasks build the patched tools.**
   - `tools:async-profiler` checks out and builds retronym/async-profiler's integration branch (kperf events, `--hw`, the extended flame graphs).
   - `tools:kperf-helper` builds `asprof-kperf`. Starting it needs root, so that step stays yours.
   - `tools:jdk` builds the patched JDK (C2 node notes, W^X healing). It's optional and slow.

   Each task pins a branch or commit and records it, so a campaign can name the exact tools it ran with. The scripts find the tools in mise's tool directory before falling back to the PATH.

6. **Published through JitPack while this is a temporary dependency.** A tag (or a commit) on GitHub becomes a Maven artifact, `com.github.retronym.jvm-perf-lab:perflab-jmh:<tag>`, with no publishing setup. For quick iteration across both repos, `mise run install` puts a snapshot in `~/.m2`, and sbt reads it with `Resolver.mavenLocal`. Maven Central can come later if it outlives bench-lab.

7. **agentscope as an optional store and viewer for profiles, not a dependency.** Its capture store already keeps JFR files with metadata, diffs two captures, and draws flame graphs with frame-type strips, filters, a sub-second heatmap and per-thread lanes. That is better than the static jfrconv pages the lab renders today.
   - **Export:** `perflab export agentscope <cell>…` registers a cell's recording as a capture. The label holds the campaign, corpus, variant and round. The context holds the JMH parameters, result, iteration spans and tool versions, so agentscope's views and diffs work on benchmark runs.
   - **What agentscope would need:**
     - an import endpoint for an existing JFR file, plus its context;
     - reading `profiler.HardwareSample` (kperf) as one kind per event;
     - pinned captures that skip the 30-day retention;
     - a way to tell benchmark forks apart (`-Dbenchlab.cell`), so continuous recording leaves them alone instead of adding JFR overhead to the measurement.
   - **Who owns what:** perf-lab owns experiment design and measurement (variants, interleaving, checks, counters); agentscope owns storage and viewing. The live fork timeline stays in perf-lab, because it pairs iterations and variants with counters agentscope doesn't have. Its lanes could later become an agentscope view.

## What stays in scala3's bench-lab

- **Compiler-side code:** the compile, parser and pickler benchmarks, `InMemoryCompiler`, `InMemoryClasspath` and `Corpus`.
- **Compiler comparison tools:** `OutputDigest`/`samebytes`, the javac yardstick and `compare.py`.
- **Configuration for perf-lab:** the dotc phase table, the audit predicates and specs, the campaign specs, and `perflab.toml`.
- **Build wiring:** the dependency on `perflab-jmh`, and the agent jar resolved from it.

The custom sbt commands go away.

## Prior art

- **JMH's own profilers:** `XCTraceNormProfiler` and `XCTraceAsmProfiler`. jvm-perf-lab's xctrace profiler adds per-thread-group counts, the per-thread breakdown and splitting by iteration time; those could go upstream later.
- **Renaissance and the scala/compiler-benchmark harness:** precedents for a benchmark project consuming a shared harness.
- **Continuous profilers (Pyroscope, Parca):** agentscope's model, on one machine.
- **Mytkowicz et al. (ASPLOS 2009), and Williams designs from crossover trials:** behind the interleaving.

## Plan

- DONE 0. Repository skeleton: `mise.toml`, the Maven wrapper and two modules, `pyproject.toml`, CI building both, Apache-2.0 licence (JMH is GPLv2 with the classpath exception, which covers profilers built against it).
- DONE 1. Move the Java code, renamed to `io.github.retronym.perflab`:
  - **What moves:** the driver (with `@file` and `&`), JitProfiler, PairedProfiler, IterationLog and Variants, XctraceProfiler with PerfMap and its templates, and the audit agent.
  - **Unit tests:** the Williams order, spec parsing, assigning samples to iterations, the XML filter, the driver's argument handling.
  - **Integration test:** a tiny JMH benchmark in the repo, run with each profiler.
- DONE 2. Move the Python into a `perflab` package with one CLI, and a sample project (`examples/sample`) that runs every command:
  - **Commands:** `run`, `ab`, `abtrees`, `loadgate`, `regraph`, `profdiff`, `frameweight`, `subtree`, `index`, `timeline`, `auditfold`, `analyze`.
  - **Configuration:** `perflab.toml` replaces the hard-coded benchmark, parameter, variant-flag and phase assumptions.
- DONE 3. scala3 bench-lab depends on jvm-perf-lab (`~/.m2` while iterating) and deletes the moved code and the sbt commands (retronym/scala3 `bench-lab-perflab`). Back-ported first: `perflab-spans` (async-profiler's Span API, which both compiler labs vendored) and the span panel in `regraph` (`[async] spans`, `span_config`).
  - **Check:** the envelope audit gives the same counts as bench-lab's own agent; paired variants and cost-frame spans work through `perflab`.
- TODO 4. `tools:*` mise tasks for async-profiler, the kperf helper and the patched JDK.
- TODO 5. agentscope export, plus the four agentscope changes it needs (decision 7). This one is for you to decide; it's independent of 0–4.
## Future work

- **Histogram utilities.**
  - **Heap class histograms:** per iteration or per op (the `CompileLoop -Dbenchlab.histoAt` hunt for the cross-Run leak, made a profiler), and diffs between them, the growth per op by class.
  - **Paths to GC roots:** for what grows, with retronym/jvm-heap-paths.
  - **Distributions:** of per-op time and per-iteration counters (not only means and spreads), to show bimodal runs such as a fork whose iterations were preempted.
- Linux: perf counters in place of xctrace.
- Maven Central, if it outlives bench-lab.
- Upstreaming the xctrace improvements to JMH.
