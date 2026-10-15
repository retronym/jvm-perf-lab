### maps-async

| corpus | variant | us/op (per round) | mean | Δ | instructions/op (per round) | Δ | cycles/op | Δ | IPC | alloc/op | GC time |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 100000 | hash | 3145 ± 1.1e+02 | 3145 |  |  |  | – |  | – | 3 MB | 0.0 s |
| 100000 | tree | 1.14e+04 ± 4.2e+02 | 1.14e+04 | +262.5% |  |  | – |  | – | 3 MB | 0.0 s |

Flame graphs: ~/code/retronym/jvm-perf-lab/examples/sample/out/campaigns/maps-async/index.html
