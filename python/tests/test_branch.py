import json, os, subprocess, sys, tempfile, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ["PERFLAB_SERVER_HOME"] = tempfile.mkdtemp()  # never a real `perflab server`: commands run here, not on its queue
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


class BuildKeyTest(unittest.TestCase):
    def setUp(self):
        self.out = tempfile.mkdtemp()
        self.c = {"tree": "t", "sha": "1", "variant": "v", "short": "v"}

    def snapshot(self, key):
        d = os.path.join(self.out, launch.BUILD_DIR, key)
        os.makedirs(d)
        json.dump({"snapshot": d}, open(os.path.join(d, launch.LAUNCH), "w"))

    def test_the_harness_follows_the_old_key(self):
        old = branch.build_key(self.c, {"E": "x"}, "sbt")
        k1, k2 = (branch.build_key(self.c, {"E": "x"}, "sbt", {"java": j}) for j in ("a", "b"))
        self.assertEqual([k1.split("-")[0], k2.split("-")[0]], [old, old])
        self.assertNotEqual(branch.harness_part(k1), branch.harness_part(k2))
        self.assertIsNone(branch.harness_part(old))

    def test_a_campaign_from_before_builds_json_keeps_its_snapshots(self):
        old = branch.build_key(self.c, {}, "sbt")
        self.snapshot(old)
        self.assertEqual(branch.recorded_key(self.out, self.c, {}, "sbt", {"java": "b"}), (old, None))
        # without its snapshot, the key with the harness
        self.assertEqual(branch.recorded_key(self.out, {**self.c, "tree": "u"}, {}, "sbt", {"java": "b"})[0],
                         branch.build_key({**self.c, "tree": "u"}, {}, "sbt", {"java": "b"}))

    def test_a_recorded_key_wins_while_its_snapshot_is_kept(self):
        k1 = branch.build_key(self.c, {}, "sbt", {"java": "a"})
        self.snapshot(k1)
        branch.record_key(self.out, self.c, k1)
        key, warning = branch.recorded_key(self.out, self.c, {}, "sbt", {"java": "b"})
        self.assertEqual(key, k1)
        self.assertIn("another harness", warning)
        self.assertEqual(branch.recorded_key(self.out, self.c, {}, "sbt", {"java": "a"}), (k1, None))
        # a commit built after the harness changed: the new harness, and a warning
        c2 = {**self.c, "tree": "u", "variant": "w", "short": "w"}
        key, warning = branch.recorded_key(self.out, c2, {}, "sbt", {"java": "b"})
        self.assertEqual(key, branch.build_key(c2, {}, "sbt", {"java": "b"}))
        self.assertIn("earlier commits", warning)
        # the snapshot dropped: built again, with the harness of now
        import shutil
        shutil.rmtree(os.path.join(self.out, launch.BUILD_DIR, k1))
        self.assertEqual(branch.recorded_key(self.out, self.c, {}, "sbt", {"java": "b"}),
                         (branch.build_key(self.c, {}, "sbt", {"java": "b"}), None))

    def test_harness_is_the_jdk_and_the_projects_state(self):
        p = Project('[build]\njmh = "true"\n')
        os.chdir(p.dir)
        h = branch.harness({"JAVA_HOME": p.dir})
        self.assertEqual(h["javaHome"], os.path.realpath(p.dir))
        self.assertNotIn("tree", h)  # not a git repo
        git(p.dir, "init", "-q")
        git(p.dir, "add", ".")
        git(p.dir, "commit", "-qm", "p")
        h1 = branch.harness({})
        with open(os.path.join(p.dir, "perflab.toml"), "a") as f:
            f.write("# changed\n")
        h2 = branch.harness({})
        self.assertEqual(h1["tree"], h2["tree"])
        self.assertNotEqual(h1["diff"], h2["diff"])


