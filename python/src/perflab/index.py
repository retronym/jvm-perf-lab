"""<campaigns>/index.html: every campaign and every run of `perflab run` (<runs>), newest first, and a live timeline of
the running fork. A campaign shows a summary and its cells (score, cycles, instructions, flags), links to each cell's
flame graphs (dashed until rendered) and timeline, its differential flame graphs, notes (<campaign>/NOTES.md) and
findings (<campaigns>/FINDINGS.md); a run its benchmark, parameters, JVM, status, scores, and links to its timeline,
logs and flame graphs. Graphs and timelines open in a lightbox over the page (ui.py). `perflab ab` rebuilds it around
each cell, `perflab run` at its start and end, and the page refreshes itself.

  perflab index [<campaigns-dir> [<runs-dir>]]
"""
import glob, html, json, os, re, sys, time

from . import ab, config, regraph, runinfo, specs, timeline, ui

root = None  # the directory of the page being built: its links are relative to it
CAMPAIGNS = None
HOME = None  # the page being built, for the pages it renders to link back to
esc = html.escape
rel = lambda f: esc(os.path.relpath(f, root))


def link(path, label, lb=None, title=None):
    """A small button linking `path`; with `lb` (`<group>|<label>`, or a label alone) it opens in the lightbox, among
    the other such links of its `[data-lb-group]`. Dashed until the file exists."""
    if not os.path.exists(path):
        return f'<span class="btn pending" title="not written yet (flame graphs: perflab regraph)">{esc(label)}</span>'
    attrs = (f' data-lb="{esc(lb)}"' if lb else "") + (f' title="{esc(title)}"' if title else "")
    return f'<a class="btn" href="{rel(path)}"{attrs}>{esc(label)}</a>'


def table(heads, rows, cls="t"):
    """heads: [(html, numeric)]; rows: [(tr attributes, [cell html])], or with a third element, html for a full-width
    row beneath (a cell's graphs). Columns empty in every row are left out."""
    keep = [i for i in range(len(heads)) if any(r[1][i] for r in rows)]
    n = lambda i: ' class="n"' if heads[i][1] else ""
    def tr(attrs, cells, detail=""):
        main = f"<tr{attrs}{' class=\"has-sub\"' if detail else ''}>" + "".join(f"<td{n(i)}>{cells[i]}</td>" for i in keep) + "</tr>"
        return main + (f'<tr class="sub"{attrs}><td colspan="{len(keep)}">{detail}</td></tr>' if detail else "")
    return (f'<div class="scroll"><table class="{cls}"><tr>' + "".join(f"<th{n(i)}>{heads[i][0]}</th>" for i in keep) + "</tr>"
            + "".join(tr(*r) for r in rows) + "</table></div>")


unit, num, si, size = ui.unit, ui.num, ui.si, ui.size


def flame_graphs(cell):
    """Buttons for an async-profiler cell's or run's flame graphs, a row per event, a button per kind (dashed until rendered)."""
    if not (os.path.exists(os.path.join(cell, "profile.txt")) and open(os.path.join(cell, "profile.txt")).read().startswith("async")):
        return ""
    jfr = (glob.glob(os.path.join(cell, "**", "*.jfr"), recursive=True) or [None])[0]
    events = regraph.events_of(cell)
    if not jfr and events:
        # a published copy leaves the recording out: find it by its first event's bench graph, <jfr stem>-<label>.html
        g = (glob.glob(os.path.join(cell, "**", f"*-{events[0][0]}.html"), recursive=True) or [None])[0]
        jfr = g and g[:-len(f"-{events[0][0]}.html")] + ".jfr"
    if not jfr:
        return ""
    rows = []
    for label, _ in events:
        ev = label.removeprefix("hw-")
        ks = "".join(graph_link(regraph.graph_path(jfr, label, k), k, ev) for k in regraph.kinds())
        rows.append(f'<span class="ev" title="{esc(regraph.EVENT_HELP.get(ev, ev))}">{esc(ev)}</span><span class="btns">{ks}</span>')
    return f'<div class="graphs">{"".join(rows)}</div>'


def graph_link(path, kind, event):
    """A flame graph's button, with its total (samples, or event counts for PMU events) once it is rendered."""
    n = runinfo.graph_samples(path) if os.path.exists(path) else None
    if n is None:
        return link(path, kind, f"{event}|{kind}", regraph.KIND_HELP.get(kind))
    title = f"{regraph.KIND_HELP.get(kind, kind)} Total: {n:,} (samples, or event counts for PMU events)."
    return (f'<a class="btn{" empty" if n == 0 else ""}" href="{rel(path)}" data-lb="{esc(event)}|{esc(kind)}" title="{esc(title)}">'
            f'{esc(kind)} <span class="k">{si(n) if n else 0}</span></a>')


def timeline_link(d):
    return link(os.path.join(d, "timeline.html"), "timeline", "timeline", "Each fork from JVM start to exit: iterations, GC pauses, counters")


CELL_HEADS = [("corpus", False), ("variant", False), ("{unit}", True), ("cycles/op", True), ("instructions/op", True),
              ("alloc/op", True), ("flags", False), ("finished", False)]


