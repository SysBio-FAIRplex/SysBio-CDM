/* ───────────── the spec sheet: element, source blocks, Layer 1 ───────────── */
const hasOwn = (o, k) => C.isObj(o) && Object.prototype.hasOwnProperty.call(o, k);
const PROSE = new Set(['definition', 'description', 'status_note', 'note', 'src_definition', 'evidence', 'reason']);
const TABLE_FIELD = { measurement: 'measurement_concept_id', observation: 'observation_concept_id', condition_occurrence: 'condition_concept_id', procedure_occurrence: 'procedure_concept_id', specimen: 'specimen_concept_id', drug_exposure: 'drug_concept_id', device_exposure: 'device_concept_id', visit_occurrence: 'visit_concept_id' };
const ELEMENT_ORDER = ['schema_version'].concat(K.ELEMENT_FIELDS.map(f => f[0]).slice(0, 9), ['one_per', 'loading_grain', 'unit'], K.ELEMENT_FIELDS.map(f => f[0]).slice(9), ['links', 'policies', 'status_note']);
const BLOCK_ORDER = K.BLOCK_FIELDS.map(f => f[0]);
const L1_ORDER = K.L1_FIELDS.map(f => f[0]);
const TARGET_ORDER = K.TARGET_FIELDS.map(f => f[0]);

function q(text) { return text ? h('span', { class: 'q', title: text }, '?') : null; }
function isCollapsed(F, path) { return !!S.sheet.collapsed[edKey(F, path)]; }
function toggleCollapsed(F, path) { const k = edKey(F, path); if (S.sheet.collapsed[k]) delete S.sheet.collapsed[k]; else S.sheet.collapsed[k] = true; scheduleRender(); }

/* Insert a key where the template puts it, so the saved file reads in template order. */
function addKeyOrdered(F, objPath, key, value, order) {
  mutate(F, root => {
    const o = C.get(root, objPath);
    if (!C.isObj(o) || hasOwn(o, key)) return;
    const keys = Object.keys(o);
    let at = keys.length;
    const oi = order ? order.indexOf(key) : -1;
    if (oi >= 0) {
      let best = -1;
      keys.forEach((k, i) => { const ki = order.indexOf(k); if (ki >= 0 && ki < oi) best = i; });
      if (best >= 0) at = best + 1;
      else { const first = keys.findIndex(k => order.indexOf(k) > oi); at = first >= 0 ? first : keys.length; }
    }
    const entries = Object.entries(o);
    entries.splice(at, 0, [key, value]);
    for (const k of keys) delete o[k];
    for (const [k, v] of entries) o[k] = v;
  });
}
function addField(F, objPath, key, dflt, order) {
  const v = typeof dflt === 'function' ? dflt(F) : (dflt === undefined ? '' : C.clone(dflt));
  if (v === null || typeof v !== 'object') S.pendingOpen = edKey(F, objPath.concat(key));
  addKeyOrdered(F, objPath, key, v, order);
}

/* ── rows, notes, absent fields ── */
function noteEl(F, objPath, key) {
  const o = C.get(F.value, objPath);
  const nk = '_' + key;
  if (!hasOwn(o, nk)) return null;
  return h('div', { class: 'note' },
    h('span', { class: 'nk' }, nk, ' ', h('button', { class: 'linkbtn warn', title: 'remove this note', onclick: () => delPath(F, objPath.concat(nk)) }, '×')),
    typeof o[nk] === 'string' ? scalar(F, objPath.concat(nk), { prose: true }) : nodeEditor(F, objPath.concat(nk)));
}
function fieldRow(F, objPath, key, helpText, valueEl, opt) {
  opt = opt || {};
  const p = objPath.concat(key);
  const present = hasOwn(C.get(F.value, objPath), key);
  return h('div', { class: 'row', 'data-path': edKey(F, p) },
    h('div', { class: 'k' }, opt.title || key, q(helpText),
      present && !opt.noDelete ? h('button', { class: 'linkbtn warn kdel', title: 'remove ' + key + ' from the file (Ctrl+Z undoes)', onclick: () => delPath(F, p) }, '×') : null),
    h('div', { class: 'val' }, valueEl, opt.after || null, noteEl(F, objPath, key)));
}
function absentLine(F, objPath, fields, defaults, order, text) {
  const o = C.get(F.value, objPath);
  if (!C.isObj(o)) return null;
  const missing = fields.filter(([k]) => !hasOwn(o, k));
  if (!missing.length) return null;
  return h('div', { class: 'absent' }, h('span', { class: 'muted' }, text || 'Not in the file:'),
    missing.map(([k, hp]) => h('button', { class: 'addf', title: (hp || '') + '\n\nclick to add it', onclick: () => addField(F, objPath, k, defaults ? defaults[k] : '', order) }, '+ ' + k)));
}
/* Keys of an object that no known list covers, edited as found. */
function otherRows(F, objPath, knownSet, title) {
  const o = C.get(F.value, objPath);
  if (!C.isObj(o)) return null;
  const keys = Object.keys(o).filter(k => !knownSet.has(k) && !(k.startsWith('_') && hasOwn(o, k.slice(1)) && (knownSet.has(k.slice(1)) || true)));
  const stray = keys.filter(k => k.startsWith('_'));
  const plain = keys.filter(k => !k.startsWith('_'));
  if (!plain.length && !stray.length) return null;
  return h('div', { class: 'others' },
    h('div', { class: 'subhead' }, title || 'Other fields in the file', h('span', { class: 'sub2' }, 'not in the 2.7 template; shown and edited as found')),
    plain.map(k => fieldRow(F, objPath, k, K.OLDER_ELEMENT_FIELDS[k] || '', nodeEditor(F, objPath.concat(k)))),
    stray.map(k => fieldRow(F, objPath, k, 'A note whose field is not in this object.', typeof o[k] === 'string' ? scalar(F, objPath.concat(k), { prose: true }) : nodeEditor(F, objPath.concat(k)))));
}
function addKeyInput(F, objPath) {
  const inp = h('input', { class: 'chipadd', placeholder: '+ field', title: 'Type a field name and press Enter', 'data-focus': 'addkey:' + edKey(F, objPath) });
  inp.addEventListener('keydown', ev => {
    ev.stopPropagation();
    if (ev.key === 'Enter' && inp.value.trim()) {
      ev.preventDefault();
      const k = inp.value.trim();
      const o = C.get(F.value, objPath);
      if (hasOwn(o, k)) { toast('“' + k + '” is already there.', 'err'); return; }
      S.pendingOpen = edKey(F, objPath.concat(k));
      addKey(F, objPath, k, '');
    }
  });
  return inp;
}

