"""Machine code of JIT compilations (hsdis), per cell, and two variants' code of a method compared (doc/asm.md).

  perflab asm capture <campaign | spec.json> --method <Class::method>... [--corpus c]... [--name <n>] [--iterations 2]
                      [--local] [--dry-run]
                                              an asm capture of a campaign: its spec, its builds, one fork, the
                                              methods printed (spec "asm", "asmOf"); queued like `ab run`
  perflab asm list <campaign> [--corpus c] [--variant v] [--round r] [--method m]
                                              a capture's compilations, per cell
  perflab asm show <campaign> <variant> --method m [--compile-id n] [--raw]
                                              one compilation's code, normalised, with its source lines
  perflab asm diff <campaign> <a> <b> --method m [--corpus c] [--round r] [--compile-id-a n] [--compile-id-b n]
                                              the two variants' code side by side by source line, with counts, to
                                              <campaign>/asm-diff-<method>-<a>-<b>.html (and .json)
  perflab asm hsdis [--jvm <java>]            whether a JDK has hsdis, and how to install it

A spec with "asm": ["Class::method", ...] runs its forks with -XX:CompileCommand=print for each method, its tty
output (the disassembly) in <cell>/vm-<pid>.log rather than jmh.log, and after the fork splits it into
<cell>/asm/<method>/<compile id>-t<level>[-osr].s with <cell>/asm/index.json listing every compilation. Printing
slows the fork and can change what is compiled: an asm capture's scores are not for timing, and the capture is a
campaign of its own ("asmOf" the campaign it explains, whose builds it reuses).

A method is compiled several times (tier 3, tier 4, again after a deopt, OSR) and can be overloaded: the default
compilation of a (method, signature) is its last top-tier one that is not OSR. The diff groups each compilation's
instructions by their source position, the inlining path of the debug info (`; - Class::method@bci (line N)`) as
(method, line) pairs from the compiled method in, so that two builds align on source even where their lambdas are
numbered differently; it counts instructions, loads, stores, stack spills and fills, calls, branches and safepoint
polls per group, and shades the groups by their share of the samples of an async profile of the parent campaign
(same source key; the capture's own forks are not the timed ones).
"""
import argparse, collections, difflib, glob, gzip, html, json, os, re, shlex, subprocess, sys

from . import config

esc = html.escape
INDEX = "index.json"  # in <cell>/asm
LOG = "vm-%p.log"  # the fork's -XX:LogFile, in the cell

# hsdis -------------------------------------------------------------------------------------------------------------


def _release(home):
    rel = {}
    try:
        for line in open(os.path.join(home, "release")):
            k, eq, v = line.strip().partition("=")
            if eq:
                rel[k] = v.strip().strip('"')
    except OSError:
        pass
    return rel


def hsdis_name(home):
    rel = _release(home)
    arch = {"arm64": "aarch64", "x86_64": "amd64"}.get(rel.get("OS_ARCH", ""), rel.get("OS_ARCH") or os.uname().machine)
    arch = {"arm64": "aarch64", "x86_64": "amd64"}.get(arch, arch)
    osn = rel.get("OS_NAME") or os.uname().sysname
    ext = "dylib" if osn.lower() in ("darwin", "macos") else "dll" if osn.lower().startswith("win") else "so"
    return f"hsdis-{arch}.{ext}"


def java_home(java):
    return os.path.dirname(os.path.dirname(os.path.realpath(java)))


def find_hsdis(java):
    """The hsdis library the JVM at `java` loads (it looks in its lib/server, then lib), or None."""
    home = java_home(java)
    name = hsdis_name(home)
    for d in ("lib/server", "lib", "jre/lib/server", "jre/lib"):
        p = os.path.join(home, d, name)
        if os.path.exists(p):
            return p
    return None


def install_hint(java):
    return f"HSDIS_JDKS={java_home(java)} mise run tools:hsdis   (in jvm-perf-lab: builds {hsdis_name(java_home(java))} on capstone, into its lib/)"


def check_hsdis(java):
    """None when `java` has hsdis, else what to do about it."""
    if find_hsdis(java):
        return None
    return f"{java} has no {hsdis_name(java_home(java))}: without it, -XX:CompileCommand=print prints hex. Install it: {install_hint(java)}"


# capture -----------------------------------------------------------------------------------------------------------


def jvm_flags(methods, dest):
    """The JVM arguments that print `methods`' compilations into <dest>/vm-<pid>.log, out of the fork's stdout."""
    # DebugNonSafepoints: debug info at every pc the compiler can give it for, not only at safepoints, so that more
    # instructions have a source line (async-profiler turns it on too, so the profiles' lines are the same kind)
    out = ["-XX:+UnlockDiagnosticVMOptions", "-XX:+DebugNonSafepoints", "-XX:+LogVMOutput", "-XX:-DisplayVMOutput",
           f"-XX:LogFile={os.path.join(dest, LOG)}", "-XX:CompileCommand=quiet"]
    return out + [f"-XX:CompileCommand=print,{m}" for m in methods]


PRINT = re.compile(r"<print_nmethod compile_id='(\d+)' compiler='(\w+)' level='(\d+)'(?: stamp='([\d.]+)')?")
HEADER = re.compile(r"^Compiled method \((\w+)\)\s+(\d+)\s+(\d+)\s+([%sbn! ]*?)\s*(\d)\s+(\S+?)(?: @ (\d+))? \((\d+) bytes\)\s*$")
SIG = re.compile(r"# \{method\} \{0x[0-9a-f]+\} '([^']*)' '([^']*)' in '([^']*)'")
UNESCAPE = (("&apos;", "'"), ("&quot;", '"'), ("&lt;", "<"), ("&gt;", ">"), ("&amp;", "&"))


def _unescape(s):
    for a, b in UNESCAPE:
        s = s.replace(a, b)
    return s


def _safe(s):
    return re.sub(r"[^\w.$:<>-]", "_", s).replace(":", "_").replace("<", "_").replace(">", "_")


STDOUT_START = re.compile(r"^=+ [\w-]+-compiled nmethod =+$")


def nmethods(lines):
    """The printed compilations in a HotSpot -XX:LogFile (<print_nmethod> elements), or in a fork's stdout (from a
    `=== ...-compiled nmethod ===` line to `[/Disassembly]`, as jmh.log has them without LogVMOutput), as
    (attributes, text lines)."""
    cur, xml = None, False
    for line in lines:
        line = line.rstrip("\n")
        if cur is None:
            m = PRINT.search(line)
            if m:
                xml = True
                cur = ({"compileId": int(m.group(1)), "compiler": m.group(2), "level": int(m.group(3)),
                        "stamp": float(m.group(4)) if m.group(4) else None}, [])
            elif STDOUT_START.match(line):
                xml = False
                cur = ({}, [line])
            continue
        if xml and line.startswith("</print_nmethod>"):
            yield cur
            cur = None
        elif not xml and line.startswith("[/Disassembly]"):
            cur[1].append(line)
            yield cur
            cur = None
        elif not (xml and line.startswith("<writer ")):
            cur[1].append(_unescape(line) if xml else line)
    if cur:
        yield cur