def cell_row(spec, corpus, variant, cell):
    """((tr attributes, cells), when, corpus, data) of a campaign cell, or None before it has started; data is None while
    it runs, else (variant, score, cycles, instructions, spec version, alloc, secondary metrics, unit)."""
    res_f = os.path.join(cell, "result.json")
    if not os.path.exists(res_f):
        return None
    n = os.path.basename(cell)
    # a paired cell is one fork alternating the variants
    name = f"fork {esc(n)}" if variant == "paired" else f"{esc(variant)} #{esc(n)}"
    attrs = f' data-corpus="{esc(corpus)}" data-lb-group="{esc(f"{spec} · {corpus} · {variant} #{n}")}"'
    try:
        r = json.load(open(res_f))[0]
        p = r["primaryMetric"]
    except (OSError, ValueError, IndexError, KeyError):
        # JMH writes result.json when the fork ends, so an empty or partial one is a cell still running
        return ((f' data-running="1"{attrs} data-profiled="0"', [esc(corpus), name, '<span class="badge running">running</span>']
                 + [""] * 5, f'<div class="cellg"><span class="btns">{timeline_link(cell)}</span></div>' if os.path.exists(os.path.join(cell, "timeline.html")) else ""),
                time.time(), corpus, None)
    m = r.get("secondaryMetrics", {})
    cyc = m.get("xctrace.CORE_ACTIVE_CYCLE", {}).get("score")
    ins = m.get("xctrace.INST_ALL", {}).get("score")
    alloc = m.get("gc.alloc.rate.norm", {}).get("score")
    # a paired cell's -prof gc mixes its variants, so show each variant's own
    paired_alloc = [(k.removeprefix("paired.alloc."), x["score"]) for k, x in m.items()
                    if k.startswith("paired.alloc.") and ".delta%" not in k]
    alloc_html = ("".join(f'<span class="pv">{esc(v)} <b>{size(x) or 0}</b></span>' for v, x in paired_alloc) if paired_alloc else size(alloc))
    scalac = r.get("params", {}).get("scalacOptions", "")
    pattern = re.compile(config.get().get("index", "flags"))
    flags = " ".join([a for a in r["jvmArgs"] if pattern.search(a) and not a.startswith("-Dperflab.")] + ([scalac] if scalac else []))
    graphs = flame_graphs(cell)
    tl = timeline_link(cell) if os.path.exists(os.path.join(cell, "timeline.html")) else ""
    when = os.path.getmtime(res_f)
    version = specs.of_cell(cell)
    ver_html = f' <span class="when ver" title="spec version">spec {esc(version)}</span>' if version else ""
    cells = [esc(corpus), f"{name}{ver_html}", num(p['score']) + (f" ± {num(p['scoreError'], p['score'])}" if isinstance(p.get("scoreError"), (int, float)) else ""),  # JMH writes "NaN" for too few iterations
             si(cyc) if cyc else "", si(ins) if ins else "", alloc_html,
             f"<code>{esc(flags)}</code>" if flags else "", f'<span class="when">{stamp(when)}</span>']
    detail = (f'<div class="cellg">{f"<span class={chr(34)}btns{chr(34)}>{tl}</span>" if tl else ""}{graphs}</div>') if tl or graphs else ""
    return ((f'{attrs} data-profiled="{1 if graphs else 0}"', cells, detail), when, corpus,
            (variant, p["score"], cyc, ins, version, alloc, m, p.get("scoreUnit", "")))


def score_head(units, suffix=""):
    """The score column's name: its unit (µs/op), else "score"."""
    return (esc(unit(next(iter(units)))) if len(units) == 1 and next(iter(units)) else "score") + suffix


