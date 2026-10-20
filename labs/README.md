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

## Why outside the compiler repos

A lab inside a compiler repo has to be merged into every branch it measures, and keeps that branch from being reviewed or shared on its own. Here, the lab loads the checkout's build as a source dependency (`ProjectRef`), compiles the compiler from the checkout's sources into the checkout's own target directories, and compiles against it. The compiler branch carries only compiler changes. What needs a compiler change that is not upstream is compiled only when the checkout has it: `SpanCostListener` needs the cost per definition (`-Yprofile-defs-listener`).

What it takes to load a compiler's build from another build:

- The same sbt version (`project/build.properties`).
- Meta-build dependencies the checkout's build plugins rely on, where the lab's plugins bring older versions (scala3: ASM, in `project/plugins.sbt`).
- Builds that resolve paths against the working directory rather than their own base: scala/scala reads `versions.properties` that way (the lab copies it in); scala/scala3's `ScalaLibraryPlugin` keyed its Zinc stamps by the root build's `${BASE}`, so every compile in the lab recompiled the library (fixed on scala3 branch `sbt-library-stamps`, needed in the checkout until upstream).
- One sbt server compiling a checkout at a time: the lab's server and the checkout's own share its target directories.