/* ── generic editor for any value, used for fields the sheet has no special view for ── */
function nodeEditor(F, path, opt) {
  opt = opt || {};
  const v = C.get(F.value, path);
  const last = path[path.length - 1];
  const key = typeof last === 'number' ? path[path.length - 2] : last;
  if (v === null || typeof v !== 'object') {
    return scalar(F, path, { enumKey: (K.ENUMS[key] || S.enums[key]) ? key : undefined, prose: PROSE.has(key) || (typeof v === 'string' && v.length > 90) });
  }
  if (C.isConcept(v)) return conceptChip(F, path, { column: typeof key === 'string' ? key : undefined });
  if (Array.isArray(v)) {
    if (v.every(x => x === null || typeof x !== 'object')) return chips(F, path, { enumKey: (K.ENUMS[key] || S.enums[key]) ? key : undefined, numbers: v.length > 0 && v.every(x => typeof x === 'number') });
    if (v.every(x => C.isObj(x))) return objTable(F, path, null, {});
    return h('div', { class: 'nest' }, v.map((x, i) => h('div', { class: 'nrow' }, h('span', { class: 'muted mono' }, '[' + i + ']'), nodeEditor(F, path.concat(i)), rowActs(F, path, i, {}))),
      h('div', { class: 'tablebar' }, h('button', { class: 'linkbtn', onclick: () => jsonModal(F, path) }, 'edit as JSON')));
  }
  const box = h('div', { class: 'nest' });
  for (const k of Object.keys(v)) {
    if (k.startsWith('_') && hasOwn(v, k.slice(1))) continue;
    box.append(fieldRow(F, path, k, '', nodeEditor(F, path.concat(k))));
  }
  box.append(h('div', { class: 'tablebar' }, addKeyInput(F, path), h('button', { class: 'linkbtn', onclick: () => jsonModal(F, path) }, 'edit as JSON')));
  return box;
}
/* A small object shown as inline fields (dictionary, layout, input …). */
function subFields(F, path, fields, opt) {
  opt = opt || {};
  const o = C.get(F.value, path);
  if (!C.isObj(o)) return nodeEditor(F, path);
  const box = h('div', { class: 'subf' });
  const known = new Set(fields.map(f => f[0]));
  for (const [k, hp, kind] of fields) {
    if (!hasOwn(o, k)) continue;
    box.append(h('span', { class: 'sf', 'data-path': edKey(F, path.concat(k)) }, h('span', { class: 'sk', title: hp || '' }, k), ' ',
      kind === 'chips' ? chips(F, path.concat(k), {}) : kind === 'concept' ? conceptChip(F, path.concat(k), { column: k }) : Array.isArray(o[k]) ? chips(F, path.concat(k), {}) : scalar(F, path.concat(k), { enumKey: (K.ENUMS[k] || S.enums[k]) ? k : undefined, newType: kind === 'number' ? 'number' : undefined }),
      h('button', { class: 'linkbtn warn kdel', title: 'remove ' + k, onclick: () => delPath(F, path.concat(k)) }, '×'),
      noteEl(F, path, k)));
  }
  for (const k of Object.keys(o)) {
    if (known.has(k) || (opt.hide && opt.hide.includes(k)) || (k.startsWith('_') && hasOwn(o, k.slice(1)))) continue;
    box.append(h('span', { class: 'sf' }, h('span', { class: 'sk' }, k), ' ', nodeEditor(F, path.concat(k)), h('button', { class: 'linkbtn warn kdel', title: 'remove ' + k, onclick: () => delPath(F, path.concat(k)) }, '×')));
  }
  const miss = fields.filter(([k]) => !hasOwn(o, k));
  if (miss.length) box.append(h('span', { class: 'absent inl' }, miss.map(([k, hp, kind]) => h('button', { class: 'addf', title: (hp || '') + '\n\nclick to add it', onclick: () => addField(F, path, k, kind === 'chips' ? [] : kind === 'number' ? null : kind === 'concept' ? { id: null, name: '' } : '', fields.map(f => f[0])) }, '+ ' + k))));
  if (opt.allowNew) box.append(addKeyInput(F, path));
  return box;
}

