"""`perflab worker`: runs a coordinator's jobs of this machine's testbed (doc/remote-workers.md; the coordinator's side
is perflab.remote and perflab.server).

  perflab worker [--server <url>] [--token-file <file>] [--name <name>] [--testbed <name>] [--once]

It claims the next `ab run` job of its testbed from the coordinator's queue, and while the job lives sends a heartbeat
every 10 s (which renews its lease, carries the job's transcript, and brings back pause and cancel). For the job it
- checks out the harness (the coordinator's project repository at its HEAD, with its uncommitted diff) into a worktree
  of its own, and each build's commit into a worktree per commit, from a mirror per repository: fetched from the
  repository's remotes, else from a git bundle the coordinator makes;
- maps the spec's paths (the coordinator's repository and home, and worker.toml's [paths]), and its `jvm` and the
  builds' JAVA_HOME by their JDK's release file (worker.toml's [jdks], the mapped path, SDKMAN's candidates,
  /Library/Java), and fails the job, before anything runs, on a JDK or path it does not have;
- downloads the campaign's finished cells (their results), so `ab run` resumes where the coordinator's index is;
- runs `ab run` on the mapped spec with the harness's perflab, and uploads each cell when it finishes, each voided
  attempt and the campaign's top-level files, and at the end all of them.

State is in ~/.perflab/worker (PERFLAB_WORKER_HOME): repos/<key> (mirrors), harness/<key>, src/<key>/<commit>,
jobs/<id>/. Settings in <home>/worker.toml, every one optional, the command line's options over them:

  server = "http://127.0.0.1:8690/"        # the coordinator (through `ssh -R 8690:127.0.0.1:8690 <this machine>`)
  token-file = "~/.perflab/worker/token"   # the coordinator's ~/.perflab/server/token, copied
  name = "m4-laptop"                       # default: the host name
  testbed = "m4"                           # default: perflab.testbed's name for this machine
  [jdks]                                   # a coordinator's java (its path, or its JAVA_RUNTIME_VERSION) -> this machine's
  "/Users/me/jdks/jdk26-patched/bin/java" = "/Users/me/jdk26/bin/java"
  [paths]                                  # a coordinator's path prefix -> this machine's
  "/Users/me/code/corpora" = "/Users/me/corpora"
  [env]                                    # variables for every job: what a lab reads beyond its spec
  SCALA3_BENCHMARKS = "~/.perflab/worker/scala3-benchmarks"
"""
import argparse, glob, io, json, os, re, shutil, signal, socket, subprocess, sys, tarfile, tempfile, threading, time, tomllib
import urllib.error, urllib.parse, urllib.request

from . import ab, config, control, remote, testbed, transcript

HOME_ENV = "PERFLAB_WORKER_HOME"
BEAT = float(os.environ.get("PERFLAB_WORKER_BEAT") or 10)  # seconds between heartbeats (the coordinator's lease is server.LEASE, 90 s)
GRACE, KILL_AFTER = 10.0, 20.0  # as the coordinator's own worker: cancel, then SIGTERM, then SIGKILL
SYNC = ".worker-sync.json"  # in a campaign on the worker: each unit's stamp as last uploaded
GIT_ENV = {"GIT_TERMINAL_PROMPT": "0", "GIT_SSH_COMMAND": "ssh -o BatchMode=yes"}  # never wait for a password


def home():
    return os.path.abspath(os.path.expanduser(os.environ.get(HOME_ENV) or "~/.perflab/worker"))


