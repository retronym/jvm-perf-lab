"""`perflab server`: one per user, it owns the machine's measurements. It keeps a durable queue of jobs, runs one at a
time, and serves a UI (the queue, storage admin) and every registered project's index on 127.0.0.1.

  perflab server start [--port <port>]   start it unless it is running; print its URL (idempotent, like `perflab serve`)
  perflab server stop                    stop it; a running job runs on, and the next server adopts it
  perflab server status                  its URL and the queue
  perflab server run [--port <port>]     run it in the foreground
  perflab server reload                  restart it on the code now on disk (it does so itself when that changes)
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
(pid, port), server.lock (flock-ed by the running server: one per home), jobs/<id>/. The port is 8690 unless --port or PERFLAB_SERVER_PORT says otherwise.

Hot reload: a server run in the foreground (`run`, as launchd does) polls its own package's files, and when they change
and then stay put (a checkout or a fast-forward has finished writing them), it restarts itself on them: it checks that
the new code compiles and that the server's modules import, in a subprocess, then stops serving, leaves its jobs to run on
(as `stop` does), and execs its own command line in its own pid, which takes the lock and the port again and adopts the
jobs. New code that does not import is not loaded: the server keeps serving on the old, says why on the queue page and in
/api/status, and tries again on the next change. PERFLAB_SERVER_RELOAD=0 turns the polling off; POST /api/reload (`perflab
server reload`) reloads at once.

HTTP (JSON unless noted):
  GET  /api/status                       the server
  POST /api/reload                       restart the server on the code on disk (409, and why, if it does not import)
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
  GET  /api/v1[/...]; POST /api/v1/...  perflab.api: campaigns, cells, branch history, comparisons, void and rerun
                                         (GET /api/v1 lists it, /api/v1/openapi.json describes it, /api/v1/docs shows it)
  GET  /, /admin                         the queue page, the storage page
  GET  /p/<project>/...                  the project's campaigns and runs (its index), as `perflab serve` serves them

Under /p/, only the campaigns and runs directories are served (at their paths below the two's common directory), never
a path with a segment that starts with `.` (worktrees, build snapshots), and every page but the project's index, which
carries the token, under a CSP sandbox: its scripts run in an opaque origin, so that a flame graph or a page a
benchmark wrote cannot read the index (and its token) or call the API.
"""
import argparse, fcntl, functools, hashlib, json, os, re, secrets, signal, socket, sqlite3, subprocess, sys, threading, time, traceback
import http.server, urllib.error, urllib.parse, urllib.request

from . import config, control, httpd, storage, transcript

DEFAULT_PORT = 8690
HOME_ENV, PORT_ENV, GRACE_ENV = "PERFLAB_SERVER_HOME", "PERFLAB_SERVER_PORT", "PERFLAB_SERVER_GRACE"
PUBLIC_ENV = "PERFLAB_SERVER_URL"  # the URL people are shown for the server (public_url)
JOB_ENV = "PERFLAB_JOB"
LOCAL_ENV = "PERFLAB_LOCAL"  # set by a command run in the foreground, so that the perflab commands it runs are too
STATES = ("queued", "running", "paused", "done", "failed", "cancelled")
ACTIVE = ("running", "paused")


def concurrent(argv):
    """A job that only renders recordings already made (`branch diff`, `ab diff`, `profdiff`): it starts as soon as it
    is queued, beside the job that measures, which a diff would neither disturb much nor need to wait for."""
    return argv[:1] == ["profdiff"] or argv[:2] in (["branch", "diff"], ["ab", "diff"])
FINAL = ("done", "failed", "cancelled")
TRANSITIONS = {"queued": {"running", "cancelled"},
               "running": {"paused", "done", "failed", "cancelled"},
               "paused": {"running", "done", "failed", "cancelled"}}
# the submitting shell's variables a job keeps: the toolchain, perflab's own settings, the locale
ENV_KEEP = re.compile(r"^(PATH|HOME|USER|LOGNAME|SHELL|LANG|LC_\w+|TMPDIR|TZ|JAVA_HOME|JAVA_\w+|JDK_\w+|SBT_\w+|SCALA\w*|"
                      r"MAVEN_\w+|M2_HOME|COURSIER_\w+|MISE_\w+|ASYNC_PROFILER\w*|JFRCONV|PYTHONPATH|PERFLAB_\w+)$")
