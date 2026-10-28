"""`perflab server`: one per user, it owns the machine's measurements. It keeps a durable queue of jobs, runs one at a
time, and serves a UI (the queue, storage admin) and every registered project's index on 127.0.0.1.

  perflab server start [--port <port>]   start it unless it is running; print its URL (idempotent, like `perflab serve`)
  perflab server stop                    stop it; a running job runs on, and the next server adopts it
  perflab server status                  its URL and the queue
  perflab server run [--port <port>]     run it in the foreground
  perflab submit [--detach] [--priority <n>] [--env NAME[=VALUE]]... -- <perflab arguments>
                                         queue `perflab <arguments>` for this project (starting the server if need be),
                                         and follow its transcript until it ends; Ctrl-C detaches, the job runs on
  perflab jobs [--all]                   the queue, and with --all the finished jobs too

A job is a perflab command line, `{argv, cwd, env}`: the server runs `python -m perflab --transcript
<job dir>/transcript.txt <argv>` in `cwd`, in its own session and process group, with the submitting shell's toolchain
variables (ENV_KEEP) and PERFLAB_CONTROL=<job dir>/control (perflab.control: pause and cancel at a cell boundary) and
PERFLAB_JOB=<id>, under a small wrapper that holds an flock on <job dir>/lock while it lives and writes its exit status
to <job dir>/exit.json (read by a server that adopts the job after a restart). Cancel writes `cancel` there, and after
a grace period sends SIGTERM to the job's process group.

A job's identity is its lock, not its pid: a server that can take the lock knows the job is gone (and that the pid may
now be someone else's), and signals the job's process group only while the lock is held. A job whose wrapper took no
lock (one started before the lock existed) is identified by its pid and, when it was recorded at spawn, the pid's start
time.

State is in ~/.perflab/server (PERFLAB_SERVER_HOME): jobs.sqlite, token (POSTs carry it as X-Perflab-Token), server.json
(pid, port), jobs/<id>/. The port is 8690 unless --port or PERFLAB_SERVER_PORT says otherwise.

HTTP (JSON unless noted):
  GET  /api/status                       the server
  GET  /api/jobs[?all=1]                 jobs, queue order first
  GET  /api/jobs/<id>                    one job
  GET  /api/jobs/<id>/transcript[?tail=<lines>|offset=<bytes>][&file=output]   its transcript (text), or its output
  POST /api/jobs                         {argv, cwd, env?, priority?}: a new job, `perflab <argv>`
  POST /api/jobs/<id>/pause|resume|cancel
  POST /api/jobs/<id>/priority           {priority}
  POST /api/jobs/<id>/move               {by: -1 (earlier) or 1}
  GET  /api/projects; POST /api/projects {root}
  GET  /api/storage                      perflab.storage's entries of every project
  POST /api/storage/cleanup              {action: builds|graphs|profiles|delete, dry_run (default true), target?, days?}
  POST /api/storage/pin                  {project, kind, name, pinned}
  GET  /, /admin                         the queue page, the storage page
  GET  /p/<project>/...                  the project's campaigns and runs (its index), as `perflab serve` serves them

Under /p/, only the campaigns and runs directories are served (at their paths below the two's common directory), never
a path with a segment that starts with `.` (worktrees, build snapshots), and every page but the project's index, which
carries the token, under a CSP sandbox: its scripts run in an opaque origin, so that a flame graph or a page a
benchmark wrote cannot read the index (and its token) or call the API.
"""
import argparse, fcntl, hashlib, json, os, re, secrets, signal, socket, sqlite3, subprocess, sys, threading, time, traceback
import http.server, urllib.error, urllib.parse, urllib.request

from . import config, control, httpd, storage, transcript

DEFAULT_PORT = 8690
HOME_ENV, PORT_ENV, GRACE_ENV = "PERFLAB_SERVER_HOME", "PERFLAB_SERVER_PORT", "PERFLAB_SERVER_GRACE"
JOB_ENV = "PERFLAB_JOB"
LOCAL_ENV = "PERFLAB_LOCAL"  # set by a command run in the foreground, so that the perflab commands it runs are too
STATES = ("queued", "running", "paused", "done", "failed", "cancelled")
ACTIVE = ("running", "paused")
FINAL = ("done", "failed", "cancelled")
TRANSITIONS = {"queued": {"running", "cancelled"},
               "running": {"paused", "done", "failed", "cancelled"},
               "paused": {"running", "done", "failed", "cancelled"}}
# the submitting shell's variables a job keeps: the toolchain, perflab's own settings, the locale
ENV_KEEP = re.compile(r"^(PATH|HOME|USER|LOGNAME|SHELL|LANG|LC_\w+|TMPDIR|TZ|JAVA_HOME|JAVA_\w+|JDK_\w+|SBT_\w+|SCALA\w*|"
                      r"MAVEN_\w+|M2_HOME|COURSIER_\w+|MISE_\w+|ASYNC_PROFILER\w*|JFRCONV|PYTHONPATH|PERFLAB_\w+)$")
ENV_DROP = {"PERFLAB_TRANSCRIPT", control.ENV, control.POLL_ENV, HOME_ENV, PORT_ENV, GRACE_ENV, JOB_ENV, LOCAL_ENV}
PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # what `import perflab` needs on the path


def home():
    return os.path.abspath(os.path.expanduser(os.environ.get(HOME_ENV) or "~/.perflab/server"))


def _alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, TypeError, ValueError):
        return False


def _reap(pid):
    """Reaps `pid` if it has exited and is this process's own child (a server restarted in this process); whether it was."""
    try:
        return bool(os.waitpid(int(pid), os.WNOHANG)[0])
    except (ChildProcessError, ValueError, TypeError):
        return False