def settings(h):
    try:
        with open(os.path.join(h, "worker.toml"), "rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        return {}


class Lost(Exception):
    """The coordinator gave the job back to the queue, or to another worker."""


class Cancelled(Exception):
    pass


class Client:
    def __init__(self, url, token, name):
        self.url, self.token, self.name = url.rstrip("/"), token, name

    def post(self, path, body=None, timeout=60, raw=False, data=None, query=None):
        q = "?" + urllib.parse.urlencode(query) if query else ""
        headers = {"X-Perflab-Token": self.token}
        if data is None:
            data = json.dumps({"worker": self.name, **(body or {})}).encode()
            headers["Content-Type"] = "application/json"
        else:
            headers["Content-Type"] = "application/gzip"
            headers["Content-Length"] = str(os.fstat(data.fileno()).st_size)
        req = urllib.request.Request(self.url + path + q, data=data, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                out = r.read()
        except urllib.error.HTTPError as e:
            try:
                msg = json.loads(e.read()).get("error")
            except ValueError:
                msg = e.reason
            if e.code == 409:
                raise Lost(msg) from None
            raise RuntimeError(f"coordinator: {e.code} {msg}") from None
        return out if raw else json.loads(out or b"{}")


def git(d, *args, check=True, input=None):
    p = subprocess.run(["git", "-C", d, *args], capture_output=True, text=True, input=input, env={**os.environ, **GIT_ENV})
    if check and p.returncode:
        raise RuntimeError(f"git {' '.join(args)} in {d}: {(p.stderr or p.stdout).strip()}")
    return p


def has(repo, sha):
    return git(repo, "cat-file", "-e", f"{sha}^{{commit}}", check=False).returncode == 0


def urls(rs):
    """The remotes' URLs to fetch from, an https one beside each GitHub ssh one (a worker may have no keys)."""
    out = []
    for u in rs.values():
        out.append(u)
        m = re.fullmatch(r"(?:ssh://)?git@github\.com[:/](.+?)(?:\.git)?/?", u)
        if m:
            out.append(f"https://github.com/{m.group(1)}.git")
    return list(dict.fromkeys(out))


def bundle_prerequisites(path):
    """The commits a bundle needs its receiver to have (its header's `-<sha>` lines)."""
    out = []
    with open(path, "rb") as f:
        f.readline()  # "# v2 git bundle"
        for line in f:
            line = line.decode(errors="replace").rstrip("\n")
            if not line:
                break
            if line.startswith("-"):
                out.append(line[1:].split()[0])
    return out


class Job:
    """One claimed job, run to its end."""

    def __init__(self, w, payload):
        self.w, self.p = w, payload
        self.id = payload["job"]
        self.dir = os.path.join(w.home, "jobs", str(self.id))
        os.makedirs(self.dir, exist_ok=True)
        self.transcript = os.path.join(self.dir, "transcript.txt")
        self.ctl = os.path.join(self.dir, "control")
        for f in (self.ctl, control.ack_path(self.ctl)):
            control.write(f, None)
        open(self.transcript, "w").close()
        self.sent, self.word, self.lost, self.proc = 0, None, None, None
        self.java_home = None
        self.hold = False  # the worker's own pause at a cell boundary, to upload while nothing is measured
        self.ctl_lock = threading.Lock()
        self.stop = threading.Event()

    def say(self, msg):
        with open(self.transcript, "a") as f:
            f.write(msg + "\n")
        print(f"[worker] job {self.id}: {msg}", flush=True)

    # the heartbeat: lease, transcript, control

    def chunk(self):
        with open(self.transcript, "rb") as f:
            f.seek(self.sent)
            data = f.read()
        return data

    def beat(self, final_rc=None):
        data = self.chunk()
        body = {"transcript": data.decode(errors="replace"), "paused": control.acked(self.ctl) and self.word == control.PAUSE}
        if final_rc is not None:
            self.w.client.post(f"/api/workers/jobs/{self.id}/finish", {**body, "rc": final_rc})
            self.sent += len(data)
            return
        r = self.w.client.post(f"/api/workers/jobs/{self.id}/heartbeat", body)
        self.sent += len(data)
        if r.get("control") != self.word:
            self.word = r.get("control")
            self.apply()

    def apply(self):
        """The control file: the coordinator's word, else the worker's own pause while it uploads."""
        with self.ctl_lock:
            control.write(self.ctl, self.word or (control.PAUSE if self.hold else None))

    def beats(self):
        while not self.stop.wait(BEAT):
            try:
                self.beat()
            except Lost as e:
                self.lost = str(e)
                self.say(f"[perflab] the coordinator took the job back: {e}")
                self.kill(signal.SIGTERM)
                return
            except (OSError, RuntimeError) as e:  # the coordinator is away for a moment; the lease outlasts a few
                print(f"[worker] heartbeat failed: {e}", flush=True)

    def kill(self, sig):
        if self.proc and self.proc.poll() is None:
            try:
                os.killpg(self.proc.pid, sig)
            except (ProcessLookupError, PermissionError):
                pass

    def checkpoint(self):
        if self.lost:
            raise Lost(self.lost)
        if self.word == control.CANCEL:
            raise Cancelled()

    # sources

    def repo(self, key):
        d = os.path.join(self.w.home, "repos", key)
        if not os.path.isdir(os.path.join(d, ".git")):
            os.makedirs(d, exist_ok=True)
            git(d, "init", "-q")
        return d

    def fetch(self, repo, src, name):
        """`src`'s commit in `repo`: from its remotes, else from the coordinator's bundle."""
        sha = src["commit"]
        if has(repo, sha):
            return
        for u in urls(src["remotes"]):
            self.say(f"[perflab] fetching {sha[:10]} ({name}) from {u}")
            if git(repo, "fetch", "-q", "--no-tags", u, sha, check=False).returncode == 0 and has(repo, sha):
                git(repo, "update-ref", f"refs/perflab/keep/{sha}", sha)
                return
            self.checkpoint()
        for full in (False, True):
            self.say(f"[perflab] {sha[:10]} ({name}) from the coordinator's bundle" + (" (whole history)" if full else ""))
            data = self.w.client.post(f"/api/workers/jobs/{self.id}/bundle", {"source": name, "full": full}, timeout=3600, raw=True)
            fd, b = tempfile.mkstemp(suffix=".bundle", dir=self.dir)
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            try:
                missing = [c for c in bundle_prerequisites(b) if not has(repo, c)]
                for c in list(missing):
                    for u in urls(src["remotes"]):
                        if git(repo, "fetch", "-q", "--no-tags", u, c, check=False).returncode == 0 and has(repo, c):
                            git(repo, "update-ref", f"refs/perflab/keep/{c}", c)
                            missing.remove(c)
                            break
                if missing:
                    continue  # the whole history, then
                git(repo, "fetch", "-q", "--no-tags", b, "refs/perflab/bundle/*:refs/perflab/keep/*")
            finally:
                os.unlink(b)
            if has(repo, sha):
                return
        raise RuntimeError(f"could not get {sha} ({name})")

    def harness(self):
        """The coordinator's project, here: its repository's worktree at its commit with its diff; the project's path."""
        h = self.p["harness"]
        repo = self.repo(h["key"])
        self.fetch(repo, h, "harness")
        wt = os.path.join(self.w.home, "harness", h["key"])
        if not os.path.exists(os.path.join(wt, ".git")):
            git(repo, "worktree", "prune")
            git(repo, "worktree", "add", "-q", "--detach", wt, h["commit"])
        else:  # the last job's diff undone; what git ignores (the lab's corpora, its campaigns) stays
            git(wt, "reset", "-q", "--hard")
            git(wt, "clean", "-fdq")
            git(wt, "checkout", "-q", "--detach", h["commit"])
        if h.get("diff"):
            git(wt, "apply", "--binary", "--whitespace=nowarn", "-", input=h["diff"])
        self.say(f"[perflab] harness: {h['commit'][:10]}" + (" with the coordinator's uncommitted changes" if h.get("diff") else "") + f" in {wt}")
        return wt, os.path.normpath(os.path.join(wt, h["rel"]))

    def checkout(self, v, src):
        repo = self.repo(src["key"])
        self.fetch(repo, src, v)
        wt = os.path.join(self.w.home, "src", src["key"], src["commit"][:12])
        if not os.path.exists(os.path.join(wt, ".git")):
            git(repo, "worktree", "prune")
            git(repo, "worktree", "add", "-q", "--detach", wt, src["commit"])
        elif git(wt, "rev-parse", "HEAD").stdout.strip() != src["commit"]:
            git(wt, "checkout", "-q", "--detach", "--force", src["commit"])
        return wt

    def same_jdk(self, d, harness_wt):
        """A worktree last built with another JDK loses its build outputs (an incremental build would keep class files
        of that JDK's version): what git ignores, but for the harness the lab's out/ (its campaigns and corpora)."""
        state = os.path.join(self.w.home, "jdk-of", re.sub(r"[^A-Za-z0-9_.-]", "_", os.path.relpath(d, self.w.home)))
        want = self.java_home or ""
        try:
            had = open(state).read()
        except OSError:
            had = None
        if had is not None and had != want:
            if d == harness_wt:
                out = os.path.join(os.path.normpath(os.path.join(d, self.p["harness"]["rel"])), "out")
                git(d, "clean", "-fdXq", "-e", "!" + os.path.relpath(out, d) + "/")
            else:
                git(d, "clean", "-fdxq")
            self.say(f"[perflab] {d}: built with another JDK last ({had or 'the default'}); its build outputs removed")
        os.makedirs(os.path.dirname(state), exist_ok=True)
        with open(state, "w") as f:
            f.write(want)

    # paths and JDKs

    def mapper(self, harness_wt):
        table = {self.p["harness"]["top"]: harness_wt, self.p["home"]: os.path.expanduser("~")}
        table.update({os.path.expanduser(k): os.path.expanduser(v) for k, v in (self.w.cfg.get("paths") or {}).items()})
        keys = sorted(table, key=len, reverse=True)
        pat = re.compile("(" + "|".join(map(re.escape, keys)) + r")(?=/|$|[^\w.-])")
        return lambda s: pat.sub(lambda m: table[m.group(1)], s)

    def jdk(self, want, mapped):
        """This machine's java for the coordinator's (remote.jdk), or RuntimeError saying what to install."""
        rel = want.get("release") or {}
        version, vendor = rel.get("JAVA_RUNTIME_VERSION") or rel.get("JAVA_VERSION"), rel.get("IMPLEMENTOR")
        jdks = self.w.cfg.get("jdks") or {}
        named = jdks.get(want["path"]) or jdks.get(want.get("home")) or (version and jdks.get(version))
        if named:
            named = os.path.expanduser(named)
            java = named if os.path.basename(named) == "java" else os.path.join(named, "bin", "java")
            if not os.path.exists(java):
                raise RuntimeError(f"worker.toml [jdks] maps {want['path']} to {java}, which is not there")
            return java

        def same(java):
            r = remote.jdk(java)["release"]
            return os.path.exists(java) and (r.get("JAVA_RUNTIME_VERSION") or r.get("JAVA_VERSION")) == version and r.get("IMPLEMENTOR") == vendor
        homes = [os.path.dirname(os.path.dirname(mapped))]
        homes += sorted(glob.glob(os.path.expanduser("~/.sdkman/candidates/java/*")))
        homes += sorted(glob.glob("/Library/Java/JavaVirtualMachines/*/Contents/Home"))
        for h in homes:
            java = os.path.join(h, "bin", "java")
            if version and same(java):
                return java
        sdk = re.search(r"/candidates/java/([^/]+)/", want["path"])
        raise RuntimeError(f"no JDK {version or '?'} ({vendor or '?'}) for {want['path']}: "
                           + (f"`sdk install java {sdk.group(1)}`, or " if sdk else "install it, or ")
                           + f"map it in {os.path.join(self.w.home, 'worker.toml')} [jdks]")

    def spec(self, map_, checkouts):
        """The coordinator's spec with this machine's paths, and the paths it names that are not here."""
        def walk(x, key=None):
            if isinstance(x, str):
                return x if key in ("name", "testbed", "description", "historical") else map_(x)
            if isinstance(x, list):
                return x if key == "description" else [walk(y) for y in x]
            if isinstance(x, dict):
                return {k: x[k] if k in ("variantDescriptions",) else walk(v, k) for k, v in x.items()}
            return x
        s = walk(self.p["spec"])
        for v, wt in checkouts.items():
            s["builds"][v] = {**s["builds"][v], "checkout": wt}
        if self.p.get("jvm"):
            s["jvm"] = self.jdk(self.p["jvm"], map_(self.p["jvm"]["path"]))
        missing = {}  # the coordinator's path -> where it maps to here, for the inputs this machine lacks
        for path in remote.input_paths(self.p["spec"]):
            here = map_(path)
            if not os.path.exists(here) and not os.path.isdir(os.path.dirname(here)):
                missing[path] = here
        return s, missing

    def copy_inputs(self, missing):
        """The inputs the spec names that this machine lacks (a lab's corpora, jars of a build tool's cache), copied
        from the coordinator to where their paths map; those it could not copy."""
        left = []
        for theirs, here in sorted(missing.items()):
            try:
                data = self.w.client.post(f"/api/workers/jobs/{self.id}/input", {"path": theirs}, timeout=3600, raw=True)
            except RuntimeError as e:
                left.append(f"{here} ({e})")
                continue
            os.makedirs(os.path.dirname(here), exist_ok=True)
            tmp = tempfile.mkdtemp(prefix=".incoming-", dir=os.path.dirname(here))
            try:
                with tarfile.open(fileobj=io.BytesIO(data)) as tar:
                    tar.extractall(tmp, filter="data")
                os.replace(os.path.join(tmp, os.path.basename(theirs)), here)
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
            self.say(f"[perflab] copied {theirs} from the coordinator ({len(data) / 1e6:.1f} MB compressed) to {here}")
            self.checkpoint()
        return left

    # results

    def units(self, camp, skip=None):
        """{unit: directory or file list} of the campaign: cells, voided attempts, and "." (its top-level files)."""
        out = {}
        for c in sorted(os.listdir(camp)) if os.path.isdir(camp) else []:
            cd = os.path.join(camp, c)
            if c.startswith(".") or not os.path.isdir(cd):
                continue
            for v in sorted(os.listdir(cd)):
                for r in sorted(os.listdir(os.path.join(cd, v))) if os.path.isdir(os.path.join(cd, v)) else []:
                    if r.isdigit() and os.path.isdir(os.path.join(cd, v, r)):
                        out[f"{c}/{v}/{r}"] = os.path.join(cd, v, r)
        for vd in glob.glob(os.path.join(camp, ab.VOID_DIR, "*", "*", "*")):
            if os.path.isdir(vd):
                out[os.path.relpath(vd, camp)] = vd
        out["."] = camp
        return {u: d for u, d in out.items() if u != skip}

    @staticmethod
    def files(unit, d):
        if unit == ".":
            return sorted(f for f in os.listdir(d) if not f.startswith(".") and f not in remote.OWN and os.path.isfile(os.path.join(d, f)))
        return sorted(os.path.relpath(os.path.join(r, f), d) for r, _, fs in os.walk(d) for f in fs)

    def stamp(self, unit, d):
        st = []
        for f in self.files(unit, d):
            try:
                s = os.stat(os.path.join(d, f))
                st.append((f, s.st_size, s.st_mtime_ns))
            except OSError:
                pass
        return json.dumps(st)

    def sync(self, camp, running=None):
        """Uploads every unit that changed since it was last uploaded, but the cell being run."""
        f = os.path.join(camp, SYNC)
        synced = _read_json(f) or {}
        for unit, d in self.units(camp, running).items():
            st = self.stamp(unit, d)
            if synced.get(unit) == st or st == "[]":
                continue
            with tempfile.TemporaryFile(dir=self.dir) as tf:
                with tarfile.open(fileobj=tf, mode="w:gz") as tar:
                    for name in self.files(unit, d):
                        tar.add(os.path.join(d, name), name, recursive=False)
                tf.flush()
                tf.seek(0)
                self.w.client.post(f"/api/workers/jobs/{self.id}/upload", data=tf, timeout=3600,
                                   query={"worker": self.w.name, "unit": unit})
            synced[unit] = st
            with open(f + ".tmp", "w") as out:
                json.dump(synced, out)
            os.replace(f + ".tmp", f)
            if unit != ".":
                self.say(f"[perflab] uploaded {unit}")

    def resume_from_coordinator(self, camp):
        """The coordinator's finished cells, here: the results of those this campaign lacks; a cell this worker uploaded
        that the coordinator no longer has (voided there) is set aside, so that it is measured again."""
        data = self.w.client.post(f"/api/workers/jobs/{self.id}/cells", timeout=600, raw=True)
        os.makedirs(camp, exist_ok=True)
        f = os.path.join(camp, SYNC)
        synced = _read_json(f) or {}
        theirs = {}
        with tarfile.open(fileobj=io.BytesIO(data)) as tar:
            for m in tar.getmembers():
                theirs.setdefault(os.path.dirname(m.name), []).append(m)
            for unit, members in theirs.items():
                if not remote.CELL_UNIT.fullmatch(unit) or ab.done(os.path.join(camp, unit)):
                    continue
                tar.extractall(camp, members=members, filter="data")
                synced[unit] = self.stamp(unit, os.path.join(camp, unit))
        for unit, d in self.units(camp).items():
            if remote.CELL_UNIT.fullmatch(unit) and unit not in theirs and ab.done(d) and unit in synced:
                aside = os.path.join(camp, ".worker-void", unit.replace("/", "-") + time.strftime("-%Y%m%d-%H%M%S"))
                os.makedirs(os.path.dirname(aside), exist_ok=True)
                os.replace(d, aside)
                synced.pop(unit)
                self.say(f"[perflab] {unit}: the coordinator no longer has it (voided?); measured again")
        with open(f, "w") as out:
            json.dump(synced, out)
        self.say(f"[perflab] {sum(1 for u in theirs if remote.CELL_UNIT.fullmatch(u))} finished cells on the coordinator")

    # the job

    def run(self):
        beats = threading.Thread(target=self.beats, daemon=True, name=f"perflab-worker-beat-{self.id}")
        beats.start()
        rc, camp = 1, None
        try:
            self.say(f"[perflab] {self.w.name} (testbed {self.w.testbed}) runs job {self.id}: {' '.join(self.p['argv'])}")
            wt, project = self.harness()
            self.checkpoint()
            checkouts = {}
            for v, src in self.p["sources"].items():
                checkouts[v] = self.checkout(v, src)
                self.say(f"[perflab] build {v}: {src['commit'][:10]} in {checkouts[v]}")
                self.checkpoint()
            map_ = self.mapper(wt)
            spec, missing = self.spec(map_, checkouts)
            if self.p.get("javaHome"):  # the builds' JDK, as the coordinator's: a build's class files are of its version
                self.java_home = os.path.dirname(os.path.dirname(self.jdk(self.p["javaHome"], map_(self.p["javaHome"]["path"]))))
                self.say(f"[perflab] builds with JAVA_HOME={self.java_home}")
            for d in [wt, *checkouts.values()]:
                self.same_jdk(d, wt)
            left = self.copy_inputs(missing)
            if left:
                raise RuntimeError("the spec names paths this machine does not have and the coordinator could not send "
                                   "(after mapping the coordinator's repository and home; worker.toml [paths] maps others): "
                                   + ", ".join(left))
            cfg = config.find(project)
            camp = os.path.join(cfg.campaigns, self.p["campaign"])
            self.resume_from_coordinator(camp)
            spec_path = os.path.join(self.dir, "spec.json")
            with open(spec_path, "w") as f:
                json.dump(spec, f, indent=2)
            rc = self.execute(project, wt, spec_path, camp)
        except Cancelled:
            self.say("[perflab] cancelled by the server")
            rc = control.CANCELLED
        except Lost:
            rc = None
        except Exception as e:
            self.say(f"[perflab] failed: {type(e).__name__}: {e}" if not isinstance(e, RuntimeError) else f"[perflab] failed: {e}")
            rc = 1
        finally:
            self.stop.set()
            beats.join(BEAT + 30)
        if rc is None or self.lost:
            return
        try:
            if camp:
                self.sync(camp)
        except (OSError, RuntimeError) as e:
            self.say(f"[perflab] uploading the results failed: {e}")
            rc = rc or 1
        for _ in range(30):  # the result is the point: keep trying through a short absence of the coordinator
            try:
                self.beat(final_rc=rc)
                return
            except Lost:
                return
            except (OSError, RuntimeError) as e:
                print(f"[worker] finish failed ({e}); retrying", flush=True)
                time.sleep(10)

    def execute(self, project, wt, spec_path, camp):
        argv = [spec_path if a.endswith(".json") else a for a in self.p["argv"] if a != "--local"]
        env = {k: v for k, v in os.environ.items() if not k.startswith("PERFLAB_")}
        src = os.path.join(wt, "python", "src")
        if os.path.isdir(os.path.join(src, "perflab")):  # the coordinator's perflab, as its harness has it
            env["PYTHONPATH"] = os.pathsep.join(filter(None, [src, os.environ.get("PYTHONPATH")]))
        env.update({"PERFLAB_LOCAL": "1", control.ENV: self.ctl, "PERFLAB_SPEC_VERSION": self.p["specVersion"],
                    testbed.ENV: self.w.testbed, "PYTHONUNBUFFERED": "1",
                    # a perflab server of this machine's own is not the coordinator: the job never registers with it
                    "PERFLAB_SERVER_HOME": os.path.join(self.w.home, "server")})
        env.update({k: os.path.expanduser(str(v)) for k, v in (self.w.cfg.get("env") or {}).items()})
        if self.java_home:
            env["JAVA_HOME"] = self.java_home
            env["PATH"] = os.pathsep.join([os.path.join(self.java_home, "bin"), env.get("PATH", "")])
        cmd = [sys.executable, "-m", "perflab", "--transcript", self.transcript, *argv]
        self.say(f"[perflab] running {' '.join(argv)} in {project}")
        with open(os.path.join(self.dir, "output.log"), "ab") as out:
            self.proc = subprocess.Popen(cmd, cwd=project, env=env, stdin=subprocess.DEVNULL, stdout=out,
                                         stderr=subprocess.STDOUT, start_new_session=True)
        running_f = os.path.join(os.path.dirname(camp), ab.RUNNING_NAME)
        term_at, cancel_at, seen, pending = None, None, None, False
        while self.proc.poll() is None:
            time.sleep(1)
            if self.lost:
                break
            now = time.time()
            if self.word == control.CANCEL:
                cancel_at = cancel_at or now
                if term_at is None and now - cancel_at >= GRACE:
                    self.kill(signal.SIGTERM)
                    term_at = now
                elif term_at and now - term_at >= KILL_AFTER:
                    self.kill(signal.SIGKILL)
                    term_at = float("inf")
            # a cell ended: its upload waits for the next cell boundary, where the job pauses (its checkpoint) while it
            # goes, so that nothing is measured meanwhile; the load gate's quiet period then follows it
            r = _read_json(running_f) or {}
            now_running = (r.get("cell"), r.get("started")) if r.get("campaign") == self.p["campaign"] else None
            if now_running != seen:
                pending = pending or seen is not None
                seen = now_running
            if pending and not self.hold and self.word is None:
                self.hold = True
                self.apply()
            elif self.hold and control.acked(self.ctl):
                try:
                    self.sync(camp)
                    pending = False
                except (OSError, RuntimeError) as e:
                    print(f"[worker] upload failed ({e}); at the next cell boundary", flush=True)
                self.hold = False
                self.apply()
        rc = self.proc.wait()
        return control.CANCELLED if self.word == control.CANCEL and rc else rc


def _read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


class Worker:
    def __init__(self, url, token, name, testbed_name, h, cfg):
        self.client = Client(url, token, name)
        self.name, self.testbed, self.home, self.cfg = name, testbed_name, h, cfg

    def claim(self):
        tb = {**testbed.local(), "name": self.testbed}
        return self.client.post("/api/workers/claim", {"testbed": tb}, timeout=300).get("job")

    def loop(self, once=False, poll=10.0):
        print(f"[worker] {self.name} (testbed {self.testbed}) polling {self.client.url}", flush=True)
        while True:
            try:
                job = self.claim()
            except (OSError, RuntimeError, Lost) as e:
                print(f"[worker] claim failed: {e}", flush=True)
                job = None
            if job:
                Job(self, job).run()
            elif once:
                return 0
            if once and job:
                return 0
            if not job:
                time.sleep(poll)


def main(argv):
    ap = argparse.ArgumentParser(prog="perflab worker", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--server", help="the coordinator's URL (worker.toml: server)")
    ap.add_argument("--token-file", help="a file holding the coordinator's token (worker.toml: token-file; or PERFLAB_WORKER_TOKEN)")
    ap.add_argument("--name", help="this worker's name on the coordinator (default: the host name)")
    ap.add_argument("--testbed", help="the testbed it runs jobs of (default: this machine's, perflab.testbed)")
    ap.add_argument("--once", action="store_true", help="run one job if there is one, then exit")
    ap.add_argument("--poll", type=float, default=10.0, help="seconds between claims while the queue has nothing (default 10)")
    x = ap.parse_args(argv)
    h = home()
    os.makedirs(h, exist_ok=True)
    cfg = settings(h)
    url = x.server or cfg.get("server") or "http://127.0.0.1:8690/"
    tok = os.environ.get("PERFLAB_WORKER_TOKEN")
    tf = x.token_file or cfg.get("token-file") or os.path.join(h, "token")
    if not tok:
        try:
            tok = open(os.path.expanduser(tf)).read().strip()
        except OSError:
            sys.exit(f"perflab worker: no token: copy the coordinator's ~/.perflab/server/token to {tf} (or --token-file)")
    name = x.name or cfg.get("name") or socket.gethostname().split(".")[0]
    tb = x.testbed or cfg.get("testbed") or testbed.name()
    os.environ[testbed.ENV] = tb  # what this process's perflab (ab.done, of a campaign) takes this machine to be
    try:
        return Worker(url, tok, name, tb, h, cfg).loop(x.once, x.poll)
    except KeyboardInterrupt:
        return 130