/* ── list tables ── */
function rowActs(F, arrPath, i, opt) {
  const arr = C.get(F.value, arrPath);
  return h('span', { class: 'rowacts' },
    opt.noMove ? null : h('button', { title: 'move up', disabled: i === 0 ? true : null, onclick: ev => { ev.stopPropagation(); arrMove(F, arrPath, i, -1); } }, '↑'),
    opt.noMove ? null : h('button', { title: 'move down', disabled: i >= arr.length - 1 ? true : null, onclick: ev => { ev.stopPropagation(); arrMove(F, arrPath, i, 1); } }, '↓'),
    h('button', { title: 'duplicate', onclick: ev => { ev.stopPropagation(); arrDuplicate(F, arrPath, i); } }, '⧉'),
    h('button', { class: 'del', title: 'delete (Ctrl+Z undoes)', onclick: ev => { ev.stopPropagation(); arrDelete(F, arrPath, i); } }, '✕'));
}
function blankLike(sample, cols) {
  const out = {};
  if (C.isObj(sample)) {
    for (const [k, v] of Object.entries(sample)) {
      if (k.startsWith('_')) continue;
      out[k] = typeof v === 'string' ? '' : typeof v === 'boolean' ? false : Array.isArray(v) ? [] : C.isConcept(v) ? { id: null, name: '' } : null;
    }
    return out;
  }
  for (const c of cols) out[c] = null;
  if (cols.length) out[cols[0]] = '';
  return out;
}
function intervalText(v) {
  if (!C.isObj(v)) return C.describe(v);
  const lo = v.low === null || v.low === undefined ? '−∞' : String(v.low);
  const hi = v.high === null || v.high === undefined ? '∞' : String(v.high);
  return (v.low_inclusive && lo !== '−∞' ? '[' : '(') + lo + ', ' + hi + (v.high_inclusive && hi !== '∞' ? ']' : ')');
}
function objPop(F, path, fields, anchor, title) {
  const cur = C.get(F.value, path);
  const o = C.isObj(cur) ? cur : {};
  const keys = C.uniq(fields.concat(Object.keys(o)));
  const ins = {};
  const grid = h('div', { class: 'grid2' });
  for (const k of keys) {
    const v = o[k];
    let inp;
    if (typeof v === 'boolean' || /_inclusive$/.test(k)) { inp = h('input', { type: 'checkbox' }); inp.checked = v === true; }
    else { inp = h('input', { type: 'text', value: v === null || v === undefined ? '' : typeof v === 'object' ? JSON.stringify(v) : String(v), placeholder: 'empty = null' }); }
    ins[k] = inp;
    grid.append(h('span', { class: 'muted' }, k), inp);
  }
  const apply = () => {
    const out = {};
    for (const k of Object.keys(o).concat(keys.filter(k => !(k in o)))) {
      const inp = ins[k];
      if (!inp) { out[k] = o[k]; continue; }
      if (inp.type === 'checkbox') { out[k] = inp.checked; continue; }
      const s = inp.value.trim();
      if (s === '') out[k] = typeof o[k] === 'string' ? '' : null;
      else if (NUM_RE.test(s) && (typeof o[k] === 'number' || o[k] === null || o[k] === undefined)) out[k] = Number(s);
      else { try { out[k] = typeof o[k] === 'object' && o[k] !== null ? JSON.parse(s) : s; } catch (e) { out[k] = s; } }
    }
    closePop();
    setPath(F, path, out);
  };
  const box = h('div', null, h('h4', null, title || C.pathLabel(F.value, path)), grid,
    h('div', { class: 'sideacts' }, h('button', { class: 'btn pri', onclick: apply }, 'Apply'), h('button', { class: 'btn', onclick: closePop }, 'Cancel')));
  box.addEventListener('keydown', ev => { ev.stopPropagation(); if (ev.key === 'Enter') { ev.preventDefault(); apply(); } if (ev.key === 'Escape') closePop(); });
  openPop(anchor, box);
  const first = box.querySelector('input[type=text]');
  if (first) first.focus();
}
function defaultCell(F, path, col, opt) {
  const exists = C.has(F.value, path);
  const v = C.get(F.value, path);
  if (opt.cell) { const r = opt.cell(F, path, col, v, exists); if (r) return r; }
  if (Array.isArray(v)) return chips(F, path, { numbers: v.length > 0 && v.every(x => typeof x === 'number') });
  if (C.isConcept(v) || (C.isObj(v) && /concept/.test(col))) return conceptChip(F, path, { column: col });
  if (C.isObj(v) && ('low' in v || 'high' in v)) {
    const b = h('span', { class: 'v' + (isChanged(F, path) ? ' changed' : ''), 'data-ed': edKey(F, path), title: JSON.stringify(v) + '\nclick to edit' }, intervalText(v));
    b.addEventListener('click', ev => { ev.stopPropagation(); objPop(F, path, ['low', 'high', 'low_inclusive', 'high_inclusive'], b, col); });
    return b;
  }
  return scalar(F, path, { enumKey: (opt.enums && opt.enums[col]) || ((K.ENUMS[col] || S.enums[col]) ? col : undefined), suggest: opt.suggest && opt.suggest[col], prose: PROSE.has(col) && typeof v === 'string' && v.length > 40 });
}
/* A list of objects as a table: columns from the template list plus whatever keys the rows carry. */
function objTable(F, arrPath, cols, opt) {
  opt = opt || {};
  const arr = C.get(F.value, arrPath);
  if (!Array.isArray(arr)) return nodeEditor(F, arrPath);
  const key = edKey(F, arrPath);
  const base = cols ? cols.slice() : [];
  const extraKeys = [];
  let hasNotes = false;
  for (const it of arr) if (C.isObj(it)) for (const k of Object.keys(it)) {
    if (k.startsWith('_')) { hasNotes = true; continue; }
    if (!base.includes(k) && !extraKeys.includes(k)) extraKeys.push(k);
  }
  const present = base.filter(c => arr.some(it => hasOwn(it, c)) || (opt.always || []).includes(c));
  const added = (S.sheet.extraCols[key] || []).filter(c => !present.includes(c) && !extraKeys.includes(c));
  let show = present.concat(added, extraKeys);
  if (!show.length) show = base.slice(0, Math.min(base.length, 4));
  const qtxt = (S.sheet.filters[key] || '').toLowerCase();
  const limit = S.sheet.showAll[key] ? Infinity : (opt.limit || 150);
  const idx = arr.map((_, i) => i).filter(i => !qtxt || JSON.stringify(arr[i]).toLowerCase().includes(qtxt));
  const shown = idx.slice(0, limit);
  const table = h('table', { class: 't' });
  table.append(h('thead', null, h('tr', null,
    opt.rowLabel ? h('th', null, opt.rowLabel) : null,
    show.map(c => h('th', { title: (opt.help && opt.help[c]) || '' }, c, base.length && !base.includes(c) ? h('span', { class: 'warnc', title: 'not a column in the 2.7 template list for this table' }, ' ·') : null)),
    hasNotes ? h('th', null, 'notes') : null,
    h('th', null, ''))));
  const tb = h('tbody');
  for (const i of shown) {
    const it = arr[i];
    const rp = arrPath.concat(i);
    const tr = h('tr', { 'data-path': edKey(F, rp) });
    if (opt.rowLabel) tr.append(h('td', { class: 'muted mono' }, opt.rowText ? opt.rowText(it, i) : String(i + 1)));
    if (!C.isObj(it)) {
      tr.append(h('td', { colspan: show.length + (hasNotes ? 1 : 0) }, scalar(F, rp), h('span', { class: 'flagtxt' }, ' not an object')));
    } else {
      for (const c of show) tr.append(h('td', { 'data-path': edKey(F, rp.concat(c)) }, defaultCell(F, rp.concat(c), c, opt)));
      if (hasNotes) tr.append(h('td', null, Object.keys(it).filter(k => k.startsWith('_')).map(k => h('div', { class: 'note' }, h('span', { class: 'nk' }, k), scalar(F, rp.concat(k), { prose: true })))));
    }
    tr.append(h('td', { class: 'acts' }, rowActs(F, arrPath, i, opt)));
    if (opt.rowFlag) { const fl = opt.rowFlag(it, i); if (fl) { tr.classList.add('flag'); tr.title = fl; } }
    tb.append(tr);
  }
  table.append(tb);
  const bar = h('div', { class: 'tablebar' });
  if (!opt.noAdd) bar.append(h('button', { class: 'btn small', onclick: () => {
    const nv = opt.newRow ? opt.newRow(arr) : blankLike(arr.length ? arr[arr.length - 1] : null, show);
    const firstKey = Object.keys(nv)[0];
    if (firstKey !== undefined) S.pendingOpen = edKey(F, arrPath.concat(arr.length, firstKey));
    arrInsert(F, arrPath, arr.length, nv);
  } }, '+ ' + (opt.rowName || 'row')));
  const addable = base.filter(c => !show.includes(c));
  if (addable.length && !opt.noAddCol) {
    const sel = h('select', { class: 'colsel', title: 'Show another column; its cells are added to a row when you fill them' }, h('option', { value: '' }, '+ column'), addable.map(c => h('option', { value: c }, c)));
    sel.addEventListener('change', () => { if (!sel.value) return; (S.sheet.extraCols[key] = S.sheet.extraCols[key] || []).push(sel.value); scheduleRender(); });
    bar.append(sel);
  }
  if (arr.length > 12) {
    const f = h('input', { placeholder: 'filter rows…', value: S.sheet.filters[key] || '', 'data-focus': 'filter:' + key });
    f.addEventListener('input', () => { S.sheet.filters[key] = f.value; S.pendingFocus = 'filter:' + key; scheduleRender(); });
    f.addEventListener('keydown', ev => ev.stopPropagation());
    bar.append(f);
  }
  bar.append(h('span', null, idx.length === arr.length ? arr.length + ' row' + (arr.length === 1 ? '' : 's') : idx.length + ' of ' + arr.length + ' rows'));
  if (idx.length > shown.length) bar.append(h('button', { class: 'linkbtn', onclick: () => { S.sheet.showAll[key] = true; scheduleRender(); } }, 'show all ' + idx.length));
  if (opt.extraBar) bar.append(opt.extraBar);
  return h('div', { class: 'tblock' }, h('div', { class: 'tw' }, table), bar);
}

