"""What the OS can tell about a benchmark fork from outside it, cheaply, every half second while a cell runs (macOS,
no root, no change to the fork): for a post-mortem of a fork that came out slow or fast.

  perflab osprobe sample <root-pid> <out.jsonl> [secs=0.5]   appends one JSON line per sample until killed
  perflab osprobe summary <cell>                             the cell's os.json, printed
  perflab osprobe now [pid]                                  one sample, printed (this machine's core classes too)

Each sample has, for the JMH fork (the descendant of <root-pid> running JMH's ForkedMain), cumulative since it started:
  ru   proc_pid_rusage(RUSAGE_INFO_V6): CPU time, instructions and cycles, and how much of each was on the top core
       tier (`p*`: the Super cores of an M5 Pro, the P cores of an M4); time runnable but waiting for a core; energy;
       time waiting on page faults. Times are in ns.
  th   CPU time (ns) of the fork's threads by group: bench (JMH workers), jit, gc, other; and thread counts
and for the machine, cumulative CPU ticks of each core class (busy, total): whether the top tier was full.

`per_iteration` turns the samples into per-iteration figures by interpolating the cumulative values at each iteration's
start and end; `summary` adds them up over the measured iterations into the cell's os.json, which `metrics.of` shows
as `os:` metrics. The core class each thread ran on is not here (a thread can only ask for its own CPU); xctrace
profiles have it per thread.
"""
import ctypes, ctypes.util, json, os, re, subprocess, sys, time

OS_JSONL = "os.jsonl"
OS_JSON = "os.json"

RU_FIELDS = ("user_time system_time pkg_idle_wkups interrupt_wkups pageins wired_size resident_size phys_footprint "
             "proc_start_abstime proc_exit_abstime child_user_time child_system_time child_pkg_idle_wkups "
             "child_interrupt_wkups child_pageins child_elapsed_abstime diskio_bytesread diskio_byteswritten "
             "cpu_time_qos_default cpu_time_qos_maintenance cpu_time_qos_background cpu_time_qos_utility "
             "cpu_time_qos_legacy cpu_time_qos_user_initiated cpu_time_qos_user_interactive billed_system_time "
             "serviced_system_time logical_writes lifetime_max_phys_footprint instructions cycles billed_energy "
             "serviced_energy interval_max_phys_footprint runnable_time flags user_ptime system_ptime pinstructions "
             "pcycles energy_nj penergy_nj secure_time_in_system secure_ptime_in_system neural_footprint "
             "lifetime_max_neural_footprint interval_max_neural_footprint conclave_footprint page_wait_time_mach "
             "page_cache_hits").split()
# mach absolute time units, converted to ns
RU_MACH = {"user_time", "system_time", "runnable_time", "user_ptime", "system_ptime", "page_wait_time_mach"}
RU_KEEP = ("user_time", "system_time", "user_ptime", "system_ptime", "instructions", "cycles", "pinstructions", "pcycles",
           "runnable_time", "energy_nj", "penergy_nj", "page_wait_time_mach", "phys_footprint")


class RusageV6(ctypes.Structure):
    _fields_ = [("uuid", ctypes.c_uint8 * 16)] + [(f, ctypes.c_uint64) for f in RU_FIELDS] + [("reserved", ctypes.c_uint64 * 6)]


class ThreadInfo(ctypes.Structure):
    _fields_ = [("user_time", ctypes.c_uint64), ("system_time", ctypes.c_uint64), ("cpu_usage", ctypes.c_int32),
                ("policy", ctypes.c_int32), ("run_state", ctypes.c_int32), ("flags", ctypes.c_int32),
                ("sleep_time", ctypes.c_int32), ("curpri", ctypes.c_int32), ("priority", ctypes.c_int32),
                ("maxpriority", ctypes.c_int32), ("name", ctypes.c_char * 64)]


class _Timebase(ctypes.Structure):
    _fields_ = [("numer", ctypes.c_uint32), ("denom", ctypes.c_uint32)]


_lib = None


def lib():
    global _lib
    if _lib is None:
        _lib = ctypes.CDLL(ctypes.util.find_library("System") or "/usr/lib/libSystem.B.dylib", use_errno=True)
        tb = _Timebase()
        _lib.mach_timebase_info(ctypes.byref(tb))
        _lib.ns_per_tick = tb.numer / tb.denom
    return _lib


