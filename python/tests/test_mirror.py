import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from perflab import mirror


class MirrorTest(unittest.TestCase):
    """A worker's <campaigns> (src) mirrored into a coordinator's (dst) by heartbeats' entries."""

    def setUp(self):
        t = tempfile.mkdtemp()
        self.src, self.dst = os.path.join(t, "worker"), os.path.join(t, "coord")
        self.cell = os.path.join(self.src, "camp", "c", "v", "1")
        os.makedirs(self.cell)
        os.makedirs(self.dst)
        self.s = mirror.Sender(self.src)

    def write(self, rel, text, mode="a"):
        with open(os.path.join(self.src, rel), mode) as f:
            f.write(text)

    def beat(self, **kw):
        es = self.s.changes(**kw)
        self.s.forget(mirror.apply(self.dst, "w1", 7, es))
        return es

    def mirrored(self, rel):
        with open(os.path.join(mirror.root(self.dst, "w1"), rel)) as f:
            return f.read()

    def test_appends_are_sent_once_and_a_replaced_file_again(self):
        self.write("running.json", json.dumps({"campaign": "camp", "cell": "camp/c/v/1", "started": 1}), "w")
        self.write("camp/c/v/1/iterations.tsv", "a\n")
        self.write("camp/c/v/1/gc.log", "fork1\n")
        self.beat()
        self.write("camp/c/v/1/iterations.tsv", "b\n")
        es = self.beat()
        self.assertEqual([(e["path"], e["off"], e["data"]) for e in es], [("camp/c/v/1/iterations.tsv", 2, "b\n")])  # only what was appended
        self.assertEqual(self.mirrored("camp/c/v/1/iterations.tsv"), "a\nb\n")
        self.assertEqual(self.beat(), [])
        # the next fork: the JVM moves gc.log aside and starts a new one
        os.rename(os.path.join(self.cell, "gc.log"), os.path.join(self.cell, "gc.log.0"))
        self.write("camp/c/v/1/gc.log", "f2\n")
        self.beat()
        self.assertEqual((self.mirrored("camp/c/v/1/gc.log"), self.mirrored("camp/c/v/1/gc.log.0")), ("f2\n", "fork1\n"))
        self.assertEqual(json.load(open(os.path.join(self.dst, ".live", "index.json")))["w1"]["job"], 7)
        # the cell over: running.json goes, and so does its copy
        os.unlink(os.path.join(self.src, "running.json"))
        self.assertEqual(self.beat(), [{"path": "running.json", "gone": True}])
        self.assertFalse(os.path.exists(os.path.join(mirror.root(self.dst, "w1"), "running.json")))
        mirror.clear(self.dst, "w1")
        self.assertFalse(os.path.exists(mirror.root(self.dst, "w1")))
        self.assertEqual(json.load(open(os.path.join(self.dst, ".live", "index.json"))), {})

    def test_a_coordinator_that_lost_the_mirror_gets_it_again_and_a_beat_has_a_budget(self):
        self.write("running.json", json.dumps({"campaign": "camp", "cell": "camp/c/v/1/", "started": 1}), "w")
        self.write("camp/c/v/1/load.tsv", "x" * 100)
        self.beat()
        mirror.clear(self.dst, "w1")  # the coordinator restarted with its mirror gone, say
        self.write("camp/c/v/1/load.tsv", "y")
        self.beat()  # a gap: refused, and forgotten by the sender
        self.beat(budget=60)  # from 0 again, in two beats of at most 60 bytes
        self.assertEqual(len(self.mirrored("camp/c/v/1/load.tsv")), 60)
        self.beat(budget=60)
        self.assertEqual(self.mirrored("camp/c/v/1/load.tsv"), "x" * 100 + "y")

    def test_paths_stay_in_the_mirror(self):
        mirror.apply(self.dst, "w1", 7, [{"path": p, "off": 0, "data": "no"} for p in ("../evil", "/etc/x", "a/../../b", ".live/index.json", "")])
        self.assertEqual(sorted(os.listdir(self.dst)), [".live"])
        self.assertEqual(os.listdir(os.path.join(self.dst, ".live")), ["index.json"])


if __name__ == "__main__":
    unittest.main()
