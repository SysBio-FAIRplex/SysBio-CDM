/* ───────────── shared machinery: state, storage, folder access, relay, editors ───────────── */
const C = window.Core, K = C.K;
const LS = {
  get(k, d) { try { const v = localStorage.getItem('cdeb:' + k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem('cdeb:' + k, JSON.stringify(v)); } catch (e) { /* storage unavailable */ } }
};
function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  if (attrs) for (const k of Object.keys(attrs)) {
    const v = attrs[k];
    if (v === undefined || v === null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'style') el.style.cssText = v;
    else if (k === 'text') el.textContent = v;
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid === null || kid === undefined || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}
/* "1 entry", "2 entries" */
const pl = (n, one, many) => n + ' ' + (n === 1 ? one : (many || one + 's'));
/* append, skipping null / undefined / false */
function put(el, ...kids) { for (const k of kids.flat(Infinity)) if (k !== null && k !== undefined && k !== false) el.append(k); return el; }
const $ = (sel, root) => (root || document).querySelector(sel);
const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

const S = {
  files: new Map(), current: null, compare: null, tab: 'files',
  root: null, rootName: '', mode: 'none', loading: null,
  lib: { filter: '', groupBy: LS.get('groupBy', 'program'), onlyEdited: false, collapsed: {} },
  sheet: { l2View: 'target', collapsed: {}, raw: false, rawMode: 'edit', showAll: {}, filters: {}, extraCols: {}, scroll: {} },
  cl: Object.assign({ dims: ['labelWord'], labelMode: 'word', editDistance: 2, maxWordShare: 40, minWordLength: 3, jaccard: 0.6, minSize: 2, hideReviewed: false, onlyFiltered: false, extraCols: [] }, LS.get('clusterOpts', {})),
  clSel: null, clTicked: new Set(), clCache: null,
  enums: {}, enumsDirty: true,
  relay: { base: null, status: 'unknown' },
  editing: null, pendingMove: null, pendingFocus: null, pendingOpen: null, pendingScroll: null,
  exclude: LS.get('exclude', ['history', 'delete', 'superseded', '_backups', 'node_modules', '__pycache__'])
};
const fileById = id => S.files.get(id);
const curFile = () => (S.current ? S.files.get(S.current) : null);

/* ── IndexedDB: the remembered folder and earlier versions of every file this page overwrote ── */
let _db = null;
function idb() {
  if (_db) return Promise.resolve(_db);
  return new Promise((res, rej) => {
    const r = indexedDB.open('cde-registry-browser', 1);
    r.onupgradeneeded = () => {
      const db = r.result;
      db.createObjectStore('kv');
      const hs = db.createObjectStore('history', { keyPath: 'k', autoIncrement: true });
      hs.createIndex('file', 'file');
    };
    r.onsuccess = () => { _db = r.result; res(_db); };
    r.onerror = () => rej(r.error);
  });
}
async function kvGet(k) {
  try { const db = await idb(); return await new Promise(res => { const r = db.transaction('kv').objectStore('kv').get(k); r.onsuccess = () => res(r.result); r.onerror = () => res(undefined); }); }
  catch (e) { return undefined; }
}
async function kvSet(k, v) {
  try { const db = await idb(); return await new Promise(res => { const t = db.transaction('kv', 'readwrite'); t.objectStore('kv').put(v, k); t.oncomplete = () => res(true); t.onerror = () => res(false); }); }
  catch (e) { return false; }
}
async function histAdd(fileKey, text, why) {
  try { const db = await idb(); return await new Promise(res => { const t = db.transaction('history', 'readwrite'); t.objectStore('history').add({ file: fileKey, time: Date.now(), text, why: why || '' }); t.oncomplete = () => res(true); t.onerror = () => res(false); }); }
  catch (e) { return false; }
}
async function histList(fileKey) {
  try { const db = await idb(); return await new Promise(res => { const r = db.transaction('history').objectStore('history').index('file').getAll(fileKey); r.onsuccess = () => res((r.result || []).sort((a, b) => b.time - a.time)); r.onerror = () => res([]); }); }
  catch (e) { return []; }
}
const histKey = F => S.rootName + '/' + F.id;

/* ── OMOP Hub relay (OMOP Hub refuses requests made straight from a browser page) ── */
const OMOP_DOMAINS = new Set(['Measurement', 'Observation', 'Condition', 'Procedure', 'Specimen', 'Spec Anatomic Site', 'Meas Value', 'Unit', 'Drug', 'Device', 'Visit', 'Type Concept', 'Gender', 'Race', 'Ethnicity', 'Meas Value Operator', 'Metadata', 'Relationship', 'Route', 'Spec Disease Status', 'Note', 'Episode', 'Regimen', 'Provider', 'Language', 'Currency', 'Geography']);
const Relay = {
  candidates() {
    const list = [];
    const saved = LS.get('relay', '');
    if (saved) list.push(saved.replace(/\/+$/, ''));
    if (/^https?:$/.test(location.protocol)) list.push(location.origin);
    list.push('http://127.0.0.1:8765');
    return C.uniq(list);
  },
  async health() {
    for (const base of this.candidates()) {
      try {
        const ctl = new AbortController();
        const timer = setTimeout(() => ctl.abort(), 2500);
        const r = await fetch(base + '/health', { cache: 'no-store', signal: ctl.signal });
        clearTimeout(timer);
        if (r.ok) {
          const j = await r.json();
          if (j && j.service === 'cde-registry-browser-relay') { S.relay = { base, status: j.has_key ? 'ok' : 'nokey' }; renderTop(); return S.relay; }
        }
      } catch (e) { /* not this one */ }
    }
    S.relay = { base: null, status: 'down' };
    renderTop();
    return S.relay;
  },
  async call(path) {
    if (!S.relay.base) await this.health();
    if (!S.relay.base) { const e = new Error('The OMOP Hub relay is not running.'); e.code = 'relay-down'; throw e; }
    let r;
    try { r = await fetch(S.relay.base + '/omophub/' + path, { cache: 'no-store' }); }
    catch (e) { S.relay = { base: null, status: 'down' }; renderTop(); const er = new Error('The OMOP Hub relay stopped answering.'); er.code = 'relay-down'; throw er; }
    const j = await r.json().catch(() => null);
    if (!r.ok) {
      const msg = j && j.error ? (j.error.message || j.error.code || JSON.stringify(j.error)) : 'HTTP ' + r.status;
      const e = new Error(msg); e.status = r.status; throw e;
    }
    return j;
  },
  search(q, domains, standardOnly) {
    const p = new URLSearchParams({ query: q, page_size: '40' });
    const doms = (domains || []).filter(d => OMOP_DOMAINS.has(d));
    if (doms.length) p.set('domain_ids', doms.join(','));
    if (standardOnly) p.set('standard_concept', 'S');
    return this.call('search/concepts?' + p.toString());
  },
  get(id) { return this.call('concepts/' + encodeURIComponent(String(id).trim())); }
};

/* ── edits: every change goes through mutate(), which keeps an undo snapshot ── */
function snapshot(F) { return { v: C.clone(F.value), raw: new Map(F.meta.rawNums), ko: new Map(F.meta.keyOrder) }; }
function mutate(F, fn) {
  if (!F || F.value === undefined || F.error) return;
  F.undo.push(snapshot(F));
  if (F.undo.length > 300) F.undo.shift();
  F.redo = [];
  fn(F.value, F);
  afterChange(F);
}
function afterChange(F) {
  F.dirty = !C.deepEqual(F.value, F.base);
  F.sum = C.summarize(F.id, F.value);
  F.gaps = l2Gaps(F.value);
  F.leaves = null;
  F.saveState = F.dirty ? null : F.saveState;
  S.clCache = null;
  S.enumsDirty = true;
  scheduleRender();
}
function undo(F) {
  if (!F || !F.undo.length) return;
  F.redo.push(snapshot(F));
  const s = F.undo.pop();
  F.value = s.v; F.meta.rawNums = s.raw; F.meta.keyOrder = s.ko;
  afterChange(F);
}
function redo(F) {
  if (!F || !F.redo.length) return;
  F.undo.push(snapshot(F));
  const s = F.redo.pop();
  F.value = s.v; F.meta.rawNums = s.raw; F.meta.keyOrder = s.ko;
  afterChange(F);
}
function setPath(F, path, v, rawText) {
  mutate(F, root => {
    C.set(root, path, v);
    const key = C.pk(path);
    if (typeof v === 'number' && rawText && String(v) !== rawText) F.meta.rawNums.set(key, rawText); else F.meta.rawNums.delete(key);
  });
}
function delPath(F, path) {
  const parent = C.get(F.value, path.slice(0, -1));
  if (Array.isArray(parent)) return arrDelete(F, path.slice(0, -1), path[path.length - 1]);
  mutate(F, root => C.del(root, path));
}
/* Keep each number's exact spelling attached to the right list item when items move. */
function remapRaw(F, arrPath, mapFn) {
  const plen = arrPath.length;
  const head = JSON.stringify(arrPath).slice(0, -1);
  const out = new Map();
  for (const [k, v] of F.meta.rawNums) {
    if (k.startsWith(head) && (plen === 0 ? k.length > 2 : k[head.length] === ',')) {
      const p = JSON.parse(k);
      if (p.length > plen && typeof p[plen] === 'number') {
        for (const ni of mapFn(p[plen])) { const np = p.slice(); np[plen] = ni; out.set(JSON.stringify(np), v); }
        continue;
      }
    }
    out.set(k, v);
  }
  F.meta.rawNums = out;
}
function arrDelete(F, arrPath, i) {
  mutate(F, root => { C.get(root, arrPath).splice(i, 1); remapRaw(F, arrPath, j => (j < i ? [j] : j === i ? [] : [j - 1])); });
}
function arrInsert(F, arrPath, i, value) {
  mutate(F, root => { const a = C.get(root, arrPath); const at = Math.max(0, Math.min(i, a.length)); a.splice(at, 0, value); remapRaw(F, arrPath, j => (j < at ? [j] : [j + 1])); });
}
function arrDuplicate(F, arrPath, i) {
  mutate(F, root => { const a = C.get(root, arrPath); a.splice(i + 1, 0, C.clone(a[i])); remapRaw(F, arrPath, j => (j < i ? [j] : j === i ? [i, i + 1] : [j + 1])); });
}
function arrMove(F, arrPath, i, d) {
  const a = C.get(F.value, arrPath);
  const j = i + d;
  if (!Array.isArray(a) || j < 0 || j >= a.length) return;
  mutate(F, root => { const arr = C.get(root, arrPath); const t = arr[i]; arr[i] = arr[j]; arr[j] = t; remapRaw(F, arrPath, x => (x === i ? [j] : x === j ? [i] : [x])); });
}
function addKey(F, objPath, key, value) {
  mutate(F, root => { const o = C.get(root, objPath); if (C.isObj(o) && !(key in o)) o[key] = value; });
}
const isChanged = (F, path) => JSON.stringify(C.get(F.value, path)) !== JSON.stringify(C.get(F.base, path));

/* ── render scheduling ── */
let _queued = false;
function scheduleRender() {
  if (_queued) return;
  _queued = true;
  requestAnimationFrame(() => { _queued = false; renderAll(); });
}

/* ── toast + modal + popover ── */
function toast(msg, kind) {
  const t = h('div', { class: 'toast ' + (kind || '') }, msg);
  $('#toast').append(t);
  setTimeout(() => t.remove(), kind === 'err' ? 7000 : 3200);
}
function modal(title, body, buttons) {
  return new Promise(res => {
    const bg = h('div', { class: 'modalbg' });
    const close = v => { bg.remove(); document.removeEventListener('keydown', onKey, true); res(v); };
    const onKey = ev => { if (ev.key === 'Escape') { ev.stopPropagation(); close(null); } };
    const acts = h('div', { class: 'acts' }, buttons.map(b => h('button', { class: 'btn' + (b.pri ? ' pri' : ''), onclick: () => close(typeof b.value === 'function' ? b.value() : b.value) }, b.label)));
    bg.append(h('div', { class: 'modal' }, h('h3', null, title), body, acts));
    bg.addEventListener('mousedown', ev => { if (ev.target === bg) close(null); });
    document.addEventListener('keydown', onKey, true);
    document.body.append(bg);
    const f = bg.querySelector('textarea,input');
    if (f) f.focus();
  });
}
function openPop(anchor, content) {
  const pop = $('#pop');
  pop.replaceChildren(content);
  pop.hidden = false;
  const r = anchor.getBoundingClientRect();
  const w = Math.min(560, window.innerWidth - 20);
  let left = Math.min(Math.max(10, r.left), window.innerWidth - w - 10);
  pop.style.left = left + 'px';
  pop.style.top = '0px';
  const ph = pop.offsetHeight;
  let top = r.bottom + 6;
  if (top + ph > window.innerHeight - 10) top = Math.max(10, r.top - ph - 6);
  pop.style.top = top + 'px';
}
function closePop() { const pop = $('#pop'); if (pop && !pop.hidden) { pop.hidden = true; pop.replaceChildren(); } }

/* ── editors ── */
const edKey = (F, path) => F.id + '|' + C.pk(path);
function typeLabel(v, exists) {
  if (!exists) return 'not in the file';
  if (v === null) return 'null';
  if (Array.isArray(v)) return 'list';
  return typeof v;
}
function datalistFor(key, extra) {
  const id = 'dl-' + key.replace(/[^a-z0-9_]/gi, '_') + (extra ? '-x' : '');
  let dl = document.getElementById(id);
  if (!dl) { dl = h('datalist', { id }); document.body.append(dl); }
  const vals = C.uniq((S.enums[key] || K.ENUMS[key] || []).concat(extra || []));
  dl.replaceChildren(...vals.map(v => h('option', { value: v })));
  return id;
}
/* A single value: click to edit, Enter saves, Tab moves to the next field, Esc cancels. */
function scalar(F, path, opt) {
  opt = opt || {};
  const exists = C.has(F.value, path);
  const v = C.get(F.value, path);
  if (typeof v === 'boolean' || (opt.kind === 'bool' && (v === undefined || v === null))) return boolToggle(F, path, v, exists, opt);
  let text, cls = 'v';
  if (!exists) { text = opt.absent || '—'; cls += ' empty'; }
  else if (v === null) { text = 'null'; cls += ' null'; }
  else if (v === '') { text = '""'; cls += ' empty'; }
  else if (typeof v === 'number') { const raw = F.meta.rawNums.get(C.pk(path)); text = raw && Number(raw) === v ? raw : String(v); cls += ' num'; }
  else if (typeof v === 'string') { text = v; if (opt.prose) cls += ' txt'; }
  else { text = C.describe(v, 120); }
  if (opt.display && exists && v !== null && v !== '') text = opt.display(v, text);
  if (opt.cls) cls += ' ' + opt.cls;
  if (opt.bad && exists && opt.bad(v)) cls += ' bad';
  if (isChanged(F, path)) cls += ' changed';
  const el = h('span', { class: cls, 'data-ed': edKey(F, path), title: (opt.title ? opt.title + '\n' : '') + typeLabel(v, exists) + (opt.readonly ? '' : ' · click to edit') });
  el.textContent = text;
  if (opt.readonly) { el.classList.add('ro'); return el; }
  if (v !== null && typeof v === 'object') { el.addEventListener('click', ev => { ev.stopPropagation(); jsonModal(F, path); }); return el; }
  el.addEventListener('click', ev => { ev.stopPropagation(); startEdit(el, F, path, opt); });
  return el;
}
function boolToggle(F, path, v, exists, opt) {
  const b = h('button', { class: 'tog ' + (v === true ? 't' : 'f') + (isChanged(F, path) ? ' changed' : ''), 'data-ed': edKey(F, path), title: (opt && opt.title ? opt.title + '\n' : '') + 'click to switch' }, exists ? String(v) : 'not set');
  b.addEventListener('click', ev => { ev.stopPropagation(); setPath(F, path, !(v === true)); });
  return b;
}
const NUM_RE = /^-?(0|[1-9]\d*)(\.\d+)?([eE][+-]?\d+)?$/;
function startEdit(el, F, path, opt) {
  if (S.editing) S.editing.commit();
  const exists = C.has(F.value, path);
  const v = C.get(F.value, path);
  let type = typeof v === 'number' ? 'number' : v === null ? (opt.newType || 'null') : 'text';
  if (!exists) type = opt.newType || 'text';
  if (S.pendingOpenType) { type = S.pendingOpenType; S.pendingOpenType = null; }
  const raw = typeof v === 'number' ? (F.meta.rawNums.get(C.pk(path)) || String(v)) : (v === null || v === undefined ? '' : String(v));
  const multiline = !!opt.prose || raw.length > 70 || raw.includes('\n');
  const input = multiline ? h('textarea', { rows: Math.min(12, Math.max(2, Math.ceil(raw.length / 85) + 1)) }) : h('input', { type: 'text', spellcheck: 'false' });
  input.value = raw;
  if (opt.enumKey) input.setAttribute('list', datalistFor(opt.enumKey, opt.suggest));
  else if (opt.suggest) input.setAttribute('list', datalistFor('s-' + edKey(F, path), opt.suggest));
  const sel = h('select', { title: 'Type written to the file' }, ['text', 'number', 'null'].map(t => { const o = h('option', { value: t }, t); if (t === type) o.selected = true; return o; }));
  const err = h('span', { class: 'ederr' });
  const wrap = h('span', { class: 'edwrap', 'data-ed': edKey(F, path) }, input, sel, err);
  el.replaceWith(wrap);
  input.focus();
  if (!multiline) input.select();
  let done = false;
  function finish(commit, move) {
    if (done) return true;
    if (commit) {
      const t = sel.value;
      let nv, rawTxt;
      if (t === 'null') nv = null;
      else if (t === 'number') {
        const s = input.value.trim();
        if (!NUM_RE.test(s)) { err.textContent = 'not a number — pick “text” to keep it as text'; input.focus(); return false; }
        nv = Number(s); rawTxt = s;
      } else nv = input.value;
      done = true;
      S.editing = null;
      const same = exists && nv === v && (typeof nv !== 'number' || rawTxt === raw);
      if (same) {
        const fresh = scalar(F, path, opt);
        wrap.replaceWith(fresh);
        if (move) moveEdit(fresh.getAttribute('data-ed'), move);
        return true;
      }
      S.pendingMove = move ? { key: edKey(F, path), dir: move } : null;
      setPath(F, path, nv, rawTxt);
      if (wrap.isConnected) wrap.replaceWith(scalar(F, path, opt));
      return true;
    }
    done = true;
    S.editing = null;
    wrap.replaceWith(scalar(F, path, opt));
    return true;
  }
  S.editing = { commit: () => finish(true), cancel: () => finish(false) };
  input.addEventListener('keydown', ev => {
    ev.stopPropagation();
    if (ev.key === 'Escape') { ev.preventDefault(); finish(false); }
    else if (ev.key === 'Enter' && (!multiline || ev.ctrlKey || ev.metaKey)) { ev.preventDefault(); finish(true); }
    else if (ev.key === 'Tab') { ev.preventDefault(); finish(true, ev.shiftKey ? -1 : 1); }
  });
  const onBlur = () => setTimeout(() => { if (!done && document.activeElement !== input && document.activeElement !== sel) finish(true); }, 150);
  input.addEventListener('blur', onBlur);
  sel.addEventListener('blur', onBlur);
  sel.addEventListener('change', () => { err.textContent = ''; input.focus(); });
}
/* Tab / Shift+Tab: open the next or previous editable value on the page. */
function moveEdit(key, dir) {
  const all = $$('#center [data-ed]').filter(e => e.offsetParent !== null);
  const i = all.findIndex(e => e.getAttribute('data-ed') === key);
  const nx = all[i + dir];
  if (nx) { nx.scrollIntoView({ block: 'nearest' }); nx.click(); }
}
/* A list of plain values as chips. */
function chips(F, path, opt) {
  opt = opt || {};
  const arr = C.get(F.value, path);
  const key = edKey(F, path);
  const wrap = h('div', { class: 'chips', 'data-path': key });
  if (!Array.isArray(arr)) { wrap.append(scalar(F, path, opt)); return wrap; }
  const q = (S.sheet.filters[key] || '').toLowerCase();
  if (arr.length > 30) {
    const f = h('input', { class: 'chipadd', placeholder: 'filter ' + arr.length + '…', value: S.sheet.filters[key] || '' });
    f.addEventListener('input', () => { S.sheet.filters[key] = f.value; S.pendingFocus = 'filter:' + key; scheduleRender(); });
    f.setAttribute('data-focus', 'filter:' + key);
    wrap.append(f);
  }
  const limit = S.sheet.showAll[key] ? Infinity : 300;
  let shown = 0, hidden = 0;
  arr.forEach((v, i) => {
    if (q && !String(v).toLowerCase().includes(q)) return;
    if (shown >= limit) { hidden++; return; }
    shown++;
    wrap.append(h('span', { class: 'chip' + (opt.flag && opt.flag(v) ? ' bad' : ''), title: opt.flag && opt.flag(v) ? opt.flagText || '' : '' },
      v !== null && typeof v === 'object' ? scalar(F, path.concat(i)) : scalar(F, path.concat(i), { enumKey: opt.enumKey, suggest: opt.suggest }),
      h('button', { class: 'x', title: 'remove', onclick: ev => { ev.stopPropagation(); arrDelete(F, path, i); } }, '×')));
  });
  if (hidden) wrap.append(h('button', { class: 'linkbtn', onclick: () => { S.sheet.showAll[key] = true; scheduleRender(); } }, 'show ' + hidden + ' more'));
  const add = h('input', { class: 'chipadd', placeholder: opt.addText || '+ add', 'data-focus': 'add:' + key });
  if (opt.enumKey) add.setAttribute('list', datalistFor(opt.enumKey, opt.suggest));
  else if (opt.suggest) add.setAttribute('list', datalistFor('s-' + key, opt.suggest));
  add.addEventListener('keydown', ev => {
    ev.stopPropagation();
    if (ev.key === 'Enter' && add.value.trim() !== '') {
      ev.preventDefault();
      const s = add.value.trim();
      const val = opt.numbers && NUM_RE.test(s) ? Number(s) : s;
      S.pendingFocus = 'add:' + key;
      arrInsert(F, path, arr.length, val);
    }
  });
  wrap.append(add);
  return wrap;
}
/* A concept object {id, name, …}: a chip that opens the concept editor and the OMOP Hub search. */
function conceptChip(F, path, ctx) {
  ctx = ctx || {};
  const v = C.get(F.value, path);
  const exists = C.has(F.value, path);
  if (!C.isObj(v)) {
    const b = h('button', { class: 'concept none' + (isChanged(F, path) ? ' changed' : ''), 'data-ed': edKey(F, path) }, (exists && v === null ? 'null · ' : '') + '+ choose a concept');
    b.addEventListener('click', ev => { ev.stopPropagation(); openConceptPop(F, path, ctx, b); });
    return b;
  }
  const c = C.conceptOf(v);
  const idTxt = c.id === null || c.id === undefined || c.id === '' ? 'no id' : String(c.id);
  const b = h('button', { class: 'concept' + (isChanged(F, path) ? ' changed' : ''), 'data-ed': edKey(F, path), title: Object.entries(v).map(([k, x]) => k + ': ' + C.describe(x, 200)).join('\n') + '\n\nclick to edit or search OMOP Hub' },
    h('span', { class: 'cn' }, c.name || '(no name)'),
    h('span', { class: 'ci' }, idTxt + (c.domain ? ' · ' + c.domain : '') + (c.vocabulary ? ' · ' + c.vocabulary : '')));
  b.addEventListener('click', ev => { ev.stopPropagation(); openConceptPop(F, path, ctx, b); });
  return b;
}
function conceptValueFromHit(cur, hit, ctx) {
  const out = C.isObj(cur) ? C.clone(cur) : {};
  const idKey = 'concept_id' in out && !('id' in out) ? 'concept_id' : 'id';
  const nameKey = 'concept_name' in out && !('name' in out) ? 'concept_name' : 'name';
  out[idKey] = hit.concept_id;
  out[nameKey] = hit.concept_name;
  if ('domain' in out || ctx.wantDomain) out.domain = hit.domain_id;
  if ('vocabulary_id' in out) out.vocabulary_id = hit.vocabulary_id;
  if ('vocabulary' in out) out.vocabulary = hit.vocabulary_id;
  if ('concept_code' in out) out.concept_code = hit.concept_code;
  return out;
}
function openConceptPop(F, path, ctx, anchor) {
  const pickOnly = typeof ctx.onPick === 'function';
  const cur = pickOnly ? null : C.get(F.value, path);
  const draft = C.isObj(cur) ? C.clone(cur) : { id: null, name: null };
  const fields = pickOnly ? [] : Object.keys(draft);
  const pick = (hit, label) => { closePop(); if (pickOnly) ctx.onPick(hit); else setPath(F, path, conceptValueFromHit(readFields(), hit, ctx)); toast((label || 'Concept set: ') + hit.concept_name + ' (' + hit.concept_id + ')', 'ok'); };
  const allowed = ctx.domains || C.allowedDomains(ctx.column) || null;
  const doms = new Set(allowed || []);
  const box = h('div', null);
  const title = h('h4', null, (ctx.title || C.pathStr(path)) + (ctx.column ? ' → ' + ctx.column : ''));
  const info = h('div', { class: 'sub2' }, allowed ? 'Domains allowed in ' + ctx.column + ': ' + allowed.join(' / ') : 'Any domain.');
  const grid = h('div', { class: 'grid2' });
  const inputs = {};
  for (const f of fields) {
    const val = draft[f];
    const inp = h('input', { type: 'text', value: val === null || val === undefined ? '' : String(val), spellcheck: 'false' });
    inputs[f] = inp;
    grid.append(h('span', { class: 'muted' }, f), inp);
  }
  const lookupOut = h('div', { class: 'sub2' });
  function readFields() {
    const out = {};
    for (const f of fields) {
      const s = inputs[f].value.trim();
      if (s === '') out[f] = draft[f] === undefined ? null : (typeof draft[f] === 'string' ? '' : null);
      else if ((f === 'id' || f === 'concept_id') && /^-?\d+$/.test(s)) out[f] = Number(s);
      else out[f] = typeof draft[f] === 'number' && NUM_RE.test(s) ? Number(s) : s;
    }
    for (const k of Object.keys(draft)) if (!(k in out)) out[k] = draft[k];
    return out;
  }
  const acts = h('div', { class: 'sideacts' },
    h('button', { class: 'btn pri', onclick: () => { closePop(); setPath(F, path, readFields()); } }, 'Apply fields'),
    h('button', { class: 'btn', onclick: async () => {
      const idf = 'id' in inputs ? 'id' : 'concept_id';
      const id = inputs[idf] ? inputs[idf].value.trim() : '';
      if (!/^\d+$/.test(id)) { lookupOut.textContent = 'Enter a numeric concept id first.'; return; }
      lookupOut.textContent = 'Looking up ' + id + ' …';
      try {
        const d = conceptData(await Relay.get(id));
        if (!d) { lookupOut.textContent = 'No concept returned.'; return; }
        lookupOut.replaceChildren(
          h('div', null, h('b', null, d.concept_name), ' · ', d.domain_id, ' · ', d.vocabulary_id, ' · ', d.concept_code, ' · ', d.standard_concept === 'S' ? 'Standard' : 'non-standard (' + (d.standard_concept || 'none') + ')', d.invalid_reason ? ' · invalid: ' + d.invalid_reason : ''),
          allowed && !allowed.includes(d.domain_id) ? h('div', { class: 'flagtxt' }, 'domain ' + d.domain_id + ' is not one of ' + allowed.join(' / ')) : null,
          h('button', { class: 'btn small', onclick: () => pick(d, 'Concept set from OMOP Hub: ') }, 'Use these values'));
      } catch (e) { lookupOut.textContent = e.status === 404 ? 'OMOP Hub does not hold concept ' + id + '.' : relayMessage(e); }
    } }, 'Look up this id'),
    h('button', { class: 'btn', onclick: () => { closePop(); setPath(F, path, null); } }, 'Set to null'),
    h('button', { class: 'btn', onclick: closePop }, 'Close'));
  const q = h('input', { type: 'text', placeholder: 'Search OMOP Hub by name, code or id …', value: draft.name || draft.concept_name || '' });
  const std = h('input', { type: 'checkbox' }); std.checked = true;
  const domBox = h('div', { class: 'doms' });
  const domList = C.uniq((allowed || []).concat(['Measurement', 'Observation', 'Condition', 'Procedure', 'Specimen', 'Spec Anatomic Site', 'Meas Value', 'Unit']));
  function drawDoms() {
    domBox.replaceChildren(...domList.map(d => h('label', { class: doms.has(d) ? 'on' : '', onclick: () => { doms.has(d) ? doms.delete(d) : doms.add(d); drawDoms(); } }, d)),
      h('span', { class: 'muted' }, doms.size ? '' : '(all domains)'));
  }
  drawDoms();
  const results = h('div', { style: 'display:flex;flex-direction:column;gap:4px' });
  async function run() {
    const s = q.value.trim();
    if (s.length < 3 && !/^\d+$/.test(s)) { results.replaceChildren(h('div', { class: 'sub2' }, 'Type at least 3 characters.')); return; }
    results.replaceChildren(h('div', { class: 'sub2' }, 'Searching OMOP Hub …'));
    try {
      let hits;
      if (/^\d+$/.test(s)) { const d = conceptData(await Relay.get(s)); hits = d ? [d] : []; }
      else hits = hitList(await Relay.search(s, Array.from(doms), std.checked));
      if (std.checked) hits = hits.filter(x => x.standard_concept === 'S' || /^\d+$/.test(s));
      if (doms.size) { const ok = hits.filter(x => doms.has(x.domain_id)); if (ok.length || !/^\d+$/.test(s)) hits = ok; }
      if (!hits.length) { results.replaceChildren(h('div', { class: 'sub2' }, 'No concepts found.')); return; }
      results.replaceChildren(...hits.map(x => h('div', { class: 'hit' + (x.standard_concept === 'S' ? '' : ' nonstd'), onclick: () => pick(x) },
        h('div', { class: 'hn' }, x.concept_name),
        h('div', { class: 'hm' }, [x.concept_id, x.domain_id, x.vocabulary_id, x.concept_class_id, x.concept_code, x.standard_concept === 'S' ? 'Standard' : 'non-standard'].filter(Boolean).join(' · ')),
        allowed && !allowed.includes(x.domain_id) ? h('div', { class: 'flagtxt' }, 'domain not allowed in ' + ctx.column) : null)));
    } catch (e) { results.replaceChildren(h('div', { class: 'flagtxt' }, relayMessage(e))); }
  }
  q.addEventListener('keydown', ev => { ev.stopPropagation(); if (ev.key === 'Enter') { ev.preventDefault(); run(); } if (ev.key === 'Escape') closePop(); });
  if (pickOnly) box.append(title, info);
  else box.append(title, info, grid, acts, lookupOut);
  box.append(
    h('div', { class: 'subhead' }, 'Search OMOP Hub'),
    h('div', { class: 'srch' }, q, h('button', { class: 'btn', onclick: run }, 'Search')),
    domBox, h('label', { class: 'sub2' }, std, ' Standard concepts only'), results);
  openPop(anchor, box);
  q.focus();
  q.select();
}
/* OMOP Hub answers { data: [...] } for a search and { data: {...} } for one concept; accept close variants. */
function hitList(j) {
  const d = j && j.data !== undefined ? j.data : j;
  const arr = Array.isArray(d) ? d : d && Array.isArray(d.concepts) ? d.concepts : d && Array.isArray(d.results) ? d.results : d && Array.isArray(d.items) ? d.items : [];
  return arr.filter(x => x && typeof x === 'object' && x.concept_id !== undefined);
}
function conceptData(j) {
  const d = j && j.data !== undefined ? j.data : j;
  if (d && typeof d === 'object' && !Array.isArray(d) && d.concept_id !== undefined) return d;
  if (d && d.concept && d.concept.concept_id !== undefined) return d.concept;
  return null;
}
function relayMessage(e) {
  if (e && e.code === 'relay-down') return 'The OMOP Hub relay is not running. Start it from your CDE_REGISTRY folder with:  python cde_registry_browser_relay.py   — then try again.';
  return 'OMOP Hub: ' + (e && e.message ? e.message : String(e));
}
/* Edit any value as JSON (objects, odd shapes). */
function jsonModal(F, path, title) {
  const v = C.get(F.value, path);
  const ta = h('textarea', { spellcheck: 'false' });
  ta.value = JSON.stringify(v === undefined ? null : v, null, 2);
  const err = h('div', { class: 'flagtxt' });
  return modal(title || 'Edit ' + (C.pathLabel(F.value, path) || 'value') + ' as JSON', h('div', null, ta, err), [
    { label: 'Cancel', value: null },
    { label: 'Apply', pri: true, value: () => ta.value }
  ]).then(text => {
    if (text === null || text === undefined) return;
    let parsed;
    try { parsed = C.parseJSONText(text); } catch (e) { toast('Not valid JSON: ' + e.message, 'err'); return; }
    mutate(F, root => {
      if (path.length) C.set(root, path, parsed.value); else F.value = parsed.value;
      const head = JSON.stringify(path).slice(0, -1);
      for (const k of Array.from(F.meta.rawNums.keys())) if (path.length === 0 || k === JSON.stringify(path) || k.startsWith(head + ',')) F.meta.rawNums.delete(k);
      for (const [k, raw] of parsed.meta.rawNums) F.meta.rawNums.set(JSON.stringify(path.concat(JSON.parse(k))), raw);
    });
  });
}
