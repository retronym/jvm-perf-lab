"""A static site of a project's results, for publishing (e.g. on GitHub Pages): the index's one page of campaigns and
runs (index.py), with an intro, at the site's root, and everything it links.

  perflab site <dest> [--title <title>] [--intro-file <html>] [--footer <html>] [--with-raw]

Copies <campaigns> and <runs> (perflab.toml) into <dest>, renders the page over the copies at <dest>/index.html (the
copied campaigns/index.html redirects to it), and replaces the home directory in copied text with `~`. xctrace traces
and their exports, and JFR recordings, are left out unless --with-raw.
"""
import argparse, os, re, shutil

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
            if f.startswith("."):  # .serve.json and the like: local state
                continue
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


REDIRECT = ('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=../index.html">'
            '<title>Moved</title><p>Campaigns and runs are on <a href="../index.html">one page</a> now.</p>'
            '<script>location.replace("../index.html" + location.hash)</script>')


def main(argv):
    ap = argparse.ArgumentParser(prog="perflab site", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dest")
    ap.add_argument("--title", default="perflab results")
    ap.add_argument("--with-raw", action="store_true")
    ap.add_argument("--intro", help="an HTML paragraph for the top of the page")
    ap.add_argument("--intro-file", help="an HTML fragment for the top of the page; it may use the page's .lead, .ideas, .steps and .terms")
    ap.add_argument("--footer", help="an HTML paragraph for the bottom of the page")
    x = ap.parse_args(argv)
    intro = open(x.intro_file).read() if x.intro_file else f"<p class='lead'>{x.intro}</p>" if x.intro else ""
    cfg = config.get()
    dest = os.path.abspath(x.dest)
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest)
    if os.path.isdir(cfg.campaigns):
        index.build(cfg.campaigns)  # brings the pages it renders beside results (reports, text outputs) up to date
        copy_tree(cfg.campaigns, os.path.join(dest, "campaigns"), x.with_raw)
    if os.path.isdir(cfg.runs):
        copy_tree(cfg.runs, os.path.join(dest, "runs"), x.with_raw)
    os.makedirs(os.path.join(dest, "campaigns"), exist_ok=True)
    index.build(os.path.join(dest, "campaigns"), os.path.join(dest, "runs"), out=os.path.join(dest, "index.html"),
                title=x.title, intro=intro, footer=x.footer or "")
    with open(os.path.join(dest, "campaigns", "index.html"), "w") as f:
        f.write(REDIRECT)
    open(os.path.join(dest, ".nojekyll"), "w").close()
    size = sum(os.path.getsize(os.path.join(p, f)) for p, _, fs in os.walk(dest) for f in fs)
    print(f"{dest}: {size / 1e6:.1f} MB")
    return 0
