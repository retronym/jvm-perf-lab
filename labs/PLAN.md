# Plan: curating the compiler labs

## Problem

The Scala 3 lab (retronym/scala3 `bench-lab-harness`, `bench-lab-perflab`) and the Scala 2 lab (retronym/scala `compiler-lab-builds`) lived on long branches of the compiler forks: the lab mixed with upstreamable compiler changes (cost per definition) and experiment leftovers (goForward, Positioned and kperf specs, a goForward benchmark and generators). Using the lab on a compiler branch meant merging it in, and no piece could be reviewed or shared without the whole stack.

## Key decisions

1. **The labs live here, in `labs/scala3` and `labs/scala2`, as sbt builds that load a compiler checkout as a source dependency** (`ProjectRef`). A compiler branch carries only compiler changes; the lab is pointed at it with `SCALA3_CHECKOUT` / `SCALA_CHECKOUT`. This replaces the earlier plan of a squashed lab commit in each compiler repo.
2. **Compiler changes become their own branches, in the form they'd take upstream.** The lab depends on none of them: the cost per definition, first a patch (`cost-per-definition`), is now woven in by perflab-agent ([def-costs.md](def-costs.md)).
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
2. scala/scala3: the `-opt` toggle.
3. Maybe scala/scala: read `versions.properties` relative to the build's base directory, so the lab's copy can go.

The cost per definition is no longer on this list: it comes from the lab ([def-costs.md](def-costs.md)), and the `cost-per-definition` branches are kept as the reference it was checked against.

## Status

- DONE Archive tags; curated compiler branches. `DefCostsTest` passes on both (scala3 bootstrapped, 4 tests; scala junit, 2 tests).
- DONE `labs/scala3` and `labs/scala2` load their checkout via `ProjectRef`, and `lab/Jmh/compile` is a no-op the second time. Each has run through `perflab run` with `-Yprofile-defs` and with `SpanCostListener` (dottyUtil, scalaLibrary, scalap; one short fork each, smoke only).
- DONE Alignment: one layout (`lab` project, `perflab.toml` with `out/runs` and `out/ab`, `campaigns/`, `span-config.json`, README for running, `doc/design.md` for the why), `perflab-spans` in both (Scala 2's vendored `Span`/`Recording` are gone), `SpanCostListener$All` in both, a Scala 2 `span-config.json`, `bench-lab` / `dotty.tools.benchlab` renamed to `labs/scala3` / `dotty.tools.compilerlab`, and system properties `benchlab.*` renamed to `compilerlab.*`.
- DONE Dropped: `scripts/compare.py` (the one-off dotc-vs-javac comparison), per-lab `CLAUDE.md` files (the root `AGENTS.md` has their rules), and the plan sections of the docs (kept as Checks and Future work).
- DONE Reusing a compiler between ops: `-p compiler=fresh|resident` and `-Dcompilerlab.resident` (for `CompileLoop`) in both labs, replacing Scala 3's `context=fresh|shared` and Scala 2's `global=fresh|resident`.
- DONE Cost per definition from the lab: perflab-agent `hook` probes, perflab-spans `CostStack` and `SpanCostListener`, a `CostHooks` and `def-costs.hooks` per lab, `--defs:<file>` / `--defs-listener:<class>`; the same tables as the patches ([def-costs.md](def-costs.md)). `src/costs` is gone from both labs.
- TODO `perflab trees` for the labs. A tree is a lab directory with its own sbt server, so comparing checkouts means a jvm-perf-lab worktree per checkout. Better: `@build=` in-fork variants for Scala 3 too (the generic part of `IsolatedBuild` in perflab-jmh).
- TODO perflab defaults for `perflab.toml` boilerplate (`[agent] jar`, `[index] flags`, `[benchmark] corpus/variants`).
- TODO Publish a tagged perflab (JitPack). Until then the labs build only where `mise run install` has run, which is the real blocker to sharing.
- TODO `OutputDigest` and a `perflab-phases.toml` for Scala 2.
- DONE Old lab branches deleted from the forks and locally; each is a tag `archive/<branch>` (scala3: `bench-lab-harness`, `bench-lab-perflab`, `bench-lab-curation-plan`, `scala3-counters-lab-dc0f98`; scala: `compiler-lab`, `compiler-lab-builds`, `compiler-lab-step5`, `compiler-lab-multi-global`, `compiler-lab-601e68`). Draft PRs retronym/scala3#14 and retronym/scala#144 are closed. Their worktrees are detached, not removed: they still hold results in `out/` and uncommitted experiment specs (`cc-fields-memo*.json`, `not-a-member-msg*.json`, `perf-integration-opt*.json`).

## Risks

- **The lab and the checkout's own sbt server share target directories.** Compiling from both at once can corrupt the Zinc analyses. Use one server per checkout at a time.
- **The lab breaks when the compiler build changes** in ways a source dependency notices: an sbt version bump, a meta-build dependency (ASM), or a path resolved against the working directory. Each failure is loud (load errors, or a full recompile on every run), and each fix belongs upstream.
- **Experiment branches stacked on the old lab** (`claude/positioned-bench`, the goForward worktrees) should drop their lab merges and point the lab at their worktree. Their specs are in the archive tag.
