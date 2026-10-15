# Notes for coding agents

## Benchmark runs: share the index first

Before starting any campaign or run, give the user the URL of the live index, so they can watch results arrive:

```bash
perflab serve
```

It builds the index, starts a server for the campaigns directory if none is running, and prints the URL (the same one every time for a checkout). `perflab ab run` does the same before its first cell and logs the URL as `index (updates as cells finish): ...`; if you start a campaign directly, pass that line on before the first cell finishes.

The page keeps itself current: `perflab ab run` rebuilds the index around every cell, the page refetches its tables every 10 s, and its timeline follows the running fork every 5 s. Each campaign shows how many of its planned cells have results. There is nothing to regenerate when a campaign finishes, so don't tell the user you will.

## Commits

Say in the commit message that the change was made with an LLM. Do not add `Co-Authored-By` or "Generated with" trailers.
