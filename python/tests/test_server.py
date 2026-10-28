import json, os, re, shutil, socket, subprocess, sys, tempfile, threading, time, unittest, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src")
sys.path.insert(0, SRC)
from perflab import control, server, serverui, storage  # noqa: E402


def project(toml='[build]\njmh = "x"\n'):
    d = os.path.realpath(tempfile.mkdtemp())
    with open(os.path.join(d, "perflab.toml"), "w") as f:
        f.write(toml)
    return d


def wait_for(cond, timeout=20, what="condition"):
    end = time.time() + timeout
    while time.time() < end:
        v = cond()
        if v:
            return v
        time.sleep(0.1)
    raise AssertionError(f"timed out waiting for {what}")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class QueueTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.q = server.Queue(os.path.join(self.home, "jobs.sqlite"))
        self.p = self.q.register(project())

    def submit(self, *argv, priority=0):
        return self.q.submit(self.p["id"], list(argv), "/", priority=priority)

    def ids(self):
        return [j["id"] for j in self.q.queued()]

    def test_project_registers_once_with_its_paths(self):
        again = self.q.register(self.p["root"])
        self.assertEqual(again["id"], self.p["id"])
        self.assertEqual(len(self.q.projects()), 1)
        self.assertTrue(self.p["campaigns"].endswith("out/perflab/ab"))
        self.assertEqual(self.p["index"], f"/p/{self.p['id']}/ab/index.html")
        with self.assertRaises(ValueError):
            self.q.register(tempfile.mkdtemp())

    def test_order_priority_and_moves(self):
        a, b, c = self.submit("a"), self.submit("b"), self.submit("c")
        self.assertEqual(self.ids(), [a["id"], b["id"], c["id"]])
        self.q.move(c["id"], -1)
        self.assertEqual(self.ids(), [a["id"], c["id"], b["id"]])
        self.q.move(a["id"], -1)  # already first
        self.q.move(a["id"], 1)
        self.assertEqual(self.ids(), [c["id"], a["id"], b["id"]])
        self.q.set_priority(b["id"], 5)
        self.assertEqual(self.ids(), [b["id"], c["id"], a["id"]])
        self.q.move(c["id"], -1)  # passing a job of higher priority takes its priority
        self.assertEqual(self.ids(), [c["id"], b["id"], a["id"]])
        self.assertEqual(self.q.get(c["id"])["priority"], 5)
        hi = self.submit("hi", priority=9)
        self.assertEqual(self.ids()[0], hi["id"])

    def test_state_transitions(self):
        a, b = self.submit("a"), self.submit("b")
        j = self.q.claim()
        self.assertEqual((j["id"], j["state"]), (a["id"], "running"))
        self.assertIsNone(self.q.claim())  # one at a time
        self.q.transition(a["id"], "paused")
        self.q.transition(a["id"], "running")
        with self.assertRaises(server.Conflict):
            self.q.transition(a["id"], "queued")
        with self.assertRaises(server.Conflict):
            self.q.set_priority(a["id"], 3)
        self.q.transition(a["id"], "done", rc=0)
        self.assertIsNotNone(self.q.get(a["id"])["ended"])
        with self.assertRaises(server.Conflict):
            self.q.transition(a["id"], "running")
        self.assertEqual(server.cancel(self.q, b["id"])["state"], "cancelled")
        with self.assertRaises(server.Conflict):
            server.pause(self.q, b["id"])
        self.assertIsNone(self.q.claim())
        self.assertEqual([j["state"] for j in self.q.jobs()], ["cancelled", "done"])

    def test_pause_and_cancel_of_a_running_job_go_through_its_control_file(self):
        a = self.submit("a")
        self.q.claim()
        ctl = os.path.join(a["dir"], "control")
        self.assertEqual(server.pause(self.q, a["id"])["control"], "pause")
        self.assertEqual(control.read(ctl), "pause")
        self.assertIsNone(server.resume(self.q, a["id"])["control"])
        j = server.cancel(self.q, a["id"])
        self.assertEqual((j["state"], control.read(ctl)), ("running", "cancel"))
        self.assertIsNotNone(j["cancel_requested"])


