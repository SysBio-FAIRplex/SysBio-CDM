/* ───────────── main: folder, library, search, side panel, saving, keyboard ───────────── */
const anyDirty = () => Array.from(S.files.values()).some(F => F.dirty);
function l2Gaps(root) {
  let missing = 0, targets = 0;
  for (const t of C.targets(root)) {
    if (!C.isObj(t) || !Array.isArray(t.value_map)) continue;
    targets++;
    for (const r of C.l2Grid(root, t).rows) if (r.entryIndex === null) missing++;
  }
  return { targets, missing };
}
/* regId: the file's path in the registry (null for a file that exists only as a staged copy).
   stagedId: its path under staged_proposed/ once a staged copy exists; the page shows the staged copy when there is one. */
function newFile(id, text, regId, stagedId) {
  const F = { id, name: id.split('/').pop(), regId: regId === undefined ? id : regId, stagedId: stagedId || null, diskText: '', value: undefined, base: undefined, meta: null, undo: [], redo: [], dirty: false, sum: null, leaves: null, saveState: null };
  loadText(F, text);
  return F;
}
function loadText(F, text) {
  F.diskText = text; F.undo = []; F.redo = []; F.leaves = null; F.saveState = null; F.histCache = null;
  try {
    const r = C.parseJSONText(text);
    F.value = r.value; F.meta = r.meta; F.base = C.clone(r.value);
    F.baseRaw = new Map(r.meta.rawNums); F.baseKO = new Map(r.meta.keyOrder); F.error = null;
    const out = C.stringifyJSON(r.value, r.meta);
    F.roundTrip = out === text;
    if (!F.roundTrip) { const d = C.lineDiff(text, out); F.rtLines = d ? d.changed : undefined; } else F.rtLines = 0;
  } catch (e) {
    F.value = undefined; F.meta = null; F.base = undefined; F.baseRaw = new Map(); F.baseKO = new Map();
    F.error = { message: e.message, line: e.line, col: e.col }; F.roundTrip = null;
  }
  F.dirty = false;
  F.sum = C.summarize(F.id, F.value);
  F.gaps = l2Gaps(F.value);
  S.clCache = null; S.enumsDirty = true;
}

function refreshEnums() {
  S.enumsDirty = false; S.enumsAt = Date.now();
  const roots = [];
  for (const F of S.files.values()) if (C.isObj(F.value)) roots.push(F.value);
  const e = C.collectEnums(roots);
  const count = () => new Map();
  const progs = count(), units = count(), pc = count();
  const bump = (m, v) => { if (typeof v === 'string' && v) m.set(v, (m.get(v) || 0) + 1); };
  for (const r of roots) {
    if (Array.isArray(r.programs_covered)) r.programs_covered.forEach(p => bump(pc, p));
    bump(units, r.unit);
    for (const { block } of C.blocks(r)) { bump(progs, block.program); if (C.isObj(block.layer_1_etl)) bump(units, block.layer_1_etl.unit); }
  }
  const top = m => Array.from(m.entries()).sort((a, b) => b[1] - a[1]).map(x => x[0]);
  e.program = top(progs); e.programs_covered = C.uniq(top(pc).concat(top(progs))); e.unit = top(units);
  S.enums = e;
}

/* ── where files are read from, and where saves go ──
   Every save goes to <registry>/staged_proposed/<path>; a registry file is never written.
   The staged file is named after registry_label, so a relabelled element is staged under its new name. */
