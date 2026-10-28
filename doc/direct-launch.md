# Design: perflab launches JMH itself

Status: steps 1 to 3 are implemented (`[build] mode = "launch"`, `perflab.launch`; the scala3 lab's `perflabLaunch`); 4 is not. A mode beside `[build] jmh = "sbt --client '...Jmh/run {args}'"`, not a replacement.

## Problem

Every run goes through a long-lived sbt server, which owns things that should belong to the campaign:

- **Environment.** The lab's build reads `SCALA3_CHECKOUT` when the server starts. A server that idled out and was auto-started by `sbt --client` has no such variable and fails to load (seen on PR 27252). With `trees`, the user starts one correctly configured server per checkout, by hand.
- **The JVM.** The JMH launcher runs in the server's JVM: the server's JDK (unless `-jvm` is given), and its heap (`-Xmx2G` from the client unless `SBT_OPTS` overrides it).
- **The build, while measuring.** Each cell runs `Jmh/run`, which recompiles whatever changed in the checkout since the last cell. An edit or a `git checkout` mid-campaign silently changes the later cells' compiler.
- **Noise.** The server runs on the machine during the measurement and is part of "our" process tree, so loadgate can't see it as load. Its output reaches perflab only as `sbt --client` relays it.
- **Comparing builds needs a server per build.** `trees` A/B means a lab worktree, a compiler worktree and a configured server for each variant.

## Proposal

Split the build from the run. The build step runs once per build: it compiles the checkout and the benchmarks, then writes a **launch file**. Every cell after that is a plain `java` process that perflab starts itself.

```toml
[build]
launch = "sbt -batch 'lab/perflabLaunch {out}'"   # writes {out}/launch.json; replaces `jmh`
```

`launch.json` holds what `Jmh/run` would have used:

```json
{"mainClass": "io.github.retronym.perflab.jmh.Main",
 "classpath": ["…/lab/target/classes", "…/jmh/classes", "…/scala3-compiler-bootstrapped/classes", "…jar"],
 "javaOptions": ["-Dcompilerlab.corpora=…", "-Dcompilerlab.scalaLibrary=…"],
 "build": {"checkout": "…/scala3", "commit": "5559365", "dirty": false}}
```

The lab provides `perflabLaunch` as a small sbt task, or perflab ships it as a plugin: `Jmh/compile`, then `Jmh/fullClasspath`, `Jmh/run/javaOptions` and `Jmh/run/mainClass`.

### Builds are snapshots

perflab copies every classpath entry, and every path in a `-D` option, that lies under one of the build's `roots` (the lab and the checkout) into `<campaign>/.build/snapshot/`, and rewrites `launch.json` to point at the copies. On macOS the copy is an APFS clone, so it costs nothing until the checkout changes; a scala3 build is about 120 MB of class directories. Jars outside the roots (`~/.m2`, Coursier's cache) stay where they are, recorded with their size and modification time. A campaign then measures exactly the build it took, whatever happens to the checkout afterwards. Rerunning or resuming the campaign reuses the snapshot, and its card shows each build's commit and whether it was dirty.

### Campaigns over builds

A spec names builds instead of trees:

```json
"builds": {
  "base": {"checkout": "../scala3-base", "env": {"SCALA3_CHECKOUT": "{checkout}"}},
  "pr":   {"checkout": "../scala3-pr",   "env": {"SCALA3_CHECKOUT": "{checkout}"}}
}
```

perflab runs the build step once per build, with that environment, as a batch sbt (`sbt -batch`, no server), and then alternates cells across the snapshots like any other set of variants. One lab checkout serves every build, and no server is left running. This replaces `trees` for the case where the builds differ in the code under test. Each build compiles into its own checkout's target directories, so builds of different checkouts can't clash. Two builds of the same checkout run one after the other.

### Running a cell

`java <launch javaOptions> -cp <snapshot classpath> <mainClass> @jmh.args`, started by perflab with the JDK the run's `-jvm` names (a campaign's `jvm`), else the build's. Everything else stays as it is today: `jmh.args`, the single `-jvmArgsAppend`, the checks, the timeline and the transcript. What changes:

- loadgate's root is perflab's own process, and nothing of the build is running during a cell.
- The launcher's output comes straight to the transcript.
- The launcher gets the build's `javaOptions`, as `Jmh/run` gave them; JMH passes them on to its forks, before perflab's `-jvmArgsAppend`, as it did under sbt.

## Why not …

- **An uber-jar per build (`Jmh/assembly`).** Assembly is slow for the compiler, loses directory classpaths that tools such as the agent's `def-costs.hooks` resolve, and the snapshot copy already gives immutability.
- **Keep sbt, pin the environment in a `.sbt` file.** That fixes the environment, but not the recompiles mid-campaign, the server's JVM or the per-build servers.
- **Bloop or a Coursier-launched classpath.** Either would add a dependency only to get a classpath sbt already computes.

## Prior art

JMH's own uber-jar workflow (`java -jar benchmarks.jar`) separates build and run the same way. scala/compiler-benchmark exports the classpath from sbt and runs JMH outside it. Gradle's `jmh` plugin forks the JMH runner as a separate process from a resolved classpath.

## Work

1. The `perflabLaunch` sbt task: done in the scala3 lab; the scala2 lab and `examples/sample` to follow.
2. `[build] launch` and `mode = "launch"`: run the step, snapshot the build, launch directly, in `run` and `ab run`. Done. A run snapshots into `<run>/.build`, a campaign into `<campaign>/.build`, once, reused when it resumes.
3. `"builds"` in campaign specs: done, a snapshot per variant in `<campaign>/.build/<variant>`, each cell checked to have run from its variant's snapshot. While a build step runs, the index shows it live (`<campaigns>/build.json`: the command, elapsed time, the log's last lines); a panel on the campaign card listing its builds' commits is still to do. First used on scala/scala3#27357 (`labs/scala3/campaigns/pr27357.json`).
4. Retire `trees` once `builds` covers it, or keep it for builds that need different lab code.

