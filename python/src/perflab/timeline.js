// A benchmark fork's timeline: its iterations (coloured by variant when variants alternate within the fork) and, on the
// same wall-clock axis, what the machine did meanwhile. Reads a cell's files as written by the fork and `perflab ab`:
//   iterations.tsv  every iteration as it finishes: index, kind, variant, start_ms, end_ms, score, ops, gc_ms, pid, unit, alloc_bytes;
//                   all forks of a run append to it; kind "startup" (JVM start to the first iteration) and "exit"
//                   (the last iteration to JVM exit) give each fork's lifetime
//   timeline.tsv    per 50 ms: cycles and instructions of the benchmark thread, JIT, GC, other threads of the fork and
//                   other processes (from xctrace, so only once the fork has finished)
//   gc.log          -Xlog:gc with wall-clock `time` decorations: pauses (a run's forks' logs concatenated)
//   load.tsv        the load gate's 5 s samples of other processes' CPU, in cores
//   profile.txt     the run's profile (e.g. xctrace:ipc), to name the gaps a profiler leaves between iterations
//   jvm-events.tsv  the JDK's events in an async run's .jfr (jvmevents.py): kind (vmop, c1, c2, deopt), start_ms, end_ms, what
// Used by timeline.py (a page per cell) and index.py (a live panel in index.html).
const BenchTimeline = (() => {
  const NS = 'http://www.w3.org/2000/svg';
  const BIN_MS = 50;

  function tsv(text) {
    if (!text) return [];
    const lines = text.split('\n').filter(l => l.trim());
    if (!lines.length) return [];
    const head = lines[0].split('\t');
    return lines.slice(1).map(l => Object.fromEntries(l.split('\t').map((v, i) => [head[i], v])));
  }

  function parse(f) {
    const iters = tsv(f.iterations).map(r => ({i: +r.index, kind: r.kind, variant: r.variant, s: +r.start_ms, e: +r.end_ms,
      score: +r.score, gc: r.gc_ms === '' || r.gc_ms == null ? null : +r.gc_ms, pid: r.pid || '', unit: r.unit || 'ms/op'}));
    // forks in the order they ran, numbered from 1
    const pids = [...new Set(iters.slice().sort((a, b) => a.s - b.s).map(i => i.pid))];
    for (const it of iters) it.fork = pids.indexOf(it.pid) + 1;
    const series = tsv(f.timeline).map(b => ({t: +b.bin_ms, bench_c: +b.bench_cycles, bench_i: +b.bench_inst, jit_c: +b.jit_cycles,
      gc_c: +b.gc_cycles, other_c: +b.other_cycles, processes_c: +b.processes_cycles}));
    const pauses = [];
    for (const line of (f.gc || '').split('\n')) {
      const m = line.match(/^\[([^\]]+)\]\[[^\]]+\].*?(Pause[^(]*(?:\([^)]*\))*).*?([\d.]+)ms\s*$/);
      if (!m) continue;
      const end = Date.parse(m[1].replace(/([+-]\d\d)(\d\d)$/, '$1:$2'));
      if (!isNaN(end)) pauses.push({s: end - +m[3], e: end, what: m[2].trim()});
    }
    const load = (f.load || '').split('\n').map(l => l.split('\t')).filter(p => p.length >= 2 && p[0])
      .map(p => ({t: +p[0] * 1000, cores: +p[1], top: p[2] || ''}));
    const jvm = tsv(f.jvm).map(r => ({kind: r.kind, s: +r.start_ms, e: +r.end_ms, what: r.what}));
    return {iters, series, pauses, load, jvm, profile: (f.profile || '').trim()};
  }

  async function fetchCell(base) {
    const get = async n => { try { const r = await fetch(base + n, {cache: 'no-store'}); return r.ok ? await r.text() : ''; } catch (e) { return ''; } };
    const [iterations, timeline, gc, load, profile, jvm] = await Promise.all(
      ['iterations.tsv', 'timeline.tsv', 'gc.log', 'load.tsv', 'profile.txt', 'jvm-events.tsv'].map(get));
    return parse({iterations, timeline, gc, load, profile, jvm});
  }

  function mount(svg, legend, tip) {
    let D = {iters: [], series: [], pauses: [], load: [], jvm: [], profile: ''}, t0 = 0, t1 = 1, x0 = 0, x1 = 1, zoomed = false;
    let L = 150;
    const R = 16;
    const counterRows = [
      {name: 'iterations', h: 46},
      {name: 'benchmark thread', h: 80, key: 'bench_c', unit: 'G cycles/s'},
      {name: 'IPC (benchmark)', h: 56, ipc: true},
      {name: 'GC threads', h: 70, key: 'gc_c', unit: 'G cycles/s', pauses: true},
      {name: 'JIT threads', h: 56, key: 'jit_c', unit: 'G cycles/s'},
      {name: 'other in fork', h: 46, key: 'other_c', unit: 'G cycles/s'},
      {name: 'other processes', h: 86, key: 'processes_c', unit: 'G cycles/s', load: true},
    ];
    // without counters (no xctrace): iterations and GC pauses only, plus the load gate's samples when there are any
    const plainRows = [{name: 'iterations', h: 46}, {name: 'GC pauses', h: 34, pauses: true}];
    // from the JDK's events in an async-profiler recording: one track per kind
    const JVM = {vmop: {name: 'VM op', color: 'var(--v3)'}, c1: {name: 'C1', color: 'var(--v5)'}, c2: {name: 'C2', color: 'var(--v1)'},
                 deopt: {name: 'deopt', color: 'var(--fg)'}};
    const jvmRows = [{name: 'VM operations', h: 26, jvm: ['vmop']}, {name: 'JIT compiles', h: 50, jvm: ['c1', 'c2', 'deopt']}];
    let rows = counterRows, height = 0;
    const layout = () => {
      rows = D.series.length ? counterRows : plainRows.concat(D.load.length ? [{name: 'other processes', h: 60, load: true}] : []);
      if (D.jvm.length) rows = rows.concat(jvmRows);
      height = rows.reduce((a, r) => a + r.h + 8, 8) + 24;
    };
    let variants = [];
    const color = v => v ? `var(--v${variants.indexOf(v) % 6})` : 'var(--v0)';
    const unitOf = u => (u || '').replace('us/', 'µs/');
    const fmt = x => Math.abs(x) >= 1000 ? Math.round(x).toLocaleString('en-US') : x.toPrecision(4);
    const xctrace = () => D.profile.startsWith('xctrace');
    // time between a fork's iterations that is in none of them: the profiler attaching (xctrace records only measurement)
    function gaps() {
      const out = [];
      const byFork = {};
      for (const it of D.iters) (byFork[it.fork] = byFork[it.fork] || []).push(it);
      for (const its of Object.values(byFork)) {
        its.sort((a, b) => a.s - b.s);
        for (let i = 1; i < its.length; i++) {
          const g = its[i].s - its[i - 1].e;
          if (g > 250 && g > 0.2 * (its[i].e - its[i].s)) out.push({s: its[i - 1].e, e: its[i].s,
            what: xctrace() && its[i - 1].kind === 'warmup' && its[i].kind === 'measure' ? 'xctrace attaching' : 'between iterations'});
        }
      }
      return out;
    }
    function defs() {
      const d = el('defs', {});
      const p = el('pattern', {id: 'tl-hatch', width: 6, height: 6, patternUnits: 'userSpaceOnUse', patternTransform: 'rotate(45)'}, d);
      el('rect', {width: 6, height: 6, fill: 'var(--life)', opacity: 0.35}, p);
      el('line', {x1: 0, y1: 0, x2: 0, y2: 6, stroke: 'var(--life)', 'stroke-width': 3}, p);
    }
    function el(tag, attrs, parent) { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); (parent || svg).appendChild(e); return e; }

    function draw() {
      svg.innerHTML = '';
      const W = svg.clientWidth || 900;
      L = W < 600 ? 106 : 150;
      const X = t => L + (t - x0) / (x1 - x0) * (W - L - R);
      defs();
      if (!D.iters.length && !D.series.length) {
        svg.setAttribute('height', 40);
        el('text', {x: 12, y: 24, class: 'lab'}).textContent = 'No iterations yet.';
        return;
      }
      layout();
      svg.setAttribute('height', height);
      let y = 8;
      const ticks = W < 600 ? 6 : 12;
      const span = x1 - x0, step = [100, 200, 500, 1000, 2000, 5000, 10000, 20000, 60000].find(s => span / s < ticks) || 120000;
      for (let t = Math.ceil((x0 - t0) / step) * step; t0 + t <= x1; t += step) {
        el('line', {x1: X(t0 + t), x2: X(t0 + t), y1: 0, y2: height - 22, class: 'grid'});
        el('text', {x: X(t0 + t) + 2, y: height - 8, class: 'lab'}).textContent = (t / 1000).toFixed(step < 1000 ? 1 : 0) + ' s';
      }
      for (const r of rows) {
        el('text', {x: 6, y: y + 14}).textContent = r.name;
        const u = r.name === 'iterations' ? unitOf((D.iters.find(i => i.kind === 'measure' || i.kind === 'warmup') || {}).unit) : r.unit;
        if (u) el('text', {x: 6, y: y + 28, class: 'lab'}).textContent = u;
        el('line', {x1: L, x2: W - R, y1: y + r.h, y2: y + r.h, class: 'grid'});
        if (r.name === 'iterations') {
          const forks = Math.max(0, ...D.iters.map(i => i.fork));
          const label = (a, b, texts, cls) => {
            // the longest text that fits the bar
            const t = texts.find(t => t.length * 6.2 + 8 < b - a);
            if (t) el('text', {x: a + 4, y: y + r.h / 2 + 4, class: cls || ''}).textContent = t;
          };
          for (const g of gaps()) {
            if (g.e < x0 || g.s > x1) continue;
            const a = Math.max(X(g.s), L), b = Math.min(X(g.e), W - R);
            const rect = el('rect', {x: a + 1, y: y + 10, width: Math.max(1, b - a - 2), height: r.h - 20, rx: 2, fill: 'none',
              stroke: 'var(--life)', 'stroke-dasharray': '3 3'});
            rect.dataset.tip = `${g.what}: ${((g.e - g.s) / 1000).toFixed(2)} s, in no iteration`;
            label(a, b, [g.what, xctrace() ? 'attach' : 'gap'], 'lab');
          }
          for (const it of D.iters) {
            if (it.e < x0 || it.s > x1) continue;
            const a = Math.max(X(it.s), L), b = Math.min(X(it.e), W - R);
            const life = it.kind === 'startup' || it.kind === 'exit';
            const fork = forks > 1 ? `fork ${it.fork}: ` : '';
            const secs = ((it.e - it.s) / 1000).toFixed(2) + ' s';
            const rect = el('rect', {x: a, y: y + (life ? 12 : 6), width: Math.max(1, b - a - 1), height: life ? r.h - 24 : r.h - 12, rx: 2,
              fill: life ? 'url(#tl-hatch)' : it.kind === 'warmup' ? 'var(--grey)' : color(it.variant)});
            const exitWhat = xctrace() ? 'last iteration to JVM exit, and xctrace saving its trace' : 'last iteration to JVM exit';
            rect.dataset.tip = life
              ? `${fork}${it.kind === 'startup' ? 'JVM start to first iteration (JVM boot, benchmark setup)' : exitWhat}: ${secs}`
              : `${fork}#${it.i} ${it.kind} ${it.variant || ''}: ${fmt(it.score)} ${unitOf(it.unit)}` + (it.gc != null ? `, GC pauses ${it.gc} ms` : '');
            if (life) label(a, b, it.kind === 'startup' ? ['JVM start ' + secs, 'start']
                                                        : [(xctrace() ? 'JVM exit + xctrace saving trace ' : 'JVM exit ') + secs, 'JVM exit', 'exit'], 'lab halo');
            else label(a, b, [`${fmt(it.score)} ${unitOf(it.unit)}`, fmt(it.score)], it.kind === 'warmup' ? '' : 'on');
          }
          // each fork's start, labelled when there are several
          if (forks > 1) for (let f = 1; f <= forks; f++) {
            const s = Math.min(...D.iters.filter(i => i.fork === f).map(i => i.s));
            if (s < x0 || s > x1) continue;
            el('line', {x1: X(s), x2: X(s), y1: 0, y2: height - 22, stroke: 'var(--fg)', 'stroke-width': 1, opacity: 0.35});
            el('text', {x: X(s) + 2, y: y + r.h + 1, class: 'lab'}).textContent = `fork ${f}`;
          }
        } else if (r.jvm) {
          const th = (r.h - 4) / r.jvm.length;
          r.jvm.forEach((kind, k) => {
            const ty = y + 2 + k * th;
            // the track's name beside it, or inside the plot when the label column is too narrow (as the counter lanes' scales)
            const sx = L < 150 ? {x: L + 3, 'text-anchor': 'start', class: 'lab halo'} : {x: L - 4, 'text-anchor': 'end', class: 'lab'};
            if (r.jvm.length > 1) el('text', {...sx, y: ty + th / 2 + 4}).textContent = JVM[kind].name;
            // bars closer than a pixel merge into one, its tip counting them: a fork compiles thousands of methods
            const groups = [];
            for (const ev of D.jvm) {
              if (ev.kind !== kind || ev.e < x0 || ev.s > x1) continue;
              const a = Math.max(X(ev.s), L), b = Math.min(X(ev.e), W - R), g = groups[groups.length - 1];
              if (g && a <= g.b + 1) { g.b = Math.max(g.b, b); g.n++; g.ms += ev.e - ev.s; }
              else groups.push({a, b, n: 1, ms: ev.e - ev.s, first: ev});
            }
            for (const g of groups) {
              const m = el('rect', {x: g.a, y: ty + 1, width: Math.max(kind === 'deopt' ? 1.5 : 2, g.b - g.a), height: th - 2,
                fill: JVM[kind].color, opacity: kind === 'deopt' ? 0.8 : 0.6});
              m.dataset.tip = g.n === 1 ? `${JVM[kind].name}: ${g.first.what}` + (kind === 'deopt' ? '' : `: ${g.ms.toFixed(1)} ms`)
                : `${g.n} × ${JVM[kind].name}` + (kind === 'deopt' ? '' : `, ${g.ms.toFixed(1)} ms in all`) + `; the first, ${g.first.what}`;
            }
          });
          if (!D.jvm.some(ev => r.jvm.includes(ev.kind) && ev.e >= x0 && ev.s <= x1))
            el('text', {x: L + 6, y: y + r.h / 2 + 4, class: 'lab'}).textContent = 'none in view (the recording covers the last fork\'s measurement)';
        } else if (!r.key && !r.ipc) {
          // pauses / load only
        } else {
          const pts = r.ipc ? D.series.map(s => ({t: s.t, v: s.bench_c ? s.bench_i / s.bench_c : null}))
                            : D.series.map(s => ({t: s.t, v: s[r.key] / (BIN_MS / 1000) / 1e9}));
          const vis = pts.filter(p => p.t >= x0 - BIN_MS && p.t <= x1 && p.v != null);
          const max = r.ipc ? Math.max(4, ...vis.map(p => p.v)) : Math.max(0.5, ...vis.map(p => p.v));
          const Y = v => y + r.h - 4 - v / max * (r.h - 10);
          // a baseline, a mid line, and the lane's own scale at both
          el('line', {x1: L, x2: W - R, y1: Y(0), y2: Y(0), class: 'axis'});
          el('line', {x1: L, x2: W - R, y1: Y(max / 2), y2: Y(max / 2), class: 'grid', 'stroke-dasharray': '2 4'});
          // on a narrow chart the scale goes inside the plot, the label column being too narrow for it
          const sx = L < 150 ? {x: L + 3, 'text-anchor': 'start', class: 'lab halo'} : {x: L - 4, 'text-anchor': 'end', class: 'lab'};
          el('text', {...sx, y: Y(max) + 8}).textContent = max.toFixed(1);
          el('text', {...sx, y: Y(max / 2) + 4}).textContent = (max / 2).toFixed(max / 2 < 1 ? 2 : 1);
          if (!vis.length) el('text', {x: L + 6, y: y + r.h / 2 + 4, class: 'lab'}).textContent = 'no samples in view';
          let d = '', prev = null;
          // a new segment after a gap (between forks, or between xctrace's recordings)
          for (const p of vis) { d += (prev == null || p.t - prev > 2 * BIN_MS ? 'M' : 'L') + X(p.t + BIN_MS / 2).toFixed(1) + ',' + Y(p.v).toFixed(1); prev = p.t; }
          if (d) el('path', {d, fill: 'none', stroke: r.ipc ? 'var(--v2)' : 'var(--v0)', 'stroke-width': 1.2});
        }
        if (r.pauses && !r.key && !D.pauses.some(p => p.e >= x0 && p.s <= x1))
          el('text', {x: L + 6, y: y + r.h / 2 + 4, class: 'lab'}).textContent = D.pauses.length ? 'none in view' : 'none';
        if (r.pauses) for (const p of D.pauses) {
          if (p.e < x0 || p.s > x1) continue;
          const m = el('rect', {x: X(p.s), y: y + 2, width: Math.max(2, X(p.e) - X(p.s)), height: r.h - 4, fill: 'var(--pause)', opacity: 0.55});
          m.dataset.tip = `${p.what}: ${(p.e - p.s).toFixed(1)} ms`;
        }
        if (r.load && D.load.length) {
          const lmax = Math.max(2, ...D.load.map(l => l.cores));
          el('text', {x: W - R - 2, y: y + 12, 'text-anchor': 'end', class: 'lab'}).textContent = `load.tsv: other processes, cores (max ${lmax.toFixed(1)})`;
          let ld = '';
          for (const l of D.load) {
            if (l.t < x0 - 5000 || l.t > x1 + 5000) continue;
            const yy = y + r.h - 4 - l.cores / lmax * (r.h - 10);
            const clamp = x => Math.min(Math.max(x, L), W - R);
            ld += (ld ? 'L' : 'M') + clamp(X(l.t - 5000)).toFixed(1) + ',' + yy.toFixed(1) + 'L' + clamp(X(l.t)).toFixed(1) + ',' + yy.toFixed(1);
          }
          if (ld) el('path', {d: ld, fill: 'none', stroke: 'var(--v1)', 'stroke-width': 1.2, 'stroke-dasharray': '4 3'});
        }
        y += r.h + 8;
      }
    }

    function set(data) {
      D = data;
      variants = [...new Set(D.iters.map(i => i.variant).filter(v => v))];
      const ts = [...D.iters.flatMap(i => [i.s, i.e]), ...D.series.map(s => s.t), ...D.series.map(s => s.t + BIN_MS)];
      const n0 = ts.length ? Math.min(...ts) : 0, n1 = ts.length ? Math.max(...ts) : 1;
      // keep a zoomed view where it is as data arrives; otherwise follow the whole range
      if (!zoomed) { x0 = n0; x1 = Math.max(n1, n0 + 1); }
      t0 = n0; t1 = Math.max(n1, n0 + 1);
      const sw = (bg, text, extra) => `<span><i style="background:${bg}${extra || ''}"></i>${text}</span>`;
      if (legend) legend.innerHTML = sw('var(--grey)', 'warmup')
        + (variants.length ? variants.map(v => sw(color(v), v)).join('') : sw('var(--v0)', 'measurement'))
        + (D.iters.some(i => i.kind === 'startup') ? sw('repeating-linear-gradient(45deg,var(--life) 0 2px,transparent 2px 4px)', 'JVM start / exit', ';outline:1px solid var(--life)') : '')
        + (gaps().length ? sw('transparent', xctrace() ? 'xctrace attaching' : 'between iterations', ';outline:1px dashed var(--life)') : '')
        + (D.pauses.length ? sw('var(--pause)', 'GC pause') : '')
        + Object.keys(JVM).filter(k => D.jvm.some(ev => ev.kind === k)).map(k => sw(JVM[k].color, k === 'vmop' ? 'VM operation at a safepoint' : JVM[k].name)).join('');
      draw();
    }

    svg.addEventListener('wheel', e => { e.preventDefault(); const W = svg.clientWidth, f = Math.exp(e.deltaY * 0.002);
      const at = x0 + (e.offsetX - L) / (W - L - R) * (x1 - x0); x0 = Math.max(t0, at - (at - x0) * f); x1 = Math.min(t1, at + (x1 - at) * f); zoomed = true; draw(); }, {passive: false});
    let drag = null;
    svg.addEventListener('pointerdown', e => { drag = {x: e.clientX, x0, x1}; svg.setPointerCapture(e.pointerId); });
    svg.addEventListener('pointermove', e => {
      const t = e.target.dataset && e.target.dataset.tip;
      if (tip && t && !drag) { tip.textContent = t; tip.style.display = 'block'; tip.style.left = (e.clientX + 12) + 'px'; tip.style.top = (e.clientY + 12) + 'px'; }
      else if (tip && !drag) tip.style.display = 'none';
      if (!drag) return;
      const W = svg.clientWidth, dt = (e.clientX - drag.x) / (W - L - R) * (drag.x1 - drag.x0), w = drag.x1 - drag.x0;
      x0 = Math.min(Math.max(t0, drag.x0 - dt), t1 - w); x1 = x0 + w; zoomed = true; draw();
    });
    svg.addEventListener('pointerup', () => drag = null);
    svg.addEventListener('dblclick', () => { zoomed = false; x0 = t0; x1 = t1; draw(); });
    window.addEventListener('resize', draw);
    return {set, reset() { zoomed = false; }};
  }

  return {parse, fetchCell, mount};
})();