def _started(pid):
    """When `pid` started, as `ps` says (to the second), or None; with the pid, it tells a process from a later one
    that reuses its pid."""
    try:
        r = subprocess.run(["ps", "-o", "lstart=", "-p", str(int(pid))], capture_output=True, text=True, timeout=10,
                           env={**os.environ, "LC_ALL": "C"})
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() or None


def _lock_held(path):
    """Whether some process holds an flock on `path`; None if there is no such file."""
    try:
        fd = os.open(path, os.O_RDONLY)
    except FileNotFoundError:
        return None
    except OSError:
        return True  # unreadable: assume the job is there rather than give it up
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return False
    except OSError:  # BlockingIOError: held
        return True
    finally:
        os.close(fd)  # and with it our lock, if we took it


def job_alive(job):
    """Whether the job's wrapper is still running: its lock is held; or, for a job whose wrapper took no lock (started
    before there was one, or not yet taken), its pid is alive and started when the server recorded at spawn."""
    if job.get("dir"):
        held = _lock_held(os.path.join(job["dir"], LOCK_NAME))
        if held is not None:
            return held
    pid = job.get("pid")
    if _reap(pid) or not _alive(pid):
        return False
    return job.get("pid_start") is None or _started(pid) == job["pid_start"]


def _listening(port):
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


class Conflict(Exception):
    """A request that the job's state does not allow."""


# ---- the queue

