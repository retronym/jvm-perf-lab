"""Profiles of a branch campaign's commits, and their differential flame graphs (doc/branch-explore.md, decision 4).

  perflab branch profile <spec.json | campaign> [<commit>...] [--diff] [--dry-run]
  perflab branch diff    <spec.json | campaign> <commit-a> <commit-b> [--corpus <c>] [--force]

A profiler perturbs the score, so a branch campaign's profiles are a campaign of their own beside it,
<campaigns>/<name>.profile: an ordinary campaign (its card, cells, flame graphs and timelines are on the index like any
other) whose spec.json is "profileOf" the branch campaign. It has the branch campaign's commits (branch.json) and its
builds (<name>/.build/<key>), so a commit measured there is not built again, and one profiled first is built once for
both. Its variants are the commits profiled so far; `profile` adds the commits it is given (default: all of them, in
explore order) and runs their missing cells. A commit is named by its sha, any unique prefix of it, or a ref.

The branch spec's "profiles" sets them up (every key optional):

  "profiles": {"profile": "async:cpu,alloc",   # as `perflab run --profile`; cpu and alloc need no kperf helper
               "corpora": ["scalaz"],          # default: the first corpus
               "jmhArgs": "-wi 5 -i 3",        # default: each corpus's JMH arguments in the campaign; or {corpus: args}
               "rounds": 1, "kperf": "<socket>", "lib": "<libasyncProfiler>"}

`diff` writes profdiff's output for two commits' profile cells, older first by default as the arguments give them,
per profiled corpus, to <name>.profile/diff-<corpus>-<a>-<b>/ (compare.html: each event's graphs of a and b and the
differential graphs both ways, as tabs) with pair.json naming the two cells. It is cached by that pair of cells (and
their recordings): run again, it does nothing unless they changed or --force. `profile --diff` with two commits runs
both commits' profiles and then the diff, which is what the branch view's "Profile & diff these two" queues.
"""
import argparse, glob, json, os, sys

from . import ab, branch, branchview, config, jmh, regraph

SUFFIX = branchview.PROFILE_SUFFIX
DEFAULT_PROFILE = "async:cpu,alloc"
PAIR = "pair.json"


def load_spec(arg):
    """(spec, path) of a branch campaign, given its spec file or its name (its spec.json in <campaigns>/<name>)."""
    path = arg if os.path.isfile(arg) else os.path.join(config.get().campaigns, arg, "spec.json")
    if not os.path.isfile(path):
        sys.exit(f"{arg}: neither a spec file nor a campaign in {config.get().campaigns}")
    s = json.load(open(path))
    if not s.get("branch"):
        sys.exit(f"{path}: not a branch campaign (it has no \"branch\")")
    return s, path


def branch_out(s):
    return os.path.join(config.get().campaigns, s["name"])


def profile_out(name):
    return os.path.join(config.get().campaigns, name + SUFFIX)


def branch_info(s, path):
    """The campaign's branch.json, resolving its range now (and keeping it) if the campaign has not run yet. The copy
    of a spec in its campaign has its checkout relative to the original's directory, so branch.json's is used."""
    f = os.path.join(branch_out(s), branch.BRANCH)
    copy = os.path.join(branch_out(s), "spec.json")
    if not os.path.exists(copy):  # as `ab run` keeps it: the profile campaign reads the build's env from it
        os.makedirs(branch_out(s), exist_ok=True)
        import shutil
        shutil.copy(path, copy)
        with open(os.path.join(branch_out(s), ab.SOURCE), "w") as out:
            out.write(os.path.abspath(path) + "\n")
    if os.path.exists(f):
        return json.load(open(f))
    b = {**s["branch"], "checkout": os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(path)), s["branch"]["checkout"]))}
    return branch.load(branch_out(s), b)


def find_commit(b, ref):
    """The commit of the branch `ref` names: a variant, a unique prefix of a sha (4 characters or more), or a ref."""
    cs = b["commits"]
    hits = [c for c in cs if c["variant"] == ref] or ([c for c in cs if c["sha"].startswith(ref.lower())] if len(ref) >= 4 else [])
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        sys.exit(f"{ref}: ambiguous, {', '.join(c['short'] for c in hits)}")
    import subprocess
    p = subprocess.run(["git", "-C", b["checkout"], "rev-parse", "--verify", "-q", f"{ref}^{{commit}}"], capture_output=True, text=True)
    hits = [c for c in cs if c["sha"] == p.stdout.strip()]
    if not hits:
        sys.exit(f"{ref}: not a commit of {b['range']}")
    return hits[0]


def profile_spec(s, b, variants):
    """The profile campaign's spec: the branch spec's benchmark, JVM and corpora under its "profiles" settings, with
    `variants` (commits) in history order."""
    p = s.get("profiles") or {}
    corpora = p.get("corpora") or list(s["corpora"])[:1]
    jmh_args = p.get("jmhArgs")
    unknown = [c for c in corpora if c not in s["corpora"] and not (isinstance(jmh_args, str) or c in (jmh_args or {}))]
    if unknown:
        sys.exit(f"profiles: corpora {unknown} are not the campaign's, and \"jmhArgs\" gives no JMH arguments for them")
    args = {c: (jmh_args if isinstance(jmh_args, str) else (jmh_args or {}).get(c, s["corpora"].get(c, ""))) for c in corpora}
    index = {c["variant"]: c for c in b["commits"]}
    variants = sorted(set(variants), key=lambda v: index[v]["index"])
    out = {"name": s["name"] + SUFFIX, "profileOf": s["name"], "benchmark": s.get("benchmark"),
           "profile": p.get("profile", DEFAULT_PROFILE), "kperf": p.get("kperf"), "lib": p.get("lib", s.get("lib")),
           "jvm": s.get("jvm"), "jvmArgs": s.get("jvmArgs"), "rounds": p.get("rounds", 1), "corpora": args,
           "variants": {v: "" for v in variants}, "loadgate": s.get("loadgate"), "perUnit": s.get("perUnit"),
           "description": f"Profiles of the commits of **{s['name']}**, run apart from its measurement (a profiler perturbs "
                          "the score), from its builds. `perflab branch profile` adds commits; `perflab branch diff` compares two.",
           "variantDescriptions": {v: index[v]["subject"] for v in variants}}
    return {k: x for k, x in out.items() if x is not None}


