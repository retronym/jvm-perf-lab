"""A quiet machine for a measurement (macOS). `perflab quiet on` turns off what the OS runs in the background that
competes with a benchmark, quits the heavy applications that are running, keeps the machine awake, and records what it
changed; `perflab quiet off` puts it all back; `perflab quiet status` shows what is on, with the machine's state
(thermal, power, memory, its performance and efficiency cores) and a sample of other load.

  perflab quiet on  [--no-apps] [--no-spotlight]    Time Machine, Spotlight indexing, automatic software update checks
                                                    and Low Power Mode off; the applications in [quiet] apps quit; the
                                                    user's launchd agents in [quiet] agents (git maintenance) unloaded;
                                                    caffeinate for the duration
  perflab quiet off [--no-apps]                     restore what `on` recorded (apps relaunched unless --no-apps)
  perflab quiet status                              what is quiet, and a 5 s sample of the machine

Needs root for Time Machine, Spotlight, software update and Low Power Mode: it asks for sudo once (`sudo -v`), and
without a terminal or cached credentials it prints those commands for you to run and does the rest.

    [quiet]
    apps = ["Docker", "Slack", "Google Chrome"]   # applications to quit (perflab.toml); default: QUIT_APPS
    spotlight = false                             # keep indexing on: for a build directory kept out of Spotlight by a
                                                  # .noindex suffix or its Privacy list, which costs nothing to leave on
    agents = ["^com\\.example\\.sync$"]           # more labels (regexes) of ~/Library/LaunchAgents to unload, beside
                                                  # AGENTS: `git maintenance start`'s hourly/daily/weekly gc and repack

What it does not do, because macOS exposes no knob: pin threads to the performance cores (size JMH's threads to
`hw.perflevel0.logicalcpu` instead), hold the clock frequency, or stop the thermal controller (watch the thermal
state the load sampler records). `perflab ab run` with a `loadgate` waits for the machine to be quiet and reruns a
cell measured under a throttling thermal state; this command makes that wait short.

State: ~/.perflab/quiet.json (PERFLAB_QUIET_STATE).
"""
import json, os, re, signal, subprocess, sys, time

from . import loadgate

STATE_ENV = "PERFLAB_QUIET_STATE"
QUIT_APPS = ["Docker", "Slack", "Discord", "Microsoft Teams", "zoom.us", "Google Chrome", "Brave Browser", "Firefox", "Safari",
             "Arc", "Photos", "Music", "Mail", "Messages", "IntelliJ IDEA", "Visual Studio Code", "Xcode", "Dropbox",
             "Google Drive", "OneDrive", "Spotify"]
TM_PREFS = "/Library/Preferences/com.apple.TimeMachine"
# the user's launchd agents that wake up to do heavy background work: `git maintenance start`'s (gc, repack, prefetch,
# commit-graph of every registered repository) and anything that runs it
AGENTS = [r"^org\.git-scm\.git\.(hourly|daily|weekly)$", r"git-maintenance"]
AGENTS_DIR = os.path.expanduser("~/Library/LaunchAgents")


def state_path():
    return os.path.abspath(os.path.expanduser(os.environ.get(STATE_ENV) or "~/.perflab/quiet.json"))


def load_state():
    try:
        return json.load(open(state_path()))
    except (OSError, ValueError):
        return None


def save_state(state):
    path = state_path()
    if state is None:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w") as f:
        json.dump(state, f, indent=1)
    os.replace(path + ".tmp", path)


def run(cmd, timeout=30):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as e:
        return subprocess.CompletedProcess(cmd, 1, "", str(e))


class Sudo:
    """Runs privileged commands, asking for the password once; where it can't (no terminal, no cached credentials), it
    collects the commands for the user to run and says so at the end."""

    def __init__(self):
        self.ok = None
        self.deferred = []

    def available(self):
        if self.ok is None:
            self.ok = run(["sudo", "-n", "true"]).returncode == 0
            if not self.ok and sys.stdin.isatty():
                print("sudo: for Time Machine, Spotlight, software update and Low Power Mode", flush=True)
                self.ok = subprocess.run(["sudo", "-v"]).returncode == 0
        return self.ok

    def run(self, cmd):
        """True when the command ran; False when it is left for the user."""
        if self.available():
            r = run(["sudo", "-n", *cmd])
            if r.returncode:
                print(f"  {' '.join(cmd)}: {(r.stderr or r.stdout).strip()}")
            return r.returncode == 0
        self.deferred.append("sudo " + " ".join(cmd))
        return False

    def report(self):
        if self.deferred:
            print("Could not get root; run these yourself:\n  " + "\n  ".join(self.deferred))


# --- what is on

def time_machine():
    """Whether automatic backups are on; None when Time Machine is not set up."""
    r = run(["defaults", "read", TM_PREFS, "AutoBackup"])
    return r.stdout.strip() == "1" if r.returncode == 0 else None


