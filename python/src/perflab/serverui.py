"""The pages of `perflab server`: the queue (/) and storage (/admin), in the look of the index (ui.py). Each page polls
the server's JSON API, and carries the server's token for its POSTs: it is served only to 127.0.0.1, with our own Host.
"""
import html, json, os

from . import ui

CSS = """
main{max-width:1100px;margin:0 auto;padding:16px 20px 40px}
.nav{position:sticky;top:0;z-index:10}
.tabsrow{background:var(--ink)} .tabsrow .in{max-width:1100px;margin:0 auto;padding:0 20px;display:flex;align-items:center;gap:8px}
nav.tabs{display:flex;gap:2px;overflow-x:auto;scrollbar-width:none;flex:1} nav.tabs::-webkit-scrollbar{display:none}
nav.tabs a{color:var(--ink-muted);padding:9px 12px 7px;border-bottom:2px solid transparent;font-weight:500;white-space:nowrap}
nav.tabs a.on{color:#fff;border-bottom-color:var(--brand)} nav.tabs a:hover{color:#fff;text-decoration:none}
nav.tabs .n{font-size:11px;color:var(--ink-muted);margin-left:5px;font-weight:normal}
nav.tabs .sep{border-left:1px solid var(--ink-line);margin:8px 6px}
h2.sec{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:18px 0 8px;font-weight:600}
h2.sec .k{text-transform:none;letter-spacing:0;font-weight:normal}
.badge.queued,.badge.cancelled{background:var(--line2);color:var(--muted)} .badge.paused{background:var(--link-bg);color:var(--link)}
.badge.pinned{background:var(--link-bg);color:var(--link)} .badge.active{background:var(--warn-bg);color:var(--warn)}
.job{border-top:1px solid var(--line2);padding:9px 0} .job:first-child{border-top:0;padding-top:2px}
.jh{display:flex;flex-wrap:wrap;align-items:center;gap:4px 10px} .jh .id{font-weight:700;font-variant-numeric:tabular-nums}
.jh .btns{margin-left:auto}
button.btn{font:inherit;font-size:12px;line-height:18px;cursor:pointer} button.btn:disabled{color:var(--muted);cursor:default;background:var(--panel)}
button.btn.bad{color:var(--bad)} button.btn.bad:hover{background:var(--bad-bg)} button.btn.go{background:var(--link);border-color:var(--link);color:var(--panel)}
.argv{display:block;margin:4px 0 0;overflow-wrap:anywhere;color:var(--fg)}
.argv .cwd{color:var(--muted)}
pre.tail{margin:8px 0 0;max-height:320px;overflow:auto;background:var(--bg);border:1px solid var(--line2);border-radius:6px;padding:6px 8px;
  font:11.5px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace;white-space:pre-wrap;overflow-wrap:anywhere}
details.more>summary{cursor:pointer;color:var(--link);font-size:12px;margin-top:4px;list-style:none} details.more>summary::-webkit-details-marker{display:none}
.empty{color:var(--muted);margin:2px 0}
#toast{position:fixed;left:50%;bottom:20px;transform:translateX(-50%);background:var(--bad-bg);color:var(--bad);border:1px solid var(--line);
  border-radius:8px;padding:6px 14px;box-shadow:0 6px 24px rgba(0,0,0,.18);z-index:50;max-width:calc(100vw - 32px)}
#toast[hidden]{display:none}
.tiles{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 4px} .tile{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:8px 14px;min-width:120px;box-shadow:var(--shadow)}
.tile .v{font-size:20px;font-weight:600;font-variant-numeric:tabular-nums} .tile .l{color:var(--muted);font-size:12px}
.bulk{display:flex;flex-wrap:wrap;gap:8px;align-items:center} .bulk input{width:52px;font:inherit;padding:1px 4px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg)}
#pending{border-color:var(--link)} #pending[hidden]{display:none} #pending ul{margin:4px 0;padding-left:18px;max-height:180px;overflow:auto;font-size:12px}
#pending li{overflow-wrap:anywhere}
table.t td.name{overflow-wrap:anywhere;min-width:140px} table.t td.acts{white-space:nowrap} table.t td .btns{flex-wrap:nowrap}
table.t tr.on td{background:var(--link-bg)}
@media (max-width:700px){main{padding:12px 12px 24px} .tabsrow .in{padding:0 12px} .jh .btns{margin-left:0;width:100%} .argv .cwd{display:none} pre.tail{max-height:240px}
  .tile{min-width:0;flex:1 1 40%} .tile .v{font-size:17px}}
"""

