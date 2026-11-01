"""Competing load on the machine: CPU used by processes other than the benchmark's own (a given root process and
its descendants: the sbt server, JMH's launcher and forks, xctrace), measured as the change in cumulative CPU time.

  perflab loadgate wait   <root-pid> [max-cores=1.5] [quiet-secs=60]   blocks until other load stays under max-cores
  perflab loadgate sample <root-pid> <out.tsv> [secs=5]                 appends "epoch<TAB>cores<TAB>top<TAB>secs<TAB>state" every secs
                                                                       until killed: the load over the secs before epoch, and the
                                                                       machine's state then (`machine`)
  perflab loadgate mean   <out.tsv> [since-epoch]                       mean other-load in cores over the samples
  perflab loadgate machine                                              the machine's state now, one line

Besides other processes' CPU, each sample records what the OS says about the machine (macOS, no root needed): its
thermal state (NSProcessInfo.thermalState: nominal, fair, serious, critical; from serious the CPU is throttled), whether
it runs on battery, Low Power Mode, and free memory. A wait holds while the thermal state is serious or critical, and a
measurement iteration under one counts as disturbed, as one under too much other load does.
"""
import json, os, subprocess, sys, time

from . import transcript

# macOS daemons that run at background QoS, which Apple Silicon confines to the efficiency cores: reported, but not
# counted against the limit, since the benchmark runs on the performance cores.
BACKGROUND = {"mediaanalysisd", "photoanalysisd", "spotlightknowledged", "spotlightknowledged.updater", "mds", "mds_stores", "mdworker",
              "mdworker_shared", "mdbulkimport", "backupd", "backupd-helper", "corespotlightd", "suggestd",
              "knowledge-agent", "duetexpertd", "triald", "softwareupdated", "fseventsd"}

def cputimes():
    out = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,time=,comm="], capture_output=True, text=True).stdout
    procs = {}
    for line in out.splitlines():
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        pid, ppid, t, comm = int(parts[0]), int(parts[1]), parts[2], parts[3]
        secs = 0.0
        d, _, hms = t.rpartition("-")
        for x in hms.split(":"):
            secs = secs * 60 + float(x)
        if d:
            secs += int(d) * 86400
        procs[pid] = (ppid, secs, comm.rsplit("/", 1)[-1])
    return procs

def ours(procs, root):
    # the parent is launchd (pid 1) once a detaching shell has exited: everything would count as ours
    keep = {root, *(p for p in (subprocess.os.getpid(), subprocess.os.getppid()) if p > 1)}
    changed = True
    while changed:
        changed = False
        for pid, (ppid, _, comm) in procs.items():
            if pid not in keep and (ppid in keep or comm == "xctrace"):
                keep.add(pid)
                changed = True
    return keep

def other_load(root, interval=5.0):
    a = cputimes()
    time.sleep(interval)
    b = cputimes()
    mine = ours(b, root)
    per = {}
    for pid, (_, secs, comm) in b.items():
        if pid in mine or pid not in a:
            continue
        d = secs - a[pid][1]
        if d > 0:
            per[comm] = per.get(comm, 0) + d / interval
    total = sum(v for c, v in per.items() if c not in BACKGROUND)
    bg = sum(v for c, v in per.items() if c in BACKGROUND)
    fg = [(c, v) for c, v in sorted(per.items(), key=lambda kv: -kv[1]) if c not in BACKGROUND]
    top = ", ".join(f"{c} {v:.1f}" for c, v in fg[:3])
    if bg >= 0.1:
        top += f"; background daemons {bg:.1f}"
    return total, top

THERMAL = ("nominal", "fair", "serious", "critical")  # NSProcessInfo.thermalState, from 0
HOT = {"serious", "critical"}  # thermal states under which macOS throttles the CPU: a measurement under one is disturbed


def _run(cmd, timeout=5):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def machine():
    """What the OS reports about the machine that bears on a measurement, without root: {"thermal": nominal | fair |
    serious | critical, "power": ac | battery, "lowpower": bool, "memfree": % of memory free}, each key only where it
    could be read (macOS; the thermal state through the ObjC bridge of osascript, 40 ms)."""
    m = {}
    if sys.platform != "darwin":
        return m
    t = _run(["osascript", "-l", "JavaScript", "-e", 'ObjC.import("Foundation"); $.NSProcessInfo.processInfo.thermalState']).strip()
    if t.isdigit() and int(t) < len(THERMAL):
        m["thermal"] = THERMAL[int(t)]
    batt = _run(["pmset", "-g", "batt"])
    if "AC Power" in batt:
        m["power"] = "ac"
    elif "Battery Power" in batt:
        m["power"] = "battery"
    for line in _run(["pmset", "-g"]).splitlines():
        p = line.split()
        if p[:1] == ["lowpowermode"] and len(p) > 1 and p[1].isdigit():
            m["lowpower"] = p[1] != "0"
    mem = _run(["sysctl", "-n", "kern.memorystatus_level"]).strip()
    if mem.isdigit():
        m["memfree"] = int(mem)
    return m


