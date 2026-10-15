"""A static site of a project's results: the campaigns' index (with its timelines) and the runs' flame graphs and audit
reports, for publishing (e.g. on GitHub Pages).

  perflab site <dest> [--title <title>] [--with-raw]

Copies <campaigns> and <runs> (perflab.toml) into <dest>, writes <dest>/index.html linking them, and replaces the home
directory in copied text with `~`. xctrace traces and their exports, and JFR recordings, are left out unless --with-raw.
"""
import argparse, glob, html, os, re, shutil

from . import config, index

RAW = re.compile(r"(\.trace$|\.trace/|\.counters\.xml$|\.toc\.xml$|\.bythread\.xml$|\.jfr$|\.collapsed$)")
TEXT = (".html", ".json", ".tsv", ".txt", ".md", ".log", ".args", ".js")


def copy_tree(src, dest, with_raw):
    home = os.path.expanduser("~")
    for dirpath, dirnames, files in os.walk(src):
        rel = os.path.relpath(dirpath, src)
        if not with_raw and RAW.search(rel + "/"):
            dirnames[:] = []
            continue
        for f in files:
            path = os.path.join(rel, f)
            if not with_raw and RAW.search(path):
                continue
            out = os.path.join(dest, path)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            if f.endswith(TEXT):
                with open(os.path.join(dirpath, f), errors="replace") as fh:
                    text = fh.read()
                with open(out, "w") as fh:
                    fh.write(text.replace(home, "~"))
            else:
                shutil.copy(os.path.join(dirpath, f), out)


def metrics_table(result):
    """A run's JMH results: per benchmark and parameters, the score and the secondary metrics worth reading."""
    import json
    esc = html.escape
    keep = re.compile(r"^(xctrace\.|paired\.|gc\.alloc\.rate\.norm$|gc\.time$|jit\.compilations$|jit\.lastWarmup\.compilations$)")
    out = []
    for r in json.load(open(result)):
        params = " ".join(f"{k}={v}" for k, v in r.get("params", {}).items() if v)
        p = r["primaryMetric"]
        num = lambda v, f: format(v, f) if isinstance(v, (int, float)) else str(v)
        err = "" if not isinstance(p["scoreError"], (int, float)) else f" ± {p['scoreError']:.3g}"
        rows = [f"<tr><th>score</th><td>{num(p['score'], '.6g')}{err} {esc(p['scoreUnit'])}</td></tr>"]
        for k, v in sorted(r.get("secondaryMetrics", {}).items()):
            if keep.search(k) and not k.endswith(".other"):
                rows.append(f"<tr><th>{esc(k)}</th><td>{num(v['score'], '.6g')} {esc(v.get('scoreUnit', ''))}</td></tr>")
        name = r["benchmark"].rsplit(".", 2)
        out.append(f"<details><summary><b>{esc('.'.join(name[-2:]))}</b> {esc(params)}</summary><table class='m'>{''.join(rows)}</table></details>")
    return "".join(out)


# the overview's columns: (heading, metric, format); per-op counts are shown per 1,000 instructions by XctraceProfiler
OVERVIEW = [("IPC", "xctrace.IPC.bench", "{:.2f}"), ("L1D misses /k", "xctrace.L1D_CACHE_MISS_LD_NONSPEC/kinst", "{:.2f}"),
            ("branch mispredicts /k", "xctrace.BRANCH_MISPRED_NONSPEC/kinst", "{:.2f}"),
            ("L1I misses /k", "xctrace.L1I_CACHE_MISS_DEMAND/kinst", "{:.2f}"),
            ("useful %", "xctrace.useful.bench", "{:.1f}"), ("front end %", "xctrace.delivery.bench", "{:.1f}"),
            ("back end %", "xctrace.processing.bench", "{:.1f}"), ("discarded %", "xctrace.discarded.bench", "{:.1f}"),
            ("instructions/op", "xctrace.INST_ALL", "{:.3g}"), ("cycles/op", "xctrace.CORE_ACTIVE_CYCLE", "{:.3g}")]


