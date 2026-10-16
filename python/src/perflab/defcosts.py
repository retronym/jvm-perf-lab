"""Cost per definition: histograms and outliers, from a compiler's per-definition cost table.

  perflab defcosts [--top 30] [--min-us 1000] [--out <page.html>] [--compare <base.tsv>] <costs.tsv>

The table (Scala 3's -Yprofile-defs) has one row per kind of work, phase and key: kind, phase (for the kinds that are
per phase), symbol, file, line, chars (the definition's size in source characters), calls, self_us (time excluding
nested frames' work), total_us, max_self_us, self_alloc. Kinds:
  - phase, unit: a phase, and a compilation unit in a phase, outside the definitions in it; `symbol` is the phase's
    name or the unit's source path
  - def (type checking in the typer), complete (completing a symbol from source: its signature, and its body when its
    type is inferred), load (from a classfile or TASTy), retype (typing after the typer, as in erasure), transform
    (a definition's subtree in a MegaPhase): `symbol` is the definition's full name
  - implicit, inline: implicit searches and inline expansions, charged to the definition they are made in

Prints, and writes as a page:
  - per kind: rows, total self time, and a histogram of self time in power-of-two buckets
  - unit self time per phase
  - the definitions with the most self time, all kinds summed, with the split by kind
  - definitions slow for their size: self time per source character more than --k scaled median absolute deviations
    above the median of all definitions (log scale), with at least --min-us of self time. A class's characters include
    its members', but its self time does not, so classes rarely show up here.
  - with --compare: the definitions whose self time changed most against the base table

For where a definition's time goes, record async-profiler spans with the compiler's span listener and open the flame
graph made with `jfrconv --spans`: its span panel breaks down any frame by definition, and filters by one.
"""
import argparse, collections, csv, html, math, os, re

# Kinds whose rows are containers of definitions, not definitions
CONTAINERS = ("phase", "unit")
KINDS = ["phase", "unit", "def", "complete", "load", "implicit", "inline", "retype", "transform"]
MAD_SCALE = 1.4826  # the median absolute deviation of a normal distribution, in standard deviations
MIN_MAD = 0.1       # in log units, about 10%: when most values are equal the MAD is 0, and every larger value would score


