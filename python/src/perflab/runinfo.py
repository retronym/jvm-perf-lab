"""What the index shows of a run beyond its JMH score: all its metrics, what its profile is for, its PMU counters beside
other runs', its flame graphs' totals, and pages for its text outputs (audit report, hot methods, threads) and for a
campaign's report.md, written next to the files they render.
"""
import glob, html, json, os, re

from . import ui

esc = html.escape


def metrics_details(results):
    """Every metric worth reading of a run's results (score, PMU counters, paired, allocation, GC, JIT), collapsed."""
    keep = re.compile(r"^(xctrace\.|paired\.|gc\.alloc\.rate\.norm$|gc\.time$|jit\.compilations$|jit\.lastWarmup\.compilations$)")
    num = lambda v: format(v, ".6g") if isinstance(v, (int, float)) else str(v)
    out = []
    for r in results:
        p = r["primaryMetric"]
        err = f" ± {num(p['scoreError'])}" if isinstance(p.get("scoreError"), (int, float)) else ""
        rows = [f"<tr><th>score</th><td class='n'>{num(p['score'])}{err}</td><td>{esc(ui.unit(p.get('scoreUnit', '')))}</td></tr>"]
        for k, v in sorted(r.get("secondaryMetrics", {}).items()):
            if keep.search(k) and not k.endswith(".other"):
                rows.append(f"<tr><th>{esc(k)}</th><td class='n'>{num(v['score'])}</td><td>{esc(ui.unit(v.get('scoreUnit', '')))}</td></tr>")
        params = " ".join(f"{k}={v}" for k, v in r.get("params", {}).items() if v)
        head = f"<p class='k'>{esc(r['benchmark'].rsplit('.', 1)[-1])} <code>{esc(params)}</code></p>" if len(results) > 1 else ""
        out.append(f"{head}<div class='scroll'><table class='t m'>{''.join(rows)}</table></div>")
    return f"<details class='metrics'><summary>All metrics</summary>{''.join(out)}</details>" if out else ""


# the counters table's columns: (heading, metric, format); per-op counts are shown per 1,000 instructions by XctraceProfiler
COUNTERS = [("IPC", "xctrace.IPC.bench", "{:.2f}"), ("L1D misses /k", "xctrace.L1D_CACHE_MISS_LD_NONSPEC/kinst", "{:.2f}"),
            ("branch mispredicts /k", "xctrace.BRANCH_MISPRED_NONSPEC/kinst", "{:.2f}"),
            ("L1I misses /k", "xctrace.L1I_CACHE_MISS_DEMAND/kinst", "{:.2f}"),
            ("useful %", "xctrace.useful.bench", "{:.1f}"), ("front end %", "xctrace.delivery.bench", "{:.1f}"),
            ("back end %", "xctrace.processing.bench", "{:.1f}"), ("discarded %", "xctrace.discarded.bench", "{:.1f}"),
            ("instructions/op", "xctrace.INST_ALL", "si"), ("cycles/op", "xctrace.CORE_ACTIVE_CYCLE", "si")]


def counters(runs):
    """(rows, table html): one row per run with PMU counters (xctrace), the counters worth comparing across runs."""
    rows, used = [], set()
    for run in runs:
        f = os.path.join(run, "result.json")
        try:
            results = json.load(open(f))
        except (OSError, ValueError):
            continue
        for r in results:
            m = r.get("secondaryMetrics", {})
            if not any(k.startswith("xctrace.") for k in m):
                continue
            cells = {}
            for head, key, fmt in COUNTERS:
                if key in m:
                    cells[head] = ui.si(m[key]["score"]) if fmt == "si" else fmt.format(m[key]["score"])
                    used.add(head)
            p = r["primaryMetric"]
            rows.append((os.path.basename(run.rstrip("/")), f"{ui.num(p['score'])} {ui.unit(p['scoreUnit'])}", cells, facets(run)))
    if not rows:
        return 0, ""
    heads = [h for h, _, _ in COUNTERS if h in used]
    body = "".join(f"<tr data-benchmark='{esc(fb)}' data-tool='{esc(ft)}'><td><a href='#{esc(n)}'>{esc(n)}</a></td><td class='n'>{esc(sc)}</td>"
                   + "".join(f"<td class='n'>{c.get(h, '')}</td>" for h in heads) + "</tr>"
                   for n, sc, c, (fb, ft) in rows)
    return len(rows), ("<div class='scroll'><table class='t o'><tr><th>run</th><th class='n'>score</th>"
                       + "".join(f"<th class='n'>{esc(h)}</th>" for h in heads) + f"</tr>{body}</table></div>")


DOC = "https://github.com/retronym/jvm-perf-lab/blob/main/doc/pmu-counters.md"