/* ── element card ── */
function elementCard(F) {
  const root = F.value;
  const P = [];
  const card = h('div', { class: 'card', 'data-path': edKey(F, ['__element']) }, h('h3', null, 'Element', h('span', { class: 'sub' }, 'what the element is and its declared value domain')));
  const blockLabels = C.blocks(root).flatMap(x => C.blockLabels(x.block));
  const render = {
    schema_version: p => scalar(F, p, { suggest: ['harmonized-element/2.5', 'harmonized-element/2.7'] }),
    registry_id: p => scalar(F, p, { newType: 'number' }),
    definition: p => scalar(F, p, { prose: true }),
    programs_covered: p => chips(F, p, { suggest: S.enums.programs_covered || [] }),
    modality: p => scalar(F, p, { enumKey: 'modality' }),
    harmonized_values: p => chips(F, p, { addText: '+ value' }),
    must_agree: p => scalar(F, p, { kind: 'bool' }),
    null_is_agreement: p => scalar(F, p, { kind: 'bool' }),
    on_conflict: p => scalar(F, p, { suggest: ['qc_flag', 'collapse_if_equal'].concat(blockLabels.map(l => 'prefer:' + l)) }),
    harmonized_with: p => chips(F, p, {}),
    conflicts: p => nodeEditor(F, p)
  };
  card.append(fieldRow(F, P, 'schema_version', 'The schema this file follows.', hasOwn(root, 'schema_version') ? render.schema_version(['schema_version']) : scalar(F, ['schema_version'])));
  for (const [k, hp] of K.ELEMENT_FIELDS) {
    if (!hasOwn(root, k)) continue;
    const p = [k];
    card.append(fieldRow(F, P, k, hp, render[k] ? render[k](p) : scalar(F, p)));
  }
  put(card, absentLine(F, P, K.ELEMENT_FIELDS, {
    registry_id: null, programs_covered: [], harmonized_values: [], must_agree: false, null_is_agreement: false, harmonized_with: [], conflicts: []
  }, ELEMENT_ORDER, 'Template fields not in this file:'));
  /* older fields: present only */
  const older = Object.keys(K.OLDER_ELEMENT_FIELDS).filter(k => hasOwn(root, k));
  if (older.length) {
    card.append(h('div', { class: 'subhead' }, 'Element fields the 2.7 template places elsewhere', h('span', { class: 'sub2' }, 'shown and edited as found')));
    for (const k of older) {
      const p = [k];
      let el;
      if (k === 'one_per') el = Array.isArray(root.one_per) ? chips(F, p, { enumKey: 'one_per' }) : scalar(F, p);
      else if (k === 'loading_grain') el = subFields(F, p, [['anchor', 'the identifier a procedure minted'], ['entity', 'the Layer 1 table the identifier names'], ['attribute', "this element's column"]]);
      else if (k === 'status_note') el = scalar(F, p, { prose: true });
      else el = nodeEditor(F, p);
      card.append(fieldRow(F, P, k, K.OLDER_ELEMENT_FIELDS[k], el));
    }
  }
  const known = new Set([...K.ELEMENT_KNOWN, ...Object.keys(K.OLDER_ELEMENT_FIELDS)]);
  const others = otherRows(F, P, known, 'Other fields in this file');
  if (others) card.append(others);
  return card;
}

