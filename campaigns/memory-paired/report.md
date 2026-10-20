### memory-paired (paired within forks: sequential, shuffled)

| size | variant | forks | score | Δ (paired) | score excl. GC | Δ (paired) | instructions/op | Δ (paired) | cycles/op | Δ (paired) | alloc/op | Δ (paired) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 4194304 | sequential | 2 | 1,752 |  | 1,752 |  | 22.1M |  | 5.03M |  | 28B |  |
| 4194304 | shuffled | 2 | 345,505 | +18454.46% ± 10772.53 | 345,505 | +18454.46% ± 10772.53 | 71.6M | +248.97% ± 35.30 | 1.01G | +20716.48% ± 12915.31 | 5.4KB | – |

Δ per fork against sequential: each fork's mean difference over its iteration pairs (and their median).

| size | variant | metric | per fork |
|---|---|---|---|
| 4194304 | shuffled | score | +26071.78% (median +25611.72%) · +10837.13% (median +8346.75%) |
| 4194304 | shuffled | score excl. GC | +26071.78% (median +25611.72%) · +10837.13% (median +8346.75%) |
| 4194304 | shuffled | instructions/op | +224.01% (median +5.78%) · +273.93% (median +39.75%) |
| 4194304 | shuffled | cycles/op | +29848.98% (median +29946.10%) · +11583.97% (median +8251.80%) |