def state_str(m):
    """`machine()` as the sample column: `thermal=fair power=battery lowpower mem=23%`, tokens for what is known."""
    out = []
    if "thermal" in m:
        out.append(f"thermal={m['thermal']}")
    if "power" in m:
        out.append(f"power={m['power']}")
    if m.get("lowpower"):
        out.append("lowpower")
    if "memfree" in m:
        out.append(f"mem={m['memfree']}%")
    return " ".join(out)


def parse_state(s):
    """`state_str` back to a dict (the sample column; "" or an old file's missing column gives {})."""
    m = {}
    for tok in (s or "").split():
        k, _, v = tok.partition("=")
        if k == "thermal" and v in THERMAL:
            m["thermal"] = v
        elif k == "power" and v in ("ac", "battery"):
            m["power"] = v
        elif k == "lowpower":
            m["lowpower"] = True
        elif k == "mem" and v.rstrip("%").isdigit():
            m["memfree"] = int(v.rstrip("%"))
    return m


def describe(m, load=None, top=""):
    """One line for people: `other load 0.3 cores (WindowServer 0.2); thermal nominal, AC power, 81% memory free`."""
    parts = []
    if load is not None:
        parts.append(f"other load {load:.2f} cores" + (f" ({top})" if top else ""))
    words = []
    if "thermal" in m:
        words.append(f"thermal {m['thermal']}")
    if "power" in m:
        words.append("AC power" if m["power"] == "ac" else "on battery")
    if m.get("lowpower"):
        words.append("Low Power Mode")
    if "memfree" in m:
        words.append(f"{m['memfree']}% memory free")
    if words:
        parts.append(", ".join(words))
    return "; ".join(parts)


def hot(m):
    return m.get("thermal") in HOT


def samples(path):
    """A sample file's [(start, end, cores, top, state)], in epoch seconds, `state` as `machine()` gives it ({} for a
    sample from before it was recorded); samples without a window are of 5 s."""
    out = []
    try:
        lines = open(path).read().splitlines()
    except FileNotFoundError:
        return out
    for l in lines:
        p = l.split("\t")
        try:
            end, cores = float(p[0]), float(p[1])
            secs = float(p[3]) if len(p) > 3 and p[3] else 5.0
        except (IndexError, ValueError):
            continue
        out.append((end - secs, end, cores, p[2] if len(p) > 2 else "", parse_state(p[4] if len(p) > 4 else "")))
    return out


def per_iteration(load_tsv, iterations_tsv):
    """Each measurement iteration's competing load: [{"index", "start", "end", "score", "cores" (the highest of the
    samples overlapping it, None without any), "top", "thermal" (the worst over it, None where unknown), "lowpower"
    (whether any sample over it had Low Power Mode on)}], from a cell's load.tsv and iterations.tsv."""
    ss = samples(load_tsv)
    out = []
    try:
        rows = open(iterations_tsv).read().splitlines()
    except FileNotFoundError:
        return out
    head = rows[0].split("\t") if rows else []
    for r in rows[1:]:
        x = dict(zip(head, r.split("\t")))
        if x.get("kind") not in ("measure", "measurement"):
            continue
        try:
            a, b = float(x["start_ms"]) / 1000, float(x["end_ms"]) / 1000
        except (KeyError, ValueError):
            continue
        over = [s for s in ss if s[0] < b and s[1] > a]
        top = max(over, key=lambda s: s[2]) if over else None
        therm = [s[4]["thermal"] for s in over if "thermal" in s[4]]
        out.append({"index": int(x.get("index") or 0), "start": a, "end": b, "score": float(x["score"]) if x.get("score") else None,
                    "cores": top[2] if top else None, "top": top[3] if top else "",
                    "thermal": max(therm, key=THERMAL.index) if therm else None, "lowpower": any(s[4].get("lowpower") for s in over)})
    return out


