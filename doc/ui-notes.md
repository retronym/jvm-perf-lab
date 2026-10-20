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
9. DONE Campaigns (second round of notes): the score column named by its unit everywhere (the `ms/op` bug was already fixed by step 3); cells in a Cells section under the summary; one line for a single spec version; Δ on one line, coloured by better/worse beyond the spread, grey when inconclusive, a dash when both values are about zero; paired cells named as forks with the variants they alternate; per-variant allocation stacked; the header on one line with scrolling chips; `perflab ab report`'s per-fork differences in a table of their own.

Deferred, with reasons:

- **Lanes that share a scale.** No two counter lanes share one today: each is scaled to its own peak, since a shared scale would flatten GC and JIT against the benchmark thread. The `?` says each lane has its own scale; a shared-scale mode is future work if a comparison across lanes is wanted.
- **The exit bar drawn differently from JVM time.** The fork's files don't separate the JVM's exit from xctrace saving its trace; the bar is labelled as both. Splitting it needs xctrace's end time recorded in iterations.tsv.
- **Live timeline of an xctrace run.** The index's panel fetches `timeline.tsv`, but xctrace runs write `<trace>.timeline.tsv` per fork, so live counters show only on the static page (pre-existing, not a UI change).
- **Linked controls in the lightbox.** The compare page relays a graph's toolbar state to its siblings; the lightbox shows one graph at a time, so it doesn't.

### Follow-ups for retronym/async-profiler (integration-kperf-flamegraph)

The "Flame graphs" notes above: open the bench graph zoomed to the benchmark method (or fold the JMH harness frames), dock the span panel and collapse it by default, header tooltips for the span columns, toolbar tooltips and labels, plain-language titles. The lopsided span split is the sample's benchmark, in this repo, not the flame graph.

## Plan: one page, branded

Feedback on the rebuilt sample site: the landing page is plain, with no branding, and the split between the landing page (runs, counters) and the campaigns index is confusing. Two layout bugs at 800px: the header's last chip is clipped, and branch-paired's summary is cut off on the right with no sign that it scrolls.

### Direction

- **One page, two homes.** `index.build` renders the whole page: the intro when one is given, campaigns, runs and the counters table. `perflab serve` keeps serving it at `<campaigns>/index.html` (the same URL). `perflab site` renders the same page at the site's root, with `--intro-file`. The site's `campaigns/index.html` becomes a redirect to it, so old links keep working. site.py keeps copying and packaging; its landing-page code moves into index.py, and its run-card extras merge into the index's run cards: the about-this-profile line, the secondary metrics, hot methods, threads, the audit report page and graph totals.
- **Navigation.** A sticky bar with section tabs: Overview (only with an intro), Campaigns n, Runs n and Counters n. They are anchors, and the current one is highlighted as you scroll. Under the tabs, one filter bar for the whole page: benchmark, tool, corpus, show (profiled / with notes / last 24 h) and text. It wraps onto a second line instead of clipping. The fork timeline panel shows only while something runs; otherwise every card's timeline button opens it in the lightbox. The lightbox is unchanged.
- **Branding.** A dark ink header band carries the mark, an inline SVG of three flame-graph bars in flame orange; the name **jvm-perf-lab** with the project's title after it (`/ sample results`); a tagline; and GitHub and Docs links. One accent colour (flame orange) is used for the active tab, step numbers and idea cards. The timeline and compare pages get a slim version of the band, linking back to the page, and hide it when shown in the lightbox.
- **Designed intro.** `site-intro.html` is restructured into a lead paragraph, idea cards, numbered "Where to start" steps and a glossary of terms, styled by classes the page provides (`.lead`, `.ideas`, `.steps`, `.terms`). Any HTML fragment still works as an intro.
- **Wide tables.** Every table scrolls inside its card, with an edge shadow while there is more to the right. The summary puts each Δ under its value, in the same cell, which halves its columns, so most summaries fit without scrolling.

### Steps

1. TODO Branding: the header band and mark in ui.py, used by the index, timeline and compare pages.
2. TODO One page: index.py renders intro, campaigns, runs and counters; run cards take site.py's extras; site.py renders it at the root and redirects campaigns/index.html.
3. TODO Navigation: section tabs with scroll highlight, the shared filter bar across campaigns and runs, and a timeline panel shown only while something runs.
4. TODO Intro: site-intro.html restructured, with styles for its blocks.
5. TODO Layout: scroll shadows, Δ under value in summaries, and the 800px fixes. Also fix a Δ of +0.00% ± 0.00 shown red (gc campaign).
