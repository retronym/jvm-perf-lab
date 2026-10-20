# Cost per definition, from the lab side

## Problem

The cost per definition (exclusive time and allocation per definition, and an async-profiler span per frame; [scala3/doc/def-costs.md](scala3/doc/def-costs.md)) exists as compiler patches: retronym/scala3 and retronym/scala `cost-per-definition`, adding `-Yprofile-defs`, `-Yprofile-defs-listener`, `DefCosts` and hooks in the typer, Namer, transforms and hash-consing tables. They are not ready to upstream, and while they are patches, measuring a compiler branch with costs per definition means rebasing them onto it. The point of the labs is that the measured branch carries no lab commits, so the cost per definition should come from the lab too, for both compilers, with the same table (`perflab defcosts`) and spans (`jfrconv --spans`).

## What the patches hook

| frame | Scala 2 | Scala 3 |
|---|---|---|
| phase, unit | `Profiler.before/afterPhase`, `before/afterUnit` (existing) | `onPhase`, `onUnit` (existing, `inline`, calling `beforePhase`/`afterPhase` etc.) |
| def (typer), retype (after it) | `before/afterTypedImplDef` (existing) | `onTypedDef` (existing) in `typed{Val,Def,Type,Class}Def`; new in `Recheck` |
| complete (Namer) | new: `TypeCompleterBase.complete` | new: around `completeInCreationContext` in `Namer.Completer.complete` |
| load (classfile, TASTy) | `before/afterCompletion` (existing) | `onCompletion` (existing) |
| implicit, macro / inline | existing | existing |
| transform, per member | none (no common seam) | new: the `ValDef`/`DefDef`/`TypeDef` cases of `MegaPhase.transformTree`, `MacroTransform`, `Inlining` |
| rehash | none | new: `WeakHashSet.resize` in the three `Uniques` tables |

Half the value is in the new hooks: the Namer completion is what charges a typed-ahead body to its own definition, and the per-member transforms are most of Scala 3's time after the typer.

## Options

**(a) Patch overlay.** Compile replacement classes in the lab against the checkout and put them ahead of the compiler on the benchmark classpath.

