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
        j = server.submit_local(a, {"argv": list(argv), "cwd": self.root, "env": self.env, "module": "perflab_fakejob"})
        wait_for(lambda: a.q.get(j["id"])["pid"] and "cell 0" in server._tail(j["transcript"]), what="the job to start")
        a.stop()
        b = self.start()
        return wait_for(lambda: (lambda x: x if x["state"] in server.FINAL else None)(b.q.get(j["id"])), what="the job to end")

    def test_an_adopted_job_ends_with_its_own_status(self):
        j = self.adopted("cells", "4", "0.3", "3")
        self.assertEqual((j["state"], j["rc"]), ("failed", 3))
        self.assertEqual(json.load(open(os.path.join(j["dir"], "exit.json")))["rc"], 3)
        j = self.adopted("cells", "4", "0.3")
        self.assertEqual((j["state"], j["rc"]), ("done", 0))


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


if __name__ == "__main__":
    unittest.main()
