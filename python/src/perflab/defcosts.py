"""Cost per definition: histograms and outliers, from a compiler's per-definition cost table.

  perflab defcosts [--top 30] [--out <page.html>] [--compare <base.tsv>] [--jfr <recording.jfr>] <costs.tsv>

The table (Scala 3's -Yprofile-defs) has one row per kind of work and definition: kind (def, complete, load,
implicit, inline), symbol, file, line, chars (the definition's size in source characters), calls, self_us (time
excluding nested definitions' work), total_us, max_self_us, self_alloc.

Prints, and writes as a page:
  - per kind: how many definitions, their total self time, and a histogram of self time in power-of-two buckets
  - the definitions with the most self time, all kinds summed, with the split by kind
  - outliers for their size: self time per source character, far above the median for definitions of that kind
    (median plus 3.5 median absolute deviations, on a log scale), among those with at least --min-us of self time
  - with --compare: the definitions whose self time changed most against the base table
  - with --jfr (async-profiler recording with spans from -Yprofile-defs-listener): a flame graph of each of the top
    definitions, from the samples in its spans (jfrconv --tag)
"""
import argparse, collections, csv, html, math, os, re, subprocess, sys

KINDS = ["unit", "def", "complete", "load", "implicit", "inline", "retype", "transform"]