ENV_DROP = {"PERFLAB_TRANSCRIPT", control.ENV, control.POLL_ENV, HOME_ENV, PORT_ENV, GRACE_ENV, JOB_ENV, LOCAL_ENV}
RELOAD_ENV = "PERFLAB_SERVER_RELOAD"
RELOAD_POLL = 2.0  # seconds between looks at the code
# what the server needs to start and serve its pages; every module is compiled as well
RELOAD_IMPORTS = "import perflab.server, perflab.serverui, perflab.api, perflab.docs, perflab.ui, perflab.index, perflab.mcp"
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
        pid = project_id(root)
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

    def forget(self, pid):
        """Unregister a project: the server stops serving its index and listing it. Its campaigns, runs and finished
        jobs stay, and it registers again when perflab next runs in it. Not while it has a job queued or running."""
        with self.lock:
            p = self.project(pid)
            if p is None:
                raise KeyError(pid)
            busy = [r["id"] for r in self._q("SELECT id FROM jobs WHERE project=? AND state IN ('queued','running','paused')", (pid,))]
            if busy:
                raise Conflict(f"{p['name']} has jobs queued or running: {', '.join(f'#{i}' for i in busy)}")
            with self._db() as db:
                db.execute("DELETE FROM projects WHERE id=?", (pid,))
            return p

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
        """The jobs waiting their turn to measure, in order (a concurrent one does not wait: see `claim_concurrent`)."""
        return [j for j in map(_job, self._q("SELECT * FROM jobs WHERE state='queued' ORDER BY priority DESC, seq, id"))
                if not concurrent(j["argv"])]

    def jobs(self, include_final=True, limit=100):
        active = [_job(r) for r in self._q("SELECT * FROM jobs WHERE state IN ('running','paused') ORDER BY started")]
        queued = self.queued()
        for i, j in enumerate(queued):
            j["position"] = i + 1
        queued += [j for j in map(_job, self._q("SELECT * FROM jobs WHERE state='queued' ORDER BY seq, id")) if concurrent(j["argv"])]
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
        """The job measuring now, if any."""
        return next((j for j in self.running() if not concurrent(j["argv"])), None)

    def running(self):
        return [_job(r) for r in self._q("SELECT * FROM jobs WHERE state IN ('running','paused') ORDER BY started")]

    def claim_concurrent(self):
        """Every queued concurrent job, now running."""
        with self.lock:
            return [self.transition(j["id"], "running", started=time.time())
                    for j in map(_job, self._q("SELECT * FROM jobs WHERE state='queued' ORDER BY seq, id")) if concurrent(j["argv"])]

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


def project_id(root):
    """A project's id on the server: its directory's name and a hash of its real path."""
    return re.sub(r"[^A-Za-z0-9_.-]", "-", os.path.basename(root)) + "-" + hashlib.sha1(root.encode()).hexdigest()[:6]


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
    """A job as the API shows it: without its environment, which may name more than anyone needs to see, and with the
    campaign it runs (`campaign`), for the queue and the project's index to link each other."""
    return {k: v for k, v in job.items() if k != "env"} | {"envKeys": sorted(job.get("env") or {}), "campaign": campaign_of(job)}


def campaign_of(job):
    """The name of the campaign a job's command runs (`ab run <spec>`, `trees <spec>`, `branch profile <spec>`...): the
    "name" of the first spec file among its arguments, or None."""
    for a in job.get("argv") or ():
        if a.endswith(".json"):
            f = os.path.join(job.get("cwd") or "", a)
            try:
                return _spec_name(f, os.stat(f).st_mtime_ns)
            except OSError:
                return None
    return None


