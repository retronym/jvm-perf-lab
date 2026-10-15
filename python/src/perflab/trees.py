"""Campaigns across builds: each variant is a checkout (e.g. a git worktree) with its own perflab.toml, run round by
round, alternating variants; results are gathered into this checkout's campaign directory and reported together.

  perflab trees <spec.json>

The spec is a campaign spec plus "trees": {"<variant>": "<checkout, relative to this one>"}. A variant's JVM flags come
from "variants" (default none). With an sbt build, each checkout needs its sbt server running.
"""
import json, os, shutil, subprocess, sys

from . import config


def run_in(tree, *args):
    """`perflab <args>` with `tree` as the project root (its perflab.toml, its build)."""
    env = {**os.environ, "PERFLAB_ROOT": tree}
    return subprocess.run([sys.executable, "-m", "perflab", *args], cwd=tree, env=env).returncode


def campaigns_of(tree):
    return config.find(tree).campaigns


def tree_spec(spec, variant, rounds, tree):
    s = {k: v for k, v in spec.items() if k != "trees"}
    s["rounds"] = rounds
    s["variants"] = {variant: spec.get("variants", {}).get(variant, "")}
    path = os.path.join(campaigns_of(tree), f"{spec['name']}.{variant}.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(s, open(path, "w"), indent=2)
    return path


def main(argv):
    spec = json.load(open(argv[0]))
    here = config.get().root
    trees = {v: os.path.abspath(os.path.join(here, t)) for v, t in spec["trees"].items()}
    for r in range(1, spec["rounds"] + 1):
        for variant, tree in trees.items():
            if run_in(tree, "ab", "run", tree_spec(spec, variant, r, tree)) != 0:
                sys.exit(f"perflab trees: {variant} round {r} failed ({tree})")
    out = os.path.join(config.get().campaigns, spec["name"])
    for variant, tree in trees.items():
        src = os.path.join(campaigns_of(tree), spec["name"])
        if os.path.abspath(src) == os.path.abspath(out):
            continue
        for corpus in os.listdir(src):
            v = os.path.join(src, corpus, variant)
            if os.path.isdir(v):
                dest = os.path.join(out, corpus, variant)
                shutil.rmtree(dest, ignore_errors=True)
                shutil.copytree(v, dest)
    combined = {k: v for k, v in spec.items() if k != "trees"}
    combined["variants"] = {v: spec.get("variants", {}).get(v, "") for v in trees}
    path = os.path.join(out, "spec.json")
    json.dump(combined, open(path, "w"), indent=2)
    from . import ab
    ab.report(ab.Spec(path))
    return 0
