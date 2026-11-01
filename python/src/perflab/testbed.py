"""Testbeds (doc/remote-workers.md): the machine a cell ran on. Numbers from two machines are not comparable, so a
campaign has one testbed, its spec's "testbed" or else the testbed of the machine reading it, and counts only that
testbed's cells.

A testbed is a name and what identifies the machine: {"name", "model" (hw.model), "cpu", "cores", "memory" (bytes),
"os", "host"}. The name is PERFLAB_TESTBED, else the first line of ~/.perflab/testbed, else the CPU's (Apple M4 Pro
-> m4-pro). Every cell records its testbed in <cell>/testbed.json; a cell from before testbeds has none, and is its
campaign's.
"""
import functools, json, os, platform, re, socket, subprocess

ENV = "PERFLAB_TESTBED"
CELL_FILE = "testbed.json"


def _sysctl(name):
    try:
        return subprocess.run(["sysctl", "-n", name], capture_output=True, text=True, timeout=5).stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _cpu():
    if platform.system() == "Darwin":
        return _sysctl("machdep.cpu.brand_string")
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or None


def slug(cpu):
    """A testbed name from a CPU's name: "Apple M4 Pro" -> "m4-pro"."""
    s = re.sub(r"\((r|tm)\)|\bcpu\b|@.*$", "", (cpu or "unknown").lower())
    s = re.sub(r"^apple\s+", "", s.strip())
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "unknown"


def name():
    """This machine's testbed name."""
    if os.environ.get(ENV):
        return os.environ[ENV].strip()
    try:
        with open(os.path.expanduser("~/.perflab/testbed")) as f:
            n = f.readline().strip()
            if n:
                return n
    except OSError:
        pass
    return slug(_cpu())


@functools.lru_cache(maxsize=1)
def _machine():
    darwin = platform.system() == "Darwin"
    mem = _sysctl("hw.memsize") if darwin else None
    if not darwin:
        try:
            mem = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        except (ValueError, OSError):
            mem = None
    cores = {"logical": os.cpu_count()}
    if darwin:
        for level, kind in (("0", "performance"), ("1", "efficiency")):
            n = _sysctl(f"hw.perflevel{level}.physicalcpu")
            if n:
                cores[kind] = int(n)
    os_ = f"macOS {platform.mac_ver()[0]}" if darwin else f"{platform.system()} {platform.release()}"
    return {"model": _sysctl("hw.model") if darwin else platform.machine(), "cpu": _cpu(), "cores": cores,
            "memory": int(mem) if mem else None, "os": os_, "host": socket.gethostname().split(".")[0]}


def local():
    """This machine's testbed."""
    return {"name": name(), **_machine()}


def record(cell):
    """Records this machine's testbed in the cell."""
    os.makedirs(cell, exist_ok=True)
    with open(os.path.join(cell, CELL_FILE), "w") as f:
        json.dump(local(), f)
        f.write("\n")


def of_cell(cell):
    """The name of the testbed the cell ran on; None for a cell from before testbeds."""
    try:
        with open(os.path.join(cell, CELL_FILE)) as f:
            return json.load(f).get("name")
    except (OSError, ValueError, AttributeError):
        return None


def of_campaign(campaign):
    """The campaign's testbed: its spec's "testbed", else this machine's."""
    f = os.path.join(campaign, "spec.json")
    try:
        return _spec_testbed(f, os.stat(f).st_mtime_ns) or name()
    except OSError:
        return name()


@functools.lru_cache(maxsize=256)
def _spec_testbed(f, mtime):
    try:
        with open(f) as fh:
            t = json.load(fh).get("testbed")
        return t if isinstance(t, str) and t else None
    except (OSError, ValueError, AttributeError):
        return None


def campaign_of_cell(cell):
    """<campaign> of <campaign>/<corpus>/<variant>/<round>."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(cell))))


def foreign(cell):
    """The testbed the cell ran on when it is not its campaign's (the cell counts for nothing), else None."""
    t = of_cell(cell)
    if t is None:
        return None
    return t if t != of_campaign(campaign_of_cell(cell)) else None
