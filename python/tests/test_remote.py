import json, os, shutil, subprocess, sys, tempfile, time, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.realpath(os.path.join(HERE, "..", "src"))
sys.path.insert(0, SRC)
os.environ["PERFLAB_SERVER_HOME"] = tempfile.mkdtemp()  # never a real `perflab server`
from perflab import ab, remote, serve, server, testbed, worker  # noqa: E402
from test_server import free_port, project, wait_for  # noqa: E402


def sh(d, *cmd):
    return subprocess.run(cmd, cwd=d, check=True, capture_output=True, text=True).stdout.strip()


def git_repo(d):
    os.makedirs(d, exist_ok=True)
    sh(d, "git", "init", "-q", "-b", "main")
    sh(d, "git", "config", "user.email", "t@example.com")
    sh(d, "git", "config", "user.name", "t")
    return d


def commit(d, msg, **files):
    for name, text in files.items():
        os.makedirs(os.path.dirname(os.path.join(d, name)), exist_ok=True)
        with open(os.path.join(d, name), "w") as f:
            f.write(text)
    sh(d, "git", "add", "-A")
    sh(d, "git", "commit", "-q", "-m", msg)
    return sh(d, "git", "rev-parse", "HEAD")


class QueueTest(unittest.TestCase):
    def setUp(self):
        self.q = server.Queue(os.path.join(tempfile.mkdtemp(), "jobs.sqlite"))
        self.p = self.q.register(project())

    def submit(self, tb=None):
        return self.q.submit(self.p["id"], ["ab", "run", "x.json"], "/", testbed_=tb)

    def test_each_testbed_claims_its_own(self):
        far = self.submit("far")
        near = self.submit()
        self.assertEqual(self.q.claim()["id"], near["id"])  # the local worker skips far's
        self.assertIsNone(self.q.claim_remote("w1", "other"))
        got = self.q.claim_remote("w1", "far")
        self.assertEqual((got["id"], got["worker"], got["state"]), (far["id"], "w1", "running"))
        self.assertEqual(self.q.active()["id"], near["id"])  # a remote job is not this machine's to supervise
        self.assertEqual(self.q.claim_remote("w1", "far")["id"], far["id"])  # a worker that restarted gets it again
        self.assertIsNone(self.q.claim_remote(testbed.name(), testbed.name()))  # never this machine's own

    def test_heartbeat_pause_finish_and_a_lost_lease(self):
        j = self.submit("far")
        self.q.claim_remote("w1", "far")
        self.assertEqual(self.q.heartbeat(j["id"], "w1", paused=True)["state"], "paused")
        self.assertEqual(self.q.heartbeat(j["id"], "w1")["state"], "running")
        with self.assertRaises(server.Conflict):
            self.q.heartbeat(j["id"], "w2")
        [back] = self.q.expire(time.time() + server.LEASE + 1)
        self.assertEqual((back["state"], back["worker"]), ("queued", None))
        self.assertIn("w1 stopped answering", back["note"])
        with self.assertRaises(server.Conflict):
            self.q.heartbeat(j["id"], "w1")
        self.q.claim_remote("w2", "far")
        self.assertEqual(self.q.finish(j["id"], "w2", 0)["state"], "done")

    def test_a_cancelled_job_whose_worker_went_is_cancelled(self):
        j = self.submit("far")
        self.q.claim_remote("w1", "far")
        self.q.update(j["id"], cancel_requested=time.time())
        [c] = self.q.expire(time.time() + server.LEASE + 1)
        self.assertEqual(c["state"], "cancelled")

    def test_only_ab_run_goes_to_another_testbed(self):
        d = tempfile.mkdtemp()
        json.dump({"name": "x", "testbed": "far", "corpora": {}}, open(os.path.join(d, "x.json"), "w"))
        self.assertEqual(server.job_testbed(["ab", "run", "x.json"], d), "far")
        self.assertIsNone(server.job_testbed(["ab", "report", "x.json"], d))
        json.dump({"name": "x", "testbed": testbed.name(), "corpora": {}}, open(os.path.join(d, "x.json"), "w"))
        self.assertIsNone(server.job_testbed(["ab", "run", "x.json"], d))