def load(path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    for r in rows:
        r.setdefault("phase", "")
        for k in ("chars", "calls", "self_us", "total_us", "max_self_us", "self_alloc"):
            r[k] = int(r[k] or 0)
    return rows


def by_symbol(rows):
    """symbol -> {"self_us", "alloc", "kinds": {kind: self_us}, "file", "line", "chars"}, for definitions (not units)"""
    out = {}
    for r in rows:
        if r["kind"] == "unit":
            continue
        d = out.setdefault(r["symbol"], {"self_us": 0, "alloc": 0, "kinds": collections.Counter(), "file": "", "line": "", "chars": 0})
        d["self_us"] += r["self_us"]
        d["alloc"] += r["self_alloc"]
        d["kinds"][r["kind"]] += r["self_us"]
        if r["file"] and not d["file"]:
            d["file"], d["line"] = r["file"], r["line"]
        d["chars"] = max(d["chars"], r["chars"])
    return out


def histogram(values):
    """Counts per power-of-two bucket of µs: bucket b holds [2^b, 2^(b+1)); 0 µs goes in bucket 0."""
    h = collections.Counter(max(0, int(math.log2(v))) if v > 0 else 0 for v in values)
    return [(b, h[b]) for b in range(0, max(h) + 1)] if h else []


def bucket_label(b):
    lo = 2 ** b
    def short(x, unit):
        return f"{x:.1f} {unit}" if x < 10 else f"{x:.0f} {unit}"
    return f"{lo} µs" if lo < 1000 else short(lo / 1000, "ms") if lo < 1_000_000 else short(lo / 1e6, "s")


def median(xs):
    s = sorted(xs)
    n = len(s)
    return 0.0 if n == 0 else s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def size_outliers(syms, min_us=1000, k=3.5):
    """Definitions from source (by_symbol entries with a size) whose log(self time per character, all kinds summed)
    is more than k median absolute deviations above the median: [(score, symbol, entry)], most self time first."""
    cands = [(s, d) for s, d in syms.items() if d["chars"] > 0 and d["self_us"] > 0]
    if len(cands) < 10:
        return []
    logs = [math.log(d["self_us"] / d["chars"]) for _, d in cands]
    m = median(logs)
    mad = median([abs(x - m) for x in logs]) or 1e-9
    out = [((x - m) / mad, s, d) for (s, d), x in zip(cands, logs) if (x - m) / mad > k and d["self_us"] >= min_us]
    return sorted(out, key=lambda t: -t[2]["self_us"])


def ms(us):
    return f"{us / 1000:,.1f}"


def tag_regex(symbol):
    return f".*:\\Q{symbol}\\E"


def flame(jfr, symbol, out, jfrconv):
    r = subprocess.run([jfrconv, "--cpu", "--tag", tag_regex(symbol), "--title", f"{symbol} (exclusive)", jfr, out],
                       capture_output=True, text=True)
    return out if r.returncode == 0 and os.path.exists(out) else None


def report(rows, top, base=None, min_us=1000):
    """(text, html body)"""
    esc = html.escape
    text, parts = [], []
    total = sum(r["self_us"] for r in rows)
    text.append(f"{len(rows)} rows, {ms(total)} ms self time in all")
    # per kind
    parts.append("<h2>By kind</h2><table><tr><th>kind</th><th>definitions</th><th>self ms</th><th>share</th><th>histogram of self time</th></tr>")
    for kind in KINDS + sorted({r["kind"] for r in rows} - set(KINDS)):
        rs = [r for r in rows if r["kind"] == kind]
        if not rs:
            continue
        s = sum(r["self_us"] for r in rs)
        h = histogram([r["self_us"] for r in rs])
        mx = max(n for _, n in h) or 1
        bars = "".join(f"<div class='bar' title='{esc(bucket_label(b))}: {n}'><i style='height:{max(1, 40 * n // mx)}px'></i><span>{esc(bucket_label(b)) if b % 3 == 0 else ''}</span></div>" for b, n in h)
        parts.append(f"<tr><td>{kind}</td><td>{len(rs):,}</td><td>{ms(s)}</td><td>{100 * s / total if total else 0:.1f}%</td><td><div class='hist'>{bars}</div></td></tr>")
        text.append(f"  {kind:9} {len(rs):7,} defs {ms(s):>10} ms  " + " ".join(f"{bucket_label(b)}:{n}" for b, n in h if n))
    parts.append("</table>")
    # units: per phase, and the units with most self time outside their definitions
    units = [r for r in rows if r["kind"] == "unit"]
    if units:
        per_phase = collections.Counter()
        for r in units:
            per_phase[r["phase"]] += r["self_us"]
        parts.append("<h2>Units</h2><p class='k'>Self time of compilation units per phase: the work on a unit outside its definitions' frames.</p>"
                     "<table><tr><th>phase</th><th>self ms</th></tr>" + "".join(f"<tr><td><code>{esc(p)}</code></td><td>{ms(v)}</td></tr>" for p, v in per_phase.most_common()) + "</table>")
        text.append("\nunits, self time per phase:")
        for p, v in per_phase.most_common(top):
            text.append(f"  {ms(v):>9} ms  {p}")
    # top definitions
    syms = by_symbol(rows)
    ranked = sorted(syms.items(), key=lambda kv: -kv[1]["self_us"])[:top]
    parts.append(f"<h2>Most self time</h2><p class='k'>All kinds summed per definition: its type checking, its completion (signature, and body when its type is inferred), its implicit searches and inline expansions.</p>"
                 "<table><tr><th>definition</th><th>self ms</th><th>split by kind</th><th>alloc MB</th><th>chars</th><th>where</th></tr>")
    text.append(f"\nmost self time:")
    for sym, d in ranked:
        split = ", ".join(f"{k} {ms(v)}" for k, v in d["kinds"].most_common() if v)
        where = f"{os.path.basename(d['file'])}:{d['line']}" if d["file"] else ""
        parts.append(f"<tr><td><code>{esc(sym)}</code></td><td>{ms(d['self_us'])}</td><td>{esc(split)}</td><td>{d['alloc'] / 1e6:,.1f}</td><td>{d['chars']:,}</td><td>{esc(where)}</td></tr>")
        text.append(f"  {ms(d['self_us']):>9} ms  {sym}  ({split})")
    parts.append("</table>")
    # outliers for size
    outl = size_outliers(syms, min_us=min_us)[:top]
    parts.append(f"<h2>Slow for their size</h2><p class='k'>Definitions whose self time (all kinds) per character of source is more than 3.5 median absolute deviations above the median (log scale), with at least {ms(min_us)} ms.</p>"
                 "<table><tr><th>definition</th><th>self ms</th><th>chars</th><th>µs per char</th><th>score</th><th>where</th></tr>")
    text.append(f"\nslow for their size:")
    for z, sym, d in outl:
        where = f"{os.path.basename(d['file'])}:{d['line']}" if d["file"] else ""
        parts.append(f"<tr><td><code>{esc(sym)}</code></td><td>{ms(d['self_us'])}</td><td>{d['chars']:,}</td><td>{d['self_us'] / d['chars']:.1f}</td><td>{z:.1f}</td><td>{esc(where)}</td></tr>")
        text.append(f"  {ms(d['self_us']):>9} ms  {d['chars']:6} chars  {sym}")
    parts.append("</table>" if outl else "<p>None.</p>")
    # comparison
    if base is not None:
        b = by_symbol(base)
        deltas = [(d["self_us"] - b.get(s, {"self_us": 0})["self_us"], s, d["self_us"]) for s, d in syms.items()]
        deltas += [(-d["self_us"], s, 0) for s, d in b.items() if s not in syms]
        deltas.sort(key=lambda t: -abs(t[0]))
        tot_b = sum(r["self_us"] for r in base)
        parts.append(f"<h2>Changed against the base</h2><p class='k'>Base {ms(tot_b)} ms, this {ms(total)} ms in all ({100 * (total / tot_b - 1) if tot_b else 0:+.1f}%).</p>"
                     "<table><tr><th>definition</th><th>change ms</th><th>base ms</th><th>this ms</th></tr>")
        text.append(f"\nchanged against the base ({ms(tot_b)} -> {ms(total)} ms):")
        for dlt, s, now in deltas[:top]:
            parts.append(f"<tr><td><code>{esc(s)}</code></td><td>{dlt / 1000:+,.1f}</td><td>{ms(now - dlt)}</td><td>{ms(now)}</td></tr>")
            text.append(f"  {dlt / 1000:+10,.1f} ms  {s}")
        parts.append("</table>")
    return "\n".join(text), "".join(parts), ranked


STYLE = """<style>:root{--bg:#f6f7f9;--fg:#1d232b;--muted:#5d6875;--line:#dde2e8;--link:#2f6fb2;--panel:#fff;--bar:#2f6fb2}
@media (prefers-color-scheme: dark){:root{--bg:#14181d;--fg:#e3e8ee;--muted:#94a0ad;--line:#2c333c;--link:#6ea8e6;--panel:#1b2027;--bar:#6ea8e6;color-scheme:dark}}
body{background:var(--bg);color:var(--fg);font:13px/1.5 -apple-system,system-ui,sans-serif;margin:0}main{padding:16px;max-width:1200px}
a{color:var(--link)}h1{font-size:18px}h2{font-size:15px;margin-top:22px}.k{color:var(--muted);font-size:12px}
table{border-collapse:collapse;background:var(--panel)}td,th{border:1px solid var(--line);padding:3px 8px;text-align:left;vertical-align:bottom}
code{font-size:12px;overflow-wrap:anywhere}.hist{display:flex;gap:1px;align-items:flex-end;height:58px}
.bar{display:flex;flex-direction:column;align-items:center;width:14px}.bar i{display:block;width:12px;background:var(--bar)}
.bar span{font-size:9px;color:var(--muted);white-space:nowrap;height:14px}</style>"""


def main(argv):
    ap = argparse.ArgumentParser(prog="perflab defcosts", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("table")
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--min-us", type=int, default=1000, help="least self time for a size outlier (default %(default)s µs)")
    ap.add_argument("--compare", help="a base table to compare against")
    ap.add_argument("--jfr", help="an async-profiler recording with per-definition spans, for flame graphs of the top definitions")
    ap.add_argument("--flames", type=int, default=10, help="how many of the top definitions get a flame graph with --jfr")
    ap.add_argument("--out", help="write the page here (default: beside the table, .html)")
    x = ap.parse_args(argv)
    rows = load(x.table)
    base = load(x.compare) if x.compare else None
    text, body, ranked = report(rows, x.top, base, x.min_us)
    print(text)
    out = x.out or re.sub(r"\.tsv$", "", x.table) + ".html"
    if x.jfr:
        from . import jmh
        jfrconv = jmh.jfrconv(jmh.async_lib())
        d = os.path.splitext(out)[0] + "-flames"
        os.makedirs(d, exist_ok=True)
        links = []
        for sym, _ in ranked[:x.flames]:
            f = flame(x.jfr, sym, os.path.join(d, re.sub(r"[^A-Za-z0-9_.$-]", "_", sym)[:150] + ".html"), jfrconv)
            if f:
                links.append(f"<li><a href='{html.escape(os.path.relpath(f, os.path.dirname(os.path.abspath(out))))}'>{html.escape(sym)}</a></li>")
        body += f"<h2>Flame graphs</h2><p class='k'>CPU samples inside each definition's own spans (jfrconv --tag), from {html.escape(os.path.basename(x.jfr))}.</p><ul>{''.join(links)}</ul>"
    title = f"Cost per definition: {os.path.basename(x.table)}"
    with open(out, "w") as f:
        f.write(f"<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{html.escape(title)}</title>{STYLE}<main><h1>{html.escape(title)}</h1>{body}</main>")
    print(f"\n{out}")
    return 0
