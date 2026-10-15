# PMU counters on Apple Silicon

Two ways to read the CPU's performance counters (cycles, instructions, cache and branch misses) for a JMH benchmark on macOS:

| | `XctraceProfiler` (JMH profiler, `xctrace`) | async-profiler with kperf events |
|---|---|---|
| Question | How many cycles, instructions, misses per op? Did a change move them? | Which code do the cycles, instructions, misses come from? |
| Output | Counts per op, IPC, misses per 1000 instructions, Apple's top-down split; per variant in a paired fork; a 50 ms timeline | Flame graphs per event, from one JFR recording of several events |
| Threads | Benchmark threads, JIT, GC and other threads reported separately | Any; the site renders benchmark threads, all threads, and by category |
| Stacks | Leaf method only (`methods.txt`) | Full Java stacks, inlined frames included |
| Needs | Xcode | retronym/async-profiler's integration branch, a helper running as root, `-XX:+PreserveFramePointer` |
| Profile | `xctrace:<template>` | `async:<event>+<event>...` with `--kperf <socket>` |

## When to use which

Use `XctraceProfiler` to measure. Instructions and cycles per op on the benchmark thread vary much less than time per op, so they show small changes that `ms/op` hides under noise. In a paired campaign, each variant gets its own counts and a paired difference. The timeline shows what else ran during the fork: GC, JIT, other processes.

Use kperf events to locate. Once the counts show that a change moved cycles or misses, a kperf flame graph of that event shows which methods are responsible. `cache-misses` and `branch-misses` are charged to the load or branch that caused them.

The sample site has both for each benchmark: a `<benchmark>-xctrace-ipc` run, and a `<benchmark>-kperf` run of cycles and the miss event the benchmark is about (`cache-misses` or `branch-misses`). The paired campaigns `memory-paired` (`mem-l1d`) and `branch-paired` (`ipc`) compare both settings of a benchmark within one fork.

## XctraceProfiler

```bash
perflab run --profile xctrace:ipc -- <jmh args>
```

The profiler starts `xctrace record --attach` on its own fork before the first measurement iteration and stops it after the last, then splits the samples by thread. Templates:

- `ipc`: cycles, instructions, branches, branch mispredicts
- `frontend`: cycles, instructions, L1I misses, iTLB misses
- `mem-l1d`: cycles, instructions, L1D load misses, cycles the load/store unit waits on an L1D miss
- `CPU Counters` (Instruments' stock template): the top-down split per thread group (useful, processing, delivery, discarded)

`make_template.py`, beside the bundled templates, makes others with four events of your choice (names in `/usr/share/kpep/*.plist`).

Results go into JMH's secondary results (`xctrace.<event>` per op, `xctrace.IPC.<group>`, ratios), so they appear in `result.json`, campaign reports and the index.

## async-profiler kperf events

```bash
mise run tools:async-profiler
sudo tools/build/async-profiler/build/bin/asprof-kperf -s /tmp/asprof-kperf.sock
perflab run --profile async:cycles+instructions+cache-misses+branch-misses --kperf /tmp/asprof-kperf.sock -- <jmh args>
```

The helper programs the counters (which needs root) and serves PMU samples to profiled JVMs that connect to its socket. Events joined by `+` are recorded in one session into one JFR; `jfrconv --hw <event>` renders each. Counts are user mode only, so time spent in the kernel does not appear. Upstream async-profiler has no hardware-counter events on macOS.
