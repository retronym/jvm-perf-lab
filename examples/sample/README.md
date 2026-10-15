# Sample project

A JMH project that uses perflab: `WordCountBenchmark` counts the words of a generated text in a `HashMap`,
`LinkedHashMap` or `TreeMap`. `target/benchmarks.jar` has perflab's JMH driver as its main class; `perflab.toml` tells
`perflab` how to run it.

Build it with the rest of the repository (`mise run build`, from the root), then from this directory:

```bash
perflab run -- -p size=10000 WordCountBenchmark
perflab run --profile async:cpu,alloc -- -p size=10000 WordCountBenchmark
perflab run --profile audit:campaigns/normalize.audit -- -wi 1 -i 1 WordCountBenchmark
perflab ab run campaigns/gc.json && perflab ab report campaigns/gc.json
perflab ab run campaigns/maps.json && perflab ab report campaigns/maps.json
perflab index
```

On Apple Silicon with Xcode, `--profile xctrace:ipc` adds PMU counters for the benchmark thread.
