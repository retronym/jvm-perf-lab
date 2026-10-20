# Compiler labs

Benchmarks and profiles of the Scala compilers' working trees, on perflab: what did a change do to the machine, and where.

| | compiler | checkout | corpora | lab |
|---|---|---|---|---|
| [scala3](scala3/README.md) | dotc, bootstrapped | `SCALA3_CHECKOUT` (scala/scala3) | lampepfl/scala3-benchmarks (`SCALA3_BENCHMARKS`) | `dotty.tools.compilerlab` |
| [scala2](scala2/README.md) | scalac, quick | `SCALA_CHECKOUT` (scala/scala) | scala/compiler-benchmark (`COMPILER_BENCHMARK`) | `scala.tools.nsc.compilerlab` |

Each lab is its own sbt build (`lab` project, `perflab.toml`, `campaigns/`, `span-config.json`, `doc/design.md`), run from its directory:

```bash
cd labs/scala2
export SCALA_CHECKOUT=~/code/scala/scala
perflab run -- -p corpus=scalap CompileBenchmark
```

## What's in a lab

The labs keep only what is specific to a compiler; running, comparing, profiling and the index are perflab's.

- **In-memory compiler** (`InMemoryCompiler`, `InMemoryClasspath`). One op is one full compilation of a corpus with no file I/O in the measured window: sources are read up front, the classpath (JDK modules, the checkout's library/reflect/compiler or library jar, the corpus's jars) is snapshotted into read-only in-memory directories once per JVM, bypassing the compilers' process-wide jar and jrt caches, and output (class files, TASTy) is generated and serialized into an in-memory directory. `compiler=fresh` (default) starts each op from scratch (new `Global` / `ContextBase`), paying for everything a cold compile does but file reads and JIT warmup; `compiler=resident` shares one compiler with a new `Run` per op, as a compile server does.
- **Benchmarks.** `CompileBenchmark` in both, with `corpus`, `scalacOptions` and `variants` (settings compared within one fork, alternating by iteration, reported as paired differences). Scala 3 adds `ParserBenchmark`, `PicklerBenchmark` (re-pickling typed trees from a run stopped before the pickler) and `JavacBenchmark` as a yardstick.
- **In-fork build comparison** (Scala 2, `IsolatedBuild`). A variant `@build=<dir>` loads another checkout's reflect and compiler in a class loader of its own, so builds are paired within a fork like flags, rather than across noisy forks.
- **Corpora** (`Corpus`): named corpora from scala/compiler-benchmark or lampepfl/scala3-benchmarks with their options and classpaths, or any directory of sources.
- **`CompileLoop`**: the same compilation in a loop outside JMH, printing time and live heap per run, for attaching other tools.
- **Cost per definition** (`CostHooks`, `def-costs.hooks`): perflab-agent weaves frame hooks into the compiler as it loads; `--defs:<file>` writes a table for `perflab defcosts`, `--defs-listener:` records frames as async-profiler spans ([def-costs.md](def-costs.md)).
- **Caller audits** (Scala 3, `audit/`, `audit/Predicates.scala`): probe specs for `perflab run --profile audit:<spec>`.
- **`OutputDigest`** (Scala 3): hashes of each output file, to check two builds produce the same bytes (`scripts/samebytes.py` ignores TASTy's git hash).
- **perflab configuration**: `perflab.toml` (driving `lab/Jmh/run` through the sbt server), `campaigns/*.json` (example A/A and overhead campaigns), `span-config.json` (span panel grouping), and for Scala 3 `perflab-phases.toml` (samples by phase).

## Why outside the compiler repos

A lab inside a compiler repo has to be merged into every branch it measures, and keeps that branch from being reviewed or shared on its own. Here, the lab loads the checkout's build as a source dependency (`ProjectRef`), compiles the compiler from the checkout's sources into the checkout's own target directories, and compiles against it. The compiler branch carries only compiler changes. What would otherwise need a compiler change comes in from outside: the cost per definition is woven into the compiler by perflab-agent ([def-costs.md](def-costs.md)).

What it takes to load a compiler's build from another build:

- The same sbt version (`project/build.properties`).
- Meta-build dependencies the checkout's build plugins rely on, where the lab's plugins bring older versions (scala3: ASM, in `project/plugins.sbt`).
- Builds that resolve paths against the working directory rather than their own base: scala/scala reads `versions.properties` that way (the lab copies it in); scala/scala3's `ScalaLibraryPlugin` keyed its Zinc stamps by the root build's `${BASE}`, so every compile in the lab recompiled the library (fixed on scala3 branch `sbt-library-stamps`, needed in the checkout until upstream).
- One sbt server compiling a checkout at a time: the lab's server and the checkout's own share its target directories.
