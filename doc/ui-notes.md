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

## Plan

### Direction

One look across the four pages (index, timeline, site landing, profdiff compare), from one module (`perflab/ui.py`) that each page inlines, so every page stays a single dependency-free file that works from `file://` and under `perflab serve`:

- **Tokens, light and dark.** The existing palette, as CSS variables, plus status colours that also work in dark mode (today's badges stay pastel on dark). System font; tabular figures; numbers right-aligned.
- **Cards with a header row.** A card's title, its date and status chip on the left; its links (timeline, graphs, logs) as small buttons on the right. Facts on one muted line under it.
- **Quiet tables.** No empty columns, units in headers (`µs/op`), horizontal scroll inside the card on a phone instead of the page.
- **Help on demand.** Explanations move into `?` popovers and link tooltips; what stays on the page is one short line.
- **Graphs in a lightbox.** A link to a flame graph opens it in an overlay over the page: a bar of chips for the other graphs of the same run, cell or diff (event × kind), `↗` to open the current one in a new tab, `[` / `]` to step, Esc to close. The page under it (scroll, filters, open details) is untouched. Index run cards, campaign cells, campaign diffs, the site's runs and the compare page's widgets all use it.
- **Phone.** A viewport meta on every page, the filter bar wrapping into labelled groups, the timeline's label column narrower.

Out of scope: the flame graph pages themselves (retronym/async-profiler's jfrconv); see the follow-ups at the end.

### Steps

1. DONE `site.py`: a run with an empty result.json (interrupted) no longer stops the site build.
2. DONE `ui.py`: shared tokens (light and dark), base CSS, `?` popovers and the lightbox; every page inlines it and has a viewport meta.
3. DONE Index cards: run and campaign headers with link buttons; facts line; tables without empty columns, params folded into the benchmark cell, units in headers (`µs/op`); a campaign cell's timeline and graphs on a row beneath it; anchors per card (`#run-<name>`, `#c-<name>`); summary and cells tables captioned; spec versions collapsed.
4. DONE Index chrome: filter bar grouped (corpus / show / updated / text); the graph-kind legend in a `?` popover and the buttons' tooltips; the timeline picker names runs and cells alike (grouped), with the running fork as a status chip ("running since 16:16:01", or "<name> running" to jump to it).
5. DONE Lightbox: timelines, flame graphs and diffs on the index and the site open in it; a refresh of the index keeps opened details; the compare page's widgets have `↗` and `⤢`.
6. DONE Timeline drawing: measurement in the legend; start/exit hatched and labelled; every bar labelled where it fits (unit under the lane name); gaps between iterations dashed and named (xctrace attaching); the exit bar says it includes xctrace saving the trace; "none" in empty lanes; baseline, mid line and scale per counter lane; fits a phone.
7. DONE Timeline page: titled by run (or cell) name, with benchmark, parameters, profile and date; one line of help plus `?`.
8. DONE Site landing: runs as cards with buttons; graph totals in short form; PMU table styled to match; one number format everywhere (scores to four significant digits with separators, counts per op as K/M/G).

Deferred, with reasons:

- **Lanes that share a scale.** No two counter lanes share one today: each is scaled to its own peak, since a shared scale would flatten GC and JIT against the benchmark thread. The `?` says each lane has its own scale; a shared-scale mode is future work if a comparison across lanes is wanted.
- **The exit bar drawn differently from JVM time.** The fork's files don't separate the JVM's exit from xctrace saving its trace; the bar is labelled as both. Splitting it needs xctrace's end time recorded in iterations.tsv.
- **Live timeline of an xctrace run.** The index's panel fetches `timeline.tsv`, but xctrace runs write `<trace>.timeline.tsv` per fork, so live counters show only on the static page (pre-existing, not a UI change).
- **Linked controls in the lightbox.** The compare page relays a graph's toolbar state to its siblings; the lightbox shows one graph at a time, so it doesn't.

### Follow-ups for retronym/async-profiler (integration-kperf-flamegraph)

The "Flame graphs" notes above: open the bench graph zoomed to the benchmark method (or fold the JMH harness frames), dock the span panel and collapse it by default, header tooltips for the span columns, toolbar tooltips and labels, plain-language titles. The lopsided span split is the sample's benchmark, in this repo, not the flame graph.
