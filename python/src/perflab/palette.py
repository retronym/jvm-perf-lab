"""⌘K on the perflab server's pages: a window that searches what /api/search lists (perflab.server.search_items) and, before
anything is typed, shows the pages this browser opened last (localStorage, so per browser), the active jobs and the latest
campaigns. Not on file://, and not in a sandboxed page, which can use neither the API nor localStorage: there
ui.FRAME_KEYS_JS passes ⌘K up to the page framing it, or goes to the queue page, which opens the window (`/?k=1`).
"""

CSS = """
#pal{position:fixed;inset:0;z-index:300;background:rgba(10,14,20,.45);display:flex;align-items:flex-start;justify-content:center;padding:10vh 16px 16px}
#pal[hidden]{display:none}
#pal .box{background:var(--panel);color:var(--fg);border:1px solid var(--line);border-radius:10px;width:min(720px,100%);max-height:100%;display:flex;flex-direction:column;
  box-shadow:0 10px 40px rgba(0,0,0,.35);overflow:hidden;font-size:13px}
#pal input{font:15px/22px -apple-system,system-ui,"Segoe UI",sans-serif;padding:10px 14px;border:0;border-bottom:1px solid var(--line);background:none;color:var(--fg);outline:0;width:100%;flex:none}
#pal .list{overflow-y:auto;padding:4px 0;min-height:60px}
#pal .sec{font-size:11px;font-weight:600;color:var(--muted);margin:8px 14px 2px;text-transform:uppercase;letter-spacing:.05em}
#pal a{display:flex;align-items:baseline;gap:8px;padding:4px 14px;color:var(--fg);text-decoration:none;min-width:0}
#pal a.on{background:var(--link-bg)}
#pal .kd{flex:none;width:58px;font-size:11px;color:var(--muted)}
#pal .tt{flex:0 1 auto;min-width:0;max-width:65%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#pal .sb{flex:1 1 0;min-width:0;color:var(--muted);font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#pal .wh{flex:none;color:var(--muted);font-size:11.5px}
#pal .none{padding:12px 14px;color:var(--muted)}
#pal .hint{flex:none;border-top:1px solid var(--line2);padding:4px 14px;color:var(--muted);font-size:11.5px}
@media (max-width:600px){#pal{padding:0} #pal .box{border-radius:0;height:100%} #pal .kd,#pal .wh{display:none}}
"""