/* ── grain panel: what a block's value is a fact about ── */
function grainPanel(F, root, bPath) {
  const block = C.get(F.value, bPath);
  const g = C.blockGrain(root, block);
  const label = g.label;
  const srcText = { block: 'declared on this block', element: 'inherited from the file-level loading_grain (older placement)', one_per: 'only the older one_per field', none: 'not declared' }[g.source];
  const panel = h('div', { class: 'gpanel' }, h('div', { class: 'gtitle' }, 'Grain', h('span', { class: 'src ' + g.source }, srcText),
    g.level ? h('span', { class: 'sub2' }, 'level: ' + g.level) : null));
  const declare = (anchor, entity) => addKeyOrdered(F, bPath, 'loading_grain', { anchor, entity, attribute: label }, BLOCK_ORDER);
  if (g.source === 'block' || g.source === 'element') {
    const gp = g.source === 'block' ? bPath.concat('loading_grain') : ['loading_grain'];
    const ro = g.source === 'element';
    const box = (cls, lab, valEl, help) => h('div', { class: 'gbox ' + cls }, h('span', { class: 'gl' }, lab), valEl, h('span', { class: 'gh' }, help));
    panel.append(h('div', { class: 'chain' },
      box('proc', 'procedure (follows from the anchor)', h('span', { class: 'gv' }, g.procedure || '—'), g.procHelp),
      h('span', { class: 'garrow' }, 'minted →'),
      box('', 'anchor', scalar(F, gp.concat('anchor'), { enumKey: 'anchor', readonly: ro, cls: 'gv' }), g.anchorHelp),
      h('span', { class: 'garrow' }, 'names one →'),
      box('', 'entity', scalar(F, gp.concat('entity'), { enumKey: 'entity', readonly: ro, cls: 'gv' }), g.entityNoun ? 'a ' + g.entityNoun + ': ' + g.entityHelp : g.entityHelp),
      h('span', { class: 'garrow' }, 'whose row gets →'),
      box('', 'attribute', scalar(F, gp.concat('attribute'), { readonly: ro, cls: 'gv', suggest: [label] }), g.attrHelp)));
    panel.append(h('div', { class: 'reads' }, h('b', null, 'Reads as: '), g.readsAs));
    if (g.besides && g.besides.length) panel.append(h('div', { class: 'legend' }, 'Also written in that row, beside the value: ', h('span', { class: 'mono' }, g.besides.join(', ')), ' (from the unit, harmonized_curie and harmonized_encoding of this block).'));
    if (!g.attrMatches) panel.append(h('div', { class: 'flagtxt' }, 'attribute is “' + g.attribute + '”; this file\'s registry_label is “' + label + '”.'));
    if (ro) panel.append(h('div', { class: 'sideacts' }, h('span', { class: 'sub2' }, 'Read-only here: it belongs to the whole file.'),
      h('button', { class: 'btn small', onclick: () => addKeyOrdered(F, bPath, 'loading_grain', C.clone(root.loading_grain), BLOCK_ORDER) }, 'Declare it on this block (copy)')));
  } else {
    panel.append(h('div', { class: 'reads' }, g.readsAs));
    if (g.source === 'one_per') panel.append(h('div', { class: 'sub2' }, 'one_per (element-level, older): ', chips(F, ['one_per'], { enumKey: 'one_per' })));
    const opts = [['participant_id', 'participant'], ['participant_id', 'participant_visit'], ['participant_id', 'baseline_clinical_labs'], ['specimen_id', 'specimen'], ['sample_id', 'sample'], ['sample_id', 'serum_sample'], ['sample_id', 'urine_sample']];
    panel.append(h('div', { class: 'sideacts' }, h('span', { class: 'sub2' }, 'Declare on this block:'),
      opts.map(([a, e]) => h('button', { class: 'btn small', onclick: () => declare(a, e) }, a + ' → ' + e)),
      h('button', { class: 'btn small', onclick: () => declare('', '') }, 'empty')));
  }
  panel.append(h('div', { class: 'legend' }, h('b', null, 'anchor'), ' = the identifier a procedure minted; it keys the Layer 1 row. ', h('b', null, 'entity'), ' = the thing that identifier names = the Layer 1 table the value lands in. ', h('b', null, 'attribute'), ' = this element = the column in that table that receives the harmonized value.'));
  return panel;
}