class Queue:
    """Jobs and projects in SQLite. Every method takes the lock; the HTTP threads and the worker share one Queue."""

    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with self._db() as db:
            db.executescript("""
              CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY AUTOINCREMENT, project TEXT, argv TEXT, cwd TEXT,
                env TEXT, python TEXT, module TEXT, state TEXT, priority INTEGER DEFAULT 0, seq REAL, created REAL,
                started REAL, ended REAL, rc INTEGER, pid INTEGER, cancel_requested REAL, dir TEXT, transcript TEXT, note TEXT,
                pid_start TEXT);
              CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, root TEXT UNIQUE, name TEXT, campaigns TEXT, runs TEXT,
                registered REAL);""")
            if "pid_start" not in {r[1] for r in db.execute("PRAGMA table_info(jobs)")}:  # a queue from before it
                db.execute("ALTER TABLE jobs ADD COLUMN pid_start TEXT")

    def _db(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        return db

    def _q(self, sql, args=()):
        with self.lock, self._db() as db:
            return [dict(r) for r in db.execute(sql, args)]

    # projects

    def register(self, root):
        """The project at `root` (holding perflab.toml), registered if new."""
        root = os.path.realpath(root)
        if not os.path.exists(os.path.join(root, "perflab.toml")):
            raise ValueError(f"no perflab.toml in {root}")
        cfg = config.find(root)
        pid = re.sub(r"[^A-Za-z0-9_.-]", "-", os.path.basename(root)) + "-" + hashlib.sha1(root.encode()).hexdigest()[:6]
        with self.lock, self._db() as db:
            db.execute("INSERT INTO projects(id, root, name, campaigns, runs, registered) VALUES(?,?,?,?,?,?) "
                       "ON CONFLICT(root) DO UPDATE SET campaigns=excluded.campaigns, runs=excluded.runs",
                       (pid, root, os.path.basename(root), cfg.campaigns, cfg.runs, time.time()))
        return self.project(pid)

    def project(self, pid):
        rows = self._q("SELECT * FROM projects WHERE id=?", (pid,))
        return _project(rows[0]) if rows else None

    def projects(self):
        return [_project(r) for r in self._q("SELECT * FROM projects ORDER BY name")]

    # jobs

    def submit(self, project, argv, cwd, env=None, priority=0, python=None, module="perflab", jobs_dir=None):
        if not isinstance(argv, list) or not all(isinstance(a, str) for a in argv) or not argv:
            raise ValueError("argv must be a non-empty list of strings")
        now = time.time()
        with self.lock, self._db() as db:
            cur = db.execute("INSERT INTO jobs(project, argv, cwd, env, python, module, state, priority, seq, created) "
                             "VALUES(?,?,?,?,?,?,?,?,?,?)",
                             (project, json.dumps(argv), cwd, json.dumps(env or {}), python, module or "perflab", "queued",
                              int(priority or 0), now, now))
            jid = cur.lastrowid
            d = os.path.join(jobs_dir or os.path.join(os.path.dirname(self.path), "jobs"), str(jid))
            db.execute("UPDATE jobs SET dir=?, transcript=? WHERE id=?", (d, os.path.join(d, "transcript.txt"), jid))
        os.makedirs(d, exist_ok=True)
        return self.get(jid)

    def get(self, jid):
        rows = self._q("SELECT * FROM jobs WHERE id=?", (int(jid),))
        return _job(rows[0]) if rows else None

    def queued(self):
        return [_job(r) for r in self._q("SELECT * FROM jobs WHERE state='queued' ORDER BY priority DESC, seq, id")]

    def jobs(self, include_final=True, limit=100):
        active = [_job(r) for r in self._q("SELECT * FROM jobs WHERE state IN ('running','paused') ORDER BY started")]
        queued = self.queued()
        for i, j in enumerate(queued):
            j["position"] = i + 1
        final = [_job(r) for r in self._q("SELECT * FROM jobs WHERE state IN ('done','failed','cancelled') "
                                          "ORDER BY ended DESC, id DESC LIMIT ?", (limit,))] if include_final else []
        return active + queued + final

    def update(self, jid, **kw):
        if not kw:
            return self.get(jid)
        with self.lock, self._db() as db:
            db.execute(f"UPDATE jobs SET {', '.join(k + '=?' for k in kw)} WHERE id=?", (*kw.values(), int(jid)))
        return self.get(jid)

    def transition(self, jid, state, **kw):
        """Moves a job to `state` if its current state allows it (TRANSITIONS); Conflict otherwise."""
        with self.lock:
            j = self.get(jid)
            if j is None:
                raise KeyError(jid)
            if state == j["state"]:
                return self.update(jid, **kw)
            if state not in TRANSITIONS.get(j["state"], ()):
                raise Conflict(f"job {jid} is {j['state']}: it cannot become {state}")
            if state in FINAL:
                kw.setdefault("ended", time.time())
            return self.update(jid, state=state, **kw)

    def claim(self):
        """The next queued job, now running; None if there is none or a job is already running."""
        with self.lock:
            if self.active():
                return None
            q = self.queued()
            if not q:
                return None
            return self.transition(q[0]["id"], "running", started=time.time())

    def active(self):
        rows = self._q("SELECT * FROM jobs WHERE state IN ('running','paused') ORDER BY started LIMIT 1")
        return _job(rows[0]) if rows else None

    def set_priority(self, jid, priority):
        with self.lock:
            j = self.get(jid)
            if j is None:
                raise KeyError(jid)
            if j["state"] != "queued":
                raise Conflict(f"job {jid} is {j['state']}: only a queued job has a priority")
            return self.update(jid, priority=int(priority))

    def move(self, jid, by):
        """Moves a queued job one place earlier (by < 0) or later in the queue. Passing a job of another priority takes
        that job's priority, so the order stays (priority, then submission)."""
        with self.lock:
            q = self.queued()
            i = next((i for i, j in enumerate(q) if j["id"] == int(jid)), None)
            if i is None:
                raise Conflict(f"job {jid} is not queued")
            k = i + (-1 if by < 0 else 1)
            if not 0 <= k < len(q):
                return q[i]
            me, other = q[i], q[k]
            if me["priority"] == other["priority"]:
                self.update(me["id"], seq=other["seq"])
                self.update(other["id"], seq=me["seq"])
                if me["seq"] == other["seq"]:  # submitted in the same instant
                    self.update(me["id"], seq=other["seq"] + (-1e-6 if by < 0 else 1e-6))
            else:
                self.update(me["id"], priority=other["priority"], seq=other["seq"] + (-1e-6 if by < 0 else 1e-6))
            return self.get(jid)


def _job(r):
    r = dict(r)
    r["argv"] = json.loads(r["argv"] or "[]")
    r["env"] = json.loads(r["env"] or "{}")
    if r.get("dir"):
        c = os.path.join(r["dir"], "control")
        r["control"] = control.read(c)
        r["acked"] = control.acked(c)
    return r


def _project(r):
    r = dict(r)
    root = os.path.commonpath([r["campaigns"], r["runs"]]) if r.get("runs") else r["campaigns"]
    r["serveRoot"] = root  # what the URLs are relative to; only the mounts below it are served
    r["mounts"] = [[os.path.relpath(d, root).replace(os.sep, "/"), d] for d in (r["campaigns"], r.get("runs")) if d]
    r["index"] = f"/p/{r['id']}/" + os.path.relpath(os.path.join(r["campaigns"], "index.html"), root)
    return r


def _mount(project, rel):
    """The directory `rel` (a URL path below /p/<project>/, unquoted) is in, and its path there; None if it is in
    neither the campaigns nor the runs, or names a dot file or directory."""
    if any(s.startswith(".") for s in rel.split("/")):
        return None
    for prefix, d in sorted(project["mounts"], key=lambda m: -len(m[0])):
        if prefix == ".":
            return d, rel
        if rel == prefix or rel.startswith(prefix + "/"):
            return d, rel[len(prefix) + 1:]
    return None


def _under(path, project):
    return any(path.startswith(d + os.sep) for _, d in project["mounts"])


def public(job):
    """A job as the API shows it: without its environment, which may name more than anyone needs to see."""
    return {k: v for k, v in job.items() if k != "env"} | {"envKeys": sorted(job.get("env") or {})}


# ---- control requests

def pause(q, jid):
    j = q.get(jid)
    if j is None:
        raise KeyError(jid)
    if j["state"] not in ACTIVE:
        raise Conflict(f"job {jid} is {j['state']}: only a running job pauses")
    control.write(os.path.join(j["dir"], "control"), control.PAUSE)
    return q.get(jid)


def resume(q, jid):
    j = q.get(jid)
    if j is None:
        raise KeyError(jid)
    if j["state"] not in ACTIVE:
        raise Conflict(f"job {jid} is {j['state']}: only a paused job resumes")
    if j["control"] == control.PAUSE:
        control.write(os.path.join(j["dir"], "control"), None)
    return q.get(jid)


def cancel(q, jid):
    with q.lock:
        j = q.get(jid)
        if j is None:
            raise KeyError(jid)
        if j["state"] == "queued":
            return q.transition(jid, "cancelled")
        if j["state"] not in ACTIVE:
            raise Conflict(f"job {jid} is {j['state']}")
        control.write(os.path.join(j["dir"], "control"), control.CANCEL)
        return q.update(jid, cancel_requested=j["cancel_requested"] or time.time())


# ---- the worker

class Worker(threading.Thread):
    """Runs the queue's jobs one at a time; a job found running at start (the server restarted under it) is adopted
    and watched until it exits."""

    def __init__(self, q, grace=10.0, kill_after=20.0):
        super().__init__(daemon=True, name="perflab-worker")
        self.q, self.grace, self.kill_after = q, grace, kill_after
        self.wake, self.stopping = threading.Event(), threading.Event()

    def run(self):
        while not self.stopping.is_set():
            try:
                job = self.q.active() or self.q.claim()
                if job:
                    self.supervise(job)
                else:
                    self.wake.wait(1)
                    self.wake.clear()
            except Exception:
                traceback.print_exc()
                time.sleep(1)

    def command(self, job):
        """The job's perflab command line, under WRAPPER, which records how it ended in <job dir>/exit.json."""
        return [sys.executable, "-c", WRAPPER, os.path.join(job["dir"], EXIT_NAME), os.path.join(job["dir"], LOCK_NAME),
                job["python"] or sys.executable, "-m", job["module"] or "perflab", "--transcript", job["transcript"], *job["argv"]]

    def environment(self, job):
        env = {k: v for k, v in os.environ.items() if not k.startswith("PERFLAB_")}
        env.update(job["env"])
        env[control.ENV] = os.path.join(job["dir"], "control")
        env[JOB_ENV] = str(job["id"])
        env["PYTHONUNBUFFERED"] = "1"
        return env

    def spawn(self, job):
        os.makedirs(job["dir"], exist_ok=True)
        for f in ("control", "control.ack", EXIT_NAME, LOCK_NAME):
            control.write(os.path.join(job["dir"], f), None)
        with open(os.path.join(job["dir"], "output.log"), "ab") as out:
            return subprocess.Popen(self.command(job), cwd=job["cwd"], env=self.environment(job), stdin=subprocess.DEVNULL,
                                    stdout=out, stderr=subprocess.STDOUT, start_new_session=True)

    def supervise(self, job):
        jid, proc = job["id"], None
        if job["pid"] is None:
            try:
                proc = self.spawn(job)
            except OSError as e:
                self.q.transition(jid, "failed", note=f"could not start: {e}")
                return
            job = self.q.update(jid, pid=proc.pid, pid_start=_started(proc.pid))
        pid = job["pid"]
        ctl, exit_file = os.path.join(job["dir"], "control"), os.path.join(job["dir"], EXIT_NAME)
        term_at = None
        while True:
            ended = _read_json(exit_file)
            if proc:
                rc = proc.poll()
                if rc is None and ended:  # the wrapper has written its record and is exiting
                    try:
                        rc = proc.wait(5)
                    except subprocess.TimeoutExpired:
                        rc = "recorded"
            else:
                rc = "recorded" if ended else "gone" if not job_alive(job) else None
            if rc is not None:
                break
            if self.stopping.is_set():  # the server is stopping: the job runs on, and the next server adopts it
                return
            j = self.q.get(jid)
            want = "paused" if control.acked(ctl) else "running"
            if j["state"] != want:
                self.q.transition(jid, want)
            now = time.time()
            if j["cancel_requested"] and term_at is None and now - j["cancel_requested"] >= self.grace:
                self._signal_job(job, signal.SIGTERM)
                term_at = now
            elif term_at and now - term_at >= self.kill_after:
                self._signal_job(job, signal.SIGKILL)
                term_at = float("inf")
            self.wake.wait(0.5)
            self.wake.clear()
        ended = _read_json(exit_file)
        if ended and isinstance(ended.get("rc"), int):  # the wrapper's record: all an adopted job leaves of its status
            rc = ended["rc"]
        if not isinstance(rc, int):  # adopted, and its wrapper died without a record (SIGKILL), or is not ours
            rc = None
            failed = "[perflab] failed:" in _tail(job["transcript"], 20)
        else:
            failed = rc != 0
        if os.path.exists(os.path.join(job["dir"], LOCK_NAME)) or job["pid_start"]:
            self._signal_job(job, signal.SIGTERM)  # the wrapper signals its group itself; this only while it lingers
        else:  # a wrapper from before the lock does not: anything the job left behind in its group, as it always was
            self._signal(pid, signal.SIGTERM)
        j = self.q.get(jid)
        state = "cancelled" if j["cancel_requested"] else "failed" if failed else "done"
        self.q.transition(jid, state, rc=rc)
        for f in ("control", "control.ack"):
            control.write(os.path.join(job["dir"], f), None)

    @staticmethod
    def _signal_job(job, sig):
        """Signals the job's process group if the job is still there (job_alive): never a group that reuses its pid."""
        if job_alive(job):
            Worker._signal(job["pid"], sig)

    @staticmethod
    def _signal(pgid, sig):
        try:
            os.killpg(pgid, sig)
        except (ProcessLookupError, PermissionError):
            pass


EXIT_NAME, LOCK_NAME = "exit.json", "lock"
# The job's process group leader: it holds an flock on <job dir>/lock for as long as it lives (the job's identity:
# taken on lock.tmp and renamed, so that the lock file is there only once held), runs the job, outlives a SIGTERM to
# the group (the job's to act on), sends SIGTERM to anything the job left in its group, and writes how the job ended
# to exit.json, so that a server adopting the job (restarted while it ran) knows its status. Inline, so that it needs
# nothing but the server's Python. The job does not inherit the lock's descriptor. rc is Popen's: -N for a signal.
WRAPPER = r"""
import fcntl, json, os, signal, subprocess, sys, time
for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
    signal.signal(s, lambda *_: None)
out, lock, cmd = sys.argv[1], sys.argv[2], sys.argv[3:]
try:
    fd = os.open(lock + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    os.write(fd, str(os.getpid()).encode())
    os.replace(lock + ".tmp", lock)
except OSError:
    pass  # no lock: the server falls back to the pid and its start time
try:
    rc = subprocess.Popen(cmd).wait()
except OSError as e:
    print(f"could not start {cmd[0]}: {e}", flush=True)
    rc = 127
try:
    os.killpg(0, signal.SIGTERM)  # anything the job left behind in its group (this process ignores it)
except OSError:
    pass
with open(out + ".tmp", "w") as f:
    json.dump({"rc": rc, "ended": time.time()}, f)
os.replace(out + ".tmp", out)
sys.exit(rc if rc >= 0 else 128 - rc)
"""


def _tail(path, lines=None, offset=None, block=1 << 16):
    """The file's text from byte `offset`, or its last `lines` lines (read back from its end, not all of it), or all."""
    try:
        with open(path, "rb") as f:
            if offset is not None:
                f.seek(int(offset))
                return f.read().decode(errors="replace")
            if not lines:
                return f.read().decode(errors="replace")
            pos, data = f.seek(0, os.SEEK_END), b""
            while pos > 0 and data.count(b"\n") <= lines:  # one more than `lines`: the end of the line before them
                n = min(block, pos)
                pos -= n
                f.seek(pos)
                data = f.read(n) + data
    except OSError:
        return ""
    return b"".join(data.splitlines(keepends=True)[-lines:]).decode(errors="replace")


# ---- HTTP

class Server:
    """The queue, its worker and the HTTP server, in this process."""

    def __init__(self, home_dir=None, port=None, grace=None):
        self.home = home_dir or home()
        os.makedirs(self.home, exist_ok=True)
        self.q = Queue(os.path.join(self.home, "jobs.sqlite"))
        self.token = token(self.home)
        g = grace if grace is not None else float(os.environ.get(GRACE_ENV) or 10)
        self.worker = Worker(self.q, g)
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", DEFAULT_PORT if port is None else port), self._handler())
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        self.url = f"http://127.0.0.1:{self.port}/"
        self.indexing = set()

    def start(self):
        self.worker.start()
        threading.Thread(target=self.httpd.serve_forever, daemon=True, name="perflab-http").start()
        return self

    def stop(self):
        self.worker.stopping.set()
        self.worker.wake.set()
        self.httpd.shutdown()
        self.httpd.server_close()

    def serve_forever(self):
        """Foreground: writes server.json, serves until SIGTERM or SIGINT."""
        self.worker.start()
        state = os.path.join(self.home, "server.json")
        with open(state + ".tmp", "w") as f:
            json.dump({"pid": os.getpid(), "port": self.port, "url": self.url, "started": time.time(), "python": sys.executable}, f)
        os.replace(state + ".tmp", state)
        signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=self.httpd.shutdown).start())
        try:
            self.httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            st = _read_json(state)
            if st and st.get("pid") == os.getpid():
                os.unlink(state)

    def build_index(self, project):
        """The project's index, built in the background (by the project's own perflab, as `perflab index` would) if it
        has none yet."""
        if os.path.exists(os.path.join(project["campaigns"], "index.html")) or project["id"] in self.indexing:
            return
        self.indexing.add(project["id"])

        def run():
            try:
                subprocess.run([sys.executable, "-m", "perflab", "index"], cwd=project["root"], capture_output=True, timeout=300,
                               env={**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [PKG, os.environ.get("PYTHONPATH")]))})
            except (OSError, subprocess.TimeoutExpired):
                pass
            finally:
                self.indexing.discard(project["id"])
        threading.Thread(target=run, daemon=True).start()

    def storage_entries(self):
        projects = self.q.projects()
        jobs = {}
        for j in self.q.jobs(include_final=False):
            if j["state"] in ACTIVE:
                jobs.setdefault(j["project"], []).append((j["argv"], j["cwd"]))
        return storage.scan([(p["id"], p["campaigns"], p["runs"]) for p in projects], jobs)

    def _handler(self):
        server = self

        class Handler(httpd.Handler):
            sandbox = False  # this response under SANDBOX

            def __init__(self, *a, **kw):
                super().__init__(*a, directory=server.home, **kw)

            # the boundary: 127.0.0.1 only (the bind), our own Host (DNS rebinding), and for POST our own Origin and the token

            def _host_ok(self):
                return self.headers.get("Host") in (f"127.0.0.1:{server.port}", f"localhost:{server.port}")

            def _origin_ok(self):
                o = self.headers.get("Origin")
                return o is None or o in (f"http://127.0.0.1:{server.port}", f"http://localhost:{server.port}")

            def _send(self, code, body, ctype="application/json; charset=utf-8"):
                data = (json.dumps(body) if ctype.startswith("application/json") else body).encode()
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(data)

            def _error(self, code, msg):
                self._send(code, {"error": msg})

            def end_headers(self):
                if self.sandbox:
                    self.send_header("Content-Security-Policy", SANDBOX)
                super().end_headers()

            def do_HEAD(self):
                self.do_GET()

            def do_GET(self):
                self.sandbox = False
                if not self._host_ok():
                    return self._error(403, "bad Host")
                url = urllib.parse.urlsplit(self.path)
                qs = dict(urllib.parse.parse_qsl(url.query))
                p = url.path
                try:
                    if p in ("/", "/index.html"):
                        from . import serverui
                        return self._send(200, serverui.queue_page(server), "text/html; charset=utf-8")
                    if p == "/admin":
                        from . import serverui
                        return self._send(200, serverui.admin_page(server), "text/html; charset=utf-8")
                    if p.startswith("/p/"):
                        return self._static(p, url.query)
                    if p == "/api/status":
                        return self._send(200, status(server))
                    if p == "/api/jobs":
                        return self._send(200, [public(j) for j in server.q.jobs(include_final=qs.get("all") != "0")])
                    if p == "/api/projects":
                        return self._send(200, server.q.projects())
                    if p == "/api/storage":
                        return self._send(200, {"entries": server.storage_entries(), "projects": server.q.projects()})
                    m = re.fullmatch(r"/api/jobs/(\d+)(/transcript)?", p)
                    if m:
                        j = server.q.get(m.group(1))
                        if j is None:
                            return self._error(404, "no such job")
                        if not m.group(2):
                            return self._send(200, public(j))
                        f = os.path.join(j["dir"], "output.log") if qs.get("file") == "output" else j["transcript"]
                        try:
                            offset = int(qs["offset"]) if "offset" in qs else None
                            lines = int(qs.get("tail") or 0)
                        except ValueError:
                            return self._error(400, "offset and tail are numbers")
                        if (offset or 0) < 0 or lines < 0:
                            return self._error(400, "offset and tail are not negative")
                        text = _tail(f, offset=offset) if offset is not None else _tail(f, lines or None)
                        return self._send(200, text, "text/plain; charset=utf-8")
                    return self._error(404, "not found")
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def _static(self, p, query):
                parts = p.split("/", 3)  # '', 'p', id, rest
                project = server.q.project(parts[2])
                if project is None:
                    return self._error(404, "no such project")
                if len(parts) < 4 or not parts[3]:
                    server.build_index(project)
                    self.send_response(302)
                    self.send_header("Location", project["index"])
                    self.end_headers()
                    return
                m = _mount(project, urllib.parse.unquote(parts[3]))
                if m is None:
                    return self._error(404, "not found")
                self.directory, rel = m
                local = self.translate_path("/" + urllib.parse.quote(rel))
                if os.path.isdir(local) and not p.endswith("/"):
                    self.send_response(301)
                    self.send_header("Location", p + "/" + (f"?{query}" if query else ""))
                    self.end_headers()
                    return
                if p == project["index"] and os.path.isfile(local):
                    # the project's index can queue jobs (a branch campaign's "profile these two"): it gets the token the
                    # queue page already carries, on the same origin
                    page = open(local, encoding="utf-8").read()
                    meta = f'<meta name="perflab-token" content="{server.token}">'
                    at = page.index(">") + 1 if page[:9].lower() == "<!doctype" else 0
                    return self._send(200, page[:at] + meta + page[at:], "text/html; charset=utf-8")
                self.path = "/" + urllib.parse.quote(rel) + (f"?{query}" if query else "")
                self.sandbox = True
                return super().do_GET() if self.command == "GET" else super().do_HEAD()

            def do_POST(self):
                if not self._host_ok() or not self._origin_ok():
                    return self._error(403, "cross-origin request")
                if not secrets.compare_digest(self.headers.get("X-Perflab-Token") or "", server.token):
                    return self._error(403, "bad or missing token")
                try:
                    n = int(self.headers.get("Content-Length") or 0)
                    body = json.loads(self.rfile.read(n) or b"{}") if n <= 1 << 20 else None
                    if not isinstance(body, dict):
                        return self._error(400, "expected a JSON object")
                except ValueError:
                    return self._error(400, "bad JSON")
                p = urllib.parse.urlsplit(self.path).path
                try:
                    if p == "/api/jobs":  # always `perflab`, by the server's Python: what to run is not the request's to say
                        return self._send(201, public(submit_local(server, body)))
                    if p == "/api/projects":
                        project = server.q.register(body.get("root") or "")
                        server.build_index(project)
                        return self._send(200, project)
                    m = re.fullmatch(r"/api/jobs/(\d+)/(pause|resume|cancel|priority|move)", p)
                    if m:
                        jid, op = int(m.group(1)), m.group(2)
                        j = (pause(server.q, jid) if op == "pause" else resume(server.q, jid) if op == "resume"
                             else cancel(server.q, jid) if op == "cancel"
                             else server.q.set_priority(jid, body.get("priority", 0)) if op == "priority"
                             else server.q.move(jid, int(body.get("by", -1))))
                        server.worker.wake.set()
                        return self._send(200, public(j))
                    if p == "/api/storage/cleanup":
                        entries = server.storage_entries()
                        dry = body.get("dry_run", True) is not False
                        r = storage.cleanup(entries, body.get("action"), dry_run=dry, target=body.get("target"),
                                            days=body.get("days"))
                        if not dry:
                            for pr in server.q.projects():
                                if any(_under(x, pr) for x in r["removed"]):
                                    _reindex(pr)
                        return self._send(200, r)
                    if p == "/api/storage/pin":
                        e = next((e for e in server.storage_entries()
                                  if all(e[k] == body.get(k) for k in ("project", "kind", "name"))), None)
                        if e is None:
                            return self._error(404, "no such campaign or run")
                        storage.pin(e["path"], bool(body.get("pinned", True)))
                        return self._send(200, {"pinned": bool(body.get("pinned", True))})
                    return self._error(404, "not found")
                except KeyError:
                    return self._error(404, "no such job")
                except Conflict as e:
                    return self._error(409, str(e))
                except ValueError as e:
                    return self._error(400, str(e))

        return Handler


