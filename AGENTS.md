# Notes for coding agents

## Benchmark runs: share the index first

Before starting any campaign or run, give the user the URL of the live index, so they can watch results arrive:

```bash
perflab serve
```

It builds the index, starts a server for the checkout's campaigns and runs if none is running, and prints the URL (the same one every time for a checkout). `perflab run` and `perflab ab run` do the same before they start and log the URL as `index (updates ...): ...`; if you start one directly, pass that line on. Never start another HTTP server for results: everything is on this one.

The page keeps itself current: `perflab ab run` rebuilds the index around every cell, `perflab run` every 10 s while it runs, the page refetches its tables every 10 s, and its timeline follows the running fork every 5 s. Each campaign shows how many of its planned cells have results, each run its status (running, finished, failed, interrupted). There is nothing to regenerate when a campaign or run finishes, so don't tell the user you will.

## Commits

Say in the commit message that the change was made with an LLM. Do not add `Co-Authored-By` or "Generated with" trailers.