# @ON_SERVER@: ui.ON_SERVER
JS = r"""
(() => {
  if (!(@ON_SERVER@) || self !== top || self.origin === 'null') return;
  // sent here by ⌘K in a sandboxed page, which is no page to remember
  const fromSandbox = new URLSearchParams(location.search).get('k') === '1';
  if (fromSandbox) history.replaceState(null, '', location.pathname + location.hash);
  const KEY = 'perflab.recent', MAX = 30;
  const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'})[c]);
  const recent = () => { try { return JSON.parse(localStorage.getItem(KEY)) || []; } catch (e) { return []; } };
  // a page opened again keeps the name it was remembered by, unless the caller knows a better one
  function remember(title, url, kind, better) {
    try {
      const u = new URL(url, location.href), to = u.pathname + u.search + u.hash, was = recent(), old = was.find(r => r.url === to);
      const keep = old && !better;
      localStorage.setItem(KEY, JSON.stringify([{title: keep ? old.title : title, url: to, kind: keep ? old.kind : kind, at: Date.now()},
                                                ...was.filter(r => r.url !== to)].slice(0, MAX)));
    } catch (e) {}
  }
  window.perflabRecent = (title, url, kind) => remember(title, url, kind, true);
  const here = () => {
    const h = location.hash ? decodeURIComponent(location.hash.slice(1)) : '';
    remember((h ? h + ' · ' : '') + document.title, location.href, 'page', false);
  };
  here(); addEventListener('hashchange', here);

  const box = document.createElement('div');
  box.id = 'pal'; box.hidden = true; box.setAttribute('role', 'dialog'); box.setAttribute('aria-label', 'Search');
  box.innerHTML = '<div class="box"><input type="search" placeholder="Search campaigns, runs, jobs, docs…" aria-label="Search" autocomplete="off" spellcheck="false">'
    + '<div class="list"></div><div class="hint"><kbd>↑</kbd> <kbd>↓</kbd> choose · <kbd>↵</kbd> open · <kbd>⌘</kbd> <kbd>↵</kbd> new tab · <kbd>Esc</kbd> close</div></div>';
  document.body.appendChild(box);
  const input = box.querySelector('input'), list = box.querySelector('.list');
  let items = [], loaded = 0, shown = [], sel = 0, before = null;

  const ago = ms => {
    const s = (Date.now() - ms) / 1000;
    return s < 90 ? 'just now' : s < 5400 ? Math.round(s / 60) + ' min ago' : s < 129600 ? Math.round(s / 3600) + ' h ago' : Math.round(s / 86400) + ' d ago';
  };
  const stamp = it => it.at || (it.when || 0) * 1000;
  const row = (it, i) => `<a href="${esc(it.url)}" data-i="${i}"><span class="kd">${esc(it.kind)}</span><span class="tt">${esc(it.title)}</span>`
    + `<span class="sb">${esc(it.sub)}</span><span class="wh">${esc(it.state || (stamp(it) ? ago(stamp(it)) : ''))}</span></a>`;
  // every word somewhere in the item, those in its title counting most; failing that, the query's letters in order in its title
  function score(it, words, q) {
    const t = it.title.toLowerCase(), all = t + ' ' + String(it.sub || '').toLowerCase() + ' ' + String(it.text || '').toLowerCase();
    let s = 0;
    for (const w of words) {
      if (!all.includes(w)) return inOrder(t, q);
      const at = t.indexOf(w);
      s += at === 0 ? 100 : at > 0 ? (/[\s\/._-]/.test(t[at - 1]) ? 60 : 40) : 10;
    }
    return s;
  }
  function inOrder(t, q) {
    let i = 0;
    for (const c of q.replace(/\s+/g, '')) { i = t.indexOf(c, i) + 1; if (!i) return 0; }
    return 1;
  }
  function render() {
    const q = input.value.trim().toLowerCase();
    let html = '';
    const all = [];
    const section = (name, its) => {
      if (!its.length) return;
      if (name) html += `<div class="sec">${esc(name)}</div>`;
      for (const it of its) { html += row(it, all.length); all.push(it); }
    };
    if (q) {
      const words = q.split(/\s+/), known = new Set(items.map(i => i.url));
      section('', [...items, ...recent().filter(r => !known.has(r.url))]
        .map(it => [score(it, words, q), it]).filter(x => x[0] > 0)
        .sort((a, b) => b[0] - a[0] || (a[1].kind === 'job') - (b[1].kind === 'job') || stamp(b[1]) - stamp(a[1])).slice(0, 40).map(x => x[1]));
    } else {
      const at = location.pathname + location.search + location.hash;
      section('Recent', recent().filter(r => r.url !== at).slice(0, 8));
      section('Jobs', items.filter(i => i.kind === 'job' && i.active));
      section('Latest campaigns', items.filter(i => i.kind === 'campaign').sort((a, b) => stamp(b) - stamp(a)).slice(0, 5));
      section('Go to', items.filter(i => i.kind === 'project' || i.kind === 'page'));
    }
    shown = all;
    sel = Math.max(0, Math.min(sel, all.length - 1));
    list.innerHTML = html || `<div class="none">${q ? 'Nothing matches.' : 'Loading…'}</div>`;
    mark();
  }
  function mark(scroll = true) {
    list.querySelectorAll('a').forEach(a => {
      const on = +a.dataset.i === sel;
      a.classList.toggle('on', on);
      if (on && scroll) a.scrollIntoView({block: 'nearest'});
    });
  }
  function load() {
    if (Date.now() - loaded < 15000) return;
    fetch('/api/search', {cache: 'no-store'}).then(r => r.json()).then(r => {
      items = r.items || []; loaded = Date.now();
      if (!box.hidden) render();
    }).catch(() => {});
  }
  function open() {
    if (!box.hidden) return;
    before = document.activeElement; box.hidden = false; input.value = ''; sel = 0;
    render(); input.focus(); load();
  }
  function close() {
    box.hidden = true;
    if (before && before.focus) before.focus();
  }
  function go(it, tab) {
    if (!it) return;
    remember(it.title, it.url, it.kind, true);
    if (tab) { window.open(it.url, '_blank', 'noopener'); return; }
    close();
    if (typeof Lightbox !== 'undefined') Lightbox.close();
    location.href = it.url;
  }
  const toggle = () => box.hidden ? open() : close();
  // capture: ⌘K wherever the focus is, and Esc closes this before the overlays under it
  document.addEventListener('keydown', e => {
    if ((e.metaKey || e.ctrlKey) && !e.altKey && !e.shiftKey && e.key.toLowerCase() === 'k') { e.preventDefault(); e.stopImmediatePropagation(); toggle(); return; }
    if (box.hidden) return;
    const move = d => { if (shown.length) { sel = (sel + d + shown.length) % shown.length; mark(); } e.preventDefault(); };
    if (e.key === 'Escape') { close(); e.preventDefault(); e.stopImmediatePropagation(); }
    else if (e.key === 'ArrowDown' || (e.ctrlKey && e.key === 'n')) move(1);
    else if (e.key === 'ArrowUp' || (e.ctrlKey && e.key === 'p')) move(-1);
    else if (e.key === 'Enter') { e.preventDefault(); go(shown[sel], e.metaKey || e.ctrlKey); }
  }, true);
  input.addEventListener('input', () => { sel = 0; render(); });
  box.addEventListener('click', e => {
    if (e.target === box) { close(); return; }
    const a = e.target.closest('a[data-i]');
    if (a && !e.metaKey && !e.ctrlKey) { e.preventDefault(); go(shown[+a.dataset.i]); }
  });
  list.addEventListener('mousemove', e => {
    const a = e.target.closest('a[data-i]');
    if (a && +a.dataset.i !== sel) { sel = +a.dataset.i; mark(false); }
  });
  addEventListener('message', e => { if (e.data && e.data.perflabKey === 'k') toggle(); });
  document.querySelectorAll('.pal-btn').forEach(b => { b.hidden = false; b.onclick = toggle; });
  const keys = document.querySelector('#keys dl');
  if (keys) keys.insertAdjacentHTML('afterbegin', '<dt><kbd>⌘</kbd> <kbd>K</kbd></dt><dd>search campaigns, runs, jobs and docs; recent pages</dd>');
  if (fromSandbox) open();
})();
"""


def script(on_server):
    return f"<style>{CSS}</style><script>{JS.replace('@ON_SERVER@', on_server)}</script>"