/* ── applies_to_rows: which rows a block reads ── */
function condText(c) {
  if (!C.isObj(c)) return '(not a condition)';
  const col = c.column ? '“' + c.column + '”' : '(no column)';
  const delims = Array.isArray(c.delimiters) ? c.delimiters : [];
  const pos = c.token_position;
  let where = col;
  if (delims.length) where += ' split on ' + delims.map(d => JSON.stringify(d)).join(' ') + ', piece ' + (pos === null || pos === undefined ? '(no token_position)' : pos);
  else where += ' (whole cell)';
  let test;
  if (c.inequality === true) test = ' satisfies ' + (typeof c.token === 'string' ? c.token : JSON.stringify(c.token));
  else if (c.match === 'in' || Array.isArray(c.token)) test = ' is one of ' + (Array.isArray(c.token) ? c.token.map(t => JSON.stringify(t)).join(', ') : JSON.stringify(c.token));
  else test = ' equals ' + JSON.stringify(c.token === undefined ? null : c.token);
  return where + test;
}
function condTable(F, rowPaths, opt) {
  const cols = K.CONDITION_COLUMNS.filter(c => rowPaths.some(p => hasOwn(C.get(F.value, p), c)) || ['column', 'token'].includes(c));
  for (const p of rowPaths) { const o = C.get(F.value, p); if (C.isObj(o)) for (const k of Object.keys(o)) if (!cols.includes(k) && !k.startsWith('_')) cols.push(k); }
  const t = h('table', { class: 't' }, h('thead', null, h('tr', null, cols.map(c => h('th', null, c)), opt.arrPath ? h('th', null, '') : null)));
  const tb = h('tbody');
  rowPaths.forEach((p, i) => {
    tb.append(h('tr', { 'data-path': edKey(F, p) }, cols.map(c => {
      const cp = p.concat(c);
      const v = C.get(F.value, cp);
      let el;
      if (c === 'delimiters' || Array.isArray(v)) el = chips(F, cp, {});
      else if (c === 'inequality') el = scalar(F, cp, { kind: 'bool' });
      else if (c === 'token_position') el = scalar(F, cp, { newType: 'number' });
      else el = scalar(F, cp, { enumKey: c === 'match' ? 'match' : undefined });
      return h('td', null, el);
    }), opt.arrPath ? h('td', { class: 'acts' }, rowActs(F, opt.arrPath, i, {})) : null));
  });
  t.append(tb);
  return h('div', { class: 'tw' }, t);
}
function rowsPanel(F, bPath) {
  const p = bPath.concat('applies_to_rows');
  const v = C.get(F.value, p);
  const shape = v === undefined ? 'absent' : Array.isArray(v) ? 'list' : C.isObj(v) && Array.isArray(v.conditions) ? 'current' : C.isObj(v) ? 'flat' : 'other';
  const panel = h('div', { class: 'gpanel' }, h('div', { class: 'gtitle' }, 'Rows this block reads', h('span', { class: 'src ' + (shape === 'current' ? 'block' : shape === 'absent' ? '' : 'element') },
    { absent: 'all rows', current: 'require / action / conditions', flat: 'older single-condition form', list: 'older list form', other: 'unrecognised shape' }[shape])));
  if (shape === 'absent') {
    panel.append(h('div', { class: 'reads' }, 'Every row of the file (no applies_to_rows).'),
      h('div', { class: 'sideacts' }, h('button', { class: 'btn small', onclick: () => { S.pendingOpen = edKey(F, p.concat('conditions', 0, 'column')); addKeyOrdered(F, bPath, 'applies_to_rows', { require: 'all', action: 'include', conditions: [{ column: '', match: 'equals', token: '', inequality: false, token_position: null, delimiters: [] }] }, BLOCK_ORDER); } }, '+ condition')));
    return panel;
  }
  if (shape === 'other') { panel.append(nodeEditor(F, p)); return panel; }
  const convert = (require) => setPath(F, p, { require, action: 'include', conditions: shape === 'flat' ? [C.clone(v)] : C.clone(v) });
  if (shape === 'current') {
    const conds = v.conditions;
    const act = v.action === 'exclude' ? 'Skips' : v.action === 'flag' ? 'Flags' : 'Reads only';
    panel.append(h('div', { class: 'reads' }, h('b', null, act + ' rows where '), conds.length > 1 ? (v.require === 'any' ? 'any' : v.require === 'all' ? 'all' : '(require not set: all or any?)') + ' of: ' : '',
      conds.map(condText).join(conds.length > 1 ? '; ' : '') || '(no conditions)', '.'));
    panel.append(h('div', { class: 'subf' },
      h('span', { class: 'sf' }, h('span', { class: 'sk', title: 'how several conditions combine' }, 'require'), ' ', scalar(F, p.concat('require'), { enumKey: 'require' })),
      h('span', { class: 'sf' }, h('span', { class: 'sk', title: 'include the matching rows, exclude them, or flag them' }, 'action'), ' ', scalar(F, p.concat('action'), { enumKey: 'action' }))));
    panel.append(condTable(F, conds.map((_, i) => p.concat('conditions', i)), { arrPath: p.concat('conditions') }));
    panel.append(h('div', { class: 'sideacts' }, h('button', { class: 'btn small', onclick: () => { S.pendingOpen = edKey(F, p.concat('conditions', conds.length, 'column')); arrInsert(F, p.concat('conditions'), conds.length, { column: '', match: 'equals', token: '', inequality: false, token_position: null, delimiters: [] }); } }, '+ condition')));
    const other = Object.keys(v).filter(k => !['require', 'action', 'conditions'].includes(k));
    if (other.length) panel.append(h('div', { class: 'sub2' }, 'Also here: ', other.map(k => h('span', { class: 'sf' }, h('span', { class: 'sk' }, k), ' ', nodeEditor(F, p.concat(k))))));
  } else if (shape === 'flat') {
    panel.append(h('div', { class: 'reads' }, h('b', null, 'Reads only rows where '), condText(v), '.'), condTable(F, [p], {}),
      h('div', { class: 'sideacts' }, h('button', { class: 'btn small', title: 'Rewrites it as { require: "all", action: "include", conditions: [ this condition ] }', onclick: () => convert('all') }, 'Rewrite as require / action / conditions')));
  } else {
    panel.append(h('div', { class: 'reads' }, h('b', null, v.length + ' conditions; '), 'this older list form does not say whether all or any must hold.'),
      h('ul', { class: 'conds' }, v.map(c => h('li', null, condText(c)))),
      condTable(F, v.map((_, i) => p.concat(i)), { arrPath: p }),
      h('div', { class: 'sideacts' }, h('span', { class: 'sub2' }, 'Rewrite as require / action / conditions with'),
        h('button', { class: 'btn small', onclick: () => convert('all') }, 'require: all'), h('button', { class: 'btn small', onclick: () => convert('any') }, 'require: any')));
  }
  return panel;
}