const STAGED = 'staged_proposed';
const dirOf = p => (p.includes('/') ? p.slice(0, p.lastIndexOf('/') + 1) : '');
const labelFileName = v => (C.isObj(v) && typeof v.registry_label === 'string' && /^[A-Za-z0-9][A-Za-z0-9_.-]{0,150}$/.test(v.registry_label) ? v.registry_label + '.json' : null);
function stageTarget(F) {
  const base = F.stagedId || F.regId || F.name;
  return dirOf(base) + (labelFileName(F.value) || base.split('/').pop());
}
const excluded = id => id.split('/').some(seg => seg.startsWith('.') || S.exclude.includes(seg));
async function walk(dir, prefix, out, depth) {
  for await (const [name, hd] of dir.entries()) {
    if (hd.kind === 'directory') { if (depth < 4 && !name.startsWith('.') && !S.exclude.includes(name) && !(depth === 0 && name === STAGED)) await walk(hd, prefix + name + '/', out, depth + 1); }
    else if (/\.json$/i.test(name) && !name.startsWith('.')) out.push({ id: prefix + name, handle: hd });
  }
}
const notFound = e => e && (e.name === 'NotFoundError' || e.name === 'TypeMismatchError');
/* a folder picked in the browser (File System Access API) */
function folderStore(root) {
  async function fileAt(path, create) {
    const parts = path.split('/'), name = parts.pop();
    let d = root;
    for (const p of parts) d = await d.getDirectoryHandle(p, { create });
    return d.getFileHandle(name, { create });
  }
  const asEntries = list => list.map(e => ({ id: e.id, read: async () => (await e.handle.getFile()).text() }));
  return {
    kind: 'folder', name: root.name, handle: root,
    async permission() {
      if (!root.queryPermission) return true;
      let p = await root.queryPermission({ mode: 'readwrite' });
      if (p !== 'granted' && root.requestPermission) p = await root.requestPermission({ mode: 'readwrite' });
      return p === 'granted';
    },
    async list() { const out = []; await walk(root, '', out, 0); return asEntries(out); },
    async listStaged() {
      let d;
      try { d = await root.getDirectoryHandle(STAGED); } catch (e) { if (notFound(e)) return []; throw e; }
      const out = []; await walk(d, '', out, 0); return asEntries(out);
    },
    async read(area, path) {
      try { return await (await (await fileAt(area === 'staged' ? STAGED + '/' + path : path, false)).getFile()).text(); }
      catch (e) { if (notFound(e)) return null; throw e; }
    },
    async write(path, text) {
      const w = await (await fileAt(STAGED + '/' + path, true)).createWritable();
      await w.write(text); await w.close();
    }
  };
}
/* the registry folder the relay serves (the page was opened from the relay) */
function relayStore(base, token) {
  const hdr = { 'X-CDEB-Token': token };
  async function fail(r) { const j = await r.json().catch(() => null); return new Error(j && j.error ? j.error.message : 'the relay answered HTTP ' + r.status); }
  async function getJSON(url) { const r = await fetch(base + url, { headers: hdr, cache: 'no-store' }); if (!r.ok) throw await fail(r); return r.json(); }
  let listing = null;
  const entries = (paths, area) => paths.map(p => ({ id: p, read: () => store.read(area, p) }));
  const store = {
    kind: 'relay', name: 'registry',
    async permission() { return true; },
    async list() { listing = await getJSON('/registry/list'); store.name = listing.name; store.where = listing.registry; return entries(listing.files, 'registry'); },
    async listStaged() { if (!listing) await store.list(); return entries(listing.staged, 'staged'); },
    async read(area, path) {
      const r = await fetch(base + '/registry/file?area=' + area + '&path=' + encodeURIComponent(path), { headers: hdr, cache: 'no-store' });
      if (r.status === 404) return null;
      if (!r.ok) throw await fail(r);
      return r.text();
    },
    async write(path, text) {
      const r = await fetch(base + '/registry/staged?path=' + encodeURIComponent(path), { method: 'PUT', headers: Object.assign({ 'Content-Type': 'application/json; charset=utf-8' }, hdr), body: text, cache: 'no-store' });
      if (!r.ok) throw await fail(r);
    }
  };
  return store;
}
function relayServedToken() {
  const m = document.querySelector('meta[name="cdeb-relay-token"]');
  return m && m.content && /^https?:$/.test(location.protocol) ? m.content : '';
}
async function confirmDiscard() {
  const n = Array.from(S.files.values()).filter(F => F.dirty).length;
  const r = await modal('Unsaved changes', h('p', null, n + ' file' + (n === 1 ? ' has' : 's have') + ' unsaved changes. Opening another folder drops them (a copy of each goes to “Earlier versions” in this browser).'), [{ label: 'Cancel', value: false }, { label: 'Drop them and continue', value: true }]);
  if (r) for (const F of S.files.values()) if (F.dirty && F.value !== undefined) await histAdd(histKey(F), C.stringifyJSON(F.value, F.meta), 'unsaved edits, dropped when another folder was opened');
  return !!r;
}
async function openFolder() {
  if (!window.showDirectoryPicker) { $('#dirinput').click(); return; }
  let hd;
  try { hd = await window.showDirectoryPicker({ id: 'cde-registry', mode: 'readwrite' }); }
  catch (e) { if (e && e.name !== 'AbortError') toast('Could not open the folder: ' + e.message, 'err'); return; }
  if (anyDirty() && !(await confirmDiscard())) return;
  await kvSet('root', hd);
  await loadStore(folderStore(hd));
}
async function reopenFolder() {
  const hd = await kvGet('root');
  if (!hd) return openFolder();
  try {
    const p = await hd.requestPermission({ mode: 'readwrite' });
    if (p !== 'granted') { toast('Permission to the folder was not granted.', 'err'); return; }
    await loadStore(folderStore(hd));
  } catch (e) { toast('Could not reopen the folder: ' + e.message + '. Use Open folder.', 'err'); }
}
const loadFolder = hd => loadStore(folderStore(hd));
/* Reads every registry file; where staged_proposed/ holds a copy at the same path, the staged copy is what opens.
   A staged file with no registry counterpart (a relabelled or new element) opens as its own entry. */
async function loadStore(store) {
  S.loading = { done: 0, total: 0, name: store.name };
  renderCenter();
  let reg, stg;
  try { reg = (await store.list()).filter(e => !excluded(e.id)); stg = (await store.listStaged()).filter(e => !excluded(e.id)); }
  catch (e) { S.loading = null; toast('Could not read the registry: ' + e.message, 'err'); renderAll(); return; }
  S.loading.name = store.name;
  const stagedBy = new Map(stg.map(e => [e.id, e]));
  const regIds = new Set(reg.map(e => e.id));
  const jobs = reg.map(e => ({ id: e.id, regId: e.id, src: stagedBy.get(e.id) || e, stagedId: stagedBy.has(e.id) ? e.id : null }))
    .concat(stg.filter(e => !regIds.has(e.id)).map(e => ({ id: STAGED + '/' + e.id, regId: null, src: e, stagedId: e.id })));
  jobs.sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
  S.loading.total = jobs.length;
  const files = new Map(jobs.map(j => [j.id, null]));
  const failed = [];
  for (let i = 0; i < jobs.length; i += 24) {
    await Promise.all(jobs.slice(i, i + 24).map(async j => {
      try { files.set(j.id, newFile(j.id, await j.src.read(), j.regId, j.stagedId)); }
      catch (err) { failed.push(j.id + ': ' + err.message); files.delete(j.id); }
      S.loading.done++;
    }));
    const pr = $('#loadprog');
    if (pr) pr.textContent = 'Read ' + S.loading.done + ' of ' + S.loading.total + ' files …';
  }
  S.files = files;
  S.store = store; S.root = store.handle || null; S.rootName = store.name; S.mode = 'rw'; S.loading = null;
  if (!S.files.has(S.current)) S.current = null;
  if (!S.files.has(S.compare)) S.compare = null;
  S.clCache = null;
  refreshEnums();
  if (failed.length) toast(failed.length + ' file(s) could not be read: ' + failed.slice(0, 3).join('; '), 'err');
  scheduleRender();
}
async function loadReadOnly(fileList) {
  const list = Array.from(fileList).filter(f => /\.json$/i.test(f.name));
  if (!list.length) { toast('No .json files in that folder.', 'err'); return; }
  if (anyDirty() && !(await confirmDiscard())) return;
  const files = new Map();
  const rootName = (list[0].webkitRelativePath || '').split('/')[0] || 'folder';
  for (const f of list) {
    const rel = (f.webkitRelativePath || f.name).split('/').slice(1).join('/') || f.name;
    if (excluded(rel) || rel.split('/')[0] === STAGED) continue;
    files.set(rel, newFile(rel, await f.text()));
  }
  S.files = new Map(Array.from(files.entries()).sort((a, b) => (a[0] < b[0] ? -1 : 1)));
  S.store = null; S.root = null; S.rootName = rootName; S.mode = 'ro'; S.current = null; S.compare = null; S.clCache = null;
  refreshEnums();
  toast('Opened read-only: this browser cannot write to folders. Use Download to keep an edited file.', 'err');
  scheduleRender();
}

