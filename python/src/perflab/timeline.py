"""timeline.html for a run or a campaign cell: each fork from JVM start to exit, its iterations and, on the same
wall-clock axis, what the machine did meanwhile; see timeline.js for the files it reads. A standalone page, with the cell's files embedded;
the campaigns' index.html shows the same view live.

  perflab timeline <cell-dir> [<out.html>]
"""
import glob, html, json, os, sys, time

from . import ui

HERE = os.path.dirname(os.path.abspath(__file__))

# shared with index.py's live panel
CSS = """
:root { --life:#8a96a3; --v0:#2f6fb2; --v1:#c2571a; --v2:#2e8a57; --v3:#8a4fbf; --v4:#b8860b; --v5:#3a9aa6; --pause:#d33; --grey:#c3c9d1; }
@media (prefers-color-scheme: dark) { :root { --v0:#6ea8e6; --v1:#e58a4e; --v2:#5cc08a; --v3:#b58ae6; --v4:#e0b84a; --v5:#6cc6d1;
  --pause:#ff6b6b; --grey:#46505c; --life:#7d8996; } }
svg.timeline { background:var(--panel); border:1px solid var(--line); border-radius:8px; width:100%; touch-action:none; cursor:grab; display:block; }
svg.timeline text { fill:var(--fg); font-size:11px; } svg.timeline .lab { fill:var(--muted); } svg.timeline text.on { fill:var(--panel); } svg.timeline text.halo { paint-order:stroke; stroke:var(--panel); stroke-width:3px; }
svg.timeline .grid { stroke:var(--line); } svg.timeline .axis { stroke:var(--muted); opacity:.5; }
.tl-legend { margin:2px 0 6px; } .tl-legend span { display:inline-block; margin-right:14px; font-size:12px; color:var(--muted); }
.tl-legend i { display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:5px; vertical-align:-1px; }
.tl-tip { position:fixed; pointer-events:none; background:var(--panel); border:1px solid var(--line); border-radius:6px;
  padding:4px 8px; font-size:12px; display:none; max-width:360px; z-index:5; box-shadow:0 4px 16px rgba(0,0,0,.15); }
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
    files["profile"] = read("profile.txt")
    name, facts = describe(d)
    help_html = ui.help_popover(
        "Startup is JVM boot and benchmark setup; exit runs from the last iteration to the JVM's exit (with xctrace, it "
        "includes saving the trace). GC pauses come from the fork's GC log. With xctrace, counter lanes cover the measurement "
        "iterations, which is what xctrace records; cycles are per second, so one busy performance core is about 4–4.5 G. "
        "Each counter lane has its own scale. Wheel or pinch to zoom, drag to pan, double-click to reset.", right=True)
    page = f"""{ui.HEAD}<title>{html.escape(name)}: timeline</title>
{ui.style(ui.BASE, CSS, "main{padding:16px;max-width:1600px;margin:0 auto} h1{font-size:17px;margin:0;overflow-wrap:anywhere}")}
<main><div class="card-h"><span class="kind">timeline</span><h1>{html.escape(name)}</h1></div>
<p class="facts">{facts}</p>
<div class="card-h" style="margin:0"><span class="k">Each fork from JVM start to exit, on the wall clock.</span>{help_html}</div>
<div class="tl-legend" id="legend"></div><svg class="timeline" id="chart"></svg></main><div class="tl-tip" id="tip"></div>
<script>{script()}
BenchTimeline.mount(document.getElementById('chart'), document.getElementById('legend'), document.getElementById('tip'))
  .set(BenchTimeline.parse({json.dumps(files)}));
</script>
"""
    open(out, "w").write(page)
    return out


def describe(d):
    """(name, facts html) of a run or a campaign cell: its name, and its benchmark, parameters, profile and date."""
    esc = html.escape
    from . import index
    parts = os.path.abspath(d).rstrip("/").split(os.sep)
    # a campaign cell is <campaign>/<corpus>/<variant>/<round>
    name = f"{parts[-4]} · {parts[-3]} · {parts[-2]} #{parts[-1]}" if parts[-1].isdigit() and len(parts) >= 4 else parts[-1]
    benches, params, opts, _, _ = index.run_args(d)
    facts = [f"<b>{esc(' '.join(b.rsplit('.', 1)[-1] for b in benches))}</b>"] if benches else []
    facts += [f"<code>{esc(k)}={esc(v)}</code>" for k, v in params.items() if v]
    try:
        profile = open(os.path.join(d, "profile.txt")).read().strip()
    except OSError:
        profile = ""
    if profile and profile != "none":
        facts.append(f"profile <code>{esc(profile)}</code>")
    stamps = [os.path.getmtime(os.path.join(d, f)) for f in ("jmh.args", "iterations.tsv") if os.path.exists(os.path.join(d, f))]
    if stamps:
        facts.append(esc(time.strftime("%a %d %b %Y %H:%M", time.localtime(min(stamps)))))
    return name, " · ".join(facts)


def main(argv):
    print(write(argv[0], argv[1] if len(argv) > 1 else None))
    return 0
