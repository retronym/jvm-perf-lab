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


if __name__ == "__main__":
    unittest.main()