/* ── library ── */
const GROUPS = {
  program: ['Program', F => F.sum.programs.join(' + ') || '(no programs_covered)'],
  l2: ['Layer 2 gaps', F => (F.value === undefined ? 'not valid JSON' : !F.gaps.targets ? 'no targets with a value_map' : F.gaps.missing ? 'values without a Layer 2 entry' : 'every value has an entry')],
  grain: ['Grain', F => F.sum.grains.join('; ') || '(no grain declared)'],
  table: ['Layer 2 table', F => F.sum.tables.join(' + ') || '(no target table)'],
  form: ['value_form', F => F.sum.forms.join(' + ') || '(no value_form)'],
  schema: ['Schema', F => F.sum.schema || '(no schema_version)'],
  word: ['First word', F => F.sum.label.toLowerCase().split(/[_\W]+/)[0] || '(none)'],
  folder: ['Folder', F => F.sum.dir || '(top folder)'],
  state: ['Edit state', F => (F.value === undefined ? 'not valid JSON' : F.dirty ? 'edited' : F.roundTrip === false ? 'layout differs from json.dump' : 'unchanged')],
  none: ['None', () => 'All files']
};
function libItems() {
  const f = S.lib.filter.toLowerCase().trim();
  const words = f ? f.split(/\s+/) : [];
  const out = [];
  for (const F of S.files.values()) {
    if (S.lib.onlyEdited && !F.dirty) continue;
    if (words.length) {
      const s = F.sum;
      const hay = (s.label + ' ' + F.id + ' ' + s.programs.join(' ') + ' ' + s.tables.join(' ') + ' ' + s.forms.join(' ') + ' ' + s.curie).toLowerCase();
      if (!words.every(w => hay.includes(w))) continue;
    }
    out.push(F);
  }
  return out;
}
function libGroups() {
  const g = GROUPS[S.lib.groupBy] || GROUPS.program;
  const map = new Map();
  for (const F of libItems()) { const k = g[1](F); if (!map.has(k)) map.set(k, []); map.get(k).push(F); }
  const groups = Array.from(map.entries()).sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));
  for (const [, items] of groups) items.sort((a, b) => (a.sum.label < b.sum.label ? -1 : a.sum.label > b.sum.label ? 1 : 0));
  return groups;
}
function libraryOrder(includeCollapsed) {
  const ids = [];
  for (const [k, items] of libGroups()) if (includeCollapsed || !S.lib.collapsed[k]) for (const F of items) ids.push(F.id);
  return ids;
}
function renderLibrary() {
  const list = $('#liblist');
  if (!list) return;
  const groups = libGroups();
  const total = groups.reduce((n, g) => n + g[1].length, 0);
  const edited = Array.from(S.files.values()).filter(F => F.dirty).length;
  const invalid = Array.from(S.files.values()).filter(F => F.value === undefined).length;
  $('#libmeta').textContent = S.files.size ? (total === S.files.size ? total + ' files' : total + ' of ' + S.files.size + ' files') + (edited ? ' · ' + edited + ' edited' : '') + (invalid ? ' · ' + invalid + ' not valid JSON' : '') : '';
  const kids = [];
  for (const [k, items] of groups) {
    const coll = !!S.lib.collapsed[k];
    if (S.lib.groupBy !== 'none') kids.push(h('div', { class: 'grp', title: 'click to fold', onclick: () => { if (coll) delete S.lib.collapsed[k]; else S.lib.collapsed[k] = true; renderLibrary(); } }, (coll ? '▸ ' : '▾ ') + k + ' · ' + items.length));
    if (coll) continue;
    for (const F of items) {
      const s = F.sum;
      const meta = [F.name !== s.label + '.json' ? F.id : null, s.nBlocks + ' block' + (s.nBlocks === 1 ? '' : 's') + ' · ' + s.nTargets + ' target' + (s.nTargets === 1 ? '' : 's'), F.gaps && F.gaps.missing ? F.gaps.missing + ' L2 gap' + (F.gaps.missing === 1 ? '' : 's') : null].filter(Boolean).join(' · ');
      kids.push(h('div', { class: 'item' + (F.id === S.current ? ' on' : '') + (F.id === S.compare ? ' cmp' : ''), 'data-id': F.id, onclick: () => openFile(F.id) },
        h('div', { class: 'l' }, s.label, F.stagedId ? h('span', { class: 'badge staged', title: 'opened from ' + STAGED + '/' + F.stagedId }, 'staged') : null, F.dirty ? h('span', { class: 'badge edit' }, 'edited') : null, F.value === undefined ? h('span', { class: 'badge err' }, 'not valid JSON') : null,
          F.roundTrip === false ? h('span', { class: 'badge fmt', title: 'Save rewrites some layout lines' }, 'layout') : null, F.saveState && F.saveState.kind === 'err' ? h('span', { class: 'badge err' }, 'save failed') : null),
        h('div', { class: 'm' }, meta)));
    }
  }
  if (!S.files.size) kids.push(h('div', { class: 'sub2', style: 'padding:12px' }, 'No folder open.'));
  else if (!total) kids.push(h('div', { class: 'sub2', style: 'padding:12px' }, 'No file matches the filter.'));
  list.replaceChildren(...kids);
  const on = list.querySelector('.item.on');
  if (on && S._libScrollTo !== S.current) { on.scrollIntoView({ block: 'nearest' }); S._libScrollTo = S.current; }
}
function openFile(id) {
  if (!S.files.has(id)) return;
  if (S.editing) S.editing.commit();
  closePop();
  S.current = id;
  if (S.compare === id) S.compare = null;
  S.tab = 'files';
  scheduleRender();
}
function step(d) {
  if (S.tab === 'clusters') { clusterStep(d); return; }
  const ids = libraryOrder();
  if (!ids.length) return;
  const i = ids.indexOf(S.current);
  const n = i < 0 ? (d > 0 ? 0 : ids.length - 1) : Math.max(0, Math.min(ids.length - 1, i + d));
  openFile(ids[n]);
}