class MappingTest(unittest.TestCase):
    def test_inputs_are_the_paths_the_spec_names(self):
        spec = {"jvmArgs": "-Xmx1G -Da=/x/corpus/ -Db=/y/a.jar:/y/b.jar", "lib": "/z/lib.dylib", "description": "/not/this",
                "corpora": {"c": "-p corpus=/x/c2"}, "builds": {"b": {"checkout": "/not/a/build"}}}
        self.assertEqual(remote.input_paths(spec), ["/x/c2", "/x/corpus", "/y/a.jar", "/y/b.jar", "/z/lib.dylib"])


    def job(self, **cfg):
        w = worker.Worker("http://x", "t", "w", "far", tempfile.mkdtemp(), cfg)
        return worker.Job(w, {"job": 1, "harness": {"top": "/coord/repo"}, "home": "/coord", "spec": {}})

    def test_paths_map_by_longest_prefix_in_one_pass(self):
        j = self.job(paths={"/coord/data": "/elsewhere/data"})
        m = j.mapper("/w/harness")
        here = os.path.expanduser("~")
        self.assertEqual(m("-Da=/coord/repo/lab/x -Db=/coord/lib/y.jar:/coord/data/z"),
                         f"-Da=/w/harness/lab/x -Db={here}/lib/y.jar:/elsewhere/data/z")
        self.assertEqual(m("/coord-other/x /coordx"), "/coord-other/x /coordx")  # whole segments only

    def test_a_jdk_by_its_release_or_a_message_saying_what_to_install(self):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "bin"))
        open(os.path.join(d, "bin", "java"), "w").close()
        open(os.path.join(d, "release"), "w").write('JAVA_RUNTIME_VERSION="99.0.1+1"\nIMPLEMENTOR="Acme"\n')
        want = {"path": "/coord/.sdkman/candidates/java/99-acme/bin/java", "home": "/coord/.sdkman/candidates/java/99-acme",
                "release": {"JAVA_RUNTIME_VERSION": "99.0.1+1", "IMPLEMENTOR": "Acme"}}
        self.assertEqual(self.job().jdk(want, os.path.join(d, "bin", "java")), os.path.join(d, "bin", "java"))
        self.assertEqual(self.job(jdks={"99.0.1+1": d}).jdk(want, "/nowhere/bin/java"), os.path.join(d, "bin", "java"))
        with self.assertRaises(RuntimeError) as e:
            self.job().jdk(want, "/nowhere/bin/java")
        self.assertIn("sdk install java 99-acme", str(e.exception))


