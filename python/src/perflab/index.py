"""<campaigns>/index.html: every campaign and every run of `perflab run` (<runs>), newest first, and a live timeline of
the running fork. A campaign shows a summary and its cells (score, cycles, instructions, flags), links to each cell's
flame graphs (dashed until rendered) and timeline, its differential flame graphs, notes (<campaign>/NOTES.md) and
findings (<campaigns>/FINDINGS.md); a run its benchmark, parameters, JVM, status, scores, and links to its timeline,
logs and flame graphs. Graphs and timelines open in a lightbox over the page (ui.py). `perflab ab` rebuilds it around
each cell, `perflab run` at its start and end, and the page refreshes itself.

  perflab index [<campaigns-dir> [<runs-dir>]]
"""
import glob, html, json, os, re, sys, time

from . import ab, config, regraph, specs, timeline, ui

root = None
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


def unit(u):
    return (u or "").replace("us/", "µs/")


def num(x, like=None):
    """A score with four significant digits (separators from 1,000); an error `like` its score, to the same decimals."""
    import math
    ref = abs(like if like is not None else x)
    d = max(0, 3 - int(math.floor(math.log10(ref)))) if ref else 0
    return f"{x:,.{d}f}"


def si(x):
    """A count per op: 3 significant digits with K, M or G."""
    for scale, suffix in ((1e9, "G"), (1e6, "M"), (1e3, "K")):
        if x >= scale:
            return f"{x / scale:.3g}{suffix}"
    return f"{x:.3g}"


def size(b):
    return "" if not b else f"{b / 1e6:.1f}MB" if b >= 1e5 else f"{b / 1e3:.1f}KB" if b >= 1e3 else f"{b:.0f}B"


def flame_graphs(cell):
    """Buttons for an async-profiler cell's or run's flame graphs, a row per event, a button per kind (dashed until rendered)."""
    if not (os.path.exists(os.path.join(cell, "profile.txt")) and open(os.path.join(cell, "profile.txt")).read().startswith("async")):
        return ""
    jfr = (glob.glob(os.path.join(cell, "**", "*.jfr"), recursive=True) or [None])[0]
    if not jfr:
        return ""
    rows = []
    for label, _ in regraph.events_of(cell):
        ev = label.removeprefix("hw-")
        ks = "".join(link(regraph.graph_path(jfr, label, k), k, f"{ev}|{k}", regraph.KIND_HELP.get(k)) for k in regraph.kinds())
        rows.append(f'<span class="ev" title="{esc(regraph.EVENT_HELP.get(ev, ev))}">{esc(ev)}</span><span class="btns">{ks}</span>')
    return f'<div class="graphs">{"".join(rows)}</div>'


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
    attrs = f' data-corpus="{esc(corpus)}" data-lb-group="{esc(f"{spec} · {corpus} · {variant} #{n}")}"'
    try:
        r = json.load(open(res_f))[0]
        p = r["primaryMetric"]
    except (OSError, ValueError, IndexError, KeyError):
        # JMH writes result.json when the fork ends, so an empty or partial one is a cell still running
        return ((f' data-running="1"{attrs} data-profiled="0"', [esc(corpus), f"{esc(variant)} #{esc(n)}", '<span class="badge running">running</span>']
                 + [""] * 5, f'<div class="cellg"><span class="btns">{timeline_link(cell)}</span></div>' if os.path.exists(os.path.join(cell, "timeline.html")) else ""),
                time.time(), corpus, None)
    m = r.get("secondaryMetrics", {})
    cyc = m.get("xctrace.CORE_ACTIVE_CYCLE", {}).get("score")
    ins = m.get("xctrace.INST_ALL", {}).get("score")
    alloc = m.get("gc.alloc.rate.norm", {}).get("score")
    # a paired cell's -prof gc mixes its variants, so show each variant's own
    paired_alloc = [(k.removeprefix("paired.alloc."), x["score"]) for k, x in m.items()
                    if k.startswith("paired.alloc.") and ".delta%" not in k]
    alloc_html = (" · ".join(f"{esc(v)} {x / 1e6:.1f}MB" for v, x in paired_alloc) if paired_alloc
                  else f"{alloc / 1e6:.1f}MB" if alloc else "")
    scalac = r.get("params", {}).get("scalacOptions", "")
    pattern = re.compile(config.get().get("index", "flags"))
    flags = " ".join([a for a in r["jvmArgs"] if pattern.search(a) and not a.startswith("-Dperflab.")] + ([scalac] if scalac else []))
    graphs = flame_graphs(cell)
    tl = timeline_link(cell) if os.path.exists(os.path.join(cell, "timeline.html")) else ""
    when = os.path.getmtime(res_f)
    version = specs.of_cell(cell)
    ver_html = f' <span class="when" title="spec version">spec {esc(version)}</span>' if version else ""
    cells = [esc(corpus), f"{esc(variant)} #{esc(n)}{ver_html}", f"{num(p['score'])} ± {num(p['scoreError'], p['score'])}",
             si(cyc) if cyc else "", si(ins) if ins else "", alloc_html,
             f"<code>{esc(flags)}</code>" if flags else "", f'<span class="when">{stamp(when)}</span>']
    detail = (f'<div class="cellg">{f"<span class={chr(34)}btns{chr(34)}>{tl}</span>" if tl else ""}{graphs}</div>') if tl or graphs else ""
    return ((f'{attrs} data-profiled="{1 if graphs else 0}"', cells, detail), when, corpus,
            (variant, p["score"], cyc, ins, version, alloc, m, p.get("scoreUnit", "")))