/* ── going to a field ── */
function scrollToPath(F, path) {
  if (S.current !== F.id && S.compare !== F.id) S.current = F.id;
  S.tab = 'files';
  S.sheet.raw = false;
  if (path[0] === 'sysbio_etl') S.sheet.l2View = 'target';
  for (let i = 1; i <= path.length; i++) delete S.sheet.collapsed[edKey(F, path.slice(0, i))];
  for (let i = 1; i < path.length; i++) if (typeof path[i] === 'number') { const ak = edKey(F, path.slice(0, i)); delete S.sheet.filters[ak]; if (path[i] >= 150) S.sheet.showAll[ak] = true; }
  S.pendingScroll = { file: F.id, path };
  scheduleRender();
}
function doScroll(ps) {
  for (let n = ps.path.length; n >= 0; n--) {
    const key = ps.file + '|' + C.pk(ps.path.slice(0, n));
    const el = document.querySelector('[data-ed="' + CSS.escape(key) + '"]') || document.querySelector('[data-path="' + CSS.escape(key) + '"]');
    if (el) {
      el.scrollIntoView({ block: 'center' });
      el.classList.remove('flash'); void el.offsetWidth; el.classList.add('flash');
      return true;
    }
  }
  return false;
}

/* ── search across every file ── */
function leavesOf(F) {
  if (F.leaves) return F.leaves;
  const out = [];
  if (F.value !== undefined) C.leaves(F.value, (p, v) => { if (v === null || typeof v === 'object') return; out.push([p, String(v)]); });
  F.leaves = out;
  return out;
}
function runSearch(qs) {
  const raw = qs.trim();
  if (!raw) return { results: [], files: 0, more: false };
  const m = raw.match(/^([A-Za-z_][\w.]*):(.*)$/);
  const field = m ? m[1].toLowerCase() : null;
  const qq = (m ? m[2] : raw).trim().toLowerCase();
  const res = [];
  const hitFiles = new Set();
  if (!field) {
    for (const F of S.files.values()) {
      const lab = F.sum.label.toLowerCase();
      if (lab.includes(qq) || F.id.toLowerCase().includes(qq)) { res.push({ id: F.id, path: [], kind: 'file', text: F.sum.label, score: lab === qq ? 0 : lab.startsWith(qq) ? 1 : 2 }); hitFiles.add(F.id); }
    }
    res.sort((a, b) => a.score - b.score || (a.text < b.text ? -1 : 1));
  }
  let more = false;
  outer: for (const F of S.files.values()) {
    for (const [p, v] of leavesOf(F)) {
      if (field) {
        const names = p.filter(x => typeof x === 'string').map(x => x.toLowerCase());
        const last = names[names.length - 1];
        if (!(last === field || names.join('.').endsWith(field))) continue;
        if (qq && !v.toLowerCase().includes(qq)) continue;
      } else if (!v.toLowerCase().includes(qq)) continue;
      if (res.length >= 500) { more = true; break outer; }
      res.push({ id: F.id, path: p, kind: 'value', text: v });
      hitFiles.add(F.id);
    }
  }
  return { results: res, files: hitFiles.size, more, q: qq };
}
function markText(text, qq) {
  const t = text.length > 160 ? text.slice(0, 160) + '…' : text;
  if (!qq) return [t];
  const i = t.toLowerCase().indexOf(qq);
  if (i < 0) return [t];
  return [t.slice(0, i), h('mark', null, t.slice(i, i + qq.length)), t.slice(i + qq.length)];
}
let _sr = { results: [], hi: 0 };
function showResults() {
  const box = $('#results');
  const r = runSearch($('#search').value);
  _sr = { results: r.results, hi: 0, q: r.q };
  if (!$('#search').value.trim()) { box.hidden = true; return; }
  const kids = [h('div', { class: 'r p' }, r.results.length ? r.results.length + (r.more ? '+' : '') + ' match' + (r.results.length === 1 ? '' : 'es') + ' in ' + r.files + ' file' + (r.files === 1 ? '' : 's') + ' · Enter opens · field:text searches one field' : 'No match.')];
  r.results.slice(0, 300).forEach((x, i) => {
    const F = S.files.get(x.id);
    kids.push(h('div', { class: 'r' + (i === 0 ? ' hi' : ''), 'data-i': i, onmousedown: ev => { ev.preventDefault(); chooseResult(i); } },
      h('div', { class: 'f' }, F.sum.label, x.kind === 'file' ? h('span', { class: 'sub2' }, '  file') : null),
      x.kind === 'value' ? h('div', { class: 'p' }, C.pathLabel(F.value, x.path)) : null,
      x.kind === 'value' ? h('div', null, markText(x.text, _sr.q)) : null));
  });
  box.replaceChildren(...kids);
  box.hidden = false;
}
function hideResults() { const b = $('#results'); if (b) b.hidden = true; }
function chooseResult(i) {
  const x = _sr.results[i];
  if (!x) return;
  hideResults();
  $('#search').blur();
  const F = S.files.get(x.id);
  if (x.kind === 'file') { openFile(x.id); return; }
  S.current = x.id;
  scrollToPath(F, x.path);
}
function moveResult(d) {
  const box = $('#results');
  const rows = $$('.r[data-i]', box);
  if (!rows.length) return;
  _sr.hi = Math.max(0, Math.min(rows.length - 1, _sr.hi + d));
  rows.forEach((r, i) => r.classList.toggle('hi', i === _sr.hi));
  rows[_sr.hi].scrollIntoView({ block: 'nearest' });
}