# the policy of every page under /p/ but the project's index: scripts run (flame graphs need them) in an opaque origin,
# and links open, but nothing reads the server's pages
SANDBOX = "sandbox allow-scripts allow-popups allow-popups-to-escape-sandbox allow-downloads"


def _reindex(project):
    subprocess.Popen([sys.executable, "-m", "perflab", "index"], cwd=project["root"], stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True,
                     env={**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [PKG, os.environ.get("PYTHONPATH")]))})


def submit_local(server, body, python=None, module=None):
    """Queues the job `body` describes ({argv, cwd, env?, priority?}); `python` and `module` (tests: a stand-in for
    perflab) are this process's to choose, never a request's."""
    cwd = os.path.abspath(body.get("cwd") or "")
    if not os.path.isdir(cwd):
        raise ValueError(f"no such directory: {cwd}")
    project = server.q.register(config.find(cwd).root)
    server.build_index(project)
    env = body.get("env") or {}
    if not isinstance(env, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
        raise ValueError("env must map names to strings")
    j = server.q.submit(project["id"], body.get("argv"), cwd, env, body.get("priority") or 0, python,
                        module or "perflab", os.path.join(server.home, "jobs"))
    server.worker.wake.set()
    j["position"] = next((i + 1 for i, q in enumerate(server.q.queued()) if q["id"] == j["id"]), None)
    j["index"] = project["index"]
    return j


def status(server):
    jobs = server.q.jobs(include_final=False)
    return {"pid": os.getpid(), "url": server.url, "home": server.home, "port": server.port,
            "running": next((public(j) for j in jobs if j["state"] in ACTIVE), None),
            "queued": sum(j["state"] == "queued" for j in jobs)}


def token(home_dir):
    path = os.path.join(home_dir, "token")
    try:
        with open(path) as f:
            t = f.read().strip()
            if t:
                return t
    except OSError:
        pass
    t = secrets.token_hex(16)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(t + "\n")
    return t


def _read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


# ---- the client: what the CLI (and later `perflab ab run`) calls

def running():
    """The server's URL if one is running for this user, else None."""
    st = _read_json(os.path.join(home(), "server.json"))
    if st and _alive(st.get("pid")) and _listening(st["port"]):
        return st["url"]
    return None


def ensure(port=None):
    """The server's URL, starting it in the background if it is not running."""
    url = running()
    if url:
        return url
    h = home()
    os.makedirs(h, exist_ok=True)
    if port is None:
        port = int(os.environ.get(PORT_ENV) or DEFAULT_PORT)
    if port and _listening(port):
        sys.exit(f"perflab server: port {port} is in use by something else (--port, or {PORT_ENV})")
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [PKG, os.environ.get("PYTHONPATH")]))}
    with open(os.path.join(h, "server.log"), "ab") as log:
        proc = subprocess.Popen([sys.executable, "-m", "perflab", "server", "run", "--port", str(port)], env=env, cwd=h,
                                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    for _ in range(100):
        st = _read_json(os.path.join(h, "server.json"))
        if st and st.get("pid") == proc.pid and _listening(st["port"]):
            return st["url"]
        if proc.poll() is not None:
            break
        time.sleep(0.1)
    sys.exit(f"perflab server: did not start; see {os.path.join(h, 'server.log')}")


def api(method, path, body=None, url=None):
    url = url or running()
    if not url:
        raise ConnectionError("no perflab server is running (perflab server start)")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url.rstrip("/") + path, data=data, method=method,
                                 headers={"Content-Type": "application/json", "X-Perflab-Token": token(home())})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            text = r.read().decode()
            return json.loads(text) if r.headers.get_content_type() == "application/json" else text
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read()).get("error")
        except ValueError:
            msg = e.reason
        raise RuntimeError(f"perflab server: {e.code} {msg}") from None