def about(name, profile, names):
    """What a PMU-counter run shows, with links to the same benchmark's runs under the other integration."""
    kind = profile.partition(":")[0]
    base = re.sub(r"-(xctrace-.*|kperf)$", "", name)
    if kind == "xctrace":
        what, others = "XctraceProfiler: counts per op on the benchmark thread, beside JIT, GC and other threads; methods by leaf only, no stacks.", [f"{base}-kperf"]
    elif kind == "async" and "+" in profile:
        what, others = "async-profiler kperf events: where each PMU event is spent, as flame graphs.", sorted(n for n in names if n.startswith(f"{base}-xctrace-"))
    else:
        return ""
    links = " · ".join(f'<a href="#{esc(o)}">{esc(o)}</a>' for o in others if o in names)
    return f"<p class='about'>{esc(what)} {'Same benchmark: ' + links + '. ' if links else ''}<a href=\"{DOC}\">Which to use when</a>.</p>"


def graph_samples(path):
    """The flame graph's total: the root frame's width, the first n(key, width) / f(...) in the page's data."""
    try:
        with open(path, errors="replace") as f:
            for line in f:
                m = re.match(r"^n\((\d+)(?:,(\d+))?", line)
                if m:
                    return int(m.group(2) or 0)
    except OSError:
        pass
    return None


def tool_of(profile):
    kind, _, arg = profile.partition(":")
    if kind == "async":
        return "kperf" if "+" in arg else "async-profiler"
    return kind or "none"


def benchmarks_of(d):
    """The benchmark classes a run or cell measured (from result.json), e.g. ["WordCountBenchmark"]."""
    try:
        return sorted({r["benchmark"].split(".")[-2] for r in json.load(open(os.path.join(d, "result.json")))})
    except (OSError, ValueError, KeyError, IndexError):
        return []


def profile_of(d):
    try:
        return open(os.path.join(d, "profile.txt")).read().strip()
    except OSError:
        return ""


def facets(d):
    """(benchmarks, tool) of a run or cell, for the page's filter chips."""
    return " ".join(benchmarks_of(d)), tool_of(profile_of(d))


PAGE_CSS = """
main{max-width:1100px;margin:0 auto;padding:16px 20px 40px} h1{font-size:18px;margin:6px 0 10px} h2{font-size:15px;margin:20px 0 6px}
pre{font-size:12px;overflow-x:auto;background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:10px}
.scroll{background-color:var(--panel);border:1px solid var(--line);border-radius:8px;padding:0 6px;margin:6px 0 12px}
table.t td{white-space:nowrap}
"""


def fresh(out, src):
    return os.path.exists(out) and os.path.getmtime(out) >= os.path.getmtime(src)


def text_page(path, title, home=None):
    """<path>.html: a text file as a page, unless it is up to date; its brand links `home` (the index). Returns its path."""
    page = path + ".html"
    if not fresh(page, path):
        with open(page, "w") as f:
            f.write(f"{ui.HEAD}<title>{esc(title)}</title>{ui.style(ui.BASE, PAGE_CSS)}{ui.masthead(home=home and os.path.relpath(home, os.path.dirname(page)), slim=True)}"
                    f"<main><h1>{esc(title)}</h1><pre>{esc(open(path, errors='replace').read())}</pre></main>")
    return page


def md_page(md, out, title, note="", home=None):
    """`out`: a Markdown report (headings, tables and paragraphs, as auditfold and `perflab ab report` write) as a page,
    with a link to the Markdown, unless it is up to date. Returns `out`."""
    if not fresh(out, md):
        link = f'<a class="btn" href="{esc(os.path.basename(md))}" download>{esc(os.path.basename(md))}</a>'
        with open(out, "w") as f:
            f.write(f"{ui.HEAD}<title>{esc(title)}</title>{ui.style(ui.BASE, PAGE_CSS)}{ui.masthead(home=home and os.path.relpath(home, os.path.dirname(out)), slim=True)}"
                    f"<main><div class='card-h'><h1>{esc(title)}</h1><span class='btns'>{link}</span></div>"
                    f"{f'<p class=k>{esc(note)}</p>' if note else ''}{md_html(open(md).read())}</main>")
    return out


def md_html(text):
    """Markdown tables, ### headings and paragraphs as HTML."""
    out, rows = [], []
    inline = lambda t: re.sub(r"`([^`]+)`", r"<code>\1</code>", esc(t))
    def flush():
        if rows:
            out.append("<div class='scroll'><table class='t'>" + "".join(rows) + "</table></div>")
            rows.clear()
    for line in text.splitlines():
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue
            tag = "th" if not rows else "td"
            rows.append("<tr>" + "".join(f"<{tag}>{inline(c)}</{tag}>" for c in cells) + "</tr>")
        else:
            flush()
            if line.startswith("#"):
                out.append(f"<h2>{inline(line.lstrip('#').strip())}</h2>")
            elif line.strip():
                out.append(f"<p>{inline(line)}</p>")
    flush()
    return "".join(out)