def summary(name, cells):
    """Per corpus and variant: mean score, cycles/op, instructions/op and allocation/op over rounds, each against the
    spec's first variant (in the order of the campaign's spec.json, else alphabetical). For a paired campaign, each
    variant's own metrics and the paired differences within forks (`paired_summary`)."""
    spec_f = os.path.join(root, name, "spec.json")
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
        cols = ((1, num), (2, lambda x: f"{x / 1e9:.3f}G"), (3, lambda x: f"{x / 1e9:.3f}G"), (5, lambda x: f"{x / 1e6:.1f}MB"))
        base = {i: stats([c[i] for c in vs[names[0]]])[0] for i, _ in cols}
        for v in names:
            cs = vs[v]
            tds = [f"{esc(corpus)}{mixed(vs) if v == names[0] else ''}", esc(v), str(len(cs))]
            for i, fmt in cols:
                mean, sd = stats([c[i] for c in cs])
                if mean is None:
                    tds += ["", ""]; continue
                rel_sd = f" ± {100 * sd / mean:.1f}%" if len(cs) > 1 else ""
                tds += [f"{fmt(mean)}{rel_sd}", "" if v == names[0] or not base[i] else f"{100 * (mean / base[i] - 1):+.2f}%"]
            out.append(("", tds))
    score = esc(unit(units.pop())) if len(units) == 1 else "score"
    heads = [("corpus", False), ("variant", False), ("n", False), (score, False), ("Δ", False), ("cycles/op", False), ("Δ", False),
             ("instructions/op", False), ("Δ", False), ("alloc/op", False), ("Δ", False)]
    return table(heads, out, "t summary") if out else ""


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
    for corpus in sorted(cells):
        forks = [c[6] for cs in cells[corpus].values() for c in cs]
        for v in names:
            tds = [f"{esc(corpus)}{mixed(cells[corpus]) if v == names[0] else ''}", esc(v), str(len(forks))]
            for _, key, scale, fmt in ab.PAIRED_METRICS:
                m, ds, _ = ab.paired_metric(forks, key.format(v))
                tds += [fmt.format(m / scale) if m is not None else "", ab.delta_summary(ds) if ds else ""]
            out.append(("", tds))
    heads = [("corpus", False), ("variant", False), ("forks", False)]
    heads += [h for label, *_ in ab.PAIRED_METRICS for h in ((esc(label), False), ("Δ (paired)", False))]
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
    return (f'<details class="specs" id="{sid}-specs"><summary>Spec versions <span class="k">({len(items)})</span></summary>'
            f'<ul>{"".join(items)}</ul></details>')