def job_env(extra=()):
    """The submitting shell's variables a job keeps (ENV_KEEP), with `extra` (NAME or NAME=VALUE) added, and this
    perflab first on PYTHONPATH."""
    env = {k: v for k, v in os.environ.items() if ENV_KEEP.match(k) and k not in ENV_DROP}
    for e in extra:
        k, eq, v = e.partition("=")
        if eq:
            env[k] = v
        elif k in os.environ:
            env[k] = os.environ[k]
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [PKG, env.get("PYTHONPATH")]))
    return env


def submit(argv, cwd=None, env=None, priority=0, start=True):
    """Queues `perflab <argv>` run in `cwd`; the job (with its "url" on the queue page). Starts the server if need be
    (unless `start` is false, when no server is a ConnectionError)."""
    url = ensure() if start else running()
    if not url:
        raise ConnectionError("no perflab server is running")
    j = api("POST", "/api/jobs", {"argv": list(argv), "cwd": os.path.abspath(cwd or os.getcwd()),
                                  "env": job_env() if env is None else env, "priority": priority}, url)
    j["url"] = f"{url}#job-{j['id']}"
    if j.get("index"):
        j["indexUrl"] = url.rstrip("/") + j["index"]
    return j


class _Tee:
    def __init__(self, out, path):
        self.out, self.path = out, path

    def write(self, text):
        self.out.write(text)
        if self.path:
            with open(self.path, "a") as f:
                f.write(text)

    def flush(self):
        self.out.flush()


