# Machine code: comparing two builds' JIT output (hsdis)

Some regressions only show up in machine code. Two builds can make the same calls (an audit shows equal counts), inline the same methods and allocate the same, and still differ by a point in instructions, because the top-tier compiler laid out one hot method differently: a field load hoisted onto the common path, spills, a branch it no longer folds. The case that motivated this: in scala3's sharing-off work, `SymDenotation.is` inlined into `SourceLanguage$.apply` compiled under Graal to 268 instructions in one build and 327 in the other, with three times the spills. Finding that by hand took a hand-built hsdis, `CompileCommand=print` in a campaign's variants and ad-hoc scripts over a 1 MB `jmh.log`. `perflab asm` does it as one step: name the methods, get each build's code, read a normalised diff by source line.

## When to reach for it

When a profile has narrowed a gap to one compiled unit (`perflab inlinetree`, a curated diff's flips), `jit_diff` shows no change of inlining or code size large enough to explain it, and the instructions per op of that unit still differ. Machine code answers "what did the compiler make of this method in each build". It does not say how often each path runs: that is the profile's job, and the diff borrows it (see Heat).

## Workflow

1. **hsdis.** `perflab asm hsdis --jvm <java>` says whether a JDK has it. `HSDIS_JDKS="<jdk home> ..." mise run tools:hsdis` (in jvm-perf-lab; Homebrew's `capstone` needed) builds `hsdis-<arch>.dylib|so` from OpenJDK's capstone backend (two source files fetched at a pinned tag, or `HSDIS_SRC=<a JDK checkout>`) with capstone linked statically, and copies it into each JDK's `lib/`. Do it on every machine that runs captures (the testbed's worker too: `ssh m4`, same command). A capture fails before its first cell when its `jvm` has none: without hsdis, `CompileCommand=print` prints hex after minutes of running.
2. **Capture.** `perflab asm capture <campaign> --method 'dotty.tools.dotc.core.SourceLanguage$::apply' [--method ...]` writes `<campaign>-asm.json` beside the campaign's spec and runs it (queued on the server like `ab run`; `--local`, `--dry-run`). The capture is a campaign of its own: the parent's builds (their snapshots reused), JVM, JVM arguments, variants, corpora and testbed; one round, one fork, the warmup kept and `--iterations` (2) measured; no profile, no load gate. Its spec has `"asm": [methods]` and `"asmOf": "<parent>"`; a hand-written spec with `"asm"` works too.
3. **Read.** `perflab asm list <capture>` lists every printed compilation per cell. `perflab asm diff <capture> <a> <b> --method SourceLanguage$::apply` prints the totals and the groups that differ, and writes `<capture>/asm-diff-<method>-<a>-<b>.html` (and `.json`), linked from the capture's card under "Machine code". `perflab asm show <capture> <variant> --method M` prints one compilation, normalised and grouped (`--raw` for HotSpot's printout, `--compile-id` for another compilation). Agents read the API instead (below).

Method names are HotSpot's: `pkg.Class::method`, `$` for a nested class or a Scala object (`SourceLanguage$::apply`), `*` wildcards as `CompileCommand` takes them. For `list`, `show` and `diff`, a dotted suffix is enough, with the descriptor appended for an overload (`SymDenotation::is(JLdotty/tools/dotc/core/Contexts$Context;)Z`); without one, `diff` compares every overload present in both.

## What a capture records

The forks run with `-XX:+UnlockDiagnosticVMOptions -XX:+DebugNonSafepoints -XX:+LogVMOutput -XX:-DisplayVMOutput -XX:LogFile=<cell>/vm-%p.log -XX:CompileCommand=quiet -XX:CompileCommand=print,<method>...`. The disassembly goes to the log, not to stdout, so `jmh.log` stays JMH's. `DebugNonSafepoints` gives debug info (a source line) at many more instructions than the safepoints alone, about five times as many; async-profiler sets it as well, so the capture's lines and the profiles' are the same kind. After each fork perflab splits the log into `<cell>/asm/<method>/<compile id>-t<level>[-osr].s`, one per compilation, and writes `<cell>/asm/index.json`, which records for each compilation its compiler, tier, OSR bci, signature, bytecode size and instruction counts. It then gzips the log.

## Why a separate campaign

`CompileCommand=print` slowed a microbenchmark's forks by 15–40%, and what a fork compiles depends on its profile and timing, so the printed code is the code of that fork, not of the timed ones. A capture therefore never shares cells with timing: its card says "asm capture, not for timing", and `profdiff` refuses to compare its cells with a timed campaign's. Its scores are kept but mean nothing. The code itself is usually the same as the timed forks' at steady state, and the heat (below) comes from the timed forks.

