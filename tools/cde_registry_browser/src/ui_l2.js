/* ───────────── Layer 2: targets, keys, the value-map fan-out; links; policies; raw JSON ───────────── */
const PH_RE = /^\{[^{}]+\}$/;
function l1Columns(root) {
  const label = C.labelOf(root);
  const cols = [label, label + '_unit', label + '_curie', label + '_code'];
  for (const { block } of C.blocks(root)) { const g = C.blockGrain(root, block); if (g.anchor) cols.push(g.anchor); }
  C.leaves(root, (p, v) => { if (typeof v === 'string' && PH_RE.test(v)) cols.push(v.slice(1, -1)); });
  return C.uniq(cols);
}
function anchorSuggest(key) {
  const counts = new Map();
  for (const F of S.files.values()) {
    if (!C.isObj(F.value)) continue;
    for (const t of C.targets(F.value)) if (C.isObj(t) && C.isObj(t.anchored_to) && typeof t.anchored_to[key] === 'string' && t.anchored_to[key]) counts.set(t.anchored_to[key], (counts.get(t.anchored_to[key]) || 0) + 1);
  }
  const best = Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
  return best.length ? best[0][0] : '';
}
function valueText(v) {
  if (v === undefined) return '—';
  if (v === null) return 'null';
  if (C.isConcept(v)) { const c = C.conceptOf(v); return (c.name || '(no name)') + ' · ' + (c.id === null || c.id === undefined || c.id === '' ? 'no id' : c.id); }
  if (typeof v === 'string') return v === '' ? '""' : v;
  return typeof v === 'object' ? JSON.stringify(v) : String(v);
}

/* ── the keys a target's rows hang on ── */
function keysPanel(F, root, tPath) {
  const t = C.get(F.value, tPath);
  const res = C.targetKeys(root, t);
  const p = tPath.concat('anchored_to');
  const panel = h('div', { class: 'gpanel l2' }, h('div', { class: 'gtitle' }, 'Keys — what each ' + res.table + ' row hangs on', h('span', { class: 'sub2' }, 'CDM key column → the table or map the loader resolves it from')));
  if (res.shape === 'list') {
    panel.append(h('div', { class: 'reads' }, 'anchored_to is a list here; the key table below reads an object (key column → table or map).'), nodeEditor(F, p));
    return panel;
  }
  if (res.shape !== 'object') {
    put(panel, h('div', { class: 'reads' }, res.shape === 'missing' ? 'No anchored_to: the loader has nothing to hang the rows on.' : 'anchored_to is not an object.'),
      res.shape === 'other' ? nodeEditor(F, p) : null,
      h('div', { class: 'sideacts' }, h('button', { class: 'btn small', onclick: () => { const v = {}; v.person_id = anchorSuggest('person_id'); addKeyOrdered(F, tPath, 'anchored_to', v, TARGET_ORDER); } }, '+ anchored_to with person_id')));
    return panel;
  }
  const tb = h('tbody');
  for (const r of res.rows) {
    const kp = p.concat(r.key);
    tb.append(h('tr', { class: r.present ? '' : 'absentrow' },
      h('td', { class: 'mono' }, r.key),
      h('td', null, r.present ? scalar(F, kp, { suggest: [anchorSuggest(r.key)].filter(Boolean) }) : h('button', { class: 'addf', onclick: () => { S.pendingOpen = edKey(F, kp); addKey(F, p, r.key, anchorSuggest(r.key)); } }, '+ ' + r.key)),
      h('td', { class: 'sub2' }, r.explain),
      h('td', { class: 'acts' }, r.present ? h('span', { class: 'rowacts' }, h('button', { class: 'del', title: 'remove this key', onclick: () => delPath(F, kp) }, '✕')) : null)));
  }
  panel.append(h('div', { class: 'tw' }, h('table', { class: 't' }, h('thead', null, h('tr', null, h('th', null, 'key column'), h('th', null, 'resolved from'), h('th', null, 'what the loader does'), h('th', null, ''))), tb)));
  panel.append(h('div', { class: 'tablebar' }, addKeyInput(F, p)));
  panel.append(h('div', { class: 'res' }, h('b', null, 'Result: '), res.resultText));
  if (res.check) panel.append(h('div', { class: 'res ' + res.check.status }, h('b', null, res.check.status === 'ok' ? '✓ ' : res.check.status === 'warn' ? '⚠ ' : '? '), 'Against the source blocks\' grain: ', res.check.text));
  return panel;
}