@functools.lru_cache(maxsize=256)
def _spec_name(f, mtime):
    try:
        with open(f) as fh:
            name = json.load(fh).get("name")
        return name if isinstance(name, str) else None
    except (OSError, ValueError, AttributeError):
        return None


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
    """Runs the queue's jobs that measure one at a time, and a concurrent one (`concurrent`) as soon as it is queued,
    each watched by a thread of its own; a job found running at start (the server restarted under it) is adopted and
    watched until it exits."""

    def __init__(self, q, grace=10.0, kill_after=20.0, home_dir=None):
        super().__init__(daemon=True, name="perflab-worker")
        self.q, self.grace, self.kill_after = q, grace, kill_after
        self.home = home_dir or home()
        self.wake, self.stopping = threading.Event(), threading.Event()
        self.beside = set()  # the ids of the concurrent jobs being watched

    def start_concurrent(self):
        adopted = [j for j in self.q.running() if concurrent(j["argv"]) and j["id"] not in self.beside]
        for job in adopted + self.q.claim_concurrent():
            self.beside.add(job["id"])

            def watch(job=job):
                try:
                    self.supervise(job)
                except Exception:
                    traceback.print_exc()
                finally:
                    self.beside.discard(job["id"])
            threading.Thread(target=watch, daemon=True, name=f"perflab-job-{job['id']}").start()

    def run_concurrent(self):
        while not self.stopping.is_set():
            try:
                self.start_concurrent()
            except Exception:
                traceback.print_exc()
            self.stopping.wait(0.5)

    def run(self):
        threading.Thread(target=self.run_concurrent, daemon=True, name="perflab-concurrent").start()
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
        # this server's home, so that the perflab a job runs finds this server (registers its project here, links its
        # index here), not the one in the default home: a test's server, or a second one, never reaches the user's
        env[HOME_ENV] = self.home
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
        self.worker = Worker(self.q, g, home_dir=self.home)
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", DEFAULT_PORT if port is None else port), self._handler())
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        self.url = f"http://127.0.0.1:{self.port}/"
        self.indexing = set()
        self.reexec, self.reload_error = False, None

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
        """Foreground: takes home/server.lock (one server per home: a second exits), writes server.json, serves until
        SIGTERM or SIGINT."""
        self.lockf = single_instance(self.home)
        if self.lockf is None:
            self.httpd.server_close()
            st = _read_json(os.path.join(self.home, "server.json")) or {}
            sys.exit(f"perflab server: another server is running for {self.home}"
                     + (f" (pid {st['pid']}, {st.get('url')})" if st.get("pid") else ""))
        self.worker.start()
        state = os.path.join(self.home, "server.json")
        with open(state + ".tmp", "w") as f:
            json.dump({"pid": os.getpid(), "port": self.port, "url": self.url, "started": time.time(), "python": sys.executable}, f)
        os.replace(state + ".tmp", state)
        signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=self.httpd.shutdown).start())
        if os.environ.get(RELOAD_ENV, "1") != "0":
            threading.Thread(target=self.watch_code, daemon=True, name="perflab-reload").start()
        try:
            self.httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            st = _read_json(state)
            if st and st.get("pid") == os.getpid() and not self.reexec:
                os.unlink(state)
        if self.reexec:
            self._exec()

    def watch_code(self):
        """Reloads when the package's files have changed and then stayed put for a poll."""
        seen = code_stamp()
        while True:
            time.sleep(RELOAD_POLL)
            now = code_stamp()
            if now == seen:
                continue
            time.sleep(RELOAD_POLL)
            if code_stamp() != now:  # still being written
                continue
            seen = code_stamp()
            self.reload("its code changed")

    def reload(self, why):
        """Restarts on the code on disk, once it is known to import; else keeps serving and returns why not."""
        err = check_code()
        if err:
            self.reload_error = {"at": time.time(), "error": err}
            print(f"perflab server: not reloading ({why}): the new code does not import:\n{err}", flush=True)
            return err
        print(f"perflab server: reloading: {why}", flush=True)
        self.reload_error, self.reexec = None, True
        threading.Thread(target=self.httpd.shutdown).start()
        return None

    def _exec(self):
        self.worker.stopping.set()  # the jobs run on; the next image adopts them
        self.worker.wake.set()
        self.worker.join(5)
        self.httpd.server_close()
        sys.stdout.flush(), sys.stderr.flush()
        os.execv(sys.executable, sys.orig_argv)

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
                return local_host(self.headers.get("Host"), server.port)

            def _origin_ok(self):
                o = self.headers.get("Origin")
                if o is None:
                    return True
                scheme, _, host = o.partition("://")
                return scheme in ("http", "https") and local_host(host, server.port)

            def _send(self, code, body, ctype="application/json; charset=utf-8", headers=()):
                data = (json.dumps(body) if ctype.startswith("application/json") else body).encode()
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                for k, v in headers:
                    self.send_header(k, v)
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
                    if p == "/favicon.ico":
                        from . import ui
                        return self._send(200, ui.ICON_SVG, "image/svg+xml")
                    if p == "/llms.txt":
                        from . import api
                        return self._send(200, api.llms_txt(), "text/plain; charset=utf-8")
                    if p == "/skill.md":
                        from . import api
                        md = api.skill_md()
                        return self._send(200, md, "text/plain; charset=utf-8") if md else self._error(404, "no perflab skill beside this perflab")
                    if p in ("/doc", "/doc/"):
                        from . import docs
                        return self._send(200, docs.index(server.q.projects()), "text/html; charset=utf-8")
                    if p.startswith("/doc/"):
                        from . import docs
                        page = docs.page(p[len("/doc/"):], server.q.projects())
                        return self._send(200, page, "text/html; charset=utf-8") if page else self._error(404, "no such doc")
                    if p == "/api/v1" or p.startswith("/api/v1/"):
                        return self._api(lambda api: api.http_get(p, qs, server))
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

            def _api(self, handle):
                """An /api/v1 request (perflab.api): its result, described by its schema, or its error."""
                from . import api
                try:
                    code, body, ctype, schema = handle(api)
                except api.ApiError as e:
                    return self._send(e.status, e.body(), headers=[("Link", api.described_by("Error"))])
                except Exception as e:  # a bug: still the API's error shape
                    traceback.print_exc()
                    return self._send(500, {"error": {"code": "internal", "message": f"{type(e).__name__}: {e}"}})
                if ctype.startswith("application/json"):
                    ctype = "application/json; charset=utf-8"
                return self._send(code, body, ctype, [("Link", api.described_by(schema))] if schema else [])

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
                if p.startswith("/api/v1/"):
                    return self._api(lambda api: api.http_post(p, body, server))
                try:
                    if p == "/api/jobs":  # always `perflab`, by the server's Python: what to run is not the request's to say
                        return self._send(201, public(submit_local(server, body)))
                    if p == "/api/reload":
                        err = server.reload("asked to")
                        return self._error(409, f"the code on disk does not import: {err}") if err else self._send(202, {"reloading": True})
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