def disturbed(it, limit):
    """Whether a `per_iteration` record is of an iteration other load over `limit` cores, or a throttling thermal state,
    disturbed (`limit` None: load never counts)."""
    return (limit is not None and it.get("cores") is not None and it["cores"] > limit) or it.get("thermal") in HOT


def disturbance(it):
    """Why a disturbed iteration is: `1.7 cores: java 0.9`, `thermal serious`, or both."""
    parts = []
    if it.get("thermal") in HOT:
        parts.append(f"thermal {it['thermal']}")
    if it.get("cores") is not None:
        parts.append(f"{it['cores']:.1f} cores" + (f": {it['top']}" if it.get("top") else ""))
    return "; ".join(parts)


STATE_NAME = "loadgate.json"
# where the wait is published: <campaigns> of this checkout, or of the one `perflab trees` runs from
LIVE_ENV = "PERFLAB_LIVE_DIR"


def state_path(name=STATE_NAME):
    from . import config
    return os.path.join(os.environ.get(LIVE_ENV) or config.get().campaigns, name)


def publish(state, name=STATE_NAME):
    """<campaigns>/<name> (loadgate.json while a wait lasts) for the index to draw; removed when `state` is None."""
    path = state_path(name)
    try:
        if state is None:
            os.unlink(path)
        else:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path + ".tmp", "w") as f:
                json.dump(state, f)
            os.replace(path + ".tmp", path)
    except OSError:
        pass


def wait(root, limit=1.5, quiet=60):
    """Blocks until other processes' load stays under `limit` cores for `quiet` seconds. While it waits, the samples
    are published for the index (`publish`) and each is a line of the transcript."""
    since = None
    state = {"pid": os.getpid(), "started": time.time(), "limit": limit, "quiet": quiet, "quietSince": None, "samples": []}
    try:
        while True:
            load, top = other_load(root)
            m = machine()
            now = time.time()
            if load <= limit and not hot(m):
                since = since or now
                if now - since >= quiet:
                    transcript.say(f"idle: {describe(m, load, top)}")
                    return
                transcript.write(f"quiet: other load {load:.2f} cores for {now - since:.0f} of {quiet:.0f} s")
            else:
                since = None
                transcript.say("waiting: " + (f"thermal state {m['thermal']}, " if hot(m) else "") + f"other load {load:.1f} cores ({top})")
            state["samples"] = (state["samples"] + [[round(now), round(load, 2), top, state_str(m)]])[-720:]
            state["quietSince"] = since
            publish(state)
    finally:
        publish(None)


def server_pid():
    """The root of the process tree that runs this project's benchmarks ([build] server in perflab.toml): the sbt server
    of this checkout (the process holding the socket named in project/target/active.json), or perflab itself."""
    from . import config
    cfg = config.get()
    from . import launch
    if cfg.get("build", "server") == "sbt" and not launch.enabled():  # in launch mode, perflab starts JMH itself
        try:
            uri = json.load(open(os.path.join(cfg.root, "project", "target", "active.json")))["uri"]
        except (OSError, ValueError, KeyError):
            sys.exit("loadgate: no sbt server found for this checkout; start one with `sbt --client` first")
        out = subprocess.run(["lsof", "-t", uri.removeprefix("local://")], capture_output=True, text=True).stdout.split()
        if not out:
            sys.exit("loadgate: the sbt server of this checkout is not running")
        return int(out[0])
    return os.getpid()


def main(argv):
    cmd = argv[0] if argv else ""
    if cmd == "wait":
        wait(int(argv[1]), float(argv[2]) if len(argv) > 2 else 1.5, float(argv[3]) if len(argv) > 3 else 60)
    elif cmd == "sample":
        root, path = int(argv[1]), argv[2]
        secs = float(argv[3]) if len(argv) > 3 else 5.0
        while True:
            load, top = other_load(root, secs)
            with open(path, "a") as f:
                f.write(f"{time.time():.1f}\t{load:.2f}\t{top}\t{secs:g}\t{state_str(machine())}\n")
    elif cmd == "machine":
        print(describe(machine()))
    elif cmd == "mean":
        path = argv[1]
        since = float(argv[2]) if len(argv) > 2 else 0
        try:
            xs = [float(l.split("\t")[1]) for l in open(path) if l.strip() and float(l.split("\t")[0]) >= since]
        except FileNotFoundError:   # the run ended before the first sample
            xs = [0.0]
        print(f"{sum(xs) / len(xs):.2f}" if xs else "nan")
    else:
        sys.exit(__doc__)
    return 0