def follow(job, out=None, poll=1.0):
    """Prints the job's transcript as it grows until the job ends, and appends it to this command's own transcript if
    it has one (`perflab --transcript`); its exit status (1 if it failed without one, 130 if it was cancelled)."""
    out = _Tee(out or sys.stdout, os.environ.get(transcript.ENV))
    offset = 0
    while True:
        j = api("GET", f"/api/jobs/{job['id']}")
        try:
            with open(j["transcript"], "rb") as f:
                f.seek(offset)
                chunk = f.read()
        except OSError:
            chunk = b""
        if chunk:
            offset += len(chunk)
            out.write(chunk.decode(errors="replace"))
            out.flush()
        if j["state"] in FINAL:
            break
        time.sleep(poll)
    if j["state"] == "failed":
        tail = _tail(os.path.join(j["dir"], "output.log"), 15)
        if tail.strip():
            out.write("[perflab] the job's output ends:\n" + "".join("  " + l for l in tail.splitlines(keepends=True)))
    out.write(f"[perflab] job {j['id']} {j['state']}" + (f" (exit {j['rc']})" if j["rc"] not in (None, 0) else "") + "\n")
    return 130 if j["state"] == "cancelled" else (j["rc"] if j["rc"] is not None else 0 if j["state"] == "done" else 1)