/* ── one cell of the Layer 2 grid ── */
function cellMenu(F, path, col, anchor, ctx) {
  const v = C.get(F.value, path);
  const exists = C.has(F.value, path);
  const items = [];
  const add = (label, fn, title) => items.push(h('button', { class: 'menuitem', title: title || '', onclick: () => { closePop(); fn(); } }, label));
  add('Concept from OMOP Hub…', () => setTimeout(() => openConceptPop(F, path, { column: col, title: col }, document.querySelector('[data-ed="' + CSS.escape(edKey(F, path)) + '"]') || anchor), 0));
  if (col === 'value_as_number' || col === 'quantity') add('<value>  the harmonized value itself, as a number', () => setPath(F, path, '<value>'));
  add('{column}  taken from a Layer 1 column of the same row…', () => setTimeout(() => placeholderPop(F, path, ctx.root, anchor), 0));
  add('Text', () => { S.pendingOpen = edKey(F, path); setPath(F, path, typeof v === 'string' ? v : ''); });
  add('Number', () => { S.pendingOpenType = 'number'; S.pendingOpen = edKey(F, path); setPath(F, path, typeof v === 'number' ? v : null); });
  add('null', () => setPath(F, path, null));
  if (exists) add('Remove from this entry', () => delPath(F, path), 'deletes the key: the column is not filled by this entry');
  openPop(anchor, h('div', { class: 'menu' }, h('h4', null, col + (ctx.hv !== undefined ? ' · for “' + ctx.hv + '”' : '')), h('div', { class: 'sub2' }, (K.L2_CELL_HELP[col] || '') + (C.allowedDomains(col) ? ' Domains allowed: ' + C.allowedDomains(col).join(' / ') + '.' : '')), items));
}
function placeholderPop(F, path, root, anchor) {
  const cur = C.get(F.value, path);
  const inp = h('input', { type: 'text', value: typeof cur === 'string' && PH_RE.test(cur) ? cur.slice(1, -1) : '', placeholder: 'Layer 1 column name' });
  inp.setAttribute('list', datalistFor('l1cols-' + F.id, l1Columns(root)));
  const go = () => { const s = inp.value.trim().replace(/^\{|\}$/g, ''); if (!s) return; closePop(); setPath(F, path, '{' + s + '}'); };
  inp.addEventListener('keydown', ev => { ev.stopPropagation(); if (ev.key === 'Enter') { ev.preventDefault(); go(); } if (ev.key === 'Escape') closePop(); });
  openPop(anchor, h('div', null, h('h4', null, '{column}: take the value from a Layer 1 column'), h('div', { class: 'sub2' }, 'The loader reads that column of the same Layer 1 row (an identifier, a count, a second element).'), h('div', { class: 'srch' }, inp, h('button', { class: 'btn pri', onclick: go }, 'Set'))));
  inp.focus();
}
function l2Cell(F, path, col, ctx) {
  const exists = C.has(F.value, path);
  const v = C.get(F.value, path);
  let main;
  if (!exists) {
    main = h('span', { class: 'v empty', 'data-ed': edKey(F, path), title: 'not filled by this entry · click to choose what goes here' }, '—');
    main.addEventListener('click', ev => { ev.stopPropagation(); if (/_concept_id$/.test(col)) openConceptPop(F, path, { column: col, title: col + ' · for “' + ctx.hv + '”' }, main); else cellMenu(F, path, col, main, ctx); });
  } else if (C.isConcept(v) || (C.isObj(v) && /_concept_id$/.test(col))) main = conceptChip(F, path, { column: col, title: col + ' · for “' + ctx.hv + '”' });
  else if (typeof v === 'string' && (v === '<value>' || PH_RE.test(v))) main = scalar(F, path, { cls: 'ph', title: v === '<value>' ? '<value> = the harmonized value itself, as a number' : v + ' = the value of Layer 1 column ' + v.slice(1, -1) + ' of the same row' });
  else main = scalar(F, path, { enumKey: undefined, suggest: col === 'value_as_string' ? [ctx.hv] : col === 'unit_source_value' ? (S.enums.unit || []) : undefined, prose: col === 'note' });
  return h('div', { class: 'l2c' }, main, h('button', { class: 'cm', title: 'change what this cell holds', onclick: ev => { ev.stopPropagation(); cellMenu(F, path, col, ev.currentTarget, ctx); } }, '▾'));
}
function insertEntryFor(F, root, vmPath, hv) {
  const vm = C.get(F.value, vmPath);
  const order = C.allHarmonizedValues(root);
  const oi = order.indexOf(hv);
  let at = vm.length;
  if (oi >= 0) {
    let best = -1;
    vm.forEach((e, i) => { if (C.isObj(e)) { const ei = order.indexOf(String(e.harmonized_value)); if (ei >= 0 && ei < oi) best = i; } });
    at = best + 1;
    if (best < 0) { const first = vm.findIndex(e => C.isObj(e) && order.indexOf(String(e.harmonized_value)) > oi); at = first >= 0 ? first : vm.length; }
  }
  return at;
}
/* The fan-out grid: one row per harmonized value, one column per CDM column the value fills. */
function l2Grid(F, root, tPath) {
  const t = C.get(F.value, tPath);
  const vmPath = tPath.concat('value_map');
  const grid = C.l2Grid(root, t);
  const key = edKey(F, vmPath);
  const cols = grid.columns.filter(c => !c.isNote);
  for (const c of S.sheet.extraCols[key] || []) if (!cols.some(x => x.key === c)) cols.push({ key: c, isColumn: grid.knownTable ? grid.cdmColumns.includes(c) : null });
  const hasNote = grid.columns.some(c => c.isNote);
  const missing = grid.rows.filter(r => r.entryIndex === null).map(r => r.hv);
  const table = h('table', { class: 't l2t' });
  table.append(h('thead', null, h('tr', null, h('th', null, 'harmonized value'),
    cols.map(c => h('th', { title: K.L2_CELL_HELP[c.key] || (c.key.startsWith('_') ? 'a note key' : '') }, c.key, c.isColumn === false ? h('span', { class: 'warnc', title: 'Every value_map key must be a column of the target table' }, ' · not a column of ' + grid.table) : null)),
    hasNote ? h('th', null, 'note') : null, h('th', null, ''))));
  const tb = h('tbody');
  const qtxt = (S.sheet.filters[key] || '').toLowerCase();
  const limit = S.sheet.showAll[key] ? Infinity : 150;
  let shown = 0, hidden = 0;
  for (const r of grid.rows) {
    if (qtxt && !r.hv.toLowerCase().includes(qtxt)) continue;
    if (shown >= limit) { hidden++; continue; }
    shown++;
    if (r.entryIndex === null) {
      tb.append(h('tr', { class: 'missing' }, h('td', { class: 'hv' }, r.hv),
        h('td', { colspan: cols.length + (hasNote ? 1 : 0) }, h('span', { class: 'flagtxt' }, 'no entry for this value in this target '),
          h('button', { class: 'btn small', onclick: () => { const at = insertEntryFor(F, root, vmPath, r.hv); arrInsert(F, vmPath, at, { harmonized_value: r.hv }); } }, '+ entry')),
        h('td', null)));
      continue;
    }
    const ep = vmPath.concat(r.entryIndex);
    const e = C.get(F.value, ep);
    if (!C.isObj(e)) {
      tb.append(h('tr', { class: 'flag' }, h('td', { class: 'hv' }, '(not an object)'), h('td', { colspan: cols.length + (hasNote ? 1 : 0) }, scalar(F, ep)), h('td', { class: 'acts' }, rowActs(F, vmPath, r.entryIndex, { noMove: true }))));
      continue;
    }
    const flagText = r.flags.map(f => ({ duplicate: 'two entries for this value in this target', undeclared: 'not one of harmonized_values', malformed: 'not an object' }[f] || f)).join('; ');
    tb.append(h('tr', { class: r.flags.length ? 'flag' : '', title: flagText, 'data-path': edKey(F, ep) },
      h('td', { class: 'hv' }, scalar(F, ep.concat('harmonized_value'), { suggest: C.allHarmonizedValues(root) }), r.flags.length ? h('div', { class: 'flagtxt' }, flagText) : null),
      cols.map(c => h('td', { 'data-path': edKey(F, ep.concat(c.key)) }, l2Cell(F, ep.concat(c.key), c.key, { hv: r.hv, root }))),
      hasNote ? h('td', null, scalar(F, ep.concat('note'), { prose: true })) : null,
      h('td', { class: 'acts' }, rowActs(F, vmPath, r.entryIndex, { noMove: true }))));
  }
  table.append(tb);
  const bar = h('div', { class: 'tablebar' });
  if (missing.length) bar.append(h('button', { class: 'btn small', title: missing.join(' | '), onclick: () => mutate(F, () => {
    for (const hv of missing) { const at = insertEntryFor(F, root, vmPath, hv); C.get(F.value, vmPath).splice(at, 0, { harmonized_value: hv }); remapRaw(F, vmPath, j => (j < at ? [j] : [j + 1])); }
  }) }, missing.length === 1 ? '+ entry for the missing value' : '+ entries for all ' + missing.length + ' missing values'));
  bar.append(h('button', { class: 'btn small', onclick: () => { const vm = C.get(F.value, vmPath); S.pendingOpen = edKey(F, vmPath.concat(vm.length, 'harmonized_value')); arrInsert(F, vmPath, vm.length, { harmonized_value: '' }); } }, '+ entry'));
  const pool = grid.knownTable ? K.L2_VALUE_KEYS_ORDER.filter(c => grid.cdmColumns.includes(c)).concat(grid.cdmColumns) : K.L2_VALUE_KEYS_ORDER;
  const avail = C.uniq(pool.filter(c => !cols.some(x => x.key === c) && c !== 'person_id' && c !== grid.table + '_id'));
  const sel = h('select', { class: 'colsel', title: 'Show another column of ' + (grid.table || 'the table') + '; a cell is written to an entry when you fill it' },
    h('option', { value: '' }, '+ column'), avail.map(c => h('option', { value: c }, c)), h('option', { value: '__note' }, 'note'));
  sel.addEventListener('change', () => {
    if (!sel.value) return;
    (S.sheet.extraCols[key] = S.sheet.extraCols[key] || []).push(sel.value === '__note' ? 'note' : sel.value);
    scheduleRender();
  });
  bar.append(sel);
  if (grid.rows.length > 12) {
    const f = h('input', { placeholder: 'filter values…', value: S.sheet.filters[key] || '', 'data-focus': 'filter:' + key });
    f.addEventListener('input', () => { S.sheet.filters[key] = f.value; S.pendingFocus = 'filter:' + key; scheduleRender(); });
    f.addEventListener('keydown', ev => ev.stopPropagation());
    bar.append(f);
  }
  bar.append(h('span', null, pl(grid.rows.filter(r => r.entryIndex !== null).length, 'entry', 'entries') + (missing.length ? ' · ' + pl(missing.length, 'value') + ' without an entry' : '')));
  if (hidden) bar.append(h('button', { class: 'linkbtn', onclick: () => { S.sheet.showAll[key] = true; scheduleRender(); } }, 'show ' + hidden + ' more'));
  return h('div', { class: 'tblock' }, h('div', { class: 'tw' }, table), bar);
}
function l2GrainEl(F, root, p) {
  const g = C.get(F.value, p);
  if (!C.isObj(g)) return nodeEditor(F, p);
  const gb = g.group_by;
  return h('div', null,
    hasOwn(g, 'group_by') ? (Array.isArray(gb) ? chips(F, p.concat('group_by'), { suggest: l1Columns(root), addText: '+ Layer 1 column' }) : scalar(F, p.concat('group_by'))) : h('button', { class: 'addf', onclick: () => addKey(F, p, 'group_by', []) }, '+ group_by'),
    h('div', { class: 'sub2' }, Array.isArray(gb) && gb.length
      ? 'Layer 1 rows that share ' + gb.join(' + ') + ' collapse into one ' + 'CDM row; the collapsed values come from emits entries with a measure.'
      : 'Empty: one Layer 1 row in, one CDM row out.'),
    Object.keys(g).filter(k => k !== 'group_by').map(k => h('span', { class: 'sf' }, h('span', { class: 'sk' }, k), ' ', nodeEditor(F, p.concat(k)))));
}
function sourceValueEl(F, p) {
  const v = C.get(F.value, p);
  const txt = v === '<raw>' ? '<raw>: the original source string, exactly as read from the file.' : typeof v === 'string' && v !== '' ? 'The literal “' + v + '” on every row.' : v === '' ? 'An empty string on every row.' : '';
  return h('div', null, scalar(F, p, { suggest: ['<raw>'] }), txt ? h('span', { class: 'sub2' }, '  ' + txt) : null);
}
function definingConceptEl(F, root, tPath) {
  const t = C.get(F.value, tPath);
  const p = tPath.concat('defining_concept_id');
  const c = C.get(F.value, p);
  if (!C.isObj(c)) return h('div', null, conceptChip(F, p, { column: TABLE_FIELD[t.table], wantDomain: true, title: 'defining_concept_id' }));
  const field = typeof c.target_field === 'string' && c.target_field ? c.target_field : TABLE_FIELD[t.table];
  const chk = C.conceptDomainCheck(t);
  return h('div', { class: 'dc' },
    conceptChip(F, p, { column: field, wantDomain: true, title: 'defining_concept_id' }),
    chk ? h('span', { class: 'ck ' + chk.status }, (chk.status === 'ok' ? '✓ ' : chk.status === 'warn' ? '⚠ ' : '? ') + chk.text) : null,
    subFields(F, p, [['target_field', 'the CDM column the concept is written to'], ['domain', 'written here so the domain rule reads from the file'], ['vocabulary_id', 'optional provenance'], ['concept_code', 'optional provenance'], ['vocabulary_version', 'optional provenance']], { hide: ['id', 'name', 'concept_id', 'concept_name'] }),
    hasOwn(c, 'target_field') ? null : (TABLE_FIELD[t.table] ? h('button', { class: 'btn small', onclick: () => addKey(F, p, 'target_field', TABLE_FIELD[t.table]) }, 'target_field = ' + TABLE_FIELD[t.table]) : null));
}
function raCell(F, path, col, v) {
  if (col === 'role') return scalar(F, path, { enumKey: 'role' });
  if (col === 'status') return scalar(F, path, { enumKey: 'status' });
  if (col === 'link_id') {
    const links = Array.isArray(F.value.links) ? F.value.links.filter(C.isObj) : [];
    const ids = links.map(l => String(l.link_id));
    const dangling = v !== null && v !== undefined && v !== '' && !ids.includes(String(v));
    return h('span', null, scalar(F, path, { suggest: ids, bad: () => dangling, title: dangling ? 'no link with this link_id in links' : '' }),
      v !== null && v !== undefined && v !== '' && !dangling ? h('button', { class: 'linkbtn', title: 'go to the link', onclick: () => { const i = links.findIndex(l => String(l.link_id) === String(v)); scrollToPath(F, ['links', F.value.links.indexOf(links[i])]); } }, '→') : null,
      dangling ? h('div', { class: 'flagtxt' }, 'no link ' + v + ' in links') : null);
  }
  if (col === 'column') { const t = C.get(F.value, path.slice(0, -3)); return scalar(F, path, { suggest: C.isObj(t) && K.CDM[t.table] ? K.CDM[t.table] : [] }); }
  return null;
}
function targetEl(F, root, tPath, n) {
  const t = C.get(F.value, tPath);
  const coll = isCollapsed(F, tPath);
  const c = C.isObj(t) && C.isObj(t.defining_concept_id) ? C.conceptOf(t.defining_concept_id) : null;
  const head = h('div', { class: 'bhead', onclick: () => toggleCollapsed(F, tPath) },
    h('span', { class: 'tw2' }, coll ? '▸' : '▾'),
    h('span', { class: 't' }, 'Target ' + n + ' · ' + (C.isObj(t) && t.target_id ? t.target_id : '(no target_id)') + ' → ' + (C.isObj(t) && t.table ? t.table : '?')),
    h('span', { class: 's' }, c ? (c.name || '(no name)') + ' · ' + (c.id === null || c.id === undefined ? 'no id' : c.id) : ''),
    h('span', { class: 'acts', onclick: ev => ev.stopPropagation() }, rowActs(F, ['sysbio_etl'], tPath[1], {}), h('button', { class: 'linkbtn', title: 'edit this target as JSON', onclick: () => jsonModal(F, tPath) }, '{ }')));
  const el = h('div', { class: 'target', 'data-path': edKey(F, tPath) }, head);
  if (!C.isObj(t)) { el.append(h('div', { class: 'flagtxt' }, 'This target is not an object.'), nodeEditor(F, tPath)); return el; }
  if (coll) return el;
  const render = {
    target_id: p => scalar(F, p),
    table: p => h('span', null, scalar(F, p, { enumKey: 'table' }), K.CDM[t.table] ? h('span', { class: 'sub2' }, '  ' + K.CDM[t.table].length + ' columns in CDM v5.4') : (t.table ? h('span', { class: 'flagtxt' }, '  not a CDM v5.4 table this browser knows') : null)),
    input: p => (C.isObj(C.get(F.value, p)) ? subFields(F, p, [['element', "'self' or registry_label@registry_etl_version"], ['hash', "sha256 of that element's Layer 1 output table"]]) : scalar(F, p, { suggest: ['self'] })),
    defining_concept_id: () => definingConceptEl(F, root, tPath),
    anchored_to: () => keysPanel(F, root, tPath),
    grain: p => l2GrainEl(F, root, p),
    source_value: p => sourceValueEl(F, p),
    qualifier_concept_id: p => conceptChip(F, p, { column: 'qualifier_concept_id', title: 'qualifier_concept_id (every row of this target)' }),
    omop_value_set: p => objTable(F, p, K.OVS_COLUMNS, { rowName: 'concept', extraBar: h('button', { class: 'btn small', onclick: ev => {
      const arr = C.get(F.value, p);
      const useIdName = Array.isArray(arr) && arr.some(x => C.isObj(x) && 'id' in x);
      openConceptPop(F, p, { title: 'Add a concept to omop_value_set', onPick: hit => arrInsert(F, p, C.get(F.value, p).length, useIdName ? { id: hit.concept_id, name: hit.concept_name } : { concept_id: hit.concept_id, concept_name: hit.concept_name }) }, ev.currentTarget);
    } }, '+ from OMOP Hub') }),
    record_attributes: p => objTable(F, p, K.RA_COLUMNS, { rowName: 'attribute', cell: raCell, always: ['role'] }),
    emits: p => objTable(F, p, K.EMITS_COLUMNS, { rowName: 'column', always: ['cdm_column'], cell: (F2, cp, col) => (col === 'cdm_column' ? scalar(F2, cp, { suggest: K.CDM[t.table] || [] }) : col === 'measure' ? scalar(F2, cp, { enumKey: 'measure' }) : null) }),
    note: p => scalar(F, p, { prose: true }),
    status_note: p => scalar(F, p, { prose: true })
  };
  for (const [k, hp] of K.TARGET_FIELDS) {
    const p = tPath.concat(k);
    if (k === 'anchored_to') { el.append(fieldRow(F, tPath, k, hp, keysPanel(F, root, tPath), { noDelete: !hasOwn(t, k) })); continue; }
    if (!hasOwn(t, k)) continue;
    if (k === 'value_map') {
      put(el, h('div', { class: 'subhead', 'data-path': edKey(F, p) }, 'value_map — the fan-out', h('span', { class: 'sub2' }, 'one entry per harmonized value; each names every CDM column of the row it fills'),
        h('button', { class: 'linkbtn warn', title: 'remove value_map', onclick: () => delPath(F, p) }, '×')),
      Array.isArray(t.value_map) ? l2Grid(F, root, tPath) : nodeEditor(F, p), noteEl(F, tPath, k));
      continue;
    }
    el.append(fieldRow(F, tPath, k, hp, render[k] ? render[k](p) : nodeEditor(F, p)));
  }
  put(el, absentLine(F, tPath, K.TARGET_FIELDS.filter(f => f[0] !== 'anchored_to'), {
    input: { element: 'self' }, defining_concept_id: () => ({ id: null, name: '', domain: '', target_field: TABLE_FIELD[t.table] || '' }), grain: { group_by: [] }, source_value: '<raw>',
    qualifier_concept_id: { id: null, name: '' }, omop_value_set: [], record_attributes: [], value_map: () => C.allHarmonizedValues(root).map(hv => ({ harmonized_value: hv })), emits: []
  }, TARGET_ORDER, 'Not in this target:'));
  const others = otherRows(F, tPath, new Set(TARGET_ORDER), 'Other fields in this target');
  if (others) el.append(others);
  return el;
}
/* Every harmonized value across every target: where each value lands. */
function byValueEl(F, root) {
  const tg = C.targets(root);
  const rows = C.l2ByValue(root);
  const table = h('table', { class: 't' });
  table.append(h('thead', null, h('tr', null, h('th', null, 'harmonized value'), tg.map((t, i) => h('th', null, 'Target ' + (i + 1) + ' · ' + (C.isObj(t) ? (t.target_id || '') + ' → ' + (t.table || '?') : '?'))))));
  const tb = h('tbody');
  for (const r of rows) {
    tb.append(h('tr', null, h('td', { class: 'hv' }, r.hv), r.landings.map(l => {
      const vmPath = ['sysbio_etl', l.ti, 'value_map'];
      if (l.entryIndex === null) return h('td', { class: 'missingc' }, h('span', { class: 'flagtxt' }, 'no entry '), Array.isArray(C.get(F.value, vmPath)) ? h('button', { class: 'btn small', onclick: () => arrInsert(F, vmPath, insertEntryFor(F, root, vmPath, r.hv), { harmonized_value: r.hv }) }, '+ entry') : null);
      const e = l.entry;
      const lines = C.isObj(e) ? Object.keys(e).filter(k => k !== 'harmonized_value').map(k => h('div', { class: 'land' }, h('span', { class: 'mono sub2' }, k), ' ', valueText(e[k]))) : [h('div', null, valueText(e))];
      return h('td', { class: 'landc', title: 'click to edit in the target', onclick: () => { S.sheet.l2View = 'target'; scrollToPath(F, vmPath.concat(l.entryIndex)); } }, lines.length ? lines : h('span', { class: 'sub2' }, '(entry with no columns)'));
    })));
  }
  table.append(tb);
  return h('div', { class: 'tw' }, table);
}
function targetsCard(F) {
  const root = F.value;
  const tg = root.sysbio_etl;
  const card = h('div', { class: 'card l2card', 'data-path': edKey(F, ['sysbio_etl']) });
  const n = Array.isArray(tg) ? tg.length : 0;
  const view = S.sheet.l2View;
  card.append(h('h3', null, 'Layer 2 · CDM targets', h('span', { class: 'sub' }, n + ' target' + (n === 1 ? '' : 's') + ' · one target = one kind of CDM row: one table, one defining concept, the same keys'),
    n ? h('span', { class: 'tabs small' }, h('button', { class: view === 'target' ? 'on' : '', onclick: () => { S.sheet.l2View = 'target'; scheduleRender(); } }, 'By target'), h('button', { class: view === 'value' ? 'on' : '', onclick: () => { S.sheet.l2View = 'value'; scheduleRender(); } }, 'By harmonized value')) : null));
  const nn = noteEl(F, [], 'sysbio_etl');
  if (nn) card.append(nn);
  if (!hasOwn(root, 'sysbio_etl')) { card.append(h('button', { class: 'btn small', onclick: () => addKeyOrdered(F, [], 'sysbio_etl', [], ELEMENT_ORDER) }, '+ sysbio_etl')); return card; }
  if (!Array.isArray(tg)) { card.append(nodeEditor(F, ['sysbio_etl'])); return card; }
  if (view === 'value' && n) card.append(byValueEl(F, root));
  else tg.forEach((t, i) => card.append(targetEl(F, root, ['sysbio_etl', i], i + 1)));
  card.append(h('div', { class: 'sideacts' }, h('button', { class: 'btn small', onclick: () => {
    const nt = { target_id: '', table: '', defining_concept_id: { id: null, name: '', domain: '', target_field: '' }, anchored_to: { person_id: anchorSuggest('person_id') }, source_value: '<raw>', record_attributes: [], value_map: C.allHarmonizedValues(root).map(hv => ({ harmonized_value: hv })) };
    S.pendingOpen = edKey(F, ['sysbio_etl', tg.length, 'target_id']);
    arrInsert(F, ['sysbio_etl'], tg.length, nt);
  } }, '+ target'), h('span', { class: 'sub2' }, 'a new target gets one value_map entry per harmonized value; ⧉ duplicates a target')));
  return card;
}

