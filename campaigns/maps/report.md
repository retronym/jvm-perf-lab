### maps (paired within forks: hash, linked, tree)

| size | variant | forks | score | Δ (paired) | score excl. GC | Δ (paired) | instructions/op | Δ (paired) | cycles/op | Δ (paired) | alloc/op | Δ (paired) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 10000 | hash | 2 | 205.8 |  | 205.3 |  | – |  | – |  | 0.3MB |  |
| 10000 | linked | 2 | 210.2 | +3.19% ± 6.67 | 209.8 | +3.22% ± 6.63 | – |  | – |  | 0.4MB | +5.14% ± 0.00 |
| 10000 | tree | 2 | 558.8 | +175.67% ± 67.89 | 558.4 | +176.19% ± 68.07 | – |  | – |  | 0.3MB | -4.29% ± 0.00 |

Δ per fork against hash: each fork's mean difference over its iteration pairs (and their median).

| size | variant | metric | per fork |
|---|---|---|---|
| 10000 | linked | score | +7.91% (median +7.91%) · -1.53% (median -1.53%) |
| 10000 | linked | score excl. GC | +7.91% (median +7.91%) · -1.46% (median -1.46%) |
| 10000 | linked | alloc/op | +5.14% (median +5.14%) · +5.14% (median +5.14%) |
| 10000 | tree | score | +223.67% (median +223.67%) · +127.66% (median +127.66%) |
| 10000 | tree | score excl. GC | +224.32% (median +224.32%) · +128.05% (median +128.05%) |
| 10000 | tree | alloc/op | -4.29% (median -4.29%) · -4.29% (median -4.29%) |