def split(cell, logs=None):
    """Splits a cell's vm-*.log into <cell>/asm/<method>/<id>-t<level>[-osr].s and writes <cell>/asm/index.json; the
    logs are gzipped. Returns the index (a list of compilations), or None without logs. A log that says hsdis did not
    load raises RuntimeError."""
    given = logs is not None
    logs = sorted(logs or glob.glob(os.path.join(cell, "vm-*.log")))
    if not logs:
        return None
    out = os.path.join(cell, "asm")
    os.makedirs(out, exist_ok=True)
    index = []
    for lp in logs:
        pid = re.search(r"vm-(?:pid)?(\d+)\.log", lp)  # %p is pid<n> in a LogFile name
        with open(lp, errors="replace") as f:
            for attrs, text in nmethods(f):
                hdr = next((HEADER.match(t) for t in text if t.startswith("Compiled method")), None)
                if not hdr:
                    continue
                if any("Could not load hsdis" in t for t in text[:40]) or not any(INSN.match(t) for t in text[:400]):
                    raise RuntimeError(f"{lp}: compile {attrs['compileId']} has no disassembly: hsdis did not load")
                sig = next((SIG.search(t) for t in text if "# {method}" in t), None)
                method = hdr.group(6)
                attrs = attrs or {"compileId": int(hdr.group(3)), "compiler": hdr.group(1).lower(), "level": int(hdr.group(5)),
                                  "stamp": int(hdr.group(2)) / 1000}
                c = {**attrs, "method": method, "signature": sig.group(2) if sig else None,
                     "bytes": int(hdr.group(8)), "osr": int(hdr.group(7)) if hdr.group(7) else None,
                     "flags": hdr.group(4).strip(), "pid": int(pid.group(1)) if pid else None}
                name = f"{c['compileId']}-t{c['level']}" + ("-osr" if c["osr"] is not None else "") + ".s"
                d = os.path.join(out, _safe(method))
                os.makedirs(d, exist_ok=True)
                with open(os.path.join(d, name), "w") as w:
                    w.write("\n".join(text).strip("\n") + "\n")
                c["file"] = os.path.relpath(os.path.join(d, name), cell)
                code = parse("\n".join(text))
                c["counts"] = code["totals"]["main"]
                c["instructions"] = c["counts"]["insns"]
                index.append(c)
    index.sort(key=lambda c: (c["method"], c.get("pid") or 0, c["compileId"]))
    with open(os.path.join(out, INDEX), "w") as f:
        json.dump(index, f, indent=1)
    write_cell_page(cell)
    for lp in [] if given else logs:
        with open(lp, "rb") as src, gzip.open(lp + ".gz", "wb") as dst:
            dst.write(src.read())
        os.unlink(lp)
    return index


def load_index(cell):
    try:
        return json.load(open(os.path.join(cell, "asm", INDEX)))
    except (OSError, ValueError):
        return None


def matches(c, method):
    """Whether compilation `c` is of `method`: `Class::name`, a dotted suffix of it (`SourceLanguage$::apply`), or
    with its signature (`Class::name(J...)Z`)."""
    want, _, sig = method.partition("(")
    full = c["method"]
    ok = full == want or full.endswith("." + want) or full.endswith("$" + want) or full.split(".")[-1] == want
    return ok and (not sig or c.get("signature") == "(" + sig)


def default(comps):
    """Of one method's compilations, the one to compare: the last top-tier one that is not OSR (else the last)."""
    top = max((c["level"] for c in comps), default=0)
    best = [c for c in comps if c["level"] == top and c.get("osr") is None] or comps
    return max(best, key=lambda c: (c.get("pid") or 0, c["compileId"]))


def select(cell, method, compile_id=None):
    """{(method, signature): compilation} of `method` in a cell, by default the default one of each overload."""
    idx = load_index(cell) or []
    comps = [c for c in idx if matches(c, method)]
    if compile_id is not None:
        comps = [c for c in comps if c["compileId"] == int(compile_id)]
    by = collections.defaultdict(list)
    for c in comps:
        by[(c["method"], c.get("signature"))].append(c)
    return {k: default(v) for k, v in by.items()}


# parsing -----------------------------------------------------------------------------------------------------------

INSN = re.compile(r"^\s+0x([0-9a-f]+):\s+(\S+)[ \t]*([^;]*?)\s*(?:;(.*))?$")
COMMENT = re.compile(r"^\s+;(.*)$")
SECTION = re.compile(r"^\[([^\]/][^\]]*)\]\s*$")
SCOPE = re.compile(r"-\s+(?:\(reexecute\)\s+)?(\S+?)::(\S+?)@(-?\d+)(?:\s+\(line (-?\d+)\))?")
BYTECODE = re.compile(r"\*(\w+)\b(.*?)(?:\{|$)")
RELOC = re.compile(r"\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}")
HEX = re.compile(r"(#?-?)0x([0-9a-f]+)")
OUT_OF_LINE = ("Stub Code", "Exception Handler", "Deopt Handler Code")

BRANCH_A64 = re.compile(r"^(b(\.\w+)?|cbn?z|tbn?z|br|ret|bc\.\w+)$")
CALL = re.compile(r"^(bl|blr|blraa\w*|call\w*)$")
BRANCH_X86 = re.compile(r"^(j\w+|ret\w*)$")


def kind(op, args):
    """The classes of an instruction: load, store, spill (a store to the stack), fill (a load from it), call, branch,
    nop. aarch64 by mnemonic; x86 by its memory operand's side."""
    k = set()
    if op == "nop":
        k.add("nop")
    elif CALL.match(op):
        k.add("call")
    elif BRANCH_A64.match(op) or BRANCH_X86.match(op):
        k.add("branch")
    elif op.startswith("ld") and not op.startswith(("ldadd", "ldclr", "ldset", "ldeor")):
        k.add("load")
    elif op.startswith("st") and op not in ("stc", "std", "sti"):
        k.add("store")
    elif "[" in args or "ptr" in args:  # x86: the memory operand's side
        dst = args.split(",")[0]
        k.add("store" if "[" in dst else "load")
    stack = re.search(r"\[(sp|rsp)\b", args)
    if stack and "store" in k:
        k.add("spill")
    if stack and "load" in k:
        k.add("fill")
    return k


def norm_scope_name(cls, name):
    """A frame's (class, method) without what differs between two builds of the same source: lambda numbers."""
    f = f"{cls}::{name}"
    f = re.sub(r"\$anonfun\$\d+", "$anonfun", f)
    f = re.sub(r"\$\$Lambda[/$][\w./$]*", "$$Lambda", f)
    f = re.sub(r"lambda\$(\w+)\$\d+", r"lambda$\1", f)
    return f


