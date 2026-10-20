# Sample project

A JMH project that uses perflab. `WordCountBenchmark` counts the words of a generated text in a `HashMap`, `LinkedHashMap` or `TreeMap`. `MemoryBenchmark` walks an int array in order or as a pointer chase through a random cycle. `BranchBenchmark` sums the bytes above a threshold, over sorted or random data. `target/benchmarks.jar` has perflab's JMH driver as its main class; `perflab.toml` tells `perflab` how to run it.

Build it with the rest of the repository (`mise run build`, from the root), then from this directory:

```bash
perflab serve    # the results page; open its URL first
perflab run -- -p size=10000 WordCountBenchmark
perflab run --profile async:cpu,alloc -- -p size=10000 WordCountBenchmark
perflab run --profile audit:campaigns/normalize.audit -- -wi 1 -i 1 WordCountBenchmark
perflab ab run campaigns/gc.json && perflab ab report campaigns/gc.json
perflab ab run campaigns/maps.json && perflab ab report campaigns/maps.json
```

On Apple Silicon, PMU counters ([doc/pmu-counters.md](../../doc/pmu-counters.md)): counts per op for the benchmark thread through `xctrace` (needs Xcode), and flame graphs per event through async-profiler's kperf events (needs `mise run tools:async-profiler` and its helper running as root):

```bash
perflab run --profile xctrace:ipc -- -p size=100000 WordCountBenchmark
perflab ab run campaigns/memory-paired.json
perflab run --profile async:cycles+instructions+cache-misses+branch-misses --kperf /tmp/asprof-kperf.sock -- -p size=100000 WordCountBenchmark
```

`WordCountBenchmark` also marks each op's two parts, counting and looking up, as async-profiler spans with perflab-spans. With the lab's async-profiler build (`mise run tools:async-profiler`), its `bench` flame graphs have a span panel that splits the samples by part (`[async] spans` in `perflab.toml`).

`site.sh` (`mise run site`) runs every benchmark under each profile and its campaigns, then builds the static site: the same results page, with `site-intro.html` as its overview, published by `mise run publish-site` to [retronym.github.io/jvm-perf-lab](https://retronym.github.io/jvm-perf-lab/).
