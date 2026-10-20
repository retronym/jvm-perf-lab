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