/* ── links and policies ── */
function linksCard(F) {
  const root = F.value;
  const links = root.links;
  const card = h('div', { class: 'card', 'data-path': edKey(F, ['links']) });
  const n = Array.isArray(links) ? links.length : 0;
  card.append(h('h3', null, 'Links', h('span', { class: 'sub' }, n + ' · how rows of this element tie to rows of another element or target; pointed at by record_attributes.link_id')));
  const nn = noteEl(F, [], 'links');
  if (nn) card.append(nn);
  if (!hasOwn(root, 'links')) { card.append(h('button', { class: 'btn small', onclick: () => addKeyOrdered(F, [], 'links', [], ELEMENT_ORDER) }, '+ links')); return card; }
  if (!Array.isArray(links)) { card.append(nodeEditor(F, ['links'])); return card; }
  const users = new Map();
  C.targets(root).forEach((t, ti) => { if (C.isObj(t) && Array.isArray(t.record_attributes)) t.record_attributes.forEach((ra, ri) => { if (C.isObj(ra) && ra.link_id !== undefined && ra.link_id !== null && ra.link_id !== '') { const k = String(ra.link_id); if (!users.has(k)) users.set(k, []); users.get(k).push({ ti, ri, role: ra.role, t }); } }); });
  links.forEach((l, i) => {
    const lp = ['links', i];
    const coll = isCollapsed(F, lp);
    const head = h('div', { class: 'bhead', onclick: () => toggleCollapsed(F, lp) }, h('span', { class: 'tw2' }, coll ? '▸' : '▾'),
      h('span', { class: 't' }, 'Link ' + (C.isObj(l) ? l.link_id : '?') + ' · ' + (C.isObj(l) ? (l.kind || '?') + ' → ' + (l.linked_element_label || '?') + (l.linked_table ? ' (' + l.linked_table + ')' : '') : '')),
      h('span', { class: 's' }, C.isObj(l) ? (l.linking_mechanism || '') : ''),
      h('span', { class: 'acts', onclick: ev => ev.stopPropagation() }, rowActs(F, ['links'], i, {}), h('button', { class: 'linkbtn', onclick: () => jsonModal(F, lp) }, '{ }')));
    const el = h('div', { class: 'block lk', 'data-path': edKey(F, lp) }, head);
    card.append(el);
    if (coll) return;
    if (!C.isObj(l)) { el.append(nodeEditor(F, lp)); return; }
    const u = users.get(String(l.link_id)) || [];
    el.append(h('div', { class: 'sub2' }, u.length ? 'Used by: ' : 'No record_attributes entry points at this link.', u.map(x => h('button', { class: 'linkbtn', onclick: () => scrollToPath(F, ['sysbio_etl', x.ti, 'record_attributes', x.ri]) }, 'target ' + (x.ti + 1) + ' ' + (x.t.target_id || x.t.table || '') + ' (' + (x.role || 'no role') + ')'))));
    const render = {
      kind: p => scalar(F, p, { enumKey: 'kind' }),
      linked_element_label: p => {
        const v = C.get(F.value, p);
        const target = typeof v === 'string' && v ? Array.from(S.files.values()).find(G => G.sum && G.sum.label === v) : null;
        return h('span', null, scalar(F, p, { suggest: Array.from(S.files.values()).map(G => G.sum ? G.sum.label : '').filter(Boolean) }),
          target ? h('button', { class: 'linkbtn', title: 'open ' + target.id, onclick: () => openFile(target.id) }, ' open →') : (typeof v === 'string' && v ? h('span', { class: 'sub2' }, '  (no file with this registry_label in this folder)') : null));
      },
      linked_table: p => scalar(F, p, { enumKey: 'linked_table' }),
      linked_defining_concept: p => conceptChip(F, p, { column: 'linked_defining_concept' }),
      linked_value_set: p => (Array.isArray(C.get(F.value, p)) ? chips(F, p, {}) : scalar(F, p)),
      linking_mechanism: p => scalar(F, p, { enumKey: 'linking_mechanism' }),
      linking_mechanism_concept_id: p => conceptChip(F, p, { column: 'linking_mechanism_concept_id' }),
      inverse_concept_id: p => conceptChip(F, p, { column: 'inverse_concept_id' }),
      note: p => scalar(F, p, { prose: true })
    };
    for (const k of K.LINK_COLUMNS) {
      if (!hasOwn(l, k)) continue;
      const p = lp.concat(k);
      el.append(fieldRow(F, lp, k, K.LINK_HELP[k], render[k] ? render[k](p) : scalar(F, p)));
    }
    put(el, absentLine(F, lp, K.LINK_COLUMNS.map(k => [k, K.LINK_HELP[k]]), { linked_defining_concept: { id: null, name: '' }, linked_value_set: [], linking_mechanism_concept_id: { id: null, name: '' }, inverse_concept_id: { id: null, name: '' } }, K.LINK_COLUMNS, 'Not in this link:'));
    const others = otherRows(F, lp, new Set(K.LINK_COLUMNS), 'Other fields in this link');
    if (others) el.append(others);
  });
  card.append(h('div', { class: 'sideacts' }, h('button', { class: 'btn small', onclick: () => {
    const ids = links.filter(C.isObj).map(l => Number(l.link_id)).filter(x => isFinite(x));
    const next = String(ids.length ? Math.max(...ids) + 1 : 1);
    arrInsert(F, ['links'], links.length, { link_id: next, kind: '', linked_element_label: '', linked_table: '', linking_mechanism: '' });
    S.pendingOpen = edKey(F, ['links', links.length - 1, 'kind']);
  } }, '+ link')));
  return card;
}
function policiesCard(F) {
  const root = F.value;
  const card = h('div', { class: 'card', 'data-path': edKey(F, ['policies']) }, h('h3', null, 'Policies', h('span', { class: 'sub' }, 'guards on emitted strings, checked at load')));
  const nn = noteEl(F, [], 'policies');
  if (nn) card.append(nn);
  if (!hasOwn(root, 'policies')) { card.append(h('button', { class: 'btn small', onclick: () => addKeyOrdered(F, [], 'policies', [], ELEMENT_ORDER) }, '+ policies')); return card; }
  card.append(objTable(F, ['policies'], K.POLICY_COLUMNS, { rowName: 'policy', always: ['field', 'split_on', 'assert', 'set'], cell: (F2, p, col) => (col === 'assert' ? scalar(F2, p, { enumKey: 'assert' }) : col === 'split_on' ? (Array.isArray(C.get(F2.value, p)) ? chips(F2, p, {}) : null) : null),
    newRow: () => ({ field: '', split_on: [], assert: 'no_token_in', set: '' }) }));
  return card;
}