def parse(text):
    """A compilation's printout: its instructions (address, op, args, comment, section, scope, bytecode, kinds), basic
    blocks, and totals over its main code and its out-of-line sections."""
    insns, section = [], "code"
    for line in text.splitlines():
        m = INSN.match(line)
        if m and section != "constants":
            insns.append({"addr": int(m.group(1), 16), "op": m.group(2), "args": m.group(3).strip(),
                          "comment": [m.group(4).strip()] if m.group(4) and m.group(4).strip() else [],
                          "section": section, "scope": None})
            continue
        m = COMMENT.match(line)
        if m and insns:
            insns[-1]["comment"].append(m.group(1).strip())
            continue
        m = SECTION.match(line)
        if m:
            s = m.group(1)
            if s in OUT_OF_LINE:
                section = s
            elif s.startswith("Constant Pool"):
                section = "constants"
            elif s == "Verified Entry Point":
                section = "code"
            elif s in ("Entry Point", "Instructions begin"):
                section = "entry"
    lo = min((i["addr"] for i in insns), default=0)
    hi = max((i["addr"] for i in insns), default=0)
    for i in insns:
        scopes = [m for c in i["comment"] for m in SCOPE.finditer(c)]
        if scopes:  # innermost first, as HotSpot prints them; kept outermost first
            i["scope"] = [(norm_scope_name(s.group(1), s.group(2)), int(s.group(4)) if s.group(4) else None,
                           int(s.group(3))) for s in reversed(scopes)]
        bc = next((BYTECODE.search(c) for c in i["comment"] if c.startswith("*")), None)
        i["bytecode"] = (bc.group(1) + bc.group(2).rstrip()) if bc else None
        relocs = [r for c in i["comment"] for r in RELOC.findall(c)]
        i["reloc"] = [_norm_reloc(r) for r in relocs if r not in ("other",) and "=Oop" not in r and "reexecute=" not in r
                      and not r.startswith("[")]
        i["kinds"] = sorted(kind(i["op"], i["args"]) | ({"poll"} if any(r.startswith("poll") for r in relocs) else set()))
        i["target"] = None
        if "branch" in i["kinds"] or "call" in i["kinds"]:
            t = HEX.search(i["args"])
            if t and lo <= int(t.group(2), 16) <= hi:
                i["target"] = int(t.group(2), 16)
    # a constant built in a register by mov + movk (aarch64): an address, which differs between runs
    for j, i in enumerate(insns):
        if i["op"] == "movk":
            reg = i["args"].split(",")[0]
            i["built"] = True
            for k in range(j - 1, max(-1, j - 4), -1):
                p = insns[k]
                if p["op"] not in ("mov", "movz", "movk") or p["args"].split(",")[0] != reg:
                    break
                p["built"] = True
    # basic blocks: a leader starts each section, follows a branch, or is a branch target
    targets = {i["target"] for i in insns if i["target"] is not None and "branch" in i["kinds"]}
    block, prev = -1, None
    for i in insns:
        if prev is None or i["section"] != prev["section"] or i["addr"] in targets or "branch" in prev["kinds"]:
            block += 1
        i["block"] = block
        prev = i
    labels = {}
    for i in insns:
        if i["addr"] in targets and i["addr"] not in labels:
            labels[i["addr"]] = f"L{len(labels)}"
    # an instruction without debug info takes the next one's in its block (the annotated pc ends the code it covers),
    # else the last one's before it; those before any (the frame's setup) stay without
    nxt = None
    for i in reversed(insns):
        if i["scope"]:
            nxt = i
        elif nxt is not None and nxt["block"] == i["block"] and nxt["section"] == i["section"]:
            i["scope_from"] = nxt["scope"]
    last = None
    for i in insns:
        if i["section"] != "code":
            i.pop("scope_from", None)
        elif i["scope"]:
            last = i
        else:
            i["scope"] = i.pop("scope_from", None) or (last["scope"] if last else None)
        i.pop("scope_from", None)
        i["norm"] = normalise(i, labels, lo, hi)
        i.pop("built", None)
    if not any(i["section"] == "code" for i in insns):  # no verified entry (a static method's code starts at [Entry Point])
        for i in insns:
            if i["section"] == "entry":
                i["section"] = "code"
    totals = {"main": counts([i for i in insns if i["section"] == "code"]),
              "entry": counts([i for i in insns if i["section"] == "entry"]),
              "outOfLine": counts([i for i in insns if i["section"] not in ("code", "entry")])}
    return {"insns": insns, "labels": {f"{a:#x}": l for a, l in labels.items()}, "blocks": block + 1, "totals": totals}


def _norm_reloc(r):
    r = re.sub(r"\{method\} \{0x[0-9a-f]+\} '([^']*)' '([^']*)' in '([^']*)'", lambda m: f"{m.group(3).replace('/', '.')}::{m.group(1)}{m.group(2)}", r)
    r = re.sub(r"0x[0-9a-f]{5,}", "ADDR", r)
    return r.strip()


def normalise(i, labels, lo, hi):
    """`op args` with what differs between two builds' code of the same source replaced: branch targets by block
    labels, addresses and the immediates that build them (instructions carrying a relocation) by ADDR/IMM."""
    args = i["args"]
    reloc = bool(i["reloc"])

    def sub(m):
        v = int(m.group(2), 16)
        if lo <= v <= hi and v in labels:
            return labels[v]
        if lo <= v <= hi + 0x10000:
            return m.group(1).replace("-", "") + "ADDR"
        if v >= 0x10000 or reloc:
            return m.group(1).replace("-", "") + ("ADDR" if v >= 0x10000 else "IMM")
        return m.group(0)
    args = HEX.sub(sub, args)
    if i.get("built"):
        args = re.sub(r"#-?(0x)?[0-9a-f]+\b", "#IMM", args)
    if (reloc or i.get("built")) and i["op"] in ("movk", "movz", "mov", "movabs"):
        args = re.sub(r"#-?\d+\b", "#IMM", args)
    s = (i["op"] + " " + re.sub(r"\s+", " ", args)).strip()
    if i["reloc"]:
        s += "  ; " + ", ".join(i["reloc"])
    return s


KINDS = ("insns", "load", "store", "spill", "fill", "call", "branch", "poll", "nop")


def counts(insns):
    c = dict.fromkeys(KINDS, 0)
    for i in insns:
        c["insns"] += 1
        for k in i["kinds"]:
            if k in c:
                c[k] += 1
    return c


def scope_key(scope):
    """A group's key: the inlining path as (method, line) pairs, outermost first."""
    return tuple((m, l) for m, l, _ in scope) if scope else ()


