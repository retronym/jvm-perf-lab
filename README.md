# jvm-perf-lab

JMH profilers and a Java agent for benchmarking JVM programs:

- default profilers for allocation and JIT activity
- variants compared within one fork, by iteration
- Apple Silicon PMU counters per thread, via `xctrace`
- an agent that counts the callers reaching a method

Split out of the Scala 3 compiler's bench-lab. Design and plan: [doc/design.md](doc/design.md).

Java 17 or later, no Scala.

## Modules

**`perflab-jmh`**: depend on it from the benchmarks (JMH itself is `provided`, so your build picks the version).

- `io.github.retronym.perflab.jmh.Main`: `org.openjdk.jmh.Main` with default profilers (`gc`, `JitProfiler`, `PairedProfiler`). Use it as the benchmark's main class. It takes `@file` arguments (the file's lines, one argument each, unquoted) and `&` between a profiler's options, so build tools that split a typed command at `;` (sbt) never see JMH's `;`.
- `JitProfiler`: compilations, compile time and deoptimizations while measuring and in the last warmup iteration. Is the JIT still busy?
- `Variants`, `IterationLog`, `PairedProfiler`: compare variants that a benchmark can switch between iterations (e.g. compiler settings) within one fork, in a Williams design, so they share the fork's compiled code. Reports time per variant and paired differences ([doc/paired-ab.md](doc/paired-ab.md)).
- `xctrace.XctraceProfiler`: Apple Silicon PMU counters through `xctrace`, for the benchmark thread separately from JIT, GC and other threads, per variant when variants alternate, plus per-method attribution and a 50 ms timeline. Bundled templates: `template=ipc`, `frontend`, `mem-l1d`.

**`perflab-agent`**: a `-javaagent` jar for caller audits ([doc/caller-audit.md](doc/caller-audit.md)): probes woven into the program as it loads, from a spec, counting hits, distinct call sites and creation-site tags.

```
java -javaagent:perflab-agent.jar=spec=envelope.audit,out=audit-{pid}.json ...
```

## In a build

sbt with sbt-jmh:

```scala
libraryDependencies += "com.github.retronym.jvm-perf-lab" % "perflab-jmh" % "<tag>"   // resolvers += "jitpack" at "https://jitpack.io"
Jmh / run / mainClass := Some("io.github.retronym.perflab.jmh.Main")
```

then put profiler options in a file instead of typing them:

```
sbt "Jmh/run @prof.args -p corpus=x MyBenchmark"
```

## Building

`mise run build` (Java 21 builds the Java 17 release), `mise run install` for a snapshot in `~/.m2`.

Licensed under the Apache License 2.0.