def summary(name, cells):
    """Per corpus and variant: mean score, cycles/op, instructions/op and allocation/op over rounds, each against the
    spec's first variant (in the order of the campaign's spec.json, else alphabetical). For a paired campaign, each
    variant's own metrics and the paired differences within forks (`paired_summary`)."""
    spec_f = os.path.join(CAMPAIGNS, name, "spec.json")
    spec = json.load(open(spec_f)) if os.path.exists(spec_f) else {}
    if spec.get("paired"):
        return paired_summary(list(spec["paired"]), cells)
    order = list(spec.get("variants", {}))
    out = []
    units = {c[7] for vs in cells.values() for cs in vs.values() for c in cs}
    for corpus in sorted(cells):
        vs = cells[corpus]
        names = [v for v in order if v in vs] + sorted(v for v in vs if v not in order)
        def stats(xs):
            xs = [x for x in xs if x]
            if not xs:
                return None, None
            mean = sum(xs) / len(xs)
            sd = (sum((x - mean) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5 if len(xs) > 1 else 0.0
            return mean, sd
        cols = ((1, num, "score"), (2, si, "count"), (3, si, "count"), (5, size, "alloc"))
        base = {i: stats([c[i] for c in vs[names[0]]]) for i, _, _ in cols}
        for v in names:
            cs = vs[v]
            tds = [f"{esc(corpus)}{mixed(vs) if v == names[0] else ''}", esc(v), str(len(cs))]
            for i, fmt, kind in cols:
                mean, sd = stats([c[i] for c in cs])
                if mean is None:
                    tds.append(""); continue
                rel_sd = f' <span class="pm">± {100 * sd / mean:.1f}%</span>' if len(cs) > 1 else ""
                b, bsd = base[i]
                # the spread of the difference: both variants' relative spreads over rounds
                spread = 100 * ((sd / mean) ** 2 + (bsd / b) ** 2) ** 0.5 if b and len(cs) > 1 and len(vs[names[0]]) > 1 else None
                tds.append(with_delta(f"{fmt(mean)}{rel_sd}", "" if v == names[0] or not b else delta(100 * (mean / b - 1), spread, ui.delta_ok(b, kind))))
            out.append(("", tds))
    heads = [("corpus", False), ("variant", False), ("rounds", False), (score_head(units), False), ("cycles/op", False),
             ("instructions/op", False), ("alloc/op", False)]
    return table(heads, out, "t summary") if out else ""


def delta(d, spread=None, ok=True):
    """A percent change as html: green or red when the spread over rounds or forks doesn't cross zero (lower is better
    for every metric here), grey when it does or is unknown; a dash when the base is about zero."""
    if d is None:
        return ""
    if not ok:
        return '<span class="d na" title="the values are about zero: no percent change">–</span>'
    cls = "flat" if spread is None or abs(d) <= spread or abs(d) < 0.005 else "worse" if d > 0 else "better"
    title = {"flat": "inconclusive: within the spread" if spread is not None else "one round: no spread",
             "worse": "higher, beyond the spread", "better": "lower, beyond the spread"}[cls]
    return (f'<span class="d {cls}" title="{title}">{d:+.2f}%' + (f' <span class="pm">± {spread:.2f}</span>' if spread is not None else "")
            + "</span>")


def with_delta(value, d):
    """A summary cell: the value, and its Δ beneath."""
    return f"{value}<br>{d}" if d else value


def mixed(variants):
    """A warning when a corpus's cells ran under different spec versions."""
    versions = {c[4] for cs in variants.values() for c in cs}
    return (f' <span class="mixed" title="the cells of this corpus ran under different spec versions">⚠ mixed spec versions: '
            f'{esc(", ".join(sorted(v or "unversioned" for v in versions)))}</span>') if len(versions) > 1 else ""


def paired_summary(names, cells):
    """A paired campaign's variants alternate within each fork (cell), so its JMH score mixes them: per corpus and
    variant, the variant's own metrics (`ab.PAIRED_METRICS`) as means over forks, and the paired difference against
    the first variant, as the mean and spread over forks of each fork's difference."""
    out = []
    units = {c[7] for vs in cells.values() for cs in vs.values() for c in cs}
    for corpus in sorted(cells):
        forks = [c[6] for cs in cells[corpus].values() for c in cs]
        for v in names:
            tds = [f"{esc(corpus)}{mixed(cells[corpus]) if v == names[0] else ''}", esc(v), str(len(forks))]
            for label, key, scale, fmt in ab.PAIRED_METRICS:
                kind = ui.kind_of(label)
                m, ds, _ = ab.paired_metric(forks, key.format(v))
                b, _, _ = ab.paired_metric(forks, key.format(names[0]))
                show = size if kind == "alloc" else si if kind == "count" else num
                d = sd = None
                if ds:
                    d = sum(ds) / len(ds)
                    sd = (sum((x - d) ** 2 for x in ds) / (len(ds) - 1)) ** 0.5 if len(ds) > 1 else None
                tds.append(with_delta((show(m) or "0") if m is not None else "", delta(d, sd, ui.delta_ok(b, kind) and ui.delta_ok(m, kind))))
            out.append(("", tds))
    heads = [("corpus", False), ("variant", False), ("forks", False)]
    heads += [h for label, *_ in ab.PAIRED_METRICS
              for h in ((score_head(units, label[5:]) if label.startswith("score") else esc(label), False),)]
    return table(heads, out, "t summary") if out else ""


def spec_history(spec_dir, counts, sid):
    """The campaign's spec versions, each with the cells that ran under it and what changed from the previous version."""
    hist = specs.history(spec_dir)
    if not hist and not counts.get(None):
        return ""
    items = []
    for v, _, changes in hist:
        when = time.strftime("%a %d %b %H:%M:%S", time.strptime(v[:15], "%Y%m%d-%H%M%S"))
        body = ("<ul>" + "".join(f"<li><code>{esc(c)}</code></li>" for c in changes) + "</ul>") if changes else ""
        items.append(f'<li><b>{esc(v)}</b> <span class="when">{when} · {counts.get(v, 0)} cells</span>{body}</li>')
    if counts.get(None):
        items.append(f'<li><i>unversioned</i> <span class="when">{counts[None]} cells (before spec versions were recorded)</span></li>')
    if len(items) == 1 and hist:
        v = hist[0][0]
        return f'<p class="specs k" title="spec version {esc(v)}">spec of {time.strftime("%a %d %b %H:%M", time.strptime(v[:15], "%Y%m%d-%H%M%S"))}</p>'
    return (f'<details class="specs" id="{sid}-specs"><summary>Spec versions <span class="k">({len(items)})</span></summary>'
            f'<ul>{"".join(items)}</ul></details>')


# JMH options that take no value; every other option in a run's jmh.args is followed by one
JMH_FLAGS = {"-h", "-l", "-lp", "-lprof", "-lrf"}
RUN_STATE = "run.json"
RUN_NAMES = set()  # every run's name, for runs to link their siblings
STALE_SECS = 600  # a run without run.json (an older perflab) counts as running while its logs grow


def run_args(run):
    """A run's jmh.args as (benchmarks, {param: value}, [(option, value)], JVM, JVM arguments)."""
    try:
        args = open(os.path.join(run, "jmh.args")).read().splitlines()
    except OSError:
        return [], {}, [], None, []
    benches, params, opts, jvm, jvm_args = [], {}, [], None, []
    i = 0
    while i < len(args):
        a = args[i]
        if a.startswith("-") and a not in JMH_FLAGS and i + 1 < len(args):
            v = args[i + 1]
            if a == "-p":
                k, _, pv = v.partition("=")
                params[k] = pv
            elif a == "-jvm":
                jvm = v
            elif a in ("-jvmArgs", "-jvmArgsAppend", "-jvmArgsPrepend"):
                jvm_args += v.split()
            elif a not in ("-o", "-rf", "-rff", "-prof"):
                opts.append((a, v))
            i += 2
        else:
            if not a.startswith("-"):
                benches.append(a)
            i += 1
    return benches, params, opts, jvm, jvm_args


def run_status(run):
    """(status, detail, results) of a run: running, finished, failed or interrupted; results are result.json's entries."""
    try:
        results = json.load(open(os.path.join(run, "result.json")))
    except (OSError, ValueError):
        results = None
    try:
        st = json.load(open(os.path.join(run, RUN_STATE)))
    except (OSError, ValueError):
        st = None
    if st:
        if st.get("status") == "running":
            alive = True
            try:
                os.kill(st["pid"], 0)
            except (OSError, KeyError, TypeError):
                alive = False
            return ("running", "", results) if alive else ("interrupted", "perflab exited without finishing the run", results)
        if st.get("status") == "failed":
            return "failed", f"build exited with {st.get('rc')}", results
        if st.get("status") == "interrupted":
            return "interrupted", "", results
        return ("finished", "", results) if results else ("failed", "no results", results)
    if results:
        return "finished", "", results
    logs = [f for f in (os.path.join(run, n) for n in ("jmh.log", "build.log", "iterations.tsv", "result.json")) if os.path.exists(f)]
    if logs and time.time() - max(os.path.getmtime(f) for f in logs) < STALE_SECS:
        return "running", "", None
    return "failed", "no results", None


def iterations(run):
    """'forks · warmup · measurement · last score' from a run's iterations.tsv, for a run in progress."""
    try:
        rows = [l.split("\t") for l in open(os.path.join(run, "iterations.tsv")).read().splitlines()[1:]]
    except OSError:
        return ""
    rows = [r for r in rows if len(r) >= 10]
    if not rows:
        return ""
    count = lambda k: sum(1 for r in rows if r[1] == k)
    last = next((r for r in reversed(rows) if r[5]), None)
    forks = len({r[8] for r in rows})
    return (f"{forks} fork{'s' if forks > 1 else ''} · {count('warmup')} warmup, {count('measure')} measurement iterations"
            + (f" · last {float(last[5]):.1f} {unit(last[9])}" if last else ""))


def short_jvm(jvm):
    home = os.path.expanduser("~")
    jvm = jvm.removesuffix("/bin/java")
    return "~" + jvm[len(home):] if jvm.startswith(home + "/") else jvm


def sub(title, note):
    return f'<h3 class="sub">{title} <span class="k">{note}</span></h3>'


def card_head(kind, name, badge, when, buttons=""):
    return (f'<div class="card-h"><span class="kind">{kind}</span><h2>{esc(name)}</h2>{badge}<span class="when">{when}</span>'
            + (f'<span class="btns">{buttons}</span>' if buttons else "") + "</div>")


def run_section(run):
    """A run of `perflab run`: its benchmark, parameters, JVM, status, scores and links. (mtime, html) or None."""
    if not any(os.path.exists(os.path.join(run, f)) for f in ("jmh.args", "result.json", "jmh.log")):
        return None
    name = os.path.basename(run.rstrip("/"))
    benches, params, opts, jvm, jvm_args = run_args(run)
    status, detail, results = run_status(run)
    corpus_param = config.get().get("benchmark", "corpus")
    corpus = params.get(corpus_param, "")
    try:
        profile = open(os.path.join(run, "profile.txt")).read().strip()
    except OSError:
        profile = ""
    pattern = re.compile(config.get().get("index", "flags"))
    flags = [a for a in jvm_args if pattern.search(a) and not a.startswith("-Dperflab.")]
    facts = [f"<b>{esc(' '.join(benches) or '(default benchmark)')}</b>"]
    facts += [f"<code>-p {esc(k)}={esc(v)}</code>" for k, v in params.items()]
    if opts:
        facts.append(f"<code>{esc(' '.join(f'{o} {v}' for o, v in opts))}</code>")
    if profile and profile != "none":
        facts.append(f"profile <code>{esc(profile)}</code>")
    if jvm:
        facts.append(f'JVM <code title="{esc(jvm)}">{esc(short_jvm(jvm))}</code>')
    if flags:
        facts.append(f"flags <code>{esc(' '.join(flags))}</code>")
    graphs = flame_graphs(run)
    # pages over the run's text outputs open in the lightbox; logs open as they are
    pages = []
    if os.path.exists(os.path.join(run, "report.md")):
        pages.append((runinfo.md_page(os.path.join(run, "report.md"), os.path.join(run, "report.html"), f"{name}: audit report", profile, HOME), "audit report"))
    pages += [(runinfo.text_page(f, f"{name}: hot methods by counter", HOME), "hot methods")
              for f in sorted(glob.glob(os.path.join(run, "**", "*.methods.txt"), recursive=True))]
    pages += [(runinfo.text_page(f, f"{name}: threads", HOME), "threads") for f in sorted(glob.glob(os.path.join(run, "**", "*.threads.txt"), recursive=True))]
    links = ([timeline_link(run)] + [link(p, label, label) for p, label in pages]
             + [link(os.path.join(run, f), f) for f in ("jmh.log", "build.log") if os.path.exists(os.path.join(run, f))])
    rows = ""
    if results:
        varying = [k for k in results[0].get("params", {}) if len({str(r.get("params", {}).get(k)) for r in results}) > 1]
        units = {r["primaryMetric"].get("scoreUnit", "") for r in results}
        one_unit = len(units) == 1
        out = []
        for r in results:
            p = r["primaryMetric"]
            m = r.get("secondaryMetrics", {})
            cyc = m.get("xctrace.CORE_ACTIVE_CYCLE", {}).get("score")
            ins = m.get("xctrace.INST_ALL", {}).get("score")
            alloc = m.get("gc.alloc.rate.norm", {}).get("score")
            rp = r.get("params", {})
            err = f" ± {num(p['scoreError'], p['score'])}" if isinstance(p.get("scoreError"), (int, float)) else ""
            ps = " ".join(f"{k}={rp.get(k)}" for k in varying)
            out.append((f' data-corpus="{esc(str(rp.get(corpus_param, corpus)))}" data-profiled="{1 if graphs else 0}"',
                        [esc(r["benchmark"].rsplit(".", 1)[-1]) + (f" <code>{esc(ps)}</code>" if ps else ""),
                         f"{num(p['score'])}{err}" + ("" if one_unit else f" {esc(unit(p.get('scoreUnit', '')))}"),
                         si(cyc) if cyc else "", si(ins) if ins else "", size(alloc)]))
        heads = [("benchmark", False), (esc(unit(units.pop())) if one_unit else "score", True), ("cycles/op", True),
                 ("instructions/op", True), ("alloc/op", True)]
        rows = table(heads, out) + runinfo.metrics_details(results)
    progress = iterations(run) if status == "running" else ""
    # the run's own files: pages rendered from it later (timeline, report) don't move its end
    mtimes = [os.path.getmtime(os.path.join(run, f)) for f in os.listdir(run)
              if not f.endswith(".html") and os.path.isfile(os.path.join(run, f))] or [os.path.getmtime(run)]
    args_f = os.path.join(run, "jmh.args")
    started = os.path.getmtime(args_f) if os.path.exists(args_f) else min(mtimes)
    last = time.time() if status == "running" else max(mtimes)
    when = span(started, max(mtimes)) if status != "running" else f"since {stamp(started)}"
    badge = f'<span class="badge {status}"{f" title={chr(34)}{esc(detail)}{chr(34)}" if detail else ""}>{status}</span>'
    bench, tool = runinfo.facets(run)
    return last, (f'<section class="card run" id="{esc(name)}" data-last="{last:.0f}" data-notes="0" data-lb-group="{esc(name)}" '
                  f'data-benchmark="{esc(bench)}" data-tool="{esc(tool)}" data-corpus="{esc(corpus)}" data-profiled="{1 if graphs else 0}">'
                  f'{card_head("run", name, badge, when, "".join(links))}'
                  f'<p class="facts">{" · ".join(facts)}{f"<br>{esc(progress)}" if progress else ""}</p>'
                  f'{runinfo.about(name, profile, RUN_NAMES)}{rows}{graphs}</section>')


def stamp(t):
    return time.strftime("%a %d %b %H:%M", time.localtime(t))


def span(a, b):
    """'Tue 20 Oct 15:57 – 15:58', with the day once when both ends share it."""
    sa, sb = stamp(a), stamp(b)
    if sa == sb:
        return sa
    return f"{sa} – {sb[11:]}" if sa[:10] == sb[:10] else f"{sa} – {sb}"


def md(text):
    """Just enough Markdown for notes: paragraphs, `- ` bullets, **bold**, `code` and [text](url) links."""
    import re as _re
    def inline(t):
        t = esc(t)
        t = _re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', t)
        t = _re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
        return _re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    out, items = [], []
    for block in text.strip().split("\n\n"):
        lines = block.splitlines()
        if lines[0].startswith("### "):
            out.append(f"<h3>{inline(lines[0][4:])}</h3>")
            lines = lines[1:]
        if lines and all(l.lstrip().startswith("- ") for l in lines):
            out.append("<ul>" + "".join(f"<li>{inline(l.lstrip()[2:])}</li>" for l in lines) + "</ul>")
        elif lines:
            out.append(f"<p>{inline(' '.join(lines))}</p>")
    return "".join(out)


def notes(path):
    return f'<div class="notes">{md(open(path).read())}</div>' if os.path.exists(path) else ""


def progress(spec_dir):
  """(cells with results, cells planned) from the campaign's spec.json; None without one."""
  try:
    s = json.load(open(os.path.join(spec_dir, "spec.json")))
    variants = 1 if s.get("paired") else len(s["variants"])
    planned = s.get("rounds", 2) * len(s["corpora"]) * variants
  except (OSError, ValueError, KeyError, TypeError):
    return None
  done = sum(1 for f in glob.glob(os.path.join(spec_dir, "*", "*", "*", "result.json")) if os.path.getsize(f) > 0)
  return done, planned


def progress_badge(prog, name):
  if not prog:
    return ""
  done, planned = prog
  running = ""
  try:
    r = json.load(open(os.path.join(CAMPAIGNS, "running.json")))
    running = " · running" if r.get("campaign") == name else ""
  except (OSError, ValueError):
    pass
  cls = "done" if done >= planned else "running" if running else "partial"
  return f'<span class="badge {cls}">{done} of {planned} cells{running}</span>'


CSS = """
main{max-width:1400px;margin:0 auto;padding:16px 20px 40px}
.nav{position:sticky;top:0;z-index:10}
.tabsrow{background:var(--ink)} .tabsrow .in{max-width:1400px;margin:0 auto;padding:0 20px;display:flex;align-items:center;gap:8px}
nav.tabs{display:flex;gap:2px;overflow-x:auto;scrollbar-width:none;flex:1} nav.tabs::-webkit-scrollbar{display:none}
nav.tabs a{color:var(--ink-muted);padding:9px 12px 7px;border-bottom:2px solid transparent;font-weight:500;white-space:nowrap}
nav.tabs a.on{color:#fff;border-bottom-color:var(--brand)} nav.tabs a:hover{color:#fff;text-decoration:none}
nav.tabs .n{font-size:11px;color:var(--ink-muted);margin-left:5px;font-weight:normal}
.tabsrow details.help>summary{border-color:var(--ink-line);color:var(--ink-muted)}
.filterbar{background:var(--panel);border-bottom:1px solid var(--line);box-shadow:var(--shadow)}
.filterbar .in{max-width:1400px;margin:0 auto;padding:7px 20px;display:flex;flex-wrap:wrap;gap:6px 18px;align-items:center}
.fg{display:inline-flex;flex-wrap:wrap;gap:4px;align-items:center} .fl{color:var(--muted);font-size:12px;margin-right:2px}
#q{border:1px solid var(--line);background:var(--bg);color:var(--fg);border-radius:6px;padding:4px 8px;font:inherit;width:220px;margin-left:auto}
h2.sec{font-size:18px;margin:28px 0 10px;display:flex;align-items:baseline;gap:8px;scroll-margin-top:100px} h2.sec .k{font-weight:normal}
h2.sec:first-child{margin-top:8px}
.card .notes{border-left:3px solid var(--link);padding:0 12px;margin:8px 0 12px} .notes h3{margin:6px 0;font-size:13px}
#findings{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--brand);border-radius:10px;padding:4px 16px;margin:0 0 14px}
.mixed{color:var(--warn);font-size:11px} details.specs{margin:2px 0 6px;font-size:12px} details.specs summary{cursor:pointer;color:var(--muted)}
details.specs ul{margin:2px 0 6px;padding-left:20px}
.diffs{display:flex;flex-wrap:wrap;gap:4px 8px;align-items:center;margin:4px 0 8px}
table.summary td:nth-child(n+3),table.summary th:nth-child(n+3){text-align:right}
tr[data-running] td{color:var(--muted)} .single-ver .ver{display:none} p.specs{margin:0 0 4px}
details.cells{margin:10px 0 0} details.cells>summary,details.metrics>summary{cursor:pointer;font-size:12.5px} .pv{display:block;white-space:nowrap} .pv b{font-weight:normal}
details.metrics{margin:2px 0 6px} details.metrics>summary{color:var(--muted)} table.m th{font-weight:normal;color:var(--fg);border:0;padding:2px 14px 2px 0} table.m td{border:0;padding:2px 10px}
.d{white-space:nowrap;font-size:12px} .pm{font-size:11px;color:var(--muted)} .d.better{color:var(--ok)} .d.worse{color:var(--bad)} .d.flat,.d.na{color:var(--muted)}
table.t td{white-space:nowrap} p.about{color:var(--muted);margin:0 0 6px}
table.t tr.has-sub td{border-bottom:0} table.t tr.sub td{padding-top:0} .cellg{display:flex;flex-wrap:wrap;gap:4px 16px;align-items:baseline}
.cellg .graphs{margin:0} h3.sub{font-size:12.5px;margin:12px 0 0;font-weight:600} .btn .k{font-size:11px} .btn.empty{color:var(--muted)}
.hidden{display:none!important} section.card{scroll-margin-top:100px} #counters-card .k{margin:0 0 4px}
#tl .card-h{gap:6px 12px} #tl select{font:inherit;max-width:100%;padding:2px 4px;border:1px solid var(--line);border-radius:6px;background:var(--panel);color:var(--fg)}
#tl label{white-space:nowrap} #tl .help{margin-left:auto} #tl[hidden]{display:none}
footer{max-width:1400px;margin:0 auto;padding:0 20px 30px;color:var(--muted);font-size:12px}
.ftoggle{display:none}
@media (max-width:700px){.ftoggle{display:inline-block} .filterbar:not(.open) .fg{display:none} main{padding:12px 12px 24px} .filterbar .in,.tabsrow .in{padding-left:12px;padding-right:12px} #q{width:100%;margin-left:0}
  .nav{position:static} .card{padding:10px 12px}}
"""

# what the page's intro may use: a lead paragraph, idea cards, numbered steps and a glossary (see examples/sample/site-intro.html)
INTRO_CSS = """
.intro{margin:4px 0 8px} .intro .lead{font-size:16px;line-height:1.6;max-width:860px;margin:0 0 16px}
.intro h3{font-size:13px;margin:18px 0 8px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}
.ideas{display:grid;grid-template-columns:repeat(5,1fr);gap:12px} @media (max-width:1150px){.ideas{grid-template-columns:repeat(3,1fr)}} @media (max-width:700px){.ideas{grid-template-columns:1fr}}
.idea{background:var(--panel);border:1px solid var(--line);border-top:3px solid var(--brand);border-radius:10px;padding:12px 14px}
.idea b{display:block;margin-bottom:4px;font-size:13.5px} .idea p{margin:0;color:var(--muted);font-size:12.5px;line-height:1.55}
.intro .cols{display:grid;grid-template-columns:3fr 2fr;gap:20px} @media (max-width:860px){.intro .cols{grid-template-columns:1fr}}
ol.steps{counter-reset:s;display:grid;gap:8px;padding:0;margin:0;list-style:none}
ol.steps li{counter-increment:s;position:relative;padding:10px 14px 10px 50px;background:var(--panel);border:1px solid var(--line);border-radius:10px;line-height:1.55}
ol.steps li::before{content:counter(s);position:absolute;left:14px;top:10px;width:24px;height:24px;border-radius:50%;background:var(--brand);color:#fff;font-weight:700;font-size:12px;display:grid;place-items:center}
dl.terms{margin:0;display:grid;gap:8px} dl.terms>div{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:8px 12px}
dl.terms dt{font-weight:600} dl.terms dd{margin:2px 0 0;color:var(--muted);font-size:12.5px;line-height:1.5}
.intro .note{color:var(--muted);font-size:12.5px;margin:14px 0 0}
"""


def title_of():
    """The project's title for the page: [index] title in perflab.toml, else the project directory's name."""
    c = config.get()
    return c.get("index", "title") or os.path.basename(os.path.normpath(c.root))


def build(campaigns, runs=None, out=None, title=None, intro="", footer=""):
  """One page over the project's campaigns (<campaigns>) and runs of `perflab run` (<runs>, default [paths] runs): an
  intro when one is given, the campaigns, the runs' PMU counters side by side, and the runs. `perflab serve` and the
  campaigns' tools write it to <campaigns>/index.html (`out` by default); `perflab site` to the site's root."""
  global root, CAMPAIGNS, HOME
  CAMPAIGNS = campaigns
  runs = runs or config.get().runs
  out = out or os.path.join(campaigns, "index.html")
  root = os.path.dirname(os.path.abspath(out))
  HOME = os.path.abspath(out)
  os.makedirs(campaigns, exist_ok=True)
  title = title or title_of()
  camp_sections, run_sections = [], []
  facet = {"benchmark": set(), "tool": set(), "corpus": set()}
  timeline_cells = []  # (mtime, value, label, group) of cells with an iterations.tsv, for the timeline panel
  for spec_dir in glob.glob(os.path.join(campaigns, "*/")):
      name = os.path.basename(spec_dir.rstrip("/"))
      rows, whens, corpora, cells, counts, benches, tools = [], [], set(), {}, {}, set(), set()
      for corpus_dir in sorted(glob.glob(os.path.join(spec_dir, "*/"))):
          corpus = os.path.basename(corpus_dir.rstrip("/"))
          if corpus.startswith("diff-"):
              continue
          for variant_dir in sorted(glob.glob(os.path.join(corpus_dir, "*/"))):
              variant = os.path.basename(variant_dir.rstrip("/"))
              for cell in sorted(glob.glob(os.path.join(variant_dir, "*"))):
                  if os.path.isdir(cell) and os.path.basename(cell).isdigit():
                      ver = specs.of_cell(cell)
                      counts[ver] = counts.get(ver, 0) + 1
                      b, t = runinfo.facets(cell)
                      benches |= set(b.split()); tools.add(t)
                      if os.path.exists(os.path.join(cell, "iterations.tsv")):
                          timeline_cells.append((os.path.getmtime(os.path.join(cell, "iterations.tsv")), os.path.relpath(cell, root) + "/",
                                                 f"{name} · {corpus} · {variant} #{os.path.basename(cell)}", "campaign cells"))
                      row = cell_row(name, corpus, variant, cell)
                      if row:
                          rows.append(row[0]); whens.append(row[1]); corpora.add(row[2])
                          if row[3]:
                              cells.setdefault(corpus, {}).setdefault(row[3][0], []).append(row[3])
      # a profdiff output directory: its compare page (each event's graphs as tabs), else its graphs
      diffs = sorted(f for d in glob.glob(os.path.join(spec_dir, "diff-*/"))
                     for f in ([os.path.join(d, "compare.html")] if os.path.exists(os.path.join(d, "compare.html"))
                               else glob.glob(os.path.join(d, "*.html"))))
      prog = progress(spec_dir)
      if not rows and not diffs and not prog:
          continue
      sid = "c-" + esc(name)
      diff_html = (f'<div class="diffs" data-lb-group="{esc(name)} · differential flame graphs"><span class="k">Differential flame graphs (a → b)</span>'
                   + "".join(link(d, os.path.basename(os.path.dirname(d)).removeprefix("diff-"), "diff|" + os.path.basename(os.path.dirname(d)).removeprefix("diff-"))
                             for d in diffs) + "</div>") if diffs else ""
      last = max(whens) if whens else os.path.getmtime(spec_dir)
      when = span(min(whens), last) if whens else stamp(last)
      has_notes = os.path.exists(os.path.join(spec_dir, "NOTES.md"))
      report = os.path.join(spec_dir, "report.md")
      buttons = (link(runinfo.md_page(report, os.path.join(spec_dir, "report.html"), f"{name}: report", home=HOME), "report", "report",
                      "The campaign's report (perflab ab report)") if os.path.exists(report) else "")
      units = {c[7] for vs in cells.values() for cs in vs.values() for c in cs}
      heads = [(esc(unit(units.pop())) if len(units) == 1 else "score", n) if h == "{unit}" else (h, n) for h, n in CELL_HEADS]
      try:
          paired = list(json.load(open(os.path.join(spec_dir, "spec.json"))).get("paired") or [])
      except (OSError, ValueError):
          paired = []
      summ = summary(name, cells)
      about = (f"means over forks, each alternating {', '.join(paired)}; Δ against {paired[0]} within each fork" if paired
               else "means over rounds; Δ against the first variant")
      # the cells: open while they are what there is to see (no summary yet, a cell running) or carry flame graphs
      cells_open = not summ or any(' data-running="1"' in r[0] or ' data-profiled="1"' in r[0] for r in rows)
      cells_html = (f'<details class="cells" id="{sid}-cells"{" open" if cells_open else ""}><summary><b>Cells</b> <span class="k">{len(rows)}: '
                    f'{"forks of the paired run" if paired else "one per variant and round"}; timelines and flame graphs</span></summary>'
                    f'{table(heads, rows)}</details>') if rows else ""
      single = " single-ver" if len(counts) <= 1 else ""
      facet["benchmark"] |= benches; facet["tool"] |= tools; facet["corpus"] |= corpora
      profiled = any(' data-profiled="1"' in r[0] for r in rows)
      camp_sections.append((last, f'<section class="card campaign{single}" id="{sid}" data-last="{last:.0f}" data-notes="{1 if has_notes else 0}" '
                                  f'data-benchmark="{esc(" ".join(sorted(benches)))}" data-tool="{esc(" ".join(sorted(tools)))}" '
                                  f'data-corpus="{esc(" ".join(sorted(corpora)))}" data-profiled="{1 if profiled else 0}">'
                                  f'{card_head("campaign", name, progress_badge(prog, name), when, buttons)}'
                                  f'{notes(os.path.join(spec_dir, "NOTES.md"))}{diff_html}{spec_history(spec_dir, counts, sid)}'
                                  f'{sub("Summary", esc(about)) + summ if summ else ""}{cells_html}</section>'))
  run_dirs = sorted(glob.glob(os.path.join(runs, "*/"))) if runs and os.path.isdir(runs) else []
  RUN_NAMES.clear(); RUN_NAMES.update(os.path.basename(r.rstrip("/")) for r in run_dirs)
  for run in run_dirs:
      sec = run_section(run)
      if sec:
          run_sections.append(sec)
          b, t = runinfo.facets(run)
          facet["benchmark"] |= set(b.split()); facet["tool"].add(t)
          corpus = run_args(run)[1].get(config.get().get("benchmark", "corpus"), "")
          if corpus:
              facet["corpus"].add(corpus)
          tsv = os.path.join(run, "iterations.tsv")
          if os.path.exists(tsv):
              timeline_cells.append((os.path.getmtime(tsv), os.path.relpath(run, root).rstrip("/") + "/",
                                     os.path.basename(run.rstrip('/')), "runs"))
  newest = lambda secs: "".join(h for _, h in sorted(secs, key=lambda x: -x[0]))
  n_counters, counters_html = runinfo.counters(run_dirs)
  options = "".join(f'<optgroup label="{g}">' + "".join(f'<option value="{esc(v)}">{esc(l)}</option>'
                                                        for _, v, l, gg in sorted(timeline_cells, reverse=True) if gg == g) + "</optgroup>"
                    for g in ("runs", "campaign cells") if any(c[3] == g for c in timeline_cells))
  groups = "".join(f'<span class="fg"><span class="fl">{f}</span>' + "".join(f'<button class="chip" data-f="{f}" data-v="{esc(v)}">{esc(v)}</button>'
                                                                           for v in sorted(vs)) + "</span>"
                   for f, vs in facet.items() if len(vs) > 1)
  kinds = "".join(f"<li><b>{esc(k)}</b>: {esc(regraph.KIND_HELP[k])}</li>" for k in regraph.kinds() if k in regraph.KIND_HELP)
  help_html = ui.help_popover(
      "<p style='margin-top:0'>Newest first in each section. A <b>campaign</b> compares variants over rounds; a <b>run</b> is one "
      "<code>perflab run</code>. The chips filter campaigns, runs and counters together.</p>"
      "<p>Timelines, flame graphs and reports open over this page: chips switch between the graphs of the same run or cell, "
      "<b>[</b> and <b>]</b> step, <b>↗</b> opens one in a new tab, Esc closes. Dashed buttons are not rendered yet; "
      f"they turn into links when <code>perflab regraph</code> finishes.</p><p style='margin-bottom:0'>Graph kinds:</p><ul style='margin:2px 0;padding-left:18px'>{kinds}</ul>", right=True)
  tl_help = ui.help_popover("Each fork from JVM start to exit. Iterations appear as they finish; counter lanes (xctrace) once the fork has "
                            "finished. Wheel or pinch to zoom, drag to pan, double-click to reset.", right=True)
  tabs = ((f'<a href="#overview" data-sec="overview">Overview</a>' if intro else "")
          + f'<a href="#campaigns" data-sec="campaigns">Campaigns<span class="n" id="n-campaigns">{len(camp_sections)}</span></a>'
          + (f'<a href="#counters" data-sec="counters">Counters<span class="n">{n_counters}</span></a>' if n_counters else "")
          + f'<a href="#runs" data-sec="runs">Runs<span class="n" id="n-runs">{len(run_sections)}</span></a>')
  running_json = os.path.relpath(os.path.join(campaigns, ab.RUNNING_NAME), root)
  counters_sec = (f'<h2 class="sec" id="counters">PMU counters <span class="k">by run, benchmark thread only (xctrace)</span></h2>'
                  f'<section class="card" id="counters-card"><p class="k">Misses per 1,000 instructions; top-down shares of issue slots when a run used the '
                  f'CPU Counters template. Each run name links to its card.</p>{counters_html}</section>') if counters_html else ""

  page = f"""{ui.HEAD}<title>{esc(title)} · {ui.NAME}</title>
  {ui.style(ui.BASE, ui.LIGHTBOX_CSS, CSS, INTRO_CSS, timeline.CSS)}
  {ui.masthead(title)}
  <div class="nav"><div class="tabsrow"><div class="in"><nav class="tabs">{tabs}</nav>{help_html}</div></div>
  <div class="filterbar"><div class="in"><button class="chip ftoggle" onclick="this.closest('.filterbar').classList.toggle('open')">Filter ▾</button>{groups}
  <span class="fg"><span class="fl">show</span><button class="chip" data-f="show" data-v="profiled">profiled</button><button class="chip" data-f="show" data-v="notes">with notes</button></span>
  <span class="fg"><span class="fl">updated</span><button class="chip" data-f="age" data-v="10800">last 3 h</button><button class="chip" data-f="age" data-v="86400">last 24 h</button></span>
  <input id="q" type="search" placeholder="filter: name, flags, notes…"></div></div></div>
  <main>
  {f'<section class="intro" id="overview">{intro}</section>' if intro else ''}
  <section class="card" id="tl" hidden><div class="card-h"><h2>Fork timeline</h2><select id="tl-cell">{options}</select>
  <label class="k"><input type="checkbox" id="tl-follow" checked> follow the running fork</label><span id="tl-status"></span>{tl_help}</div>
  <div class="tl-legend" id="tl-legend"></div><svg class="timeline" id="tl-chart"></svg></section>
  <div class="tl-tip" id="tl-tip"></div>
  <div id="live">
  <h2 class="sec" id="campaigns">Campaigns <span class="k">variants compared over rounds, newest first</span></h2>
  {notes(os.path.join(campaigns, "FINDINGS.md")).replace('class="notes"', 'class="notes" id="findings"', 1)}
  {newest(camp_sections) or '<p class="k">No campaigns yet: <code>perflab ab run &lt;spec&gt;</code>.</p>'}
  {counters_sec}
  <h2 class="sec" id="runs">Runs <span class="k">one benchmark under one profile, newest first</span></h2>
  {newest(run_sections) or '<p class="k">No runs yet: <code>perflab run</code>.</p>'}
  </div></main>{f'<footer>{footer}</footer>' if footer else ''}
  <script>{timeline.script()}</script>{ui.lightbox_script()}
  <script>
  const RUNNING = {json.dumps(running_json)};
  const chips = [...document.querySelectorAll('.filterbar .chip')];
  chips.forEach(c => c.onclick = () => {{ c.classList.toggle('on'); apply(); }});
  document.getElementById('q').oninput = apply;
  function on(f) {{ return new Set(chips.filter(c => c.classList.contains('on') && c.dataset.f === f).map(c => c.dataset.v)); }}
  // chips within a group are alternatives; groups, show, age and the text combine
  function apply() {{
    const sel = {{benchmark: on('benchmark'), tool: on('tool'), corpus: on('corpus')}}, show = on('show'), ages = [...on('age')].map(Number);
    const q = document.getElementById('q').value.toLowerCase(), now = Date.now() / 1000;
    const match = el => Object.entries(sel).every(([f, vs]) => !vs.size || (el.dataset[f] || '').split(' ').some(v => vs.has(v)));
    for (const card of document.querySelectorAll('#live section.card[data-last]')) {{
      let ok = match(card);
      if (show.has('profiled')) ok = ok && card.dataset.profiled === '1';
      if (show.has('notes')) ok = ok && card.dataset.notes === '1';
      if (ages.length) ok = ok && now - Number(card.dataset.last) < Math.max(...ages);
      if (q) ok = ok && card.textContent.toLowerCase().includes(q);
      card.classList.toggle('hidden', !ok);
      for (const tr of card.querySelectorAll('tr[data-corpus]')) tr.classList.toggle('hidden', sel.corpus.size > 0 && !sel.corpus.has(tr.dataset.corpus));
    }}
    for (const tr of document.querySelectorAll('#counters-card tr[data-tool]')) tr.classList.toggle('hidden', !match(tr));
    const n = s => document.querySelectorAll(`#live section.card.${{s}}:not(.hidden)`).length;
    for (const [id, s] of [['n-campaigns', 'campaign'], ['n-runs', 'run']]) {{ const e = document.getElementById(id); if (e) e.textContent = n(s); }}
  }}
  // the tab of the section in view
  const tabs = [...document.querySelectorAll('nav.tabs a')];
  function spy() {{
    let cur = tabs[0];
    for (const t of tabs) {{ const h = document.getElementById(t.dataset.sec); if (h && h.getBoundingClientRect().top < 140) cur = t; }}
    tabs.forEach(t => t.classList.toggle('on', t === cur));
  }}
  addEventListener('scroll', spy, {{passive: true}}); spy();
  // live: the timeline panel shows while a fork runs (running.json, written by `perflab ab` and `perflab run`) and
  // polls its files; the sections are refetched from this page, which they rebuild around every cell
  const panel = document.getElementById('tl');
  const tl = BenchTimeline.mount(document.getElementById('tl-chart'), document.getElementById('tl-legend'), document.getElementById('tl-tip'));
  const sel = document.getElementById('tl-cell'), follow = document.getElementById('tl-follow'), status = document.getElementById('tl-status');
  let shown = null, running = null, picked = false;
  sel.onchange = () => {{ follow.checked = false; picked = true; tick(); }};
  follow.onchange = tick;
  const base = RUNNING.replace(/[^/]*$/, '');
  const dir = c => base + c.replace(/\\/?$/, '/');
  // a cell's name as the picker shows it: a run's name, or campaign · corpus · variant #round
  const nameOf = r => r.run || (p => p.length >= 4 ? `${{p[0]}} · ${{p[1]}} · ${{p[2]}} #${{p[3]}}` : r.cell)(r.cell.replace(/\\/$/, '').split('/'));
  status.onclick = e => {{ if (e.target.closest('a')) {{ e.preventDefault(); follow.checked = true; tick(); }} }};
  async function tick() {{
    try {{ const r = await fetch(RUNNING, {{cache: 'no-store'}}); running = r.ok ? await r.json() : null; }} catch (e) {{ running = null; }}
    panel.hidden = !running && !picked;
    if (panel.hidden) return;
    if (follow.checked && running) {{
      const v = dir(running.cell);
      if (![...sel.options].some(o => o.value === v)) sel.add(new Option(nameOf(running), v), 0);
      sel.value = v;
    }}
    const since = running ? new Date(running.started * 1000).toLocaleTimeString([], {{hour: '2-digit', minute: '2-digit', second: '2-digit'}}) : '';
    status.innerHTML = !running ? '<span class="k">nothing running</span>'
      : dir(running.cell) === sel.value ? `<span class="badge running">running since ${{since}}</span>`
      : `<a href="#" class="badge running" title="Show it">${{nameOf(running).replace(/[&<>]/g, c => ({{'&': '&amp;', '<': '&lt;', '>': '&gt;'}})[c])}} running</a>`;
    if (!sel.value) return;
    if (sel.value !== shown) {{ tl.reset(); shown = sel.value; }}
    tl.set(await BenchTimeline.fetchCell(sel.value));
  }}
  async function refresh() {{
    try {{
      const r = await fetch(location.pathname.endsWith('/') ? 'index.html' : location.pathname, {{cache: 'no-store'}});
      if (!r.ok) return;
      const doc = new DOMParser().parseFromString(await r.text(), 'text/html');
      // keep what the reader opened
      const open = new Map([...document.querySelectorAll('#live details[id]')].map(d => [d.id, d.open]));
      document.getElementById('live').innerHTML = doc.getElementById('live').innerHTML;
      for (const [id, o] of open) {{ const d = document.getElementById(id); if (d) d.open = o; }}
      const keep = sel.value;
      sel.innerHTML = doc.getElementById('tl-cell').innerHTML;
      if (keep && ![...sel.options].some(o => o.value === keep)) sel.add(new Option(keep, keep), 0);
      sel.value = keep;
      apply();
    }} catch (e) {{}}
  }}
  apply(); tick();
  // served (not from a file): follow what runs
  if (location.protocol.startsWith('http')) {{ setInterval(tick, 5000); setInterval(refresh, 10000); }}
  </script>"""
  with open(out, "w") as f:
      f.write(page)
  return out


def main(argv):
    print(build(os.path.abspath(argv[0]) if argv else config.get().campaigns, os.path.abspath(argv[1]) if len(argv) > 1 else None))
    return 0