def scope_label(key):
    if not key:
        return "(before any debug info: the frame's setup)"
    return " → ".join(f"{m.split('.')[-1]}:{l if l is not None else '?'}" for m, l in key)


def groups(code):
    """The main code's instructions per source group, in order of their first instruction; and the out-of-line ones."""
    g = collections.OrderedDict()
    for i in code["insns"]:
        k = ("<" + i["section"] + ">",) if i["section"] != "code" else scope_key(i["scope"])
        g.setdefault(k, []).append(i)
    return g


# compare -----------------------------------------------------------------------------------------------------------


def offsets(ka, kb, wa=None, wb=None):
    """Per method, the shift of its source lines from build a to build b: the one under which the most code (by
    instructions at each line) lines up. A patch that adds lines above a method moves all of its lines alike."""
    wa, wb = wa or {}, wb or {}
    la, lb = collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
    for keys, w, acc in ((ka, wa, la), (kb, wb, lb)):
        for k in keys:
            if k and isinstance(k[0], tuple):
                for m, l in k:
                    if l is not None:
                        acc[m][l] += w.get(k, 1)
    out = {}
    for m in la.keys() & lb.keys():
        best = max({b - a for a in la[m] for b in lb[m]},
                   key=lambda d: (sum(min(n, lb[m].get(a + d, 0)) for a, n in la[m].items()), -abs(d)))
        out[m] = best
    return out


def _shift(k, off):
    if not k or not isinstance(k[0], tuple):
        return k
    return tuple((m, l + off.get(m, 0) if l is not None else None) for m, l in k)


def align(ka, kb, wa=None, wb=None):
    """Pairs two compilations' groups: the same inlining path of methods at the same lines, after shifting each
    method's lines in a by its offset to b (where the patch moved the source). Returns [(key a or None, key b or None)]
    in a's order, b's own after the a group they follow in b. `wa`, `wb`: instructions per group, to weigh offsets."""
    off = offsets(ka, kb, wa, wb)
    kb_set = set(kb)
    pa = {k: _shift(k, off) for k in ka if _shift(k, off) in kb_set}
    out, seen_b = [], set(pa.values())
    for k in ka:
        out.append((k, pa.get(k)))
    pos = {b: j for j, (a, b) in enumerate(out) if b is not None}
    after = -1
    for k in kb:
        if k in pos:
            after = pos[k]
            continue
        if k in seen_b:
            continue
        out.insert(after + 1, (None, k))
        pos = {b: j for j, (a, b) in enumerate(out) if b is not None}
        after = pos[k]
    return out


def compare(code_a, code_b, hot_a=None, hot_b=None):
    """Two compilations side by side per source group: counts and a diff of their normalised instructions."""
    ga, gb = groups(code_a), groups(code_b)
    rows = []
    for ka, kb in align(list(ga), list(gb), {k: len(v) for k, v in ga.items()}, {k: len(v) for k, v in gb.items()}):
        k = ka if ka is not None else kb
        ia, ib = ga.get(ka, []), gb.get(kb, [])
        sa, sb = [i["norm"] for i in ia], [i["norm"] for i in ib]
        ops = []
        for tag, a1, a2, b1, b2 in difflib.SequenceMatcher(None, sa, sb, autojunk=False).get_opcodes():
            ops.append({"tag": tag, "a": [_insn_out(i) for i in ia[a1:a2]], "b": [_insn_out(i) for i in ib[b1:b2]]})
        ool = bool(k and isinstance(k[0], str))
        label = k[0] if ool else scope_label(k) if ka is None or kb is None or ka == kb else _moved_label(ka, kb)
        rows.append({"keyA": _key_out(ka), "keyB": _key_out(kb), "label": label, "outOfLine": ool,
                     "a": counts(ia), "b": counts(ib), "same": sa == sb, "ops": ops,
                     "hotA": (hot_a or {}).get(ka), "hotB": (hot_b or {}).get(kb)})
    return {"groups": rows, "totals": {"a": code_a["totals"], "b": code_b["totals"]},
            "blocks": {"a": code_a["blocks"], "b": code_b["blocks"]}}


def _key_out(k):
    if k is None:
        return None
    return [{"method": m, "line": l} for m, l in k] if k and isinstance(k[0], tuple) else list(k)


def _moved_label(ka, kb):
    return " → ".join(f"{m.split('.')[-1]}:{la}" + (f"/{lb}" if la != lb else "") for (m, la), (_, lb) in zip(ka, kb))


def _insn_out(i):
    return {"addr": f"{i['addr']:#x}", "op": i["op"], "args": i["args"], "norm": i["norm"], "kinds": i["kinds"],
            "block": i["block"], "bytecode": i["bytecode"],
            "scope": [{"method": m, "line": l, "bci": b} for m, l, b in (i["scope"] or [])]}


# hot path: an async profile of the parent campaign, by the same source key -------------------------------------------

FRAME = re.compile(r"^(.*?)(?::(\d+))?_\[(\w)\]$")


def _profile_name(asm_method):
    """`a.b.C$D::m` as async-profiler names the frame: `a/b/C$D.m` (jfrconv collapsed) -> one dotted form for both."""
    return asm_method.replace("/", ".").replace("::", ".")


def hot(cells, method, jfrconv=None, event="cycles"):
    """{group key: share of the samples of `method`'s compiled unit} over async cells: each sample whose innermost
    compiled unit (a `_[j]` frame and the `_[i]` frames above it) is `method`, by the unit's inlining path of
    (method, line). The share is of the unit's samples, summed over the cells."""
    from . import profdiff
    want = _profile_name(method.split("(")[0])
    acc = collections.Counter()

    def sink(stack, n):
        frames = stack.split(";")
        root = None
        for j in range(len(frames) - 1, -1, -1):
            m = FRAME.match(frames[j])
            if m and m.group(3) == "j":
                root = j
                break
        if root is None:
            return
        path = []
        for f in frames[root:]:
            m = FRAME.match(f)
            if not m or (path and m.group(3) != "i"):
                break
            path.append((norm_scope_name(*_split_frame(m.group(1))), int(m.group(2)) if m.group(2) else None))
        if not path or not _same_method(path[0][0], want):
            return
        acc[tuple(path)] += n
    read = 0
    for c in cells:
        try:
            profdiff.load(c, event, jfrconv, None, "asm", keep=False, sink=sink, extra=("--lines",))
            read += 1
        except Exception as e:  # no profile or a broken one: no shading, the diff stands
            print(f"[asm] no hot path from {c}: {e}", file=sys.stderr)
    if not read:
        return None
    total = sum(acc.values())
    return {k: v / total for k, v in acc.items()} if total else {}


def _split_frame(f):
    f = f.replace("/", ".")
    cls, _, name = f.rpartition(".")
    return cls, name


def _same_method(a, want):
    return a.replace("::", ".") == want or a.replace("::", ".").endswith("." + want.split(".", 1)[-1]) and a.split("::")[-1] == want.rsplit(".", 1)[-1]


