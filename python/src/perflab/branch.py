"""Branch campaigns (doc/branch-explore.md): the commits of a range as a campaign's variants, each its own launch-mode
build, explored coarse-first.

    "branch": {"checkout": "<repo>", "range": "<base>..<tip>", "firstParent": true, "env": {"SCALA3_CHECKOUT": "{checkout}"}}

The range is resolved once, oldest first with its base, into <campaign>/branch.json; a resumed campaign keeps it (a
moved ref doesn't change what it measures). Every commit is checked out in turn into one detached worktree of the
campaign, <campaign>/.worktree, so the build tool's incremental state carries over between neighbours and the user's
checkout is left alone; "{checkout}" in env is that worktree. A commit's variant is its short sha.
"""
import hashlib, json, os, subprocess, sys

from . import config

BRANCH = "branch.json"
WORKTREE = ".worktree"
SHORT = 10


def git(repo, *args):
    p = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)
    if p.returncode:
        sys.exit(f"git {' '.join(args)} in {repo}: {p.stderr.strip()}")
    return p.stdout


def _commit(repo, sha):
    sep = "\x1f"
    out = git(repo, "show", "-s", f"--format=%H{sep}%T{sep}%P{sep}%an{sep}%aI{sep}%s", sha).rstrip("\n")
    h, tree, parents, author, date, subject = out.split(sep, 5)
    return {"sha": h, "short": h[:SHORT], "variant": h[:SHORT], "tree": tree, "parents": parents.split(),
            "subject": subject, "author": author, "date": date}


def resolve(repo, range_, first_parent=True):
    """branch.json's content for `range_` (<base>..<tip>) in `repo`: the commits oldest first, the base included."""
    if ".." not in range_:
        sys.exit(f"branch range {range_!r}: expected <base>..<tip>")
    base_ref, tip_ref = range_.split("..", 1)
    base, tip = (git(repo, "rev-parse", "--verify", f"{r}^{{commit}}").strip() for r in (base_ref, tip_ref or "HEAD"))
    shas = git(repo, "rev-list", "--reverse", *(["--first-parent"] if first_parent else []), f"{base}..{tip}").split()
    commits = [_commit(repo, s) for s in [base, *shas]]
    for i, c in enumerate(commits):
        c["index"] = i
        c["merged"] = []
        if first_parent and len(c["parents"]) > 1:
            for s in git(repo, "rev-list", "--reverse", f"{c['parents'][0]}..{c['sha']}").split():
                if s != c["sha"]:
                    m = _commit(repo, s)
                    c["merged"].append({"sha": m["sha"], "subject": m["subject"]})
    return {"checkout": os.path.abspath(repo), "range": range_, "firstParent": first_parent,
            "base": base, "tip": tip, "commits": commits, "order": [commits[i]["variant"] for i in explore(len(commits))]}


def load(out, spec_branch, write=True):
    """branch.json of the campaign in `out`, resolving the spec's range the first time (and keeping it, with `write`)."""
    path = os.path.join(out, BRANCH)
    if os.path.exists(path):
        return json.load(open(path))
    b = resolve(spec_branch["checkout"], spec_branch["range"], spec_branch.get("firstParent", True))
    if write:
        save(out, b)
    return b


def save(out, b):
    path = os.path.join(out, BRANCH)
    if not os.path.exists(path):
        os.makedirs(out, exist_ok=True)
        with open(path, "w") as f:
            json.dump(b, f, indent=2)


def van_der_corput(i):
    """The i-th (from 1) point of the base-2 van der Corput sequence in (0, 1): 1/2, 1/4, 3/4, 1/8, 5/8, ..."""
    x, d = 0.0, 0.5
    while i:
        if i & 1:
            x += d
        i >>= 1
        d /= 2
    return x


def explore(n):
    """Indices 0..n-1 in coarse-first order: both ends, then the interior at van der Corput positions, so after k
    commits the range is covered at a spacing of about n/k."""
    if n <= 2:
        return list(range(n))
    order, seen, i = [0, n - 1], {0, n - 1}, 1
    while len(order) < n:
        j = min(n - 2, max(1, round(van_der_corput(i) * (n - 1))))
        i += 1
        if j not in seen:
            seen.add(j)
            order.append(j)
        elif i > 4 * n:  # rounding collisions on a small range: the rest in order
            order += [k for k in range(n) if k not in seen]
    return order


def cells(rounds, corpora, order):
    """(round, corpus, variant) in explore order: round 1 corpus by corpus, each in `order`; later rounds the same,
    with the order reversed, so drift over the campaign doesn't line up with history."""
    for r in range(1, rounds + 1):
        for corpus in corpora:
            for v in (order if r % 2 else order[::-1]):
                yield r, corpus, v


def build_key(commit, env, template):
    """What a commit's build depends on: its tree, the build's variables and the build command (not the commit, so a
    rebase that leaves a tree alone reuses its build)."""
    h = hashlib.sha1(json.dumps([commit["tree"], sorted(env.items()), template]).encode()).hexdigest()
    return h[:16]


def checkout(out, b, commit):
    """The campaign's worktree with `commit` checked out (made on first use); its path."""
    wt = os.path.join(out, WORKTREE)
    repo = b["checkout"]
    if not os.path.exists(os.path.join(wt, ".git")):
        git(repo, "worktree", "add", "--detach", wt, commit["sha"])
    else:
        git(wt, "checkout", "--detach", "--force", commit["sha"])
    return wt


def env_for(spec_branch, wt):
    return {k: str(x).replace("{checkout}", wt) for k, x in (spec_branch.get("env") or {}).items()}


def remove_worktree(out, b):
    wt = os.path.join(out, WORKTREE)
    if os.path.exists(wt):
        subprocess.run(["git", "-C", b["checkout"], "worktree", "remove", "--force", wt], capture_output=True)


def template():
    return config.get().get("build", "launch") or ""