def code_stamp():
    """The package's files, as (path, mtime, size): what a reload watches."""
    out = []
    for d, dirs, files in os.walk(os.path.join(PKG, "perflab")):
        dirs[:] = [x for x in dirs if x != "__pycache__"]
        for f in files:
            try:
                st = os.stat(os.path.join(d, f))
            except OSError:
                continue
            out.append((os.path.join(d, f), st.st_mtime_ns, st.st_size))
    return sorted(out)


def check_code():
    """None if the package's code on disk compiles and the server's modules import (in a fresh Python), else why not."""
    src = ("import compileall, sys\n"
           f"ok = compileall.compile_dir({os.path.join(PKG, 'perflab')!r}, quiet=1, force=False)\n"
           f"{RELOAD_IMPORTS}\n"
           "sys.exit(0 if ok else 1)")
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(p for p in (PKG, os.environ.get("PYTHONPATH")) if p))
    try:
        r = subprocess.run([sys.executable, "-c", src], capture_output=True, text=True, timeout=60, env=env, cwd=PKG)
    except subprocess.TimeoutExpired:
        return "importing the new code took over 60 s"
    return None if r.returncode == 0 else (r.stderr or r.stdout or f"exit {r.returncode}").strip()[-2000:]


def status(server):
    jobs = server.q.jobs(include_final=False)
    return {"pid": os.getpid(), "url": server.url, "publicUrl": public_url(server.url), "home": server.home, "port": server.port,
            "running": next((public(j) for j in jobs if j["state"] in ACTIVE), None),
            "queued": sum(j["state"] == "queued" for j in jobs), "reloadError": server.reload_error}


def local_host(host, port):
    """Whether `host` (a Host header, or an Origin's host) names this server on this machine: 127.0.0.1 or localhost
    on its port, or a name under .localhost (RFC 6761: loopback only, so no DNS rebinding) on any port or none, as a
    local proxy such as portless (`portless alias perflab 8690`: https://perflab.localhost) forwards it."""
    if not host:
        return False
    if host in (f"127.0.0.1:{port}", f"localhost:{port}"):
        return True
    name = (host.rsplit(":", 1)[0] if host.count(":") == 1 else host).lower()
    return name.endswith(".localhost") and re.fullmatch(r"[a-z0-9.-]+", name) is not None