@unittest.skipUnless(shutil.which("git"), "needs git")
class EndToEndTest(unittest.TestCase):
    """A campaign of testbed "sim", queued on a coordinator, run by `perflab worker` in another process: two builds, one
    of a pushed commit and one of an unpushed one (a bundle), with the harness's uncommitted change and a path in the
    spec mapped to the worker's checkout of it."""

    def setUp(self):
        t = os.path.realpath(tempfile.mkdtemp())
        self.t = t
        # the source repository: upstream has VERSION 5; the checkout has an unpushed commit of VERSION 7
        up = os.path.join(t, "upstream.git")
        sh(t, "git", "init", "-q", "--bare", "-b", "main", up)
        src = git_repo(os.path.join(t, "src"))
        self.pushed = commit(src, "five", VERSION="5")
        sh(src, "git", "remote", "add", "origin", up)
        sh(src, "git", "push", "-q", "origin", "main")
        self.unpushed = commit(src, "seven", VERSION="7")
        sh(src, "git", "worktree", "add", "-q", "--detach", os.path.join(t, "base"), self.pushed)
        # the harness: a project whose launch build and JMH are fakes; data.txt changed but not committed
        h = git_repo(os.path.join(t, "harness"))
        lab = os.path.join(h, "lab")
        fx = os.path.join(HERE, "remote_fixture")
        files = {f"lab/{f}": open(os.path.join(fx, f)).read() for f in ("fakebuild.py", "fakejmh.py")}
        files["lab/perflab.toml"] = (f'[build]\njmh = "x {{args}}"\nlaunch = "{sys.executable} fakebuild.py {{out}}"\n'
                                     '[benchmark]\ndefault = "B"\ncorpus = "corpus"\n[paths]\ncampaigns = "out/ab"\nruns = "out/runs"\n')
        files[".gitignore"] = "out/\n"
        files["lab/data.txt"] = "1"
        env = {"FAKE_CHECKOUT": "{checkout}"}
        files["lab/campaigns/rw.json"] = json.dumps({
            "name": "rw", "testbed": "sim", "rounds": 1, "corpora": {"c": ""},
            "jvmArgs": f"-Dfake.data={lab}/data.txt",
            "builds": {"base": {"checkout": "../../../base", "env": env}, "tip": {"checkout": "../../../src", "env": env},
                       "tip2": {"checkout": "../../../src", "env": env}}})
        commit(h, "lab", **files)
        open(os.path.join(lab, "data.txt"), "w").write("2")
        self.lab = lab
        self.srv = server.Server(home_dir=os.path.join(t, "coord"), port=free_port()).start()
        self.whome = os.path.join(t, "worker")
        os.makedirs(os.path.join(t, "tmp"))

    def tearDown(self):
        self.srv.stop()
        for d in glob_campaigns(self.whome):
            serve.stop(d)  # the worker's job serves its own index

    def work(self):
        env = {**os.environ, "PERFLAB_WORKER_HOME": self.whome, "PERFLAB_WORKER_TOKEN": self.srv.token,
               "PYTHONPATH": SRC, "PERFLAB_WORKER_BEAT": "0.5", "PERFLAB_CONTROL_POLL": "0.2", "TMPDIR": os.path.join(self.t, "tmp")}  # its own jmh.lock
        env.pop("PERFLAB_SERVER_HOME", None)
        return subprocess.run([sys.executable, "-m", "perflab", "worker", "--server", self.srv.url, "--testbed", "sim",
                               "--name", "w1", "--once", "--poll", "0.2"], env=env, capture_output=True, text=True, timeout=180)

    def test_a_worker_runs_the_campaign_and_its_cells_land_on_the_coordinator(self):
        j = server.submit_local(self.srv, {"argv": ["ab", "run", "campaigns/rw.json"], "cwd": self.lab})
        self.assertEqual(j["testbed"], "sim")
        time.sleep(1.5)
        self.assertEqual(self.srv.q.get(j["id"])["state"], "queued")  # the coordinator's own worker leaves it
        r = self.work()
        j = self.srv.q.get(j["id"])
        log = open(j["transcript"]).read()
        self.assertEqual(j["state"], "done", r.stdout + r.stderr + log)
        camp = os.path.join(self.lab, "out", "ab", "rw")
        version = open(os.path.join(camp, "c", "base", "1", "spec.version")).read()
        self.assertEqual(version, remote.payload(j)["specVersion"])
        for v, want in (("base", 5 + 2), ("tip", 7 + 2), ("tip2", 7 + 2)):  # VERSION of its commit + the harness's uncommitted data.txt
            cell = os.path.join(camp, "c", v, "1")
            res = json.load(open(os.path.join(cell, "result.json")))[0]
            self.assertEqual(res["primaryMetric"]["score"], want, v)
            self.assertEqual(testbed.of_cell(cell), "sim")
            self.assertTrue(ab.done(cell))
        self.assertIn("from the coordinator's bundle", log)  # the unpushed commit
        self.assertIn("uploaded c/tip/1", log)
        # a cell is uploaded at a cell boundary, the job paused meanwhile: never while a later cell measures
        self.assertLess(log.index("uploaded c/base/1"), log.index("round 1 c tip2"))
        self.assertNotIn(self.whome, json.load(open(os.path.join(camp, "spec.json")))["jvmArgs"])  # the coordinator's own spec
        # again: the worker resumes from the coordinator's cells, and has nothing to run
        j2 = server.submit_local(self.srv, {"argv": ["ab", "run", "campaigns/rw.json"], "cwd": self.lab})
        r = self.work()
        j2 = self.srv.q.get(j2["id"])
        self.assertEqual(j2["state"], "done", r.stdout + r.stderr)
        self.assertIn("3 cells, 0 to run", open(j2["transcript"]).read())


def glob_campaigns(whome):
    import glob
    return glob.glob(os.path.join(whome, "harness", "*", "lab", "out", "ab"))


if __name__ == "__main__":
    unittest.main()
