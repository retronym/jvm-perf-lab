# UI notes: de-uglifying the index and site

Observations from watching `mise run site` build the sample (live index at `perflab serve`, then the static site). Each item says what is wrong and a proposed fix.

## Live index (`campaigns/index.html`)

- **Filter row mixes kinds under a wrong label.** `corpus:` precedes chips that are not corpora (`profiled`, `timing only`, `with notes`), followed by time chips (`last 24 h`, `last 3 h`) and a text filter, all the same style. Group them as kind / time / text, with the label matching each group, or drop the label.
- **A legend paragraph sits above everything.** "bench: benchmark threads · reverse: by leaf · …" is jargon that the reader meets before any result. Move it to tooltips on the graph links, where it is needed, or a collapsed "graph kinds" note.
- **Timeline picker leaks paths, and its label changes format.** The select reads `running: ../runs/wordcount-async`, then `../runs/wordcount-xctrace-ipc/` (trailing slash), then `run · wordcount-xctrace-ipc` for the same run as it progresses. Show the run's name in one format, and the status as a chip. "follow the running fork running since 15:57:48" says running twice.
- **The legend omits measurement.** Measurement iterations are blue, but the legend lists only warmup and "JVM start / exit", whose swatch is the same grey as warmup.
- **Unexplained gaps in the timeline.** An xctrace run shows 3 s of nothing between warmup and measurement (xctrace attaching). Draw it as a labelled span ("profiler attach") so it does not read as missing data.
- **Iteration bars lack units, and two greys mean different things.** The bar label `3488.9` has no unit (µs/op). Warmup bars and the JVM start/exit bar are near-identical greys; give start/exit a distinct marker (a thin tick or hatch).
- **Empty lanes are silent.** "GC pauses" with no pauses looks like a rendering failure; say "none" in the lane.
- **Hint text under the timeline is long** ("Iterations appear as they finish; counter lanes once …"). One short line, or a `?` tooltip.
- **Results tables show empty columns.** An async run's table has `params` (empty, though the parameters are on the line above), `cycles/op (xctrace)` and `instructions/op` (empty without xctrace). Hide columns with no values; fold parameters into the benchmark cell. `us/op` should be `µs/op`.
- **Run card is sparse.** "timeline" is a bare link at the bottom, and the card is mostly whitespace. Put links (timeline, graphs, jmh.log) on one row as small buttons beside the title.
- **Open flame graphs in a lightbox, not by navigating away.** Clicking a graph link and coming back with Back loses the reader's place on the index (scroll position, expanded cells, filters). Show the graph in an overlay on the index instead, with a small bar above it to cycle through the cell's other graphs (event × kind as chips or tabs: cpu bench / reverse / classify, alloc …, diffs), and an expand icon that opens the current graph in a new tab. Esc closes the overlay and leaves the index where it was. The same viewer would serve the run cards, the campaign cells and profdiff's compare page.

## Campaigns (live index)

- **Wrong unit in the summary (bug).** `maps-async` is in µs/op (`ab` logs `4493.5 ± 1180.1 us/op`), but the summary and cell tables head the column `ms/op`. Take the unit from the result, as the run cards do. The paired `maps` campaign heads the same metric `score` instead: one name, with its unit.
- **Two stacked tables with different columns.** The summary (corpus, variant, n, ms/op, Δ, cycles/op, Δ, …) sits directly above the cell table (corpus, variant, ms/op, cycles/op (xctrace), …), mostly empty columns in both for an async campaign. Show only metrics the campaign has; make the cell table a collapsed "cells" section under the summary.
- **Spec versions take space when there is one.** A one-entry "Spec versions" list on every campaign; show it only when there are several, or as one line ("spec 2026-10-20 16:05").
- **Δ cells wrap.** `+3.19% ± 6.67` breaks across lines; keep it on one line (`white-space: nowrap`, smaller ± part), and colour the sign by better/worse with an "inconclusive" grey when the spread crosses zero.
- **Paired cells are named `paired #1`, `paired #2`.** Say what a cell is: fork 1, fork 2 of the paired run, with the variants it alternates.
- **Per-variant values are crammed into one cell.** `hash 0.3MB · linked 0.4MB · tree 0.3MB` in the alloc/op cell of a paired cell; use sub-rows or a small inline table.
- **Percent changes of near-zero values.** `memory-paired`'s alloc/op is `0.0MB` for both variants and the Δ is `+22227% ± 13047`. Below a noise floor (or when both values round to zero), show the absolute values and no percentage.
- **"Δ per fork (median)" is unreadable.** Cells like `+26071.78 (+25611.72) +10837.13 (+8346.75)` pack two forks' means and medians into one string. Show per-fork values as small dots on a strip, or in a tooltip, and keep the column to the paired mean ± spread.
- **The header wraps once corpus chips appear.** The filter input drops to a second line under the chips; let the chips scroll or collapse into a menu so the sticky header stays one line.

## Flame graphs (async-profiler, integration branch)

- **Harness frames dominate the bench graph.** Below `countAndLookUp` sit about 20 frames of JMH stub, reflection, executor and native thread start (`call_stub`, `JavaCalls::…`, `thread_start`), half the graph's height, and the interesting part is a sliver at the top. Open the bench graph zoomed to the benchmark method (or collapse frames below the `_jmhStub` frame into one "JMH harness" frame).
- **The span panel covers the graph.** It floats over the bottom right and hides frames. Dock it as a side or bottom panel that the graph reflows around, collapsed to a one-line summary by default.
- **The span panel's columns are cryptic.** `here`, `root`, `total` need a header tooltip each, or plainer names.
- **Toolbar icons have no labels.** Nine icons plus `100%` and `1:1`; a reader cannot guess them. Add tooltips at least; text labels for the less obvious ones (reverse, classify, frame types).
- **Titles use internal vocabulary.** "wordcount-async: cpu, bench": "bench" means "benchmark threads only". Say so in the title or a subtitle.
- **Sample: the span split is lopsided.** `look up` is 0.0% of samples (100 lookups against 100 000 merges), so the panel shows one span. Either make the look-up part a visible share of the op, or pick a benchmark whose parts are comparable, so the demo shows what the panel is for.

## Run timeline (`timeline.html`)

- **The title is a path.** `out/runs/wordcount-xctrace-ipc`; use the run's name, benchmark, profile and date, as the index card does.
- **Bar labels are inconsistent.** Only the first warmup iteration shows its score; the other warmups and every measurement iteration are blank, though wide enough. Label every bar that fits, with the unit; tooltip the rest.
- **The exit bar dominates.** "JVM exit" runs from 10.7 s to 18 s (xctrace saving its trace), longer than the measurement. Label what it is, or draw time spent in the profiler differently from time spent in the JVM.
- **Lanes have only a max label.** Each counter lane shows its peak (4.5, 0.5, 17.9) and no baseline or gridline, and each lane has its own scale. A light zero line and a mid gridline would help; mark lanes that share a scale.
- **The explanatory paragraph is dense.** Four sentences above the chart; keep the first, move the rest to a `?`.