class DoneTest(unittest.TestCase):
    def test_an_empty_result_is_not_done(self):
        d = tempfile.mkdtemp()
        self.assertFalse(ab.done(d))
        open(os.path.join(d, "result.json"), "w").close()  # interrupted
        self.assertFalse(ab.done(d))
        for partial in ("[]", '[{"primaryMetric": {"sco'):  # no result, or a truncated one
            with open(os.path.join(d, "result.json"), "w") as f:
                f.write(partial)
            self.assertFalse(ab.done(d))
        with open(os.path.join(d, "result.json"), "w") as f:
            f.write('[{"primaryMetric": {"score": 1.0}}]')
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

    def test_a_worktree_deleted_by_hand_is_made_again(self):
        out = tempfile.mkdtemp()
        b = branch.resolve(self.repo, f"{self.base}..main")
        wt = branch.checkout(out, b, b["commits"][0])
        subprocess.run(["rm", "-rf", wt], check=True)  # still registered with the repo
        self.assertEqual(branch.checkout(out, b, b["commits"][1]), wt)
        self.assertEqual(git(wt, "rev-parse", "HEAD"), b["commits"][1]["sha"])

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
        keys = json.load(open(os.path.join(spec.out, branch.BUILDS)))
        for v in spec.branch_info["order"][:2]:
            b = launch.read(os.path.join(spec.out, launch.BUILD_DIR, keys[v], launch.LAUNCH))
            self.assertEqual(open(os.path.join(b["classpath"][0], "A.class")).read(), commits[v]["sha"])

    def run_all(self, *flags):
        """Runs the campaign with every cell succeeding; the commits it built."""
        built = []
        orig = jmh.run_build

        def stub(cmd, log, *a, **k):
            if "build.py" in cmd:
                built.append(git(k["env"]["CO"], "rev-parse", "HEAD")[:branch.SHORT])
                return orig(cmd, log, *a, **k)
            json.dump([{"primaryMetric": {"score": 1.0, "scoreError": 0.1, "scoreUnit": "ms/op"}, "secondaryMetrics": {}}],
                      open(os.path.join(os.path.dirname(log), "result.json"), "w"))
            return 0
        jmh.run_build, check = stub, ab.check
        ab.check = lambda *a, **k: None
        try:
            ab.run(ab.Spec(self.spec_f), False, *flags)
        finally:
            jmh.run_build, ab.check = orig, check
        return built

    def test_a_commit_that_does_not_build_is_skipped_and_recorded(self):
        # c1's build fails; the merge's builds a dirty checkout
        with open(os.path.join(self.p.dir, "build.py")) as f:
            good = f.read()
        with open(os.path.join(self.p.dir, "build.py"), "w") as f:
            f.write("import os, sys\nco = os.environ['CO']\n"
                    "if os.path.exists(co + '/c1') and not os.path.exists(co + '/f1'): print('no'); sys.exit(1)\n"
                    + good.replace("'dirty': False", "'dirty': os.path.exists(co + '/f1') and not os.path.exists(co + '/c3')"))
        spec = ab.Spec(self.spec_f)
        commits = spec.branch_info["commits"]
        c1, merge = commits[1]["variant"], commits[2]["variant"]
        self.assertEqual(sorted(self.run_all()), sorted(c["variant"] for c in commits))
        u = branch.unbuildable(spec.out)
        self.assertEqual(sorted(u), sorted([c1, merge]))
        self.assertIn("exit 1", u[c1]["reason"])
        self.assertIn("dirty", u[merge]["reason"])
        self.assertIn("no", open(os.path.join(spec.out, u[c1]["log"])).read())
        for v in (c1, merge):  # no cells, and nothing kept in .build
            self.assertFalse(os.path.exists(os.path.join(spec.out, "x", v)))
        self.assertEqual(len(os.listdir(os.path.join(spec.out, launch.BUILD_DIR))), 2)
        for v in (commits[0]["variant"], commits[3]["variant"]):
            self.assertTrue(ab.done(spec.cell_dir("y", v, 1)))
        # a resume doesn't try them again; --retry-unbuildable does, and a commit that builds now leaves the list
        self.assertEqual(self.run_all(), [])
        with open(os.path.join(self.p.dir, "build.py"), "w") as f:
            f.write(good)
        self.assertEqual(sorted(self.run_all(True)), sorted([c1, merge]))
        self.assertEqual(branch.unbuildable(spec.out), {})
        self.assertTrue(ab.done(spec.cell_dir("x", c1, 1)))

    def test_a_resume_keeps_its_snapshots_whatever_the_harness(self):
        import shutil
        spec = ab.Spec(self.spec_f)
        self.assertEqual(len(self.run_all()), 4)
        # as a campaign from before builds.json: its snapshots under the keys without a harness
        keys = json.load(open(os.path.join(spec.out, branch.BUILDS)))
        os.unlink(os.path.join(spec.out, branch.BUILDS))
        for k in keys.values():
            os.rename(os.path.join(spec.out, launch.BUILD_DIR, k), os.path.join(spec.out, launch.BUILD_DIR, k.split("-")[0]))
        shutil.rmtree(os.path.join(spec.out, "x"))
        os.environ["JAVA_HOME"], old = self.p.dir, os.environ.get("JAVA_HOME")  # and the JDK changed
        self.addCleanup(lambda: os.environ.__setitem__("JAVA_HOME", old) if old else os.environ.pop("JAVA_HOME", None))
        self.assertEqual(self.run_all(), [])
        self.assertEqual(json.load(open(os.path.join(spec.out, branch.BUILDS))), {v: k.split("-")[0] for v, k in keys.items()})
        self.assertTrue(all(ab.done(spec.cell_dir("x", c["variant"], 1)) for c in spec.branch_info["commits"]))

    def test_the_view_shows_a_failed_build(self):
        from perflab import branchview
        spec = ab.Spec(self.spec_f)
        branch.save(spec.out, spec.branch_info)
        log = os.path.join(tempfile.mkdtemp(), "build.log")
        open(log, "w").write("boom")
        v = spec.branch_info["commits"][1]["variant"]
        branch.set_unbuildable(spec.out, v, "the build step failed (exit 1)", log)
        u = branchview.branch_view(spec.out, os.path.dirname(spec.out))["unbuildable"]
        self.assertEqual(u, {v: {"reason": "the build step failed (exit 1)", "log": f"br/.unbuildable/{v}.log"}})
if __name__ == "__main__":
    unittest.main()
