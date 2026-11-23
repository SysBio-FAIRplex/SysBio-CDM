/* ───────────── clusters: files that share labels, columns, files, values, concepts, grains ───────────── */
const CL_EDIT = { forms: 'sources[*].layer_1_etl.value_form', units: 'sources[*].layer_1_etl.unit', curie: 'harmonized_element_curie', programs: 'programs_covered' };
function saveClOpts() { const o = Object.assign({}, S.cl); LS.set('clusterOpts', o); S.clCache = null; scheduleRender(); }
function clusterList() {
  const key = JSON.stringify([S.cl.dims, S.cl.labelMode, S.cl.editDistance, S.cl.maxWordShare, S.cl.minWordLength, S.cl.jaccard, S.cl.minSize, S.cl.onlyFiltered, S.cl.onlyFiltered ? S.lib.filter : '']);
  if (S.clCache && S.clCache.key === key) return S.clCache.list;
  const ids = S.cl.onlyFiltered ? libraryOrder(true) : Array.from(S.files.keys());
  const sums = ids.map(id => S.files.get(id)).filter(F => F && F.sum).map(F => F.sum);
  const list = C.clusters(sums, S.cl.dims, S.cl).filter(c => c.members.length >= Math.max(2, Number(S.cl.minSize) || 2));
  S.clCache = { key, list };
  return list;
}
function clusterStep(d) {
  const reviewed = LS.get('clReviewed', {});
  const list = clusterList().filter(c => !S.cl.hideReviewed || !reviewed[c.key]);
  if (!list.length) return;
  const i = list.findIndex(c => c.key === S.clSel);
  const n = i < 0 ? 0 : Math.max(0, Math.min(list.length - 1, i + d));
  selectCluster(list[n]);
}
function selectCluster(c) { S.clSel = c.key; S.clSelIds = c.ids.slice(); S.clSelLabel = c.label; S.clTicked = new Set(); scheduleRender(); }
function cellValues(F, col) {
  if (col.pattern) return C.patternValues(F.value, col.pattern);
  return null;
}
function cellString(F, col) {
  if (F.value === undefined) return '';
  if (col.pattern) return cellValues(F, col).map(x => (x.value !== null && typeof x.value === 'object' ? JSON.stringify(x.value) : String(x.value))).join(' | ');
  return C.compareCell(F.sum, col.id);
}
function clusterCell(F, col) {
  if (F.value === undefined) return h('span', { class: 'flagtxt' }, 'not valid JSON');
  const pattern = col.pattern || CL_EDIT[col.id];
  if (!pattern) return h('span', { class: 'ro' }, C.compareCell(F.sum, col.id) || h('span', { class: 'sub2' }, '—'));
  const vals = C.patternValues(F.value, pattern);
  if (!vals.length) return h('span', { class: 'sub2', title: pattern }, '—');
  return h('div', { class: 'clvals' }, vals.slice(0, 12).map(x => {
    const v = x.value;
    let el;
    if (Array.isArray(v) && v.every(y => y === null || typeof y !== 'object')) el = chips(F, x.path, {});
    else if (C.isConcept(v)) el = conceptChip(F, x.path, { column: String(x.path[x.path.length - 1]) });
    else if (v !== null && typeof v === 'object') el = h('button', { class: 'linkbtn', title: JSON.stringify(v).slice(0, 400), onclick: () => scrollToPath(F, x.path) }, C.describe(v, 50));
    else el = scalar(F, x.path, { enumKey: (K.ENUMS[x.path[x.path.length - 1]] ? x.path[x.path.length - 1] : undefined) });
    return h('div', { class: 'clv' }, vals.length > 1 ? h('span', { class: 'sub2 mono' }, C.pathStr(x.path.slice(0, -1)).replace(/^sources/, 's').replace('.layer_1_etl', '') + ' ') : null, el);
  }), vals.length > 12 ? h('div', { class: 'sub2' }, '… ' + (vals.length - 12) + ' more') : null);
}
function clusterDetail() {
  const box = h('div', { class: 'cldetail', 'data-keep-scroll': 'cldetail' });
  if (!S.clSelIds) { box.append(h('div', { class: 'sub2' }, 'Pick a cluster on the left (j / k step through them).')); return box; }
  const members = S.clSelIds.map(id => S.files.get(id)).filter(Boolean);
  const reviewed = LS.get('clReviewed', {});
  const isRev = !!reviewed[S.clSel];
  const stillThere = clusterList().some(c => c.key === S.clSel);
  const cols = C.COMPARE_COLUMNS.map(c => ({ id: c.id, name: c.name })).concat((S.cl.extraCols || []).map(p => ({ id: 'x:' + p, name: p, pattern: p, extra: true })));
  const ticked = members.filter(F => S.clTicked.has(F.id));
  box.append(h('div', { class: 'shead' }, h('h2', null, S.clSelLabel || ''), h('span', { class: 'tag' }, members.length + ' files'), isRev ? h('span', { class: 'badge fmt' }, 'reviewed') : null,
    h('span', { class: 'spacer' }),
    h('button', { class: 'btn small', onclick: () => { const r = LS.get('clReviewed', {}); if (r[S.clSel]) delete r[S.clSel]; else r[S.clSel] = Date.now(); LS.set('clReviewed', r); scheduleRender(); } }, isRev ? 'Unmark reviewed' : 'Mark reviewed'),
    h('button', { class: 'btn small', disabled: ticked.length !== 2 ? true : null, title: 'tick two files', onclick: () => { S.current = ticked[0].id; S.compare = ticked[1].id; S.tab = 'files'; scheduleRender(); } }, 'Side by side (tick 2)')));
  if (!stillThere) box.append(h('div', { class: 'banner info' }, 'This group no longer forms under the current settings or edits; the files stay listed until you pick another cluster.'));
  /* tint: the value most members share, per column */
  const common = {};
  for (const col of cols) {
    const counts = new Map();
    for (const F of members) { const s = cellString(F, col); if (s) counts.set(s, (counts.get(s) || 0) + 1); }
    const best = Array.from(counts.entries()).sort((a, b) => b[1] - a[1])[0];
    common[col.id] = best && best[1] >= 2 ? best[0] : null;
  }
  const table = h('table', { class: 't clt' });
  table.append(h('thead', null, h('tr', null, h('th', null, ''), h('th', null, 'file'),
    cols.map(c => h('th', { title: c.pattern || (CL_EDIT[c.id] ? 'editable: ' + CL_EDIT[c.id] : 'summary') }, c.name, c.extra ? h('button', { class: 'linkbtn warn', title: 'remove this column', onclick: () => { S.cl.extraCols = S.cl.extraCols.filter(x => x !== c.pattern); saveClOpts(); } }, ' ×') : null)))));
  const tb = h('tbody');
  for (const F of members) {
    const cb = h('input', { type: 'checkbox' });
    cb.checked = S.clTicked.has(F.id);
    cb.addEventListener('change', () => { if (cb.checked) S.clTicked.add(F.id); else S.clTicked.delete(F.id); scheduleRender(); });
    tb.append(h('tr', null, h('td', null, cb),
      h('td', { class: 'clfile' }, h('button', { class: 'linkbtn', title: 'open ' + F.id, onclick: () => openFile(F.id) }, F.sum.label), F.dirty ? h('span', { class: 'badge edit' }, 'edited') : null, h('div', { class: 'sub2' }, pl(F.sum.nBlocks, 'block') + ' · ' + pl(F.sum.nTargets, 'target'))),
      cols.map(col => h('td', { class: common[col.id] && cellString(F, col) === common[col.id] ? 'tint' : '' }, clusterCell(F, col)))));
  }
  table.append(tb);
  const add = h('input', { type: 'text', placeholder: '+ column: a field path, e.g. sysbio_etl[*].anchored_to or sources[*].loading_grain.entity', style: 'width:460px' });
  add.addEventListener('keydown', ev => {
    ev.stopPropagation();
    if (ev.key === 'Enter' && add.value.trim()) { S.cl.extraCols = (S.cl.extraCols || []).concat(add.value.trim()); saveClOpts(); }
  });
  add.setAttribute('list', datalistFor('clpaths', ['definition', 'harmonized_values', 'sources[*].source_label', 'sources[*].layer_1_etl.value_form', 'sources[*].layer_1_etl.unit', 'sources[*].loading_grain', 'sources[*].layer_1_etl.data_files[*].sha256', 'sysbio_etl[*].table', 'sysbio_etl[*].defining_concept_id', 'sysbio_etl[*].anchored_to', 'sysbio_etl[*].value_map', 'links[*].linked_element_label', 'one_per', 'registry_label']));
  box.append(h('div', { class: 'tw' }, table), h('div', { class: 'tablebar' }, add, h('span', null, 'Shaded cells hold the value most of these files share. Values in editable columns save to their own file.')));
  return box;
}
function renderClusters() {
  const list = clusterList();
  const reviewed = LS.get('clReviewed', {});
  const ctl = h('div', { class: 'clctl', 'data-keep-scroll': 'clctl' });
  ctl.append(h('h4', null, 'Group files that share'));
  for (const d of C.DIMENSIONS) {
    const cb = h('input', { type: 'checkbox' });
    cb.checked = S.cl.dims.includes(d.id);
    cb.addEventListener('change', () => { S.cl.dims = cb.checked ? S.cl.dims.concat(d.id) : S.cl.dims.filter(x => x !== d.id); saveClOpts(); });
    ctl.append(h('label', { title: d.help }, cb, h('span', null, d.name, h('div', { class: 'sub2' }, d.help))));
  }
  ctl.append(h('div', { class: 'sub2' }, S.cl.dims.length > 1 ? 'Several ticked: a file joins a group only when it matches on all of them.' : 'Tick several to require a match on all of them.'));
  const num = (key, label, step, min, max) => {
    const i = h('input', { type: 'number', value: S.cl[key], step: step || 1, min: min !== undefined ? min : '', max: max !== undefined ? max : '' });
    i.addEventListener('change', () => { S.cl[key] = Number(i.value); saveClOpts(); });
    i.addEventListener('keydown', ev => ev.stopPropagation());
    return h('label', null, h('span', null, label), i);
  };
  if (S.cl.dims.includes('labelWord')) {
    const sel = h('select', null, [['word', 'share a word'], ['first', 'same first word'], ['edit', 'within a few edits']].map(([v, t]) => { const o = h('option', { value: v }, t); if (S.cl.labelMode === v) o.selected = true; return o; }));
    sel.addEventListener('change', () => { S.cl.labelMode = sel.value; saveClOpts(); });
    ctl.append(h('h4', null, 'Similar labels'), h('label', null, h('span', null, 'Labels '), sel));
    if (S.cl.labelMode === 'word') ctl.append(num('minWordLength', 'shortest word ', 1, 1), num('maxWordShare', 'skip words in more than … files ', 1, 2));
    if (S.cl.labelMode === 'edit') ctl.append(num('editDistance', 'edits at most ', 1, 1, 6));
  }
  if (S.cl.dims.includes('valueOverlap')) ctl.append(h('h4', null, 'Overlapping values'), num('jaccard', 'overlap at least (0–1) ', 0.05, 0.05, 1));
  const hide = h('input', { type: 'checkbox' }); hide.checked = !!S.cl.hideReviewed;
  hide.addEventListener('change', () => { S.cl.hideReviewed = hide.checked; saveClOpts(); });
  const onlyF = h('input', { type: 'checkbox' }); onlyF.checked = !!S.cl.onlyFiltered;
  onlyF.addEventListener('change', () => { S.cl.onlyFiltered = onlyF.checked; saveClOpts(); });
  ctl.append(h('h4', null, 'Show'), num('minSize', 'groups of at least ', 1, 2), h('label', null, hide, h('span', null, 'hide groups marked reviewed')), h('label', null, onlyF, h('span', null, 'only files that pass the library filter')));
  const shown = list.filter(c => !S.cl.hideReviewed || !reviewed[c.key]);
  ctl.append(h('h4', null, shown.length + ' group' + (shown.length === 1 ? '' : 's') + (list.length !== shown.length ? ' (' + (list.length - shown.length) + ' reviewed hidden)' : '')));
  if (!S.cl.dims.length) ctl.append(h('div', { class: 'sub2' }, 'Tick at least one dimension.'));
  for (const c of shown.slice(0, 600)) ctl.append(h('div', { class: 'cli' + (c.key === S.clSel ? ' on' : '') + (reviewed[c.key] ? ' rev' : ''), title: c.ids.join('\n'), onclick: () => selectCluster(c) }, h('span', null, c.label), h('span', { class: 'n' }, c.members.length)));
  if (shown.length > 600) ctl.append(h('div', { class: 'sub2' }, '… ' + (shown.length - 600) + ' more; narrow the settings.'));
  return h('div', { class: 'cl' }, ctl, clusterDetail());
}