def overview(dest, runs):
    """One row per run with PMU counters (xctrace): the counters worth comparing across runs."""
    import json
    esc = html.escape
    rows, used = [], set()
    for run in runs:
        f = os.path.join(run, "result.json")
        if not os.path.exists(f) or not os.path.getsize(f):
            continue
        for r in json.load(open(f)):
            m = r.get("secondaryMetrics", {})
            if not any(k.startswith("xctrace.") for k in m):
                continue
            cells = {}
            for head, key, fmt in OVERVIEW:
                if key in m:
                    cells[head] = fmt.format(m[key]["score"])
                    used.add(head)
            p = r["primaryMetric"]
            rows.append((os.path.basename(run), f"{p['score']:.4g} {p['scoreUnit']}", cells))
    if not rows:
        return ""
    heads = [h for h, _, _ in OVERVIEW if h in used]
    body = "".join(f"<tr><th><a href='#{esc(n)}'>{esc(n)}</a></th><td>{esc(sc)}</td>" + "".join(f"<td>{c.get(h, '')}</td>" for h in heads) + "</tr>"
                   for n, sc, c in rows)
    return (f"<h2>PMU counters by run</h2><p class='k'>Benchmark thread only (xctrace). Misses per 1,000 instructions; top-down "
            f"shares of issue slots (CPU Counters template).</p><div class='scroll'><table class='o'><tr><th>run</th><th>score</th>"
            + "".join(f"<th>{esc(h)}</th>" for h in heads) + f"</tr>{body}</table></div>")


def text_page(path, dest, title):
    page = path + ".html"
    with open(page, "w") as f:
        f.write(f"<!doctype html><meta charset='utf-8'><title>{html.escape(title)}</title>{STYLE}<main><h1>{html.escape(title)}</h1>"
                f"<pre>{html.escape(open(path, errors='replace').read())}</pre></main>")
    return os.path.relpath(page, dest)


DOC = "https://github.com/retronym/jvm-perf-lab/blob/main/doc/pmu-counters.md"


def about(name, profile, names):
    """What a PMU-counter run shows, with links to the same benchmark's runs under the other integration."""
    esc = html.escape
    kind = profile.partition(":")[0]
    base = re.sub(r"-(xctrace-.*|kperf)$", "", name)
    if kind == "xctrace":
        what, others = "XctraceProfiler: counts per op on the benchmark thread, beside JIT, GC and other threads; methods by leaf only, no stacks.", [f"{base}-kperf"]
    elif kind == "async" and "+" in profile:
        what, others = "async-profiler kperf events: where each PMU event is spent, as flame graphs.", sorted(n for n in names if n.startswith(f"{base}-xctrace-"))
    else:
        return ""
    links = " · ".join(f'<a href="#{esc(o)}">{esc(o)}</a>' for o in others if o in names)
    return f"<p>{esc(what)} {'Same benchmark: ' + links + '. ' if links else ''}<a href=\"{DOC}\">Which to use when</a>.</p>"


def landing(dest, title, runs):
    esc = html.escape
    items = []
    names = {os.path.basename(r) for r in runs}
    for run in runs:
        name = os.path.basename(run)
        profile = open(os.path.join(run, "profile.txt")).read().strip() if os.path.exists(os.path.join(run, "profile.txt")) else ""
        parts = []
        result = os.path.join(run, "result.json")
        if os.path.exists(result):
            parts.append(metrics_table(result))
        links = []
        report = os.path.join(run, "report.md")
        if os.path.exists(report):
            page = os.path.join(run, "report.html")
            with open(page, "w") as f:
                f.write(f"<!doctype html><meta charset='utf-8'><title>{esc(name)}</title>{STYLE}<main><h1>{esc(name)}</h1>"
                        f"<p class='k'>{esc(profile)}</p>{md_tables(open(report).read())}</main>")
            links.append(f'<a href="{esc(os.path.relpath(page, dest))}">audit report</a>')
        for f in sorted(glob.glob(os.path.join(run, "**", "*.methods.txt"), recursive=True)):
            links.append(f'<a href="{esc(text_page(f, dest, name + ": hot methods by counter"))}">hot methods by counter</a>')
        for f in sorted(glob.glob(os.path.join(run, "**", "*.threads.txt"), recursive=True)):
            links.append(f'<a href="{esc(text_page(f, dest, name + ": threads"))}">threads</a>')
        if links:
            parts.append("<p>" + " · ".join(links) + "</p>")
        # flame graphs, <jfr stem>-<event>[-<kind>].html, as a row per event
        graphs = sorted(g for g in glob.glob(os.path.join(run, "**", "*.html"), recursive=True)
                        if not g.endswith((".txt.html", "report.html")))
        events = {}
        for g in graphs:
            base, kind = os.path.basename(g)[:-5], "bench"
            for k in ("bench-classify", "reverse-classify", "reverse", "threads", "classify"):
                if base.endswith("-" + k):
                    base, kind = base[:-len(k) - 1], k
                    break
            event = base[base.index("-hw-") + 4:] if "-hw-" in base else base.rsplit("-", 1)[-1]
            events.setdefault(event, []).append((kind, g))
        if events:
            rows = "".join(f"<tr><th>{esc(e)}</th><td>" + " · ".join(
                f'<a href="{esc(os.path.relpath(g, dest))}">{esc(k)}</a>' for k, g in sorted(gs, key=lambda kg: (kg[0] != "bench", kg[0])))
                + "</td></tr>" for e, gs in events.items())
            parts.append(f"<table class='g'><tr><th>flame graphs</th><td class='k'>bench: benchmark threads · reverse: by leaf · "
                         f"threads: all threads · classify: by category</td></tr>{rows}</table>")
        items.append(f"<section id='{esc(name)}'><h2>{esc(name)}</h2><p class='k'>{esc(profile)}</p>{about(name, profile, names)}{''.join(parts)}</section>")
    campaigns = '<p><a href="campaigns/index.html"><b>Campaigns</b></a>: every campaign, its cells and summaries, flame graphs per cell, differential flame graphs, and fork timelines.</p>' \
        if os.path.exists(os.path.join(dest, "campaigns", "index.html")) else ""
    with open(os.path.join(dest, "index.html"), "w") as f:
        f.write(f"<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                f"<title>{esc(title)}</title>{STYLE}<main><h1>{esc(title)}</h1>{INTRO}{campaigns}{overview(dest, runs)}"
                f"<h2>Runs</h2>{''.join(items) or '<p>none</p>'}</main>")


