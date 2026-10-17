"""<campaigns>/index.html: every campaign and every run of `perflab run` (<runs>), newest first, and a live timeline of
the running fork. A campaign shows a summary and its cells (score, cycles, instructions, flags), links to each cell's
flame graphs (greyed out until rendered) and timeline, its differential flame graphs, notes (<campaign>/NOTES.md) and
findings (<campaigns>/FINDINGS.md); a run its benchmark, parameters, JVM, status, scores, and links to its timeline,
logs and flame graphs. `perflab ab` rebuilds it around each cell, `perflab run` at its start and end, and the page
refreshes itself.

  perflab index [<campaigns-dir> [<runs-dir>]]
"""
import glob, html, json, os, re, sys, time

from . import config, regraph, specs, timeline

root = None
esc = html.escape
rel = lambda f: esc(os.path.relpath(f, root))


def link(path, label):
    return f'<a href="{rel(path)}">{esc(label)}</a>' if os.path.exists(path) else f'<span class="pending">{esc(label)}</span>'


def flame_graphs(cell):
    """Links to an async-profiler cell's or run's flame graphs, per event and kind (greyed out until rendered)."""
    if not (os.path.exists(os.path.join(cell, "profile.txt")) and open(os.path.join(cell, "profile.txt")).read().startswith("async")):
        return ""
    jfr = (glob.glob(os.path.join(cell, "**", "*.jfr"), recursive=True) or [None])[0]
    if not jfr:
        return ""
    parts = []
    for label, _ in regraph.events_of(cell):
        ks = " · ".join(link(regraph.graph_path(jfr, label, k), k) for k in regraph.kinds())
        parts.append(f"<b>{esc(label.removeprefix('hw-'))}</b>: {ks}")
    return "<br>".join(parts)


def cell_row(spec, corpus, variant, cell):
    res_f = os.path.join(cell, "result.json")
    if not os.path.exists(res_f):
        return None
    try:
        r = json.load(open(res_f))[0]
        p = r["primaryMetric"]
    except (OSError, ValueError, IndexError, KeyError):
        # JMH writes result.json when the fork ends, so an empty or partial one is a cell still running
        return (f'<tr class="running" data-corpus="{esc(corpus)}" data-profiled="0"><td>{esc(corpus)}</td>'
                f'<td>{esc(variant)} #{esc(os.path.basename(cell))}</td><td colspan="5"><i>running</i></td><td></td></tr>',
                time.time(), corpus, None)
    m = r.get("secondaryMetrics", {})
    cyc = m.get("xctrace.CORE_ACTIVE_CYCLE", {}).get("score")
    ins = m.get("xctrace.INST_ALL", {}).get("score")
    scalac = r.get("params", {}).get("scalacOptions", "")
    pattern = re.compile(config.get().get("index", "flags"))
    flags = " ".join([a for a in r["jvmArgs"] if pattern.search(a) and not a.startswith("-Dperflab.")] + ([scalac] if scalac else []))
    graphs = flame_graphs(cell)
    tl = os.path.join(cell, "timeline.html")
    if os.path.exists(tl):
        graphs = link(tl, "timeline") + ("<br>" + graphs if graphs else "")
    when = os.path.getmtime(res_f)
    version = specs.of_cell(cell)
    ver_html = f' <span class="when" title="spec version">spec {esc(version)}</span>' if version else ""
    html_row = (f'<tr data-corpus="{esc(corpus)}" data-profiled="{1 if graphs else 0}">'
                f"<td>{esc(corpus)}</td><td>{esc(variant)} #{esc(os.path.basename(cell))}{ver_html}</td>"
                f"<td>{p['score']:.0f} ± {p['scoreError']:.0f}</td><td>{f'{cyc / 1e9:.2f}G' if cyc else ''}</td>"
                f"<td>{f'{ins / 1e9:.3f}G' if ins else ''}</td>"
                f"<td><code>{esc(flags) or '(none)'}</code></td><td class=\"when\">{stamp(when)}</td><td>{graphs}</td></tr>")
    return html_row, when, corpus, (variant, p["score"], cyc, ins, version)


