# zinc lab

What a regular sbt user experiences of Zinc: one sbt JVM compiling the independent subprojects of a real build in parallel, so that several `Global`s share the JVM. The lab compares Scala and Zinc versions on that workload. This is a design scaffold; nothing here is built or run yet.

## Question

How much faster is a whole-build `clean; compile` under

- the Scala and Zinc releases that were current on 1 October 2026 (Scala 2.13.18, Zinc 1.12.1), and
- the latest Zinc release (1.13.0, which carries many of the Zinc performance changes) with the Scala at the tip of retronym/scala#231 (`scala2-perf-integration`)?

A 2x2 of Scala {2.13.18, integration tip} x Zinc {1.12.1, 1.13.0} separates the two effects. The two corners are the ends of the question.

## Workload

Apache Pekko 1.7.1, whole build. Two builds of it: stock, and with the typed-`Nil` change to the `FanInShapeN` and `FanOutShapeN` constructors (`in0 :: in1 :: (Nil: List[Inlet[_]])`), which removes a nested lub per cons cell. The change is two lines, in the shape templates. On the arity-22 microbenchmark it took a cold compile from 3.0 s to 1.4 s; whether it matters on the real build is part of what this lab answers.

Run the patch at least on the two corner cells. The patch file is not kept anywhere yet: rewrite it against the templates of the checkout.

## Design

- A JMH benchmark hosts sbt in-process, so perflab's JDK, JVM arguments and profilers apply to the one JVM that does the work. One op is one `clean; compile` of the whole build, issued through sbt's command API in a warm sbt.
- Variants differ in the sbt version (Zinc ships with sbt: Zinc 1.12.1 with an sbt 1.12.x, Zinc 1.13.0 with sbt 1.13.0, to be confirmed) and in `scalaVersion`. The integration tip is published locally with `sbt setupPublishCoreNonOpt publishLocal` and the optimizer on, version `2.13.19-bin-<sha>-SNAPSHOT`; Zinc builds its compiler bridge from source for it.
- Default sbt task parallelism; record the core count and the loadgate's `maxCores`.
- Patched JDK 26 on the M4, like the scala2 lab. Size warmup from a pilot fork's plateau, not a guess. Run an A/A beside the A/B.

## Risks to check first

- Pekko 1.7.1's sbt plugins may not load on sbt 1.13.0.
- Pekko's build may override parallelism and warning settings (`-Xfatal-warnings`); relax the latter if the tip's compiler warns.
- The sbt-in-process host needs a separate classpath per sbt version.

## Next steps

1. Clone Pekko 1.7.1 into a scratch directory and compile it on sbt 1.12.x with 2.13.18.
2. Write the typed-`Nil` patch.
3. Write the benchmark and a four-variant campaign spec; dry-run it.
4. One-fork pilot to size warmup.

Prior art: `IncBench` (retronym/zinc, `integration/bench-1.12.x`, `internal/zinc-scripted/.../bench/IncBench.scala`) measures incremental edits on a multi-module build through the scripted handler, one module at a time, without sbt. It is the right tool for edit scenarios and the wrong one for this question.
