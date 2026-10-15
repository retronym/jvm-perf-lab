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


def landing(dest, title, runs):
    esc = html.escape
    items = []
    for run in runs:
        rel = os.path.relpath(run, dest)
        name = os.path.basename(run)
        profile = open(os.path.join(run, "profile.txt")).read().strip() if os.path.exists(os.path.join(run, "profile.txt")) else ""
        links = []
        report = os.path.join(run, "report.md")
        if os.path.exists(report):
            page = os.path.join(run, "report.html")
            with open(page, "w") as f:
                f.write(f"<!doctype html><meta charset='utf-8'><title>{esc(name)}</title>{STYLE}<main><h1>{esc(name)}</h1>"
                        f"<p class='k'>{esc(profile)}</p>{md_tables(open(report).read())}</main>")
            links.append(f'<a href="{esc(os.path.relpath(page, dest))}">audit report</a>')
        # flame graphs: <jfr stem>-<event>[-<kind>].html, the bench graph first
        graphs = sorted(g for g in glob.glob(os.path.join(run, "**", "*.html"), recursive=True) if not g.endswith("report.html"))
        for g in sorted(graphs, key=lambda g: (len(os.path.basename(g)), g)):
            label = re.sub(r"^jfr-[^-]+-", "", os.path.basename(g)[:-5])
            links.append(f'<a href="{esc(os.path.relpath(g, dest))}">{esc(label)}</a>')
        items.append(f"<section><h2>{esc(name)}</h2><p class='k'>{esc(profile)}</p><p>{' · '.join(links)}</p></section>")
    campaigns = '<p><a href="campaigns/index.html"><b>Campaigns</b></a>: every campaign, its cells and summaries, and fork timelines.</p>' \
        if os.path.exists(os.path.join(dest, "campaigns", "index.html")) else ""
    with open(os.path.join(dest, "index.html"), "w") as f:
        f.write(f"<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                f"<title>{esc(title)}</title>{STYLE}<main><h1>{esc(title)}</h1>{campaigns}"
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
table{border-collapse:collapse;font-size:12px} td,th{border:1px solid var(--line);padding:3px 8px;text-align:left;overflow-wrap:anywhere}</style>"""


def main(argv):
    ap = argparse.ArgumentParser(prog="perflab site", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dest")
    ap.add_argument("--title", default="perflab results")
    ap.add_argument("--with-raw", action="store_true")
    x = ap.parse_args(argv)
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
