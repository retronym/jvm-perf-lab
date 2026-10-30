# Optimising a JVM program with perflab

A decision procedure for closing a performance gap between two builds of a program (a branch and its merge base, a change and the code before it): what to run next, given what you have measured so far. It is written from a scala3 investigation (a ~4% serial-compile regression of a branch against its merge base, in [labs/scala3](../labs/scala3/README.md)), but the steps apply to any program perflab benchmarks.

How to run things is documented elsewhere and not repeated here: the [README](../README.md) for the commands, the perflab skill ([.claude/skills/perflab/SKILL.md](../.claude/skills/perflab/SKILL.md), also served at `/skill.md`) for running, checking and reporting, `perflab ab --help` for campaign specs, [paired-ab.md](paired-ab.md) for variants within a fork, [pmu-counters.md](pmu-counters.md) for the two ways of reading hardware counters, [caller-audit.md](caller-audit.md) for counting callers, [direct-launch.md](direct-launch.md) for launch mode, and the scala3 lab's [variance reduction](../labs/scala3/README.md#variance-reduction) notes.

The procedure narrows the question at each step: is there a gap at all, where does the time go, can a local fix remove it, and if not, is it more work or slower work. Each step's result decides whether the next is worth running. Campaigns take hours; ask the user before queueing one, and before voiding cells.

## 1. Establish the gap with a campaign

A single run of each build answers nothing: fork-to-fork noise on a whole-program benchmark is often as large as the difference you are chasing. Write a campaign spec with one variant per build (`"builds"`, in launch mode) and run `perflab ab run`, which interleaves the variants round by round so that drift in the machine (thermals, background load, a long-lived page cache) hits both alike.

Warm both variants fairly. In single-shot mode (`-bm ss -wi N -i M`) every op is timed, and a fixed number of warmup ops lets a variant that warms up more slowly (more code to compile, a different inlining shape) reach its steady state before measurement starts. Check `jit.compilations` in the measured iterations: if it is not close to zero, warm up longer. A variant that is slower only because it is still compiling is a different finding from one that is slower once warm.

Read the result through `perflab api` (or the MCP tools): `campaign <name>` for the summary, `cells` for per-fork values, `compare` for two variants' Δ ± CI and verdict. Look at min and median as well as the mean and its CI. On an M5 Pro, about one fork in ten runs ~10% slow, so per-fork scores are bimodal; one slow fork widens the CI enough that Welch's test says "flat" while the min and the median of each variant agree on a ~1% difference. When they agree with each other and disagree with the verdict, add rounds rather than conclude there is no gap. Instructions per op (any `xctrace` profile) are far steadier than time and are a good second witness, with the caveat that they miss memory effects (step 4).

Once the gap is real and its size known, the rest of the procedure explains it.

## 2. Profile both builds and diff them

Run a second campaign of the same two builds with `"profile": "async:cpu"` (fewer rounds will do: this is for locating, not measuring), then `perflab profdiff <cell-a> <cell-b> <out>` on a cell of each, or `perflab api diff` for the diffs already made. profdiff normalises samples per op, so the two runs compare even when one is slower; read the table of methods whose self time per op changed most, and the differential flame graph to see which callers they hang under.

The caveat that costs time: a frame's self time includes the cost of the loads it makes. A sample lands on whichever instruction is waiting, and an instruction waiting on a cache miss is charged with the miss, whoever caused the line to be cold. In the scala3 investigation `VarHandle.getAcquire` showed 2.4% of the tip's profile, which looked like the cost of acquire ordering; but its callers' self time fell by about 0.7 points against the base, so part of what moved into `getAcquire` was the cost of loading the field, which the callers had paid before. A frame that grows while its callers shrink by a similar amount is a moved load, not new work.

To see where a hot leaf's samples come from, collapse the cell's JFR (`jfrconv -o collapsed <cell>/*.jfr out.collapsed`, with the `jfrconv` of the async-profiler that recorded it) and group the stacks ending in that frame by their caller: each call site's share tells you whether one site or all of them pay, and so whether a local fix can help.

## 3. Try spot fixes as variants of one campaign, with a ceiling

When the profile points at a suspect, make each candidate fix a build and put them all in one campaign beside the base and the tip, so they share the same rounds and the same machine. Comparing fixes across campaigns run on different days compares the days.

Include a ceiling variant: an unsound or extreme version of the change that bounds what the suspected cost can possibly be. For the acquire loads above, the ceiling made every acquire an opaque load, which is wrong for concurrent use but costs nothing more than a plain load in serial code. If even the ceiling does not close the gap, the suspect is not the cause, and no sound version of the fix will do better; stop chasing it. If the ceiling closes the gap, the spot fixes show how much of it a sound change can recover.

