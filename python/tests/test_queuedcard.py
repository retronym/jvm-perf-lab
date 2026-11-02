import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from perflab import index, server


class QueuedCardTest(unittest.TestCase):
    def test_a_queued_campaign_card_says_what_its_spec_runs(self):
        d = tempfile.mkdtemp()
        f = os.path.join(d, "c.json")
        json.dump({"name": "c", "testbed": "m4", "rounds": 2, "corpora": {"dotc": "-f 1 -wi 3 -i 3"}, "jvmArgs": "-Xmx1g",
                   "description": "Does <b>it</b> help?", "variantDescriptions": {"base": "main"},
                   "builds": {"base": {"checkout": "nowhere"}, "tip": {"checkout": "nowhere"}}}, open(f, "w"))
        html = index.queued_card(f)
        self.assertIn("testbed m4 · 2 variants × 1 corpus × 2 rounds = 4 cells", html)
        self.assertIn("<code>-f 1 -wi 3 -i 3</code>", html)
        self.assertIn("main", html)
        self.assertIn("-Xmx1g", html)
        self.assertEqual(server.spec_of({"argv": ["ab", "run", "c.json"], "cwd": d}), f)
        self.assertEqual(index.queued_card(os.path.join(d, "missing.json")), "")


if __name__ == "__main__":
    unittest.main()
