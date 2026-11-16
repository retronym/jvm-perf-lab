"""<cell>/jvm-events.tsv: the JDK's own events that the timeline draws: VM operations at a safepoint, JIT compilations
and deoptimizations. From an async run's .jfr (`[async] jfrsync`, perflab.jfc) when it has one; else from what every cell
records (doc/observability.md): the safepoint log and JitProfiler's jit-events-<pid>.tsv, which cover every fork from
start to exit. The page reads neither JFR nor several files per fork, so they are written out once, after the run.

  kind      vmop, c1, c2 (a compilation by tier) or deopt
  start_ms  wall clock, ms since the epoch
  end_ms    the same as start_ms for an instant (deopt)
  what      the operation, or the method and its tier, OSR, failure; the deopt's reason and action

From a .jfr: JMH's async-profiler restarts at the first measured iteration and each fork writes the same file, so the events cover the
measured window of the last fork. Read with the fork's own `jfr` (the JMH log's VM invoker), which reads its JDK's files.
timeline.write extracts them when a source is newer than the .tsv.
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
    return write(d, rows)


def write(d, rows):
    rows.sort(key=lambda r: r[1])
    out = os.path.join(d, "jvm-events.tsv")
    clean = lambda x: x.replace("\t", " ").replace("\n", " ") if isinstance(x, str) else f"{x:.3f}"
    with open(out, "w") as fh:
        fh.write("\t".join(HEADER) + "\n")
        for r in rows:
            fh.write("\t".join(map(clean, r)) + "\n")
    return out


# -Xlog:safepoint, decorated with `time,uptime` (or, before those, `uptime` alone): logged as the safepoint ends
SAFEPOINT = re.compile(r'^(?:\[([^\]]+)\])?\[([\d.]+)s\] Safepoint "([^"]+)".*?Reaching safepoint: (\d+) ns, '
                       r'At safepoint: (\d+) ns.*?Total: (\d+) ns')
GC_STAMP = re.compile(r'^\[(\d{4}-[^\]]+)\]\[([\d.]+)s\]')


def wall(stamp):
    """`2026-11-15T20:00:01.234+1000` (the JVM's `time` decoration) -> ms since the epoch."""
    return epoch_ms(re.sub(r"([+-]\d\d)(\d\d)$", r"\1:\2", stamp))


def safepoint_logs(d):
    """[(safepoint log, its fork's GC log or None)]: `perflab ab`'s safepoint.log and its rotations .0 .. .9 beside
    gc.log's, `perflab run`'s safepoint-<pid>.log beside gc-<pid>.log. A log with uptimes alone (the first cells to have
    one) is put on the wall clock by its GC log's `time,uptime` lines."""
    out = []
    for f in glob.glob(os.path.join(d, "safepoint.log")) + glob.glob(os.path.join(d, "safepoint.log.[0-9]*")) + glob.glob(os.path.join(d, "safepoint-*.log")):
        gc = os.path.join(d, os.path.basename(f).replace("safepoint", "gc", 1))
        out.append((f, gc if os.path.exists(gc) else None))
    return sorted(out)


def jvm_start(gc_log):
    """ms since the epoch at the fork's uptime 0, from its GC log's first line with both decorations."""
    try:
        for line in open(gc_log, errors="replace"):
            m = GC_STAMP.match(line)
            if m:
                return wall(m.group(1)) - float(m.group(2)) * 1000
    except (OSError, ValueError):
        pass
    return None


def safepoint_rows(path, gc_log=None):
    rows, start = [], None
    for line in open(path, errors="replace"):
        m = SAFEPOINT.match(line)
        if not m:
            continue
        stamp, up, op, reach, at, total = m.groups()
        if stamp:
            end = wall(stamp)
        else:
            if start is None:
                start = jvm_start(gc_log) if gc_log else None
                if start is None:
                    return []
            end = start + float(up) * 1000
        rows.append(["vmop", end - int(total) / 1e6, end, f"{op} (reaching {int(reach) / 1e3:.0f} µs, at {int(at) / 1e3:.0f} µs)"])
    return rows


def jit_rows(path):
    """JitProfiler's jit-events-<pid>.tsv: epoch_ms (the event's end), kind, tier, osr, compile_ms, method."""
    rows = []
    lines = open(path, errors="replace").read().splitlines()
    for line in lines[1:]:
        p = line.split("\t")
        if len(p) < 6:
            continue
        try:
            end, tier, ms = float(p[0]), int(p[2]), float(p[4])
        except ValueError:
            continue
        if p[1] == "deopt":
            rows.append(["deopt", end, end, p[5]])
        else:
            rows.append(["c2" if tier == 4 else "c1", end - ms, end, f"{p[5]} (tier {tier}{', OSR' if p[3] in ('1', 'true') else ''})"])
    return rows


def log_sources(d):
    return [f for f, _ in safepoint_logs(d)] + glob.glob(os.path.join(d, "jit-events-*.tsv"))


def from_logs(d):
    """Writes <d>/jvm-events.tsv from the safepoint logs and jit-events tsvs; returns its path, or None without either."""
    if not log_sources(d):
        return None
    rows = [r for f, gc in safepoint_logs(d) for r in safepoint_rows(f, gc)]
    rows += [r for f in glob.glob(os.path.join(d, "jit-events-*.tsv")) for r in jit_rows(f)]
    return write(d, rows)


def refresh(d):
    """extract (or from_logs, without a .jfr), unless jvm-events.tsv is newer than every source."""
    jfrs = glob.glob(os.path.join(d, "**", "*.jfr"), recursive=True)
    files = jfrs or log_sources(d)
    out = os.path.join(d, "jvm-events.tsv")
    if files and (not os.path.exists(out) or os.path.getmtime(out) < max(map(os.path.getmtime, files))):
        extract(d) if jfrs else from_logs(d)