Describe each variant in `"variantDescriptions"` with its commit, so the campaign's card says what was compared.

## 4. When the gap stays: hardware counters

If no local fix moves the gap, the cost is spread out, and the question becomes whether the tip does more work or does the same work more slowly. `xctrace` profiles answer that per op, on the benchmark thread alone ([pmu-counters.md](pmu-counters.md)). Run each as a campaign of the two builds, and start with `ipc`.

- **More instructions per op**: the tip executes extra code. Find it with a profdiff of kperf `cycles` and `instructions` events (`async:cycles+instructions` with `--kperf`): the instruction diff points at the code that runs more, without the memory effects that blur a time profile. Where you can name the operation, a [caller audit](caller-audit.md) counts it exactly.
- **The same instructions at a worse CPI**: the tip waits more. Look at memory: `mem-l1d` for L1D load misses and the cycles spent waiting on them, then the levels below with custom templates, and `frontend` for instruction-side misses when the tip's code footprint has grown (more or larger compiled methods, a lost inlining).

The bundled templates have four event slots each. To count other events, make a template with [`make_template.py`](../perflab-jmh/src/main/resources/io/github/retronym/perflab/xctrace/make_template.py) from JMH's bundled template and four event names, and name its path in the profile (`"profile": "xctrace:/abs/path/mem-l2.template.xml"`). The events this CPU has are in `/usr/share/kpep/*.plist` (the M5 Pro's is `as7`). Useful ones on the M5 Pro:

| Event | Counts |
|---|---|
| `PL2_CACHE_MISS_LD` | loads that miss the L2 |
| `LD_SRC_MEMSYS_NONSPEC` | loads served from beyond the cluster's caches: the closest the PMU has to an LLC-miss count |
| `L1D_TLB_MISS`, `L2_TLB_MISS_DATA` | data TLB misses at each level: a larger or more scattered heap working set |
| `L1I_CACHE_MISS_DEMAND` | instruction cache misses: code footprint |

A useful pair is an L2/LLC template (`CORE_ACTIVE_CYCLE`, `INST_ALL`, `PL2_CACHE_MISS_LD`, `LD_SRC_MEMSYS_NONSPEC`) and a TLB template (`CORE_ACTIVE_CYCLE`, `INST_ALL`, `L1D_TLB_MISS`, `L2_TLB_MISS_DATA`); keep cycles and instructions in every template so each campaign carries its own IPC.

Use the bundled templates or your own rather than Instruments' stock "CPU Counters" top-down template: its traces are large, and a campaign of them can fill the disk with `.ktrace` files.

## 5. Field layout and footprint

When the counters say the tip touches more memory for the same work, the usual cause in a JVM program is larger objects: a field added to a class with millions of instances, or a layout change that pushes an object over an 8-byte (or cache-line) boundary. Dump each build's instance layouts with JOL (`org.openjdk.jol:jol-core`): `ClassLayout.parseClass(Class.forName(name, false, loader))` for each class of interest, loading with `initialize = false` so no static initialiser runs. Run it with `-Djol.skipHotspotSAAttach=true`; without it JOL tries to attach the serviceability agent to its own process and hangs at 0% CPU.

Diff the instance sizes and field offsets of the hot classes between the builds, then weight each class's change by its instance count from a class histogram of the benchmark at steady state (`jcmd <pid> GC.class_histogram`; the scala3 lab's `CompileLoop` writes them with `-Dcompilerlab.histoAt`). A few bytes on a class with millions of instances can be the whole gap. The dump also catches accidental fields: in Scala, a constructor parameter that the class body reads after construction is kept as a field, so a parameter used once in a method silently grows every instance.

## 6. Practicalities

- **Keep the machine quiet.** A campaign's `"loadgate"` (`maxCores`, `quietSecs`) waits for a quiet machine and reruns cells that saw competing load, but anything you run while it measures (tests, builds, another benchmark) still competes with it or delays it. Do that work between campaigns, or accept that cells will be rerun.
- **Launch mode snapshots the build.** With `PERFLAB_BUILD_MODE=launch` a campaign builds each variant once and measures the snapshot ([direct-launch.md](direct-launch.md)), so editing a checkout mid-campaign does not change what is measured, and a resumed campaign measures the same build. To measure a new commit, make a new variant (or campaign).
- **Odd compiler crashes in a bench worktree** are usually damaged incremental state, not the change. Clean the worktree's ignored files (`git clean -fdX`, after checking what it will remove) and requeue the campaign.