def rusage(pid):
    """The process's cumulative counters (RU_KEEP; times in ns), or None if it is gone or not ours."""
    L = lib()
    r = RusageV6()
    if L.proc_pid_rusage(ctypes.c_int(pid), ctypes.c_int(6), ctypes.byref(r)) != 0:
        return None
    return {k: (getattr(r, k) * L.ns_per_tick if k in RU_MACH else getattr(r, k)) for k in RU_KEEP}


def group(name):
    """A JVM thread's group by its native name ("Java: ..."), as XctraceProfiler groups them."""
    if "jmh-worker" in name or "-jmh-" in name:
        return "bench"
    if "CompilerThread" in name:
        return "jit"
    if re.search(r"GC Thread|G1 |GC |Conc#|Marker|Refine|ZGC|Shenandoah", name):
        return "gc"
    return "other"


def threads(pid):
    """Each live thread's (group, CPU ns), by its handle: {handle: (group, ns)}."""
    L = lib()
    n = 512
    while True:
        buf = (ctypes.c_uint64 * n)()
        got = L.proc_pidinfo(ctypes.c_int(pid), ctypes.c_int(6), ctypes.c_uint64(0), buf, ctypes.c_int(ctypes.sizeof(buf)))
        if got <= 0:
            return {}
        k = got // 8
        if k < n:
            break
        n *= 2
    out = {}
    ti = ThreadInfo()
    for i in range(k):
        if L.proc_pidinfo(ctypes.c_int(pid), ctypes.c_int(5), ctypes.c_uint64(buf[i]), ctypes.byref(ti), ctypes.c_int(ctypes.sizeof(ti))) <= 0:
            continue
        out[buf[i]] = (group(ti.name.decode("utf-8", "replace")), ti.user_time + ti.system_time)
    return out


class ThreadTotals:
    """Cumulative CPU ns per thread group of one process, kept monotonic across threads that exit (HotSpot's
    compiler threads come and go): each live thread's growth since the last look is added to its group."""

    def __init__(self):
        self.pid, self.last, self.total, self.live = None, {}, {}, {}

    def update(self, pid):
        if pid != self.pid:
            self.pid, self.last, self.total = pid, {}, {}
        now = threads(pid)
        live = {}
        for h, (g, ns) in now.items():
            prev = self.last.get(h, (g, 0))[1]
            self.total[g] = self.total.get(g, 0) + max(0, ns - prev)
            live[g] = live.get(g, 0) + 1
        self.last = now
        return {g: [self.total.get(g, 0), live.get(g, 0)] for g in set(self.total) | set(live)}


def _sysctl(name):
    try:
        return subprocess.run(["sysctl", "-n", name], capture_output=True, text=True, timeout=2).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


_classes = None


def core_classes():
    """[(name, first cpu, count)] from fastest to slowest: hw.perflevel0 is the top tier. CPUs are numbered from the
    slowest tier up (an M5 Pro's 12 Performance cores are 0-11 and its 6 Super cores 12-17; an M4's E cores come before
    its P cores), as xctrace's core labels show."""
    global _classes
    if _classes is None:
        levels = []
        for i in range(int(_sysctl("hw.nperflevels") or 0)):
            levels.append((_sysctl(f"hw.perflevel{i}.name") or f"level{i}", int(_sysctl(f"hw.perflevel{i}.logicalcpu") or 0)))
        first, out = 0, []
        for name, count in reversed(levels):
            out.append((name, first, count))
            first += count
        _classes = list(reversed(out))
    return _classes


def cpu_ticks():
    """Cumulative CPU ticks per core class: {name: [busy, total]} (host_processor_info, no root)."""
    L = lib()
    count = ctypes.c_uint32()
    info = ctypes.POINTER(ctypes.c_uint32)()
    n_info = ctypes.c_uint32()
    host = L.mach_host_self()
    if L.host_processor_info(host, 2, ctypes.byref(count), ctypes.byref(info), ctypes.byref(n_info)) != 0:
        return {}
    try:
        per_cpu = [[info[c * 4 + s] for s in range(4)] for c in range(count.value)]
    finally:
        task = ctypes.c_uint32.in_dll(L, "mach_task_self_")
        L.vm_deallocate(task, ctypes.cast(info, ctypes.c_void_p), ctypes.c_size_t(n_info.value * 4))
    out = {}
    for name, first, n in core_classes():
        busy = total = 0
        for t in per_cpu[first:first + n]:
            busy += t[0] + t[1] + t[3]
            total += sum(t)
        out[name] = [busy, total]
    return out


