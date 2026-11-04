# The campaign card, rethought

Status: built (index.card_summary, metrics.pooled_delta, the index's SUMMARY_JS).

## The problem

A campaign card answers "is b faster than a?" with one number per variant: the mean over rounds of each round's mean. Everything behind that number takes three clicks or a second table:

- **The distribution is invisible.** Warmup drift, a bimodal JIT outcome, one slow fork, an iteration disturbed by other load: all of these move a mean. None shows until you open a timeline per cell.
- **The statistic is fixed.** Mean is right for throughput, but for single-shot compiler benchmarks the median or the minimum is often the more honest view of "the code's speed", and comparing all three is how you spot a skewed distribution.
- **Summary and cells are two tables.** Corpus × variant rows above, a flat list of cells below, with the same columns again. To see which cells make up a summary row, you match them by eye. Progress (pending, running, interrupted, failed cells) lives only in the lower table, so a half-run campaign's summary row looks the same as a finished one.

## The design

### One table, expandable

Each summary row (corpus × variant) gets a disclosure ▸. Expanding it shows its cells as subrows: one per round (per fork, for a paired campaign), with the cell's own value ± CI, its state badge (done, running, interrupted, failed, pending, void), its spec version, and its links (timeline, flame graphs, logs). Cells not yet run appear as pending subrows, so progress is visible where the numbers are. The separate Cells section goes. `+`/`−` expand or collapse every row; the row stays open across the index's 10 s refresh.

### A statistic switch

A segmented control on the card: **mean · median · min** (perhaps **max** and **p90**). It applies to every value and Δ in the table, the pivot and the chart, and is remembered per viewer, like the view toggle.

- **mean**: two columns for each metric. First what JMH reports for these forks as one run: every iteration pooled, their mean ± t(N−1) × sd / √N at 99.9%, N (JMH's `Cnt`) = forks × iterations, no error with N ≤ 2. Beside it, *over forks*: the mean of fork means ± t(df) × sd / √n. Δ appears under each with its own ±. The better/worse/flat verdict is Welch's t over the pooled iterations, the first column's; the second is coloured by its own interval, and a ⚠ marks a Δ significant by the first and not by the second.
- **median** and **min**: over every measured iteration of the variant's forks, pooled. Δ against the baseline's same statistic. Its interval comes from a bootstrap that resamples forks, then iterations within each fork, so the fork stays the unit of variation as it is for the mean. This is computed when the index is built (milliseconds per row), so the verdict works the same way for each statistic.

### The distribution on hover

Hovering (or focusing) any value opens a small panel:

1. **Run order**: a sparkline of the measured iterations, one segment per fork in its colour. Warmup iterations are drawn faint where iterations.tsv has them. Iterations the load gate flagged as disturbed are marked. This shows drift and outlier forks at a glance.
2. **Against the baseline**: a strip plot of this variant's iterations and the baseline's on one axis, with ticks at min, median, mean and max. This shows a shift, a widening, or a second mode.
3. **The numbers**: n (forks × iterations), min, p25, median, mean, p75, max, and the CV.

Hovering a cell subrow shows the same panel for that one cell. The panel works for every metric with per-iteration data (score, alloc, PMU counters), not only the score.

### The chart view shows distributions

The chart view becomes a box-and-strip plot per variant (per corpus) instead of mean bars with an error whisker. It uses the same data as the hover panel, so what you see in a hover is what the chart lays out side by side.

## Supporting changes

- The card's embedded JSON gains each row's raw iterations per fork per metric, from result.json's rawData, plus warmup and disturbed flags from iterations.tsv and load.json. A large campaign (10 corpora × 3 variants × 5 forks × 30 iterations) adds about 50 kB.
- `metrics.summarise` grows the median and min statistics with their bootstrap interval. The API's Stat gains `median` and `min` beside `mean`, so `compare` can answer with any of them.
- The branch view's commit popover already shows fork means. It moves to the same panel, so the A/B card, the branch history and paired campaigns share one distribution component.

## Decisions

1. Median and min are over pooled iterations. The bootstrap resamples forks, then iterations within each fork, so their spread still treats the fork as the unit of variation. It is the bootstrap's sd of Δ, like the mean's spread over rounds, so the better/worse/flat verdict reads the same for every statistic. The bootstrap is seeded, so a refresh doesn't change it.
2. The default statistic is the mean, so no verdict changes under anyone's feet.
5. JMH's figure comes first because it is the number one recognises and can compare with a JMH run, and because with few forks the interval over forks is unreadable: t(1) = 637 turns a 5 s score into `± 1232%`. The verdict follows it, which takes iterations as independent, while those of one fork share JIT decisions, code layout and GC state: it is usually far narrower and calls many more differences significant. So a value gets a ⚠ when that assumption fails badly, by `metrics.jmh_warnings`: **fork-to-fork variation**, F = k × var(fork means) / var(within a fork) ≥ 10 with the fork means' sd ≥ 1% (JMH's ± then understates by about √F), and **drift**, the later half of a fork's iterations against the earlier by ≥ 2% and ≥ 2.5 standard errors. The thresholds come from 88 rows of real campaigns with several forks: median F 6, F > 4 in 61% of them, so a warning at the mere presence of variation would be on most rows. The API's `verdict` follows JMH everywhere, with `forkVerdict` beside it. A one-fork commit in a branch's history has nothing to warn with, as its forks can't be compared, and there JMH's test flags steps that can't be real: in `m4-branch-int148-scala`, alloc/op moved significantly on 2 of the 3 commits touching only tests or docs, and score on none of them. So the history shows such a verdict with its ⚠, and `changes` lists the step under `untested`, with one fork on either side, rather than as a change. `metrics.jmh_score` is checked against JMH 1.37's `RunResult.getAggregatedResult`, and the API has it as `Stat.jmh` and `Delta.jmh`, leaving `mean`, `ci`, `pct` and `halfWidth` as they were. A paired campaign's table stays over forks, as its variants share forks.
3. The pivot view is gone. The chart's second scale is the distribution (box p25–p75, whiskers min–max, median line, mean dot, every iteration beneath). A paired campaign, whose cells are forks shared by every variant, keeps its own summary and cells table and the chart's absolute scale.
4. The API's Stat has `median` and `min` (pooled, as on the card) beside `mean`, in `campaign` and `compare`. Their Δ stays on the card for now.
