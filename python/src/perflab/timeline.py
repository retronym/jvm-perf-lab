"""timeline.html for a run or a campaign cell: each fork from JVM start to exit, its iterations and, on the same
wall-clock axis, what the machine did meanwhile; see timeline.js for the files it reads. A standalone page, with the cell's files embedded;
the campaigns' index.html shows the same view live.

  perflab timeline <cell-dir> [<out.html>]
"""
import glob, html, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))

# shared with index.py's live panel
CSS = """
:root { --life:#9aa5b1; --v0:#2f6fb2; --v1:#c2571a; --v2:#2e8a57; --v3:#8a4fbf; --v4:#b8860b; --v5:#3a9aa6; --pause:#d33; --grey:#c3c9d1; }
@media (prefers-color-scheme: dark) { :root { --v0:#6ea8e6; --v1:#e58a4e; --v2:#5cc08a; --v3:#b58ae6; --v4:#e0b84a; --v5:#6cc6d1;
  --pause:#ff6b6b; --grey:#46505c; --life:#5f6b78; } }
svg.timeline { background:var(--panel); border:1px solid var(--line); border-radius:8px; width:100%; touch-action:none; cursor:grab; display:block; }
svg.timeline text { fill:var(--fg); font-size:11px; } svg.timeline .lab { fill:var(--muted); } svg.timeline .grid { stroke:var(--line); }
.tl-legend span { display:inline-block; margin-right:12px; font-size:12px; }
.tl-legend i { display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:4px; vertical-align:-1px; }
.tl-tip { position:fixed; pointer-events:none; background:var(--panel); border:1px solid var(--line); border-radius:6px;
  padding:4px 8px; font-size:12px; display:none; max-width:360px; z-index:5; }
"""


def script():
    return open(os.path.join(HERE, "timeline.js")).read()


def write(d, out=None):
    out = out or os.path.join(d, "timeline.html")
    read = lambda n: open(os.path.join(d, n)).read() if os.path.exists(os.path.join(d, n)) else ""
    # a run of several forks: one GC log per fork, and (xctrace) one counter series per fork, named after its trace
    gc = "".join(open(f).read() for f in sorted(glob.glob(os.path.join(d, "gc.log")) + glob.glob(os.path.join(d, "gc-*.log"))))
    series = read("timeline.tsv")
    if not series:
        parts = [open(f).read().splitlines() for f in sorted(glob.glob(os.path.join(d, "*.timeline.tsv")))]
        series = "\n".join(parts[0][:1] + [l for p in parts for l in p[1:]]) + "\n" if parts else ""
    files = {"iterations": read("iterations.tsv"), "timeline": series, "gc": gc, "load": read("load.tsv")}
    page = f"""<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Timeline</title>
<style>
:root {{ --bg:#f6f7f9; --panel:#fff; --fg:#1d232b; --muted:#5d6875; --line:#dde2e8; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#14181d; --panel:#1b2027; --fg:#e3e8ee; --muted:#94a0ad; --line:#2c333c; color-scheme:dark; }} }}
body {{ margin:0; background:var(--bg); color:var(--fg); font:13px/1.45 -apple-system,system-ui,sans-serif; }}
main {{ padding:16px; }} h1 {{ font-size:16px; margin:0 0 4px; overflow-wrap:anywhere; }} .k {{ color:var(--muted); font-size:12px; }}
{CSS}
</style>
<main><h1>{html.escape(os.path.relpath(d))}</h1>
<p class="k">Each fork from JVM start to exit, on the wall clock: startup (JVM boot and benchmark setup), iterations,
exit, and GC pauses. Wheel or pinch to zoom, drag to pan, double-click to reset. With xctrace, counter lanes cover the
measurement iterations (xctrace records those); cycles are per second, so one busy performance core is about 4–4.5 G.</p>
<div class="tl-legend" id="legend"></div><svg class="timeline" id="chart"></svg></main><div class="tl-tip" id="tip"></div>
<script>{script()}
BenchTimeline.mount(document.getElementById('chart'), document.getElementById('legend'), document.getElementById('tip'))
  .set(BenchTimeline.parse({json.dumps(files)}));
</script>
"""
    open(out, "w").write(page)
    return out


def main(argv):
    print(write(argv[0], argv[1] if len(argv) > 1 else None))
    return 0
