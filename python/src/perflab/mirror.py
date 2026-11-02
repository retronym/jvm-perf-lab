"""The live mirror of a remote job (doc/remote-workers.md): what the index and the queue page draw while a local job
runs, for a job on a remote worker. The worker's heartbeat carries what changed of its <campaigns>'s running.json,
loadgate.json and build.json, and of the files of the cell being run that the fork timeline reads; the coordinator
writes them under <campaigns>/.live/<worker>/, at the paths they have on the worker, so the pages read a remote job's
running fork as a local one's, from another base.

An entry is {"path", "off", "data"}: the file is its first `off` bytes and then `data` (bytes as latin-1, so offsets are
exact). The cell's files grow by appending, so a beat sends what was appended since the last one; a file that shrank
or was replaced (a new fork's gc.log) is sent again from 0, as are the small JSON files whenever they change.
{"path", "gone": true} removes one. A heartbeat's entries are at most BUDGET bytes, the rest following on the next.
"""
import json, os, shutil, time

from . import ab, jmh, loadgate, timeline

DIR = ".live"  # in the coordinator's <campaigns>: <worker>/ (a mirror per worker), index.json
INDEX = "index.json"  # {worker: {"job", "at"}}: the mirrors being written, for the index's live panels to find
BUDGET = 256 * 1024  # bytes of data per heartbeat
STATE = (ab.RUNNING_NAME, loadgate.STATE_NAME, jmh.BUILD_STATE)  # <campaigns>'s live files, sent whole
# the cell's files the fork timeline reads (timeline.js fetchCell)
CELL = ("iterations.tsv", "timeline.tsv", "load.tsv", "profile.txt", "jvm-events.tsv", "gc.log") + tuple(f"gc.log.{i}" for i in range(timeline.GC_LOGS))


class Sender:
    """The worker's side: what changed under `root` (its <campaigns>) since the last beat."""

    def __init__(self, root):
        self.root = root
        self.sent = {}  # path -> (inode, bytes the coordinator has, mtime_ns)

    def forget(self, paths):
        """The coordinator lacks what was sent of these (it was restarted, or the mirror cleared): from 0 next time."""
        for p in paths or ():
            self.sent.pop(p, None)

    def changes(self, budget=BUDGET):
        out, cell = [], None
        r = _read_json(os.path.join(self.root, ab.RUNNING_NAME))
        if r and isinstance(r.get("cell"), str):
            cell = os.path.normpath(r["cell"].rstrip("/"))
        paths = list(STATE) + ([os.path.join(cell, f) for f in CELL] if cell and not cell.startswith("..") else [])
        for p in paths:
            f = os.path.join(self.root, p)
            try:
                st = os.stat(f)
            except OSError:
                if p in STATE and p in self.sent:
                    out.append({"path": p, "gone": True})
                    del self.sent[p]
                continue
            ino, have, mtime = self.sent.get(p, (None, 0, None))
            whole = p in STATE
            if whole and (ino, mtime) == (st.st_ino, st.st_mtime_ns) and have == st.st_size:
                continue
            off = 0 if whole or ino != st.st_ino or st.st_size < have else have
            if st.st_size == off and p in self.sent:
                continue
            n = min(st.st_size - off, budget)
            if n < st.st_size - off and whole:
                continue  # a state file larger than what is left of the budget: whole, next time
            with open(f, "rb") as fh:
                fh.seek(off)
                data = fh.read(n)
            budget -= len(data)
            out.append({"path": p, "off": off, "data": data.decode("latin-1")})
            self.sent[p] = (st.st_ino, off + len(data), st.st_mtime_ns)
            if budget <= 0:
                break
        return out


def root(campaigns, worker):
    return os.path.join(campaigns, DIR, worker)


def _safe(p):
    p = os.path.normpath(p or "")
    return p if p and not os.path.isabs(p) and not any(c in ("..", "") or c.startswith(".") for c in p.split(os.sep)) else None


def apply(campaigns, worker, job, entries):
    """The coordinator's side: writes a heartbeat's entries into the worker's mirror; the paths it could not (a gap: it
    lacks the bytes before `off`), for the worker to send again from 0."""
    d, resync = root(campaigns, worker), []
    for e in entries or ():
        p = _safe(e.get("path")) if isinstance(e, dict) else None
        if not p:
            continue
        f = os.path.join(d, p)
        if e.get("gone"):
            try:
                os.unlink(f)
            except OSError:
                pass
            continue
        off, data = int(e.get("off") or 0), str(e.get("data") or "").encode("latin-1", errors="replace")
        try:
            if off and (not os.path.exists(f) or os.path.getsize(f) < off):
                resync.append(p)
                continue
            os.makedirs(os.path.dirname(f), exist_ok=True)
            if p in STATE:  # whole: replaced at once, never read half-written
                with open(f + ".tmp", "wb") as fh:
                    fh.write(data)
                os.replace(f + ".tmp", f)
                continue
            with open(f, "r+b" if os.path.exists(f) else "wb") as fh:
                fh.truncate(off)
                fh.seek(off)
                fh.write(data)
        except OSError:
            resync.append(p)
    _index(campaigns, worker, {"job": job, "at": time.time()})
    return resync


def clear(campaigns, worker):
    """The worker's job is over (or its lease ran out): its mirror goes."""
    shutil.rmtree(root(campaigns, worker), ignore_errors=True)
    _index(campaigns, worker, None)


def _index(campaigns, worker, entry):
    f = os.path.join(campaigns, DIR, INDEX)
    idx = _read_json(f) or {}
    if entry is None and worker not in idx:
        return
    if entry is None:
        idx.pop(worker, None)
    else:
        idx[worker] = entry
    try:
        os.makedirs(os.path.dirname(f), exist_ok=True)
        with open(f + ".tmp", "w") as fh:
            json.dump(idx, fh)
        os.replace(f + ".tmp", f)
    except OSError:
        pass


def _read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None
