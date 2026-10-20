### maps-counters (paired within forks: hash, linked, tree)

| size | variant | forks | score | Δ (paired) | score excl. GC | Δ (paired) | instructions/op | Δ (paired) | cycles/op | Δ (paired) | alloc/op | Δ (paired) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 100000 | hash | 1 | 3,381 |  | 3,376 |  | 41.9M |  | 13.5M |  | 3.4MB |  |
| 100000 | linked | 1 | 3,552 | +5.05% ± 0.00 | 3,545 | +5.02% ± 0.00 | 44.1M | +5.11% ± 0.00 | 14.1M | +4.41% ± 0.00 | 3.6MB | +5.29% ± 0.00 |
| 100000 | tree | 1 | 14,036 | +313.52% ± 0.00 | 14,030 | +314.02% ± 0.00 | 104M | +148.11% ± 0.00 | 51.2M | +278.57% ± 0.00 | 3.3MB | -2.46% ± 0.00 |

Δ per fork against hash: each fork's mean difference over its iteration pairs (and their median).

| size | variant | metric | per fork |
|---|---|---|---|
| 100000 | linked | score | +5.05% (median +4.83%) |
| 100000 | linked | score excl. GC | +5.02% (median +4.72%) |
| 100000 | linked | instructions/op | +5.11% (median +5.54%) |
| 100000 | linked | cycles/op | +4.41% (median +4.69%) |
| 100000 | linked | alloc/op | +5.29% (median +5.29%) |
| 100000 | tree | score | +313.52% (median +272.63%) |
| 100000 | tree | score excl. GC | +314.02% (median +273.74%) |
| 100000 | tree | instructions/op | +148.11% (median +135.27%) |
| 100000 | tree | cycles/op | +278.57% (median +268.51%) |
| 100000 | tree | alloc/op | -2.46% (median -2.46%) |