def summary(name, cells):
    """Per corpus and variant: mean ms/op, cycles/op and instructions/op over rounds, each against the spec's first
    variant (in the order of the campaign's spec.json, else alphabetical)."""
    spec_f = os.path.join(root, name, "spec.json")
    order = list(json.load(open(spec_f)).get("variants", {})) if os.path.exists(spec_f) else []
    out = []
    for corpus in sorted(cells):
        vs = cells[corpus]
        versions = {c[4] for cs in vs.values() for c in cs}
        mixed = (f' <span class="mixed" title="the cells of this corpus ran under different spec versions">⚠ mixed spec versions: '
                 f'{esc(", ".join(sorted(v or "unversioned" for v in versions)))}</span>') if len(versions) > 1 else ""
        names = [v for v in order if v in vs] + sorted(v for v in vs if v not in order)
        def stats(xs):
            xs = [x for x in xs if x]
            if not xs:
                return None, None
            mean = sum(xs) / len(xs)
            sd = (sum((x - mean) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5 if len(xs) > 1 else 0.0
            return mean, sd
        base = {k: stats([c[i] for c in vs[names[0]]])[0] for i, k in ((1, "ms"), (2, "cyc"), (3, "ins"))}
        for v in names:
            cs = vs[v]
            tds = [f"<td>{esc(corpus)}{mixed if v == names[0] else ''}</td><td>{esc(v)}</td><td>{len(cs)}</td>"]
            for i, k, fmt in ((1, "ms", lambda x: f"{x:.0f}"), (2, "cyc", lambda x: f"{x / 1e9:.3f}G"), (3, "ins", lambda x: f"{x / 1e9:.3f}G")):
                mean, sd = stats([c[i] for c in cs])
                if mean is None:
                    tds.append("<td></td><td></td>"); continue
                rel_sd = f" ± {100 * sd / mean:.1f}%" if len(cs) > 1 else ""
                d = "" if v == names[0] or not base[k] else f"{100 * (mean / base[k] - 1):+.2f}%"
                tds.append(f"<td>{fmt(mean)}{rel_sd}</td><td>{d}</td>")
            out.append("<tr>" + "".join(tds) + "</tr>")
    return ("<table class=\"summary\"><tr><th>corpus</th><th>variant</th><th>n</th><th>ms/op</th><th>Δ</th><th>cycles/op</th><th>Δ</th>"
            "<th>instructions/op</th><th>Δ</th></tr>" + "".join(out) + "</table>") if out else ""


def spec_history(spec_dir, counts):
    """The campaign's spec versions, each with the cells that ran under it and what changed from the previous version."""
    hist = specs.history(spec_dir)
    if not hist and not counts.get(None):
        return ""
    items = []
    for v, _, changes in hist:
        when = time.strftime("%a %d %b %H:%M:%S", time.strptime(v[:15], "%Y%m%d-%H%M%S"))
        body = ("<ul>" + "".join(f"<li><code>{esc(c)}</code></li>" for c in changes) + "</ul>") if changes else ""
        items.append(f'<li><b>{esc(v)}</b> <span class="when">{when} · {counts.get(v, 0)} cells</span>{body}</li>')
    if counts.get(None):
        items.append(f'<li><i>unversioned</i> <span class="when">{counts[None]} cells (before spec versions were recorded)</span></li>')
    return f'<div class="specs"><b>Spec versions</b><ul>{"".join(items)}</ul></div>'


# JMH options that take no value; every other option in a run's jmh.args is followed by one
JMH_FLAGS = {"-h", "-l", "-lp", "-lprof", "-lrf"}
RUN_STATE = "run.json"
STALE_SECS = 600  # a run without run.json (an older perflab) counts as running while its logs grow


def run_args(run):
    """A run's jmh.args as (benchmarks, {param: value}, [(option, value)], JVM, JVM arguments)."""
    try:
        args = open(os.path.join(run, "jmh.args")).read().splitlines()
    except OSError:
        return [], {}, [], None, []
    benches, params, opts, jvm, jvm_args = [], {}, [], None, []
    i = 0
    while i < len(args):
        a = args[i]
        if a.startswith("-") and a not in JMH_FLAGS and i + 1 < len(args):
            v = args[i + 1]
            if a == "-p":
                k, _, pv = v.partition("=")
                params[k] = pv
            elif a == "-jvm":
                jvm = v
            elif a in ("-jvmArgs", "-jvmArgsAppend", "-jvmArgsPrepend"):
                jvm_args += v.split()
            elif a not in ("-o", "-rf", "-rff", "-prof"):
                opts.append((a, v))
            i += 2
        else:
            if not a.startswith("-"):
                benches.append(a)
            i += 1
    return benches, params, opts, jvm, jvm_args


def run_status(run):
    """(status, detail, results) of a run: running, finished, failed or interrupted; results are result.json's entries."""
    try:
        results = json.load(open(os.path.join(run, "result.json")))
    except (OSError, ValueError):
        results = None
    try:
        st = json.load(open(os.path.join(run, RUN_STATE)))
    except (OSError, ValueError):
        st = None
    if st:
        if st.get("status") == "running":
            alive = True
            try:
                os.kill(st["pid"], 0)
            except (OSError, KeyError, TypeError):
                alive = False
            return ("running", "", results) if alive else ("interrupted", "perflab exited without finishing the run", results)
        if st.get("status") == "failed":
            return "failed", f"build exited with {st.get('rc')}", results
        if st.get("status") == "interrupted":
            return "interrupted", "", results
        return ("finished", "", results) if results else ("failed", "no results", results)
    if results:
        return "finished", "", results
    logs = [f for f in (os.path.join(run, n) for n in ("jmh.log", "build.log", "iterations.tsv", "result.json")) if os.path.exists(f)]
    if logs and time.time() - max(os.path.getmtime(f) for f in logs) < STALE_SECS:
        return "running", "", None
    return "failed", "no results", None


def iterations(run):
    """'forks · warmup · measurement · last score' from a run's iterations.tsv, for a run in progress."""
    try:
        rows = [l.split("\t") for l in open(os.path.join(run, "iterations.tsv")).read().splitlines()[1:]]
    except OSError:
        return ""
    rows = [r for r in rows if len(r) >= 10]
    if not rows:
        return ""
    count = lambda k: sum(1 for r in rows if r[1] == k)
    last = next((r for r in reversed(rows) if r[5]), None)
    forks = len({r[8] for r in rows})
    return (f"{forks} fork{'s' if forks > 1 else ''} · {count('warmup')} warmup, {count('measure')} measurement iterations"
            + (f" · last {float(last[5]):.1f} {last[9]}" if last else ""))


def short_jvm(jvm):
    home = os.path.expanduser("~")
    jvm = jvm.removesuffix("/bin/java")
    return "~" + jvm[len(home):] if jvm.startswith(home + "/") else jvm


def run_section(run):
    """A run of `perflab run`: its benchmark, parameters, JVM, status, scores and links. (mtime, html) or None."""
    if not any(os.path.exists(os.path.join(run, f)) for f in ("jmh.args", "result.json", "jmh.log")):
        return None
    name = os.path.basename(run.rstrip("/"))
    benches, params, opts, jvm, jvm_args = run_args(run)
    status, detail, results = run_status(run)
    corpus_param = config.get().get("benchmark", "corpus")
    corpus = params.get(corpus_param, "")
    try:
        profile = open(os.path.join(run, "profile.txt")).read().strip()
    except OSError:
        profile = ""
    pattern = re.compile(config.get().get("index", "flags"))
    flags = [a for a in jvm_args if pattern.search(a) and not a.startswith("-Dperflab.")]
    facts = [f"<b>{esc(' '.join(benches) or '(default benchmark)')}</b>"]
    facts += [f"<code>-p {esc(k)}={esc(v)}</code>" for k, v in params.items()]
    if opts:
        facts.append(f"<code>{esc(' '.join(f'{o} {v}' for o, v in opts))}</code>")
    if jvm:
        facts.append(f'JVM <code title="{esc(jvm)}">{esc(short_jvm(jvm))}</code>')
    if flags:
        facts.append(f"flags <code>{esc(' '.join(flags))}</code>")
    if profile and profile != "none":
        facts.append(f"profile <code>{esc(profile)}</code>")
    graphs = flame_graphs(run)
    links = [link(os.path.join(run, f), label) for f, label in (("timeline.html", "timeline"), ("jmh.log", "jmh.log"),
                                                                 ("build.log", "build.log"), ("report.md", "audit report"))
             if os.path.exists(os.path.join(run, f)) or f == "timeline.html"]
    rows = ""
    if results:
        varying = [k for k in results[0].get("params", {}) if len({str(r.get("params", {}).get(k)) for r in results}) > 1]
        out = []
        for r in results:
            p = r["primaryMetric"]
            m = r.get("secondaryMetrics", {})
            cyc = m.get("xctrace.CORE_ACTIVE_CYCLE", {}).get("score")
            ins = m.get("xctrace.INST_ALL", {}).get("score")
            rp = r.get("params", {})
            err = f" ± {p['scoreError']:.3g}" if isinstance(p.get("scoreError"), (int, float)) else ""
            out.append(f'<tr data-corpus="{esc(str(rp.get(corpus_param, corpus)))}" data-profiled="{1 if graphs else 0}">'
                       f"<td>{esc(r['benchmark'].rsplit('.', 1)[-1])}</td>"
                       f"<td><code>{esc(' '.join(f'{k}={rp.get(k)}' for k in varying))}</code></td>"
                       f"<td>{p['score']:.4g}{err} {esc(p.get('scoreUnit', ''))}</td><td>{f'{cyc / 1e9:.2f}G' if cyc else ''}</td>"
                       f"<td>{f'{ins / 1e9:.3f}G' if ins else ''}</td></tr>")
        rows = ("<table><tr><th>benchmark</th><th>params</th><th>score</th><th>cycles/op (xctrace)</th><th>instructions/op</th></tr>"
                + "".join(out) + "</table>")
    progress = iterations(run) if status == "running" else ""
    mtimes = [os.path.getmtime(os.path.join(run, f)) for f in os.listdir(run)] or [os.path.getmtime(run)]
    args_f = os.path.join(run, "jmh.args")
    started = os.path.getmtime(args_f) if os.path.exists(args_f) else min(mtimes)
    last = time.time() if status == "running" else max(mtimes)
    span = f"{stamp(started)} – {stamp(max(mtimes))}" if status != "running" else f"since {stamp(started)}"
    badge = f'<span class="status {status}">{status}{": " + esc(detail) if detail else ""}</span>'
    return last, (f'<section class="run" data-last="{last:.0f}" data-notes="0"><h2>run {esc(name)} <span class="when">{span}</span> {badge}</h2>'
                  f'<p>{" · ".join(facts)}</p>{f"<p>{esc(progress)}</p>" if progress else ""}{rows}'
                  f'<p>{" · ".join(links)}{"<br>" + graphs if graphs else ""}</p></section>')


def stamp(t):
    return time.strftime("%a %d %b %H:%M", time.localtime(t))


def md(text):
    """Just enough Markdown for notes: paragraphs, `- ` bullets, **bold**, `code` and [text](url) links."""
    import re as _re
    def inline(t):
        t = esc(t)
        t = _re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', t)
        t = _re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
        return _re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    out, items = [], []
    for block in text.strip().split("\n\n"):
        lines = block.splitlines()
        if lines[0].startswith("### "):
            out.append(f"<h3>{inline(lines[0][4:])}</h3>")
            lines = lines[1:]
        if lines and all(l.lstrip().startswith("- ") for l in lines):
            out.append("<ul>" + "".join(f"<li>{inline(l.lstrip()[2:])}</li>" for l in lines) + "</ul>")
        elif lines:
            out.append(f"<p>{inline(' '.join(lines))}</p>")
    return "".join(out)


def notes(path):
    return f'<div class="notes">{md(open(path).read())}</div>' if os.path.exists(path) else ""


def progress(spec_dir):
  """(cells with results, cells planned) from the campaign's spec.json; None without one."""
  try:
    s = json.load(open(os.path.join(spec_dir, "spec.json")))
    variants = 1 if s.get("paired") else len(s["variants"])
    planned = s.get("rounds", 2) * len(s["corpora"]) * variants
  except (OSError, ValueError, KeyError, TypeError):
    return None
  done = sum(1 for f in glob.glob(os.path.join(spec_dir, "*", "*", "*", "result.json")) if os.path.getsize(f) > 0)
  return done, planned


def progress_badge(prog, name):
  if not prog:
    return ""
  done, planned = prog
  running = ""
  try:
    r = json.load(open(os.path.join(root, "running.json")))
    running = " · running" if r.get("campaign") == name else ""
  except (OSError, ValueError):
    pass
  cls = "done" if done >= planned else "partial"
  return f' <span class="prog {cls}">{done} of {planned} cells{running}</span>'


def build(campaigns, runs=None):
  """<campaigns>/index.html over the campaigns and the runs of `perflab run` (<runs>, default [paths] runs)."""
  global root
  root = campaigns
  runs = runs or config.get().runs
  os.makedirs(root, exist_ok=True)
  sections = []
  all_corpora = set()
  timeline_cells = []  # (mtime, value, label) of cells with an iterations.tsv, for the timeline panel
  for spec_dir in glob.glob(os.path.join(root, "*/")):
      name = os.path.basename(spec_dir.rstrip("/"))
      rows, whens, corpora, cells, counts = [], [], set(), {}, {}
      for corpus_dir in sorted(glob.glob(os.path.join(spec_dir, "*/"))):
          corpus = os.path.basename(corpus_dir.rstrip("/"))
          if corpus.startswith("diff-"):
              continue
          for variant_dir in sorted(glob.glob(os.path.join(corpus_dir, "*/"))):
              variant = os.path.basename(variant_dir.rstrip("/"))
              for cell in sorted(glob.glob(os.path.join(variant_dir, "*"))):
                  if os.path.isdir(cell) and os.path.basename(cell).isdigit():
                      ver = specs.of_cell(cell)
                      counts[ver] = counts.get(ver, 0) + 1
                      if os.path.exists(os.path.join(cell, "iterations.tsv")):
                          timeline_cells.append((os.path.getmtime(os.path.join(cell, "iterations.tsv")), os.path.relpath(cell, root) + "/",
                                                 f"{name} · {corpus} · {variant} #{os.path.basename(cell)}"))
                      row = cell_row(name, corpus, variant, cell)
                      if row:
                          rows.append(row[0]); whens.append(row[1]); corpora.add(row[2])
                          if row[3]:
                              cells.setdefault(corpus, {}).setdefault(row[3][0], []).append(row[3])
      diffs = sorted(glob.glob(os.path.join(spec_dir, "diff-*", "*.html")))
      prog = progress(spec_dir)
      if not rows and not diffs and not prog:
          continue
      diff_html = ("<p>Differential flame graphs (a → b): " + " · ".join(link(d, os.path.basename(os.path.dirname(d)).removeprefix("diff-"))
                                                                 for d in diffs) + "</p>") if diffs else ""
      all_corpora |= corpora
      last = max(whens) if whens else os.path.getmtime(spec_dir)
      span = f"{stamp(min(whens))} – {stamp(last)}" if whens else stamp(last)
      has_notes = os.path.exists(os.path.join(spec_dir, "NOTES.md"))
      sections.append((last, f"""<section data-last="{last:.0f}" data-notes="{1 if has_notes else 0}"><h2>{esc(name)} <span class="when">{span}</span>{progress_badge(prog, name)}</h2>{notes(os.path.join(spec_dir, "NOTES.md"))}{diff_html}{spec_history(spec_dir, counts)}{summary(name, cells)}
  <table><tr><th>corpus</th><th>variant</th><th>ms/op</th><th>cycles/op (xctrace)</th><th>instructions/op</th><th>flags</th><th>finished</th><th>flame graphs</th></tr>{''.join(rows)}</table></section>"""))
  for run in glob.glob(os.path.join(runs, "*/")) if runs else []:
      sec = run_section(run)
      if sec:
          sections.append(sec)
          tsv = os.path.join(run, "iterations.tsv")
          if os.path.exists(tsv):
              timeline_cells.append((os.path.getmtime(tsv), os.path.relpath(run, root).rstrip("/") + "/",
                                     f"run · {os.path.basename(run.rstrip('/'))}"))
  sections = [h for _, h in sorted(sections, key=lambda x: -x[0])]
  options = "".join(f'<option value="{esc(v)}">{esc(l)}</option>' for _, v, l in sorted(timeline_cells, reverse=True))
  chips = "".join(f'<button class="chip" data-corpus="{esc(c)}">{esc(c)}</button>' for c in sorted(all_corpora))

  page = f"""<!doctype html><meta charset="utf-8"><title>Campaigns and runs</title>
  <style>:root{{--bg:#f6f7f9;--fg:#1d232b;--muted:#5d6875;--line:#dde2e8;--link:#2f6fb2;--panel:#fff}}
  @media (prefers-color-scheme: dark){{:root{{--bg:#14181d;--fg:#e3e8ee;--muted:#94a0ad;--line:#2c333c;--link:#6ea8e6;--panel:#1b2027;color-scheme:dark}}}}
  body{{background:var(--bg);color:var(--fg);font:13px/1.5 -apple-system,system-ui,sans-serif;margin:20px}} a{{color:var(--link)}}
  section{{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:12px 16px;margin:0 0 16px}}
  table{{border-collapse:collapse}} td,th{{border:1px solid var(--line);padding:4px 8px;text-align:left;vertical-align:top}}
  .pending{{color:var(--muted)}} .prog{{font-size:12px;font-weight:normal;border-radius:999px;padding:1px 8px;margin-left:6px}} .prog.partial{{background:#fdf0d5;color:#7a5200}} .prog.done{{background:#e3f1e7;color:#22663a}} code{{font-size:11px}}
  .notes{{border-left:3px solid var(--link);padding:2px 12px;margin:8px 0 12px}} .notes h3{{margin:6px 0}}
  .when{{color:var(--muted);font-weight:normal;font-size:12px;white-space:nowrap}}
  .bar{{position:sticky;top:0;background:var(--bg);padding:8px 0;z-index:1;display:flex;flex-wrap:wrap;gap:6px;align-items:center;border-bottom:1px solid var(--line);margin-bottom:12px}}
  .bar h1{{font-size:16px;margin:0}}
  .chip{{border:1px solid var(--line);background:var(--panel);color:var(--fg);border-radius:14px;padding:3px 10px;font:inherit;cursor:pointer}}
  .chip.on{{background:var(--link);color:var(--bg);border-color:var(--link)}} .sep{{width:1px;height:18px;background:var(--line);margin:0 4px}}
  #q{{border:1px solid var(--line);background:var(--panel);color:var(--fg);border-radius:6px;padding:4px 8px;font:inherit;min-width:200px}}
  .hidden{{display:none}} .status{{font-size:12px;font-weight:normal;border-radius:999px;padding:1px 8px;margin-left:6px}}
  .status.running{{background:#fdf0d5;color:#7a5200}} .status.finished{{background:#e3f1e7;color:#22663a}} .status.failed,.status.interrupted{{background:#fbe3e3;color:#9b1c1c}}
  section.run h2{{font-size:15px}} .mixed{{color:#a05a00;font-size:11px}} .specs ul{{margin:2px 0 8px;padding-left:20px}}
  #tl{{margin:0 0 16px}} #tl h2{{font-size:14px;margin:0 0 6px}} #tl select{{font:inherit;max-width:100%}} #tl .k{{color:var(--muted);font-size:12px}}
  {timeline.CSS}</style>

  <header class="bar"><h1>Campaigns and runs</h1><span class="sep"></span><span>corpus:</span>{chips}<span class="sep"></span>
  <button class="chip" data-kind="profiled">profiled</button><button class="chip" data-kind="timing">timing only</button>
  <button class="chip" data-kind="notes">with notes</button><span class="sep"></span>
  <button class="chip" data-age="86400">last 24 h</button><button class="chip" data-age="10800">last 3 h</button>
  <input id="q" placeholder="filter: name, flags, notes…"></header>
  <p>Newest first. bench: benchmark threads · reverse: by leaf · threads: all threads · classify: all threads by category ·
  bench-/reverse-classify: benchmark threads with --classify. Grey links are not rendered yet; reload after
  <code>perflab regraph</code> finishes.</p>
  <section id="tl"><h2>Fork timeline</h2>
  <div><select id="tl-cell">{options}</select> <label class="k"><input type="checkbox" id="tl-follow" checked> follow the running fork</label>
  <span class="k" id="tl-status"></span></div>
  <div class="tl-legend" id="tl-legend"></div><svg class="timeline" id="tl-chart"></svg>
  <p class="k">Iterations appear as they finish; counter lanes once the fork has finished (xctrace export). Wheel to zoom, drag to pan, double-click to reset.</p></section>
  <div class="tl-tip" id="tl-tip"></div>
  <div id="campaigns">{notes(os.path.join(root, "FINDINGS.md"))}
  {''.join(sections)}</div>
  <script>{timeline.script()}</script>
  <script>
  const chips = [...document.querySelectorAll('.chip')];
  chips.forEach(c => c.onclick = () => {{ c.classList.toggle('on'); apply(); }});
  document.getElementById('q').oninput = apply;
  function on(attr) {{ return chips.filter(c => c.classList.contains('on') && c.dataset[attr]).map(c => c.dataset[attr]); }}
  function apply() {{
    const corpora = on('corpus'), kinds = on('kind'), ages = on('age').map(Number);
    const q = document.getElementById('q').value.toLowerCase(), now = Date.now() / 1000;
    for (const sec of document.querySelectorAll('section')) {{
      let visible = 0;
      for (const tr of sec.querySelectorAll('tr[data-corpus]')) {{
        let ok = !corpora.length || corpora.includes(tr.dataset.corpus);
        if (kinds.includes('profiled') && !kinds.includes('timing')) ok = ok && tr.dataset.profiled === '1';
        if (kinds.includes('timing') && !kinds.includes('profiled')) ok = ok && tr.dataset.profiled === '0';
        tr.classList.toggle('hidden', !ok); if (ok) visible++;
      }}
      let show = visible > 0 || !sec.querySelector('tr[data-corpus]');
      if (kinds.includes('notes')) show = show && sec.dataset.notes === '1';
      if (ages.length) show = show && now - Number(sec.dataset.last) < Math.max(...ages);
      if (q) show = show && sec.textContent.toLowerCase().includes(q);
      sec.classList.toggle('hidden', !show);
    }}
  }}
  // live: the timeline follows the running fork (running.json, written by `perflab ab`) and polls its files; the
  // campaign tables are refetched from this page, which `perflab ab` rebuilds around every cell
  const tl = BenchTimeline.mount(document.getElementById('tl-chart'), document.getElementById('tl-legend'), document.getElementById('tl-tip'));
  const sel = document.getElementById('tl-cell'), follow = document.getElementById('tl-follow'), status = document.getElementById('tl-status');
  let shown = null, running = null;
  sel.onchange = () => {{ follow.checked = false; tick(); }};
  async function tick() {{
    try {{ const r = await fetch('running.json', {{cache: 'no-store'}}); running = r.ok ? await r.json() : null; }} catch (e) {{ running = null; }}
    if (follow.checked && running) {{
      const v = running.cell.replace(/\\/?$/, '/');
      if (![...sel.options].some(o => o.value === v)) sel.add(new Option('running: ' + running.cell, v), 0);
      sel.value = v;
    }}
    if (!sel.value) return;
    if (sel.value !== shown) {{ tl.reset(); shown = sel.value; }}
    tl.set(await BenchTimeline.fetchCell(sel.value));
    status.textContent = running && running.cell.replace(/\\/?$/, '/') === sel.value
      ? `running since ${{new Date(running.started * 1000).toLocaleTimeString()}}` : (running ? `running: ${{running.cell}}` : 'nothing running');
  }}
  async function refreshTables() {{
    try {{
      const r = await fetch(location.pathname.endsWith('/') ? 'index.html' : location.pathname, {{cache: 'no-store'}});
      if (!r.ok) return;
      const doc = new DOMParser().parseFromString(await r.text(), 'text/html');
      document.getElementById('campaigns').innerHTML = doc.getElementById('campaigns').innerHTML;
      const keep = sel.value;
      sel.innerHTML = doc.getElementById('tl-cell').innerHTML;
      if (keep && ![...sel.options].some(o => o.value === keep)) sel.add(new Option(keep, keep), 0);
      sel.value = keep;
      apply();
    }} catch (e) {{}}
  }}
  tick(); setInterval(tick, 5000); setInterval(refreshTables, 10000);
  </script>"""
  out = os.path.join(root, "index.html")
  open(out, "w").write(page)
  return out


def main(argv):
    print(build(os.path.abspath(argv[0]) if argv else config.get().campaigns, os.path.abspath(argv[1]) if len(argv) > 1 else None))
    return 0