def fork_pid(root):
    """The JMH fork under `root`: the newest process whose command line runs JMH's ForkedMain, or None."""
    try:
        out = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,args="], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    procs = {}
    for line in out.splitlines():
        p = line.split(None, 2)
        if len(p) == 3 and p[0].isdigit() and p[1].isdigit():
            procs[int(p[0])] = (int(p[1]), p[2])
    keep, changed = {root}, True
    while changed:
        changed = False
        for pid, (ppid, _) in procs.items():
            if pid not in keep and ppid in keep:
                keep.add(pid)
                changed = True
    forks = [pid for pid in keep if "org.openjdk.jmh.runner.ForkedMain" in procs.get(pid, (0, ""))[1]]
    return max(forks) if forks else None


def sample(pid, totals=None):
    """One sample of `pid` (None: the machine only); `totals` carries thread groups' CPU across samples."""
    s = {"t": round(time.time(), 3), "cl": cpu_ticks()}
    if pid:
        ru = rusage(pid)
        if ru:
            s.update(pid=pid, ru=ru, th=(totals or ThreadTotals()).update(pid))
    return s


def run_sampler(root, path, secs=0.5):
    pid, last_look, totals = None, 0.0, ThreadTotals()
    with open(path, "a") as f:
        while True:
            now = time.time()
            if (pid is None or rusage(pid) is None) and now - last_look > 1.0:
                pid, last_look = fork_pid(root), now
            f.write(json.dumps(sample(pid, totals), separators=(",", ":")) + "\n")
            f.flush()
            time.sleep(max(0.0, secs - (time.time() - now)))


def load(path):
    out = []
    try:
        for line in open(path):
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    except FileNotFoundError:
        pass
    return out


def _at(ss, t, get):
    """(A cumulative value at time t, linearly between the samples around it; the fork's pid), or None outside the
    samples or across a fork change."""
    lo = hi = None
    for s in ss:
        if s["t"] <= t:
            lo = s
        elif hi is None:
            hi = s
            break
    if lo is None or hi is None or lo.get("pid") != hi.get("pid"):
        return None
    a, b = get(lo), get(hi)
    if a is None or b is None:
        return None
    w = (t - lo["t"]) / (hi["t"] - lo["t"]) if hi["t"] > lo["t"] else 0.0
    return a + (b - a) * w, lo.get("pid")


def _delta(ss, a, b, get):
    """The change of a cumulative value from a to b, None unless both ends are in the samples of one fork."""
    x, y = _at(ss, a, get), _at(ss, b, get)
    return None if x is None or y is None or x[1] != y[1] else y[0] - x[0]


def iterations(iterations_tsv):
    try:
        rows = open(iterations_tsv).read().splitlines()
    except FileNotFoundError:
        return []
    head = rows[0].split("\t") if rows else []
    out = []
    for r in rows[1:]:
        x = dict(zip(head, r.split("\t")))
        try:
            out.append({"index": int(x.get("index") or 0), "kind": x.get("kind", ""), "start": float(x["start_ms"]) / 1000,
                        "end": float(x["end_ms"]) / 1000, "ops": int(x["ops"]) if x.get("ops") else None})
        except (KeyError, ValueError):
            continue
    return out