/* ── saving: write, read back, compare ── */
function conflictModal(F, expected, disk, target) {
  return modal('The file changed on disk', h('div', null,
    h('p', null, expected === null
      ? STAGED + '/' + target + ' already exists and is not this page’s copy. Below: how it differs from the version this page opened.'
      : STAGED + '/' + target + ' is not what this page read. Below: what changed on disk since then.'),
    diffEl(expected === null ? F.diskText : expected, disk),
    h('p', { class: 'sub2' }, 'Overwrite writes your version (the disk version is kept under Earlier versions). Load drops your edits (they are kept under Earlier versions).')),
  [{ label: 'Cancel', value: 'cancel' }, { label: 'Load the disk version', value: 'reload' }, { label: 'Overwrite with mine', value: 'overwrite', pri: true }]);
}
async function saveFile(F) {
  if (S.editing) S.editing.commit();
  if (!F) return false;
  if (F.value === undefined) { toast('Nothing to save: the text does not parse yet.', 'err'); return false; }
  if (!F.dirty && F.base !== undefined) return true;
  if (S.mode !== 'rw' || !S.store) { toast('This folder is open read-only: use Download.', 'err'); return false; }
  if (F.saving) return false;
  F.saving = true;
  const text = C.stringifyJSON(F.value, F.meta);
  try {
    let check;
    try { check = C.parseJSONText(text); } catch (e) { throw new Error('the text to write does not parse (' + e.message + '); nothing written'); }
    if (!C.deepEqual(check.value, F.value)) throw new Error('the text to write does not read back as the edited value; nothing written');
    F.saveState = { kind: 'busy', msg: 'Saving …' };
    renderSide();
    if (!(await S.store.permission())) throw new Error('write permission to the folder was not granted');
    const target = stageTarget(F);
    const expected = F.stagedId === target ? F.diskText : null;
    const disk = await S.store.read('staged', target);
    if (disk !== null && disk !== expected && disk !== text) {
      const choice = await conflictModal(F, expected, disk, target);
      if (choice === 'reload') {
        await histAdd(histKey(F), text, 'your unsaved edits, replaced by the staged copy on disk');
        loadText(F, disk); F.stagedId = target;
        toast('Loaded the staged copy on disk; your edits are under Earlier versions.', 'ok');
        scheduleRender();
        return false;
      }
      if (choice !== 'overwrite') { F.saveState = { kind: 'warn', msg: 'Not saved: the staged file changed on disk.' }; scheduleRender(); return false; }
    }
    await histAdd(histKey(F), disk !== null ? disk : F.diskText, disk !== null ? 'staged copy before your save' : 'the version this page opened, before your save');
    await S.store.write(target, text);
    const back = await S.store.read('staged', target);
    if (back !== text) throw new Error('read-back mismatch: the file on disk is not what was written. Your edits are still here');
    F.diskText = back; F.stagedId = target;
    F.base = C.clone(F.value);
    F.baseRaw = new Map(F.meta.rawNums); F.baseKO = new Map(F.meta.keyOrder);
    F.dirty = false; F.roundTrip = true; F.rtLines = 0; F.histCache = null;
    F.saveState = { kind: 'ok', msg: 'Saved to ' + STAGED + '/' + target + ' · read back OK', time: Date.now() };
    scheduleRender();
    return true;
  } catch (e) {
    F.saveState = { kind: 'err', msg: 'Not saved: ' + (e && e.message ? e.message : String(e)) };
    toast(F.id + ' — ' + F.saveState.msg, 'err');
    scheduleRender();
    return false;
  } finally { F.saving = false; }
}
async function saveAll() {
  if (S.editing) S.editing.commit();
  const list = Array.from(S.files.values()).filter(F => F.dirty);
  if (!list.length) { toast('Nothing to save.'); return; }
  let ok = 0;
  for (const F of list) if (await saveFile(F)) ok++;
  toast(ok === list.length ? 'Saved ' + ok + ' file' + (ok === 1 ? '' : 's') + ' · each read back OK' : 'Saved ' + ok + ' of ' + list.length + '; see the files marked “save failed”.', ok === list.length ? 'ok' : 'err');
}
function download(F) {
  const blob = new Blob([currentText(F)], { type: 'application/json' });
  const a = h('a', { href: URL.createObjectURL(blob), download: F.name });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
}
async function reloadFromDisk(F) {
  if (!S.store) return;
  if (F.dirty) {
    const ok = await modal('Reload from disk?', h('p', null, 'Your unsaved edits to ' + F.id + ' are dropped (a copy goes to Earlier versions).'), [{ label: 'Cancel', value: false }, { label: 'Reload', value: true, pri: true }]);
    if (!ok) return;
    if (F.value !== undefined) await histAdd(histKey(F), C.stringifyJSON(F.value, F.meta), 'unsaved edits, dropped by Reload');
  }
  try {
    let text = F.stagedId ? await S.store.read('staged', F.stagedId) : null;
    if (text === null) { F.stagedId = null; text = F.regId ? await S.store.read('registry', F.regId) : null; }
    if (text === null) throw new Error('it is no longer on disk');
    loadText(F, text); toast('Reloaded ' + F.id, 'ok');
  }
  catch (e) { toast('Could not read ' + F.id + ': ' + e.message, 'err'); }
  scheduleRender();
}
function revertAll(F) {
  if (F.base === undefined || !F.dirty) return;
  F.undo.push(snapshot(F)); F.redo = [];
  F.value = C.clone(F.base); F.meta.rawNums = new Map(F.baseRaw); F.meta.keyOrder = new Map(F.baseKO);
  afterChange(F);
}
function revertChange(F, ch) {
  if (ch.kind === 'changed') {
    const b = C.clone(ch.before);
    setPath(F, ch.path, b, typeof b === 'number' ? F.baseRaw.get(C.pk(ch.path)) : undefined);
  } else if (ch.kind === 'added') {
    if (ch.arrayPath) arrDelete(F, ch.arrayPath, ch.newIndex); else delPath(F, ch.path);
  } else if (ch.kind === 'removed') {
    if (ch.arrayPath) arrInsert(F, ch.arrayPath, ch.insertAt !== undefined ? ch.insertAt : ch.oldIndex, C.clone(ch.before));
    else {
      const parent = ch.path.slice(0, -1);
      const baseParent = C.get(F.base, parent);
      if (C.isObj(C.get(F.value, parent))) addKeyOrdered(F, parent, ch.path[ch.path.length - 1], C.clone(ch.before), C.isObj(baseParent) ? Object.keys(baseParent) : null);
      else setPath(F, ch.path, C.clone(ch.before));
    }
  }
}

