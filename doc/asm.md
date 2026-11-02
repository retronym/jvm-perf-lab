# Machine code: hsdis disassembly of JIT compilations (design, for review)

## Problem

Some regressions only show up in machine code. Two builds can make the same calls (an audit shows equal counts), have the same inlining shape and allocate the same, and still differ by a point in instructions because the top-tier compiler laid out one hot method differently: a field load hoisted onto the common path, spills, a branch it can no longer fold. On 2026-11-02 one such case (`SymDenotation.is` inlined into `SourceLanguage$.apply`: 276 vs 335 instructions under Graal, so1 vs base) took a hand-built hsdis, a campaign with `CompileCommand=print` in its variants (`m4-asm-iscurrent`, job 193), and ad-hoc python over a 1 MB `jmh.log` to find. perflab should make that a routine step: name the methods, get each build's code, read a normalised diff with source lines, from the CLI, the API and the index.

## Key decisions

1. **Disassembly cells are their own campaign, never timing.** Printing slowed a microbenchmark by 15–40%, and the code printed may differ from what the timed forks ran (different profile, different compile timing). So an asm capture is a campaign of its own, `"asmOf"` the campaign it explains, like a branch campaign's `"profileOf"`: the same builds (reused from the parent's `.build` snapshots, not rebuilt), JVM, JVM arguments and corpora, one round, one fork, short measurement. Its scores are kept but labelled "asm capture, not for timing" on its card, and `ab diff`/`profdiff` refuse to compare its cells with timing cells. `perflab asm capture <campaign> --method M...` writes and queues that spec (`<campaign>-asm`, or `--name`); the spec is ordinary, so it can also be hand-written with `"asm": [...]` and no parent.

2. **Captured into its own log, not `jmh.log`.** `-XX:+UnlockDiagnosticVMOptions -XX:+LogVMOutput -XX:-DisplayVMOutput -XX:LogFile=<cell>/vm-%p.log -XX:CompileCommand=quiet -XX:CompileCommand=print,<method>...`. The tty output (the disassembly) lands in the log's `<tty>` element and JMH's output stays clean. After the fork, perflab splits it into `<cell>/asm/<Class>::<method>/<compileId>-<tier>.s`, one file per compilation, and writes `<cell>/asm/index.json`: per compilation its method, signature, bytecode size, tier (1–4, `osr` when `%`), compiler (c1, c2, JVMCI), timestamp, code size, and per block the counts below. The raw log is gzipped and kept.

3. **Which compilation.** A method is compiled several times (C1 tier 3, top tier, recompiled after deopt, OSR) and may be overloaded (`is` has a 29- and a 42-byte overload in job 193). The unit of comparison is (method, signature); the default compilation is its **last non-OSR top-tier** one; the others are listed and selectable by compile id or `--tier`/`--osr`. With `jitRecording` in the capture, the compile ids join the JFR's `jdk.Compilation`/`jdk.Deoptimization` events, so the listing can say why a method was recompiled.

4. **The diff is normalised and anchored on source.** `perflab asm diff <campaign> a b --method M`:
   - normalise: addresses, branch targets (as block labels), `#0x…` immediates that are addresses or metadata, oop/metadata comments; keep register names and small constants;
   - blocks: split at branch targets; each block is attributed to the innermost `; - Class::method@bci (line N)` debug annotation in it, i.e. a source line *and* its inlining path (`apply` → `is` → `isCurrent`);
   - align the two builds by inlining path + source line, not by order and not by lambda name (`$anonfun$39` vs `$anonfun$41`), then diff the instructions within aligned groups (`difflib` over `op args`);
   - per group and in total: instructions, loads, stores, stack spills/fills (`str`/`stp`/`ldr`/`ldp` on `[sp`), calls (`bl`/`blr` with their runtime-call or method targets), safepoint polls, and the bytes.
   Output: `<campaign>/asm-diff-<method>-<a>-<b>.html` (side by side, groups collapsible, linked from the campaign card next to the profile diffs) and the same as JSON for the API. aarch64 first (the testbeds); x86-64 is a table of opcode classes away.