def md_tables(text):
    """Markdown from auditfold (headings and tables) as HTML."""
    out, rows = [], []
    def flush():
        if rows:
            out.append("<table>" + "".join(rows) + "</table>")
            rows.clear()
    for line in text.splitlines():
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(set(c) <= set("-:") for c in cells):
                continue
            tag = "th" if not rows else "td"
            rows.append("<tr>" + "".join(f"<{tag}>{html.escape(c).replace('`', '')}</{tag}>" for c in cells) + "</tr>")
        else:
            flush()
            if line.startswith("### "):
                out.append(f"<h2>{html.escape(line[4:])}</h2>")
            elif line.strip():
                out.append(f"<p>{html.escape(line)}</p>")
    flush()
    return "".join(out)


STYLE = """<style>:root{--bg:#f6f7f9;--fg:#1d232b;--muted:#5d6875;--line:#dde2e8;--link:#2f6fb2;--panel:#fff}
@media (prefers-color-scheme: dark){:root{--bg:#14181d;--fg:#e3e8ee;--muted:#94a0ad;--line:#2c333c;--link:#6ea8e6;--panel:#1b2027;color-scheme:dark}}
body{background:var(--bg);color:var(--fg);font:14px/1.5 -apple-system,system-ui,sans-serif;margin:0} main{max-width:1100px;margin:0 auto;padding:20px 16px}
a{color:var(--link)} h1{font-size:20px} h2{font-size:15px;margin:16px 0 4px} .k{color:var(--muted);font-size:12px;margin:0}
section{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:10px 14px;margin:10px 0}
table{border-collapse:collapse;font-size:12px;margin:6px 0} details{margin:6px 0} summary{cursor:pointer}
pre{font-size:12px;overflow-x:auto} .scroll{overflow-x:auto} table.o td{text-align:right;white-space:nowrap} table.m th{font-weight:normal;color:var(--muted)} table.g th{width:120px} td,th{border:1px solid var(--line);padding:3px 8px;text-align:left;overflow-wrap:anywhere}</style>"""


INTRO = ""


def main(argv):
    ap = argparse.ArgumentParser(prog="perflab site", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dest")
    ap.add_argument("--title", default="perflab results")
    ap.add_argument("--with-raw", action="store_true")
    ap.add_argument("--intro", help="a Markdown-free HTML paragraph for the top of the landing page")
    x = ap.parse_args(argv)
    global INTRO
    INTRO = f"<p>{x.intro}</p>" if x.intro else ""
    cfg = config.get()
    dest = os.path.abspath(x.dest)
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest)
    if os.path.isdir(cfg.campaigns):
        index.build(cfg.campaigns)
        copy_tree(cfg.campaigns, os.path.join(dest, "campaigns"), x.with_raw)
    runs = []
    if os.path.isdir(cfg.runs):
        copy_tree(cfg.runs, os.path.join(dest, "runs"), x.with_raw)
        runs = sorted(d for d in glob.glob(os.path.join(dest, "runs", "*")) if os.path.isdir(d))
    landing(dest, x.title, runs)
    open(os.path.join(dest, ".nojekyll"), "w").close()
    size = sum(os.path.getsize(os.path.join(p, f)) for p, _, fs in os.walk(dest) for f in fs)
    print(f"{dest}: {size / 1e6:.1f} MB")
    return 0