/* ── raw JSON: the exact text that Save writes ── */
function diffEl(aText, bText) {
  const d = C.lineDiff(aText, bText);
  if (!d) return h('div', { class: 'sub2' }, 'Too large to compare line by line.');
  if (!d.changed) return h('div', { class: 'sub2' }, 'No differences: Save would write the file exactly as it is on disk.');
  const box = h('div', { class: 'diff' });
  const ops = d.ops;
  const ctx = 3;
  const keep = new Array(ops.length).fill(false);
  ops.forEach((o, i) => { if (o.t !== '=') for (let j = Math.max(0, i - ctx); j <= Math.min(ops.length - 1, i + ctx); j++) keep[j] = true; });
  let skipping = false;
  if (d.prefix > 0) box.append(h('div', { class: 'h' }, '… ' + d.prefix + ' unchanged lines'));
  ops.forEach((o, i) => {
    if (!keep[i]) { if (!skipping) { box.append(h('div', { class: 'h' }, '…')); skipping = true; } return; }
    skipping = false;
    const num = o.t === '+' ? o.b + 1 : o.a + 1;
    box.append(h('div', { class: o.t === '+' ? 'a' : o.t === '-' ? 'd' : '' }, (o.t === '=' ? ' ' : o.t) + String(num).padStart(5) + '  ' + o.line));
  });
  return h('div', null, h('div', { class: 'sub2' }, d.changed + ' line' + (d.changed === 1 ? '' : 's') + ' differ (− on disk, + what Save writes)'), box);
}
function currentText(F) { return F.value === undefined ? F.diskText : C.stringifyJSON(F.value, F.meta); }
function rawView(F) {
  const mode = S.sheet.rawMode;
  const box = h('div', { class: 'raw card' }, h('h3', null, 'Raw JSON', h('span', { class: 'tabs small' },
    h('button', { class: mode === 'edit' ? 'on' : '', onclick: () => { S.sheet.rawMode = 'edit'; scheduleRender(); } }, 'Text that Save writes'),
    h('button', { class: mode === 'diff' ? 'on' : '', onclick: () => { S.sheet.rawMode = 'diff'; scheduleRender(); } }, 'Difference from the file on disk'))));
  if (mode === 'diff') { box.append(diffEl(F.diskText, currentText(F))); return box; }
  const ta = h('textarea', { spellcheck: 'false' });
  ta.value = currentText(F);
  const err = h('div', { class: 'flagtxt' });
  ta.addEventListener('keydown', ev => { ev.stopPropagation(); if (ev.key === 'Tab') { ev.preventDefault(); const s = ta.selectionStart; ta.setRangeText('  ', s, ta.selectionEnd, 'end'); } if ((ev.ctrlKey || ev.metaKey) && ev.key === 'Enter') applyRaw(); });
  function applyRaw() {
    let parsed;
    try { parsed = C.parseJSONText(ta.value); } catch (e) { err.textContent = 'Not valid JSON: ' + e.message; return; }
    err.textContent = '';
    if (F.value === undefined) {
      F.error = null; F.value = parsed.value; F.meta = parsed.meta; F.base = undefined; F.undo = []; F.redo = [];
      afterChange(F);
      toast('Parsed. Save writes this text.', 'ok');
      return;
    }
    mutate(F, () => { F.value = parsed.value; F.meta.rawNums = parsed.meta.rawNums; F.meta.keyOrder = parsed.meta.keyOrder; });
    toast('Applied to the sheet (not saved yet).', 'ok');
  }
  box.append(h('div', { class: 'sub2' }, 'Edit and press Apply (Ctrl+Enter). Nothing is written to disk until you Save.'), ta, err,
    h('div', { class: 'sideacts' }, h('button', { class: 'btn pri', onclick: applyRaw }, 'Apply'), h('button', { class: 'btn', onclick: () => { ta.value = currentText(F); err.textContent = ''; } }, 'Reset text')));
  return box;
}

