# Scala 3 compiler lab: design

## Problem

[lampepfl/scala3-benchmarks](https://github.com/lampepfl/scala3-benchmarks) answers "how fast is release X on corpus Y": published compilers, end to end, files on disk, tracked over versions. It is the right tool for the release curve and the wrong one for a compiler engineer's question: *what did my change do to the machine, and where?*

That question needs a different instrument:

- **It runs the working tree.** No `publishLocal`, no version string: edit, run, compare against the branch point.
- **It reaches inside.** Micro benchmarks need the compiler's internal APIs to drop caches between invocations and to run one phase or one operation on real inputs.
- **It measures the compiler and nothing else.** No file I/O in the measured region, no sbt, and counters for the compiler thread only, not the JIT and GC threads summed in.
- **It explains, not just times.** Wall time says a change was 2% faster. Counters say why: fewer instructions, or the same instructions with fewer L1I misses. Attribution says where: which methods, which phases.

## Key decisions

1. **An sbt build here that loads a scala/scala3 checkout as a source dependency** (`ProjectRef`), built against its bootstrapped compiler. The bootstrapped compiler is the bytecode that ships, so it is the one whose JIT behaviour matters. Living outside the compiler repo, the lab needs no commits on the branch being measured: point `SCALA3_CHECKOUT` at any worktree. It uses only public and protected compiler API (a `ContextBase` with its own platform, the classpath classes, `TreePickler`), so it compiles against any recent checkout; `SpanCostListener` is compiled only when the checkout has the cost per definition (`-Yprofile-defs-listener`).

2. **No file I/O in the measured region.** Sources are read once into memory (`VirtualFile`). So is the classpath (`InMemoryClasspath`): the scala-library jar and the JDK's `java.base` (more with `-Dcompilerlab.jdkModules=`), served to dotc by a platform whose classpath is in-memory directories, instead of jars and the jrt file system, which dotc caches process-wide. Output goes to an in-memory directory, so class files and TASTy are still generated (the backend's work is real work) but never written. This needs no new compiler flag; a `-Y` flag to discard output would only help outside the repo (sbt, the CLI) and would also skip the serialization we want to measure.

3. **Macro and micro in one harness, sharing inputs.**
   - Macro: one op is one full compilation of a corpus from scratch: a new `ContextBase`, platform, `Compiler` and `Run`, in a warm JVM. It pays for what a cold compile pays (definitions, classpath indexing, symbol loading) except file reads and JIT warmup, and nothing carries over between ops but the name table, so there is no crosstalk to reason about. `-p context=shared` instead reuses one root context and `Compiler`, a fresh `Run` per op, as in a warm compile server; dotc then keeps every earlier `Run` alive (through the root context's docstrings and GADT state, and phase instance state), about 240 MB per scalaz compile, until the heap runs out.
   - Phase: split a macro run by phase rather than benchmarking phases separately. The compiler records phase boundaries on its thread, and the counter samples are split by phase.
   - Operation: subtyping, implicit search, member lookup and similar, replaying inputs recorded from a real compilation, with explicit cold- and warm-cache variants.

4. **Counters are the primary output, not a profiler bolted on.** On Apple Silicon, `XctraceProfiler`: per-op event counts for the benchmark thread only, Apple's top-down breakdown, and per-method attribution through the JIT's perf map. On Linux, JMH's `perfnorm` and `perfasm`, plus top-down. The same metric names on both where possible.

5. **Experiments are first-class.** A variant is a set of JVM flags (`-XX:MaxInlineLevel`, `-XX:-Inline`, `-XX:+UseCompactObjectHeaders`, GC choice), a compiler setting, or a different compiler build (another worktree), or the same tree built differently: `SCALA3_BUILD_OPTIMIZE=false` builds the bootstrapped compiler without `-opt -opt-inline:dotty.**`, so it compares the compiler with and without its own inlining. Benchmark the default (optimized) build unless that is the experiment. A driver runs variants interleaved (A/B/A/B) and reports differences in time and in each counter with their noise.

6. **Corpora come from a scala3-benchmarks checkout**, not copied here: `small`, `dottyUtil`, `re2s` and `scalaz` need no dependencies. Micro benchmarks may use sources inline in the benchmark (`Corpus.inline`).
