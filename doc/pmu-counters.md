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

### How counts are charged to threads

In xctrace's counters-profile table each sample's counts are the deltas since the previous sample on the same core, not on the same thread. Besides the timer samples (one per busy core per period, all cores at one phase) the table has context-switch samples, and their labels are unreliable: a sample labelled with the kernel's idle thread often carries the work of the thread that ran before it. Crediting each delta to its sample's label therefore loses work to "idle". Measured on scala2-lab cells, the labelled attribution's benchmark instructions per op were low by:

| cell | benchmark threads | low by |
|---|---|---|
| m4, scala and re2s corpora | 1 | 0.6–1.5% |
| m5-pro, scala corpus | 1 | 6% |
| m5-pro, scala corpus | 6 | 36% (108G reported, 168G done) |
| m5-pro, scala corpus | 8 | 29% (121G reported, 169G done) |

JIT, GC and other threads were under-counted more (7–200%).

So the profiler charges counts by time on core × rate, separately for each core class:

- time on core: a thread's timer samples × the sampling period;
- rate: the counts of intervals whose two ends, on one core, name the same thread, over the intervals' length;
- core class: Apple's cores run the same code at different rates (Super vs Performance on an M5 Pro, P vs E on an M4), and a thread's mix of them differs by fork, so each class's time is multiplied by that class's rate.

This applies to the per-op results, the per-iteration (paired) results, `threads.txt` and the timeline. `methods.txt` still splits the labelled samples by their leaf method, which is fine for shares within the benchmark thread. `xctrace.labelled.INST_ALL` keeps the old attribution's instructions per op, for comparing with earlier campaigns. To re-attribute an older trace: export its table (`xctrace export --input <trace> --xpath '/trace-toc/run[@number="1"]/data/table[@schema="counters-profile"]' > t.xml`), then run `io.github.retronym.perflab.xctrace.Reattribute t.xml <pid> <measured ops>` from perflab-jmh's test classes.

Where the benchmark ran: `xctrace.bench.share.<class>` is its share of time on each core class (`S`, `P`, `E`), and `xctrace.bench.GHz.<class>` the clock while it ran there. `threads.txt` shows the same per thread. With more benchmark threads than top-tier cores, the share on the slower class moves the score (see `labs/scala2` campaign `m5-forkvar-t8-contention`).

## async-profiler kperf events

```bash
mise run tools:async-profiler
sudo tools/build/async-profiler/build/bin/asprof-kperf -s /tmp/asprof-kperf.sock
perflab run --profile async:cycles+instructions+cache-misses+branch-misses --kperf /tmp/asprof-kperf.sock -- <jmh args>
```

The helper programs the counters (which needs root) and serves PMU samples to profiled JVMs that connect to its socket. To keep it running, across logins and reboots, without a terminal held open, install it as a launchd daemon: `mise run kperf:install` copies the built helper to `/usr/local/libexec` (root's own copy: root never runs a binary your user can rewrite), and runs it at `/tmp/asprof-kperf.sock` for your user, restarted if it dies, logging to `/tmp/asprof-kperf.log`. Run it again after rebuilding async-profiler; `mise run kperf:uninstall` removes it. (`sudo -b` over ssh does not do: the helper dies with the session's pty.) Events joined by `+` are recorded in one session into one JFR; `jfrconv --hw <event>` renders each. Counts are user mode only, so time spent in the kernel does not appear. Upstream async-profiler has no hardware-counter events on macOS.

### Choosing a sampling period

Each event takes a sample every `period` occurrences: `cycles@2000000`, or `cycles@2000000+cache-misses@50000` for several. Choose the period for a number of samples per fork, not for a rate. A profdiff or a flame graph needs about 50–100k samples of an event per fork; more add nothing but size, and the size is paid in the JFR, in every graph rendered from it and in the collapsed stacks perflab reads from it (a compile sampling L1D misses at async-profiler's default of 10,000 took about a million samples per fork, and its collapsed stacks ran to gigabytes). So:

period ≈ (events per op × ops per fork) / 100,000

Read the events per op from a counter run first: an `xctrace:ipc` run gives cycles and instructions per op, `xctrace:mem-l1d` L1D load misses, and a template of your own any other event (`perflab api campaign` or the run's `result.json`, `xctrace.<event>` in `#/op`). The ops per fork are the measurement iterations in single-shot mode, or about the iteration time over the time per op otherwise. For example, a compile of 22G cycles and 470M L1D load misses per op, measured for 16 ops: cycles at 22G × 16 / 100k ≈ 3.5M, L1D misses at 470M × 16 / 100k ≈ 75k.

An event the profile gives no period gets perflab's default for it, sized for a fork of about 10^11 cycles (25 s of one busy core):

| Event | Default period | Rule of thumb |
|---|---|---|
| `cycles`, `CORE_ACTIVE_CYCLE` | 2,000,000 | 10^6–10^7 |
| `instructions`, `INST_ALL` | 5,000,000 | 10^6–10^7 |
| other `INST_*` (a kind of instruction), events counting cycles while stalled | 1,000,000 | |
| `cache-misses`, `L1D_CACHE_MISS_*` | 50,000 | ~10^5 for a compiler-sized workload |
| anything else: L2 and memory-system misses, TLB misses, branch mispredictions, L1I misses | 20,000 | ~10^4 |

A short benchmark takes fewer samples at these and may want a smaller period; a long or memory-bound one, a larger. After each cell of a campaign, perflab reads the helper's sample counts from the fork's log (`kperf: <event>: N samples`), keeps them in the cell's `kperf-samples.json`, and warns, in the campaign's log and on its card in the index, of an event over 500k samples per fork, with the period that would have taken about 100k.
