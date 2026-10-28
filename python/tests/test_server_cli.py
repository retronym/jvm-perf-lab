"""perflab server and the rest of perflab: adopted jobs' exit status, `run` and `ab run` submitting themselves,
`perflab serve` under a server, and the pages' links between the queue and the projects' indexes."""
import json, os, re, shutil, subprocess, sys, tempfile, time, unittest, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src")
sys.path.insert(0, SRC)
sys.path.insert(0, HERE)
from perflab import control, server  # noqa: E402
from test_server import free_port, project, wait_for  # noqa: E402


class AdoptTest(unittest.TestCase):
    """A server stopped under a running job, and the next one adopting it, reads how the job ended from exit.json."""

    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.root = project()
        self.env = {"PYTHONPATH": os.pathsep.join([HERE, os.path.abspath(SRC)]), control.POLL_ENV: "0.1"}
        self.servers = []

    def tearDown(self):
        for s in self.servers:
            for j in s.q.jobs():
                if j["pid"] and j["state"] in server.ACTIVE:
                    server.Worker._signal(j["pid"], 9)
            s.stop()

    def start(self):
        s = server.Server(self.home, port=0, grace=1).start()
        self.servers.append(s)
        return s

    def adopted(self, *argv):
        a = self.start()
        j = server.submit_local(a, {"argv": list(argv), "cwd": self.root, "env": self.env}, module="perflab_fakejob")
        wait_for(lambda: a.q.get(j["id"])["pid"] and "cell 0" in server._tail(j["transcript"]), what="the job to start")
        a.stop()
        b = self.start()
        return wait_for(lambda: (lambda x: x if x["state"] in server.FINAL else None)(b.q.get(j["id"])), what="the job to end")

    def test_an_adopted_job_ends_with_its_own_status(self):
        j = self.adopted("cells", "4", "0.3", "3")
        self.assertEqual((j["state"], j["rc"]), ("failed", 3))
        self.assertEqual(json.load(open(os.path.join(j["dir"], "exit.json")))["rc"], 3)
        self.assertTrue(os.path.exists(os.path.join(j["dir"], "lock")))  # its wrapper held it, and let go
        self.assertFalse(server.job_alive(j))
        j = self.adopted("cells", "4", "0.3")
        self.assertEqual((j["state"], j["rc"]), ("done", 0))

    def running_job(self, *argv, **kw):
        """A job in the queue as running, as a server that stopped under it left it."""
        q = server.Queue(os.path.join(self.home, "jobs.sqlite"))
        p = q.register(self.root)
        j = q.submit(p["id"], list(argv), self.root, self.env, module="perflab_fakejob", jobs_dir=os.path.join(self.home, "jobs"))
        q.claim()
        return q, q.update(j["id"], **kw) if kw else q.get(j["id"])

    def legacy(self, *argv):
        """A job started by the wrapper from before the lock (as the live server's job was), with no recorded start time."""
        q, j = self.running_job(*argv)
        env = {**os.environ, **self.env, control.ENV: os.path.join(j["dir"], "control"), server.JOB_ENV: str(j["id"])}
        proc = subprocess.Popen([sys.executable, "-c", LEGACY_WRAPPER, os.path.join(j["dir"], "exit.json"), sys.executable,
                                 "-m", "perflab_fakejob", "--transcript", j["transcript"], *argv], cwd=self.root, env=env,
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, start_new_session=True)
        self.addCleanup(proc.wait)
        j = q.update(j["id"], pid=proc.pid)
        wait_for(lambda: "cell 0" in server._tail(j["transcript"]), what="the legacy job to start")
        return j

    def ended(self, s, jid, timeout=20):
        return wait_for(lambda: (lambda x: x if x["state"] in server.FINAL else None)(s.q.get(jid)), timeout, "the job to end")

    def test_a_legacy_job_without_a_lock_is_adopted_by_its_pid(self):
        j = self.legacy("cells", "4", "0.3", "3")
        self.assertFalse(os.path.exists(os.path.join(j["dir"], "lock")))
        self.assertTrue(server.job_alive(j))
        s = self.start()
        j = self.ended(s, j["id"])
        self.assertEqual((j["state"], j["rc"]), ("failed", 3))
        j = self.legacy("cells", "4", "0.3")
        self.assertEqual((self.ended(s, j["id"])["state"]), "done")

    def test_a_legacy_job_cancels_by_its_pid(self):
        j = self.legacy("stubborn", "1", "60")
        s = self.start()
        wait_for(lambda: s.q.get(j["id"])["state"] == "running", what="adoption")
        t = time.time()
        server.cancel(s.q, j["id"])
        self.assertEqual(self.ended(s, j["id"])["state"], "cancelled")
        self.assertLess(time.time() - t, 15)  # SIGTERM after the 1 s grace, not the 60 s sleep

    def test_a_pid_that_is_no_longer_the_jobs_is_never_signalled(self):
        """The recorded pid is now someone else's process group: with the job's lock free, or (no lock) a start time
        that does not match, the job is gone and the group is left alone, though a cancel asked for SIGTERM."""
        for kw in ({"lock": True}, {"pid_start": "Thu Jan  1 00:00:00 1970"}):
            other = subprocess.Popen(["sleep", "60"], start_new_session=True)
            self.addCleanup(other.kill)
            q, j = self.running_job("cells", "1", "0", pid=other.pid, cancel_requested=time.time() - 100,
                                    pid_start=kw.get("pid_start"))
            if kw.get("lock"):
                open(os.path.join(j["dir"], "lock"), "w").close()
            self.assertFalse(server.job_alive(j))
            s = self.start()
            self.assertEqual(self.ended(s, j["id"])["state"], "cancelled")
            time.sleep(0.5)
            self.assertIsNone(other.poll(), kw)  # not signalled
            s.stop()
            self.servers.remove(s)

    def test_a_new_jobs_start_time_is_recorded(self):
        s = self.start()
        j = server.submit_local(s, {"argv": ["cells", "20", "0.1"], "cwd": self.root, "env": self.env}, module="perflab_fakejob")
        j = wait_for(lambda: (lambda x: x if x["pid_start"] else None)(s.q.get(j["id"])), what="the start time")
        self.assertEqual(j["pid_start"], server._started(j["pid"]))
        wait_for(lambda: os.path.exists(os.path.join(j["dir"], "lock")), what="the lock")
        self.assertTrue(server.job_alive(j))
        server.cancel(s.q, j["id"])
        self.ended(s, j["id"])