def parse_mdutil(out):
    """`mdutil -a -s` to {volume: indexing on}; a volume that reports neither state is left out."""
    vols, vol = {}, None
    for line in out.splitlines():
        if line and not line[0].isspace() and line.rstrip().endswith(":"):
            vol = line.rstrip()[:-1]
        elif vol and "Indexing enabled" in line:
            vols[vol] = True
        elif vol and "Indexing disabled" in line:
            vols[vol] = False
    return vols


def spotlight():
    return parse_mdutil(run(["mdutil", "-a", "-s"]).stdout)


def software_update():
    """Whether automatic checks are on; None if unknown."""
    out = run(["softwareupdate", "--schedule"]).stdout.lower()
    return True if "turned on" in out else False if "turned off" in out else None


def low_power():
    return loadgate.machine().get("lowpower")


def running_apps(names):
    """The applications among `names` with a process running from their bundle (comm under <name>.app/)."""
    comms = run(["ps", "-A", "-o", "comm="]).stdout
    return [n for n in names if f"/{n}.app/" in comms]


def cores():
    p = run(["sysctl", "-n", "hw.perflevel0.logicalcpu"]).stdout.strip()
    e = run(["sysctl", "-n", "hw.perflevel1.logicalcpu"]).stdout.strip()
    return (int(p), int(e)) if p.isdigit() and e.isdigit() else None


def configured_apps():
    from . import config
    apps = config.get().get("quiet", "apps")
    return list(apps) if isinstance(apps, list) else QUIT_APPS


def configured_spotlight():
    from . import config
    v = config.get().get("quiet", "spotlight")
    return v is None or bool(v)


def configured_agents():
    from . import config
    more = config.get().get("quiet", "agents")
    return AGENTS + (list(more) if isinstance(more, list) else [])


def loaded_agents(patterns, agents_dir=None):
    """{label: plist} of the user's loaded launchd agents (in ~/Library/LaunchAgents) whose label matches a pattern."""
    d = agents_dir or AGENTS_DIR
    loaded = {line.split("\t")[-1] for line in run(["launchctl", "list"]).stdout.splitlines()[1:]}
    out = {}
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        label = f.removesuffix(".plist")
        if f.endswith(".plist") and label in loaded and any(re.search(p, label) for p in patterns):
            out[label] = os.path.join(d, f)
    return out


def unload_agents(agents):
    """Unloads each agent (no root: the user's own domain); the labels it unloaded. A run in progress is stopped."""
    uid = os.getuid()
    return [label for label in agents if run(["launchctl", "bootout", f"gui/{uid}/{label}"]).returncode == 0]


# --- on / off

def quit_apps(apps):
    """Asks each application to quit (as the Dock's Quit does) and waits up to 20 s for all of them; the ones still
    running are reported and left."""
    for app in apps:
        run(["osascript", "-e", f'tell application "{app}" to quit'], timeout=10)
    for _ in range(40):
        left = running_apps(apps)
        if not left:
            return []
        time.sleep(0.5)
    return left


def caffeinate_pid(state):
    """The caffeinate `on` started, if it still runs."""
    pid = (state or {}).get("caffeinate")
    if pid and "caffeinate" in run(["ps", "-p", str(pid), "-o", "comm="]).stdout:
        return pid
    return None


REVERSE = {"tmutil disable": "tmutil enable", "mdutil -a -i off": "mdutil -a -i on", "softwareupdate --schedule off": "softwareupdate --schedule on",
           "pmset -a lowpowermode 0": "pmset -a lowpowermode 1"}


