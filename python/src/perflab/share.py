"""`perflab share`: a campaign's results as a microsite, published with `share` (github.com/retronym/share: a Cloudflare
Pages site, public by an unguessable URL, not indexed).

  perflab share <campaign> [--profiles] [--asm] [--logs] [--dry-run [--out <dir>]] [--json]
  perflab share <campaign> --rm

The site is the index's page (index.py) over a copy of the campaign, the way `perflab site` makes one of a project,
with the home directory replaced by `~` in text. How much of the campaign goes:
- always its results: the card and its summaries, the compare and report pages, the spec and notes, every cell's
  result, iterations, load, GC log and fork timeline;
- --profiles: the flame graphs and profile diffs (their rendered pages), and a campaign that profiles it ("profileOf");
- --asm: the machine code pages, and an asm capture that explains it ("asmOf");
- --logs: the build's and JMH's logs, which name paths, hosts and commands.
Raw recordings (xctrace traces, JFR, collapsed stacks, JIT recordings) never go: they are hundreds of MB, over Pages'
25 MiB a file; `perflab site --with-raw` exports them.

Sharing a campaign again replaces the site at the same URL (<campaign>/share.json records it); --rm takes it down.
The `share` command and its site come from ~/.perflab/share.toml:

  command = "~/code/retronym/share/bin/share"
  url = "https://share.example.org"                 # its SHARE_URL
  [env]                                             # for the command, e.g. its wrangler
  SHARE_WRANGLER = "~/code/retronym/share/node_modules/.bin/wrangler"

else `share` on the PATH with SHARE_URL from the environment.
"""
import argparse, datetime, glob, json, os, re, secrets, shutil, subprocess, sys, tempfile, tomllib

from . import config, index, site, testbed

DEPTHS = ("profiles", "asm", "logs")
RECORD = "share.json"  # in the campaign: {url, slug, depth, at, files, bytes}
SETTINGS = "~/.perflab/share.toml"
LOGS = re.compile(r"(^|/)(build|jmh|output)\.log$")
NEVER = re.compile(r"\.regraph$|\.jitrec$|(^|/)vm-pid[^/]*\.log(\.gz)?$")


def kind(rel):
    """What a file of a campaign (`rel`, its path in it) is for sharing: raw (never), results, profiles, asm or logs."""
    parts = rel.split("/")
    if any(p.startswith(".") for p in parts) or site.RAW.search(rel) or NEVER.search(rel) or parts[-1] == RECORD:
        return "raw"
    if "asm" in parts[:-1] or parts[-1].startswith("asm-diff-"):
        return "asm"
    if LOGS.search(rel):
        return "logs"
    cell = len(parts) >= 4 and parts[2].isdigit()
    if parts[-1] == "kperf-samples.json" or (cell and len(parts) > 4) \
            or (parts[-1].endswith(".html") and (cell and parts[-1] != "timeline.html" or parts[0].startswith("diff-"))):
        return "profiles"
    return "results"


def linked(campaigns, name, depth):
    """The campaigns that go with `name`: one that profiles it (with profiles), an asm capture of it (with asm)."""
    out = []
    for f in sorted(glob.glob(os.path.join(campaigns, "*", "spec.json"))):
        try:
            s = json.load(open(f))
        except (OSError, ValueError):
            continue
        if ("profiles" in depth and s.get("profileOf") == name) or ("asm" in depth and s.get("asmOf") == name):
            out.append(os.path.basename(os.path.dirname(f)))
    return out


def files(camp, depth):
    """(path, its path in the campaign) of what goes, for the depth."""
    want = {"results", *depth}
    for d, dirs, fs in os.walk(camp):
        dirs[:] = [x for x in dirs if not x.startswith(".")]
        for f in fs:
            p = os.path.join(d, f)
            rel = os.path.relpath(p, camp).replace(os.sep, "/")
            if kind(rel) in want and not os.path.islink(p):
                yield p, rel