COMMON_JS = r"""
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'})[c]);
const bytes = b => !b ? '0' : b >= 1e9 ? (b / 1e9).toFixed(b >= 1e10 ? 0 : 1) + ' GB' : b >= 1e6 ? (b / 1e6).toFixed(b >= 1e7 ? 0 : 1) + ' MB'
  : b >= 1e3 ? (b / 1e3).toFixed(0) + ' KB' : b + ' B';
const ago = t => { if (!t) return ''; const d = Date.now() / 1000 - t;
  return d < 90 ? Math.round(d) + 's ago' : d < 5400 ? Math.round(d / 60) + 'm ago' : d < 172800 ? (d / 3600).toFixed(1) + 'h ago'
    : new Date(t * 1000).toISOString().slice(0, 10); };
const dur = s => { s = Math.max(0, Math.round(s)); return s < 60 ? s + 's' : s < 3600 ? Math.floor(s / 60) + 'm' + String(s % 60).padStart(2, '0') + 's'
  : Math.floor(s / 3600) + 'h' + String(Math.floor(s % 3600 / 60)).padStart(2, '0') + 'm'; };
function toast(msg) { const t = document.getElementById('toast'); t.textContent = msg; t.hidden = false; clearTimeout(toast.t); toast.t = setTimeout(() => t.hidden = true, 5000); }
async function post(path, body) {
  try {
    const r = await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Perflab-Token': TOKEN}, body: JSON.stringify(body || {})});
    const j = await r.json();
    if (!r.ok) { toast(j.error || r.statusText); return null; }
    return j;
  } catch (e) { toast('the server did not answer: ' + e); return null; }
}
"""