## Which compilation

A method is compiled several times: C1 at tier 3, the top tier (C2, or Graal through JVMCI) at tier 4, again after a deoptimization, OSR. Every compilation is kept. The one compared by default for each (method, signature) is the **last top-tier one that is not OSR**, the code the fork ran at the end. `--compile-id-a/-b` (API `compileIdA/B`) picks others. With `"jitRecording": true` in the capture's spec as well, `perflab api jit` explains the recompilations (the same compile ids).

## How the diff aligns two builds

Each instruction gets its source position from the debug info HotSpot prints after it: an inlining path such as `SourceLanguage$::apply@12 (line 34)` ← `SymDenotation::is@5 (line 113)`, written outermost first as `apply:34 → is:113`. An instruction without annotation takes the position of the next annotated instruction in its basic block, otherwise the last one before it. The instructions before any annotation, the frame's setup, form a group of their own. The instructions of one position form a group, and two builds are aligned group by group:

- **Moved source**: a patch that adds lines above a method shifts all of its lines alike, by a different amount per method. For each method, perflab takes the shift under which the most instructions line up (in the motivating case `apply` +1, `is` +28), shifts a's lines by it, and pairs groups with the same path at the same shifted lines. The label shows both lines where they differ (`apply:34/35 → is:113/141`).
- **Lambda numbers are ignored** (`$anonfun$39` and `$anonfun$41` are the same frame), because a build that adds a lambda renumbers the rest.
- Code of one build only (a rewritten callee, a different inlining) is shown on its own side.

Within a pair, difflib compares the normalised instructions. Normalisation replaces addresses, branch targets (with block labels `L<n>`), and the `mov`/`movk` immediates that build an address with ADDR/IMM, keeps registers and small constants, and appends relocations (`runtime_call`, `metadata('Class')`, method names). Per group and in total it counts instructions, loads, stores, spills (stores to `[sp`), fills (loads from it), calls, branches, safepoint polls and nops. Totals are split into the main code (from the verified entry), the entry (the inline-cache check) and the out-of-line sections (stubs, exception and deopt handlers). aarch64 is classified by mnemonic; x86-64 by the side of its memory operand, which is cruder.

## Heat

When the capture's parent has async profiles of the same variants, each group is shaded by its share of the compiled unit's samples. The source key is the same: async-profiler's frames of compiled code carry a line, and a unit is its `_[j]` frame and the `_[i]` frames above it. Samples at a position that no group has are reported as `hotUnplaced`. A profile's frames have no descriptors, so the overloads of one method share its heat. The samples come from the timed forks, so they are unperturbed, and they are matched by source position rather than by address, because addresses are per process. Instruction-level heat would need a profile of the capture's own fork (JMH's `perfasm`/`xctraceasm` approach), which is the perturbed one; that is not done.

## API

- `asm(campaign, [corpus, variant, round, method])`: a capture's compilations per cell, with the default one of each method marked.
- `asm_code(campaign, variant, method, [corpus, round, compileId])`: one compilation by source group, each instruction with its normalised form, classes, block, bytecode at calls and inlining path.
- `asm_diff(campaign, a, b, method, [corpus, round, compileIdA, compileIdB, code, hot])`: the groups paired, with counts, diff hunks (only for groups that differ, unless `code`), heat and the page's URL. Writes the page as `perflab asm diff` does.

## Graal and C2

hsdis output with debug annotations is the same for C2 and Graal (JVMCI), so all of the above works for both. What differs is inlining: libgraal writes no inlining tree to `LogCompilation`; its equivalents are `-Djdk.graal.TraceInlining=true` and `-Djdk.graal.Dump`. A capture can add either to its variants' JVM flags. perflab does not split their output yet.

## Prior art

JMH's `-prof perfasm` (Linux) and `-prof xctraceasm` (macOS) combine hsdis, `LogCompilation` and a sampling profiler to print one fork's hottest regions with per-instruction percentages. They answer "where is this fork hot", inside that fork's perturbation. They do not compare two builds, choose among compilations or align on source lines. JITWatch reads the same logs and shows one run's source, bytecode and assembly side by side. perflab adds the comparison of two builds of one campaign, and access to it through the API.

## Future work

- Split `jdk.graal.TraceInlining` output per compilation beside the code.
- PC-level heat from a profile of the capture's own fork, opt-in, with the perturbation caveat on the page.
- `perflab inlinetree`: link a unit's row to its machine code when a capture of it exists.
- `ab diff`'s curated tables match lambdas by name; matching by (enclosing method, source line), as here, would pair the same lambda across builds.
- Capture of a branch campaign's commits, and of paired campaigns.