/* ── Layer 1 ── */
function rangeEl(F, p) {
  const v = C.get(F.value, p);
  if (!C.isObj(v)) return nodeEditor(F, p);
  return h('span', { class: 'subf' },
    h('span', { class: 'sf' }, h('span', { class: 'sk' }, 'min'), ' ', scalar(F, p.concat('min'), { newType: 'number' })),
    h('span', { class: 'sf' }, h('span', { class: 'sk' }, 'max'), ' ', scalar(F, p.concat('max'), { newType: 'number' })),
    Object.keys(v).filter(k => k !== 'min' && k !== 'max').map(k => h('span', { class: 'sf' }, h('span', { class: 'sk' }, k), ' ', nodeEditor(F, p.concat(k)))));
}
function dataFileCell(F, path, col, v, exists) {
  if (col === 'sha256' && typeof v === 'string' && v.length > 20) return scalar(F, path, { display: s => s.slice(0, 16) + '…', title: v, cls: 'sha' });
  if (col === 'file' && typeof v === 'string' && /^withheld/.test(v)) return scalar(F, path, { display: () => 'withheld', title: v, cls: 'muted' });
  if (col === 'id_type') return scalar(F, path, { enumKey: 'id_type' });
  return null;
}
function l1VmTable(F, root, vmPath) {
  const declared = Array.isArray(root.harmonized_values) ? root.harmonized_values.map(String) : [];
  const hvs = C.allHarmonizedValues(root);
  return objTable(F, vmPath, K.VM_COLUMNS, {
    always: ['source_value', 'harmonized_value'], rowName: 'entry', help: K.VM_HELP,
    cell: (F2, path, col, v) => {
      if (col === 'harmonized_value') return scalar(F2, path, { suggest: hvs, bad: x => declared.length > 0 && !declared.includes(String(x)) && x !== '<any in range>', title: declared.length ? 'harmonized_values: ' + declared.join(' | ') : '' });
      if (col === 'harmonized_curie' && C.isObj(v)) return conceptChip(F2, path, { column: col });
      return null;
    },
    newRow: arr => {
      const last = arr.length ? arr[arr.length - 1] : null;
      const nv = C.isObj(last) ? blankLike(last, []) : { source_value: '', source_encoding: null, harmonized_value: '', harmonized_encoding: null, note: null };
      if ('source_value' in nv) nv.source_value = '';
      if ('harmonized_value' in nv) nv.harmonized_value = '';
      return nv;
    }
  });
}
function l1El(F, root, bPath) {
  const p = bPath.concat('layer_1_etl');
  const l1 = C.get(F.value, p);
  if (!C.isObj(l1)) return nodeEditor(F, p);
  const box = h('div', { class: 'l1' });
  for (const [k, hp] of K.L1_FIELDS) {
    if (!hasOwn(l1, k) || k === 'data_files' || k === 'value_map') continue;
    const kp = p.concat(k);
    let el;
    if (k === 'value_form' || k === 'datatype') el = scalar(F, kp, { enumKey: k });
    else if (k === 'range') el = rangeEl(F, kp);
    else if (k === 'missing_values') { const mv = l1[k]; el = Array.isArray(mv) ? chips(F, kp, { numbers: mv.length > 0 && mv.every(x => typeof x === 'number') }) : scalar(F, kp); }
    else el = scalar(F, kp, { suggest: k === 'unit' ? (S.enums.unit || []) : undefined });
    box.append(fieldRow(F, p, k, hp, el));
  }
  for (const k of ['data_files', 'value_map']) {
    if (!hasOwn(l1, k)) continue;
    const kp = p.concat(k);
    const arr = l1[k];
    const n = Array.isArray(arr) ? arr.length : 0;
    box.append(h('div', { class: 'subhead', 'data-path': edKey(F, kp) }, k === 'data_files' ? 'Pinned data files' : 'Value map', h('span', { class: 'sub2' }, K.L1_HELP[k]),
      k === 'value_map' && n === 0 ? h('span', { class: 'sub2' }, '(empty: values pass through as read)') : null,
      h('button', { class: 'linkbtn warn', title: 'remove ' + k, onclick: () => delPath(F, kp) }, '×')));
    if (!Array.isArray(arr)) box.append(nodeEditor(F, kp));
    else if (k === 'data_files') box.append(objTable(F, kp, K.DATA_FILE_COLUMNS, { cell: dataFileCell, rowName: 'file' }));
    else box.append(l1VmTable(F, root, kp));
    const nn = noteEl(F, p, k);
    if (nn) box.append(nn);
  }
  put(box, absentLine(F, p, K.L1_FIELDS, { range: { min: null, max: null }, missing_values: [], data_files: [], value_map: [] }, L1_ORDER, 'Not in layer_1_etl:'));
  const others = otherRows(F, p, new Set(L1_ORDER), 'Other fields in layer_1_etl');
  if (others) box.append(others);
  return box;
}

