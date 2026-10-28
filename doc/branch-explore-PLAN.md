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
4. TODO Profiles: a branch spec's `"profileCampaign"`; profile cells linked from rows; profdiff of a selected pair, cached; a "profile these two" action (needs the server).
5. DONE `perflab server`: a SQLite queue, one job at a time, jobs as command lines in their own process group; pause, resume and cancel; the CLI submits when a server is running; the UI's queue panel.
   - `server.py` (queue, worker, HTTP API, client), `serverui.py` (queue and storage pages), `control.py` (`checkpoint()`, the runner's side); `perflab server start|stop|status`, `perflab submit [--detach] -- <args>`, `perflab jobs`. A job runs with PERFLAB_CONTROL and PERFLAB_JOB set; a server restarted under a running job adopts it.
   - Deferred: `ab run` and `run` submitting by themselves when `server.running()` (and not when PERFLAB_JOB is set); the index linking the queue (and the server's home from the project pages it serves); the running job's live timeline on the queue page; reading `rc` of an adopted job.
6. DONE Admin: storage per campaign by tier (allocated bytes); cleanup actions with a dry run; pins.
   - `storage.py`; the server's /admin page and /api/storage. Active (running.json, build.json, a running job's argv or spec name, a running run.json, or written in the last 10 minutes) is never touched.
   - Deferred: APFS clones are separate inodes, so they still count once each (no portable way to see shared extents); pins from the index's cards.
7. TODO The perfint campaign under the server: coarse pass on scalaz, then tastyQuery, then a second round; check the view against it.

## Future work

- Adaptive exploration: refine where neighbours differ by more than their noise (Pinpoint).
- E-Divisive change points and triage state.
- Remote workers: testbeds, leases, git bundles, result upload (design §7).
- Drill into a merge: explore the commits a first-parent merge brought in.