# the job wrapper before <job dir>/lock (a job it started may still be running when a newer server adopts it)
LEGACY_WRAPPER = r"""
import json, os, signal, subprocess, sys, time
for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
    signal.signal(s, lambda *_: None)
out, cmd = sys.argv[1], sys.argv[2:]
try:
    rc = subprocess.Popen(cmd).wait()
except OSError as e:
    print(f"could not start {cmd[0]}: {e}", flush=True)
    rc = 127
with open(out + ".tmp", "w") as f:
    json.dump({"rc": rc, "ended": time.time()}, f)
os.replace(out + ".tmp", out)
sys.exit(rc if rc >= 0 else 128 - rc)
"""


class SubmitsItselfTest(unittest.TestCase):
    """`perflab run` and `perflab ab run` from a shell while a server runs: a job, followed; `--local` and `--dry-run`
    stay here, as does everything when no server runs."""

    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.root = project('[build]\njmh = "true {args}"\n')
        self.port = free_port()
        env = {k: v for k, v in os.environ.items() if k not in (server.JOB_ENV, server.LOCAL_ENV, "PERFLAB_TRANSCRIPT")}
        self.env = {**env, "PYTHONPATH": os.path.abspath(SRC), server.HOME_ENV: self.home, server.PORT_ENV: str(self.port)}

    def tearDown(self):
        self.perflab("server", "stop")
        self.perflab("serve", "--stop")

    def perflab(self, *args, timeout=60):
        return subprocess.run([sys.executable, "-m", "perflab", *args], cwd=self.root, env=self.env, capture_output=True,
                              text=True, timeout=timeout)

    def jobs(self):
        return json.loads(self.perflab("jobs", "--all", "--json").stdout)

    def test_without_a_server_nothing_changes(self):
        r = self.perflab("run", "--", "-foo")
        self.assertNotIn("queued", r.stdout)
        self.assertIn("[perflab] output:", r.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.home, "jobs.sqlite")))

    def test_run_and_ab_run_become_jobs(self):
        url = self.perflab("server", "start").stdout.strip()
        t = os.path.join(tempfile.mkdtemp(), "t.txt")
        r = self.perflab("--transcript", t, "run", "--", "-foo")
        self.assertRegex(r.stdout, r"job 1 queued \(#1 in the queue\): " + re.escape(url) + "#job-1")
        m = re.search(r"index \(updates as it runs\): (\S+)", r.stdout)
        self.assertTrue(m and m.group(1).startswith(url + "p/") and m.group(1).endswith("/ab/index.html"), r.stdout)
        self.assertRegex(r.stdout, r"job 1 (done|failed)")
        # the job ran `perflab run` itself, here, rather than queue another job
        self.assertEqual([(j["id"], j["argv"]) for j in self.jobs()], [(1, ["run", "--", "-foo"])])
        followed = open(t).read()
        self.assertIn("job 1 queued", followed)
        self.assertIn("[perflab] output:", followed)  # the job's own transcript, followed into ours
        # --local and --dry-run run here
        r = self.perflab("run", "--local", "--", "-foo")
        self.assertNotIn("queued", r.stdout)
        self.assertIn("[perflab] output:", r.stdout)
        spec = os.path.join(self.root, "s.json")
        json.dump({"name": "s", "benchmark": "B", "rounds": 1, "corpora": {"c": ""}, "variants": {"a": ""}}, open(spec, "w"))
        r = self.perflab("ab", "run", spec, "--dry-run")
        self.assertNotIn("queued", r.stdout + r.stderr)
        self.assertEqual(len(self.jobs()), 1)
        r = self.perflab("ab", "run", spec)
        self.assertIn("job 2 queued", r.stdout)
        self.assertEqual(self.jobs()[0]["argv"], ["ab", "run", spec])

    def test_serve_prints_the_projects_page_on_the_server(self):
        url = self.perflab("server", "start").stdout.strip()
        r = self.perflab("serve")
        self.assertEqual(r.returncode, 0, r.stderr)
        page = r.stdout.strip()
        self.assertTrue(page.startswith(url + "p/") and page.endswith("/ab/index.html"), page)
        camps = os.path.join(self.root, "out", "perflab", "ab")
        self.assertFalse(os.path.exists(os.path.join(camps, ".serve.json")))  # no server of its own
        with urllib.request.urlopen(page) as resp:
            self.assertIn("perflab-code", resp.read().decode())


