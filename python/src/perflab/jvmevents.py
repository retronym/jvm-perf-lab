"""<cell>/jvm-events.tsv: the JDK's own events in an async run's .jfr (`[async] jfrsync`, perflab.jfc) that the timeline
draws: VM operations at a safepoint, JIT compilations and deoptimizations. The page cannot read JFR, so they are written
out once, after the run.

  kind      vmop, c1, c2 (a compilation by tier) or deopt
  start_ms  wall clock, ms since the epoch
  end_ms    the same as start_ms for an instant (deopt)
  what      the operation, or the method and its tier, OSR, failure; the deopt's reason and action

JMH's async-profiler restarts at the first measured iteration and each fork writes the same file, so the events cover the
measured window of the last fork. Read with the fork's own `jfr` (the JMH log's VM invoker), which reads its JDK's files.
timeline.write extracts them when the .jfr is newer than the .tsv.
"""
import datetime, glob, json, os, re, shutil, subprocess, sys

EVENTS = ["jdk.ExecuteVMOperation", "jdk.Compilation", "jdk.Deoptimization"]
HEADER = ["kind", "start_ms", "end_ms", "what"]


def jfr_tool(d):
    """The `jfr` of the JDK that ran the forks, else $JAVA_HOME's, else the PATH's."""
    try:
        m = re.search(r"^# VM invoker: (.+)$", open(os.path.join(d, "jmh.log")).read(), re.M)
    except OSError:
        m = None
    for c in [m and os.path.join(os.path.dirname(m.group(1).strip()), "jfr"),
              os.environ.get("JAVA_HOME") and os.path.join(os.environ["JAVA_HOME"], "bin", "jfr")]:
        if c and os.path.exists(c):
            return c
    return shutil.which("jfr")


def epoch_ms(iso):
    """`2026-10-20T19:25:17.210995208+10:00` -> ms since the epoch (fromisoformat takes at most microseconds)."""
    iso = re.sub(r"(\.\d{6})\d+", r"\1", iso)
    return datetime.datetime.fromisoformat(iso).timestamp() * 1000


def duration_ms(iso):
    """`PT0.000079709S` (or with H, M) -> ms."""
    m = re.fullmatch(r"PT(?:([\d.]+)H)?(?:([\d.]+)M)?(?:([\d.]+)S)?", iso or "")
    if not m:
        return 0.0
    h, mi, s = (float(x) if x else 0.0 for x in m.groups())
    return (h * 3600 + mi * 60 + s) * 1000


def method(m):
    if not m:
        return "?"
    cls = (m.get("type") or {}).get("name", "?").replace("/", ".")
    return f"{cls}.{m.get('name', '?')}"


def row(e):
    t, v = e["type"], e["values"]
    s = epoch_ms(v["startTime"])
    end = s + duration_ms(v.get("duration"))
    if t == "jdk.ExecuteVMOperation":
        if not v.get("safepoint"):
            return None
        return ["vmop", s, end, v.get("operation") or "?"]
    if t == "jdk.Compilation":
        level = v.get("compileLevel")
        kind = "c2" if level == 4 or v.get("compiler") in ("c2", "jvmci") else "c1"
        what = f"{method(v.get('method'))} (tier {level}{', OSR' if v.get('isOsr') else ''}"
        what += f", {v.get('codeSize', 0)} B)" if v.get("succeded", True) else ", failed)"
        return [kind, s, end, what]
    if t == "jdk.Deoptimization":
        return ["deopt", s, s, f"{method(v.get('method'))}: {v.get('reason', '?')}, {v.get('action', '?')}"
                               f" ({v.get('compiler', '?')}, line {v.get('lineNumber', '?')})"]
    return None


def extract(d, jfr=None):
    """Writes <d>/jvm-events.tsv from the cell's .jfr; returns its path, or None without a .jfr or a `jfr` tool."""
    files = sorted(glob.glob(os.path.join(d, "**", "*.jfr"), recursive=True))
    tool = jfr or jfr_tool(d)
    if not files or not tool:
        return None
    rows = []
    for f in files:
        p = subprocess.run([tool, "print", "--json", "--events", ",".join(EVENTS), f], capture_output=True, text=True)
        if p.returncode != 0:
            print(f"jvm-events: {f}: {p.stderr.strip()}", file=sys.stderr)
            continue
        rows += [r for r in map(row, json.loads(p.stdout)["recording"]["events"]) if r]
    rows.sort(key=lambda r: r[1])
    out = os.path.join(d, "jvm-events.tsv")
    clean = lambda x: x.replace("\t", " ").replace("\n", " ") if isinstance(x, str) else f"{x:.3f}"
    with open(out, "w") as fh:
        fh.write("\t".join(HEADER) + "\n")
        for r in rows:
            fh.write("\t".join(map(clean, r)) + "\n")
    return out


def refresh(d):
    """extract, unless jvm-events.tsv is newer than every .jfr of the cell."""
    files = glob.glob(os.path.join(d, "**", "*.jfr"), recursive=True)
    out = os.path.join(d, "jvm-events.tsv")
    if files and (not os.path.exists(out) or os.path.getmtime(out) < max(map(os.path.getmtime, files))):
        extract(d)
