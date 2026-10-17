"""A campaign's spec history. A campaign is edited and rerun (more rounds, other JMH arguments), so each distinct spec is
kept as <campaign>/specs/<timestamp>.json when a run uses it, and each cell records the version it ran under in
<cell>/spec.version. The index lists the versions with the changes between them and flags comparisons that mix versions.
"""
import json, os, time

DIR, CELL_FILE, ENV = "specs", "spec.version", "PERFLAB_SPEC_VERSION"


def _load(path):
    return json.load(open(path))


def versions(campaign):
    """Version ids of the campaign, oldest first."""
    d = os.path.join(campaign, DIR)
    return sorted(f[:-5] for f in os.listdir(d) if f.endswith(".json")) if os.path.isdir(d) else []


def record(campaign, spec_path):
    """The id of the campaign's spec version for the spec at `spec_path`: the latest one when identical, else a new snapshot."""
    spec = _load(spec_path)
    known = versions(campaign)
    if known and _load(os.path.join(campaign, DIR, known[-1] + ".json")) == spec:
        return known[-1]
    vid = time.strftime("%Y%m%d-%H%M%S")
    while vid in known:  # several edits within one second
        vid += "x"
    os.makedirs(os.path.join(campaign, DIR), exist_ok=True)
    json.dump(spec, open(os.path.join(campaign, DIR, vid + ".json"), "w"), indent=2)
    return vid


def tag(cell, version):
    os.makedirs(cell, exist_ok=True)
    open(os.path.join(cell, CELL_FILE), "w").write(version)


def of_cell(cell):
    try:
        return open(os.path.join(cell, CELL_FILE)).read().strip() or None
    except OSError:
        return None


def _flat(v, prefix=""):
    if isinstance(v, dict) and v:
        out = {}
        for k, x in v.items():
            out.update(_flat(x, f"{prefix}.{k}" if prefix else k))
        return out
    return {prefix: v}


def diff(old, new):
    """Human-readable changes from spec `old` to spec `new` (dicts), one string per changed key."""
    a, b = _flat(old), _flat(new)
    out = []
    for k in sorted(set(a) | set(b)):
        if k not in b:
            out.append(f"{k}: removed (was {a[k]!r})")
        elif k not in a:
            out.append(f"{k}: added {b[k]!r}")
        elif a[k] != b[k]:
            out.append(f"{k}: {a[k]!r} → {b[k]!r}")
    return out


def history(campaign):
    """[(version id, spec, changes from the previous version)], oldest first."""
    out, prev = [], None
    for v in versions(campaign):
        s = _load(os.path.join(campaign, DIR, v + ".json"))
        out.append((v, s, diff(prev, s) if prev is not None else []))
        prev = s
    return out
