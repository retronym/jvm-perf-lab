# Released vs perf-integration, Scala 2 and Scala 3, on pekko-actor (2026-10-22)

Four compilers, each a published build (released style: the optimizer on in the compiler's own build), compiling pekko-actor (203 Scala + 28 Java files, exported from the zinc integration campaigns at `~/code/.integration/corpora/{scala2,scala3}`) in memory, from scratch per op, in a warm JVM. JDK 21.0.12 (Temurin), `-Xms4G -Xmx4G`, one fork per cell, 3 rounds, variants interleaved, loadgate 1.5 cores. Timing only; directional, not absolute.

| cell | compiler | lab tree |
|---|---|---|
| scala3 rel | org.scala-lang:scala3-compiler_3:3.10.0 (Maven Central) | `~/code/.worktrees/jvm-perf-lab/pi-s3-rel/labs/scala3` |
| scala3 main | `scala3-perf-integration` @ 0906947151 (upstream/main 22fb42298e + 12 perf PRs, `PERF-INTEGRATION.md`), `BENCHMARKBUILD=yes` publishLocalBin: 3.10.2-RC1-bin-09069471…-BENCH | `~/code/.worktrees/jvm-perf-lab/perf-integration/labs/scala3` |
| scala2 rel | org.scala-lang:scala-compiler:2.13.18 (Maven Central) | `~/code/.worktrees/jvm-perf-lab/pi-s2-rel/labs/scala2` |
| scala2 main | `scala2-perf-integration` @ ed508cb5d1 (upstream/2.13.x f67d42767a + 7 perf PRs + 2 cherry-picks, `PERF-INTEGRATION.md`), setupPublishCore + optimizer, publishLocal: 2.13.19-bin-ed508cb-SNAPSHOT | `~/code/.worktrees/jvm-perf-lab/perf-integration/labs/scala2` |

Like for like: both languages compile the sources with pekko's Scala 3 option set (`-encoding UTF-8 -feature -unchecked -deprecation -language:higherKinds -release 17`, Scala 3 also `-Yfuture-lazy-vals -Xtarget:17 -source:3.7`), no optimizer and no lint on the corpus. The Scala 2 corpus with pekko's own `-opt:l:inline` and `-Xlint -Ywarn-unused:_` is below, apart.

## Results (ms/op, mean of the rounds; per round in the campaign reports)

| | released | perf-integration | Δ |
|---|---|---|---|
| Scala 3 (pickling on its own thread, as released) | 1356 (1349 / 1401 / 1318) | 1298 (1389* / 1267 / 1237) | -4.3% (-8% on rounds 2-3) |
| Scala 3, pickling on the compiler thread (`-Yno-parallel-pickling`, paired, 2 forks) | – (no such option in 3.10.0) | +3.96% ± 0.82 over parallel, i.e. ~1350 | |
| Scala 2 | 1491 (1520 / 1474 / 1480) | 1325 (1333 / 1337 / 1305) | -11.1% |

\* measured while the Scala 2 campaign's fork was also running (other load 1.12 cores); the other cells ran alone (0.4-0.8 cores).

Cross-language, same sources and option set: 3.10.0 is ~9% faster than 2.13.18 on the wall clock, ~5% once its pickler thread is counted on the compiler thread. The two perf-integration branches are level: 1325 (Scala 2) against 1298 wall / ~1350 serial-pickling (Scala 3). Allocation per op: Scala 3 1385 → 1265 MB, Scala 2 1104 → 1072 MB.

Apart: pekko's actual Scala 2 options (`-opt:l:inline -opt-inline-from:… -Xlint -Ywarn-unused:_ -Ywarn-dead-code`), the `pekko-actor` corpus of the scala2 campaign's first rounds: 2.13.18 2672 ± 48 (a second round, 2834 ± 309, ran under 1.3 cores of other load), perf-integration 2425 ± 60 (-9%). The optimizer and lint are ~80% on top of the plain compile in 2.13.18.

## Where

- Dashboards: scala3 http://127.0.0.1:8797/ab/index.html, scala2 http://127.0.0.1:8750/ab/index.html (`perflab serve` in each main tree).
- Campaign specs: `labs/scala3/campaigns/perf-integration-pekko.json`, `perf-integration-pekko-pickling.json`, `labs/scala2/campaigns/perf-integration-pekko.json`; cells under each main tree's `out/ab/<name>/<corpus>/<variant>/<round>/` (`jmh.log`, `result.json`, `gc.log`, `timeline.html`).
- Compiler branches (not pushed): `~/code/.worktrees/scala3/scala3-perf-integration-1c68be` (`scala3-perf-integration`), `~/code/.worktrees/scala/scala2-perf-integration` (`scala2-perf-integration`).
- Lab support for this (jvm-perf-lab branch `perf-integration`): a published compiler via `.lab-version` instead of a checkout, corpora exported from a build (src/, lib/, incOptions.properties), the specs above.

## Caveats

- Time only; no counters (xctrace) or profiles in this campaign. Allocation and GC time come from perflab's default profilers.
- Scala 3 at 3.10.0 and the branch both pickle on an executor thread; the paired cell puts that at ~4% of wall time on the branch, and 3.10.0 was not measured that way.
- `-source:3.7` for Scala 3: pekko's options are for 3.3 LTS, and `A with B` is an error from 3.8 on.
- The Scala 2 branch was built and tested by a subagent (junit typechecker/patmat subset passed); the Scala 3 branch's merges compile (bootstrapped, published) but its test suite was not run.
- sbt servers idle out at 10 minutes by default and `perflab trees` does not start them; each tree has an untracked `local-idle.sbt` (6 hours) for a campaign that waits on the JMH lock and the loadgate.

## CPU profiles of the two perf-integration builds (async-profiler, cpu, benchmark thread)

Campaign `perf-integration-pekko-prof` in each lab: one fork, 12 measured iterations profiled, same corpus and options as above; Scala 3 with `-Yno-parallel-pickling` so the benchmark thread includes pickling. Flame graphs (`jfr-cpu-cpu.html` benchmark thread, `-reverse`, `-classify` every thread) under `labs/scala3/out/ab/perf-integration-pekko-prof/pekko-actor/main/1/dotty…/` and `labs/scala2/out/ab/perf-integration-pekko-prof/pekko-actor-plain/main/1/scala…/`, linked from the dashboards. The Scala 3 cell's timing (1547 ± 341) ran under 1.45 cores of other load; the sample shares are what to read. Shares are inclusive, `perflab frameweight --event cpu`, of the benchmark thread's samples (52.6k Scala 3, 49.9k Scala 2).

| phase | Scala 3 branch | Scala 2 branch |
|---|---|---|
| parser | 2.5% | 2.0% |
| typer (Scala 2: incl. namers 12.6%, Infer 12.5%) | 31.5% | 31.5% |
| posttyper / superaccessors + refchecks | 4.3% | 1.6% + 6.0% |
| pickler | 8.3% (TreePickler 5.8%) | 1.4% |
| inlining | 0.7% | – |
| transforms (Scala 3: MegaPhase groups) | 30.7% | ~45% |
| &nbsp;&nbsp;erasure | 10.0% | 13.3% |
| &nbsp;&nbsp;pattern matcher | 2.8% | 5.4% |
| &nbsp;&nbsp;uncurry / specialize / explicitouter | – | 5.6% / 3.7% / 3.8% |
| &nbsp;&nbsp;lambdalift, mixin, fields/memoize, delambdafy, cleanup | 2.5%, 2.0%, –, –, – | 2.8%, 3.0%, 2.1%, 1.7%, 1.2% |
| backend (genBCode) | 11.9% | 12.3% |

Cross-cutting (inclusive, overlapping):

| | Scala 3 branch | Scala 2 branch |
|---|---|---|
| subtyping (`TypeComparer` / `isSubType`) | 11.6% | 3.7% |
| member lookup (`findMember` / `FindMembers`) | 9.4% | 6.2% |
| denotation lookup (`Symbol.denot`, `SingleDenotation.current`) | 9.4% | – |
| `asSeenFrom` | 5.3% | 6.4% |
| implicits | 3.8% | 4.2% |
| `Definitions` | 3.0% | 3.5% |
| base type sequences | – | 3.0% |
| TASTy unpickling / classfile parsing | 2.6% / 1.1% | – / 1.6% |
| `pthread_jit_write_protect_np` (JIT W^X toggling on Apple Silicon; self) | 1.95% | 1.0% |

Top self frames: Scala 3 `Symbol.denot` 1.4%, `Type.widen` 1.1%, `EqHashMap.lookup` 1.1%, `boxToInteger` 1.0%, `MegaPhase.transformTree` 0.9%, `Objects.equals` 0.8%, `Type.dealias` 0.8%, `goForward` 0.8%; Scala 2 `Objects.equals` 1.5%, `Symbol.rawInfo` 1.1%, `TypeRef.mapOver` 1.0%, `Scope.lookupEntry` 1.0%, `SymTree.symbol` 1.0%. Flat profiles in both: nothing above 2% self.

Reading: typer is the same third of the compile in both; Scala 3 spends it on subtyping and denotation lookup, Scala 2 on namers and inference. Scala 3's transforms are cheaper as a whole (30.7% against ~45%) and its pickler is 6x the share of Scala 2's (TASTy vs ScalaSignature). The backends are level.