def shade(hot_, keys):
    """Attributes each sampled path to the longest prefix that is a group of the code; what has none is under None."""
    out = collections.Counter()
    ks = set(keys)
    for path, w in hot_.items():
        p = path
        while p and p not in ks:
            p = p[:-1]
        out[p if p else None] += w
    return dict(out)


def is_capture(cell):
    """Whether a cell is of an asm capture (its campaign's spec has "asm"): its forks printed code, and were slower."""
    try:
        return bool(json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(cell)))), "spec.json"))).get("asm"))
    except (OSError, ValueError, AttributeError):
        return False


def refuse_timing(a, b):
    """Refuses (SystemExit) to compare an asm capture's cell with another campaign's: printing slows the fork."""
    ca, cb = is_capture(a), is_capture(b)
    if ca != cb:
        raise SystemExit(f"{a if ca else b} is an asm capture's (its forks printed machine code, which slows them): "
                         "not comparable with a timed run; compare its code with `perflab asm diff`")


# campaign glue -----------------------------------------------------------------------------------------------------


def campaign_dir(campaign):
    if os.path.isdir(campaign):
        return os.path.abspath(campaign)
    if campaign.endswith(".json") and os.path.exists(campaign):
        return os.path.join(config.get().campaigns, json.load(open(campaign))["name"])
    return os.path.join(config.get().campaigns, campaign)


def cells_of(d, corpus=None, variant=None, rnd=None):
    for c in sorted(glob.glob(os.path.join(d, "*", "*", "*"))):
        co, v, r = c.split(os.sep)[-3:]
        if not r.isdigit() or co.startswith("."):
            continue
        if (corpus and co != corpus) or (variant and v != variant) or (rnd and int(r) != int(rnd)):
            continue
        if os.path.exists(os.path.join(c, "asm", INDEX)):
            yield co, v, int(r), c


def cell_of(d, variant, corpus=None, rnd=None):
    cs = list(cells_of(d, corpus, variant, rnd))
    if not cs:
        raise LookupError(f"{os.path.basename(d)}: no asm capture of {variant}" + (f" in {corpus}" if corpus else "")
                          + (f" round {rnd}" if rnd else "") + " (a spec with \"asm\"; `perflab asm capture`)")
    return cs[0]


def code_of(cell, comp):
    return parse(open(os.path.join(cell, comp["file"])).read())


def parent_of(d):
    """The directory of an asm capture's parent campaign (its spec's "asmOf"), or None."""
    try:
        parent = json.load(open(os.path.join(d, "spec.json"))).get("asmOf")
    except (OSError, ValueError):
        return None
    return os.path.join(os.path.dirname(d), parent) if parent else None


def parent_jfrconv(pd):
    """The jfrconv of the parent's async-profiler (its spec's "lib", else the lab's), as `ab diff` reads it with."""
    from . import jmh
    try:
        lib = json.load(open(os.path.join(pd, "spec.json"))).get("lib")
    except (OSError, ValueError):
        lib = None
    return jmh.jfrconv(jmh.async_lib(lib))


def parent_cells(d, corpus, variant):
    """The async-profiled cells of the asm capture's parent campaign (its spec's "asmOf") for one variant."""
    pd = parent_of(d)
    if not pd:
        return []
    out = []
    for c in sorted(glob.glob(os.path.join(pd, corpus, variant, "*"))):
        try:
            if open(os.path.join(c, "profile.txt")).read().startswith("async") and os.path.exists(os.path.join(c, "result.json")):
                out.append(c)
        except OSError:
            pass
    return out


def diff(campaign, a, b, method, corpus=None, rnd=None, compile_id_a=None, compile_id_b=None, hot_path=True, write=True):
    """Variants `a` and `b`'s code of `method` compared (per overload); with `write`, the page and its JSON in the
    campaign directory. Returns the JSON."""
    d = campaign_dir(campaign)
    ca, cb = cell_of(d, a, corpus, rnd), cell_of(d, b, corpus or None, rnd)
    sa, sb = select(ca[3], method, compile_id_a), select(cb[3], method, compile_id_b)
    if not sa or not sb:
        missing = [v for v, s in ((a, sa), (b, sb)) if not s]
        raise LookupError(f"no compilation of {method} in {', '.join(missing)}'s capture (`perflab asm list {os.path.basename(d)}`)")
    pairs = [(k, sa[k], sb[k]) for k in sa if k in sb]
    if not pairs and len(sa) == 1 and len(sb) == 1:  # the signature changed between the builds
        pairs = [(next(iter(sa)), *sa.values(), *sb.values())]
    if not pairs:
        raise LookupError(f"{method}: no overload in both ({sorted(sa)} vs {sorted(sb)}); give its signature")
    out = {"campaign": os.path.basename(d), "a": a, "b": b, "method": method, "corpus": ca[0],
           "cells": {"a": os.path.relpath(ca[3], d), "b": os.path.relpath(cb[3], d)}, "hotFrom": None, "methods": []}
    for (m, sig), xa, xb in pairs:
        code_a, code_b = code_of(ca[3], xa), code_of(cb[3], xb)
        ha = hb = None
        if hot_path:
            pa, pb = parent_cells(d, ca[0], a), parent_cells(d, cb[0], b)
            keys_a, keys_b = list(groups(code_a)), list(groups(code_b))
            jc = parent_jfrconv(parent_of(d)) if pa or pb else None
            ha, hb = (hot(pa, m, jc) if pa else None), (hot(pb, m, jc) if pb else None)
            for cell, h in ((ca[3], ha), (cb[3], hb)):
                if h is not None:
                    save_hot(cell, m, h, pa if cell == ca[3] else pb)
            ha = shade(ha, keys_a) if ha is not None else None
            hb = shade(hb, keys_b) if hb is not None else None
            if pa or pb:
                out["hotFrom"] = {"a": [os.path.relpath(c, os.path.dirname(d)) for c in pa],
                                  "b": [os.path.relpath(c, os.path.dirname(d)) for c in pb]}
        unplaced = {"a": ha.pop(None, 0.0) if ha is not None else None, "b": hb.pop(None, 0.0) if hb is not None else None}
        r = compare(code_a, code_b, ha, hb)
        if ha is not None or hb is not None:
            r["hotUnplaced"] = unplaced
        r.update(method=m, signature=sig, compilations={"a": _brief(xa), "b": _brief(xb)},
                 others={"a": [_brief(c) for c in load_index(ca[3]) if c["method"] == m and c.get("signature") == sig],
                         "b": [_brief(c) for c in load_index(cb[3]) if c["method"] == m and c.get("signature") == sig]})
        out["methods"].append(r)
    if write:
        for cell in {ca[3], cb[3]}:
            write_cell_page(cell)
        base = os.path.join(d, f"asm-diff-{_safe(method.split('(')[0].split('.')[-1])}-{a}-{b}")
        with open(base + ".json", "w") as f:
            json.dump(out, f)
        with open(base + ".html", "w") as f:
            f.write(page(out, d))
        out["page"] = base + ".html"
    return out


