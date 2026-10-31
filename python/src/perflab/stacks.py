"""A cell's collapsed stacks of one event, cached beside its recording so that a diff can be curated again (other hints,
another pair) in seconds, without running jfrconv over the recording or writing its collapsed text (which runs to
gigabytes for a kperf event).

The cache is `<cell>/stacks-<event>.gz`: the frames interned once (names as profdiff normalizes them: hidden-class
addresses and thread ids stripped, jfrconv's `_[j]`-style suffixes kept for the graphs' colours), then each distinct
stack as frame ids and its count, as packed integers. A recording with ~100k stacks of ~200 frames takes some tens of
MB. It is rebuilt when the recording is newer, or the format changes.

With `leaf` ("line" or "bci"), jfrconv names every frame with its line (`Class.method:42_[j]`) or bytecode index
(`Class.method@17_[j]`), cached as `stacks-<event>-<leaf>.gz`; `without_lines` makes the plain stacks of those.
"""
import array, gzip, json, os, re

LEAVES = {"line": "--lines", "bci": "--bci"}
LINE = re.compile(r"(?::|@)\d+(?=(?:_\[[a-z0-9]+\])?$)")  # a frame's `:line` or `@bci`, before its kind suffix

FORMAT = 1


def path(cell, event, leaf=None):
    return os.path.join(cell, f"stacks-{event}{'-' + leaf if leaf else ''}.gz")


class Stacks:
    """`frames`: [name]; `stacks`: [(tuple of frame ids, root first; count)]; `ops`, `score` of the run."""

    def __init__(self, frames, stacks, ops, score):
        self.frames, self.stacks, self.ops, self.score = frames, stacks, ops, score

    @property
    def total(self):
        return sum(n for _, n in self.stacks)

    def named(self):
        """(list of names, count) per stack."""
        f = self.frames
        return (([f[i] for i in s], n) for s, n in self.stacks)


def write(f, st):
    lengths, ids, counts = array.array("I"), array.array("I"), array.array("q")
    for s, n in st.stacks:
        lengths.append(len(s))
        ids.extend(s)
        counts.append(n)
    head = {"format": FORMAT, "frames": st.frames, "ops": st.ops, "score": st.score,
            "sizes": [len(lengths), len(ids)], "itemsize": [lengths.itemsize, counts.itemsize]}
    tmp = f + ".tmp"
    with gzip.open(tmp, "wb", compresslevel=6) as out:
        out.write(json.dumps(head).encode() + b"\n")
        for a in (lengths, ids, counts):
            out.write(a.tobytes())
    os.replace(tmp, f)


def read(f):
    with gzip.open(f, "rb") as inp:
        head = json.loads(inp.readline())
        if head.get("format") != FORMAT:
            raise ValueError(f"{f}: format {head.get('format')}, not {FORMAT}")
        ns, ni = head["sizes"]
        arrays = []
        for code, n in (("I", ns), ("I", ni), ("q", ns)):
            a = array.array(code)
            a.frombytes(inp.read(n * a.itemsize))
            arrays.append(a)
    lengths, ids, counts = arrays
    stacks, at = [], 0
    for k, n in zip(lengths, counts):
        stacks.append((tuple(ids[at:at + k]), n))
        at += k
    return Stacks(head["frames"], stacks, head["ops"], head["score"])


class Builder:
    """Interns frames and merges equal stacks as (stack string, count) pairs come, so a recording's collapsed text is
    never held whole."""

    def __init__(self):
        self.index, self.merged = {}, {}

    def add(self, stack, n):
        key = tuple(self.index.setdefault(fr, len(self.index)) for fr in stack.split(";"))
        self.merged[key] = self.merged.get(key, 0) + n

    def done(self, ops, score):
        frames = [None] * len(self.index)
        for fr, i in self.index.items():
            frames[i] = fr
        return Stacks(frames, list(self.merged.items()), ops, score)


def of_lines(pairs, ops, score):
    b = Builder()
    for stack, n in pairs:
        b.add(stack, n)
    return b.done(ops, score)


def without_lines(st):
    """`st` with its frames' lines (or bcis) stripped, and the stacks that become equal merged."""
    names, ids = {}, []
    for fr in st.frames:
        ids.append(names.setdefault(LINE.sub("", fr), len(names)))
    merged = {}
    for s, n in st.stacks:
        k = tuple(ids[i] for i in s)
        merged[k] = merged.get(k, 0) + n
    return Stacks(list(names), list(merged.items()), st.ops, st.score)


def load(cell, event, jfrconv=None, leaf=None):
    """The cell's stacks of `event` (as profdiff labels it: `cycles`, `cache-misses`, `cpu`), from the cache, else from
    its recording through jfrconv (and cached); every frame with its line or bci with `leaf` ("line", "bci")."""
    import glob
    from . import profdiff
    f = path(cell, event, leaf)
    d = profdiff.profile_dir(cell)
    jfrs = glob.glob(os.path.join(d, "**", "*.jfr"), recursive=True)
    if not jfrs:
        raise FileNotFoundError(f"{cell}: no recording")
    if os.path.exists(f) and os.path.getmtime(f) >= os.path.getmtime(jfrs[0]):
        try:
            return read(f)
        except (OSError, ValueError, EOFError):
            pass
    b = Builder()
    r = profdiff.load(cell, event, jfrconv, None, "stacks", keep=False, sink=b.add, extra=[LEAVES[leaf]] if leaf else ())
    st = b.done(r["ops"], r["score"])
    write(f, st)
    return st