/* ── one source block (and its nested fallback) ── */
function blockEl(F, root, bPath, n, depth) {
  const b = C.get(F.value, bPath);
  const isFb = depth > 0;
  const labels = C.blockLabels(b);
  const l1 = C.isObj(b) && C.isObj(b.layer_1_etl) ? b.layer_1_etl : {};
  const coll = isCollapsed(F, bPath);
  const top = !isFb ? bPath.slice(0, -1) : null;
  const sub = C.isObj(b) ? [b.program, b.study, b.status, l1.value_form, l1.unit, C.valueMap(b).length ? C.valueMap(b).length + ' map entries' : null].filter(x => x !== null && x !== undefined && x !== '').join(' · ') : '';
  const head = h('div', { class: 'bhead', onclick: () => toggleCollapsed(F, bPath) },
    h('span', { class: 'tw2' }, coll ? '▸' : '▾'),
    h('span', { class: 't' }, (isFb ? 'Fallback' : 'Source block ' + n) + ' · ' + (labels.join(' / ') || '(no source_label)')),
    h('span', { class: 's' }, sub),
    h('span', { class: 'acts', onclick: ev => ev.stopPropagation() },
      !isFb ? rowActs(F, top, bPath[bPath.length - 1], {}) : h('span', { class: 'rowacts' }, h('button', { class: 'del', title: 'delete the fallback', onclick: () => delPath(F, bPath) }, '✕')),
      h('button', { class: 'linkbtn', title: 'edit this block as JSON', onclick: () => jsonModal(F, bPath) }, '{ }')));
  const el = h('div', { class: 'block' + (isFb ? ' fb' : ''), 'data-path': edKey(F, bPath) }, head);
  if (!C.isObj(b)) { el.append(h('div', { class: 'flagtxt' }, 'This block is not an object.'), nodeEditor(F, bPath)); return el; }
  if (coll) return el;
  const render = {
    source_label: p => Array.isArray(C.get(F.value, p)) ? chips(F, p, {}) : scalar(F, p),
    program: p => scalar(F, p, { enumKey: 'program', suggest: S.enums.program || [] }),
    description: p => scalar(F, p, { prose: true }),
    status: p => scalar(F, p, { enumKey: 'status' }),
    status_note: p => scalar(F, p, { prose: true }),
    manual_approval: p => scalar(F, p, { kind: 'bool' }),
    dictionary: p => subFields(F, p, [['file_name', 'the dictionary document'], ['checksum', 'its checksum'], ['sourced_from', 'where it came from']]),
    src_dictionary: p => Array.isArray(C.get(F.value, p)) ? chips(F, p, {}) : scalar(F, p, { prose: true }),
    src_definition: p => scalar(F, p, { prose: true }),
    layout: p => subFields(F, p, [['file_type', 'csv | tsv | xlsx | jsonl …'], ['sheet', 'workbook sheet'], ['table', 'table or record type within the file']]),
    precedence: p => scalar(F, p, { newType: 'number' }),
    extract: p => objTable(F, p, K.EXTRACT_COLUMNS, { rowName: 'piece' }),
    layer_1_etl: () => l1El(F, root, bPath),
    fallback: p => (C.isObj(C.get(F.value, p)) ? blockEl(F, root, p, n, depth + 1) : nodeEditor(F, p))
  };
  for (const [k, hp] of K.BLOCK_FIELDS) {
    const p = bPath.concat(k);
    if (k === 'loading_grain') { el.append(fieldRow(F, bPath, k, hp, grainPanel(F, root, bPath))); continue; }
    if (k === 'applies_to_rows') { el.append(fieldRow(F, bPath, k, hp, rowsPanel(F, bPath))); continue; }
    if (!hasOwn(b, k)) continue;
    if (k === 'layer_1_etl') { put(el, h('div', { class: 'subhead', 'data-path': edKey(F, p) }, 'layer_1_etl', h('span', { class: 'sub2' }, hp)), render.layer_1_etl(), noteEl(F, bPath, k)); continue; }
    if (k === 'fallback') { put(el, h('div', { class: 'subhead' }, 'fallback', h('span', { class: 'sub2' }, hp)), render.fallback(p), noteEl(F, bPath, k)); continue; }
    el.append(fieldRow(F, bPath, k, hp, render[k] ? render[k](p) : nodeEditor(F, p)));
  }
  put(el, absentLine(F, bPath, K.BLOCK_FIELDS.filter(f => f[0] !== 'loading_grain' && f[0] !== 'applies_to_rows'), {
    manual_approval: false, dictionary: {}, src_dictionary: [], layout: {}, precedence: null, extract: [], layer_1_etl: {}, fallback: () => ({ source_label: '', program: C.isObj(b) ? (b.program || '') : '', layer_1_etl: { value_map: [] } })
  }, BLOCK_ORDER, 'Not in this block:'));
  const others = otherRows(F, bPath, new Set(BLOCK_ORDER), 'Other fields in this block');
  if (others) el.append(others);
  return el;
}
function sourcesCard(F) {
  const root = F.value;
  const srcs = root.sources;
  const card = h('div', { class: 'card', 'data-path': edKey(F, ['sources']) });
  const nTop = Array.isArray(srcs) ? srcs.length : 0;
  const nAll = C.blocks(root).length;
  card.append(h('h3', null, 'Layer 1 · source blocks', h('span', { class: 'sub' }, nTop + ' block' + (nTop === 1 ? '' : 's') + (nAll > nTop ? ' + ' + (nAll - nTop) + ' fallback' + (nAll - nTop === 1 ? '' : 's') : '') + ' · each block reads one provider column and maps its values onto harmonized_values'),
    nTop > 1 ? h('button', { class: 'linkbtn', onclick: () => { C.blocks(root).forEach(x => { S.sheet.collapsed[edKey(F, x.path)] = true; }); scheduleRender(); } }, 'collapse all') : null,
    nTop > 1 ? h('button', { class: 'linkbtn', onclick: () => { C.blocks(root).forEach(x => { delete S.sheet.collapsed[edKey(F, x.path)]; }); scheduleRender(); } }, 'expand all') : null));
  if (!hasOwn(root, 'sources')) {
    card.append(h('div', { class: 'sub2' }, 'No sources field.'), h('button', { class: 'btn small', onclick: () => addKeyOrdered(F, [], 'sources', [], ELEMENT_ORDER) }, '+ sources'));
    return card;
  }
  if (!Array.isArray(srcs)) { card.append(nodeEditor(F, ['sources'])); return card; }
  if (!srcs.length) card.append(h('div', { class: 'banner info' }, 'No source blocks: nothing in this file reads a provider column.'));
  srcs.forEach((b, i) => card.append(blockEl(F, root, ['sources', i], i + 1, 0)));
  card.append(h('div', { class: 'sideacts' }, h('button', { class: 'btn small', onclick: () => {
    const last = srcs.length ? srcs[srcs.length - 1] : null;
    arrInsert(F, ['sources'], srcs.length, { source_label: '', program: C.isObj(last) ? (last.program || '') : '', status: 'draft', layer_1_etl: { value_map: [] } });
    S.pendingOpen = edKey(F, ['sources', srcs.length - 1, 'source_label']);
  } }, '+ source block'), h('span', { class: 'sub2' }, 'or duplicate a block with ⧉ in its header')));
  const nn = noteEl(F, [], 'sources');
  if (nn) card.append(nn);
  return card;
}