def _brief(c):
    return {k: c.get(k) for k in ("compileId", "compiler", "level", "osr", "bytes", "instructions", "stamp", "pid", "file")}


# the page ----------------------------------------------------------------------------------------------------------

CSS = """
main{max-width:1500px;margin:0 auto;padding:12px 20px}
table.t{border-collapse:collapse;font-size:12.5px;margin:8px 0}
table.t td,table.t th{padding:2px 8px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
table.t td:first-child,table.t th:first-child{text-align:left}
.up{color:var(--bad,#b3261e)} .down{color:var(--good,#1b7f3b)}
details.g{border:1px solid var(--line);border-radius:6px;margin:6px 0;background:var(--card,transparent)}
details.g>summary{cursor:pointer;padding:4px 8px;font-size:13px;display:flex;gap:12px;align-items:baseline}
details.g>summary .lab{font-family:ui-monospace,monospace;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.heat{display:inline-block;width:56px;height:9px;background:var(--line);border-radius:2px;position:relative;vertical-align:middle}
.heat i{position:absolute;left:0;top:0;bottom:0;background:#e8590c;border-radius:2px}
.code{display:grid;grid-template-columns:1fr 1fr;gap:0 12px;font:12px/1.45 ui-monospace,monospace;padding:4px 8px}
.code div{white-space:pre;overflow:hidden;text-overflow:ellipsis}
.code .del{background:rgba(220,60,60,.13)} .code .ins{background:rgba(40,160,80,.15)} .code .rep{background:rgba(230,170,30,.15)}
.code .spill{font-weight:600} .code .call{color:#5b4bc4} .code .k{color:var(--muted)}
.muted{color:var(--muted)} code{font-size:12px}
"""


def _delta(a, b):
    d = b - a
    cls = "up" if d > 0 else "down" if d < 0 else "muted"
    return f'<span class="{cls}">{d:+d}</span>' if d else '<span class="muted">0</span>'


def _line(i, side):
    if i is None:
        return "<div></div>"
    cls = " ".join(k for k in ("spill", "fill", "call") if k in i["kinds"])
    bc = f'  <span class="k">{esc(i["bytecode"])}</span>' if i.get("bytecode") and "call" in i["kinds"] else ""
    return f'<div class="{side} {cls}" title="{esc(i["addr"])} block {i["block"]}">{esc(i["norm"])}{bc}</div>'


def page(out, d):
    from . import ui
    A, B = out["a"], out["b"]
    parts = [f"<p class=muted>asm capture <b>{esc(out['campaign'])}</b>, {esc(out['corpus'])}: "
             f"<code>{esc(out['cells']['a'])}</code> vs <code>{esc(out['cells']['b'])}</code>. Printed code from a fork "
             f"run with <code>CompileCommand=print</code>, not a timed one. Groups are the debug info's inlining path "
             f"(method:line, outermost first); instructions are normalised (addresses, branch targets as block labels).</p>"]
    hf = out.get("hotFrom")
    if hf and (hf["a"] or hf["b"]):
        parts.append(f"<p class=muted>Heat: share of the compiled unit's cycles by source group, from the async profiles of "
                     f"{esc(', '.join(hf['a'] + hf['b']))}.</p>")
    for r in out["methods"]:
        ta, tb = r["totals"]["a"]["main"], r["totals"]["b"]["main"]
        oa, ob = r["totals"]["a"]["outOfLine"], r["totals"]["b"]["outOfLine"]
        ca, cb = r["compilations"]["a"], r["compilations"]["b"]
        parts.append(f"<h2><code>{esc(r['method'])}{esc(r['signature'] or '')}</code></h2>")
        parts.append(f"<p class=muted>{esc(A)}: compile {ca['compileId']} ({esc(ca['compiler'])} tier {ca['level']}), "
                     f"{len(r['others']['a'])} compilation(s) in the fork; {esc(B)}: compile {cb['compileId']} "
                     f"({esc(cb['compiler'])} tier {cb['level']}), {len(r['others']['b'])}. Blocks {r['blocks']['a']} vs {r['blocks']['b']}.</p>")
        head = "".join(f"<th>{k}</th>" for k in KINDS)
        row = lambda name, x, y: (f"<tr><td>{name}</td>" + "".join(f"<td>{x[k]} → {y[k]} {_delta(x[k], y[k])}</td>" for k in KINDS) + "</tr>")
        parts.append(f"<table class=t><tr><th></th>{head}</tr>{row('main code', ta, tb)}{row('out of line', oa, ob)}</table>")
        for g in r["groups"]:
            ga, gb = g["a"], g["b"]
            heat = ""
            if g.get("hotA") is not None or g.get("hotB") is not None:
                h = max(g.get("hotA") or 0, g.get("hotB") or 0)
                heat = (f'<span class="heat" title="{esc(A)} {100 * (g.get("hotA") or 0):.1f}%, {esc(B)} {100 * (g.get("hotB") or 0):.1f}%">'
                        f'<i style="width:{min(100, 100 * h):.0f}%"></i></span>')
            summ = (f'<span class="lab" title="{esc(g["label"])}">{esc(g["label"])}</span>{heat}'
                    f'<span>{ga["insns"]} → {gb["insns"]} {_delta(ga["insns"], gb["insns"])}</span>'
                    f'<span class=muted>spills {ga["spill"]}→{gb["spill"]} · fills {ga["fill"]}→{gb["fill"]} · calls {ga["call"]}→{gb["call"]}</span>')
            lines = []
            for op in g["ops"]:
                side = {"equal": "", "delete": "del", "insert": "ins", "replace": "rep"}[op["tag"]]
                for j in range(max(len(op["a"]), len(op["b"]))):
                    lines.append(_line(op["a"][j] if j < len(op["a"]) else None, side) + _line(op["b"][j] if j < len(op["b"]) else None, side))
            opened = "" if g["same"] or g["outOfLine"] else " open"
            parts.append(f'<details class="g"{opened}><summary>{summ}</summary><div class="code">'
                         f'<div class=muted>{esc(A)}</div><div class=muted>{esc(B)}</div>{"".join(lines)}</div></details>')
    title = f"asm {out['method']}: {A} vs {B}"
    return (f"{ui.HEAD}<title>{esc(title)}</title>{ui.style(ui.BASE, CSS)}\n{ui.masthead(title, ui.home_from(d), slim=True)}"
            f"<main>{''.join(parts)}</main>{ui.footer()}")


# a cell's page ------------------------------------------------------------------------------------------------------

