import json, os, sys, tempfile, unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ["PERFLAB_SERVER_HOME"] = tempfile.mkdtemp()  # never a real `perflab server`
from perflab import loadgate, quiet  # noqa: E402

MDUTIL = "/:\n\tIndexing enabled. \n/System/Volumes/Data:\n\tIndexing disabled.\n/Volumes/Backup:\n\tError: unknown indexing state.\n"


class ParsingTest(unittest.TestCase):
    def test_mdutil_volumes(self):
        self.assertEqual(quiet.parse_mdutil(MDUTIL), {"/": True, "/System/Volumes/Data": False})

    def test_machine_state_round_trips(self):
        m = {"thermal": "serious", "power": "battery", "lowpower": True, "memfree": 23}
        s = loadgate.state_str(m)
        self.assertEqual(s, "thermal=serious power=battery lowpower mem=23%")
        self.assertEqual(loadgate.parse_state(s), m)
        self.assertEqual(loadgate.parse_state(""), {})
        self.assertEqual(loadgate.parse_state("thermal=bogus mem=x"), {})

    def test_describe(self):
        self.assertEqual(loadgate.describe({"thermal": "nominal", "power": "ac", "memfree": 81}, 0.3, "WindowServer 0.2"),
                         "other load 0.30 cores (WindowServer 0.2); thermal nominal, AC power, 81% memory free")
        self.assertEqual(loadgate.describe({}), "")


class ThermalIterationsTest(unittest.TestCase):
    """A cell whose second measurement iteration ran while the machine was throttling: disturbed though other load
    stayed under the limit."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        with open(os.path.join(self.d, "iterations.tsv"), "w") as f:
            f.write("index\tkind\tvariant\tstart_ms\tend_ms\tscore\n")
            for i, a in enumerate([1010, 1014, 1018]):
                f.write(f"{i}\tmeasure\t\t{a * 1000}\t{(a + 3.5) * 1000:.0f}\t700\n")
        with open(os.path.join(self.d, "load.tsv"), "w") as f:
            for t, c, st in [(1012, 0.5, "thermal=nominal power=ac mem=80%"), (1014, 0.6, "thermal=fair power=ac mem=80%"),
                             (1016, 0.4, "thermal=serious power=ac lowpower mem=80%"), (1018, 0.4, "thermal=fair power=ac mem=80%"),
                             (1020, 0.3, ""), (1022, 0.3, "")]:
                f.write(f"{t}\t{c}\tjava 0.3\t2\t{st}\n")

    def test_worst_thermal_state_over_each_iteration(self):
        its = loadgate.per_iteration(os.path.join(self.d, "load.tsv"), os.path.join(self.d, "iterations.tsv"))
        self.assertEqual([i["thermal"] for i in its], ["fair", "serious", None])
        self.assertEqual([i["lowpower"] for i in its], [False, True, False])
        self.assertEqual([loadgate.disturbed(i, 1.5) for i in its], [False, True, False])
        self.assertEqual(loadgate.disturbance(its[1]), "thermal serious; 0.4 cores: java 0.3")
        self.assertTrue(loadgate.disturbed(its[1], None))  # a throttling state counts without a load limit


class OnOffTest(unittest.TestCase):
    """`on` records what it turned off and `off` restores exactly that, with the privileged commands and the
    applications stubbed."""

    def setUp(self):
        self.state = os.path.join(tempfile.mkdtemp(), "quiet.json")
        os.environ[quiet.STATE_ENV] = self.state
        self.cmds = []
        p = [mock.patch.object(quiet.Sudo, "available", lambda s: True),
             mock.patch.object(quiet, "run", self.fake_run),
             mock.patch.object(quiet, "time_machine", lambda: True),
             mock.patch.object(quiet, "spotlight", lambda: {"/": True, "/System/Volumes/Data": False}),
             mock.patch.object(quiet, "software_update", lambda: False),
             mock.patch.object(quiet, "low_power", lambda: True),
             mock.patch.object(quiet, "running_apps", lambda names: [n for n in names if n in self.running]),
             mock.patch.object(quiet, "quit_apps", self.fake_quit),
             mock.patch.object(quiet, "status", lambda argv: 0),
             mock.patch.object(quiet, "configured_apps", lambda: ["Docker", "Slack"]),
             mock.patch.object(quiet, "configured_spotlight", lambda: True),
             mock.patch.object(quiet.subprocess, "Popen", lambda *a, **k: type("P", (), {"pid": 4242})()),
             mock.patch.object(quiet, "caffeinate_pid", lambda state: state.get("caffeinate")),
             mock.patch.object(quiet.os, "kill", lambda pid, sig: self.cmds.append(["kill", pid]))]
        for x in p:
            x.start()
            self.addCleanup(x.stop)
        self.running = ["Docker"]

    def fake_run(self, cmd, timeout=30):
        self.cmds.append(cmd)
        return quiet.subprocess.CompletedProcess(cmd, 0, "", "")

    def fake_quit(self, apps):
        self.running = []
        return []

    def test_on_then_off(self):
        self.assertEqual(quiet.on([]), 0)
        rec = json.load(open(self.state))
        self.assertEqual(rec["done"], {"timeMachine": True, "spotlight": ["/"], "lowPower": True})
        self.assertEqual(rec["apps"], ["Docker"])
        self.assertEqual(rec["caffeinate"], 4242)
        self.assertEqual(rec["pending"], [])
        sudo = [c[2:] for c in self.cmds if c[:2] == ["sudo", "-n"]]
        self.assertEqual(sudo, [["tmutil", "disable"], ["mdutil", "-a", "-i", "off"], ["pmset", "-a", "lowpowermode", "0"]])
        self.cmds.clear()
        self.assertEqual(quiet.off([]), 0)
        self.assertFalse(os.path.exists(self.state))
        sudo = [c[2:] for c in self.cmds if c[:2] == ["sudo", "-n"]]
        # only the volume that was indexing comes back; software update was already off, so it stays off
        self.assertEqual(sudo, [["tmutil", "enable"], ["mdutil", "-i", "on", "/"], ["pmset", "-a", "lowpowermode", "1"]])
        self.assertIn(["kill", 4242], self.cmds)
        self.assertIn(["open", "-g", "-a", "Docker"], self.cmds)

    def test_only_what_ran_is_restored(self):
        """Without root, `on` leaves the privileged commands to the user: `off` then has nothing privileged to undo,
        and says what to reverse by hand."""
        with mock.patch.object(quiet.Sudo, "available", lambda s: False):
            self.assertEqual(quiet.on([]), 0)
        rec = json.load(open(self.state))
        self.assertEqual(rec["done"], {})
        self.assertEqual(rec["pending"], ["sudo tmutil disable", "sudo mdutil -a -i off", "sudo pmset -a lowpowermode 0"])
        self.cmds.clear()
        self.assertEqual(quiet.off([]), 0)
        self.assertEqual([c for c in self.cmds if c[:1] == ["sudo"]], [])
        self.assertFalse(os.path.exists(self.state))

    def test_off_without_on(self):
        self.assertEqual(quiet.off([]), 0)
        self.assertEqual(self.cmds, [])


if __name__ == "__main__":
    unittest.main()