# JMH options that take no value; every other option in a run's jmh.args is followed by one
JMH_FLAGS = {"-h", "-l", "-lp", "-lprof", "-lrf"}
RUN_STATE = "run.json"
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
    links = [timeline_link(run)] + [link(os.path.join(run, f), label) for f, label in (("jmh.log", "jmh.log"), ("build.log", "build.log"),
                                                                                       ("report.md", "audit report"))
                                    if os.path.exists(os.path.join(run, f))]
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
        rows = table(heads, out)
    progress = iterations(run) if status == "running" else ""
    mtimes = [os.path.getmtime(os.path.join(run, f)) for f in os.listdir(run)] or [os.path.getmtime(run)]
    args_f = os.path.join(run, "jmh.args")
    started = os.path.getmtime(args_f) if os.path.exists(args_f) else min(mtimes)
    last = time.time() if status == "running" else max(mtimes)
    when = span(started, max(mtimes)) if status != "running" else f"since {stamp(started)}"
    badge = f'<span class="badge {status}"{f" title={chr(34)}{esc(detail)}{chr(34)}" if detail else ""}>{status}</span>'
    return last, (f'<section class="card run" id="run-{esc(name)}" data-last="{last:.0f}" data-notes="0" data-lb-group="{esc(name)}">'
                  f'{card_head("run", name, badge, when, "".join(links))}'
                  f'<p class="facts">{" · ".join(facts)}{f"<br>{esc(progress)}" if progress else ""}</p>{rows}{graphs}</section>')


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
    r = json.load(open(os.path.join(root, "running.json")))
    running = " · running" if r.get("campaign") == name else ""
  except (OSError, ValueError):
    pass
  cls = "done" if done >= planned else "running" if running else "partial"
  return f'<span class="badge {cls}">{done} of {planned} cells{running}</span>'


CSS = """
main{max-width:1400px;margin:0 auto;padding:0 20px 24px}
.bar{position:sticky;top:0;z-index:10;background:var(--bg);display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center;padding:10px 0;
  border-bottom:1px solid var(--line);margin-bottom:14px}
.bar h1{font-size:17px;margin:0;display:flex;gap:8px;align-items:center}
.fg{display:inline-flex;flex-wrap:wrap;gap:4px;align-items:center} .fl{color:var(--muted);font-size:12px;margin-right:2px}
#q{border:1px solid var(--line);background:var(--panel);color:var(--fg);border-radius:6px;padding:4px 8px;font:inherit;min-width:220px;margin-left:auto}
.kind{font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);border:1px solid var(--line);border-radius:4px;padding:0 5px;line-height:16px}
.card .notes{border-left:3px solid var(--link);padding:0 12px;margin:8px 0 12px} .notes h3{margin:6px 0;font-size:13px}
#campaigns>.notes{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--link);border-radius:10px;padding:4px 16px;margin:0 0 14px}
.mixed{color:var(--warn);font-size:11px} details.specs{margin:2px 0 6px;font-size:12px} details.specs summary{cursor:pointer;color:var(--muted)}
details.specs ul{margin:2px 0 6px;padding-left:20px}
.diffs{display:flex;flex-wrap:wrap;gap:4px 8px;align-items:center;margin:4px 0 8px}
table.summary td:nth-child(n+3),table.summary th:nth-child(n+3){text-align:right;white-space:nowrap}
tr[data-running] td{color:var(--muted)} table.t td:nth-child(2){white-space:nowrap}
table.t tr.has-sub td{border-bottom:0} table.t tr.sub td{padding-top:0} .cellg{display:flex;flex-wrap:wrap;gap:4px 16px;align-items:baseline}
.cellg .graphs{margin:0} h3.sub{font-size:12.5px;margin:12px 0 0;font-weight:600}
.hidden{display:none!important} section.card{scroll-margin-top:80px}
#tl .card-h{gap:6px 12px} #tl select{font:inherit;max-width:100%;padding:2px 4px;border:1px solid var(--line);border-radius:6px;background:var(--panel);color:var(--fg)}
#tl label{white-space:nowrap} #tl .help{margin-left:auto}
@media (max-width:700px){main{padding:0 12px 16px} .bar{position:static} #q{min-width:0;width:100%;margin-left:0} .card{padding:10px 12px}}
"""


