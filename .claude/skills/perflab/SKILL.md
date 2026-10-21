---
name: perflab
description: Run, check and report JMH benchmarks through perflab (jvm-perf-lab) - `perflab run`, `perflab ab` campaigns, profiles (async, xctrace, audit), JVM arguments, JDK choice, variants. Use before starting any benchmark, A/B comparison, campaign or profile in a project with a perflab.toml, and before reporting its results.
---

# perflab

perflab drives a project's JMH benchmarks through the build command in its `perflab.toml` (found from the working directory upward). Read that file first: it sets the benchmark, its parameters, the JVM arguments every run gets, and where results go.

## 1. Give the user the dashboard URL first

Before starting any run or campaign:

```bash
perflab serve
```

Send the user the URL it prints, in your next message, before results exist. It is the same URL every time for a checkout, and the page updates itself as results arrive: there is nothing to regenerate when a run finishes, so never offer to. `perflab run` and `perflab ab run` log the same URL as `index (updates ...): ...`; pass that line on if you didn't run `serve`. Never start another HTTP server for results.

When reporting, link the run or campaign on that page rather than only pasting numbers.

## 2. Dry-run, then read the arguments

```bash
perflab run --dry-run --profile <profile> -- <jmh arguments>
perflab ab run <spec.json> --dry-run
```

This prints the build command and the `jmh.args` file perflab will hand to JMH, one argument per line. Read it before the real run and check: one `-jvmArgsAppend`, the `-jvm` you meant, the `-p` values you meant. A fork that fails to start is almost always visible here.

## 3. JVM arguments: perflab owns `-jvmArgsAppend`

perflab writes exactly one `-jvmArgsAppend`: `[benchmark] jvmArgs` from `perflab.toml` (the heap settings, e.g. `-Xms4G -Xmx4G -Xss2M`) plus its own timeline flags (`-Dperflab.cell=...`, `-Xlog:gc:...`). It replaces the benchmark's `@Fork(jvmArgsAppend)`.

- **Never pass `-jvmArgsAppend` or `-jvmArgs` yourself**, and never repeat the heap flags: perflab already adds them.
- In a campaign, put flags in the spec: `"jvmArgs"` (every variant; replaces `[benchmark] jvmArgs`, so include the heap settings) or `"variants"` (per variant, added to `jvmArgs`).
- For a one-off `perflab run`, use `-jvmArgsPrepend "<flags>"`, as the labs' READMEs do for `-javaagent:`. The async profile with `--kperf` prepends its own flags; check the dry run.
- Values in `jmh.args` are not shell-quoted: `-jvmArgsPrepend` and its value are two lines, the value space-separated flags. Don't add quotes inside it.

## 4. The JDK: `-jvm`, not `JAVA_HOME`

Without `-jvm`, JMH forks the JDK running the JMH driver. With `sbt --client` that is the **already-running sbt server's** JDK: changing `JAVA_HOME`, `mise use` or the shell's `java` has no effect on it.

- `perflab run -- -jvm /path/to/jdk/bin/java ...`, or `"jvm": "/path/to/jdk/bin/java"` in a campaign spec (checked against each result).
- Find JDKs with `/usr/libexec/java_home -V` or `mise where java@<version>`; pass the `bin/java` inside.
- After a run, confirm the JDK in the index's run facts (`JVM ...`) or `result.json`'s `"jvm"`, and say which one it was when reporting.

## 5. Separators: never `;`

sbt splits a typed command at `;`, so `;` must never appear in arguments you type. perflab passes JMH arguments as an `@file`, so you rarely need one; when you do:

| Where | Separator |
|---|---|
| Several values of one JMH parameter: `-p corpus=scalaz,scalap` | `,` (JMH runs each) |
| Options of a profiler: `-prof "async:output=jfr&dir=out"` | `&` (the driver turns it into JMH's `;`) |
| Options within one compiler setting: `-p scalacOptions=-Yx -Yy` | space |
| Variants within a fork: `-p variants=base=\|new=-Yfoo -Ybar` | `\|` between variants, `name=options` each |
| A variant that names a build (scala2 lab): `base=@build=../base\|new=@build=.` | `@build=<checkout>` |

A value cannot contain `,` (JMH splits at it), so neither variants nor `paired` options can. Prefer perflab's profiles (`--profile async:cpu,alloc`, `xctrace:ipc`, `audit:<spec>`) over writing `-prof` yourself.

## 6. Campaigns over ad-hoc runs

To compare things, write a spec under the project's `campaigns/` and run `perflab ab run <spec>`, not a series of `perflab run`s or a shell loop alternating builds. A campaign interleaves variants round by round, is resumable, and checks each cell: fresh results, the JVM, every JVM argument, each variant's `-p` values, counters present. `perflab ab --help` documents the spec fields; `paired` alternates variants by iteration within one fork, which beats fork-to-fork noise (`doc/paired-ab.md`).

Say what the campaign asks and what each variant is: `"description"` and `"variantDescriptions"` (`{variant: ...}`) take Markdown (a string or a list of lines; links to PRs and issues welcome) and show in a panel atop the campaign's card and in `perflab ab report`.

To explain a difference between builds or JIT flags at the level of C2's inlining, run `perflab inlinetree <label>=<cell>... [--baseline <label>] [--event cycles] [--notes notes.json] [--strip <package>]` over an async campaign's cells. It writes `<campaign>/inlinetree-<event>.html`, linked from the campaign's card: each top compiled method, the callees it reaches marked per build as inlined, a real call or both, and cards for the largest differences. `--notes` takes `{method: Markdown}` to annotate rows with what you have found.

Let perflab choose output directories (`--out` is optional; cells go under `[paths] campaigns`). Don't write scripts that assume a directory exists.

## 7. Don't route around perflab

Never write `jmh.args` yourself, call the build's `Jmh/run` directly, or patch perflab's output to get past a failure. A run that bypasses perflab gets no checks, no timeline, no index entry, and its results can't be compared with the rest.

- If a perflab feature fails, turn it off where perflab offers a switch, and say so in your report. For example, if `jfrsync` fails, set `[async] jfrsync = false` in `perflab.toml`, and the timeline then lacks the JDK's event lanes.
- If there is no switch, or the failure looks like a perflab bug, stop and tell the user: the command, the error from `build.log` / `jmh.log`, and the JDK and async-profiler in use. Don't work around it.

## 8. When it fails

| Symptom | Look at |
|---|---|
| Forked VM failed to start | `jmh.args` (duplicate or quoted JVM arguments), then `build.log` in the run's directory |
| `Could not start master JFR recording`, or an async run without a profile | JMH names async-profiler's output directory after the benchmark and every parameter; a long value (an absolute corpus path) takes it over 255 bytes. Shorten the value, e.g. with a symlink. jfrsync and the JDK are not the cause, so don't turn jfrsync off |
| Ran on the wrong JDK | `-jvm` missing: see section 4 |
| Parameter value cut short, or sbt reports an unknown command | a `;` in a typed argument: see section 5 |
| A campaign cell is rejected | the check's message names what differs from the spec; fix the spec, don't bypass the check |
| Profile output missing | `perflab run --help` for the profile's requirements (`--lib`, `--kperf`, `[agent] jar`) |

Each run's directory holds `run.json` (status, exit code), `build.log`, `jmh.log`, `jmh.args` and `result.json`. Read them before re-running.