def load(path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    for r in rows:
        for k in ("kind", "phase", "symbol", "file", "line"):
            r[k] = r.get(k) or ""
        for k in ("chars", "calls", "self_us", "total_us", "max_self_us", "self_alloc"):
            r[k] = int(r.get(k) or 0)
    return rows


def by_symbol(rows):
    """symbol -> {"self_us", "alloc", "kinds": {kind: self_us}, "file", "line", "chars"}, for definitions"""
    out = {}
    for r in rows:
        if r["kind"] in CONTAINERS:
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
    h = collections.Counter(max(v, 1).bit_length() - 1 for v in values)
    return [(b, h[b]) for b in range(0, max(h) + 1)] if h else []


def bucket_label(b):
    lo = 2 ** b
    def short(x, unit):
        return f"{x:.1f} {unit}" if x < 10 else f"{x:.0f} {unit}"
    return "<2 µs" if b == 0 else f"{lo} µs" if lo < 1000 else short(lo / 1000, "ms") if lo < 1_000_000 else short(lo / 1e6, "s")


def median(xs):
    s = sorted(xs)
    n = len(s)
    return 0.0 if n == 0 else s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def size_outliers(syms, min_us=1000, k=3.5):
    """Definitions with a size whose log(self time per character, all kinds summed) is more than k scaled median
    absolute deviations above the median: [(score, symbol, entry)], most self time first."""
    cands = [(s, d) for s, d in syms.items() if d["chars"] > 0 and d["self_us"] > 0]
    if len(cands) < 10:
        return []
    logs = [math.log(d["self_us"] / d["chars"]) for _, d in cands]
    m = median(logs)
    spread = max(MAD_SCALE * median([abs(x - m) for x in logs]), MIN_MAD)
    out = [((x - m) / spread, s, d) for (s, d), x in zip(cands, logs) if (x - m) / spread > k and d["self_us"] >= min_us]
    return sorted(out, key=lambda t: -t[2]["self_us"])


def ms(us):
    return f"{us / 1000:,.1f}"


def where(d):
    return f"{os.path.basename(d['file'])}:{d['line']}" if d["file"] else ""


def report(rows, top, base=None, min_us=1000, k=3.5):
    """(text, html body)"""
    esc = html.escape
    text, parts = [], []
    total = sum(r["self_us"] for r in rows)
    text.append(f"{len(rows)} rows, {ms(total)} ms self time in all")
    # per kind
    parts.append("<h2>By kind</h2><table><tr><th>kind</th><th>rows</th><th>self ms</th><th>share</th><th>histogram of self time</th></tr>")
    for kind in KINDS + sorted({r["kind"] for r in rows} - set(KINDS)):
        rs = [r for r in rows if r["kind"] == kind]
        if not rs:
            continue
        s = sum(r["self_us"] for r in rs)
        h = histogram([r["self_us"] for r in rs])
        mx = max(n for _, n in h) or 1
        bars = "".join(f"<div class='bar' title='{esc(bucket_label(b))}: {n}'><i style='height:{max(1, 40 * n // mx)}px'></i><span>{esc(bucket_label(b)) if b % 3 == 0 else ''}</span></div>" for b, n in h)
        parts.append(f"<tr><td>{esc(kind)}</td><td>{len(rs):,}</td><td>{ms(s)}</td><td>{100 * s / total if total else 0:.1f}%</td><td><div class='hist'>{bars}</div></td></tr>")
        text.append(f"  {kind:9} {len(rs):7,} rows {ms(s):>10} ms  " + " ".join(f"{bucket_label(b)}:{n}" for b, n in h if n))
    parts.append("</table>")
    # units, per phase
    per_phase = collections.Counter()
    for r in rows:
        if r["kind"] == "unit":
            per_phase[r["phase"]] += r["self_us"]
    if per_phase:
        parts.append("<h2>Units</h2><p class='k'>Self time of compilation units per phase: the work on a unit outside its definitions' frames.</p>"
                     "<table><tr><th>phase</th><th>self ms</th></tr>" + "".join(f"<tr><td><code>{esc(p)}</code></td><td>{ms(v)}</td></tr>" for p, v in per_phase.most_common()) + "</table>")
        text.append("\nunits, self time per phase:")
        text.extend(f"  {ms(v):>9} ms  {p}" for p, v in per_phase.most_common())
    # top definitions
    syms = by_symbol(rows)
    ranked = sorted(syms.items(), key=lambda kv: -kv[1]["self_us"])[:top]
    parts.append("<h2>Most self time</h2><p class='k'>All kinds summed per definition: its type checking, its completion (signature, and body when its type is inferred), its implicit searches and inline expansions, its retyping and its MegaPhase transforms.</p>"
                 "<table><tr><th>definition</th><th>self ms</th><th>split by kind</th><th>alloc MB</th><th>chars</th><th>where</th></tr>")
    text.append("\nmost self time:")
    for sym, d in ranked:
        split = ", ".join(f"{kind} {ms(v)}" for kind, v in d["kinds"].most_common() if v)
        parts.append(f"<tr><td><code>{esc(sym)}</code></td><td>{ms(d['self_us'])}</td><td>{esc(split)}</td><td>{d['alloc'] / 1e6:,.1f}</td><td>{d['chars']:,}</td><td>{esc(where(d))}</td></tr>")
        text.append(f"  {ms(d['self_us']):>9} ms  {sym}  ({split})")
    parts.append("</table>")
    # outliers for size
    outl = size_outliers(syms, min_us=min_us, k=k)[:top]
    parts.append(f"<h2>Slow for their size</h2><p class='k'>Definitions whose self time (all kinds) per character of source is more than {k:g} scaled median absolute deviations above the median (log scale), with at least {ms(min_us)} ms. A class's characters include its members' but its self time does not, so classes rarely appear.</p>"
                 "<table><tr><th>definition</th><th>self ms</th><th>chars</th><th>µs per char</th><th>score</th><th>where</th></tr>")
    text.append("\nslow for their size:")
    for z, sym, d in outl:
        parts.append(f"<tr><td><code>{esc(sym)}</code></td><td>{ms(d['self_us'])}</td><td>{d['chars']:,}</td><td>{d['self_us'] / d['chars']:.1f}</td><td>{z:.1f}</td><td>{esc(where(d))}</td></tr>")
        text.append(f"  {ms(d['self_us']):>9} ms  {d['chars']:6} chars  {sym}")
    parts.append("</table>" if outl else "<p>None.</p>")
    # comparison
    if base is not None:
        now = {s: d["self_us"] for s, d in syms.items()}
        before = {s: d["self_us"] for s, d in by_symbol(base).items()}
        changes = sorted(((now.get(s, 0) - before.get(s, 0), s) for s in now.keys() | before.keys()), key=lambda t: -abs(t[0]))
        tot_b = sum(r["self_us"] for r in base)
        parts.append(f"<h2>Changed against the base</h2><p class='k'>Base {ms(tot_b)} ms, this {ms(total)} ms in all ({100 * (total / tot_b - 1) if tot_b else 0:+.1f}%).</p>"
                     "<table><tr><th>definition</th><th>change ms</th><th>base ms</th><th>this ms</th></tr>")
        text.append(f"\nchanged against the base ({ms(tot_b)} -> {ms(total)} ms):")
        for delta, s in changes[:top]:
            parts.append(f"<tr><td><code>{esc(s)}</code></td><td>{delta / 1000:+,.1f}</td><td>{ms(before.get(s, 0))}</td><td>{ms(now.get(s, 0))}</td></tr>")
            text.append(f"  {delta / 1000:+10,.1f} ms  {s}")
        parts.append("</table>")
    return "\n".join(text), "".join(parts)


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
    ap.add_argument("--k", type=float, default=3.5, help="size outliers: how many scaled MADs above the median (default %(default)s)")
    ap.add_argument("--compare", help="a base table to compare against")
    ap.add_argument("--out", help="write the page here (default: beside the table, .html)")
    x = ap.parse_args(argv)
    rows = load(x.table)
    base = load(x.compare) if x.compare else None
    text, body = report(rows, x.top, base, x.min_us, x.k)
    print(text)
    out = x.out or re.sub(r"\.tsv$", "", x.table) + ".html"
    title = f"Cost per definition: {os.path.basename(x.table)}"
    with open(out, "w") as f:
        f.write(f"<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{html.escape(title)}</title>{STYLE}<main><h1>{html.escape(title)}</h1>{body}</main>")
    print(f"\n{out}")
    return 0
