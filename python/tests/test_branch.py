import json, os, subprocess, sys, tempfile, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from perflab import ab, branch, config, jmh, launch  # noqa: E402
from test_perflab import Project  # noqa: E402


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@t", *args],
                          check=True, capture_output=True, text=True).stdout.strip()


def repo_with_history(d):
    """main: c0 (base) - c1 - merge of a feature (f1, f2) - c3; returns the base and tip shas."""
    git(d, "init", "-q", "-b", "main")

    def commit(name):
        with open(os.path.join(d, name), "w") as f:
            f.write(name)
        git(d, "add", name)
        git(d, "commit", "-qm", name)
        return git(d, "rev-parse", "HEAD")

    base = commit("c0")
    commit("c1")
    git(d, "checkout", "-qb", "feature")
    commit("f1")
    commit("f2")
    git(d, "checkout", "-q", "main")
    git(d, "merge", "-q", "--no-ff", "-m", "Merge feature", "feature")
    return base, commit("c3")


class ExploreTest(unittest.TestCase):
    def test_ends_first_then_coarse_to_fine(self):
        self.assertEqual(branch.explore(9), [0, 8, 4, 2, 6, 1, 5, 3, 7])

    def test_every_index_once(self):
        for n in range(0, 40):
            self.assertEqual(sorted(branch.explore(n)), list(range(n)))

    def test_cells_corpus_by_corpus_later_rounds_reversed(self):
        cells = list(branch.cells(2, ["a", "b"], ["x", "y", "z"]))
        self.assertEqual(cells[:6], [(1, "a", "x"), (1, "a", "y"), (1, "a", "z"), (1, "b", "x"), (1, "b", "y"), (1, "b", "z")])
        self.assertEqual(cells[6:9], [(2, "a", "z"), (2, "a", "y"), (2, "a", "x")])

    def test_build_key_is_the_tree_not_the_commit(self):
        a, b = {"tree": "t", "sha": "1"}, {"tree": "t", "sha": "2"}
        self.assertEqual(branch.build_key(a, {"E": "x"}, "sbt"), branch.build_key(b, {"E": "x"}, "sbt"))
        self.assertNotEqual(branch.build_key(a, {"E": "x"}, "sbt"), branch.build_key(a, {"E": "y"}, "sbt"))


class DoneTest(unittest.TestCase):
    def test_an_empty_result_is_not_done(self):
        d = tempfile.mkdtemp()
        self.assertFalse(ab.done(d))
        open(os.path.join(d, "result.json"), "w").close()  # interrupted
        self.assertFalse(ab.done(d))
        with open(os.path.join(d, "result.json"), "w") as f:
            f.write("[]")
        self.assertTrue(ab.done(d))


class ResolveTest(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp()
        self.base, self.tip = repo_with_history(self.repo)

    def test_first_parent_with_what_merges_brought_in(self):
        b = branch.resolve(self.repo, f"{self.base}..main")
        self.assertEqual([c["subject"] for c in b["commits"]], ["c0", "c1", "Merge feature", "c3"])
        self.assertEqual([c["index"] for c in b["commits"]], [0, 1, 2, 3])
        self.assertEqual([m["subject"] for m in b["commits"][2]["merged"]], ["f1", "f2"])
        self.assertEqual(b["tip"], self.tip)
        self.assertEqual(b["order"][:2], [b["commits"][0]["variant"], b["commits"][3]["variant"]])

    def test_every_commit_without_first_parent(self):
        b = branch.resolve(self.repo, f"{self.base}..main", first_parent=False)
        self.assertEqual(len(b["commits"]), 6)


class BranchCampaignTest(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp()
        self.base, self.tip = repo_with_history(self.repo)
        self.p = Project('[build]\njmh = "true {args}"\nlaunch = "python3 build.py {out}"\n[benchmark]\ncorpus = "c"\n')
        # the build records the commit it found in the checkout it was given
        with open(os.path.join(self.p.dir, "build.py"), "w") as f:
            f.write("import json, os, subprocess, sys\n"
                    "co = os.environ['CO']; os.makedirs(co + '/../classes-' + os.path.basename(co), exist_ok=True)\n"
                    "sha = subprocess.run(['git', '-C', co, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()\n"
                    "out = os.path.join(co, 'out'); os.makedirs(out, exist_ok=True); open(out + '/A.class', 'w').write(sha)\n"
                    "json.dump({'mainClass': 'M', 'java': 'java', 'roots': [out], 'classpath': [out],"
                    " 'build': {'checkout': co, 'commit': sha, 'dirty': False}}, open(os.path.join(sys.argv[1], 'launch.json'), 'w'))\n")
        os.chdir(self.p.dir)
        self.addCleanup(os.environ.pop, "PERFLAB_BUILD_MODE", None)
        self.spec_f = os.path.join(self.p.dir, "s.json")
        with open(self.spec_f, "w") as f:
            json.dump({"name": "br", "benchmark": "B", "rounds": 1, "corpora": {"x": "", "y": ""},
                       "branch": {"checkout": self.repo, "range": f"{self.base}..main", "env": {"CO": "{checkout}"}}}, f)

    def test_variants_are_commits_in_explore_order(self):
        spec = ab.Spec(self.spec_f)
        commits = spec.branch_info["commits"]
        self.assertEqual(list(spec.variants), [c["variant"] for c in commits])
        order = [c[3] for c in spec.cells()]
        self.assertEqual(order[:4], [commits[i]["variant"] for i in branch.explore(4)])
        self.assertFalse(os.path.exists(os.path.join(spec.out, branch.BRANCH)))  # not until it runs

    def test_each_commit_is_built_before_its_first_cell(self):
        spec = ab.Spec(self.spec_f)
        events = []
        orig = jmh.run_build

        def stub(cmd, log, *a, **k):
            if "build.py" in cmd:
                events.append(("build", k.get("env", {}).get("CO")))
                return orig(cmd, log, *a, **k)
            events.append(("cell", log))
            if len([e for e in events if e[0] == "cell"]) > 2:
                return 1
            json.dump([{"primaryMetric": {"score": 1.0, "scoreError": 0.1, "scoreUnit": "ms/op"}, "secondaryMetrics": {}}],
                      open(os.path.join(os.path.dirname(log), "result.json"), "w"))
            return 0
        jmh.run_build = stub
        self.addCleanup(setattr, jmh, "run_build", orig)
        self.addCleanup(setattr, ab, "check", ab.check)
        ab.check = lambda *a, **k: None
        with self.assertRaises(SystemExit):
            ab.run(spec, False)
        kinds = [e[0] for e in events]
        self.assertEqual(kinds[:4], ["build", "cell", "build", "cell"])
        self.assertTrue(os.path.exists(os.path.join(spec.out, branch.BRANCH)))
        # each snapshot holds the commit it was built from
        commits = {c["variant"]: c for c in spec.branch_info["commits"]}
        for v in spec.branch_info["order"][:2]:
            key = branch.build_key(commits[v], branch.env_for(spec.branch, os.path.join(spec.out, branch.WORKTREE)), branch.template())
            b = launch.read(os.path.join(spec.out, launch.BUILD_DIR, key, launch.LAUNCH))
            self.assertEqual(open(os.path.join(b["classpath"][0], "A.class")).read(), commits[v]["sha"])

if __name__ == "__main__":
    unittest.main()
