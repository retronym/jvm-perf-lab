# Paired variants within one fork

A benchmark that can switch between variants between iterations (compiler settings, feature flags, data sets) runs all of them in one fork, alternating by iteration. The variants share the fork's compiled code, so differences in JIT compilation between forks cancel in the comparison.

## Order

Iterations are grouped into cycles of `n` iterations, one per variant. Cycle `k` runs the variants in the order `Variants.order(n, k)`, a row of a Williams design: over `n` cycles (`2n` for odd `n`) each variant runs in each position equally often, and immediately after each other variant equally often. For two variants the order is A B, B A, A B, …. Warmup iterations follow the same order.

## Using it in a benchmark

```java
@Param("") String variants;          // e.g. "base=-Yx|fast=-Yx -Yfast"; JMH splits values at commas, so none in options
Variants vs; int iteration;

@Setup(Level.Trial) public void setup() { vs = Variants.parse(variants); IterationLog.reset(vs.names()); }

@Setup(Level.Iteration) public void next(IterationParams ip) {
    Variants.Variant v = vs.forIteration(iteration++);
    // configure the benchmark for v.options()
    IterationLog.begin(v.name(), ip.getType() == IterationType.MEASUREMENT);
}

@TearDown(Level.Iteration) public void end() { IterationLog.end(); }
```

## Results

`PairedProfiler` (a default profiler of the driver) reports, over the measurement iterations:

| result | meaning |
|---|---|
| `paired.<v>` | mean score of variant `v`, in the benchmark's unit |
| `paired.<v>.delta%`, `.delta%.sd`, `.delta%.median` | per cycle, `100 * (v / first variant - 1)`; mean, standard deviation and median over cycles |
| `paired.gcFree.<v>` and its deltas | the same, with each iteration's GC pause time removed pro rata |

`XctraceProfiler` reports each PMU event per op per variant (`xctrace.<EVENT>.<v>`, with the same deltas). It assigns each counter sample to an iteration by its sample time: the trace records its start to the millisecond and each row its time since then, and `IterationLog` records each iteration's span by the wall clock.

With `-Dperflab.cell=<dir>`, `PairedProfiler` also appends each iteration (span, variant, score, ops, GC pause time) to `<dir>/iterations.tsv` as it finishes.

## Limits

- xctrace credits each core's counter delta since its previous sample to the thread running at the sample. A benchmark thread preempted mid-interval loses part of its counts to the thread that replaced it, so per-iteration counts are reliable only on a quiet machine. In an A/A run with about one core of other load, slow iterations counted up to 10% fewer instructions per op.
- Variants must be switchable within a running JVM. Variants that need different JVM flags or builds run in separate forks.