/* ── the whole sheet for one file ── */
function sheetHeader(F, pane) {
  const s = F.sum || C.summarize(F.id, F.value);
  const tags = [s.schema ? s.schema.replace('harmonized-element/', 'schema ') : null, s.programs.join(', ') || null,
    s.nBlocks + ' block' + (s.nBlocks === 1 ? '' : 's'), s.nTargets + ' target' + (s.nTargets === 1 ? '' : 's'), s.nLinks ? s.nLinks + ' link' + (s.nLinks === 1 ? '' : 's') : null,
    s.tables.length ? s.tables.join(', ') : null].filter(Boolean);
  const other = pane === 'compare';
  return h('div', { class: 'shead' },
    h('h2', null, s.label),
    F.name !== s.label + '.json' ? h('span', { class: 'fn' }, F.id) : null,
    tags.map(t => h('span', { class: 'tag' }, t)),
    F.dirty ? h('span', { class: 'badge edit' }, 'edited') : null,
    h('span', { class: 'spacer' }),
    other ? h('button', { class: 'btn small', title: 'Save this file (read back after writing)', disabled: !F.dirty || S.mode !== 'rw' ? true : null, onclick: () => saveFile(F) }, 'Save') : null,
    other ? h('button', { class: 'btn small', title: 'make this the main file', onclick: () => { const a = S.current; S.current = S.compare; S.compare = a; scheduleRender(); } }, '⇄') : null,
    other ? h('button', { class: 'btn small', title: 'close the second file', onclick: () => { S.compare = null; scheduleRender(); } }, '✕') : null,
    !other ? h('span', { class: 'tabs small' },
      h('button', { class: S.sheet.raw ? '' : 'on', onclick: () => { S.sheet.raw = false; scheduleRender(); } }, 'Sheet'),
      h('button', { class: S.sheet.raw ? 'on' : '', onclick: () => { S.sheet.raw = true; scheduleRender(); } }, 'Raw JSON')) : null,
    !other ? h('button', { class: 'btn small', title: 'Open a second file next to this one', onclick: ev => pickCompare(ev.currentTarget) }, 'Side by side…') : null);
}
function sheetFor(F, pane) {
  const box = h('div', { class: 'sheet', 'data-file': F.id });
  box.append(sheetHeader(F, pane));
  if (F.value === undefined) {
    box.append(h('div', { class: 'banner warn' }, h('b', null, 'This file is not valid JSON. '), F.error ? F.error.message : '', ' Fix it in the text below and press Apply; Save then writes it.'));
    box.append(rawView(F));
    return box;
  }
  if (F.meta.dupKeys && F.meta.dupKeys.length) box.append(h('div', { class: 'banner warn' }, h('b', null, 'Duplicate keys: '), F.meta.dupKeys.slice(0, 8).map(d => (typeof d === 'string' ? d : JSON.stringify(d))).join(', '), '. The sheet shows the last value of each; Save keeps only that one.'));
  if (F.roundTrip === false) box.append(h('div', { class: 'banner info' }, 'This file is not laid out the way Python json.dump(indent=2) writes it, so Save rewrites ', F.rtLines === undefined ? 'some' : String(F.rtLines), ' line' + (F.rtLines === 1 ? '' : 's') + ' of layout even before you edit. ', h('button', { class: 'linkbtn', onclick: () => { S.sheet.raw = true; S.sheet.rawMode = 'diff'; scheduleRender(); } }, 'show them')));
  if (!C.isObj(F.value)) { box.append(h('div', { class: 'banner warn' }, 'The file holds a ' + (Array.isArray(F.value) ? 'list' : typeof F.value) + ', not an element object.'), nodeEditor(F, [])); return box; }
  if (pane !== 'compare' && S.sheet.raw) { box.append(rawView(F)); return box; }
  box.append(elementCard(F), sourcesCard(F), targetsCard(F), linksCard(F), policiesCard(F));
  return box;
}
function pickCompare(anchor) {
  const inp = h('input', { type: 'text', placeholder: 'file label…' });
  const list = h('div', { class: 'picklist' });
  const draw = () => {
    const qv = inp.value.toLowerCase();
    const items = libraryOrder().filter(id => id !== S.current).map(id => S.files.get(id)).filter(G => !qv || (G.sum ? G.sum.label : G.id).toLowerCase().includes(qv)).slice(0, 60);
    list.replaceChildren(...items.map(G => h('div', { class: 'cli', onclick: () => { closePop(); S.compare = G.id; scheduleRender(); } }, G.sum ? G.sum.label : G.id)));
  };
  inp.addEventListener('input', draw);
  inp.addEventListener('keydown', ev => { ev.stopPropagation(); if (ev.key === 'Escape') closePop(); if (ev.key === 'Enter') { const f = list.querySelector('.cli'); if (f) f.click(); } });
  draw();
  openPop(anchor, h('div', null, h('h4', null, 'Open a second file next to this one'), inp, list));
  inp.focus();
}