HOT = "hot.json"  # in <cell>/asm: {method: {"from": [cells], "paths": [[path, share]]}}, as asm diff read them
PAGE = "index.html"  # in <cell>/asm


def save_hot(cell, method, h, cells):
    f = os.path.join(cell, "asm", HOT)
    try:
        cache = json.load(open(f))
    except (OSError, ValueError):
        cache = {}
    cache[method] = {"from": [os.path.relpath(c, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(cell))))) for c in cells],
                     "paths": [[[list(x) for x in k], v] for k, v in h.items()]}
    with open(f, "w") as out:
        json.dump(cache, out)


def load_hot(cell, method):
    try:
        e = json.load(open(os.path.join(cell, "asm", HOT)))[method]
    except (OSError, ValueError, KeyError):
        return None, []
    return {tuple(tuple(x) for x in k): v for k, v in e["paths"]}, e["from"]


def page_path(cell):
    return os.path.join(cell, "asm", PAGE)


def ensure_cell_page(cell):
    """<cell>/asm/index.html, written when missing or older than the index or the heat it shows; its path, or None
    for a cell without a capture."""
    idx = os.path.join(cell, "asm", INDEX)
    if not os.path.exists(idx):
        return None
    pg = page_path(cell)
    deps = [idx] + ([os.path.join(cell, "asm", HOT)] if os.path.exists(os.path.join(cell, "asm", HOT)) else [])
    if not os.path.exists(pg) or os.path.getmtime(pg) < max(os.path.getmtime(x) for x in deps):
        write_cell_page(cell)
    return pg


def _code_section(code, heat):
    """One compilation's code by source group, one column: counts, heat, instructions."""
    gs = groups(code)
    shaded = shade(heat, list(gs)) if heat else {}
    unplaced = shaded.pop(None, 0.0) if shaded else None
    parts = []
    for k, ins in gs.items():
        c = counts(ins)
        label = k[0] if k and isinstance(k[0], str) else scope_label(k)
        h = shaded.get(k)
        bar = (f'<span class="heat" title="{100 * h:.1f}% of the unit\'s samples"><i style="width:{min(100, 100 * h):.0f}%"></i></span>'
               if h is not None else '<span class="heat nohot"></span>' if heat else "")
        lines = "".join(_line(_insn_out(i), "") for i in ins)
        parts.append(f'<details class="g"><summary><span class="lab" title="{esc(label)}">{esc(label)}</span>{bar}'
                     f'<span>{c["insns"]}</span><span class=muted>spills {c["spill"]} · fills {c["fill"]} · calls {c["call"]}</span></summary>'
                     f'<div class="code one">{lines}</div></details>')
    return "".join(parts), unplaced


def write_cell_page(cell):
    """A cell's printed compilations: a table of them all, and the code of each method's top-tier ones by source group
    (the default compilation open), shaded by the heat `asm diff` read for it."""
    from . import ui
    idx = load_index(cell) or []
    co, v, r = cell.rstrip("/").split(os.sep)[-3:]
    camp = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(cell)))))
    by = collections.defaultdict(list)
    for c in idx:
        by[(c["method"], c.get("signature"))].append(c)
    defaults = {id(default(cs)) for cs in by.values()}
    rows = []
    for c in idx:
        anchor = f"c{c['compileId']}-{c.get('pid') or 0}"
        tier = f"t{c['level']}" + (f" OSR@{c['osr']}" if c.get("osr") is not None else "")
        n = c.get("counts") or {}
        shown = c["level"] >= 4 or c["compiler"] in ("c2", "jvmci")
        name = f'<a href="#{anchor}">{esc(c["method"])}</a>' if shown else esc(c["method"])
        rows.append(f'<tr{" class=def" if id(c) in defaults else ""}><td>{name}<span class=muted>{esc(c.get("signature") or "")}</span></td>'
                    f'<td>{c["compileId"]}</td><td>{esc(c["compiler"])}</td><td>{tier}</td><td>{c["bytes"]}</td>'
                    f'<td>{n.get("insns", c.get("instructions", ""))}</td><td>{n.get("spill", "")}</td><td>{n.get("fill", "")}</td>'
                    f'<td>{n.get("call", "")}</td><td><a href="{esc(os.path.relpath(os.path.join(cell, c["file"]), os.path.join(cell, "asm")))}">.s</a>'
                    f'{" <b>default</b>" if id(c) in defaults else ""}</td></tr>')
    secs = []
    for (m, sig), cs in by.items():
        heat, frm = load_hot(cell, m)
        for c in cs:
            if not (c["level"] >= 4 or c["compiler"] in ("c2", "jvmci")):
                continue
            code = code_of(cell, c)
            body, unplaced = _code_section(code, heat)
            t = code["totals"]["main"]
            note = (f' <span class=muted>heat from {esc(", ".join(frm))}'
                    + (f", {100 * unplaced:.0f}% of it at positions this code has no group for" if unplaced else "") + "</span>") if heat else ""
            secs.append(f'<details class="comp" id="c{c["compileId"]}-{c.get("pid") or 0}"{" open" if id(c) in defaults else ""}>'
                        f'<summary><b>{esc(m.split(".")[-1])}</b><span class=muted>{esc(sig or "")}</span> compile {c["compileId"]} '
                        f'({esc(c["compiler"])} tier {c["level"]}{", default" if id(c) in defaults else ""}): {t["insns"]} instructions, '
                        f'{t["spill"]} spills, {t["fill"]} fills, {t["call"]} calls, {code["blocks"]} blocks{note}</summary>{body}</details>')
    head = "".join(f"<th>{h}</th>" for h in ("method", "compile", "compiler", "tier", "bytecode", "insns", "spills", "fills", "calls", ""))
    title = f"asm {camp} · {co}/{v}/{r}"
    html_ = (f"{ui.HEAD}<title>{esc(title)}</title>{ui.style(ui.BASE, CSS, CELL_CSS)}\n{ui.masthead(title, ui.home_from(os.path.join(cell, 'asm')), slim=True)}"
             f"<main><p class=muted>The machine code this fork compiled for the capture's methods (CompileCommand=print, "
             f"not a timed fork). Counts are of the main code, from the verified entry. The default compilation of each "
             f"method is its last top-tier, non-OSR one, the one <code>perflab asm diff</code> compares; groups are its "
             f"debug info's inlining path (method:line, outermost first); heat appears once <code>asm diff</code> has read the "
             f"parent campaign's profile.</p><table class=t>{head}{''.join(rows)}</table>{''.join(secs)}</main>{ui.footer()}")
    with open(page_path(cell), "w") as f:
        f.write(html_)
    return page_path(cell)


CELL_CSS = """
details.comp{margin:14px 0}
details.comp>summary{cursor:pointer;font-size:14px;padding:4px 0}
.code.one{grid-template-columns:1fr}
tr.def td{background:rgba(230,170,30,.08)}
.heat.nohot{opacity:.35}
"""


