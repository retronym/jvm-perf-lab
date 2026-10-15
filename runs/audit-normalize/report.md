### counters

| audit-normalize/audit-12402.json | of its name | counter |
|---|---|---|
| 1510000 | 99.0% | `normalize.count` |
| 15100 | 1.0% | `normalize.lookup` |

### normalize-sites: 1525100 hits, sites sampled 1 in 100, 2 distinct by site

| audit-normalize/audit-12402.json | share | |
|---|---|---|
| 15344 | 99.0% | `sample.WordCount.count:19 <- sample.WordCountBenchmark.countAndLookUp:66` |
| 158 | 1.0% | `sample.WordCount.contains:24 <- sample.WordCountBenchmark.countAndLookUp:67` |
