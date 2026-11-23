const fs = require('fs'), path = require('path');
const Core = require('../src/core.js');
const dir = process.argv[2] || path.join(__dirname, 'fixtures');
const files = fs.readdirSync(dir).filter(f => f.endsWith('.json')).sort();
let exact = 0, notExact = [], parseFail = [];
const sums = [];
for (const f of files) {
  const t = fs.readFileSync(path.join(dir, f), 'utf8');
  let r;
  try { r = Core.parseJSONText(t); } catch (e) { parseFail.push(f + ': ' + e.message); continue; }
  const std = JSON.parse(t);
  if (JSON.stringify(std) !== JSON.stringify(r.value)) console.log('VALUE MISMATCH vs JSON.parse', f);
  const out = Core.stringifyJSON(r.value, r.meta);
  if (out === t) exact++; else { const d = Core.lineDiff(t, out); notExact.push(f + ' (' + (d ? d.changed : '?') + ' lines)'); }
  const s = Core.summarize(f, r.value); sums.push(s);
  // exercise every model
  for (const { block } of Core.blocks(r.value)) Core.blockGrain(r.value, block);
  for (const t2 of Core.targets(r.value)) { Core.targetKeys(r.value, t2); Core.l2Grid(r.value, t2); Core.conceptDomainCheck(t2); }
  Core.l2ByValue(r.value);
}
console.log('files', files.length, 'round-trip exact', exact, 'not exact', notExact.length, notExact.slice(0, 10), 'parse fail', parseFail);
const show = n => { const r = Core.parseJSONText(fs.readFileSync(path.join(dir, n), 'utf8')).value; return r; };
const eg = show('egfr_ckd_epi_2021_creatinine_serum.json');
Core.blocks(eg).forEach(b => console.log('GRAIN', JSON.stringify(Core.blockGrain(eg, b.block))));
console.log('KEYS', JSON.stringify(Core.targetKeys(eg, eg.sysbio_etl[0]).check), Core.targetKeys(eg, eg.sysbio_etl[0]).resultText);
const rl = show('msq_v2011_item3_restless_legs.json');
console.log('GRAIN one_per', Core.blockGrain(rl, rl.sources[0]).readsAs);
rl.sysbio_etl.forEach(t => { const g = Core.l2Grid(rl, t); console.log('GRID', t.table, g.columns.map(c => c.key + (c.isColumn === false ? '(!)' : '')).join(','), g.rows.map(r => r.hv + ':' + (r.entryIndex === null ? 'MISSING' : r.entryIndex) + (r.flags.length ? '[' + r.flags + ']' : '')).join(' | ')); console.log('KEYS', Core.targetKeys(rl, t).check.status, Core.targetKeys(rl, t).check.text); console.log('DOMAIN', JSON.stringify(Core.conceptDomainCheck(t))); });
const pd = show('prodromal_category.json');
pd.sysbio_etl.forEach(t => { const g = Core.l2Grid(pd, t); console.log('GRID prodromal', g.rows.map(r => r.hv + ':' + (r.entryIndex === null ? 'MISSING' : r.entryIndex)).join(' | ')); });
for (const d of Core.DIMENSIONS) { const c = Core.clusters(sums, [d.id], { labelMode: 'word', jaccard: 0.5 }); console.log('CLUSTERS', d.id, c.length, c.slice(0, 3).map(x => x.label + ' (' + x.ids.length + ')').join(' ; ')); }
console.log('COMBINED', Core.clusters(sums, ['pinnedFile', 'grain'], {}).map(x => x.label + ' ' + x.ids.join(',')).slice(0, 3));
// diff test
const a = show('initial_diagnosis.json'); const b = Core.clone(a);
b.sources[0].layer_1_etl.value_map.splice(1, 1); b.harmonized_values[0] = "Parkinson disease"; b.sysbio_etl[0].value_map[0].note = 'x';
console.log('DIFF', Core.diff(a, b).map(d => d.kind + ' ' + Core.pathLabel(b, d.path.slice(0, -0) ) + ' ' + Core.describe(d.before) + ' → ' + Core.describe(d.after)));
console.log('PATTERN', Core.patternValues(eg, 'sources[*].layer_1_etl.unit').map(x => x.value));
// number preservation
const md = fs.readFileSync(path.join(dir, 'mdsupdrs_part3_total.json'), 'utf8'); const pm = Core.parseJSONText(md);
pm.value.sources[0].layer_1_etl.range.max = 133; const o2 = Core.stringifyJSON(pm.value, pm.meta);
console.log('NUM', /"min": 0\.0/.test(o2), /"max": 133\n/.test(o2));