5. **Hot path from the timing cells, by source line.** Addresses are per process, and the asm cell's own profile would be from the perturbed run. Instead, the hotness comes from an async profile of the parent campaign (unperturbed), attributed by (inlining path, line): async-profiler's JFR frames of compiled code carry line numbers and the inlined/compiled frame type, which is the same key the diff's groups have. Groups are shaded by their share of the method's samples. Instruction-level attribution (async-profiler can record PCs; xctrace backtraces have them, as JMH's `xctraceasm` uses) would need the profile from the same fork as the disassembly; that is future work, opt-in, with the perturbation caveat on the page.

6. **hsdis is checked, and installable.** Before the first cell, perflab runs the campaign's `jvm` with `-XX:+PrintAssembly -version` and fails the cell early on "Could not load hsdis" (otherwise the fork just prints abstract disassembly, hex, after minutes of running). A worker does the same check at claim, against its own mapped JDK, and refuses the job with the install command, as it does for a missing JDK. `mise run tools:hsdis [--jdk <home>]` builds `hsdis-<arch>.dylib|so` from OpenJDK's `src/utils/hsdis/capstone/hsdis-capstone.c` and `hsdis.h` (downloaded at a pinned tag of openjdk/jdk, not a whole JDK tree) against Homebrew's static capstone, choosing `CS_ARCH_AARCH64` or `CS_ARCH_ARM64` by the capstone version, and copies it into `<jdk>/lib` (and into the JDKs named by `--all`, e.g. every sdkman JDK). The direct `clang` build avoids `make build-hsdis`, which needs a configured JDK build and, on current Xcode, the missing `metal` tool. The dylib is built per machine rather than shipped: it is GPL with the Classpath exception and links capstone.

7. **One API, three front ends.** API functions (in `perflab api`, `perflab mcp`, the server):
   - `asm(campaign, corpus, variant, round, method?)`: a cell's compilations (the index.json above), or one method's;
   - `asmCode(campaign, corpus, variant, round, method, compileId?)`: one compilation's code, as normalised lines with their source annotations and the per-block counts (agents read this, never the `.s`);
   - `asmDiff(campaign, a, b, method, corpus?, round?, compileIdA?, compileIdB?)`: the groups, their counts and diffs, the hot-path shares when a parent profile exists, and the page's URL.
   The CLI's `perflab asm list|show|diff` are thin over these; the index links the pages.

## Graal and C2

hsdis output with debug annotations is the same for C2 and Graal (JVMCI), so everything above works for both. What differs is inlining: libgraal writes no inlining tree to `LogCompilation`; its equivalent is `-Djdk.graal.TraceInlining=true` (and `-Djdk.graal.Dump` for graphs). An asm capture can add `"asmTraceInlining": true` to keep that next to the code, split per compilation the same way. Not in the first cut.

## Prior art

JMH's `-prof perfasm` (Linux) and `-prof xctraceasm` (macOS): hsdis + `LogCompilation` + a sampling profiler, printing the hottest regions with per-instruction percentages. They answer "where is this fork hot" within one fork and its perturbation; they do not compare two builds, select a compilation, or anchor on source lines. JITWatch reads the same logs and shows source/bytecode/assembly side by side for one run. perflab's contribution is the comparison across builds of one campaign, and reaching it through the API.

## Supporting changes

- `ab diff`'s curated tables match lambdas by name; they should match by (enclosing method, source line) too, the same key as here (a separate change).
- `perflab inlinetree`: link a unit's row to its machine code when a capture exists for it (later).
- Docs: this file becomes the user doc once built; a section in the perflab skill (when to reach for it: equal call counts and inlining but more instructions per op in a unit; the pitfalls; the commands).

## Plan

- TODO: hsdis check (local + worker claim) and `mise run tools:hsdis`.
- TODO: `"asm"` in a spec: the flags, `vm-%p.log`, splitting into `asm/` + index.json; `"asmOf"` reusing the parent's builds; `perflab asm capture`.
- TODO: normaliser, block/source grouping, alignment, counts; `perflab asm diff` page + JSON; API functions; card links; "not for timing" label and the diff/profdiff refusals.
- TODO: hot-path shading from the parent's async profile.
- TODO: skill section, docs.
- TODO: verify: rerun job 193's comparison (base `bench84-base-su` vs so1 `combo6-sharing-off-su`, `SourceLanguage$::apply`, m4) as an asm capture and reproduce 276 vs 335.
- Future work: `asmTraceInlining`; PC-level hot path from a same-fork profile; x86-64 opcode classes; inlinetree links; lambda matching by line in `ab diff`.
