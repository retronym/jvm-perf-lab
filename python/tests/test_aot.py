"""perflab.aot and launch.jar_dirs: AOT caches for a campaign's forks."""
import json, os, sys, tempfile, unittest, zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from perflab import aot, launch


class FakeSpec:
    def __init__(self, out, caches=1, builds=None):
        self.out, self.aot, self.builds = out, {"caches": caches}, builds or {}
        self.variants = {"cold": "", "aot": "{aot} -Dx=1"}


class AotTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_uses_and_index(self):
        s = FakeSpec(self.tmp, caches=3)
        self.assertTrue(aot.uses(s))
        self.assertEqual([aot.index(s, r) for r in range(1, 8)], [1, 2, 3, 1, 2, 3, 1])
        self.assertEqual(aot.train_dir(s, "aot", "scala", 5), os.path.join(self.tmp, ".aot", "default", "default", "scala", "2"))
        s.builds = {"aot": {"checkout": "/x"}}
        self.assertTrue(aot.train_dir(s, "aot", "scala", 1).endswith(os.path.join(".aot", "aot", "default", "scala", "1")))
        s.aot["variants"] = {"short": {"train": "-wi 2"}}
        self.assertEqual(aot.training(s, "short"), ("short", "-wi 2"))
        self.assertEqual(aot.training(s, "aot"), ("default", None))
        self.assertTrue(aot.train_dir(s, "short", "scala", 1).endswith(os.path.join(".aot", "default", "short", "scala", "1")))
        self.assertFalse(aot.uses(type("S", (), {"variants": {"a": ""}})()))

    def test_expand(self):
        self.assertEqual(aot.expand("{aot} -Dx=1", "/t", "/cell"),
                         "-XX:AOTMode=on -XX:AOTCache=/t/cache.aot -Xlog:aot:file=/cell/aot.log -Dx=1")

    def test_check(self):
        tdir, dest = os.path.join(self.tmp, "t"), os.path.join(self.tmp, "c")
        os.makedirs(tdir), os.makedirs(dest)
        with open(os.path.join(tdir, aot.INFO), "w") as f:
            json.dump({"cache": "c", "sha256": "s", "index": 1, "build": "default", "corpus": "x"}, f)
        self.assertIn("no aot.log", aot.check(tdir, dest))
        log = os.path.join(dest, "aot.log")
        open(log, "w").write("[info][aot] Using AOT-linked classes: true\n")
        self.assertIn("did not open", aot.check(tdir, dest))
        open(log, "w").write("[info][aot] Opened AOT cache c.\n[info][aot] Using AOT-linked classes: false\n")
        self.assertIn("lacks", aot.check(tdir, dest))
        open(log, "w").write("[info][aot] Opened AOT cache c.\n[info][aot] Using AOT-linked classes: true (static archive: has aot-linked classes)\n")
        self.assertIsNone(aot.check(tdir, dest))
        self.assertEqual(json.load(open(os.path.join(dest, aot.INFO)))["sha256"], "s")
        self.assertTrue(json.load(open(os.path.join(dest, aot.INFO)))["linked"])
        with open(os.path.join(tdir, aot.INFO), "w") as f:
            json.dump({"cache": "c", "sha256": "s", "trainJvmArgs": "-XX:-AOTClassLinking"}, f)
        self.assertIn("has AOT-linked", aot.check(tdir, dest))
        open(log, "w").write("[info][aot] Opened AOT cache c.\n[info][aot] Using AOT-linked classes: false (static archive: no aot-linked classes)\n")
        self.assertIsNone(aot.check(tdir, dest))

    def test_train_jvm_args(self):
        s = FakeSpec(self.tmp)
        s.aot["variants"] = {"nolink": {"jvmArgs": "-XX:-AOTClassLinking"}}
        self.assertEqual(aot.train_jvm_args(s, "nolink"), "-XX:-AOTClassLinking")
        self.assertEqual(aot.train_jvm_args(s, "aot"), "")
        self.assertEqual(aot.training(s, "nolink"), ("nolink", None))

    def test_jar_dirs(self):
        snap = os.path.join(self.tmp, "snapshot")
        classes = os.path.join(snap, "0-classes")
        os.makedirs(os.path.join(classes, "a", "b"))
        open(os.path.join(classes, "a", "b", "C.class"), "wb").write(b"\xca\xfe")
        jar = os.path.join(self.tmp, "dep.jar")
        open(jar, "wb").close()
        with open(os.path.join(self.tmp, launch.LAUNCH), "w") as f:
            json.dump({"classpath": [classes, jar], "snapshot": snap}, f)
        l = launch.jar_dirs(self.tmp)
        self.assertTrue(l["jarred"])
        self.assertEqual(l["classpath"], [classes + ".jar", jar])
        with zipfile.ZipFile(l["classpath"][0]) as z:
            self.assertEqual(z.namelist(), ["a/b/C.class"])
            self.assertEqual(z.read("a/b/C.class"), b"\xca\xfe")
        mtime = os.path.getmtime(l["classpath"][0])
        self.assertEqual(launch.jar_dirs(self.tmp), l)  # idempotent: the JARs (and the caches that check them) stay
        self.assertEqual(os.path.getmtime(l["classpath"][0]), mtime)


if __name__ == "__main__":
    unittest.main()