def build(campaigns, runs=None):
  """<campaigns>/index.html over the campaigns and the runs of `perflab run` (<runs>, default [paths] runs)."""
  global root
  root = campaigns
  runs = runs or config.get().runs
  os.makedirs(root, exist_ok=True)
  sections = []
  all_corpora = set()
  timeline_cells = []  # (mtime, value, label, group) of cells with an iterations.tsv, for the timeline panel
  for spec_dir in glob.glob(os.path.join(root, "*/")):
      name = os.path.basename(spec_dir.rstrip("/"))
      rows, whens, corpora, cells, counts = [], [], set(), {}, {}
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
      all_corpora |= corpora
      last = max(whens) if whens else os.path.getmtime(spec_dir)
      when = span(min(whens), last) if whens else stamp(last)
      has_notes = os.path.exists(os.path.join(spec_dir, "NOTES.md"))
      buttons = link(os.path.join(spec_dir, "report.md"), "report.md") if os.path.exists(os.path.join(spec_dir, "report.md")) else ""
      units = {c[7] for vs in cells.values() for cs in vs.values() for c in cs}
      heads = [(esc(unit(units.pop())) if len(units) == 1 else "score", n) if h == "{unit}" else (h, n) for h, n in CELL_HEADS]
      sections.append((last, f'<section class="card campaign" id="{sid}" data-last="{last:.0f}" data-notes="{1 if has_notes else 0}">'
                             f'{card_head("campaign", name, progress_badge(prog, name), when, buttons)}'
                             f'{notes(os.path.join(spec_dir, "NOTES.md"))}{diff_html}{spec_history(spec_dir, counts, sid)}{sub("Summary", "means over rounds; Δ against the first variant") + summ if (summ := summary(name, cells)) else ""}'
                             f'{sub("Cells", "one per variant and round") + table(heads, rows) if rows else ""}</section>'))
  for run in glob.glob(os.path.join(runs, "*/")) if runs else []:
      sec = run_section(run)
      if sec:
          sections.append(sec)
          tsv = os.path.join(run, "iterations.tsv")
          if os.path.exists(tsv):
              timeline_cells.append((os.path.getmtime(tsv), os.path.relpath(run, root).rstrip("/") + "/",
                                     os.path.basename(run.rstrip('/')), "runs"))
  sections = [h for _, h in sorted(sections, key=lambda x: -x[0])]
  options = "".join(f'<optgroup label="{g}">' + "".join(f'<option value="{esc(v)}">{esc(l)}</option>'
                                                        for _, v, l, gg in sorted(timeline_cells, reverse=True) if gg == g) + "</optgroup>"
                    for g in ("runs", "campaign cells") if any(c[3] == g for c in timeline_cells))
  chips = "".join(f'<button class="chip" data-corpus="{esc(c)}">{esc(c)}</button>' for c in sorted(all_corpora))
  kinds = "".join(f"<li><b>{esc(k)}</b>: {esc(regraph.KIND_HELP[k])}</li>" for k in regraph.kinds() if k in regraph.KIND_HELP)
  help_html = ui.help_popover(
      "<p style='margin-top:0'>Newest first. A campaign compares variants over rounds; a run is one <code>perflab run</code>.</p>"
      "<p>Timelines and flame graphs open over this page: chips switch between the graphs of the same run or cell, "
      "<b>[</b> and <b>]</b> step, <b>↗</b> opens one in a new tab, Esc closes. Dashed buttons are not rendered yet; "
      f"they turn into links when <code>perflab regraph</code> finishes.</p><p style='margin-bottom:0'>Graph kinds:</p><ul style='margin:2px 0;padding-left:18px'>{kinds}</ul>")
  tl_help = ui.help_popover("Each fork from JVM start to exit. Iterations appear as they finish; counter lanes (xctrace) once the fork has "
                            "finished. Wheel or pinch to zoom, drag to pan, double-click to reset.", right=True)

  page = f"""{ui.HEAD}<title>Campaigns and runs</title>
  {ui.style(ui.BASE, ui.LIGHTBOX_CSS, CSS, timeline.CSS)}
  <main>
  <header class="bar"><h1>Campaigns and runs {help_html}</h1>
  {f'<span class="fg"><span class="fl">corpus</span>{chips}</span>' if chips else ''}
  <span class="fg"><span class="fl">show</span><button class="chip" data-kind="profiled">profiled</button><button class="chip" data-kind="timing">timing only</button><button class="chip" data-kind="notes">with notes</button></span>
  <span class="fg"><span class="fl">updated</span><button class="chip" data-age="10800">last 3 h</button><button class="chip" data-age="86400">last 24 h</button></span>
  <input id="q" type="search" placeholder="filter: name, flags, notes…"></header>
  <section class="card" id="tl"><div class="card-h"><h2>Fork timeline</h2><select id="tl-cell">{options}</select>
  <label class="k"><input type="checkbox" id="tl-follow" checked> follow the running fork</label><span id="tl-status"></span>{tl_help}</div>
  <div class="tl-legend" id="tl-legend"></div><svg class="timeline" id="tl-chart"></svg></section>
  <div class="tl-tip" id="tl-tip"></div>
  <div id="campaigns">{notes(os.path.join(root, "FINDINGS.md"))}
  {''.join(sections)}</div></main>
  <script>{timeline.script()}</script>{ui.lightbox_script()}
  <script>
  const chips = [...document.querySelectorAll('.bar .chip')];
  chips.forEach(c => c.onclick = () => {{ c.classList.toggle('on'); apply(); }});
  document.getElementById('q').oninput = apply;
  function on(attr) {{ return chips.filter(c => c.classList.contains('on') && c.dataset[attr]).map(c => c.dataset[attr]); }}
  function apply() {{
    const corpora = on('corpus'), kinds = on('kind'), ages = on('age').map(Number);
    const q = document.getElementById('q').value.toLowerCase(), now = Date.now() / 1000;
    for (const sec of document.querySelectorAll('#campaigns section')) {{
      let visible = 0;
      for (const tr of sec.querySelectorAll('tr[data-corpus]')) {{
        let ok = !corpora.length || corpora.includes(tr.dataset.corpus);
        if (kinds.includes('profiled') && !kinds.includes('timing')) ok = ok && tr.dataset.profiled === '1';
        if (kinds.includes('timing') && !kinds.includes('profiled')) ok = ok && tr.dataset.profiled === '0';
        tr.classList.toggle('hidden', !ok); if (ok) visible++;
      }}
      let show = visible > 0 || !sec.querySelector('tr[data-corpus]');
      if (kinds.includes('notes')) show = show && sec.dataset.notes === '1';
      if (ages.length) show = show && now - Number(sec.dataset.last) < Math.max(...ages);
      if (q) show = show && sec.textContent.toLowerCase().includes(q);
      sec.classList.toggle('hidden', !show);
    }}
  }}
  // live: the timeline follows the running fork (running.json, written by `perflab ab` and `perflab run`) and polls its
  // files; the campaign tables are refetched from this page, which they rebuild around every cell
  const tl = BenchTimeline.mount(document.getElementById('tl-chart'), document.getElementById('tl-legend'), document.getElementById('tl-tip'));
  const sel = document.getElementById('tl-cell'), follow = document.getElementById('tl-follow'), status = document.getElementById('tl-status');
  let shown = null, running = null;
  sel.onchange = () => {{ follow.checked = false; tick(); }};
  follow.onchange = tick;
  const dir = c => c.replace(/\\/?$/, '/');
  // a cell's name as the picker shows it: a run's name, or campaign · corpus · variant #round
  const nameOf = r => r.run || (p => p.length >= 4 ? `${{p[0]}} · ${{p[1]}} · ${{p[2]}} #${{p[3]}}` : r.cell)(r.cell.replace(/\\/$/, '').split('/'));
  status.onclick = e => {{ if (e.target.closest('a')) {{ e.preventDefault(); follow.checked = true; tick(); }} }};
  async function tick() {{
    try {{ const r = await fetch('running.json', {{cache: 'no-store'}}); running = r.ok ? await r.json() : null; }} catch (e) {{ running = null; }}
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
    // the timeline's height is known only now: go back to the card the URL names
    if (location.hash && !tick.done) {{ tick.done = true; const t = document.getElementById(location.hash.slice(1)); if (t) t.scrollIntoView(); }}
  }}
  async function refreshTables() {{
    try {{
      const r = await fetch(location.pathname.endsWith('/') ? 'index.html' : location.pathname, {{cache: 'no-store'}});
      if (!r.ok) return;
      const doc = new DOMParser().parseFromString(await r.text(), 'text/html');
      // keep what the reader opened
      const open = new Map([...document.querySelectorAll('#campaigns details[id]')].map(d => [d.id, d.open]));
      document.getElementById('campaigns').innerHTML = doc.getElementById('campaigns').innerHTML;
      for (const [id, o] of open) {{ const d = document.getElementById(id); if (d) d.open = o; }}
      const keep = sel.value;
      sel.innerHTML = doc.getElementById('tl-cell').innerHTML;
      if (keep && ![...sel.options].some(o => o.value === keep)) sel.add(new Option(keep, keep), 0);
      sel.value = keep;
      apply();
    }} catch (e) {{}}
  }}
  tick(); setInterval(tick, 5000); setInterval(refreshTables, 10000);
  </script>"""
  out = os.path.join(root, "index.html")
  open(out, "w").write(page)
  return out


def main(argv):
    print(build(os.path.abspath(argv[0]) if argv else config.get().campaigns, os.path.abspath(argv[1]) if len(argv) > 1 else None))
    return 0