def profile(argv):
    ap = argparse.ArgumentParser(prog="perflab branch profile")
    ap.add_argument("spec")
    ap.add_argument("commits", nargs="*")
    ap.add_argument("--diff", action="store_true", help="then diff the two commits' profiles (with exactly two)")
    ap.add_argument("--dry-run", action="store_true")
    x = ap.parse_args(argv)
    if x.diff and len(x.commits) != 2:
        sys.exit("--diff needs exactly two commits")
    s, path = load_spec(x.spec)
    b = branch_info(s, path)
    picked = [find_commit(b, r)["variant"] for r in x.commits] or list(b["order"])
    out = profile_out(s["name"])
    spec_f = os.path.join(out, "spec.json")
    try:
        before = json.load(open(spec_f))
    except (OSError, ValueError):
        before = {}
    ps = profile_spec(s, b, [*(before.get("variants") or {}), *picked])
    if ps != before:  # as `ab run`, a dry run too: the campaign keeps its spec
        os.makedirs(out, exist_ok=True)
        with open(spec_f, "w") as f:
            json.dump(ps, f, indent=2)
    spec = ab.Spec(spec_f)
    spec.only = set(picked)
    ab.run(spec, x.dry_run)
    if x.diff and not x.dry_run:
        return diff_pair(s, *picked)
    return 0


def profile_cell(out, corpus, variant):
    """A commit's profile cell on `corpus` (its first round with a recording), or None."""
    for cell in sorted(glob.glob(os.path.join(out, corpus, variant, "*")), key=lambda c: (len(c), c)):
        if os.path.basename(cell).isdigit() and ab.done(cell) and glob.glob(os.path.join(cell, "**", "*.jfr"), recursive=True):
            return cell
    return None


def diff_dir(out, corpus, a, b):
    return os.path.join(out, f"diff-{corpus}-{a}-{b}")


def pair_key(out, corpus, a, b, ca, cb):
    jfrs = [sorted(glob.glob(os.path.join(c, "**", "*.jfr"), recursive=True))[0] for c in (ca, cb)]
    return {"a": a, "b": b, "corpus": corpus, "cells": [os.path.relpath(c, out) for c in (ca, cb)],
            "recordings": [[os.path.relpath(j, out), os.path.getmtime(j)] for j in jfrs]}


def run_profdiff(argv):
    from . import profdiff
    return profdiff.main(argv)


def diff_pair(s, a, b, corpora=None, force=False):
    """profdiff of commits `a` and `b` (variants) on each corpus both have profile cells on; 0 when any was diffed."""
    out = profile_out(s["name"])
    try:
        ps = json.load(open(os.path.join(out, "spec.json")))
    except (OSError, ValueError):
        sys.exit(f"{s['name']} has no profiles yet: perflab branch profile {s['name']} {a} {b}")
    done = 0
    for corpus in corpora or list(ps["corpora"]):
        ca, cb = profile_cell(out, corpus, a), profile_cell(out, corpus, b)
        if not (ca and cb):
            print(f"{corpus}: no profile of {' or '.join(v for v, c in ((a, ca), (b, cb)) if not c)}; "
                  f"perflab branch profile {s['name']} {a} {b}", file=sys.stderr)
            continue
        dest = diff_dir(out, corpus, a, b)
        key = pair_key(out, corpus, a, b, ca, cb)
        pf = os.path.join(dest, PAIR)
        try:
            cached = json.load(open(pf)) == key and os.path.exists(os.path.join(dest, "compare.html"))
        except (OSError, ValueError):
            cached = False
        if cached and not force:
            print(f"{corpus}: {os.path.join(dest, 'compare.html')} (cached)")
            done += 1
            continue
        os.makedirs(dest, exist_ok=True)
        if os.path.exists(pf):
            os.unlink(pf)  # until this diff is complete
        jfrconv = jmh.jfrconv(jmh.async_lib(ps.get("lib")))
        for label, _ in regraph.events_of(ca):
            run_profdiff(["--event", label.removeprefix("hw-"), "--jfrconv", jfrconv, ca, cb, dest])
        with open(pf, "w") as f:
            json.dump(key, f, indent=2)
        print(f"{corpus}: {os.path.join(dest, 'compare.html')}")
        done += 1
    if done:
        from . import index
        try:
            index.rebuild(config.get().campaigns)
        except Exception as e:  # the index is a convenience
            print(f"index not rebuilt: {e}", file=sys.stderr)
    return 0 if done else 1


def diff(argv):
    ap = argparse.ArgumentParser(prog="perflab branch diff")
    ap.add_argument("spec")
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--corpus", action="append", help="only this corpus (repeatable); default: every profiled one")
    ap.add_argument("--force", action="store_true", help="diff again even when the cached diff is of the same cells")
    x = ap.parse_args(argv)
    s, path = load_spec(x.spec)
    b = branch_info(s, path)
    return diff_pair(s, find_commit(b, x.a)["variant"], find_commit(b, x.b)["variant"], x.corpus, x.force)


def main(argv):
    if not argv or argv[0] not in ("profile", "diff"):
        sys.exit(__doc__)
    return (profile if argv[0] == "profile" else diff)(argv[1:])