class ControlTest(unittest.TestCase):
    def setUp(self):
        self.ctl = os.path.join(tempfile.mkdtemp(), "control")
        os.environ[control.ENV] = self.ctl
        os.environ[control.POLL_ENV] = "0.05"

    def tearDown(self):
        os.environ.pop(control.ENV, None)
        os.environ.pop(control.POLL_ENV, None)

    def test_nothing_without_a_control_file_or_variable(self):
        control.checkpoint()
        os.environ.pop(control.ENV)
        control.write(self.ctl, "cancel")
        control.checkpoint()  # PERFLAB_CONTROL unset: a terminal run

    def test_pause_blocks_and_acks_until_cleared(self):
        control.write(self.ctl, "pause")
        t = threading.Thread(target=control.checkpoint)
        t.start()
        wait_for(lambda: control.acked(self.ctl), what="the ack")
        self.assertTrue(t.is_alive())
        control.write(self.ctl, None)
        t.join(5)
        self.assertFalse(t.is_alive())
        self.assertFalse(os.path.exists(self.ctl + ".ack"))

    def test_cancel_exits(self):
        control.write(self.ctl, "cancel")
        with self.assertRaises(SystemExit):
            control.checkpoint()


class ServerTest(unittest.TestCase):
    """The server in this process on an ephemeral port, running perflab_fakejob as its jobs."""

    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.srv = server.Server(self.home, port=0, grace=1).start()
        self.root = project()
        self.env = {"PYTHONPATH": os.pathsep.join([HERE, os.path.abspath(SRC)]), control.POLL_ENV: "0.1"}

    def tearDown(self):
        for j in self.srv.q.jobs():
            if j["pid"] and j["state"] in server.ACTIVE:
                server.Worker._signal(j["pid"], 9)
        self.srv.stop()

    def call(self, method, path, body=None, headers=None):
        h = {"Content-Type": "application/json", "X-Perflab-Token": self.srv.token, **(headers or {})}
        req = urllib.request.Request(self.srv.url.rstrip("/") + path, method=method, headers=h,
                                     data=json.dumps(body).encode() if body is not None else None)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                text = r.read().decode()
                return r.status, (json.loads(text) if "json" in r.headers.get("Content-Type", "") else text)
        except urllib.error.HTTPError as e:
            body = e.read()
            return e.code, json.loads(body) if "json" in e.headers.get("Content-Type", "") else body.decode()

    def submit(self, *argv, priority=0):
        code, j = self.call("POST", "/api/jobs", {"argv": list(argv), "cwd": self.root, "env": self.env,
                                                  "module": "perflab_fakejob", "priority": priority})
        self.assertEqual(code, 201, j)
        return j

    def job(self, jid):
        return self.call("GET", f"/api/jobs/{jid}")[1]

    def until(self, jid, state, timeout=20):
        return wait_for(lambda: (lambda j: j if j["state"] == state else None)(self.job(jid)), timeout, f"job {jid} {state}")

    def transcript(self, jid):
        return self.call("GET", f"/api/jobs/{jid}/transcript")[1]

    def test_pause_resume_cancel_end_to_end(self):
        a = self.submit("cells", "200", "0.1")
        self.until(a["id"], "running")
        b = self.submit("cells", "2", "0.05")
        self.assertEqual(b["position"], 1)
        wait_for(lambda: "cell 2" in self.transcript(a["id"]), what="cells")
        self.assertEqual(self.call("POST", f"/api/jobs/{a['id']}/pause")[0], 200)
        self.until(a["id"], "paused")
        self.assertIn("paused by the server", self.transcript(a["id"]))
        n = self.transcript(a["id"]).count("cell ")
        time.sleep(0.5)
        self.assertEqual(self.transcript(a["id"]).count("cell "), n)  # no cells while paused
        self.assertEqual(self.job(b["id"])["state"], "queued")  # and nothing else runs
        self.call("POST", f"/api/jobs/{a['id']}/resume")
        self.until(a["id"], "running")
        wait_for(lambda: self.transcript(a["id"]).count("cell ") > n + 1, what="more cells")
        self.call("POST", f"/api/jobs/{a['id']}/cancel")
        j = self.until(a["id"], "cancelled")
        self.assertNotIn("finished", self.transcript(a["id"]))
        self.assertIn("cancelled by the server", self.transcript(a["id"]))
        self.assertIsNotNone(j["ended"])
        # then the next job runs, to the end
        j = self.until(b["id"], "done")
        self.assertEqual(j["rc"], 0)
        self.assertIn("finished", self.transcript(b["id"]))
        self.assertEqual(self.call("GET", f"/api/jobs/{b['id']}/transcript?tail=1")[1], "finished\n")
        self.assertNotIn("env", j)
        self.assertIn("PYTHONPATH", j["envKeys"])

    def test_cancel_signals_a_job_between_checkpoints_and_a_failure_is_failed(self):
        a = self.submit("stubborn", "1", "60")
        self.until(a["id"], "running")
        wait_for(lambda: "cell 0" in self.transcript(a["id"]), what="the cell")
        t = time.time()
        self.call("POST", f"/api/jobs/{a['id']}/cancel")
        self.until(a["id"], "cancelled")
        self.assertLess(time.time() - t, 15)  # SIGTERM after the 1 s grace, not the 60 s sleep
        bad = self.submit("cells", "1", "0", "3")
        j = self.until(bad["id"], "failed")
        self.assertEqual(j["rc"], 3)

    def test_queue_api_reorders_and_cancels_queued_jobs(self):
        blocker = self.submit("cells", "200", "0.1")
        self.until(blocker["id"], "running")
        a, b = self.submit("cells", "1", "0"), self.submit("cells", "1", "0")
        code, j = self.call("POST", f"/api/jobs/{b['id']}/move", {"by": -1})
        self.assertEqual(code, 200)
        queued = [j["id"] for j in self.call("GET", "/api/jobs")[1] if j["state"] == "queued"]
        self.assertEqual(queued, [b["id"], a["id"]])
        self.assertEqual(self.call("POST", f"/api/jobs/{a['id']}/priority", {"priority": 2})[1]["priority"], 2)
        self.assertEqual(self.call("POST", f"/api/jobs/{a['id']}/cancel")[1]["state"], "cancelled")
        self.assertEqual(self.call("POST", f"/api/jobs/{a['id']}/pause")[0], 409)
        self.assertEqual(self.call("POST", "/api/jobs/999/cancel")[0], 404)
        self.call("POST", f"/api/jobs/{blocker['id']}/cancel")
        self.until(b["id"], "done")

    def test_posts_need_the_token_and_our_origin(self):
        self.assertEqual(self.call("POST", "/api/jobs", {}, {"X-Perflab-Token": "nope"})[0], 403)
        self.assertEqual(self.call("POST", "/api/jobs", {}, {"Origin": "http://evil.example"})[0], 403)
        self.assertEqual(self.call("GET", "/api/jobs", None, {"Host": "evil.example"})[0], 403)  # DNS rebinding
        self.assertEqual(self.call("POST", "/api/jobs", {"argv": [], "cwd": self.root})[0], 400)
        self.assertEqual(self.call("GET", "/api/status")[1]["port"], self.srv.port)
        code, page = self.call("GET", "/")
        self.assertIn(self.srv.token, page)  # same-origin: the page carries it for its POSTs

    def test_project_index_is_served_under_its_id(self):
        p = self.call("POST", "/api/projects", {"root": self.root})[1]
        camp = os.path.join(self.root, "out", "perflab", "ab")
        os.makedirs(os.path.join(camp, "c1"))
        open(os.path.join(camp, "index.html"), "w").write("<p>the index</p>")
        open(os.path.join(camp, "c1", "report.md"), "w").write("Δ ±")
        req = urllib.request.Request(self.srv.url + f"p/{p['id']}/")
        with urllib.request.urlopen(req) as r:  # redirects to the index
            # with the token, for the index's own POSTs (a branch campaign's "profile these two")
            self.assertEqual(r.read().decode(), f'<meta name="perflab-token" content="{self.srv.token}"><p>the index</p>')
            self.assertTrue(r.url.endswith(p["index"]))
        code, text = self.call("GET", f"/p/{p['id']}/ab/c1/report.md")
        self.assertEqual((code, text), (200, "Δ ±"))
        self.assertEqual(self.call("GET", f"/p/{p['id']}/../../etc/passwd")[0], 404)
        self.assertEqual(self.call("GET", "/p/nope/")[0], 404)

    def test_storage_api(self):
        p = self.call("POST", "/api/projects", {"root": self.root})[1]
        c = os.path.join(p["campaigns"], "c1")
        os.makedirs(os.path.join(c, ".build", "v"))
        open(os.path.join(c, ".build", "v", "snap.jar"), "wb").write(b"x" * 50000)
        old = time.time() - 86400
        for d, _, fs in os.walk(c):
            for f in fs:
                os.utime(os.path.join(d, f), (old, old))
        es = self.call("GET", "/api/storage")[1]["entries"]
        self.assertEqual([(e["name"], e["bytes"]["builds"] > 0) for e in es], [("c1", True)])
        r = self.call("POST", "/api/storage/cleanup", {"action": "builds"})[1]
        self.assertTrue(r["dryRun"])
        self.assertTrue(os.path.exists(os.path.join(c, ".build")))
        self.call("POST", "/api/storage/pin", {"project": p["id"], "kind": "campaign", "name": "c1", "pinned": True})
        self.assertEqual(self.call("POST", "/api/storage/cleanup", {"action": "builds", "dry_run": False})[1]["skipped"],
                         [{"name": f"{p['id']}/c1", "why": "pinned"}])
        self.call("POST", "/api/storage/pin", {"project": p["id"], "kind": "campaign", "name": "c1", "pinned": False})
        r = self.call("POST", "/api/storage/cleanup", {"action": "builds", "dry_run": False})[1]
        self.assertGreaterEqual(r["reclaimed"], 50000)
        self.assertFalse(os.path.exists(os.path.join(c, ".build")))
        self.assertEqual(self.call("POST", "/api/storage/cleanup", {"action": "nuke"})[0], 400)


class StorageTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.camps, self.runs = os.path.join(self.root, "ab"), os.path.join(self.root, "runs")
        self.old = time.time() - 40 * 86400

    def file(self, rel, n, top=None, age=None):
        p = os.path.join(top or self.camps, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(b"x" * n)
        t = time.time() - (age if age is not None else 86400)
        os.utime(p, (t, t))
        return p

    def campaign(self, name):
        self.file(f"{name}/c/v/1/result.json", 10000)
        self.file(f"{name}/c/v/1/timeline.html", 10000)
        self.file(f"{name}/c/v/1/prof/x.jfr", 100000, age=40 * 86400)
        self.file(f"{name}/c/v/1/prof/x-cpu.html", 30000)
        self.file(f"{name}/c/v/1/prof/run.trace/data", 20000, age=40 * 86400)
        self.file(f"{name}/diffs/diff-cpu.html", 30000)
        self.file(f"{name}/.build/v/snapshot/a.jar", 200000)
        self.file(f"{name}/.worktree/src.scala", 5000)

    def entry(self, name, kind="campaign", jobs=()):
        return next(e for e in storage.entries("p", self.camps, self.runs, jobs) if e["name"] == name and e["kind"] == kind)

    def test_tiers(self):
        self.assertEqual(storage.tier("c/v/1/result.json", False), ("results", False))
        self.assertEqual(storage.tier("c/v/1/timeline.html", True), ("results", False))
        self.assertEqual(storage.tier("c/v/1/x-cpu.html", True), ("profiles", True))
        self.assertEqual(storage.tier("c/v/1/report.html", False), ("results", False))
        self.assertEqual(storage.tier("diff-alloc-inverse.html", False), ("profiles", True))
        self.assertEqual(storage.tier("c/v/1/a.trace/x/y", False), ("profiles", False))
        self.assertEqual(storage.tier(".build/v/snapshot/a.jar", False), ("builds", False))

    def test_scan_counts_allocated_bytes_by_tier_and_hard_links_once(self):
        self.campaign("big")
        self.file("small/c/v/1/result.json", 1000)
        os.link(os.path.join(self.camps, "big/.build/v/snapshot/a.jar"), os.path.join(self.camps, "big/.build/v/snapshot/b.jar"))
        es = storage.scan([("p", self.camps, self.runs)])
        self.assertEqual([e["name"] for e in es], ["big", "small"])
        big = es[0]
        alloc = lambda rel: os.stat(os.path.join(self.camps, rel)).st_blocks * 512
        self.assertEqual(big["bytes"]["builds"], alloc("big/.build/v/snapshot/a.jar") + alloc("big/.worktree/src.scala"))
        self.assertEqual(big["graphs"], alloc("big/c/v/1/prof/x-cpu.html") + alloc("big/diffs/diff-cpu.html"))
        self.assertEqual(big["bytes"]["results"], alloc("big/c/v/1/result.json") + alloc("big/c/v/1/timeline.html"))
        self.assertFalse(big["active"])

    def test_cleanup_dry_run_then_real(self):
        self.campaign("a")
        self.campaign("pinned")
        storage.pin(os.path.join(self.camps, "pinned"), True)
        es = storage.scan([("p", self.camps, self.runs)])
        dry = storage.cleanup(es, "builds")
        self.assertEqual(sorted(os.path.relpath(p, self.camps) for p in dry["removed"]), ["a/.build", "a/.worktree"])
        self.assertEqual(dry["skipped"], [{"name": "p/pinned", "why": "pinned"}])
        self.assertTrue(os.path.isdir(os.path.join(self.camps, "a/.build")))
        real = storage.cleanup(es, "builds", dry_run=False)
        self.assertEqual(real["reclaimed"], dry["reclaimed"])
        self.assertFalse(os.path.exists(os.path.join(self.camps, "a/.build")))
        self.assertTrue(os.path.isdir(os.path.join(self.camps, "pinned/.build")))
        # graphs: the rendered ones only, never a timeline
        storage.cleanup(storage.scan([("p", self.camps, self.runs)]), "graphs", dry_run=False)
        self.assertFalse(os.path.exists(os.path.join(self.camps, "a/c/v/1/prof/x-cpu.html")))
        self.assertFalse(os.path.exists(os.path.join(self.camps, "a/diffs/diff-cpu.html")))
        self.assertTrue(os.path.exists(os.path.join(self.camps, "a/c/v/1/timeline.html")))
        self.assertTrue(os.path.exists(os.path.join(self.camps, "a/c/v/1/prof/x.jfr")))
        # profiles older than 30 days: the recording and the whole .trace
        r = storage.cleanup(storage.scan([("p", self.camps, self.runs)]), "profiles", days=30, dry_run=False)
        self.assertIn(os.path.join(self.camps, "a/c/v/1/prof/run.trace"), r["removed"])
        self.assertFalse(os.path.exists(os.path.join(self.camps, "a/c/v/1/prof/x.jfr")))
        self.assertFalse(os.path.exists(os.path.join(self.camps, "a/c/v/1/prof/run.trace")))
        self.assertTrue(os.path.exists(os.path.join(self.camps, "a/c/v/1/result.json")))
        # a targeted action reaches a pinned campaign; delete does not
        es = storage.scan([("p", self.camps, self.runs)])
        self.assertEqual(len(storage.cleanup(es, "builds", target={"project": "p", "kind": "campaign", "name": "pinned"})["removed"]), 2)
        self.assertEqual(storage.cleanup(es, "delete", target={"project": "p", "kind": "campaign", "name": "pinned"}, dry_run=False)["skipped"][0]["why"], "pinned")
        storage.cleanup(es, "delete", target={"project": "p", "kind": "campaign", "name": "a"}, dry_run=False)
        self.assertFalse(os.path.exists(os.path.join(self.camps, "a")))
        self.assertTrue(os.path.exists(os.path.join(self.camps, "pinned")))
        with self.assertRaises(ValueError):
            storage.cleanup(es, "profiles")

    def test_active_campaigns_and_runs_are_never_touched(self):
        for n in ("running", "building", "byjob", "byspec", "recent", "idle"):
            self.campaign(n)
        self.file("recent/c/v/2/result.json", 10, age=5)
        json.dump({"campaign": "running", "cell": "running/c/v/1"}, open(os.path.join(self.camps, "running.json"), "w"))
        json.dump({"pid": os.getpid(), "label": "building: v (/x)"}, open(os.path.join(self.camps, "build.json"), "w"))
        spec = os.path.join(self.root, "spec.json")
        json.dump({"name": "byspec"}, open(spec, "w"))
        self.file("r1/result.json", 10, top=self.runs)
        json.dump({"status": "running", "pid": os.getpid()}, open(os.path.join(self.runs, "r1", "run.json"), "w"))
        os.utime(os.path.join(self.runs, "r1", "run.json"), (self.old, self.old))
        jobs = [(["ab", "run", "spec.json"], self.root), (["ab", "report", "byjob"], self.root)]
        es = storage.entries("p", self.camps, self.runs, jobs)
        self.assertEqual(sorted(e["name"] for e in es if e["active"]), ["building", "byjob", "byspec", "r1", "recent", "running"])
        r = storage.cleanup(es, "builds", dry_run=False)
        self.assertEqual({os.path.relpath(p, self.camps).split(os.sep)[0] for p in r["removed"]}, {"idle"})
        self.assertEqual(storage.cleanup(es, "delete", target={"project": "p", "kind": "run", "name": "r1"})["skipped"][0]["why"], "active")


class CliTest(unittest.TestCase):
    """`perflab server start|status|stop`, `submit` and `jobs`, as a shell runs them."""

    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.root = project()
        self.env = {**os.environ, "PYTHONPATH": os.path.abspath(SRC), server.HOME_ENV: self.home,
                    server.PORT_ENV: str(free_port())}

    def perflab(self, *args, timeout=60):
        return subprocess.run([sys.executable, "-m", "perflab", *args], cwd=self.root, env=self.env, capture_output=True,
                              text=True, timeout=timeout)

    def tearDown(self):
        self.perflab("server", "stop")

    def test_start_submit_follow_jobs_stop(self):
        r = self.perflab("server", "start")
        self.assertEqual(r.returncode, 0, r.stderr)
        url = r.stdout.strip()
        self.assertEqual(url, f"http://127.0.0.1:{self.env[server.PORT_ENV]}/")
        self.assertEqual(self.perflab("server", "start").stdout.strip(), url)  # idempotent
        self.assertEqual(os.stat(os.path.join(self.home, "token")).st_mode & 0o777, 0o600)
        r = self.perflab("submit", "--", "index")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertRegex(r.stdout, r"job 1 queued \(#1 in the queue\): " + re.escape(url) + "#job-1")
        self.assertIn("--- perflab", r.stdout)  # the transcript, followed
        self.assertIn("job 1 done", r.stdout)
        self.assertTrue(os.path.exists(os.path.join(self.root, "out", "perflab", "ab", "index.html")))
        r = self.perflab("submit", "--detach", "--", "nosuchcommand")
        self.assertIn("job 2 queued", r.stdout)
        wait_for(lambda: "failed" in self.perflab("jobs", "--all").stdout, what="job 2 to fail")
        r = self.perflab("jobs", "--all")
        self.assertRegex(r.stdout, r"\s1  done .* index")
        r = self.perflab("server", "status")
        self.assertEqual((r.returncode, r.stdout.splitlines()[0]), (0, url))
        self.assertEqual(self.perflab("server", "stop").stdout.strip(), "stopped")
        self.assertEqual(self.perflab("server", "status").returncode, 1)


class PageTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "needs node")
    def test_the_pages_scripts_parse(self):
        srv = server.Server(tempfile.mkdtemp(), port=0)
        try:
            for page in (serverui.queue_page(srv), serverui.admin_page(srv)):
                scripts = re.findall(r"<script>(.*?)</script>", page, re.S)
                self.assertTrue(scripts)
                for i, js in enumerate(scripts):
                    f = os.path.join(srv.home, f"s{i}.js")
                    open(f, "w").write(js)
                    r = subprocess.run(["node", "--check", f], capture_output=True, text=True)
                    self.assertEqual(r.returncode, 0, r.stderr)
        finally:
            srv.httpd.server_close()


if __name__ == "__main__":
    unittest.main()