def on(argv):
    prev = load_state()
    if prev:
        print(f"already on since {time.strftime('%H:%M', time.localtime(prev['since']))}; `perflab quiet off` first to re-record what to restore")
        return status([])
    if sys.platform != "darwin":
        sys.exit("perflab quiet: macOS only")
    with_apps, with_spotlight = "--no-apps" not in argv, "--no-spotlight" not in argv and configured_spotlight()
    sudo = Sudo()
    # what `on` turned off, for `off` to turn back on: only what ran, not what was left for the user
    state = {"since": time.time(), "done": {}, "apps": [], "agents": {}, "caffeinate": None, "pending": []}
    done = []
    if time_machine() and sudo.run(["tmutil", "disable"]):
        run(["tmutil", "stopbackup"])
        state["done"]["timeMachine"] = True
        done.append("Time Machine off")
    vols = [v for v, on_ in (spotlight() if with_spotlight else {}).items() if on_]
    if vols and sudo.run(["mdutil", "-a", "-i", "off"]):
        state["done"]["spotlight"] = vols
        done.append(f"Spotlight indexing off ({', '.join(vols)})")
    if software_update() and sudo.run(["softwareupdate", "--schedule", "off"]):
        state["done"]["softwareUpdate"] = True
        done.append("automatic software update checks off")
    if low_power() and sudo.run(["pmset", "-a", "lowpowermode", "0"]):
        state["done"]["lowPower"] = True
        done.append("Low Power Mode off")
    if with_apps:
        apps = running_apps(configured_apps())
        if apps:
            left = quit_apps(apps)
            state["apps"] = [a for a in apps if a not in left]
            if state["apps"]:
                done.append(f"quit {', '.join(state['apps'])}")
            if left:
                print(f"  still running (quit them yourself): {', '.join(left)}")
    agents = loaded_agents(configured_agents())
    if agents:
        state["agents"] = {label: agents[label] for label in unload_agents(agents)}
        if state["agents"]:
            done.append(f"unloaded {', '.join(state['agents'])}")
    try:
        p = subprocess.Popen(["caffeinate", "-dimsu"], start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        state["caffeinate"] = p.pid
        done.append("caffeinate (no idle, display or disk sleep)")
    except OSError:
        pass
    state["pending"] = list(sudo.deferred)
    save_state(state)
    print("quiet: " + ("; ".join(done) if done else "nothing to change"))
    sudo.report()
    return status([])


def off(argv):
    state = load_state()
    if not state:
        print("quiet is not on (nothing recorded to restore)")
        return 0
    sudo = Sudo()
    did = state.get("done") or {}
    done = []
    if did.get("timeMachine") and sudo.run(["tmutil", "enable"]):
        done.append("Time Machine on")
    vols = did.get("spotlight") or []
    if vols and all([sudo.run(["mdutil", "-i", "on", v]) for v in vols]):
        done.append(f"Spotlight indexing on ({', '.join(vols)})")
    if did.get("softwareUpdate") and sudo.run(["softwareupdate", "--schedule", "on"]):
        done.append("automatic software update checks on")
    if did.get("lowPower") and sudo.run(["pmset", "-a", "lowpowermode", "1"]):
        done.append("Low Power Mode on")
    pid = caffeinate_pid(state)
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
            done.append("caffeinate stopped")
        except OSError:
            pass
    back = [label for label, plist in (state.get("agents") or {}).items()
            if run(["launchctl", "bootstrap", f"gui/{os.getuid()}", plist]).returncode == 0]
    if back:
        done.append(f"loaded {', '.join(back)}")
    if "--no-apps" not in argv and state.get("apps"):
        for app in state["apps"]:
            run(["open", "-g", "-a", app])
        done.append(f"relaunched {', '.join(state['apps'])}")
    print("restored: " + ("; ".join(done) if done else "nothing"))
    # what `on` could not do without root: if the user ran it, the reverse is theirs too
    undo = [REVERSE.get(c.removeprefix("sudo "), "") for c in state.get("pending") or []]
    if any(undo):
        print("if you ran what `on` left to you, reverse it:\n  " + "\n  ".join("sudo " + u for u in undo if u))
    if sudo.deferred:  # `done` stays as it was: another `off`, with root, restores the rest
        state["pending"] = list(sudo.deferred)
        state["caffeinate"], state["apps"], state["agents"] = None, [], {}
        save_state(state)
        sudo.report()
        return 1
    save_state(None)
    return 0


def status(argv):
    state = load_state()
    if state:
        did = state.get("done") or {}
        what = [w for w, on_ in (("Time Machine", did.get("timeMachine")), ("Spotlight", did.get("spotlight")),
                                 ("software update", did.get("softwareUpdate")), ("Low Power Mode", did.get("lowPower"))) if on_]
        print(f"quiet: on since {time.strftime('%H:%M', time.localtime(state['since']))}"
              + (f", turned off {', '.join(what)}" if what else ", nothing turned off") + (f"; quit {', '.join(state['apps'])}" if state.get("apps") else "")
              + (f"; unloaded {', '.join(state['agents'])}" if state.get("agents") else "")
              + ("; caffeinate" if caffeinate_pid(state) else ""))
        if state.get("pending"):
            print("  left to you (no root): " + "; ".join(state["pending"]))
    else:
        print("quiet: off")
    tm, sl, su = time_machine(), spotlight(), software_update()
    print("now: " + ", ".join(x for x in [
        None if tm is None else f"Time Machine {'on' if tm else 'off'}",
        f"Spotlight indexing {'on' if any(sl.values()) else 'off'}" if sl else None,
        None if su is None else f"software update checks {'on' if su else 'off'}"] if x))
    apps = running_apps(configured_apps())
    if apps:
        print("running: " + ", ".join(apps))
    agents = loaded_agents(configured_agents())
    if agents:
        print("background agents loaded: " + ", ".join(agents))
    c = cores()
    if c:
        print(f"cores: {c[0]} performance, {c[1]} efficiency (size JMH's threads to the performance cores)")
    load, top = loadgate.other_load(os.getpid(), 5.0)
    print(loadgate.describe(loadgate.machine(), load, top))
    return 0


def main(argv):
    cmd = argv[0] if argv else ""
    if cmd == "on":
        return on(argv[1:])
    if cmd == "off":
        return off(argv[1:])
    if cmd == "status":
        return status(argv[1:])
    sys.exit(__doc__)
