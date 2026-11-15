# Always-on observability

Every campaign cell records, besides its results, a few cheap things about the fork it ran, so that a fork that came out slow or fast can be explained after the fact from data rather than guessed at. None of them needs a profile, root, or a change to the benchmark. Each costs well under 0.1% of a core.

| file | what | from |
|---|---|---|
| `os.jsonl` | the fork as the OS sees it, every 0.5 s | `perflab osprobe sample`, a process beside the fork |
| `os.json` | the same over the measured iterations, and per iteration | `osprobe.summary`, when the cell finishes |
| `safepoint.log` | every safepoint, with time to reach it and time in it | `-Xlog:safepoint` |
| `jit-events-<pid>.tsv` | every compilation and deoptimization of the fork | `JitProfiler` (it streams them anyway) |
| `gc.log`, `load.tsv`, `iterations.tsv` | as before | |

## What osprobe records

`osprobe` finds the JMH fork among the campaign's descendants and samples it from outside:

- **Process counters**, `proc_pid_rusage(RUSAGE_INFO_V6)`, cumulative: CPU time, instructions and cycles, and how much of each ran on the top core tier (the Super cores of an M5 Pro, the P cores of an M4); time spent runnable but waiting for a core; energy; time waiting on page faults.
- **CPU time per thread group** (bench, jit, gc, other), by the threads' names, from `proc_pidinfo`.
- **Each core class's busy share for the whole machine**, from `host_processor_info`: whether the top tier was full, and with whose work.

`os.json` interpolates the cumulative values at each iteration's start and end and sums over the measured iterations. The cell's metrics show it as `os:` metrics:

| metric | meaning |
|---|---|
| `os:topTier%` | the fork's CPU time on the top core tier |
| `os:runnable%` | time its threads were runnable but waiting for a core, as % of its CPU time: contention |
| `os:GHz` | cycles over CPU time, all threads |
| `os:energy` | joules per op |
| `os:pageWait` | ms waiting on page faults over the measured iterations |
| `os:busy:<class>` | that core class's busy share for the whole machine |
| `os:cores:<group>` | cores' worth of CPU each thread group used |

These are per process, not per thread. A thread's core class at a given moment can only be read by the thread itself (`pthread_cpu_number_np`), which would need code in the benchmark's threads. An `xctrace:ipc` profile has it per thread: `threads.txt` shows each thread's time on each core class and its clock there, and `xctrace.bench.share.<class>` the benchmark threads'.

`perflab osprobe now [pid]` prints one sample, and the machine's core classes, for a quick look.

## Reading a slow fork

- **Low `os:topTier%` against its siblings:** its threads ran more on the slower cores. Compare `os:busy:<top class>`. If that is high, something else held the top tier: GC threads (`os:cores:gc`) or other processes (`load.tsv`). If it is low, the scheduler placed the threads there anyway.
- **High `os:runnable%`:** there were more threads ready to run than cores.
- **Same placement, more instructions per op:** the fork did more work. Look at `jit-events-<pid>.tsv` (a different compile trajectory) and `gc.log`.
- **A long pause that isn't a GC:** see `safepoint.log`.