QUEUE_JS = r"""
let projects = {}, jobs = [];
const open = new Set();
const proj = id => projects[id] ? `<a href="${esc(projects[id].index)}" title="${esc(projects[id].root)}">${esc(projects[id].name)}</a>` : esc(id);
function label(j) {
  if (j.state === 'running' && j.cancel_requested) return ['running', 'cancelling'];
  if (j.state === 'paused' && j.cancel_requested) return ['paused', 'cancelling'];
  if (j.state === 'running' && j.control === 'pause') return ['running', 'pausing at the next cell'];
  if (j.state === 'paused' && j.control !== 'pause') return ['paused', 'resuming'];
  return [j.state, j.state];
}
function buttons(j) {
  const b = (op, text, cls, title, body) => `<button class="btn ${cls || ''}" data-op="${op}" data-id="${j.id}" ${body ? `data-body='${esc(JSON.stringify(body))}'` : ''} title="${esc(title || '')}">${text}</button>`;
  const t = `<a class="btn" href="/api/jobs/${j.id}/transcript" target="_blank" rel="noopener" title="the whole transcript, as text">transcript</a>`;
  if (j.state === 'running' || j.state === 'paused') {
    const pausing = j.control === 'pause';
    return (pausing ? b('resume', 'Resume', 'go', 'clear the pause; a paused job carries on') : b('pause', 'Pause', '', 'pause at the next cell boundary'))
      + (j.cancel_requested ? '' : b('cancel', 'Cancel', 'bad', 'stop it: at the next cell, else SIGTERM after a grace period')) + t;
  }
  if (j.state === 'queued')
    return b('move', '↑', '', 'run sooner', {by: -1}) + b('move', '↓', '', 'run later', {by: 1})
      + b('priority', 'priority ' + (j.priority > 0 ? '+' : '') + j.priority, '', 'raise its priority by one', {priority: j.priority + 1})
      + b('cancel', 'Cancel', 'bad', 'take it off the queue');
  return t;
}
function jobHtml(j, tail) {
  const [cls, text] = label(j);
  const when = j.state === 'queued' ? `#${j.position} · submitted ${ago(j.created)}`
    : j.ended ? `${ago(j.ended)} · took ${dur(j.ended - (j.started || j.created))}` + (j.rc !== null && j.rc !== 0 ? ` · exit ${j.rc}` : '')
    : `started ${ago(j.started)} · ${dur(Date.now() / 1000 - j.started)}`;
  const body = tail ? `<pre class="tail" id="tail-${j.id}">…</pre>` : j.state === 'queued' ? ''
    : `<details class="more" data-id="${j.id}"${open.has(j.id) ? ' open' : ''}><summary>transcript ▾</summary><pre class="tail" id="tail-${j.id}">…</pre></details>`;
  return `<div class="job" id="job-${j.id}"><div class="jh"><span class="id">#${j.id}</span><span class="badge ${cls}">${esc(text)}</span>${proj(j.project)}`
    + `<span class="when">${when}</span><span class="btns">${buttons(j)}</span></div>`
    + `<code class="argv">perflab ${esc(j.argv.join(' '))}<span class="cwd"> · in ${esc(j.cwd.startsWith(HOME + '/') ? '~' + j.cwd.slice(HOME.length) : j.cwd)}</span></code>`
    + (j.note ? `<p class="k">${esc(j.note)}</p>` : '') + body + `</div>`;
}
async function fillTail(id, n) {
  const pre = document.getElementById('tail-' + id);
  if (!pre) return;
  try {
    const text = await (await fetch(`/api/jobs/${id}/transcript?tail=${n}`)).text();
    const atEnd = pre.scrollHeight - pre.scrollTop - pre.clientHeight < 24;
    pre.textContent = text || '(nothing yet)';
    if (atEnd) pre.scrollTop = pre.scrollHeight;
  } catch (e) {}
}
function section(id, list, tail, empty) {
  const el = document.getElementById(id);
  const scroll = {};
  el.querySelectorAll('pre.tail').forEach(p => scroll[p.id] = [p.scrollTop, p.textContent]);
  el.innerHTML = list.length ? list.map(j => jobHtml(j, tail)).join('') : `<p class="empty">${empty}</p>`;
  el.querySelectorAll('pre.tail').forEach(p => { if (scroll[p.id]) { p.textContent = scroll[p.id][1]; p.scrollTop = scroll[p.id][0]; } });
}
async function refresh() {
  try {
    const [js, ps] = await Promise.all([fetch('/api/jobs').then(r => r.json()), fetch('/api/projects').then(r => r.json())]);
    jobs = js; projects = Object.fromEntries(ps.map(p => [p.id, p]));
  } catch (e) { document.getElementById('conn').textContent = 'the server is not answering'; return; }
  document.getElementById('conn').textContent = '';
  const active = jobs.filter(j => j.state === 'running' || j.state === 'paused');
  const queued = jobs.filter(j => j.state === 'queued');
  const done = jobs.filter(j => ['done', 'failed', 'cancelled'].includes(j.state));
  section('active', active, true, 'Nothing is running.');
  section('queued', queued, false, 'The queue is empty. <code>perflab submit -- ab run &lt;spec&gt;</code> adds to it.');
  section('history', done, false, 'No finished jobs yet.');
  document.getElementById('n-queued').textContent = queued.length;
  document.title = (active.length ? `▶ #${active[0].id} · ` : '') + 'queue · perflab server';
  active.forEach(j => fillTail(j.id, 60));
  open.forEach(id => fillTail(id, 200));
}
document.addEventListener('click', async e => {
  const b = e.target.closest('button[data-op]');
  if (!b) return;
  if (b.dataset.op === 'cancel' && !confirm(`Cancel job #${b.dataset.id}?`)) return;
  b.disabled = true;
  await post(`/api/jobs/${b.dataset.id}/${b.dataset.op}`, b.dataset.body ? JSON.parse(b.dataset.body) : {});
  refresh();
});
document.addEventListener('toggle', e => {
  const d = e.target;
  if (!d.matches || !d.matches('details.more')) return;
  const id = +d.dataset.id;
  if (d.open) { open.add(id); fillTail(id, 200); } else open.delete(id);
}, true);
refresh();
setInterval(refresh, 3000);
"""

