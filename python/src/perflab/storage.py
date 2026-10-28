"""Storage of a project's campaigns and runs, by tier, and the cleanup actions of `perflab server`'s admin page.

Tiers:
  results   result.json, iterations.tsv, logs, timelines, gc logs: small (about 120 KB a cell), and kept
  profiles  recordings (.jfr, .trace, .collapsed, xctrace exports) and rendered graphs (the flame graphs beside a
            recording, profdiff's diff-/a-/b- pages): graphs re-render from the recording
  builds    <dir>/.build (launch-mode snapshots) and <dir>/.worktree: rebuildable from the commit

Bytes are allocated bytes (st_blocks * 512), and a file with several hard links counts once. (An APFS clone is a file
of its own to stat, so clones still count once each.)

Actions, each with a dry run that only reports what it would reclaim:
  builds     drop the builds of campaigns and runs that are not active
  graphs     drop rendered graphs
  profiles   drop profiles (recordings and graphs) older than `days`
  delete     delete one campaign or run
A campaign or run with a `.pinned` file is skipped by the bulk actions, and `delete` refuses it. An active one (running
under the server or perflab, being built, or written in the last ACTIVE_SECS) is never touched.
"""
import json, os, re, shutil, time

PIN = ".pinned"
BUILD_DIRS = (".build", ".worktree")
ACTIVE_SECS = 600
RECORDING = re.compile(r"(\.jfr$|\.collapsed$|\.trace$|\.trace\.|\.counters\.xml$|\.toc\.xml$|\.bythread\.xml$)")
PROFDIFF_PAGE = re.compile(r"^(diff|a|b)-.*\.html$")
NOT_GRAPHS = {"timeline.html", "index.html", "compare.html", "report.html"}
TIERS = ("results", "profiles", "builds")


def _alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, TypeError, ValueError):
        return False


def _json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def tier(rel, siblings_have_jfr):
    """The tier of a file by its path relative to its campaign or run, and whether it is a rendered graph."""
    parts = rel.split(os.sep)
    if any(p in BUILD_DIRS for p in parts[:-1]):
        return "builds", False
    name = parts[-1]
    if any(p.endswith(".trace") for p in parts[:-1]) or RECORDING.search(name):
        return "profiles", False
    if name.endswith(".html") and name not in NOT_GRAPHS and (siblings_have_jfr or PROFDIFF_PAGE.match(name)):
        return "profiles", True
    return "results", False


def walk(top, seen):
    """(path, rel, tier, graph, bytes, mtime) of every file under `top`; files in `seen` (dev, inode) are skipped."""
    for dirpath, dirnames, files in os.walk(top):
        has_jfr = any(f.endswith(".jfr") for f in files)
        for f in files:
            p = os.path.join(dirpath, f)
            try:
                st = os.lstat(p)
            except OSError:
                continue
            key = (st.st_dev, st.st_ino)
            if key in seen:
                continue
            seen.add(key)
            t, graph = tier(os.path.relpath(p, top), has_jfr)
            yield p, os.path.relpath(p, top), t, graph, st.st_blocks * 512, st.st_mtime


def active_names(campaigns, jobs_argv=()):
    """Campaigns the project's live files name as running or building, and those a running job's argv names (by name,
    or by a spec file's "name")."""
    names = set()
    r = _json(os.path.join(campaigns, "running.json"))
    if r and r.get("campaign"):
        names.add(r["campaign"])
    b = _json(os.path.join(campaigns, "build.json"))
    if b and _alive(b.get("pid")) and b.get("label"):
        names.add(b["label"].split(":")[0].strip())
        names.add(b["label"].split(os.sep)[0])
    for argv, cwd in jobs_argv:
        for a in argv:
            names.add(a)
            p = os.path.join(cwd or "", a)
            if a.endswith(".json") and os.path.isfile(p):
                spec = _json(p)
                if isinstance(spec, dict) and spec.get("name"):
                    names.add(spec["name"])
                names.add(os.path.splitext(os.path.basename(a))[0])
    return names