/* ── side panel ── */
function statusEl(F) {
  const st = F.saveState;
  if (st && st.kind === 'busy') return h('div', { class: 'status' }, st.msg);
  if (F.dirty) return h('div', { class: 'status dirty' }, 'Unsaved changes', st && st.kind === 'err' ? h('div', { class: 'flagtxt' }, st.msg) : null, st && st.kind === 'warn' ? h('div', { class: 'flagtxt' }, st.msg) : null);
  if (st && st.kind === 'ok') return h('div', { class: 'status ok' }, st.msg + ' · ' + new Date(st.time).toLocaleTimeString());
  if (F.value === undefined) return h('div', { class: 'status err' }, 'Not valid JSON' + (F.error ? ': ' + F.error.message : ''));
  return h('div', { class: 'status' }, 'No changes since it was read');
}
function changesEl(F) {
  if (F.value === undefined) return null;
  if (F.base === undefined) return h('div', { class: 'sub2' }, 'The disk version did not parse; Save writes the whole text.');
  if (!F.dirty) return h('div', { class: 'sub2' }, 'None.');
  const list = C.diff(F.base, F.value);
  const box = h('div', null);
  list.slice(0, 300).forEach(ch => {
    const label = C.pathLabel(ch.kind === 'removed' ? F.base : F.value, ch.path) || '(whole file)';
    box.append(h('div', { class: 'chg' },
      h('button', { class: 'linkbtn rv', title: 'undo just this change', onclick: () => revertChange(F, ch) }, 'revert'),
      h('div', { class: 'p', title: 'go to the field', onclick: () => scrollToPath(F, ch.kind === 'removed' ? ch.path.slice(0, -1) : ch.path) }, label),
      ch.kind === 'changed' ? h('div', null, h('span', { class: 'b' }, C.describe(ch.before, 60)), ' → ', C.describe(ch.after, 60))
        : ch.kind === 'added' ? h('div', null, 'added ', C.describe(ch.after, 80)) : h('div', null, h('span', { class: 'b' }, 'removed ' + C.describe(ch.before, 80)))));
  });
  if (list.length > 300) box.append(h('div', { class: 'sub2' }, '… ' + (list.length - 300) + ' more'));
  return box;
}
function historyEl(F) {
  const box = h('div', null, h('div', { class: 'sub2' }, '…'));
  const draw = list => {
    if (!list.length) { box.replaceChildren(h('div', { class: 'sub2' }, 'None yet. Each save keeps the version it replaced here, in this browser (not in your repo).')); return; }
    box.replaceChildren(...list.slice(0, 25).map(e => h('div', { class: 'chg' },
      h('div', null, new Date(e.time).toLocaleString(), h('span', { class: 'sub2' }, ' · ' + e.why)),
      h('button', { class: 'linkbtn', onclick: () => modal('Earlier version vs. the current edit', diffEl(e.text, currentText(F)), [{ label: 'Close', value: null }]) }, 'compare'),
      h('button', { class: 'linkbtn', onclick: () => {
        let parsed;
        try { parsed = C.parseJSONText(e.text); } catch (err) { toast('That version does not parse: ' + err.message, 'err'); return; }
        if (F.value === undefined) { F.value = parsed.value; F.meta = parsed.meta; F.error = null; afterChange(F); }
        else mutate(F, () => { F.value = parsed.value; F.meta.rawNums = parsed.meta.rawNums; F.meta.keyOrder = parsed.meta.keyOrder; });
        toast('Restored into the editor. Save writes it.', 'ok');
      } }, 'restore into the editor'))));
  };
  if (F.histCache) draw(F.histCache);
  else histList(histKey(F)).then(list => { F.histCache = list; draw(list); });
  return box;
}
function renderSide() {
  const side = $('#side');
  if (!side) return;
  const F = S.tab === 'files' ? curFile() : null;
  const kids = [];
  if (F) {
    kids.push(h('h3', null, 'This file'), h('div', { class: 'mono sub2', style: 'word-break:break-all' }, F.id),
      S.store && F.value !== undefined ? h('div', { class: 'sub2', style: 'word-break:break-all' },
        F.stagedId ? 'Opened from ' + STAGED + '/' + F.stagedId + '. ' : (F.regId ? 'Registry original, not staged. ' : ''),
        'Save writes ' + STAGED + '/' + stageTarget(F) + '.') : null,
      statusEl(F),
      h('div', { class: 'sideacts' },
        h('button', { class: 'btn pri', disabled: !F.dirty || S.mode !== 'rw' || F.value === undefined ? true : null, title: 'Ctrl+S', onclick: () => saveFile(F) }, 'Save'),
        h('button', { class: 'btn', disabled: !F.undo.length ? true : null, title: 'Ctrl+Z', onclick: () => undo(F) }, 'Undo' + (F.undo.length ? ' (' + F.undo.length + ')' : '')),
        h('button', { class: 'btn', disabled: !F.redo.length ? true : null, title: 'Ctrl+Shift+Z', onclick: () => redo(F) }, 'Redo'),
        h('button', { class: 'btn', disabled: !F.dirty || F.base === undefined ? true : null, onclick: () => revertAll(F) }, 'Revert all'),
        S.store ? h('button', { class: 'btn', onclick: () => reloadFromDisk(F) }, 'Reload') : null,
        h('button', { class: 'btn', title: 'download the current text', onclick: () => download(F) }, 'Download')));
    if (F.roundTrip === false) kids.push(h('div', { class: 'sub2' }, 'Layout: Save rewrites ' + (F.rtLines === undefined ? 'some' : F.rtLines) + ' line(s) to json.dump(indent=2) form. ', h('button', { class: 'linkbtn', onclick: () => { S.sheet.raw = true; S.sheet.rawMode = 'diff'; scheduleRender(); } }, 'show')));
    kids.push(h('h3', null, 'Changes'), changesEl(F));
    kids.push(h('h3', null, 'Earlier versions'), historyEl(F));
  }
  const edited = Array.from(S.files.values()).filter(G => G.dirty);
  kids.push(h('h3', null, 'Folder'));
  if (S.files.size) {
    kids.push(h('div', { class: 'sub2' }, S.rootName + ' · ' + S.files.size + ' files' + (S.mode === 'ro' ? ' · read-only' : ' · saves go to ' + STAGED + '/')),
      edited.length ? h('div', null, edited.slice(0, 40).map(G => h('div', { class: 'chg' }, h('span', { class: 'p', onclick: () => openFile(G.id) }, G.sum.label), G.saveState && G.saveState.kind === 'err' ? h('div', { class: 'flagtxt' }, G.saveState.msg) : null))) : h('div', { class: 'sub2' }, 'No unsaved files.'),
      h('div', { class: 'sideacts' }, h('button', { class: 'btn', disabled: !edited.length || S.mode !== 'rw' ? true : null, title: 'Ctrl+Shift+S', onclick: saveAll }, 'Save all' + (edited.length ? ' (' + edited.length + ')' : ''))));
  } else kids.push(h('div', { class: 'sub2' }, 'No folder open.'));
  kids.push(h('h3', null, 'Keys'), h('div', { class: 'sub2 keys' },
    h('div', null, h('span', { class: 'kbd' }, '/'), ' search  ', h('span', { class: 'kbd' }, 'j'), ' ', h('span', { class: 'kbd' }, 'k'), ' next / previous file'),
    h('div', null, 'In a value: ', h('span', { class: 'kbd' }, 'Enter'), ' keep  ', h('span', { class: 'kbd' }, 'Tab'), ' keep + next  ', h('span', { class: 'kbd' }, 'Esc'), ' cancel'),
    h('div', null, h('span', { class: 'kbd' }, 'Ctrl+S'), ' save  ', h('span', { class: 'kbd' }, 'Ctrl+Z'), ' undo  ', h('span', { class: 'kbd' }, 'Ctrl+Shift+Z'), ' redo')));
  const st = side.scrollTop;
  side.replaceChildren(...kids.filter(Boolean));
  side.scrollTop = st;
}