def build(name, depth, dest):
    """The site in `dest`: {campaigns, files, bytes}."""
    cfg = config.get()
    camp = os.path.join(cfg.campaigns, name)
    if not os.path.exists(os.path.join(camp, "spec.json")):
        raise SystemExit(f"perflab share: no campaign {name} in {cfg.campaigns}")
    index.build(cfg.campaigns)  # the pages it renders beside results (reports, compare pages), up to date
    camps = [name] + linked(cfg.campaigns, name, depth)
    home = os.path.expanduser("~")
    for c in camps:
        for src, rel in files(os.path.join(cfg.campaigns, c), depth):
            out = os.path.join(dest, "campaigns", c, rel)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            # the home directory as `~` in any text that names it, whatever its extension (spec.source has none)
            with open(src, "rb") as fh:
                data = fh.read()
            if home.encode() in data:
                try:
                    data = data.decode().replace(home, "~").encode()
                except UnicodeDecodeError:
                    pass
            if rel.endswith(testbed.CELL_FILE):  # the testbed's name and hardware, not its host's name
                try:
                    data = json.dumps({k: v for k, v in json.loads(data).items() if k != "host"}).encode() + b"\n"
                except (ValueError, AttributeError):
                    pass
            with open(out, "wb") as o:
                o.write(data)
            shutil.copystat(src, out)  # the page dates results by their files' times
    os.makedirs(os.path.join(dest, "runs"), exist_ok=True)
    s = json.load(open(os.path.join(camp, "spec.json")))
    footer = (f"Shared {datetime.date.today().isoformat()} from <a href=\"https://github.com/retronym/jvm-perf-lab\">perflab</a>: "
              f"campaign <code>{index.esc(name)}</code>, testbed <code>{index.esc(testbed.of_campaign(camp))}</code>"
              + (f", with {', '.join(depth)}" if depth else ", results only") + ".")
    index.build(os.path.join(dest, "campaigns"), os.path.join(dest, "runs"), out=os.path.join(dest, "index.html"),
                title=s.get("name") or name, footer=footer, live=False)
    with open(os.path.join(dest, "campaigns", "index.html"), "w") as f:
        f.write(site.REDIRECT)
    sizes = [os.path.getsize(os.path.join(p, f)) for p, _, fs in os.walk(dest) for f in fs]
    return {"campaigns": camps, "files": len(sizes), "bytes": sum(sizes)}


def settings():
    try:
        with open(os.path.expanduser(os.environ.get("PERFLAB_SHARE_SETTINGS") or SETTINGS), "rb") as f:
            st = tomllib.load(f)
    except FileNotFoundError:
        st = {}
    cmd = os.path.expanduser(st.get("command") or shutil.which("share") or "")
    env = {**os.environ, **{k: os.path.expanduser(str(v)) for k, v in (st.get("env") or {}).items()}}
    if st.get("url"):
        env["SHARE_URL"] = st["url"]
    if not cmd or not os.access(cmd, os.X_OK) or not env.get("SHARE_URL"):
        raise SystemExit(f"perflab share: no `share` command and site: set command and url in {SETTINGS} (see `perflab share --help`)")
    return cmd, env


def slug_for(name):
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:52] or "campaign"
    return f"{base}-{secrets.token_hex(3)}"


def main(argv):
    ap = argparse.ArgumentParser(prog="perflab share", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("campaign")
    for d in DEPTHS:
        ap.add_argument(f"--{d}", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="build the site and say what it holds; publish nothing")
    ap.add_argument("--out", help="with --dry-run: keep the site in this directory, to look at")
    ap.add_argument("--rm", action="store_true", help="take the campaign's site down")
    ap.add_argument("--json", action="store_true", help="the outcome as JSON (for the index's Share button)")
    x = ap.parse_args(argv)
    name = x.campaign.rstrip("/").split("/")[-1]
    camp = os.path.join(config.get().campaigns, name)
    rec_f = os.path.join(camp, RECORD)
    rec = None
    try:
        rec = json.load(open(rec_f))
    except (OSError, ValueError):
        pass
    say = (lambda o: print(json.dumps(o))) if x.json else None
    if x.rm:
        if not rec:
            raise SystemExit(f"perflab share: {name} is not shared")
        cmd, env = settings()
        subprocess.run([cmd, "rm", rec["slug"]], env=env, check=True, stdout=sys.stderr)
        os.unlink(rec_f)
        say({"removed": rec["url"]}) if say else print(f"took down {rec['url']}")
        return 0
    depth = [d for d in DEPTHS if getattr(x, d)]
    with tempfile.TemporaryDirectory(prefix="perflab-share-") as dest:
        r = build(name, depth, dest)
        out = {**r, "depth": depth, "url": rec and rec.get("url"), "slug": rec and rec.get("slug")}
        if x.dry_run:
            if x.out:
                shutil.rmtree(x.out, ignore_errors=True)
                shutil.copytree(dest, x.out)
            if say:
                say(out)
            else:
                print(f"{name}: {r['files']} files, {r['bytes'] / 1e6:.1f} MB ({', '.join(r['campaigns'])}; "
                      f"{'with ' + ', '.join(depth) if depth else 'results only'})"
                      + (f"; it would replace {rec['url']}" if rec else ""))
            return 0
        cmd, env = settings()
        slug = (rec or {}).get("slug") or slug_for(name)
        p = subprocess.run([cmd, "-s", slug, "-d", dest], env=env, capture_output=True, text=True)
        sys.stderr.write(p.stderr)  # wrangler's progress, and why it failed
        if p.returncode:
            why = [l.strip() for l in p.stderr.splitlines() if re.search(r"error|fail|share:|denied|not ", l, re.I)][-3:]
            raise SystemExit(f"perflab share: `share` failed (exit {p.returncode})" + (": " + " / ".join(why) if why else ""))
        url = p.stdout.strip().splitlines()[-1]
    rec = {"url": url, "slug": slug, "depth": depth, "at": datetime.datetime.now().isoformat(timespec="seconds"),
           "files": r["files"], "bytes": r["bytes"]}
    with open(rec_f, "w") as f:
        json.dump(rec, f, indent=2)
        f.write("\n")
    say({**out, **rec}) if say else print(url)
    return 0
