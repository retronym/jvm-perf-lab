# zinc-direct lab

Zinc driven through its API (`ZincUtil.defaultIncrementalCompiler`, no sbt), to answer what the sbt-hosted [zinc lab](../zinc/README.md) cannot separate:

1. **Where Zinc's time goes**, by phase, and how that differs between Zinc 1.12.1 and 1.13.0 and between Scala 2.13.18 and the tip (`2.13.19-bin-6101d22-SNAPSHOT`).
2. **The effect of concurrent compiles.** One op is a round of K clean compiles of one project (Pekko 1.7.1 `stream`, 212 sources, or `actor`, 244), at the same time in one warm JVM, each copy with its own output directory and analysis store. Scalac Globals share the JVM: GC, JIT, locks in shared Zinc and scalac state show up as per-copy time growing with K.

## Design

- `ZincDirectBenchmark` (variants: `zincVersion`, `scalaVersion`, `copies`, `project`). The score is the round's wall time. The aux counters are per-copy means in ms: `copyMeanMs`, `copyMaxMs`, and where it went: `preMs` (Zinc before the first phase), `frontMs` (parser to the phase before `jvm`), `backendMs` (`jvm`), `apiMs` (`xsbt-api`, `xsbt-dependency`: API extraction and name hashing), `analyzerMs` (`xsbt-analyzer`, `Java analysis`), `javacMs`, `postMs` (after the last phase: invalidation, analysis merge), `persistMs` (analysis store write). The full per-phase map is in each op's log line.
- Phase times come from `CompileProgress`: the time between progress events is charged to the phase of the last event. Zinc's own bridge phases are separate phases of the Global, so they separate cleanly. It is attribution at unit granularity, not a profile; the async profile (kperf cycles) is the cross-check.
- Each Zinc version is loaded in a class loader of its own (`zincdirect.driver.Driver`, called by reflection with JDK types; it is compiled against Zinc 1.12.1, and 1.13.0 is source compatible for what it uses). The Scala instance is shared by the copies, as in sbt. The compiler bridge is compiled from the `compiler-bridge_2.13` sources of the Zinc version, per Scala version, once (`out/bridge`).
- Inputs come from sbt once (`scripts/extract-inputs.sh <project> [compile]`): sources, classpath, `scalacOptions`, `javacOptions` into `out/inputs/<project>`, from a clone-on-write copy of the pristine Pekko checkout with `../zinc/overlay` (no fatal warnings, optimizer flags dropped: the inliner is off). `stream`'s classpath has `actor`'s classes compiled by Scala 2.13.18 and Pekko's protobuf assembly; `scala-library` is replaced by the Scala under test's. `scripts/prepare-classpaths.sh` resolves Zinc's and Scala's jars into `out/cp`.
- Mixed Java and Scala sources, `CompileOrder.Mixed`, in-process javac, like sbt. Analysis is stored with `FileAnalysisStore`. Lookups of other projects' analyses are empty (dependencies are binary classpath entries).
- `zincdirect.Check` runs setup and two rounds without JMH: `java -cp $(cat out/lab.cp) zincdirect.Check <zinc> <scala> <K> [project]`.

## Campaigns

`campaigns/m5-zd-pilot.json` (one fork each of K=1, K=8, to size warmup), `campaigns/m5-zd-k.json` (corners old = Zinc 1.12.1 + 2.13.18, new = Zinc 1.13.0 + tip, K in 1, 4, 8, async kperf cycles/instructions). The full grid is Zinc x Scala x K in 1, 2, 4, 8, ...

Heap is 16 GB for every K. Run on the M5 (`m5-pro`), patched JDK 26, loadgate 6 cores.
