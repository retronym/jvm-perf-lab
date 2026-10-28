"""Branch campaigns (doc/branch-explore.md): the commits of a range as a campaign's variants, each its own launch-mode
build, explored coarse-first.

    "branch": {"checkout": "<repo>", "range": "<base>..<tip>", "firstParent": true, "env": {"SCALA3_CHECKOUT": "{checkout}"}}

The range is resolved once, oldest first with its base, into <campaign>/branch.json; a resumed campaign keeps it (a
moved ref doesn't change what it measures). Every commit is checked out in turn into one detached worktree of the
campaign, <campaign>/.worktree, and the user's checkout is left alone; "{checkout}" in env is that worktree. The
explore order visits far-apart commits first, so consecutive builds are mostly not of neighbours; the build tool's
incremental state still carries over in the worktree, and saves recompiling the modules the two commits share. A
commit's variant is its short sha.

A commit's build is kept in <campaign>/.build/<key> (build_key: its tree, the build's variables and command, and the
harness), the key recorded in builds.json; a commit that does not build is recorded in unbuildable.json.
"""
import hashlib, json, os, shutil, subprocess, sys

from . import config, launch

BRANCH = "branch.json"
WORKTREE = ".worktree"
UNBUILDABLE = "unbuildable.json"
BUILDS = "builds.json"  # {variant: the key of its directory in .build}
FAILED_LOGS = ".unbuildable"  # their build.logs, <variant>.log: results, not builds, so dropping builds keeps them
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


def build_key(commit, env, template, harness=None):
    """What a commit's build depends on: its tree, the build's variables and the build command (not the commit, so a
    rebase that leaves a tree alone reuses its build), then, after a "-", the `harness` it is built with. Without a
    harness, the key campaigns had before builds.json (the same as the first part)."""
    h = hashlib.sha1(json.dumps([commit["tree"], sorted(env.items()), template]).encode()).hexdigest()[:16]
    if harness is None:
        return h
    return h + "-" + hashlib.sha1(json.dumps(harness, sort_keys=True).encode()).hexdigest()[:8]


def harness_part(key):
    return key.split("-", 1)[1] if "-" in key else None


def harness(env):
    """What a build depends on beyond the commit and the build command: the project (perflab.toml's directory) as
    committed and its uncommitted changes, when it is in a git repo, and the JDK the build would find (JAVA_HOME, and
    the `java` on PATH) in the environment it runs in, ours with `env` over it."""
    root = config.get().root
    h = {}
    p = subprocess.run(["git", "-C", root, "rev-parse", "HEAD:./"], capture_output=True, text=True)
    if p.returncode == 0:
        h["tree"] = p.stdout.strip()
        d = subprocess.run(["git", "-C", root, "diff", "HEAD", "--", "."], capture_output=True)
        h["diff"] = hashlib.sha1(d.stdout).hexdigest()
    e = {**os.environ, **env}
    h["javaHome"] = os.path.realpath(e["JAVA_HOME"]) if e.get("JAVA_HOME") else None
    java = shutil.which("java", path=e.get("PATH"))
    h["java"] = os.path.realpath(java) if java else None
    return h


def recorded_key(out, commit, env, template, harness_):
    """The build directory key of `commit` in the campaign `out`, and a warning or None.

    A commit's key is recorded in <out>/builds.json the first time it is built, and wins while its snapshot is kept:
    a campaign measures the builds it started with, even when the harness has changed since (the warning says so).
    A campaign from before builds.json has its snapshots under the key without a harness, which is then recorded.
    Otherwise, the key with the current harness."""
    keys = _read(out, BUILDS)
    v, new = commit["variant"], build_key(commit, env, template, harness_)
    have = lambda k: bool(k) and launch.reusable(os.path.join(out, launch.BUILD_DIR, k))
    key = keys.get(v)
    if not have(key):
        old = build_key(commit, env, template)
        key = old if have(old) else new
    warning = None
    if harness_part(key) and harness_part(key) != harness_part(new):
        warning = f"{commit['short']}'s snapshot was built with another harness (the project or JDK) than this one's; measuring it still"
    elif key == new:
        # (a key from before builds.json says nothing of its harness)
        others = {harness_part(k) for x, k in keys.items() if x != v and have(k)} - {harness_part(new), None}
        if others:
            warning = (f"{commit['short']} is built with another harness (the project or JDK) than earlier commits of this campaign "
                       f"({' '.join(sorted(others))} vs {harness_part(new)})")
    return key, warning


def record_key(out, commit, key):
    keys = _read(out, BUILDS)
    if keys.get(commit["variant"]) != key:
        keys[commit["variant"]] = key
        _write(out, BUILDS, keys)


def _read(out, name):
    try:
        with open(os.path.join(out, name)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _write(out, name, d):
    path = os.path.join(out, name)
    with open(path + ".tmp", "w") as f:
        json.dump(d, f, indent=2)
    os.replace(path + ".tmp", path)


def unbuildable(out):
    """The campaign's commits that did not build: {variant: {"reason": ..., "log": <its build.log, relative to out>}}."""
    return _read(out, UNBUILDABLE)


def set_unbuildable(out, variant, reason=None, log=None):
    """Records that `variant` did not build (keeping its build.log), or, with no `reason`, that it did."""
    u = unbuildable(out)
    if reason is None:
        if u.pop(variant, None) is None:
            return
    else:
        kept = os.path.join(FAILED_LOGS, f"{variant}.log")
        os.makedirs(os.path.join(out, FAILED_LOGS), exist_ok=True)
        if log and os.path.exists(log):
            shutil.copy(log, os.path.join(out, kept))
        u[variant] = {"reason": reason, "log": kept}
    _write(out, UNBUILDABLE, u)


def checkout(out, b, commit):
    """The campaign's worktree with `commit` checked out (made on first use); its path."""
    wt = os.path.join(out, WORKTREE)
    repo = b["checkout"]
    if not os.path.exists(os.path.join(wt, ".git")):
        git(repo, "worktree", "prune")  # a worktree deleted by hand is still registered, and `add` refuses its path
        git(repo, "worktree", "add", "--detach", wt, commit["sha"])
    else:
        git(wt, "checkout", "--detach", "--force", commit["sha"])
    return wt


def env_for(spec_branch, wt):
    return {k: str(x).replace("{checkout}", wt) for k, x in (spec_branch.get("env") or {}).items()}


def remove_worktree(out, b=None):
    """Removes the campaign's worktree, and unregisters it from the repo of `b` (branch.json; without it, or when git
    can't, the directory is just deleted)."""
    wt = os.path.join(out, WORKTREE)
    repo = (b or {}).get("checkout")
    if repo and os.path.exists(wt):
        subprocess.run(["git", "-C", repo, "worktree", "remove", "--force", wt], capture_output=True)
    if os.path.lexists(wt):
        shutil.rmtree(wt, ignore_errors=True)
    if repo:
        subprocess.run(["git", "-C", repo, "worktree", "prune"], capture_output=True)


def template():
    return config.get().get("build", "launch") or ""
