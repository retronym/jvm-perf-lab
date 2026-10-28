"""Campaigns across builds: each variant is a checkout (e.g. a git worktree) with its own perflab.toml, run round by
round, alternating variants; results are gathered into this checkout's campaign directory and reported together.

  perflab trees <spec.json> [--dry-run]   --dry-run: each checkout's `ab run --dry-run` for the first round

The spec is a campaign spec plus "trees": {"<variant>": "<checkout, relative to this one>"}. A variant's JVM flags come
from "variants" (default none). With an sbt build, each checkout needs its sbt server running.
"""
import json, os, shutil, subprocess, sys

from . import config, loadgate, specs


def run_in(tree, *args, version=None):
    """`perflab <args>` with `tree` as the project root (its perflab.toml, its build)."""
    env = {**os.environ, "PERFLAB_ROOT": tree, **({specs.ENV: version} if version else {})}
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


def gather(spec, trees, out):
    """Copy each variant's cells from its checkout's campaign into `out`, merging into what is already there."""
    for variant, tree in trees.items():
        src = os.path.join(campaigns_of(tree), spec["name"])
        if os.path.abspath(src) == os.path.abspath(out) or not os.path.isdir(src):
            continue
        for corpus in os.listdir(src):
            v = os.path.join(src, corpus, variant)
            if os.path.isdir(v):
                shutil.copytree(v, os.path.join(out, corpus, variant), dirs_exist_ok=True)


def main(argv):
    spec = json.load(open(argv[0]))
    here = config.get().root
    trees = {v: os.path.abspath(os.path.join(here, t)) for v, t in spec["trees"].items()}
    if "--dry-run" in argv:
        for variant, tree in trees.items():
            print(f"perflab trees: {variant} in {tree}", flush=True)
            if run_in(tree, "ab", "run", tree_spec(spec, variant, 1, tree), "--dry-run") != 0:
                sys.exit(f"perflab trees: {variant}: dry run failed ({tree})")
        return 0
    out = os.path.join(config.get().campaigns, spec["name"])
    # one live view from the start: the combined campaign and its spec (so the index knows the planned cells) exist
    # before the first round, are served from this checkout, and gain each variant's cells as its round finishes
    combined = dict(spec)  # "trees" kept for the index's variants panel; `ab` ignores it
    combined["variants"] = {v: spec.get("variants", {}).get(v, "") for v in trees}
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "spec.json")
    json.dump(combined, open(path, "w"), indent=2)
    version = specs.record(out, argv[0])  # the spec as given, trees and all; each tree's cells are tagged with it
    from . import index, serve, transcript
    try:
        transcript.say(f"perflab trees: index (updates after each round): {serve.ensure()}")
    except Exception as e:  # the index is a convenience; never let it stop a campaign
        transcript.say(f"perflab trees: index not served: {e}")
    # the checkouts' loadgate waits show on this checkout's index, the one being watched
    os.environ[loadgate.LIVE_ENV] = config.get().campaigns
    for r in range(1, spec["rounds"] + 1):
        for variant, tree in trees.items():
            transcript.say(f"perflab trees: round {r} {variant} in {tree}")
            if run_in(tree, "ab", "run", tree_spec(spec, variant, r, tree), version=version) != 0:
                sys.exit(f"perflab trees: {variant} round {r} failed ({tree})")
            gather(spec, trees, out)
            json.dump(combined, open(path, "w"), indent=2)  # a tree that is this checkout writes its own spec.json over it
            try:
                index.build(config.get().campaigns)
            except Exception as e:
                print(f"perflab trees: index not rebuilt: {e}", flush=True)
    from . import ab
    ab.report(ab.Spec(path))
    return 0
