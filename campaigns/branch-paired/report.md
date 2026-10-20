### branch-paired (paired within forks: sorted, random)

| size | variant | forks | score | Δ (paired) | score excl. GC | Δ (paired) | instructions/op | Δ (paired) | cycles/op | Δ (paired) | alloc/op | Δ (paired) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1048576 | sorted | 2 | 283.1 |  | 283.1 |  | 5.89M |  | 1.02M |  | 4B |  |
| 1048576 | random | 2 | 2,387 | +744.41% ± 33.73 | 2,387 | +744.41% ± 33.73 | 6.08M | +3.50% ± 4.06 | 8.43M | +732.45% ± 73.90 | 49B | – |

Δ per fork against sorted: each fork's mean difference over its iteration pairs (and their median).

| size | variant | metric | per fork |
|---|---|---|---|
| 1048576 | random | score | +768.26% (median +740.25%) · +720.56% (median +725.68%) |
| 1048576 | random | score excl. GC | +768.26% (median +740.25%) · +720.56% (median +725.68%) |
| 1048576 | random | instructions/op | +0.63% (median +2.48%) · +6.37% (median +1.42%) |
| 1048576 | random | cycles/op | +680.19% (median +751.63%) · +784.70% (median +742.26%) |
