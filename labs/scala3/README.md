# Scala 3 compiler lab

Benchmarks and profiles of a scala/scala3 checkout's bootstrapped compiler, for answering what a change did to the machine and where. Design: [doc/design.md](doc/design.md).

## Running

The lab keeps the compiler-specific parts (in-memory compile, parser and pickler benchmarks, corpora, the cost listener, audit predicates, an output digest); running, comparing and profiling are perflab's ([README](../../README.md)), as for the Scala 2 lab ([../scala2](../scala2/README.md)).

Setup:

- A scala/scala3 checkout, named by `SCALA3_CHECKOUT` when the lab's sbt server starts. Its build must stamp the library's patched classes through sbt's file converter (scala/scala3 branch `sbt-library-stamps`, until upstream); without it, every compile in the lab recompiles the library and the compiler.
- A [lampepfl/scala3-benchmarks](https://github.com/lampepfl/scala3-benchmarks) checkout for the corpora, by default beside the compiler checkout; otherwise `SCALA3_BENCHMARKS`.
- `mise run install` at the root of jvm-perf-lab puts perflab-jmh, perflab-spans and the audit agent in `~/.m2` (`-Dperflab.version=` picks another version), and `mise run cli` installs `perflab`.
- An sbt server in this directory (`sbt --client`), which `perflab` drives (`perflab.toml`: `lab/Jmh/run` with its arguments in a file, so profiler options containing `;` never reach sbt's command parser). It compiles the checkout into the checkout's own target directories, so don't compile there from the checkout's own sbt server at the same time. `project/build.properties` must name the checkout's sbt version.

```bash
perflab serve    # the live index of runs and campaigns; open its URL first
perflab run -- -p corpus=dottyUtil CompileBenchmark
```

Every run has perflab's default profilers (`-noDefaultProf` turns them off): `gc`, for allocation per op (`gc.alloc.rate.norm`, the benchmark thread only) and GC count and time; and `JitProfiler`, for JIT stability: compilations, compile time and deoptimizations while measuring and in the last warmup iteration (`jit.*`). A steady state has next to none; if `jit.compilations` is large, warm up longer.

Benchmarks: `CompileBenchmark` (full compilation), `ParserBenchmark` (parsing only), `PicklerBenchmark` (TASTy pickling of typed trees), `JavacBenchmark` (javac on a Java corpus, as a yardstick). `-p corpus=/abs/path` compiles the `.scala` files under any directory (with a known corpus's options when the directory name matches one). `-p scalacOptions=-Ystop-after:typer` passes extra compiler options; `-p variants='base=|new=-Yfoo'` compares settings within one fork ([paired A/B](doc/paired-ab.md)). `CompileLoop` compiles a corpus in a loop outside JMH, for attaching other tools.

Profiles (`perflab run --profile <p>`), with results in `out/runs`:

- `xctrace:<template>`: counters on Apple Silicon (needs Xcode's `xctrace`), for the benchmark thread separately from JIT and GC: `cpu-counters` (Instruments' stock template: Apple's top-down breakdown per thread group) or perflab's event-sampling templates `ipc`, `frontend`, `mem-l1d` (event counts per op and per-method attribution).
- `async:<events>`: async-profiler JFR over the measurement iterations and flame graphs: the benchmark threads, reversed, and every thread by category. `<events>` is `cpu`, `wall`, `alloc`, `lock`, or PMU events joined by `+` with `--kperf`. With the cost per definition's listener (below) the compiler's cost frames are recorded as spans, and the bench graphs get a span panel grouped as `span-config.json` says.
- `audit:<spec file>`: a caller audit with the probes of a spec, e.g. `audit/positioned-envelope.audit` (below).

### Cost per definition

Exclusive time and allocation per definition, unit and phase ([doc/def-costs.md](doc/def-costs.md) for the frames, [../def-costs.md](../def-costs.md) for how the lab gets them without a compiler change): perflab-agent weaves calls into the compiler as it loads (`def-costs.hooks`), and `CostHooks` keeps perflab's `CostStack`. Two lab options among the scalac options, stripped before dotc sees them, turn it on per compile; without the agent, the compile fails.

```bash
# a table for perflab defcosts; the audit profile loads the agent with the hooks
perflab run --profile audit:def-costs.hooks -- -p corpus=dottyUtil -p scalacOptions=--defs:$PWD/out/dottyUtil.tsv CompileBenchmark
perflab defcosts --out out/dottyUtil.html out/dottyUtil.tsv
# each frame as an async-profiler span (retronym/async-profiler's integration branch), the agent given beside the profile
perflab run --profile async:cpu -- -p corpus=dottyUtil -p scalacOptions=--defs-listener:io.github.retronym.perflab.costs.SpanCostListener -jvmArgsPrepend -javaagent:<perflab-agent.jar>=spec=$PWD/def-costs.hooks CompileBenchmark
```

`perflab analyze` splits async-profiler samples by dotc's phases (`perflab-phases.toml`); `perflab regraph`, `profdiff`, `frameweight` and `subtree` work on any async-profiler run or campaign cell.

### A/B campaigns

`perflab ab run|report <spec>` runs a campaign described by a JSON spec (`campaigns/*.json`): a benchmark under one profile, over corpora and variants, round by round with the variants interleaved, resumable, waiting for a quiet machine, and checking that each run measured what it claims. A variant is JVM flags, JMH arguments (`variantJmhArgs`, e.g. a compiler setting), or, in a `"paired"` spec, compiler settings compared within each fork. `perflab trees` does the same across builds, each variant this lab directory in another jvm-perf-lab worktree, with its own sbt server and `SCALA3_CHECKOUT`. Results go to `out/ab/<name>/<corpus>/<variant>/<round>`, and the index shows each campaign's summary, cells and graphs.

```bash
perflab ab run campaigns/<spec>.json
perflab ab report campaigns/<spec>.json
```

`scripts/samebytes.py` compares two builds' `OutputDigest` output modulo the git hash in TASTy headers.

### Caller audits

"Which callers rely on X, and how often?" `perflab run --profile audit:<spec>` runs the benchmark with perflab's agent, which weaves probes into the compiler as it loads, with no compiler change: counts at a method's entry or exit, the distinct call sites reaching it, and tags pairing the code that made an object with the code that later relies on it. Specs are in `audit/`, with predicates compiled against the compiler in `audit/Predicates.scala`; `perflab auditfold` merges and folds reports. See [doc/caller-audit.md](doc/caller-audit.md).

```bash
perflab run --profile audit:audit/positioned-envelope.audit -- -p corpus=dottyUtil -wi 1 -i 1 -w 1 -r 1 CompileBenchmark
```

### Variance reduction

What makes a difference between variants stand out from the noise, with the evidence from the Positioned campaigns (`positioned-serial`: re2s, 4 variants × 5 rounds, xctrace ipc):

- **A/B within one JVM where the change allows it.** Feature flags compared in the same fork share its compiled code, so the fork's JIT luck cancels in the difference (see Plan, paired A/B).
- **Microbenchmarks for a local change.** A benchmark of the changed operation (e.g. copying a tree with the tree copier) isolates it far better than a whole compilation, where it is a fraction of a percent.
- **No optional parallelism.** The pickler runs on an executor, a fresh thread per op, invisible to the benchmark thread's counters: on re2s 12% of the process's cycles. `-Yno-parallel-pickling` (retronym/scala3#15) moves it onto the benchmark thread (from 83% to 93% of cycles; instructions/op 4.47G → 4.88G). Use it when counting the benchmark thread, or count all compiler threads; `<trace>.threads.txt` shows what is outside the benchmark thread. The backend is already serial (`-Ybackend-parallelism` is 1).
- **Watch the machine.** `perflab ab` waits for a quiet machine and reruns a cell whose competing load averaged too high. A limit of 1.5 cores still admits about one core of other work.
- **A better-lit metric.** On re2s, instructions/op varied 0.2–1.3% between rounds where ms/op varied 1–7%, and allocation per op is steadier still. They are proxies, though: priming spans cut instructions by about 1% on scalaz but cycles by only 0.6%.
- **JIT determinism.** Forks of the same variant differ by 0.5–1% in instructions, and one re2s fork was 3% off (and the slowest). Options: `-Xbatch`, a fixed `-XX:CICompilerCount`, longer warmup, and `JitProfiler`'s check that nothing is compiled while measuring.
- **Paired, interleaved designs.** Variants alternate within each round; report the spread of the paired differences, not of the absolute values.
- **Exact counts of work.** A probe that counts operations (see `doc/caller-audit.md`) has no noise at all, and measures the work removed rather than its cost.
- **Robust statistics.** Median or trimmed mean, and the per-fork values, not only a mean with an error bar.
- **A fixed, pre-touched heap** (`-Xms` = `-Xmx`, `-XX:+AlwaysPreTouch`).
- **Apple Silicon.** Performance-core residency, Low Power Mode and thermals. Cycles normalise away the clock frequency; time does not.
- **No I/O in the measured region** (above), and an isolated machine where possible.

### No file I/O in the measured window

Checked on `dottyUtil` with JFR file events (`jdk.FileRead`, `jdk.FileWrite`, no threshold) over 10 `CompileLoop` runs: all reads fall in the first run (the classpath snapshot, and the JVM loading compiler classes on first use), none after it. An earlier check, with the jar classpath, found the same apart from the odd lazy read from the scala-library jar.

### Live heap across ops

`CompileLoop` prints the live heap after each run (after a full GC), and `-Dcompilerlab.histoAt=<runs>` writes class histograms, to diff what survives. From scratch per op, it stays flat (scalaz: 110 MB over 8 runs); with `-Dcompilerlab.resident` it grows by a whole `Run` per op.

## Future work

- Phase attribution of the counters.
- Operation-level micro benchmarks with recorded inputs and cache control.
- Optimizer benchmark: compile with `-opt` in setup, capture the class nodes before global optimization, and per op run `GlobalOptimizer` and `LocalOptimizer` on copies with fresh optimizer state (the call graph is keyed on node identity). Needs compiler refactoring: the optimizer wiring moved out of `GenBCode.getCodeGen` into a factory, and a hook to capture the pending class nodes at the start of `CodeGen.finish`.
- Comparing builds within a fork, as the Scala 2 lab's `@build=` variants do.
- Linux parity; a non-bootstrapped variant.