def per_iteration(os_jsonl, iterations_tsv):
    """Each iteration's deltas: {"index", "kind", "wall", "ops", "ru": {field: delta}, "th": {group: cpu ns},
    "cl": {class: busy fraction}}; only those the samples cover."""
    ss = load(os_jsonl)
    forked = [s for s in ss if "ru" in s]
    out = []
    for it in iterations(iterations_tsv):
        a, b = it["start"], it["end"]
        ru = {k: _delta(forked, a, b, lambda s, k=k: s["ru"].get(k)) for k in RU_KEEP if k != "phys_footprint"}
        if ru["user_time"] is None:
            continue
        groups = sorted({g for s in forked for g in s.get("th", {})})
        th = {g: _delta(forked, a, b, lambda s, g=g: s.get("th", {}).get(g, [0, 0])[0]) for g in groups}
        cl = {}
        for name in sorted({c for s in ss for c in s.get("cl", {})}):
            busy = _delta(ss, a, b, lambda s: s["cl"].get(name, [None])[0])
            tot = _delta(ss, a, b, lambda s: s["cl"].get(name, [None, None])[1])
            if busy is not None and tot:
                cl[name] = busy / tot
        out.append({"index": it["index"], "kind": it["kind"], "wall": b - a, "ops": it["ops"], "ru": ru, "th": th, "cl": cl})
    return out


def summary(cell):
    """The measured iterations' figures, summed: written to <cell>/os.json and returned ({} without samples)."""
    its = per_iteration(os.path.join(cell, OS_JSONL), os.path.join(cell, "iterations.tsv"))
    meas = [i for i in its if i["kind"] in ("measure", "measurement")]
    if not meas:
        return {}
    tot = lambda k: sum(i["ru"][k] or 0 for i in meas)
    ops = sum(i["ops"] or 0 for i in meas) or None
    wall = sum(i["wall"] for i in meas)
    cpu = tot("user_time") + tot("system_time")
    pcpu = tot("user_ptime") + tot("system_ptime")
    groups = sorted({g for i in meas for g in i["th"]})
    out = {
        "iterations": len(meas), "ops": ops, "wall_s": wall,
        "cpu_s": cpu / 1e9,
        "instructions": tot("instructions"), "cycles": tot("cycles"),
        "top_tier_time_pct": 100 * pcpu / cpu if cpu else None,
        "top_tier_cycles_pct": 100 * tot("pcycles") / tot("cycles") if tot("cycles") else None,
        "ghz": tot("cycles") / cpu if cpu else None,
        # the kernel's runnable time includes time on core: the wait is what is left
        "runnable_pct": 100 * max(0.0, tot("runnable_time") - cpu) / cpu if cpu else None,
        "energy_j": tot("energy_nj") / 1e9,
        "page_wait_ms": tot("page_wait_time_mach") / 1e6,
        "threads_cores": {g: sum(i["th"].get(g) or 0 for i in meas) / 1e9 / wall for g in groups} if wall else {},
        "class_busy_pct": {c: 100 * sum(i["cl"].get(c, 0) * i["wall"] for i in meas) / wall for c in sorted({c for i in meas for c in i["cl"]})} if wall else {},
        "per_iteration": [{"index": i["index"], "ipc": i["ru"]["instructions"] / i["ru"]["cycles"] if i["ru"]["cycles"] else None,
                           "top_tier_time_pct": 100 * (i["ru"]["user_ptime"] + i["ru"]["system_ptime"]) / (i["ru"]["user_time"] + i["ru"]["system_time"])
                           if i["ru"]["user_time"] + i["ru"]["system_time"] else None,
                           "runnable_pct": 100 * max(0.0, i["ru"]["runnable_time"] - i["ru"]["user_time"] - i["ru"]["system_time"]) / (i["ru"]["user_time"] + i["ru"]["system_time"])
                           if i["ru"]["user_time"] + i["ru"]["system_time"] else None,
                           "class_busy_pct": {c: 100 * v for c, v in i["cl"].items()}} for i in meas],
    }
    if ops:
        out["per_op"] = {"instructions": out["instructions"] / ops, "cycles": out["cycles"] / ops, "energy_j": out["energy_j"] / ops,
                         "cpu_s": out["cpu_s"] / ops}
    with open(os.path.join(cell, OS_JSON), "w") as f:
        json.dump(out, f, indent=1)
    return out


def main(argv):
    cmd = argv[0] if argv else ""
    if cmd == "sample":
        run_sampler(int(argv[1]), argv[2], float(argv[3]) if len(argv) > 3 else 0.5)
    elif cmd == "summary":
        print(json.dumps(summary(argv[1]), indent=1))
    elif cmd == "now":
        print(json.dumps({"classes": core_classes(), **sample(int(argv[1]) if len(argv) > 1 else os.getpid())}, indent=1))
    else:
        sys.exit(__doc__)
    return 0