ADMIN_JS = r"""
let entries = [], projects = {}, pending = null;
const ACTIONS = {
  builds: 'Drop builds (snapshots, worktrees)', graphs: 'Drop rendered graphs', profiles: 'Drop profiles', delete: 'Delete'};
function describe(p) {
  const what = p.body.target ? `${ACTIONS[p.body.action].toLowerCase()} of ${p.body.target.name}` : ACTIONS[p.body.action].toLowerCase()
    + (p.body.action === 'profiles' ? ` older than ${p.body.days} days` : p.body.action === 'builds' ? ' of idle campaigns and runs' : '');
  return what.charAt(0).toUpperCase() + what.slice(1);
}
async function preview(body) {
  const r = await post('/api/storage/cleanup', {...body, dry_run: true});
  if (!r) return;
  pending = {body, result: r};
  const el = document.getElementById('pending');
  const skipped = r.skipped.length ? ` Skipped: ${r.skipped.map(s => `${esc(s.name)} (${s.why})`).join(', ')}.` : '';
  el.innerHTML = `<div class="card-h"><h2>${esc(describe(pending))}</h2></div>`
    + `<p>${r.removed.length ? `Reclaims <b>${bytes(r.reclaimed)}</b> from ${r.removed.length} path${r.removed.length === 1 ? '' : 's'}.` : 'Nothing to remove.'}${skipped}</p>`
    + (r.removed.length ? `<details><summary class="k">what it removes</summary><ul>${r.removed.slice(0, 500).map(p => `<li><code>${esc(p)}</code></li>`).join('')}</ul></details>` : '')
    + `<p class="btns">${r.removed.length ? `<button class="btn bad" id="go">Remove ${bytes(r.reclaimed)}</button>` : ''}<button class="btn" id="dismiss">Close</button></p>`;
  el.hidden = false;
  el.scrollIntoView({block: 'nearest'});
  document.getElementById('dismiss').onclick = () => { el.hidden = true; pending = null; };
  const go = document.getElementById('go');
  if (go) go.onclick = async () => {
    go.disabled = true;
    const done = await post('/api/storage/cleanup', {...pending.body, dry_run: false});
    if (done) { el.innerHTML = `<p>Removed ${bytes(done.reclaimed)} from ${done.removed.length} path${done.removed.length === 1 ? '' : 's'}.</p><p class="btns"><button class="btn" id="dismiss">Close</button></p>`;
                document.getElementById('dismiss').onclick = () => { el.hidden = true; }; }
    load();
  };
}
function row(e) {
  const t = {project: e.project, kind: e.kind, name: e.name};
  const b = (action, text, cls, title) => `<button class="btn ${cls || ''}" data-act="${action}" data-t='${esc(JSON.stringify(t))}' title="${esc(title)}"${e.active ? ' disabled' : ''}>${text}</button>`;
  const p = projects[e.project];
  const href = p ? `/p/${encodeURIComponent(e.project)}/` + e.path.slice(p.serveRoot.length + 1).split('/').map(encodeURIComponent).join('/') + '/' : '';
  return `<tr><td class="name">${href ? `<a href="${esc(href)}">${esc(e.name)}</a>` : esc(e.name)} ${e.pinned ? '<span class="badge pinned">pinned</span>' : ''}${e.active ? `<span class="badge active" title="${esc(e.activeWhy)}">active</span>` : ''}`
    + `<div class="k">${e.kind} · ${esc(p ? p.name : e.project)}</div></td>`
    + `<td class="n"><b>${bytes(e.total)}</b></td><td class="n">${bytes(e.bytes.results)}</td><td class="n">${bytes(e.bytes.profiles)}</td><td class="n">${bytes(e.bytes.builds)}</td>`
    + `<td class="when">${ago(e.newest)}</td>`
    + `<td class="acts"><span class="btns"><button class="btn" data-pin="${e.pinned ? 0 : 1}" data-t='${esc(JSON.stringify(t))}' title="a pinned campaign is skipped by the bulk actions">${e.pinned ? 'Unpin' : 'Pin'}</button>`
    + (e.bytes.builds ? b('builds', 'builds', '', 'drop its builds') : '') + (e.graphs ? b('graphs', 'graphs', '', 'drop its rendered graphs') : '')
    + (e.pinned ? '' : b('delete', 'delete', 'bad', 'delete it, results and all')) + `</span></td></tr>`;
}
async function load() {
  const st = document.getElementById('scan');
  st.textContent = 'scanning…';
  let r;
  try { r = await (await fetch('/api/storage')).json(); } catch (e) { st.textContent = 'the server is not answering'; return; }
  entries = r.entries; projects = Object.fromEntries(r.projects.map(p => [p.id, p]));
  st.textContent = `${entries.length} campaigns and runs in ${r.projects.length} project${r.projects.length === 1 ? '' : 's'}, scanned ${new Date().toLocaleTimeString()}`;
  const sum = k => entries.reduce((a, e) => a + (k ? e.bytes[k] : e.total), 0);
  document.getElementById('tiles').innerHTML = [['total', sum()], ['results', sum('results')], ['profiles', sum('profiles')], ['builds', sum('builds')],
    ['rendered graphs', entries.reduce((a, e) => a + e.graphs, 0)]].map(([l, v]) => `<div class="tile"><div class="v">${bytes(v)}</div><div class="l">${l}</div></div>`).join('');
  document.getElementById('rows').innerHTML = entries.length ? entries.map(row).join('')
    : '<tr><td colspan="7" class="k">No campaigns or runs. A project registers when it submits a job, or with <code>perflab server start</code> in it.</td></tr>';
}
document.addEventListener('click', async e => {
  const a = e.target.closest('button[data-act]');
  if (a) return preview({action: a.dataset.act, target: JSON.parse(a.dataset.t)});
  const p = e.target.closest('button[data-pin]');
  if (p) { await post('/api/storage/pin', {...JSON.parse(p.dataset.t), pinned: p.dataset.pin === '1'}); return load(); }
  const bulk = e.target.closest('button[data-bulk]');
  if (bulk) {
    const body = {action: bulk.dataset.bulk};
    if (body.action === 'profiles') body.days = +document.getElementById('days').value || 30;
    preview(body);
  }
});
document.getElementById('rescan').onclick = load;
load();
"""


