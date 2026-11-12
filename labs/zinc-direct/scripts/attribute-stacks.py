#!/usr/bin/env python3
"""Attributes collapsed (jfrconv --cpu --threads -o collapsed <cell>/*/jfr-cpu.jfr) async-profiler stacks (jfrconv --threads) to Zinc subsystems, per op.

Usage: attribute-stacks.py <ops> <a.collapsed> <b.collapsed> [labels a,b]
A stack goes to the outermost frame that names a subsystem, so work a bridge phase triggers in scalac or in Zinc's
callback stays with that phase. Threads: zinc-copy (the compile), JIT compilers, GC/VM (native threads), other.
"""
import re
import sys
from collections import Counter

RULES = [
    ("persist", re.compile(r"AnalysisStore|/consistent/|/binary/converters/|ProtobufWriters|AnalysisFormat")),
    ("bridge: xsbt-api", re.compile(r"^xsbt/(API|ExtractAPI)[.$]")),
    ("bridge: xsbt-dependency", re.compile(r"^xsbt/(Dependency|ExtractUsedNames)[.$]")),
    ("bridge: xsbt-analyzer", re.compile(r"^xsbt/Analyzer[.$]")),
    ("zinc: javac classfile analysis", re.compile(r"^sbt/internal/inc/(classfile/|ClassToAPI|ClassfileToAPI|javac/.*readAPI)")),
    ("zinc: building the analysis (AnalysisCallback after the run)", re.compile(r"^sbt/internal/inc/AnalysisCallback[.$]")),
    ("javac", re.compile(r"^(com/sun/tools/javac/|javax/tools/|sbt/internal/inc/javac/LocalJava)")),
]
SCALAC = re.compile(r"^scala/tools/nsc/")
PHASE = [
    ("scalac: typer/namer", re.compile(r"^scala/tools/nsc/typechecker/")),
    ("scalac: backend", re.compile(r"^scala/tools/nsc/backend/|^scala/tools/asm/")),
    ("scalac: transform", re.compile(r"^scala/tools/nsc/transform/")),
    ("scalac: parser", re.compile(r"^scala/tools/nsc/ast/parser/")),
]


def thread_kind(t):
    if "zinc-copy" in t:
        return "compile"
    if "CompilerThread" in t:
        return "JIT"
    if t.startswith("[tid=") or "GC" in t or "VM Thread" in t:
        return "GC/VM"
    return "other threads"


def classify(frames):
    for f in frames:
        for name, rx in RULES:
            if rx.search(f):
                return name
    if any(SCALAC.search(f) for f in frames):
        for f in frames:
            for name, rx in PHASE:
                if rx.search(f):
                    return name
        return "scalac: other"
    if any(f.startswith("sbt/internal/inc/") for f in frames):
        return "zinc: setup, stamping, analysis building"
    return "other (compile thread)"


def load(path):
    c = Counter()
    with open(path) as fh:
        for line in fh:
            stack, _, n = line.rstrip("\n").rpartition(" ")
            frames = stack.split(";")
            kind = thread_kind(frames[0])
            key = classify([re.sub(r"_\[.\]$", "", f) for f in frames[1:]]) if kind == "compile" else kind
            c[key] += int(n)
    return c


def main():
    ops = float(sys.argv[1])
    a, b = load(sys.argv[2]), load(sys.argv[3])
    la, lb = (sys.argv[4].split(",") if len(sys.argv) > 4 else ["a", "b"])
    keys = sorted(set(a) | set(b), key=lambda k: -(b[k] - a[k]))
    print(f"| per op | {la} | {lb} | {lb} - {la} |")
    print("|---|---|---|---|")
    for k in keys:
        print(f"| {k} | {a[k] / ops:,.0f} | {b[k] / ops:,.0f} | {(b[k] - a[k]) / ops:+,.0f} |")
    ta, tb = sum(a.values()), sum(b.values())
    print(f"| **all threads** | {ta / ops:,.0f} | {tb / ops:,.0f} | {(tb - ta) / ops:+,.0f} |")


main()
