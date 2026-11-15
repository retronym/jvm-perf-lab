# Fork-to-fork variance: the compiler labs' GC settings

The compiler labs (`labs/scala2`, `labs/scala3`) run every fork with a fixed young generation and without adaptive IHOP:

```toml
[benchmark]
jvmArgs = "-Xms4G -Xmx4G -Xss2M -Xmn1536m -XX:-G1UseAdaptiveIHOP"
```

## Why

G1 sizes the young generation from the pause times it has measured so far, and starts concurrent marking at an occupancy it adapts the same way (adaptive IHOP). Pause times differ from fork to fork, so two forks of the same build collect at different points in the same compilation. The GC points move the work: a young GC clears weak references (Scala 2's type `uniques` table is a `WeakHashSet`, so a type collected early is rebuilt, with its per-instance caches, the next time an equal one is made), and it changes which objects are promoted together and so their locality. With `-Xmn` the young generation has one size, so young GCs fall after the same amount of allocation in every fork, and with `-XX:-G1UseAdaptiveIHOP` marking starts at a fixed occupancy.

The evidence is the `m4-forkvar-gc` campaign (m4 testbed, the scala2 perf-integration build `6101d220ca`, the scala corpus, `-f 1 -bm ss -wi 8 -i 6`, an 8 GB heap, xctrace ipc). Fork-to-fork CV with 3 forks per variant, the campaign stopped early:

| variant | time CV | instructions CV | mean time per op |
|---|---|---|---|
| default G1 | 0.70% | 0.29% | 8.37 s |
| `-Xmn3g -XX:-G1UseAdaptiveIHOP` | 0.22% | 0.24% | 8.24 s |
| `-Xbatch` | 0.58% | 0.69% | 8.71 s |
| both | 0.27% | 0.02% (p=0.01) | 8.78 s |

The fixed young generation cut the CV of time to about a third and was not slower (G1 chose about 2.8 GB of young generation by itself here). In `m4-forkvar-hash`, `-XX:hashCode=3` cut the CV of instructions per op from 0.52% to 0.17% (p=0.03).

Three forks per variant is an indication, not a test: a CV from 3 values has 2 degrees of freedom, and one quiet or noisy fork moves it a lot. `labs/scala2/campaigns/m4-forkvar-gc-confirm.json` repeats the comparison with 6 forks per variant (default G1, fixed young generation, and the fixed young generation with `-XX:hashCode=3` or with `-Xbatch`). Run it before relying on the numbers above for more than the default.

## Sizing

The rule is a young generation of 3/8 of `-Xmx`, with `-Xms` equal to `-Xmx`: `-Xmn3g` for an 8 GB heap, as measured, and `-Xmn1536m` for the labs' 4 GB default. 3/8 is close to what G1 picks by itself for the scala corpus at 8 GB, so the fixed size takes away the variation without changing the amount of GC much. At 4 GB, G1 picks a larger young generation for the small corpora (about 2.4 GB for re2s, scalap and dottyUtil, its 60% maximum), so 1536m means more young GCs there; the 4 GB setting follows the rule and has not been measured on its own.

## Campaigns that set their own `jvmArgs`

A spec's `"jvmArgs"` replaces the lab's `[benchmark] jvmArgs`, so most campaigns, which set a larger heap there, do not get the default. Add the same flags, sized by the rule, to such a spec:

```json
"jvmArgs": "-Xms8G -Xmx8G -Xss2M -Xmn3g -XX:-G1UseAdaptiveIHOP"
```

A campaign whose spec has no `"jvmArgs"` records the lab's arguments it started with (`<campaign>/lab-jvmArgs`) and keeps them when resumed, so a change to the lab's default never reaches only its later cells. One that ran before that record existed keeps the default's arguments its first cell ran with.

## When to override it

- **GC or heap-sizing campaigns.** A campaign about allocation rates, promotion, GC pauses or heap size measures what G1's own sizing does with the change. Leave `-Xmn` and `-XX:-G1UseAdaptiveIHOP` out of its spec's `"jvmArgs"`, or vary them as variants.
- **Campaigns judged on instructions per op.** Time is the usual measure, and the default is tuned for it. When the verdict rests on instructions per op (xctrace or kperf counters), add `-XX:+UnlockExperimentalVMOptions -XX:hashCode=3`, so that identity hashes, and with them the iteration order of hash sets of symbols and trees, follow allocation order; or add `-Xbatch` to the fixed young generation, which made allocation nearly deterministic and gave the lowest instruction CV above. Both change the work done, so compare variants that all have them, never one with and one without. `-Xbatch` also slows warmup: give it more warmup iterations (check `jit.compilations` in the measured iterations).