def entries(project, campaigns, runs, jobs_argv=(), seen=None, now=None):
    """One entry per campaign and run of a project: its bytes by tier, graphs, newest file, pinned and active."""
    seen = set() if seen is None else seen
    now = now or time.time()
    out = []
    names = active_names(campaigns, jobs_argv) if campaigns and os.path.isdir(campaigns) else set()
    for kind, top in (("campaign", campaigns), ("run", runs)):
        if not top or not os.path.isdir(top):
            continue
        for name in sorted(os.listdir(top)):
            d = os.path.join(top, name)
            if name.startswith(".") or not os.path.isdir(d) or os.path.islink(d):
                continue
            e = {"project": project, "kind": kind, "name": name, "path": d, "pinned": os.path.exists(os.path.join(d, PIN)),
                 "bytes": dict.fromkeys(TIERS, 0), "graphs": 0, "files": 0, "newest": 0}
            for _, rel, t, graph, b, mtime in walk(d, seen):
                e["bytes"][t] += b
                e["graphs"] += b if graph else 0
                e["files"] += 1
                if rel != PIN:  # pinning is not activity
                    e["newest"] = max(e["newest"], mtime)
            e["total"] = sum(e["bytes"].values())
            run_state = _json(os.path.join(d, "run.json")) if kind == "run" else None
            why = ("named by running.json, build.json or a running job" if kind == "campaign" and name in names
                   else "its run.json says running" if run_state and run_state.get("status") == "running" and _alive(run_state.get("pid"))
                   else f"written in the last {ACTIVE_SECS // 60} minutes" if now - e["newest"] < ACTIVE_SECS else None)
            e["active"], e["activeWhy"] = bool(why), why
            out.append(e)
    return out


def scan(projects, jobs_argv=None):
    """Entries of every project: `projects` is [(id, campaigns, runs)], `jobs_argv` {project: [(argv, cwd)]} of its
    running jobs. Largest first."""
    seen = set()
    out = []
    for pid, campaigns, runs in projects:
        out += entries(pid, campaigns, runs, (jobs_argv or {}).get(pid, ()), seen)
    return sorted(out, key=lambda e: -e["total"])


def _targets(action, e, days, now):
    """The paths `action` would remove from entry `e`, with their bytes."""
    d = e["path"]
    if action == "delete":
        return [(d, e["total"])]
    if action == "builds":
        found = []
        for b in BUILD_DIRS:
            p = os.path.join(d, b)
            if os.path.isdir(p) and not os.path.islink(p):
                found.append((p, sum(x[4] for x in walk(p, set()))))
        return found
    found = []
    for p, rel, t, graph, b, mtime in walk(d, set()):
        if t != "profiles":
            continue
        if action == "graphs" and graph or action == "profiles" and now - mtime > days * 86400:
            found.append((p, b))
    # a .trace is a directory: take it whole
    if action == "profiles":
        traces = {}
        for p, b in found:
            parts = os.path.relpath(p, d).split(os.sep)
            for i, part in enumerate(parts[:-1]):
                if part.endswith(".trace"):
                    root = os.path.join(d, *parts[:i + 1])
                    traces[root] = traces.get(root, 0) + b
                    break
            else:
                traces[p] = b
        found = list(traces.items())
    return found


def cleanup(entries_, action, dry_run=True, target=None, days=None, now=None):
    """Applies `action` (builds, graphs, profiles, delete) to the entries, or to the one `target` names
    ({project, kind, name}); returns {"reclaimed": bytes, "removed": [...], "skipped": [{name, why}]}. Bulk actions skip
    pinned entries; nothing touches an active one."""
    if action not in ("builds", "graphs", "profiles", "delete"):
        raise ValueError(f"unknown action {action!r}")
    if action == "profiles" and days is None:
        raise ValueError("profiles needs days")
    if action == "delete" and not target:
        raise ValueError("delete needs a target")
    now = now or time.time()
    chosen = [e for e in entries_ if not target or all(e[k] == target.get(k) for k in ("project", "kind", "name"))]
    if target and not chosen:
        raise ValueError(f"no such {target.get('kind')}: {target.get('name')}")
    result = {"action": action, "dryRun": dry_run, "reclaimed": 0, "removed": [], "skipped": []}
    for e in chosen:
        label = f"{e['project']}/{e['name']}"
        if e["active"]:
            result["skipped"].append({"name": label, "why": "active"})
            continue
        if e["pinned"] and (not target or action == "delete"):
            result["skipped"].append({"name": label, "why": "pinned"})
            continue
        for p, b in _targets(action, e, days, now):
            result["reclaimed"] += b
            result["removed"].append(p)
            if not dry_run:
                if os.path.basename(p) == ".worktree":  # a git worktree: unregistered too, so a resume can add it again
                    from . import branch
                    branch.remove_worktree(os.path.dirname(p), _json(os.path.join(os.path.dirname(p), "branch.json")))
                elif os.path.isdir(p) and not os.path.islink(p):
                    shutil.rmtree(p, ignore_errors=True)
                else:
                    try:
                        os.unlink(p)
                    except FileNotFoundError:
                        pass
    return result


def pin(path, on):
    p = os.path.join(path, PIN)
    if on:
        open(p, "w").close()
    elif os.path.exists(p):
        os.unlink(p)