def single_instance(home_dir):
    """The descriptor of home/server.lock, flock-ed for as long as this process keeps it open; None if another server
    holds it."""
    fd = os.open(os.path.join(home_dir, "server.lock"), os.O_WRONLY | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        return None
    return fd


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

def public_url(url):
    """The URL to show people for the server at `url` (http://127.0.0.1:<port>/, which perflab itself talks to):
    PERFLAB_SERVER_URL, else the name a portless alias gives its port (`portless alias perflab 8690`:
    https://perflab.localhost/), else `url`. The server accepts the .localhost names such a proxy forwards (local_host)."""
    env = os.environ.get(PUBLIC_ENV)
    if env:
        return env.rstrip("/") + "/"
    if not url:
        return url
    port = urllib.parse.urlsplit(url).port
    state = os.path.expanduser(os.environ.get("PORTLESS_STATE_DIR") or "~/.portless")
    routes = _read_json(os.path.join(state, "routes.json"))
    host = next((r.get("hostname") for r in routes or () if isinstance(r, dict) and r.get("port") == port), None)
    if not host:
        return url
    tls = (_read_text(os.path.join(state, "proxy.tls")) or "1").strip() != "0"
    pport = (_read_text(os.path.join(state, "proxy.port")) or "").strip()
    scheme, default = ("https", "443") if tls else ("http", "80")
    return f"{scheme}://{host}" + (f":{pport}" if pport and pport != default else "") + "/"


def _read_text(path):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return None


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
        url = _wait_running(3)  # another `ensure` racing this one: its server listens before it writes server.json
        if url:
            return url
        sys.exit(f"perflab server: port {port} is in use by something else (--port, or {PORT_ENV})")
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [PKG, os.environ.get("PYTHONPATH")]))}
    with open(os.path.join(h, "server.log"), "ab") as log:
        proc = subprocess.Popen([sys.executable, "-m", "perflab", "server", "run", "--port", str(port)], env=env, cwd=h,
                                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    for _ in range(100):
        st = _read_json(os.path.join(h, "server.json"))
        if st and st.get("pid") == proc.pid and _listening(st["port"]):
            return st["url"]
        if proc.poll() is not None:  # it exited: perhaps because another server, started meanwhile, has the lock
            break
        time.sleep(0.1)
    url = _wait_running(3)
    if url:
        return url
    sys.exit(f"perflab server: did not start; see {os.path.join(h, 'server.log')}")


def _wait_running(secs):
    end = time.time() + secs
    while True:
        url = running()
        if url or time.time() >= end:
            return url
        time.sleep(0.1)


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
    shown = public_url(url)
    j["url"] = f"{shown}#job-{j['id']}"
    if j.get("index"):
        j["indexUrl"] = shown.rstrip("/") + j["index"]
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
    ap.add_argument("action", choices=["start", "stop", "status", "run", "reload"])
    ap.add_argument("--port", type=int)
    ap.add_argument("--grace", type=float, help="seconds between asking a job to cancel and SIGTERM (default 10)")
    x = ap.parse_args(argv)
    if x.action == "run":
        port = x.port if x.port is not None else int(os.environ.get(PORT_ENV) or DEFAULT_PORT)
        try:
            srv = Server(port=port, grace=x.grace)
        except OSError as e:
            fd = single_instance(home())
            if fd is None:
                sys.exit(f"perflab server: another server is running for {home()}")
            os.close(fd)
            sys.exit(f"perflab server: cannot listen on port {port}: {e.strerror or e}")
        srv.serve_forever()
        return 0
    if x.action == "start":
        url = ensure(x.port)
        root = config.get().root
        if os.path.exists(os.path.join(root, "perflab.toml")):
            api("POST", "/api/projects", {"root": root}, url)
        print(public_url(url))
        return 0
    st = _read_json(os.path.join(home(), "server.json"))
    url = running()
    if x.action == "reload":
        if not url:
            print("not running")
            return 1
        pid = st and st.get("pid")
        api("POST", "/api/reload", {}, url)
        for _ in range(100):  # the same pid, a new server.json once it serves again
            time.sleep(0.1)
            st2 = _read_json(os.path.join(home(), "server.json")) or {}
            if st2.get("pid") == pid and st2.get("started", 0) > (st or {}).get("started", 0) and running():
                print(f"reloaded: {public_url(url)}")
                return 0
        print("reload asked; the server has not come back yet (see ~/.perflab/server/server.log)")
        return 1
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
    print(public_url(url))
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