/* ── top bar, center, render loop ── */
function renderTop() {
  const tabs = $('#tabs');
  if (!tabs) return;
  tabs.replaceChildren(
    h('button', { class: S.tab === 'files' ? 'on' : '', onclick: () => { S.tab = 'files'; scheduleRender(); } }, 'Files'),
    h('button', { class: S.tab === 'clusters' ? 'on' : '', onclick: () => { S.tab = 'clusters'; scheduleRender(); } }, 'Clusters'));
  const pill = $('#relay');
  const st = S.relay.status;
  pill.className = 'pill ' + (st === 'ok' ? 'ok' : st === 'unknown' ? '' : 'bad');
  pill.textContent = 'OMOP Hub: ' + ({ ok: 'ready', nokey: 'relay has no API key', down: 'relay not running', unknown: 'checking …' }[st] || st);
  $('#folder').textContent = S.rootName ? S.rootName + (S.mode === 'ro' ? ' (read-only)' : '') : '';
  const n = Array.from(S.files.values()).filter(F => F.dirty).length;
  const sa = $('#saveall');
  sa.disabled = !n || S.mode !== 'rw';
  sa.textContent = n ? 'Save all (' + n + ')' : 'Save all';
  $('#openfolder').textContent = S.files.size ? 'Open another folder…' : 'Open folder…';
}
function welcomeEl() {
  const w = h('div', { class: 'welcome' }, h('h2', null, 'CDE Registry browser'));
  if (S.loading) { w.append(h('p', { id: 'loadprog', class: 'progress' }, 'Reading ' + S.loading.name + ' …')); return w; }
  const acts = h('div', { class: 'acts' }, h('button', { class: 'btn pri', onclick: openFolder }, 'Open the registry folder…'));
  if (S.remembered) acts.append(h('button', { class: 'btn', onclick: reopenFolder }, 'Reopen ' + S.remembered));
  w.append(h('p', null, 'Pick the registry folder (it opens by itself when this page is served by the relay). Every .json file in it, and in its subfolders, opens in the library. A save never overwrites a registry file: it writes ' + STAGED + '/<file> inside the registry folder, named after the element’s registry_label, and reads it back before it shows as saved. Where a staged copy exists, the staged copy is what opens.'), acts);
  if (!window.showDirectoryPicker) w.append(h('p', { class: 'banner warn' }, 'This browser cannot write to a folder (no File System Access API). The folder opens read-only; use Chrome or Edge to save.'));
  w.append(h('p', null, 'Concept search goes to OMOP Hub through a small relay on this computer, because OMOP Hub refuses requests made directly from a web page. Start it from the folder that holds this page and your .env:'),
    h('p', null, h('code', null, 'python cde_registry_browser_relay.py'), ' — then open ', h('code', null, 'http://127.0.0.1:8765/'), ' (or keep using this page).'));
  return w;
}
function renderCenter() {
  const c = $('#center');
  if (!c) return;
  const sig = S.tab + '|' + (S.tab === 'files' ? S.current + '|' + S.compare + '|' + S.sheet.raw : '');
  const same = S._sig === sig;
  const keep = {};
  if (same) { keep.__c = c.scrollTop; $$('[data-keep-scroll]', c).forEach(el => { keep[el.getAttribute('data-keep-scroll')] = el.scrollTop; }); }
  else if (S._sig) S.sheet.scroll[S._sig] = c.scrollTop;
  let content;
  let split = false;
  if (S.tab === 'clusters') content = S.files.size ? renderClusters() : welcomeEl();
  else if (!S.files.size || S.loading) content = welcomeEl();
  else {
    const F = curFile();
    const G = S.compare ? S.files.get(S.compare) : null;
    if (!F) content = overviewEl();
    else if (G) {
      split = true;
      content = h('div', { class: 'split' }, h('div', { class: 'pane', 'data-keep-scroll': 'pane1' }, sheetFor(F, 'main')), h('div', { class: 'pane', 'data-keep-scroll': 'pane2' }, sheetFor(G, 'compare')));
    } else content = sheetFor(F, 'main');
  }
  c.classList.toggle('splitmode', split || S.tab === 'clusters');
  c.replaceChildren(content);
  if (same) { c.scrollTop = keep.__c; $$('[data-keep-scroll]', c).forEach(el => { const k = el.getAttribute('data-keep-scroll'); if (k in keep) el.scrollTop = keep[k]; }); }
  else c.scrollTop = S.sheet.scroll[sig] || 0;
  S._sig = sig;
}
function overviewEl() {
  const files = Array.from(S.files.values());
  const n = k => files.filter(k).length;
  const gaps = files.filter(F => F.gaps && F.gaps.missing);
  return h('div', { class: 'welcome' }, h('h2', null, S.rootName),
    h('p', null, files.length + ' mapping files. Pick one in the library, press ', h('span', { class: 'kbd' }, 'j'), ' to start at the top, or ', h('span', { class: 'kbd' }, '/'), ' to search every file.'),
    h('ul', null,
      h('li', null, n(F => F.sum.schema === 'harmonized-element/2.7') + ' on schema 2.7, ' + n(F => F.sum.schema === 'harmonized-element/2.5') + ' on 2.5'),
      h('li', null, n(F => F.sum.nBlocks === 0) + ' with no source block; ' + n(F => F.sum.nTargets === 0) + ' with no Layer 2 target'),
      h('li', null, gaps.length + ' with harmonized values that have no Layer 2 entry in some target (group the library by “Layer 2 gaps”)'),
      h('li', null, n(F => F.value === undefined) + ' not valid JSON; ' + n(F => F.roundTrip === false) + ' whose layout Save would rewrite')));
}
function afterRender() {
  if (S.pendingScroll) { const ps = S.pendingScroll; S.pendingScroll = null; doScroll(ps); }
  if (S.pendingOpen) {
    const key = S.pendingOpen; S.pendingOpen = null;
    const el = document.querySelector('#center [data-ed="' + CSS.escape(key) + '"]');
    if (el) { el.scrollIntoView({ block: 'nearest' }); el.click(); }
  }
  if (S.pendingMove) { const pm = S.pendingMove; S.pendingMove = null; moveEdit(pm.key, pm.dir); }
  if (S.pendingFocus) {
    const k = S.pendingFocus; S.pendingFocus = null;
    const el = document.querySelector('[data-focus="' + CSS.escape(k) + '"]');
    if (el) { el.focus(); if (el.setSelectionRange && typeof el.value === 'string') el.setSelectionRange(el.value.length, el.value.length); }
  }
}
function renderAll() {
  if (S.editing) { requestAnimationFrame(() => { if (!S.editing) renderAll(); }); return; }
  if (S.enumsDirty && (!S.enumsAt || Date.now() - S.enumsAt > 4000)) refreshEnums();
  renderTop(); renderLibrary(); renderCenter(); renderSide();
  afterRender();
}

