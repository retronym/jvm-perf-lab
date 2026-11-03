import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from perflab import config, share
from test_api import plain_fixture, project_dir


class KindTest(unittest.TestCase):
    def test_what_each_file_is_for_sharing(self):
        k = share.kind
        for rel, want in [("spec.json", "results"), ("NOTES.md", "results"), ("a/base/1/result.json", "results"),
                          ("a/base/1/iterations.tsv", "results"), ("a/base/1/gc.log.0", "results"), ("a/base/1/timeline.html", "results"),
                          ("diff-a-b/table-cycles.md", "results"),
                          ("a/base/1/B.compile-x/jfr-cpu.html", "profiles"), ("a/base/1/B.compile-x/jfr-cpu.jfr", "raw"),
                          ("diff-a-b/diff-cycles.html", "profiles"), ("a/base/1/kperf-samples.json", "profiles"),
                          ("a/base/1/asm/m/1-t4.s", "asm"), ("asm-diff-m-a-b.html", "asm"),
                          ("a/base/1/build.log", "logs"), ("a/base/1/jmh.log", "logs"),
                          ("a/base/1/x.trace/data", "raw"), ("a/base/1/x.trace.counters.xml", "raw"), ("a/base/1/jit-7.jitrec", "raw"),
                          ("a/base/1/vm-pid7.log.gz", "raw"), (".build/base/a.jar", "raw"), (".void/a/base/1/result.json", "raw"),
                          ("share.json", "raw")]:
            self.assertEqual(k(rel), want, rel)


class ShareTest(unittest.TestCase):
    """A campaign shared through a fake `share`, which keeps what it was given."""

    def setUp(self):
        self.root = project_dir()
        self.cwd = os.getcwd()
        os.chdir(self.root)
        plain_fixture(config.get().campaigns)
        self.got = os.path.join(self.root, "published")
        fake = os.path.join(self.root, "fake-share")
        with open(fake, "w") as f:
            f.write(f'#!/bin/sh\nif [ "$1" = rm ]; then rm -rf {self.got}; exit 0; fi\n'
                    f'rm -rf {self.got}; cp -R "$4" {self.got}; echo "$SHARE_URL/$2/"\n')
        os.chmod(fake, 0o755)
        st = os.path.join(self.root, "share.toml")
        open(st, "w").write(f'command = "{fake}"\nurl = "https://share.test"\n')
        os.environ["PERFLAB_SHARE_SETTINGS"] = st

    def tearDown(self):
        os.chdir(self.cwd)
        os.environ.pop("PERFLAB_SHARE_SETTINGS", None)

    def test_results_only_then_again_at_the_same_url_then_down(self):
        self.assertEqual(share.main(["plain"]), 0)
        rec = json.load(open(os.path.join(config.get().campaigns, "plain", share.RECORD)))
        self.assertRegex(rec["url"], r"^https://share.test/plain-[0-9a-f]{6}/$")
        self.assertTrue(os.path.exists(os.path.join(self.got, "index.html")))
        cell = os.path.join(self.got, "campaigns", "plain", "a", "base", "1")
        self.assertTrue(os.path.exists(os.path.join(cell, "result.json")))
        self.assertFalse(os.path.exists(os.path.join(cell, "jmh.log")))  # a log: only with --logs
        self.assertFalse(os.path.exists(os.path.join(cell, "jit-7.jitrec")))  # raw: never
        self.assertFalse(any(f == share.RECORD for _, _, fs in os.walk(self.got) for f in fs))
        page = open(os.path.join(self.got, "index.html")).read()
        self.assertIn("results only", page)
        self.assertNotIn(os.path.expanduser("~"), page)
        share.main(["plain", "--logs"])
        rec2 = json.load(open(os.path.join(config.get().campaigns, "plain", share.RECORD)))
        self.assertEqual((rec2["url"], rec2["depth"]), (rec["url"], ["logs"]))  # the same site, replaced
        self.assertTrue(os.path.exists(os.path.join(cell, "jmh.log")))
        share.main(["plain", "--rm"])
        self.assertFalse(os.path.exists(os.path.join(config.get().campaigns, "plain", share.RECORD)))
        self.assertFalse(os.path.exists(self.got))


if __name__ == "__main__":
    unittest.main()
