# Plan: branch exploration and the perflab server

Design: [branch-explore.md](branch-explore.md). Test case: retronym/scala3 `scala3-perf-integration` (`perfint-base`..`perfint-tip`, 13 first-parent commits).

## Contract between the runner and the view

`<campaign>/branch.json`, written when the range is resolved:

```json
{"checkout": "/path/to/repo", "range": "base..tip", "firstParent": true,
 "base": "<sha>", "tip": "<sha>",
 "commits": [{"sha": "...", "short": "0906947151", "variant": "0906947151", "tree": "...", "parents": ["..."],
              "subject": "...", "author": "...", "date": "2026-10-22T10:00:00+02:00", "index": 0,
              "merged": [{"sha": "...", "subject": "..."}]}],
 "order": ["<variant>", ...]}
```

`commits` is oldest first, and `index` is the position in it. `merged` lists, for a merge, the commits it brought in (`<first parent>..<merge>`, excluding first-parent ones). `order` is the explore order of the coarse pass. Cells live where every campaign's do: `<campaign>/<corpus>/<variant>/<round>/result.json`.

## Steps

1. DONE `branch.py`: resolve the range (git), `branch.json`, the explore order (endpoints, then van der Corput; corpora in turn; later rounds reversed), with tests.
2. DONE `ab.py`: a `"branch"` spec makes a variant and build per commit; one worktree per campaign; lazy builds keyed by tree + env + template; the explore order; an empty `result.json` is rerun; the between-cells control check (`PERFLAB_CONTROL`).
3. DONE index: the branch card. History rows with numbers, dots or both; Δ vs the previous row; the chart (score left, `gc.alloc.rate.norm` right, CI bars over a raw point cloud); selecting two rows to compare them; view state in the URL. `branchview.py` (`branch_view(campaign_dir)` is the data, tested in test_branchview.py); 99.9% CI from pooled `rawData` (t table in `metrics`), Δ spread from rounds' sd, else from the CIs; profdiff pages of a pair are linked when a `diff-*` name has both shas.
4. DONE Profiles: `perflab branch profile|diff` (`branchprofile.py`); a sibling campaign `<name>.profile` ("profileOf", the branch campaign's builds); row badges, the pair's a / DIFF / DIFF⁻¹ / b in the lightbox, cached by pair.json; "Profile & diff these two" queues on the server (which puts its token in the project's index), else shows the command.
5. DONE `perflab server`: a SQLite queue, one job at a time, jobs as command lines in their own process group; pause, resume and cancel; the CLI submits when a server is running; the UI's queue panel.
   - `server.py` (queue, worker, HTTP API, client), `serverui.py` (queue and storage pages), `control.py` (`checkpoint()`, the runner's side); `perflab server start|stop|status`, `perflab submit [--detach] -- <args>`, `perflab jobs`. A job runs with PERFLAB_CONTROL and PERFLAB_JOB set; a server restarted under a running job adopts it.
   - DONE `ab run` and `run` submit themselves while a server runs (not under PERFLAB_JOB or PERFLAB_LOCAL, which a foreground command sets for the perflab commands it runs), print the queue and index URLs and follow the job, into the caller's `--transcript` too; `--local` and `--dry-run` stay in the foreground. `perflab serve` prints the project's /p/<id>/ page on a running server, and starts its own only without one.
   - DONE the index under /p/<id>/ links the queue (masthead link, a chip of running/queued from /api/status); the queue page links each job's index and shows the running job's project live: fork timeline (running.json) and build panel (build.json).
   - DONE an adopted job's status: jobs run under an inline wrapper (the group leader, which outlives the group's SIGTERM) that writes <job dir>/exit.json; the transcript heuristic stays for a wrapper killed with SIGKILL.
   - Deferred: `perflab branch ...` submitting itself (add it to `cli.SUBMITS` when it exists).
6. DONE Admin: storage per campaign by tier (allocated bytes); cleanup actions with a dry run; pins.
   - `storage.py`; the server's /admin page and /api/storage. Active (running.json, build.json, a running job's argv or spec name, a running run.json, or written in the last 10 minutes) is never touched.
   - Deferred: APFS clones are separate inodes, so they still count once each (no portable way to see shared extents); pins from the index's cards.
7. RUNNING (job 1 on the server) The perfint campaign under the server: coarse pass on scalaz, then tastyQuery, then a second round; check the view against it.

8. DONE The load gate per measurement iteration (2 s samples; a burst over any iteration reruns the cell; `load.json` per cell).
9. Branch view, from looking at perfint-branch:
   - DONE profile metrics in the table and chart, from the campaign's own profile and from a `.profile` pass;
   - DONE within-fork uncertainty: each fork's 99.9% CI over its iterations as a thin whisker on its dash; with one fork and nothing pooled, the table shows it muted (`±~`), never used to colour Δ; the between/within-fork sd ratio in the tooltip (`branchview.within`, `within_of`);
   - DONE each iteration other load disturbed (`load.json`, else load.tsv for older cells) as an amber ring in the chart's cloud, a ring marker on the value with a tooltip naming iterations, cores and the top processes;
   - DONE a cell popover (click a value; Esc closes; a bottom sheet on a phone): its rounds and forks (mean ± CI within the fork), load, disturbed iterations, state, timeline (lightbox), jmh.log, build.log, flame graphs, and its voided cells (`<campaign>/.void/<corpus>/<variant>/<round>-<stamp>/`, `void.txt`), which count for nothing;
   - DONE (page side) **Void & rerun** per round, on the server: `bhVoid(campaign, corpus, variant, round, reason)` POSTs `/api/v1/void` then `/api/v1/rerun` (URLs in `BH_API`). The endpoints are server.py's.
   - Future work: a commit's CI with two forks is t(1) = 636.6 × sd/√2, wide enough to flatten the chart's scale; the chart could clip bars to the cloud's extent, or the explore order could give a commit its second fork in the same round.

10. DONE An API for agents (design §9): `perflab.api` (functions, JSON Schema registry, examples from the tests' fixtures), `/api/v1` on the server (index, openapi.json, docs page, reads as GET, actions as POST with the token), `perflab mcp` (MCP stdio, 2025-06-18: tools with input and output schemas, structuredContent), `perflab api` (CLI). Void (to `.void/`), unvoid, rerun (deduped against a queued job), submit and job control. `ab run <campaign>/spec.json` resumes a campaign with relative checkouts (spec.source). Tests: test_api.py, test_mcp.py.
    - The branch view's "Void & rerun" (step 9) calls POST /api/v1/void {project, campaign, corpus, variant, round, reason}, then POST /api/v1/rerun {project, campaign}.
    - Future: within-fork uncertainty in the API's stats once the view has it (step 9); a `changes` over E-Divisive change points (§5).

## Future work

- Adaptive exploration: refine where neighbours differ by more than their noise (Pinpoint).
- E-Divisive change points and triage state.
- Remote workers: testbeds, leases, git bundles, result upload (design §7).
- Drill into a merge: explore the commits a first-parent merge brought in.
