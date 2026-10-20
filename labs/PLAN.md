# Plan: curating the compiler labs

## Problem

The Scala 3 lab (retronym/scala3 `bench-lab-harness`, `bench-lab-perflab`) and the Scala 2 lab (retronym/scala `compiler-lab-builds`) lived on long branches of the compiler forks: the lab mixed with upstreamable compiler changes (cost per definition) and experiment leftovers (goForward, Positioned and kperf specs, a goForward benchmark and generators). Using the lab on a compiler branch meant merging it in, and no piece could be reviewed or shared without the whole stack.

## Key decisions

1. **The labs live here, in `labs/scala3` and `labs/scala2`, as sbt builds that load a compiler checkout as a source dependency** (`ProjectRef`). A compiler branch carries only compiler changes; the lab is pointed at it with `SCALA3_CHECKOUT` / `SCALA_CHECKOUT`. This replaces the earlier plan of a squashed lab commit in each compiler repo.
2. **Compiler changes become their own branches, in the form they'd take upstream.** The lab's dependence on them is conditional (`src/costs` compiles only when the checkout has `DefCosts`).
3. **No history is kept for the lab.** Its history was mostly tooling that has since moved into perflab; the old branches are tagged `archive/…` in the compiler forks.
4. **Experiment specs and benchmarks are not carried forward.** They name flags that exist only on experiment branches. The archive tags keep them (`bench-lab/ab/`, `GoForwardBenchmark`, `scripts/gen_goforward_*.py`, `compiler-lab-multi-global`'s `globalClasses`). Each lab keeps example specs only.

## Branches

retronym/scala3 (local, not pushed):

| branch | on | commits | purpose |
|---|---|---|---|
| `sbt-library-stamps` | `main` | 1 (+2/−2) | build: stamp the patched library classes through the file converter; needed for the lab, and correct on its own |
| `cost-per-definition` | `sbt-library-stamps` | 2 (+502/−36, +42/−4) | `-Yprofile-defs`, `-Yprofile-defs-listener`; hash-consing growth as its own frame |
| `claude/build-toggle-opt-disable-0daefd` (existing) | older `main` | 1 | `SCALA3_BUILD_OPTIMIZE=false` |
| tags `archive/bench-lab-harness`, `archive/bench-lab-perflab` | | | the old lab |

retronym/scala (local, not pushed):

| branch | on | commits | purpose |
|---|---|---|---|
| `cost-per-definition` | `2.13.x` | 1 (+525/−8) | `-Yprofile-defs`, `-Yprofile-defs-listener`, without the stray re-indent of `YpatmatExhaustdepth` |
| tags `archive/compiler-lab-builds`, `archive/compiler-lab-multi-global` | | | the old lab |

jvm-perf-lab: `compiler-labs`, on `claude/repo-activity-compiler-lab-7b2d9f` (for `perflab-spans`).

## Upstream PRs, in order

1. scala/scala3: `sbt-library-stamps`. Tiny and independent; until it is merged, a checkout used with the lab needs it.
2. scala/scala: cost per definition. The smaller diff (one new hook), and it settles the option names and the table format `perflab defcosts` reads. First measure it with the options off against the branch point (`@build=` variants).
3. scala/scala3: the `-opt` toggle.
4. scala/scala3: cost per definition, using the same option names and format. `labs/scala3/doc/def-costs.md` is the PR description's source.
5. scala/scala3: the rehash frames, as their own commit (in the same PR or a follow-up), because they change `Uniques`.
6. Maybe scala/scala: read `versions.properties` relative to the build's base directory, so the lab's copy can go.

Whether `-Yprofile-defs-listener` should load a class named by an option is a question for review. There's precedent in `-Xplugin` and `-Yprofile-external-tool`; the fallback is `-Yprofile-defs` alone.

## Status

- DONE Archive tags; curated compiler branches. `DefCostsTest` passes on both (scala3 bootstrapped, 4 tests; scala junit, 2 tests).
- DONE `labs/scala3` and `labs/scala2` load their checkout via `ProjectRef`, and `lab/Jmh/compile` is a no-op the second time. Each has run through `perflab run` with `-Yprofile-defs` and with `SpanCostListener` (dottyUtil, scalaLibrary, scalap; one short fork each, smoke only).
- DONE Alignment: one layout (`lab` project, `perflab.toml` with `out/runs` and `out/ab`, `campaigns/`, `span-config.json`, README for running, `doc/design.md` for the why), `perflab-spans` in both (Scala 2's vendored `Span`/`Recording` are gone), `SpanCostListener$All` in both, a Scala 2 `span-config.json`, `bench-lab` / `dotty.tools.benchlab` renamed to `labs/scala3` / `dotty.tools.compilerlab`, and system properties `benchlab.*` renamed to `compilerlab.*`.
- DONE Dropped: `scripts/compare.py` (the one-off dotc-vs-javac comparison), per-lab `CLAUDE.md` files (the root `AGENTS.md` has their rules), and the plan sections of the docs (kept as Checks and Future work).
- DONE Reusing a compiler between ops: `-p compiler=fresh|resident` and `-Dcompilerlab.resident` (for `CompileLoop`) in both labs, replacing Scala 3's `context=fresh|shared` and Scala 2's `global=fresh|resident`.
- TODO `perflab trees` for the labs. A tree is a lab directory with its own sbt server, so comparing checkouts means a jvm-perf-lab worktree per checkout. Better: `@build=` in-fork variants for Scala 3 too (the generic part of `IsolatedBuild` in perflab-jmh).
- TODO perflab defaults for `perflab.toml` boilerplate (`[agent] jar`, `[index] flags`, `[benchmark] corpus/variants`).
- TODO Publish a tagged perflab (JitPack). Until then the labs build only where `mise run install` has run, which is the real blocker to sharing.
- TODO `OutputDigest` and a `perflab-phases.toml` for Scala 2.
- TODO After pushing: delete the old branches (scala3 `bench-lab-harness`, `bench-lab-perflab`, `bench-lab-curation-plan`, `claude/scalalib-bench-lab-d2e828`'s lab merge; scala `compiler-lab`, `compiler-lab-builds`, `compiler-lab-step5`, `compiler-lab-multi-global`, `claude/compiler-lab-601e68`), and close draft PR retronym/scala3#14.

## Risks

- **The lab and the checkout's own sbt server share target directories.** Compiling from both at once can corrupt the Zinc analyses. Use one server per checkout at a time.
- **The lab breaks when the compiler build changes** in ways a source dependency notices: an sbt version bump, a meta-build dependency (ASM), or a path resolved against the working directory. Each failure is loud (load errors, or a full recompile on every run), and each fix belongs upstream.
- **Experiment branches stacked on the old lab** (`claude/positioned-bench`, the goForward worktrees) should drop their lab merges and point the lab at their worktree. Their specs are in the archive tag.