# ---- commands

def _when(t):
    if not t:
        return ""
    d = time.time() - t
    return f"{d:.0f}s ago" if d < 90 else f"{d / 60:.0f}m ago" if d < 5400 else f"{d / 3600:.1f}h ago" if d < 86400 * 2 else time.strftime("%Y-%m-%d", time.localtime(t))


def print_jobs(jobs, out=None):
    out = out or sys.stdout
    if not jobs:
        print("no jobs", file=out)
    for j in jobs:
        pos = f"#{j['position']}" if j.get("position") else ""
        extra = " (pausing)" if j["state"] == "running" and j.get("control") == "pause" else " (cancelling)" if j.get("cancel_requested") and j["state"] in ACTIVE else ""
        print(f"{j['id']:>5}  {j['state'] + extra:<20} {pos:<4} {j['project']:<28} {_when(j['ended'] or j['started'] or j['created']):<10} "
              f"{' '.join(j['argv'])}", file=out)


def main(argv):
    ap = argparse.ArgumentParser(prog="perflab server", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["start", "stop", "status", "run"])
    ap.add_argument("--port", type=int)
    ap.add_argument("--grace", type=float, help="seconds between asking a job to cancel and SIGTERM (default 10)")
    x = ap.parse_args(argv)
    if x.action == "run":
        port = x.port if x.port is not None else int(os.environ.get(PORT_ENV) or DEFAULT_PORT)
        Server(port=port, grace=x.grace).serve_forever()
        return 0
    if x.action == "start":
        url = ensure(x.port)
        root = config.get().root
        if os.path.exists(os.path.join(root, "perflab.toml")):
            api("POST", "/api/projects", {"root": root}, url)
        print(url)
        return 0
    st = _read_json(os.path.join(home(), "server.json"))
    url = running()
    if x.action == "stop":
        if url and st:
            active = [j for j in api("GET", "/api/jobs?all=0", url=url) if j["state"] in ACTIVE]
            os.kill(st["pid"], signal.SIGTERM)
            for _ in range(50):
                if not _alive(st["pid"]):
                    break
                time.sleep(0.1)
            for j in active:
                print(f"job {j['id']} runs on; the next server adopts it")
            print("stopped")
        else:
            print("not running")
        return 0
    if not url:
        print("not running")
        return 1
    print(url)
    print_jobs(api("GET", "/api/jobs?all=0", url=url))
    return 0


