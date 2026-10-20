### maps-async

| size | variant | us/op (per round) | mean | Δ | instructions/op (per round) | Δ | cycles/op | Δ | IPC | alloc/op | GC time |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 100000 | hash | 3965 ± 4.9e+02 | 3965 |  |  |  | – |  | – | 3 MB | 0.0 s |
| 100000 | tree | 4.077e+04 ± 2.1e+04 | 4.077e+04 | +928.1% |  |  | – |  | – | 3 MB | 0.0 s |

Flame graphs: ~/code/retronym/jvm-perf-lab/examples/sample/out/campaigns/maps-async/index.html