class SingleInstanceTest(unittest.TestCase):
    """One server per home: a second exits saying so, and `start`s racing each other agree on the one that runs."""

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

    def test_racing_starts_share_one_server_and_a_second_run_exits(self):
        procs = [subprocess.Popen([sys.executable, "-m", "perflab", "server", "start"], cwd=self.root, env=self.env,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(3)]
        outs = [p.communicate(timeout=60) for p in procs]
        self.assertEqual([p.returncode for p in procs], [0, 0, 0], outs)
        self.assertEqual(len({o.strip() for o, _ in outs}), 1, outs)
        for port in (self.env[server.PORT_ENV], str(free_port())):  # its port, or another
            r = self.perflab("server", "run", "--port", port, timeout=30)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("another server is running for " + self.home, r.stderr)
        self.assertEqual(self.perflab("server", "status").returncode, 0)


class PagesLinkTest(unittest.TestCase):
    def test_queue_page_follows_the_running_jobs_project_and_the_index_links_the_queue(self):
        from perflab import config, index, serverui
        srv = server.Server(tempfile.mkdtemp(), port=0)
        try:
            page = serverui.queue_page(srv)
        finally:
            srv.httpd.server_close()
        self.assertIn("BenchTimeline.mount", page)
        self.assertIn("'running.json'", page)
        self.assertIn("'build.json'", page)
        root = project()
        config._config = config.find(root)
        html = open(index.build(os.path.join(root, "out", "perflab", "ab"))).read()
        self.assertIn("fetch('/api/status'", html)  # only under /p/<project>/, served by the server
        self.assertIn(r"/^\/p\/[^/]+\//.test(location.pathname)", html)
        if shutil.which("node"):
            for i, js in enumerate(re.findall(r"<script>(.*?)</script>", page + html, re.S)):
                f = os.path.join(root, f"s{i}.js")
                open(f, "w").write(js)
                r = subprocess.run(["node", "--check", f], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