- A `Profiler` subclass (written in Java, which does not see `sealed`, and installed by reflection into `Run.profiler` or the context's store) reaches only the existing hooks. No Namer completion, no per-member transforms, no rehash.
- Overlays of the files with new hooks (`Namers.scala`, `Typer.scala`, `Namer.scala`, `MegaPhase.scala`, `Recheck.scala`, `Uniques.scala`, `Contexts.scala`) reach everything, but they are copies of the compiler's hottest files: every upstream change to them needs a re-merge, a stale overlay silently reverts the branch's own change to that file (the very change being measured), and Scala 3's hooks are `inline` methods, so changing one means recompiling every caller, not just the overlaid file. The overlay also has to be compiled the way the checkout is (Scala 2 with STARR and the optimizer, Scala 3 bootstrapped).

**(b) Bytecode instrumentation.** `perflab-agent` weaves calls into the compiler's methods as they load, from a spec naming them; the cost stack lives in the lab, compiled against the checkout.

- Coverage: everything the patches reach. Existing hooks are reached by weaving `NoOpProfiler`'s hook methods (each is called on every run, with its key as an argument); new ones by weaving enter/exit around a method: `TypeCompleterBase.complete`, `Namer$Completer.completeInCreationContext`, `MegaPhase.transformTree` (filtered to members of classes in the hook), `WeakHashSet.resize` (filtered to the `Uniques` tables by receiver class, a constant key and label). Where the patch put a hook inside a method (the cases of `transformTree`), the agent hooks the method and filters in the hook. Nothing in `Uniques` or `Contexts` changes.
- Keys without allocation: the woven call passes the receiver and the method's own arguments (references as `Object`) to a static hook; the hook takes the symbol from an argument, or from the receiver (a completer's tree, for the definition's size). Labels are made only when a span is kept, as now.
- Off: no agent, no change to a single class. This is better than the patches, which leave a field load and null check per hook in every run, and whose off-cost was never measured. On: an `invokestatic` per hook, inlined by the JIT, then the same stack as the patches.
- Exceptions: an around probe calls its exit hook before each return and from a catch-all handler (lowest priority in the exception table, rethrowing). The handler's stack map frame declares no locals, so it verifies whatever the method does with its slots.
- Robustness: a spec names about a dozen methods by class, name and descriptor prefix. A rename or signature change fails loudly (the agent reports every probe it never wove, and the lab refuses a table with no phase frames) and is fixed in one spec line, not by re-merging a file. The named methods (`typedDefDef`, `NoOpProfiler`'s hooks, `completeInCreationContext`, `transformTree`, `resize`) have been stable for years. What the agent cannot follow is a hook moving inside a method, which the overlay can't either without a re-merge.
- Weaving only the named class's own method keeps the patches' semantics: an override that calls `super` (erasure's `Typer.typedDefDef`) is one frame, not two.

**Choice: (b).** It reaches every hook, costs nothing when off, and its maintenance is a list of method names instead of copies of the compiler's largest files.

## Design

- **perflab-agent: `hook` probes.** `hook <name> at=Class#method[(desc-prefix] call=Hooks#enter [exit=Hooks#exit]`: at entry, `invokestatic Hooks.enter(Object receiver, <the method's parameters, references as Object>)`; with `exit`, `Hooks.exit()` before each return and on a throw. Generic: the agent knows nothing about compilers. Hook classes are resolved from the woven class's loader, so they sit beside the compiler on the benchmark classpath.
- **perflab-spans: the cost stack.** `CostStack` (frames reused by depth, self time and allocation, accumulators per kind, phase and key, the table `perflab defcosts` reads) and `CostListener` / `SpanCostListener`, in Java, parameterised by the compiler's kinds and a `Keys` adapter that names a key (full name, file, line, size, label). Both labs share it; the stack is what the two `DefCosts` already had in common.
- **Each lab: a hook object and a spec.** `CostHooks` (Scala, compiled against the checkout) maps the hooks to frames: which symbols are tracked (class members and top-level), the phase of per-phase kinds, `def` after the typer becoming `transform`/`retype`, the transparent frames below. `def-costs.hooks` names the methods.
- **Every enter pushes, every exit pops.** An untracked symbol (a local definition) gets a transparent frame: no clocks, no row, its children's time passed to its parent. Exits then need no key, which Scala 3's `after*` hooks don't have (their token is an empty string with the profiler off), and an around probe's exit needs no saved arguments.
- **Turned on per compile by lab options, not scalac's**: `--defs:<file>` and `--defs-listener:<class>` in `scalacOptions` (or a variant), stripped by the lab before the compiler sees them, so a campaign can still compare stack-off, listener and table variants within a fork. They need the agent (`-jvmArgsAppend -javaagent:<perflab-agent>=spec=def-costs.hooks`); without it, the lab fails rather than writing an empty table.

## Results

Smoke runs only (one fork, one short iteration, on a loaded machine): equal tables, not overhead.

- **Scala 2, scalap.** The agent's table has the same 8613 rows as the patch's `-Yprofile-defs`, on the patched branch and on its branch point (stock 2.13.x): every key, call count, file, line and size equal. Spans: 1773 span events in a CPU recording, definitions in the flame graph's span panel.
- **Scala 3, dottyUtil.** Against the patch on the same checkout, every row both tables have has the same call count (14845 keys, all kinds). The agent has 72 more `load` rows; on scalaz, 237 more `complete` rows and 25 symbols completed twice rather than once (scalaz's `rehash` rows land in slightly different phases between runs: the tables are weak, so when they grow depends on GC). The extra frames are completions and loads under a context whose profiler is not the run's: 261 completions on scalaz run with `ctx.profiler` the base's `NoOpProfiler` (e.g. from implicit scope computation in `OfTypeImplicits`), and the patch's hooks, which go through `ctx.profiler`, drop them. The agent, keyed to the thread rather than the context, sees them. It works the same on the patch's branch point. Spans: 1747 span events on dottyUtil.
- **Robustness, seen once already:** Scala 3 copies the `Profiler` trait's empty hook bodies into `NoOpProfiler`'s forwarders, so weaving the trait alone reached nothing; the spec weaves both (on the patched branch, where `Profiler` is a class, only the class's lines match). Every miss of this kind shows up as a missing kind in the table.

## Future work

- Overhead, paired within forks (`campaigns/def-costs-overhead.json` in each lab): the woven hooks with the stack off, the listener, the table; and the agent loaded but off against no agent, across forks.
- `perflab run --profile` with several profiles (`async:cpu` and the hooks), instead of `-jvmArgsPrepend -javaagent:...` for spans.
- `@build=` variants (Scala 2's `IsolatedBuild`) load a compiler in its own class loader: `CostHooks` must be loadable from it for the woven calls to resolve.
- The patch branches (retronym/scala and retronym/scala3 `cost-per-definition`) can be dropped from the upstream plan, or kept for the one finding worth upstreaming on its own: the profiler's hooks miss work done under contexts that do not carry the run's profiler.