def _page(server, title, tab, body, script):
    projects = server.q.projects()
    links = "".join(f'<a href="{html.escape(p["index"])}" title="{html.escape(p["root"])}">{html.escape(p["name"])}</a>' for p in projects)
    tabs = (f'<a href="/"{" class=on" if tab == "queue" else ""}>Queue<span class="n" id="n-queued"></span></a>'
            f'<a href="/admin"{" class=on" if tab == "admin" else ""}>Storage</a>' + (f'<span class="sep"></span>{links}' if links else ""))
    return f"""{ui.HEAD}<title>{html.escape(title)} · perflab server</title>
{ui.style(ui.BASE, CSS)}
{ui.masthead("server", home="/")}
<div class="nav"><div class="tabsrow"><div class="in"><nav class="tabs">{tabs}</nav></div></div></div>
<main>{body}</main><div id="toast" hidden></div>
<script>const TOKEN = {json.dumps(server.token)}, HOME = {json.dumps(os.path.expanduser("~"))};
{COMMON_JS}
{script}</script>"""


def queue_page(server):
    help_ = ui.help_popover("One job runs at a time, in queue order: higher priority first, then as submitted. <b>Pause</b> takes "
                            "effect at the next cell boundary, so no fork's work is lost; <b>Cancel</b> stops a job there too, "
                            "or with SIGTERM after a grace period. A job's results stay when it is cancelled.", right=True)
    body = (f'<h2 class="sec">Now <span class="k" id="conn"></span></h2><section class="card" id="active"></section>'
            f'<h2 class="sec">Queued {help_}</h2><section class="card" id="queued"></section>'
            f'<h2 class="sec">Finished <span class="k">newest first</span></h2><section class="card" id="history"></section>')
    return _page(server, "queue", "queue", body, QUEUE_JS)


def admin_page(server):
    help_ = ui.help_popover("Allocated bytes (a hard-linked file counts once). <b>results</b>: result.json, iterations, logs, "
                            "timelines (kept). <b>profiles</b>: recordings (.jfr, .trace) and the graphs rendered from them. "
                            "<b>builds</b>: launch-mode snapshots and worktrees, rebuildable from the commit. Each action shows "
                            "what it would remove first. A pinned campaign is skipped by the bulk actions; an active one "
                            "(running, building, or written in the last 10 minutes) is never touched.", right=True)
    body = (f'<h2 class="sec">Storage <span class="k" id="scan"></span> {help_}</h2><div class="tiles" id="tiles"></div>'
            '<h2 class="sec">Clean up</h2><section class="card"><div class="bulk">'
            '<button class="btn" data-bulk="builds" title="snapshots and worktrees of campaigns and runs that are not active">Drop builds of idle campaigns</button>'
            '<button class="btn" data-bulk="graphs" title="flame graphs and diffs; they re-render from the recordings">Drop rendered graphs</button>'
            '<span class="btns"><button class="btn" data-bulk="profiles">Drop profiles older than</button></span>'
            '<label class="k"><input id="days" type="number" min="0" value="30"> days</label>'
            '<button class="btn" id="rescan" style="margin-left:auto">Rescan</button></div></section>'
            '<section class="card" id="pending" hidden></section>'
            '<h2 class="sec">By campaign and run <span class="k">largest first</span></h2>'
            '<section class="card"><div class="scroll"><table class="t"><thead><tr><th>campaign or run</th>'
            '<th class="n">total</th><th class="n">results</th><th class="n">profiles</th><th class="n">builds</th><th>newest</th><th></th>'
            '</tr></thead><tbody id="rows"></tbody></table></div></section>')
    return _page(server, "storage", "admin", body, ADMIN_JS)
