### counters

| audit-normalize/audit-71933.json | of its name | counter |
|---|---|---|
| 1840000 | 99.0% | `normalize.count` |
| 18400 | 1.0% | `normalize.lookup` |

### normalize-sites: 1858400 hits, sites sampled 1 in 100, 2 distinct by site

| audit-normalize/audit-71933.json | share | |
|---|---|---|
| 18256 | 99.0% | `sample.WordCount.count:19 <- sample.WordCountBenchmark.countAndLookUp:71` |
| 191 | 1.0% | `sample.WordCount.contains:24 <- sample.WordCountBenchmark.countAndLookUp:74` |
