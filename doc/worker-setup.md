# Setting up a worker machine

A worker runs the campaigns of its testbed that are queued on a coordinator (the `perflab server` where campaigns are submitted and read). Why and how it works: [remote-workers.md](remote-workers.md). The steps below set up a Mac; another Unix needs the same pieces.

## On the worker

1. **perflab.** Python 3.11 or later and git. perflab has no dependencies beyond the standard library:
   ```bash
   git clone https://github.com/retronym/jvm-perf-lab ~/code/jvm-perf-lab
   ```
   ```bash
   uv tool install --editable ~/code/jvm-perf-lab/python
   ```
   This checkout only provides the `perflab worker` command. Each job runs the coordinator's own perflab and lab, from the harness worktree the worker checks out (`~/.perflab/worker/harness/<repo>`), so the worker's checkout need not be kept current.

2. **JDKs.** Install, with SDKMAN, the JDKs the campaigns name in `"jvm"`, under the same candidate names as on the coordinator: a worker finds one by its `release` file (version and vendor) in SDKMAN's candidates and `/Library/Java/JavaVirtualMachines`. A job that names a JDK the worker lacks fails at once, with the `sdk install` line to run.
   ```bash
   sdk install java 25.4.4.1+1-graal
   ```
   ```bash
   sdk install java 21.0.12+1.1-tem
   ```
   A JDK that SDKMAN does not have (a patched build) is copied over and mapped in `[jdks]` of `~/.perflab/worker/worker.toml` (below). Set `JAVA_HOME` for the build tool (sbt) in the environment the worker runs in, as on the coordinator.

3. **Build tools** the lab's `[build] launch` uses: for the scala3 lab, sbt (and Coursier's cache fills on the first build). Environment variables the lab reads beyond what the spec sets (the scala3 lab's `SCALA3_BENCHMARKS`) are taken from the worker's environment.

4. **Inputs.** A path in a spec's `jvmArgs`, `lib` or JMH arguments (a corpus, jars in Coursier's cache) is mapped from the coordinator's repository and home to the worker's. When the worker does not have it, it copies it from the coordinator (only paths the job's spec names, under the coordinator's home), to the mapped place. So a corpus made by hand on the coordinator (`labs/scala3/out/corpora/...`) needs nothing here; it is copied once into the harness worktree, which keeps it.

5. **Optional: the kperf helper**, for `async` campaigns with `"kperf"`: build retronym/async-profiler's integration branch at the coordinator's commit (`tools/build/async-profiler/BUILT_COMMIT` there; a helper and its library come from one build), install the helper as a launchd daemon, and give the worker the library, since the harness worktree has no build of its own ([pmu-counters.md](pmu-counters.md)):
   ```bash
   cd ~/code/jvm-perf-lab && mise run tools:async-profiler && mise run kperf:install
   ```
   ```bash
   export ASYNC_PROFILER_LIB=~/code/jvm-perf-lab/tools/build/async-profiler/build/lib/libasyncProfiler.dylib
   ```

6. **Its testbed name.** By default the CPU's (`Apple M4 Pro` → `m4-pro`); `testbed` in worker.toml (below) chooses another.

## The connection

The coordinator's server listens on 127.0.0.1 only. A reverse SSH tunnel from the coordinator gives the worker its port as a local one; the worker needs no access to the coordinator:
```bash
ssh -N -R 8690:127.0.0.1:8690 <worker host>
```
The worker authenticates with the coordinator's token:
```bash
ssh <worker host> mkdir -p .perflab/worker
```
```bash
scp ~/.perflab/server/token <worker host>:.perflab/worker/token
```
For a tunnel that comes back after sleep or a network change, run it under `autossh -M 0 -o ServerAliveInterval=30 -o ServerAliveCountMax=3 ...`.

## Running it

`~/.perflab/worker/worker.toml` (every setting optional; `perflab worker --help` has them all):
```toml
server = "http://127.0.0.1:8690/"
testbed = "m4"
[jdks]
"/Users/me/jdks/jdk26-patched/bin/java" = "/Users/me/jdks/jdk26-patched"
```
Then, kept awake while it waits:
```bash
caffeinate -i perflab worker
```
It polls the queue every 10 s. A job it claims shows on the coordinator's queue page with the worker's name and testbed, with its transcript as it runs; pause and cancel there take effect at the next cell, as for a local job. If the worker stops answering for 90 s (the laptop slept, the tunnel dropped) the job goes back on the queue, and the next claim resumes it from the cells already uploaded.

## Submitting to it

On the coordinator, a campaign spec says where it runs:
```json
"testbed": "m4"
```
`perflab ab run <spec>` queues it on the server as usual; only a worker of testbed `m4` claims it. Its builds' checkouts must be committed (a dirty one is refused when it is queued); unpushed commits travel as git bundles. Results land in the coordinator's campaign directory, and only cells of the campaign's testbed count in its summaries, comparisons and branch views. Absolute numbers from two machines are not comparable, so compare variants within one testbed.

What stays on the worker: builds (`.build` snapshots) and worktrees, under `~/.perflab/worker` and the harness's `out/`; delete them there when space runs short.