def submit_main(argv):
    ap = argparse.ArgumentParser(prog="perflab submit", description="Queues `perflab <arguments>` on the perflab server "
                                 "for this project and follows its transcript (Ctrl-C detaches; the job runs on).")
    ap.add_argument("--detach", action="store_true", help="print the job and return at once")
    ap.add_argument("--priority", type=int, default=0, help="higher runs sooner (default 0)")
    ap.add_argument("--env", action="append", default=[], metavar="NAME[=VALUE]", help="a variable for the job beyond the toolchain's")
    ap.add_argument("argv", nargs=argparse.REMAINDER)
    x = ap.parse_args(argv)
    args = x.argv[1:] if x.argv[:1] == ["--"] else x.argv
    if not args:
        ap.error("what to run: perflab submit -- <command> [arguments]")
    root = config.get().root
    if not os.path.exists(os.path.join(root, "perflab.toml")):
        sys.exit("perflab submit: no perflab.toml here or above")
    return queued(submit(args, os.getcwd(), job_env(x.env), x.priority), x.detach)


def queued(j, detach=False):
    """Says where a submitted job is, then follows it unless `detach`; Ctrl-C detaches."""
    where = f" (#{j['position']} in the queue)" if j.get("position") else ""
    transcript.say(f"[perflab] job {j['id']} queued{where}: {j['url']}")
    if j.get("indexUrl"):
        transcript.say(f"[perflab] index (updates as it runs): {j['indexUrl']}")
    if detach:
        return 0
    try:
        return follow(j)
    except KeyboardInterrupt:
        transcript.say(f"\n[perflab] detached; job {j['id']} runs on: {j['url']}")
        return 0


def delegate(argv):
    """`perflab <argv>` (`run`, `ab run`) as a job on the running server, followed as `perflab submit` follows it;
    None if no server is running, or this is a job or a command run in the foreground already."""
    if os.environ.get(JOB_ENV) or os.environ.get(LOCAL_ENV) or not running():
        return None
    if not os.path.exists(os.path.join(config.get().root, "perflab.toml")):
        return None  # not a project: the command says why, in the foreground
    try:
        j = submit(argv, os.getcwd(), job_env(), start=False)
    except ConnectionError:
        return None
    return queued(j)


def jobs_main(argv):
    ap = argparse.ArgumentParser(prog="perflab jobs", description="The perflab server's queue.")
    ap.add_argument("--all", action="store_true", help="the finished jobs too")
    ap.add_argument("--json", action="store_true")
    x = ap.parse_args(argv)
    if not running():
        print("no perflab server is running (perflab server start)")
        return 1
    jobs = api("GET", f"/api/jobs?all={1 if x.all else 0}")
    if x.json:
        print(json.dumps(jobs, indent=1))
    else:
        print_jobs(jobs)
    return 0