/* ── keyboard + wiring ── */
function onKey(ev) {
  const t = ev.target;
  const tag = (t && t.tagName || '').toLowerCase();
  const inField = tag === 'input' || tag === 'textarea' || tag === 'select' || (t && t.isContentEditable);
  const mod = ev.ctrlKey || ev.metaKey;
  if (mod && ev.key.toLowerCase() === 's') {
    ev.preventDefault();
    if (S.editing) S.editing.commit();
    if (ev.shiftKey) saveAll(); else saveFile(curFile());
    return;
  }
  if (inField) return;
  if (mod && ev.key.toLowerCase() === 'z') { ev.preventDefault(); if (ev.shiftKey) redo(curFile()); else undo(curFile()); return; }
  if (mod && ev.key.toLowerCase() === 'y') { ev.preventDefault(); redo(curFile()); return; }
  if (mod || ev.altKey) return;
  if (ev.key === '/') { ev.preventDefault(); const s = $('#search'); s.focus(); s.select(); }
  else if (ev.key === 'j') { ev.preventDefault(); step(1); }
  else if (ev.key === 'k') { ev.preventDefault(); step(-1); }
  else if (ev.key === 'Escape') { closePop(); hideResults(); }
}
async function init() {
  document.addEventListener('keydown', onKey);
  document.addEventListener('mousedown', ev => {
    const pop = $('#pop');
    if (!pop.hidden && !pop.contains(ev.target) && !ev.target.closest('.modalbg')) closePop();
    if (!ev.target.closest('.searchwrap')) hideResults();
  }, true);
  window.addEventListener('beforeunload', ev => { if (anyDirty()) { ev.preventDefault(); ev.returnValue = ''; } });
  const search = $('#search');
  let timer = null;
  search.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(showResults, 140); });
  search.addEventListener('focus', () => { if (search.value.trim()) showResults(); });
  search.addEventListener('keydown', ev => {
    if (ev.key === 'ArrowDown') { ev.preventDefault(); moveResult(1); }
    else if (ev.key === 'ArrowUp') { ev.preventDefault(); moveResult(-1); }
    else if (ev.key === 'Enter') { ev.preventDefault(); clearTimeout(timer); if ($('#results').hidden) showResults(); chooseResult(_sr.hi); }
    else if (ev.key === 'Escape') { hideResults(); search.blur(); }
  });
  $('#openfolder').addEventListener('click', openFolder);
  $('#saveall').addEventListener('click', saveAll);
  $('#relay').addEventListener('click', async () => {
    const r = await Relay.health();
    if (r.status === 'ok') { toast('OMOP Hub relay is running at ' + r.base, 'ok'); return; }
    modal('OMOP Hub relay', h('div', null,
      h('p', null, r.status === 'nokey' ? 'The relay is running but found no OMOPHUB_API_KEY (environment variable, or a .env file next to the relay script).' : 'The relay is not running. OMOP Hub refuses requests made straight from a web page, so concept search goes through a small program on this computer.'),
      h('p', null, 'Start it in the folder that holds this page and your .env:'), h('pre', { class: 'mono' }, 'python cde_registry_browser_relay.py'),
      h('p', null, 'It listens on 127.0.0.1:8765 only. Relay address: ', (() => { const i = h('input', { type: 'text', value: LS.get('relay', '') || 'http://127.0.0.1:8765', style: 'width:260px' }); i.addEventListener('change', () => { LS.set('relay', i.value.trim()); Relay.health(); }); return i; })())),
    [{ label: 'Close', value: null }]);
  });
  const lf = $('#libfilter');
  lf.addEventListener('input', () => { S.lib.filter = lf.value; S.clCache = null; renderLibrary(); });
  lf.addEventListener('keydown', ev => { if (ev.key === 'Enter') { const ids = libraryOrder(); if (ids.length) openFile(ids[0]); } if (ev.key === 'Escape') { lf.value = ''; S.lib.filter = ''; renderLibrary(); lf.blur(); } });
  const lg = $('#libgroup');
  lg.replaceChildren(...Object.entries(GROUPS).map(([k, g]) => { const o = h('option', { value: k }, g[0]); if (k === S.lib.groupBy) o.selected = true; return o; }));
  lg.addEventListener('change', () => { S.lib.groupBy = lg.value; LS.set('groupBy', lg.value); renderLibrary(); });
  $('#libedited').addEventListener('change', ev => { S.lib.onlyEdited = ev.target.checked; renderLibrary(); });
  $('#dirinput').addEventListener('change', ev => { if (ev.target.files && ev.target.files.length) loadReadOnly(ev.target.files); ev.target.value = ''; });
  renderAll();
  Relay.health();
  const token = relayServedToken();
  if (token) { await loadStore(relayStore(location.origin, token)); return; }
  const hd = await kvGet('root');
  if (hd && hd.name) {
    S.remembered = hd.name;
    try { if ((await hd.queryPermission({ mode: 'readwrite' })) === 'granted') { await loadFolder(hd); return; } } catch (e) { /* ask on click */ }
    renderAll();
  }
}
window.CDEB = { S, C, get files() { return S.files; }, loadFolder, loadStore, stageTarget, openFile, saveFile, saveAll, scrollToPath, runSearch, undo, redo, revertAll, revertChange, setPath, fileById, currentText, renderNow: () => renderAll() };
init();