# capture spec ------------------------------------------------------------------------------------------------------


def _iterations(args, n):
    """A corpus's JMH arguments for a capture: one fork, `n` measurement iterations, the warmup kept."""
    w = shlex.split(args)
    out, skip = [], False
    for j, x in enumerate(w):
        if skip:
            skip = False
            continue
        if x in ("-f", "-i"):
            skip = True
            continue
        out.append(x)
    return shlex.join(["-f", "1", "-i", str(n), *out])


def capture_spec(parent_path, methods, name=None, iterations=2, corpora=None):
    """The spec of an asm capture of the campaign whose spec is at `parent_path`."""
    s = json.load(open(parent_path))
    if s.get("branch") or s.get("paired") or s.get("profileOf"):
        sys.exit("perflab asm capture: a branch, paired or profile campaign is not supported yet; write the spec by hand")
    out = {k: v for k, v in s.items() if k not in ("profile", "kperf", "lib", "jfrsync", "rounds", "corpora", "loadgate",
                                                  "description", "historical", "perUnit", "diff")}
    out["name"] = name or s["name"] + "-asm"
    out["asmOf"] = s["name"]
    out["asm"] = list(methods)
    out["rounds"] = 1
    out["corpora"] = {c: _iterations(a, iterations) for c, a in s["corpora"].items() if not corpora or c in corpora}
    if not out["corpora"]:
        sys.exit(f"perflab asm capture: {s['name']} has no corpus {', '.join(corpora)} (it has {', '.join(s['corpora'])})")
    out["description"] = [f"Machine code of {', '.join(f'`{m}`' for m in methods)} in [{s['name']}](../{s['name']}) "
                          f"(hsdis, `CompileCommand=print`): one fork per variant, not for timing."]
    return out


def main(argv):
    ap = argparse.ArgumentParser(prog="perflab asm", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("capture")
    c.add_argument("campaign")
    c.add_argument("--method", action="append", required=True)
    c.add_argument("--name")
    c.add_argument("--iterations", type=int, default=2)
    c.add_argument("--corpus", action="append", help="only this corpus of the campaign's (repeatable; default all)")
    c.add_argument("--local", action="store_true")
    c.add_argument("--dry-run", action="store_true")
    l = sub.add_parser("list")
    l.add_argument("campaign")
    for p in (l,):
        p.add_argument("--corpus"); p.add_argument("--variant"); p.add_argument("--round", type=int); p.add_argument("--method")
    s = sub.add_parser("show")
    s.add_argument("campaign"); s.add_argument("variant"); s.add_argument("--method", required=True)
    s.add_argument("--corpus"); s.add_argument("--round", type=int); s.add_argument("--compile-id", type=int)
    s.add_argument("--raw", action="store_true")
    df = sub.add_parser("diff")
    df.add_argument("campaign"); df.add_argument("a"); df.add_argument("b"); df.add_argument("--method", required=True)
    df.add_argument("--corpus"); df.add_argument("--round", type=int)
    df.add_argument("--compile-id-a", type=int); df.add_argument("--compile-id-b", type=int)
    df.add_argument("--no-hot", action="store_true", help="no hot-path shading from the parent's async profile")
    h = sub.add_parser("hsdis")
    h.add_argument("--jvm", default=None)
    x = ap.parse_args(argv)
    try:
        return _main(x)
    except LookupError as e:
        sys.exit(f"perflab asm: {e.args[0]}")


def _main(x):
    if x.cmd == "hsdis":
        java = x.jvm or os.path.join(os.environ.get("JAVA_HOME", ""), "bin", "java")
        p = find_hsdis(java)
        print(f"{java}: {p}" if p else check_hsdis(java))
        return 0 if p else 1
    if x.cmd == "capture":
        d = campaign_dir(x.campaign)
        parent = x.campaign if x.campaign.endswith(".json") else os.path.join(d, "spec.json")
        spec = capture_spec(parent, x.method, x.name, x.iterations, x.corpus)
        dest = os.path.join(os.path.dirname(os.path.abspath(parent)) if not ab_is_copy(parent) else _source_dir(d), spec["name"] + ".json")
        with open(dest, "w") as f:
            json.dump(spec, f, indent=2)
            f.write("\n")
        print(f"wrote {dest}")
        argv = [sys.executable, "-m", "perflab", "ab", "run", dest] + (["--local"] if x.local else []) + (["--dry-run"] if x.dry_run else [])
        env = dict(os.environ)
        if not x.local:  # the cli runs this command in the foreground; its `ab run` goes to the server's queue as typed would
            env.pop("PERFLAB_LOCAL", None)
        return subprocess.call(argv, env=env)
    d = campaign_dir(x.campaign)
    if x.cmd == "list":
        for co, v, r, cell in cells_of(d, x.corpus, x.variant, x.round):
            print(f"{co}/{v}/{r}:")
            for c in load_index(cell):
                if x.method and not matches(c, x.method):
                    continue
                print(f"  {c['compileId']:>6} {c['compiler']:>5} t{c['level']}{' osr@' + str(c['osr']) if c.get('osr') is not None else ''}"
                      f"  {c['instructions']:>5} insns  {c['method']}{c.get('signature') or ''}")
        return 0
    if x.cmd == "show":
        co, v, r, cell = cell_of(d, x.variant, x.corpus, x.round)
        for (m, sig), comp in select(cell, x.method, x.compile_id).items():
            print(f"# {m}{sig or ''}: compile {comp['compileId']} ({comp['compiler']} tier {comp['level']}), {comp['file']}")
            if x.raw:
                print(open(os.path.join(cell, comp["file"])).read())
                continue
            code = code_of(cell, comp)
            prev = None
            for i in code["insns"]:
                k = scope_key(i["scope"])
                if k != prev:
                    print(f"  ;; {scope_label(k)}")
                    prev = k
                print(f"  {i['norm']}")
        return 0
    if x.cmd == "diff":
        out = diff(d, x.a, x.b, x.method, x.corpus, x.round, x.compile_id_a, x.compile_id_b, hot_path=not x.no_hot)
        for r in out["methods"]:
            ta, tb = r["totals"]["a"]["main"], r["totals"]["b"]["main"]
            print(f"{r['method']}{r['signature'] or ''}: " + ", ".join(f"{k} {ta[k]} → {tb[k]}" for k in KINDS if ta[k] or tb[k]))
            for g in r["groups"]:
                if not g["same"] and not g["outOfLine"]:
                    print(f"  {g['a']['insns']:>4} → {g['b']['insns']:<4} {g['label']}")
        print(f"wrote {out['page']}")
        return 0


def ab_is_copy(path):
    return os.path.basename(path) == "spec.json"


def _source_dir(d):
    try:
        return os.path.dirname(open(os.path.join(d, "spec.source")).read().strip()) or d
    except OSError:
        return d
