alloc per op (benchmark threads): a 1.62k, b 159, -90.2%  (ms/op a 3965, b 40770; ops a 6, b 6; a = hash/1, b = tree/1)

self alloc per op, biggest decreases then increases (b − a):

| Δ | a | b | Δ of a's total | method |
|---|---|---|---|---|
| -540 | 599 | 58.3 | -33.30% | `byte[]` |
| -515 | 573 | 58 | -31.73% | `java.lang.String` |
| -350 | 350 | 0 | -21.57% | `java.util.HashMap$Node` |
| -101 | 101 | 0 | -6.23% | `java.util.HashMap$Node[]` |
| +42.3 | 0 | 42.3 | +2.61% | `java.util.TreeMap$Entry` |
| … | | | | |
| +42.3 | 0 | 42.3 | +2.61% | `java.util.TreeMap$Entry` |
| -101 | 101 | 0 | -6.23% | `java.util.HashMap$Node[]` |
| -350 | 350 | 0 | -21.57% | `java.util.HashMap$Node` |
| -515 | 573 | 58 | -31.73% | `java.lang.String` |
| -540 | 599 | 58.3 | -33.30% | `byte[]` |
