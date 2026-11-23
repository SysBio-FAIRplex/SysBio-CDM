/* CDE Registry browser — core logic (no DOM).
   Runs in the page (window.Core) and in Node (module.exports), so the same code
   can be checked against every mapping file outside the browser. */
(function (root, factory) {
  const Core = factory();
  if (typeof module === 'object' && module.exports) module.exports = Core;
  else root.Core = Core;
})(typeof self !== 'undefined' ? self : this, function () {
'use strict';
const Core = {};

/* ───────────────────────── paths ───────────────────────── */
const pk = p => JSON.stringify(p);
Core.pk = pk;
const isObj = v => v !== null && typeof v === 'object' && !Array.isArray(v);
Core.isObj = isObj;
Core.get = function (o, p) {
  for (const k of p) { if (o === null || typeof o !== 'object') return undefined; o = o[k]; }
  return o;
};
Core.has = function (o, p) {
  if (!p.length) return true;
  const parent = Core.get(o, p.slice(0, -1));
  if (parent === null || typeof parent !== 'object') return false;
  const k = p[p.length - 1];
  return Array.isArray(parent) ? (k >= 0 && k < parent.length) : Object.prototype.hasOwnProperty.call(parent, k);
};
function setKey(obj, k, v) {
  if (k === '__proto__') Object.defineProperty(obj, k, { value: v, enumerable: true, writable: true, configurable: true });
  else obj[k] = v;
}
Core.set = function (o, p, v) {
  if (!p.length) throw new Error('empty path');
  const parent = Core.get(o, p.slice(0, -1));
  if (parent === null || typeof parent !== 'object') throw new Error('no container at ' + Core.pathStr(p.slice(0, -1)));
  setKey(parent, p[p.length - 1], v);
};
Core.del = function (o, p) {
  const parent = Core.get(o, p.slice(0, -1));
  if (parent === null || typeof parent !== 'object') return;
  const k = p[p.length - 1];
  if (Array.isArray(parent)) parent.splice(k, 1); else delete parent[k];
};
Core.insert = function (o, arrPath, index, v) {
  const arr = Core.get(o, arrPath);
  if (!Array.isArray(arr)) throw new Error('not a list at ' + Core.pathStr(arrPath));
  arr.splice(Math.max(0, Math.min(index, arr.length)), 0, v);
};
Core.pathStr = function (p) {
  let s = '';
  p.forEach((k, i) => { s += typeof k === 'number' ? '[' + k + ']' : (i ? '.' : '') + k; });
  return s;
};
Core.clone = v => (v === undefined ? undefined : JSON.parse(JSON.stringify(v)));

/* ───────────────────── JSON text: read and write in the file's own format ─────────────────────
   Every file in the registry is written by Python json.dump(indent=2): ", " and ": " separators,
   no escaping of non-ASCII unless ensure_ascii was on, numbers such as 132.0 spelled with ".0".
   The reader records each number's exact spelling and the file's layout so the writer reproduces
   the file byte for byte where nothing changed. */
Core.parseJSONText = function (text) {
  let i = 0;
  const n = text.length;
  const rawNums = new Map(), keyOrder = new Map(), dupKeys = [];
  const path = [];
  const NUM = /-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/y;
  const INTKEY = /^(?:0|[1-9]\d{0,9})$/;
  function err(msg) {
    const before = text.slice(0, i);
    const line = before.split('\n').length;
    const col = i - before.lastIndexOf('\n');
    const e = new SyntaxError(msg + ' at line ' + line + ', column ' + col);
    e.line = line; e.col = col; e.pos = i;
    throw e;
  }
  function ws() {
    while (i < n) {
      const c = text.charCodeAt(i);
      if (c === 32 || c === 10 || c === 13 || c === 9) i++; else break;
    }
  }
  function str() {
    const start = i; i++;
    while (i < n) {
      const c = text.charCodeAt(i);
      if (c === 34) { i++; try { return JSON.parse(text.slice(start, i)); } catch (e) { i = start; err('Bad string escape'); } }
      if (c === 92) i += 2;
      else if (c < 32) err('Control character inside a string');
      else i++;
    }
    err('Unterminated string');
  }
  function val() {
    ws();
    if (i >= n) err('Unexpected end of file');
    const c = text[i];
    if (c === '{') return obj();
    if (c === '[') return arr();
    if (c === '"') return str();
    if (c === 't' && text.startsWith('true', i)) { i += 4; return true; }
    if (c === 'f' && text.startsWith('false', i)) { i += 5; return false; }
    if (c === 'n' && text.startsWith('null', i)) { i += 4; return null; }
    NUM.lastIndex = i;
    const m = NUM.exec(text);
    if (m) {
      i += m[0].length;
      const v = Number(m[0]);
      if (String(v) !== m[0]) rawNums.set(pk(path), m[0]);
      return v;
    }
    err('Unexpected character ' + JSON.stringify(c));
  }
  function obj() {
    i++;
    const o = {};
    const order = [];
    let intKeys = false;
    ws();
    if (text[i] === '}') { i++; return o; }
    for (;;) {
      ws();
      if (text[i] !== '"') err('Expected a key in double quotes');
      const k = str();
      ws();
      if (text[i] !== ':') err("Expected ':' after a key");
      i++;
      path.push(k);
      const v = val();
      path.pop();
      if (Object.prototype.hasOwnProperty.call(o, k)) dupKeys.push(Core.pathStr(path.concat([k])));
      else order.push(k);
      setKey(o, k, v);
      if (INTKEY.test(k)) intKeys = true;
      ws();
      if (text[i] === ',') { i++; continue; }
      if (text[i] === '}') { i++; break; }
      err("Expected ',' or '}'");
    }
    if (intKeys) keyOrder.set(pk(path), order);
    return o;
  }
  function arr() {
    i++;
    const a = [];
    ws();
    if (text[i] === ']') { i++; return a; }
    for (;;) {
      path.push(a.length);
      a.push(val());
      path.pop();
      ws();
      if (text[i] === ',') { i++; continue; }
      if (text[i] === ']') { i++; break; }
      err("Expected ',' or ']'");
    }
    return a;
  }
  if (text.charCodeAt(0) === 0xFEFF) i = 1;
  const value = val();
  ws();
  if (i < n) err('Unexpected text after the end of the JSON');
  return { value, meta: { rawNums, keyOrder, dupKeys, style: Core.detectStyle(text) } };
};

Core.detectStyle = function (text) {
  const bom = text.charCodeAt(0) === 0xFEFF;
  const eol = text.indexOf('\r\n') >= 0 ? '\r\n' : '\n';
  const trailingNewline = /\n$/.test(text);
  let indent = null;
  const body = bom ? text.slice(1) : text;
  const m = body.match(/^[[{][ \t]*\r?\n([ \t]+)\S/);
  if (m) indent = m[1];
  else if (/\n/.test(body.trim())) { const m2 = body.match(/\n([ \t]+)\S/); indent = m2 ? m2[1] : '  '; }
  let ensureAscii = false;
  if (!/[^\x00-\x7f]/.test(body) && /\\u(?:00[89a-fA-F][0-9a-fA-F]|0[1-9a-fA-F][0-9a-fA-F]{2}|[1-9a-fA-F][0-9a-fA-F]{3})/.test(body)) ensureAscii = true;
  const keySep = indent === null ? (/"\s*:\s/.test(body) ? ': ' : ':') : ': ';
  const itemSep = indent === null ? (/[\]}"\d el],\s/.test(body) ? ', ' : ',') : ',';
  return { bom, eol, trailingNewline, indent, ensureAscii, keySep, itemSep };
};

Core.DEFAULT_STYLE = { bom: false, eol: '\n', trailingNewline: true, indent: '  ', ensureAscii: false, keySep: ': ', itemSep: ',' };

Core.quoteJSON = function (s, ascii) {
  let out = '"';
  let run = 0;
  for (let j = 0; j < s.length; j++) {
    const c = s.charCodeAt(j);
    let esc = null;
    if (c === 0x22) esc = '\\"';
    else if (c === 0x5c) esc = '\\\\';
    else if (c === 0x0a) esc = '\\n';
    else if (c === 0x0d) esc = '\\r';
    else if (c === 0x09) esc = '\\t';
    else if (c === 0x08) esc = '\\b';
    else if (c === 0x0c) esc = '\\f';
    else if (c < 0x20 || (ascii && c > 0x7e)) esc = '\\u' + c.toString(16).padStart(4, '0');
    if (esc !== null) { out += s.slice(run, j) + esc; run = j + 1; }
  }
  return out + s.slice(run) + '"';
};

Core.stringifyJSON = function (value, meta) {
  const st = (meta && meta.style) || Core.DEFAULT_STYLE;
  const raw = (meta && meta.rawNums) || new Map();
  const ko = (meta && meta.keyOrder) || new Map();
  const ascii = st.ensureAscii, ind = st.indent, eol = st.eol;
  const path = [];
  function num(v) {
    const r = raw.get(pk(path));
    if (r !== undefined && Number(r) === v) return r;
    if (!isFinite(v)) return 'null';
    return String(v);
  }
  function ser(v, depth) {
    if (v === null || v === undefined) return 'null';
    switch (typeof v) {
      case 'boolean': return v ? 'true' : 'false';
      case 'number': return num(v);
      case 'string': return Core.quoteJSON(v, ascii);
      case 'object': {
        if (Array.isArray(v)) {
          if (!v.length) return '[]';
          const parts = [];
          for (let j = 0; j < v.length; j++) { path.push(j); parts.push(ser(v[j], depth + 1)); path.pop(); }
          if (ind === null) return '[' + parts.join(st.itemSep) + ']';
          const pad = eol + ind.repeat(depth + 1);
          return '[' + pad + parts.join(',' + pad) + eol + ind.repeat(depth) + ']';
        }
        let keys = Object.keys(v);
        const ord = ko.get(pk(path));
        if (ord) {
          const have = new Set(keys), seen = new Set(), ks = [];
          for (const k of ord) if (have.has(k) && !seen.has(k)) { ks.push(k); seen.add(k); }
          for (const k of keys) if (!seen.has(k)) ks.push(k);
          keys = ks;
        }
        keys = keys.filter(k => v[k] !== undefined);
        if (!keys.length) return '{}';
        const parts = keys.map(k => { path.push(k); const s = Core.quoteJSON(k, ascii) + st.keySep + ser(v[k], depth + 1); path.pop(); return s; });
        if (ind === null) return '{' + parts.join(st.itemSep) + '}';
        const pad = eol + ind.repeat(depth + 1);
        return '{' + pad + parts.join(',' + pad) + eol + ind.repeat(depth) + '}';
      }
    }
    return 'null';
  }
  let out = ser(value, 0);
  if (st.trailingNewline) out += eol;
  if (st.bom) out = '﻿' + out;
  return out;
};

/* Line diff (common prefix/suffix trimmed, LCS on the middle). Returns null when too large. */
Core.lineDiff = function (aText, bText, limit) {
  const a = aText.split('\n'), b = bText.split('\n');
  let s = 0;
  while (s < a.length && s < b.length && a[s] === b[s]) s++;
  let ea = a.length, eb = b.length;
  while (ea > s && eb > s && a[ea - 1] === b[eb - 1]) { ea--; eb--; }
  const A = a.slice(s, ea), B = b.slice(s, eb);
  if (A.length * B.length > (limit || 4e6)) return null;
  const m = A.length, nB = B.length;
  const dp = Array.from({ length: m + 1 }, () => new Uint32Array(nB + 1));
  for (let x = m - 1; x >= 0; x--) for (let y = nB - 1; y >= 0; y--) dp[x][y] = A[x] === B[y] ? dp[x + 1][y + 1] + 1 : Math.max(dp[x + 1][y], dp[x][y + 1]);
  const ops = [];
  let x = 0, y = 0;
  while (x < m && y < nB) {
    if (A[x] === B[y]) { ops.push({ t: '=', a: s + x, b: s + y, line: A[x] }); x++; y++; }
    else if (dp[x + 1][y] >= dp[x][y + 1]) { ops.push({ t: '-', a: s + x, line: A[x] }); x++; }
    else { ops.push({ t: '+', b: s + y, line: B[y] }); y++; }
  }
  while (x < m) { ops.push({ t: '-', a: s + x, line: A[x] }); x++; }
  while (y < nB) { ops.push({ t: '+', b: s + y, line: B[y] }); y++; }
  return { prefix: s, ops, aLines: a, bLines: b, changed: ops.filter(o => o.t !== '=').length };
};

/* ───────────────────────── knowledge from the 2.7 template ───────────────────────── */
const K = Core.K = {};

K.ELEMENT_FIELDS = [
  ['registry_id', "The element's minted registry id (an integer). It is not the label; blank until minted."],
  ['registry_label', "The element's column name in the Layer 1 tables and the name Layer 2 reads. 'label' always means a column name."],
  ['harmonized_element_curie', "The element's Layer 1 vocabulary identity (e.g. LOINC:<code>), chosen first; it can differ from the Layer 2 defining concept."],
  ['definition', "What the element means: the provider's own dictionary text; the LOINC long common name where no provider dictionary exists; harmonized prose only when the element spans programs or files."],
  ['registry_etl_version', "Version of this element's mapping; bumped on any change that alters the Layer 1 output."],
  ['registry_etl_version_date', 'The date the version was set (YYYY-MM-DD).'],
  ['programs_covered', 'Every AMP program a source block below belongs to.'],
  ['modality', 'The data modality the element describes (clinical, scRNAseq, proteomics, wgs, ...).'],
  ['harmonized_values', "The element's declared value domain: what every source block's value map normalises onto. Enumerated values, never free text; '<any in range>' for a continuous measure."],
  ['must_agree', 'Blocks that produce a value for the same key must reconcile. Off = a silent tie-break (the first block read wins).'],
  ['null_is_agreement', 'A blank from one block is not a disagreement.'],
  ['on_conflict', 'What happens when blocks still differ: qc_flag, collapse_if_equal, or prefer:<source_label>.'],
  ['harmonized_with', 'Elements merged into this one (records the merge).'],
  ['load_id', "A name for the load job this element's targets are emitted in."],
  ['shape', 'A named requirement profile (declared; nothing enforces it yet).'],
  ['conflicts', 'Written by the loader when blocks disagree under qc_flag. Authored empty.']
];
K.ELEMENT_HELP = Object.fromEntries(K.ELEMENT_FIELDS);
K.OLDER_ELEMENT_FIELDS = {
  one_per: "Older grain field: one value per person / visit / specimen. Grain is now declared on every source block as loading_grain.",
  loading_grain: 'Older placement: grain declared once for the whole file. The template puts loading_grain on every source block.',
  unit: 'Unit declared for the whole file. The template declares the unit on each source block (layer_1_etl.unit).',
  status_note: 'Free prose about the file. The 2.7 template has status_note on source blocks and targets, not on the element.'
};
K.ELEMENT_KNOWN = new Set(['schema_version', 'sources', 'sysbio_etl', 'links', 'policies'].concat(K.ELEMENT_FIELDS.map(f => f[0])));

K.BLOCK_FIELDS = [
  ['source_name', 'A short handle so a note, a link or a fallback can point at this block.'],
  ['program', 'The AMP program this source belongs to.'],
  ['study', 'The study or cohort within the program.'],
  ['description', 'What this source is: the file, the sheet, the provider, the version.'],
  ['source_label', "The provider's column label, exactly as it appears in the file. One column per block."],
  ['status', 'Review state of this block: draft, pending, approved, rejected.'],
  ['status_note', 'Free prose, not read by the ETL.'],
  ['reviewed_by', 'Who reviewed the block.'],
  ['reviewed_on', 'When the block was reviewed.'],
  ['manual_approval', 'Approved by a person rather than generated.'],
  ['dictionary', "The provider's data dictionary document: file_name, checksum, sourced_from."],
  ['src_dictionary', 'The dictionary entry (or entries) that define this column.'],
  ['src_definition', "The provider's definition text, verbatim (errors annotated in a note, never corrected)."],
  ['layout', 'How to find the column inside the file: file_type, sheet, table.'],
  ['loading_grain', 'The grain: what this value is a fact about, and the Layer 1 table it lands on.'],
  ['precedence', 'Order among blocks producing a value for the same key: 1 is read first, higher fills only where every lower one is blank.'],
  ['applies_to_rows', 'Which rows this block reads (deterministic conditions on columns of this source).'],
  ['extract', 'Deterministic extraction: one source field split into several Layer 1 columns.'],
  ['layer_1_etl', 'Value form, datatype, missing values, range, unit, pinned data files and the value map.'],
  ['fallback', 'A complete lower-precedence block, used only where this block yields no value for the key.']
];
K.BLOCK_HELP = Object.fromEntries(K.BLOCK_FIELDS);
K.L1_FIELDS = [
  ['value_form', "Decided from the provider's dictionary, never inferred from the values."],
  ['datatype', "Copied from the provider's own type."],
  ['unit', 'The unit as the provider writes it; written beside the value as <label>_unit.'],
  ['range', "The dictionary's permissible range (continuous only); out-of-range is reported, never dropped."],
  ['missing_values', 'Sentinels this file uses (99, -9, NA); thrown out before any parse or range check.'],
  ['data_files', 'The file pin: identity only (file, accession, hash, access group). sha256 first.'],
  ['value_map', 'One line per distinct source spelling, mapped directly to a harmonized value.']
];
K.L1_HELP = Object.fromEntries(K.L1_FIELDS);
K.VM_COLUMNS = ['source_value', 'source_encoding', 'harmonized_value', 'harmonized_encoding', 'harmonized_ord', 'harmonized_curie', 'interval', 'note'];
K.VM_HELP = {
  source_value: 'The spelling in the file.',
  source_encoding: 'The code the file pairs with it, or null.',
  harmonized_value: 'The harmonized value it means: one of harmonized_values.',
  harmonized_encoding: 'The harmonized code, only where a code system exists (instrument scores); never minted.',
  harmonized_ord: 'Orders an ordinal set.',
  harmonized_curie: 'The ontology id that rides this value; written to <label>_curie.',
  interval: 'Binned elements: the numeric bounds the bin covers.',
  note: 'Why, counts, provider note.'
};
K.DATA_FILE_COLUMNS = ['file', 'source_id', 'id_type', 'sha256', 'access_groups', 'sheet'];
K.CONDITION_COLUMNS = ['column', 'match', 'token', 'inequality', 'token_position', 'delimiters'];
K.EXTRACT_COLUMNS = ['label', 'delimiters', 'token_position', 'token', 'into'];

K.TARGET_FIELDS = [
  ['target_id', 'A name for this target, unique within the file: what the row IS. Never a CDM key, never written to the CDM.'],
  ['table', "The one CDM table this target's rows go into. A second table is a second target."],
  ['input', "Which Layer 1 output this target reads: 'self' (this element's own column) or registry_label@version plus the output table's sha256."],
  ['defining_concept_id', 'The concept that says WHAT this row is, written to target_field on every row. Its domain must match the table; Standard concepts only.'],
  ['anchored_to', 'The keys each row hangs on (the Layer 2 grain): CDM key column → the table or map that supplies its value.'],
  ['grain', 'Aggregation: group_by lists Layer 1 columns that collapse several Layer 1 rows into one CDM row.'],
  ['source_value', "What the table's *_source_value column receives: <raw> = the original source string; a literal = that literal on every row."],
  ['qualifier_concept_id', 'A qualifier written on every row of this target.'],
  ['omop_value_set', 'The closed set of Standard concepts a concept column may take when values come from a vocabulary branch.'],
  ['record_attributes', 'Facts about the target as a whole: role + link_id (a link) or column (about one CDM column).'],
  ['value_map', 'The fan-out: one entry per harmonized value, naming every CDM column of the row the value fills.'],
  ['emits', "Columns whose value doesn't depend on the harmonized value: exactly one of const, template, measure."],
  ['note', 'Free text.'],
  ['status_note', 'Free text.']
];
K.TARGET_HELP = Object.fromEntries(K.TARGET_FIELDS);
K.RA_COLUMNS = ['role', 'link_id', 'column', 'status', 'note'];
K.OVS_COLUMNS = ['concept_id', 'concept_name'];
K.EMITS_COLUMNS = ['cdm_column', 'const', 'template', 'measure'];
K.LINK_COLUMNS = ['link_id', 'kind', 'linked_element_label', 'linked_element_id', 'linked_table', 'linked_defining_concept', 'linked_value_set', 'linking_mechanism', 'linking_mechanism_concept_id', 'inverse_concept_id', 'note'];
K.LINK_HELP = {
  link_id: 'Unique in this file; what record_attributes.link_id points at.',
  kind: "derivation = the linked row is this row's source or product in a chain; realized = the linked row is the context this row's fact was produced in.",
  linked_element_label: 'registry_label of the element whose target this links to (may be this element).',
  linked_element_id: "That element's registry id (optional).",
  linked_table: 'CDM table of the linked row.',
  linked_defining_concept: 'The concept of the row at the other end, so the link can be checked at load.',
  linked_value_set: 'The value or range the linked row must carry.',
  linking_mechanism: 'An event pointer (MEASUREMENT.measurement_event_id / OBSERVATION.observation_event_id) or a FACT_RELATIONSHIP pair.',
  linking_mechanism_concept_id: "Event pointer: the field concept naming the linked row's key. Fact relationship: the forward relationship concept.",
  inverse_concept_id: 'The reciprocal relationship concept (FACT_RELATIONSHIP only).',
  note: 'Free text.'
};
K.POLICY_COLUMNS = ['field', 'split_on', 'assert', 'set'];

K.ENUMS = {
  value_form: ['ordinal', 'nominal', 'continuous', 'text', 'identifier', 'date', 'binned', 'interval'],
  datatype: ['integer', 'number', 'float', 'string', 'code', 'date', 'boolean', 'interval'],
  status: ['draft', 'pending', 'approved', 'rejected', 'proposed', 'active', 'candidate'],
  on_conflict: ['qc_flag', 'collapse_if_equal', 'prefer:'],
  require: ['all', 'any'],
  action: ['include', 'exclude', 'flag'],
  match: ['equals', 'in'],
  id_type: ['synapse', 'cmdga', 'cmd_dataset', 'zenodo', 'kpmp', 'kpmp_file_uuid', 'geo', 'cellxgene'],
  file_type: ['csv', 'tsv', 'xlsx', 'jsonl', 'soft.gz', 'html'],
  table: ['measurement', 'observation', 'specimen', 'procedure_occurrence', 'condition_occurrence', 'person', 'drug_exposure', 'device_exposure', 'visit_occurrence'],
  linked_table: ['measurement', 'observation', 'specimen', 'procedure_occurrence', 'condition_occurrence'],
  kind: ['derivation', 'realized'],
  linking_mechanism: ['MEASUREMENT.measurement_event_id', 'OBSERVATION.observation_event_id', 'FACT_RELATIONSHIP'],
  role: ['derivation', 'scan', 'medication_state', 'qualifier', 'attribute'],
  target_field: ['measurement_concept_id', 'observation_concept_id', 'condition_concept_id', 'procedure_concept_id', 'specimen_concept_id', 'anatomic_site_concept_id'],
  domain: ['Measurement', 'Observation', 'Condition', 'Procedure', 'Specimen', 'Spec Anatomic Site', 'Meas Value', 'Unit', 'Drug', 'Device', 'Type Concept'],
  anchor: ['participant_id', 'sample_id', 'specimen_id', 'library_id', 'file_id'],
  entity: ['participant', 'participant_visit', 'specimen', 'library', 'file', 'serum_sample', 'plasma_sample', 'urine_sample', 'stool_sample', 'baseline_clinical_labs', 'specimen_acquisition', 'sample'],
  one_per: ['person', 'visit', 'specimen'],
  measure: ['count_rows', 'sum', 'first_nonnull of:'],
  modality: ['clinical', 'scRNAseq', 'proteomics', 'wgs'],
  source_value: ['<raw>'],
  value_as_number: ['<value>'],
  assert: ['no_token_in']
};

/* OMOP CDM v5.4 columns of the tables the registry writes. */
K.CDM = {
  person: 'person_id gender_concept_id year_of_birth month_of_birth day_of_birth birth_datetime race_concept_id ethnicity_concept_id location_id provider_id care_site_id person_source_value gender_source_value gender_source_concept_id race_source_value race_source_concept_id ethnicity_source_value ethnicity_source_concept_id',
  observation: 'observation_id person_id observation_concept_id observation_date observation_datetime observation_type_concept_id value_as_number value_as_string value_as_concept_id qualifier_concept_id unit_concept_id provider_id visit_occurrence_id visit_detail_id observation_source_value observation_source_concept_id unit_source_value qualifier_source_value value_source_value observation_event_id obs_event_field_concept_id',
  measurement: 'measurement_id person_id measurement_concept_id measurement_date measurement_datetime measurement_time measurement_type_concept_id operator_concept_id value_as_number value_as_concept_id unit_concept_id range_low range_high provider_id visit_occurrence_id visit_detail_id measurement_source_value measurement_source_concept_id unit_source_value unit_source_concept_id value_source_value measurement_event_id meas_event_field_concept_id',
  condition_occurrence: 'condition_occurrence_id person_id condition_concept_id condition_start_date condition_start_datetime condition_end_date condition_end_datetime condition_type_concept_id condition_status_concept_id stop_reason provider_id visit_occurrence_id visit_detail_id condition_source_value condition_source_concept_id condition_status_source_value',
  specimen: 'specimen_id person_id specimen_concept_id specimen_type_concept_id specimen_date specimen_datetime quantity unit_concept_id anatomic_site_concept_id disease_status_concept_id specimen_source_id specimen_source_value unit_source_value anatomic_site_source_value disease_status_source_value',
  procedure_occurrence: 'procedure_occurrence_id person_id procedure_concept_id procedure_date procedure_datetime procedure_end_date procedure_end_datetime procedure_type_concept_id modifier_concept_id quantity provider_id visit_occurrence_id visit_detail_id procedure_source_value procedure_source_concept_id modifier_source_value',
  drug_exposure: 'drug_exposure_id person_id drug_concept_id drug_exposure_start_date drug_exposure_start_datetime drug_exposure_end_date drug_exposure_end_datetime verbatim_end_date drug_type_concept_id stop_reason refills quantity days_supply sig route_concept_id lot_number provider_id visit_occurrence_id visit_detail_id drug_source_value drug_source_concept_id route_source_value dose_unit_source_value',
  device_exposure: 'device_exposure_id person_id device_concept_id device_exposure_start_date device_exposure_start_datetime device_exposure_end_date device_exposure_end_datetime device_type_concept_id unique_device_id production_id quantity provider_id visit_occurrence_id visit_detail_id device_source_value device_source_concept_id unit_concept_id unit_source_value unit_source_concept_id',
  visit_occurrence: 'visit_occurrence_id person_id visit_concept_id visit_start_date visit_start_datetime visit_end_date visit_end_datetime visit_type_concept_id provider_id care_site_id visit_source_value visit_source_concept_id admitted_from_concept_id admitted_from_source_value discharged_to_concept_id discharged_to_source_value preceding_visit_occurrence_id'
};
for (const t of Object.keys(K.CDM)) K.CDM[t] = K.CDM[t].split(' ');

K.L2_VALUE_KEYS_ORDER = ['value_as_concept_id', 'value_as_number', 'value_as_string', 'qualifier_concept_id', 'unit_concept_id', 'unit_source_value',
  'condition_concept_id', 'condition_status_concept_id', 'specimen_concept_id', 'anatomic_site_concept_id', 'anatomic_site_source_value',
  'disease_status_concept_id', 'disease_status_source_value', 'specimen_source_id', 'specimen_source_value', 'quantity'];
K.L2_CELL_HELP = {
  value_as_concept_id: "The value's concept.",
  value_as_number: "A number, or '<value>' = the harmonized value itself as a number.",
  value_as_string: 'The string written to value_as_string.',
  qualifier_concept_id: 'A qualifier that changes with the value.',
  unit_concept_id: 'The unit concept.',
  unit_source_value: 'The unit as the provider writes it.'
};

/* Concept domains allowed in a concept column (your specimen ruling covers specimen and anatomic-site columns). */
K.ALLOWED_DOMAINS = {
  measurement_concept_id: ['Measurement'],
  observation_concept_id: ['Observation'],
  condition_concept_id: ['Condition'],
  procedure_concept_id: ['Procedure'],
  specimen_concept_id: ['Specimen', 'Spec Anatomic Site', 'Body Structure'],
  anatomic_site_concept_id: ['Specimen', 'Spec Anatomic Site', 'Body Structure'],
  unit_concept_id: ['Unit'],
  drug_concept_id: ['Drug'],
  device_concept_id: ['Device'],
  visit_concept_id: ['Visit']
};
K.TABLE_DOMAIN = {
  measurement: ['Measurement'], observation: ['Observation'], condition_occurrence: ['Condition'], procedure_occurrence: ['Procedure'],
  specimen: ['Specimen', 'Spec Anatomic Site', 'Body Structure'], drug_exposure: ['Drug'], device_exposure: ['Device']
};
Core.allowedDomains = function (column) {
  if (!column) return null;
  if (K.ALLOWED_DOMAINS[column]) return K.ALLOWED_DOMAINS[column];
  if (/_type_concept_id$/.test(column)) return ['Type Concept'];
  return null;
};

/* Grain vocabulary: the identifier, the procedure that minted it, and the Layer 1 table it names. */
K.ANCHOR = {
  participant_id: { procedure: 'Enrollment', help: 'the enrollment that produced the participant and minted participant_id' },
  sample_id: { procedure: 'Sample collection', help: 'the collection that produced the sample (urine, serum, plasma, stool …) and minted sample_id' },
  specimen_id: { procedure: 'Harvest or collection', help: 'the harvest or collection that produced the specimen and minted specimen_id' },
  library_id: { procedure: 'Processing', help: 'the processing that produced the library (a derived specimen) and minted library_id' },
  file_id: { procedure: 'Analysis', help: 'the analysis that produced the file and minted file_id' }
};
K.ENTITY = {
  participant: { noun: 'participant', level: 'participant', help: 'one row per participant' },
  participant_visit: { noun: 'participant visit', level: 'visit', help: 'one row per participant per visit (key: participant_id + the visit name as the study writes it)' },
  baseline_clinical_labs: { noun: 'participant', level: 'participant', help: "one row per participant: the baseline clinical-record lab summaries, which have no identifiable sample" },
  specimen: { noun: 'specimen', level: 'specimen', help: 'one row per specimen (harvested or derived), each pointing at its parent' },
  specimen_acquisition: { noun: 'specimen acquisition', level: 'specimen', help: 'one row per specimen acquisition' },
  library: { noun: 'library', level: 'specimen', help: 'one row per library (a derived specimen)' },
  file: { noun: 'file', level: 'file', help: 'one row per file' },
  serum_sample: { noun: 'serum sample', level: 'sample', help: 'one row per serum sample' },
  plasma_sample: { noun: 'plasma sample', level: 'sample', help: 'one row per plasma sample' },
  urine_sample: { noun: 'urine sample', level: 'sample', help: 'one row per urine sample' },
  stool_sample: { noun: 'stool sample', level: 'sample', help: 'one row per stool sample' },
  sample: { noun: 'sample', level: 'sample', help: 'one row per sample' }
};
K.ONE_PER_LEVEL = { person: 'participant', visit: 'visit', specimen: 'specimen' };

/* ───────────────────────── reading a mapping file ───────────────────────── */
const str = v => (typeof v === 'string' ? v : (v === null || v === undefined ? '' : String(v)));
Core.str = str;
const uniq = a => Array.from(new Set(a.filter(x => x !== '' && x !== null && x !== undefined)));
Core.uniq = uniq;

Core.isConcept = function (v) {
  return isObj(v) && (('id' in v) || ('concept_id' in v)) && (('name' in v) || ('concept_name' in v));
};
Core.conceptOf = function (v) {
  if (!isObj(v)) return null;
  return { id: 'id' in v ? v.id : v.concept_id, name: 'name' in v ? v.name : v.concept_name, domain: v.domain, vocabulary: v.vocabulary_id || v.vocabulary };
};

/* Every source block, including fallbacks nested inside blocks, in reading order. */
Core.blocks = function (root) {
  const out = [];
  const srcs = isObj(root) && Array.isArray(root.sources) ? root.sources : [];
  function visit(b, p, depth, topIndex) {
    if (!isObj(b)) return;
    out.push({ block: b, path: p, depth, topIndex });
    if (isObj(b.fallback)) visit(b.fallback, p.concat('fallback'), depth + 1, topIndex);
  }
  srcs.forEach((b, i) => visit(b, ['sources', i], 0, i));
  return out;
};
Core.blockLabels = function (b) {
  if (!isObj(b)) return [];
  const l = b.source_label;
  if (typeof l === 'string') return l ? [l] : [];
  if (Array.isArray(l)) return l.filter(x => typeof x === 'string' && x);
  return [];
};
Core.blockPins = function (b) {
  const l1 = isObj(b) && isObj(b.layer_1_etl) ? b.layer_1_etl : null;
  const files = l1 && Array.isArray(l1.data_files) ? l1.data_files : [];
  return files.filter(isObj).map(f => {
    const sha = str(f.sha256), sid = str(f.source_id), name = str(f.file);
    const key = sha ? 'sha256:' + sha : sid ? 'id:' + sid : name ? 'file:' + name : '';
    const short = sid ? sid : sha ? sha.slice(0, 12) + '…' : name;
    return { key, sha256: sha, source_id: sid, file: name, id_type: str(f.id_type), short };
  }).filter(p => p.key);
};
Core.valueMap = b => (isObj(b) && isObj(b.layer_1_etl) && Array.isArray(b.layer_1_etl.value_map) ? b.layer_1_etl.value_map : []);
Core.targets = root => (isObj(root) && Array.isArray(root.sysbio_etl) ? root.sysbio_etl : []);
Core.labelOf = function (root, fallbackName) {
  if (isObj(root)) {
    if (typeof root.registry_label === 'string' && root.registry_label) return root.registry_label;
    if (typeof root.harmonized_element_label === 'string' && root.harmonized_element_label) return root.harmonized_element_label;
  }
  return (fallbackName || '').replace(/\.json$/i, '');
};
Core.allHarmonizedValues = function (root) {
  const out = [];
  if (isObj(root) && Array.isArray(root.harmonized_values)) for (const v of root.harmonized_values) if (typeof v === 'string' || typeof v === 'number') out.push(String(v));
  for (const { block } of Core.blocks(root)) for (const e of Core.valueMap(block)) if (isObj(e) && (typeof e.harmonized_value === 'string' || typeof e.harmonized_value === 'number')) out.push(String(e.harmonized_value));
  return uniq(out);
};

/* ── grain: what a source block's value is a fact about ── */
Core.blockGrain = function (root, block) {
  const label = Core.labelOf(root);
  let source = 'none', g = null;
  if (isObj(block) && isObj(block.loading_grain)) { source = 'block'; g = block.loading_grain; }
  else if (isObj(root) && isObj(root.loading_grain)) { source = 'element'; g = root.loading_grain; }
  const out = { source, label };
  if (g) {
    const anchor = str(g.anchor), entity = str(g.entity), attribute = str(g.attribute);
    const ent = K.ENTITY[entity];
    let a = K.ANCHOR[anchor];
    if (entity === 'participant_visit' && anchor === 'participant_id') a = { procedure: 'A visit', help: 'the visit, which mints participant_id together with the visit name as the study writes it' };
    out.anchor = anchor; out.entity = entity; out.attribute = attribute;
    out.procedure = a ? a.procedure : '';
    out.procHelp = a ? a.help : (anchor ? 'not known for the identifier ' + anchor : 'no anchor declared');
    out.anchorHelp = anchor ? 'the identifier that procedure minted; the key of the row this value is written to' : 'not declared';
    out.entityNoun = ent ? ent.noun : entity.replace(/_/g, ' ');
    out.entityHelp = entity ? (ent ? ent.help : 'the Layer 1 table named ' + entity) : 'not declared';
    out.level = ent ? ent.level : (entity ? 'unknown' : null);
    out.attrHelp = "this element; the column in that table that receives the harmonized value";
    out.attrMatches = !attribute || attribute === label;
    const procedure = out.procedure || 'The procedure that produced it';
    out.readsAs = (anchor && entity)
      ? procedure + ' minted ' + anchor + ' → ' + anchor + ' names one ' + out.entityNoun + ' → that ' + out.entityNoun + "'s row in the Layer 1 " + entity + ' table gets one ' + (attribute || label) + ' value.'
      : 'Incomplete: ' + (!anchor ? 'no anchor' : '') + (!anchor && !entity ? ' and ' : '') + (!entity ? 'no entity' : '') + ' declared.';
    const attr = attribute || label;
    const besides = [];
    const l1 = isObj(block) && isObj(block.layer_1_etl) ? block.layer_1_etl : {};
    if (str(l1.unit) || (isObj(root) && str(root.unit))) besides.push(attr + '_unit');
    const vm = Core.valueMap(block);
    if (vm.some(e => isObj(e) && e.harmonized_curie)) besides.push(attr + '_curie');
    if (vm.some(e => isObj(e) && e.harmonized_encoding !== null && e.harmonized_encoding !== undefined && e.harmonized_encoding !== '')) besides.push(attr + '_code');
    out.besides = besides;
  } else if (isObj(root) && Array.isArray(root.one_per) && root.one_per.length) {
    out.source = 'one_per';
    out.onePer = root.one_per.map(str);
    const lv = out.onePer.map(x => K.ONE_PER_LEVEL[x]).filter(Boolean);
    out.level = lv.includes('specimen') ? 'specimen' : lv.includes('visit') ? 'visit' : lv.includes('participant') ? 'participant' : 'unknown';
    out.readsAs = 'Only the older one_per field is set (' + out.onePer.join(', ') + '): one value per ' + out.onePer.join(' per ') +
      '. No anchor, entity or attribute is declared, so the file does not say which Layer 1 table the value lands on.';
  } else {
    out.readsAs = 'No grain is declared on this block or for the file.';
  }
  return out;
};

/* ── keys: what each Layer 2 row hangs on ── */
const KEY_ROWS = ['person_id', 'visit_occurrence_id', 'specimen_id'];
Core.targetKeys = function (root, target) {
  const at = isObj(target) ? target.anchored_to : undefined;
  const table = isObj(target) ? str(target.table) || 'CDM' : 'CDM';
  const grains = Core.blocks(root).map(x => Core.blockGrain(root, x.block));
  const anchors = uniq(grains.map(g => g.anchor || ''));
  const res = { table, shape: 'object', rows: [], grains };
  if (Array.isArray(at)) { res.shape = 'list'; return res; }
  if (!isObj(at)) { res.shape = at === undefined || at === null ? 'missing' : 'other'; return res; }
  const keys = uniq(KEY_ROWS.concat(Object.keys(at)));
  const anchorTxt = anchors.length === 1 ? anchors[0] : anchors.length ? anchors.join(' / ') : '';
  for (const k of keys) {
    const present = Object.prototype.hasOwnProperty.call(at, k);
    const from = present ? str(at[k]) : '';
    let explain;
    if (k === 'person_id') explain = present
      ? (anchorTxt === 'participant_id'
        ? "the loader takes the row's participant_id (the source block's anchor) and looks up its CDM person key in " + (from || 'the participant identity map')
        : "the loader looks up the CDM person key of the participant the row belongs to" + (anchorTxt ? ' (the row is keyed by ' + anchorTxt + ')' : '') + ', in ' + (from || 'the participant identity map'))
      : 'not set. Every target needs it: the CDM person key, resolved through the participant identity map.';
    else if (k === 'visit_occurrence_id') explain = present
      ? 'looked up in ' + (from || 'the visit table') + ' by participant and the visit name as the study writes it'
      : 'not set. Add when the fact belongs to a visit: looked up by participant and the visit name as the study writes it.';
    else if (k === 'specimen_id') explain = present
      ? "the row's specimen or sample identifier, looked up in " + (from || 'the specimen map')
      : 'not set. Add when the fact belongs to a specimen or sample: its identifier looked up in the specimen map.';
    else explain = present ? 'resolved from ' + (from || '(nothing named)') : '';
    res.rows.push({ key: k, present, from, explain });
  }
  const has = k => Object.prototype.hasOwnProperty.call(at, k);
  res.level = has('specimen_id') ? 'specimen' : has('visit_occurrence_id') ? 'visit' : has('person_id') ? 'participant' : 'none';
  const per = { specimen: 'per specimen', visit: 'per participant per visit', participant: 'per participant', none: '' }[res.level];
  res.resultText = res.level === 'none' ? 'No keys set: the loader has nothing to hang the rows on.' : 'Keys set: ' + Object.keys(at).filter(k => at[k] !== null && at[k] !== '').join(' + ') + ' → one ' + table + ' row ' + per + '.';
  const levels = uniq(grains.map(g => g.level || ''));
  const need = { participant: 'participant', visit: 'visit', specimen: 'specimen', sample: 'specimen' };
  if (!levels.length) res.check = { status: 'unknown', text: 'No grain is declared on the source blocks, so the keys cannot be checked against it.' };
  else if (levels.some(l => l === 'unknown' || l === 'file')) res.check = { status: 'unknown', text: 'The blocks land on ' + uniq(grains.map(g => g.entity || '')).join(', ') + '; no rule here says which keys that needs.' };
  else {
    const wanted = uniq(levels.map(l => need[l]));
    const desc = uniq(grains.map(g => g.source === 'one_per' ? 'one_per ' + g.onePer.join('+') : (g.anchor + ' → ' + g.entity))).join('; ');
    if (wanted.length === 1 && wanted[0] === res.level) res.check = { status: 'ok', text: 'Agrees with the source blocks (' + desc + ').' };
    else {
      const t = wanted.length > 1
        ? 'The source blocks land at different grains (' + desc + '), so one set of keys cannot match all of them.'
        : 'The source blocks put values on ' + desc + ' (one value ' + ({ participant: 'per participant', visit: 'per participant per visit', specimen: 'per specimen or sample' }[wanted[0]]) + '), but these keys give one row ' + per + '.';
      res.check = { status: 'warn', text: t };
    }
  }
  return res;
};

Core.conceptDomainCheck = function (target) {
  if (!isObj(target) || !isObj(target.defining_concept_id)) return null;
  const c = target.defining_concept_id;
  const field = str(c.target_field), table = str(target.table), domain = str(c.domain);
  const allowed = Core.allowedDomains(field) || K.TABLE_DOMAIN[table] || null;
  if (!domain) return { status: 'unknown', text: 'No domain written on the concept.' };
  if (!allowed) return { status: 'unknown', text: 'No domain rule known for ' + (field || table) + '.' };
  return allowed.includes(domain)
    ? { status: 'ok', text: 'domain ' + domain + ' fits ' + (field || table) }
    : { status: 'warn', text: 'domain ' + domain + ' is written to ' + (field || table) + ' (expects ' + allowed.join(' / ') + ')' };
};

/* ── Layer 2 value map grid for one target ── */
Core.l2Grid = function (root, target) {
  const vm = isObj(target) && Array.isArray(target.value_map) ? target.value_map : [];
  const declared = isObj(root) && Array.isArray(root.harmonized_values) ? root.harmonized_values.map(v => String(v)) : [];
  const hvs = Core.allHarmonizedValues(root);
  const entryHv = [];
  vm.forEach((e, i) => { if (isObj(e)) entryHv.push([String(e.harmonized_value), i]); });
  const order = uniq(hvs.concat(entryHv.map(x => x[0])));
  const table = isObj(target) ? str(target.table) : '';
  const cols = K.CDM[table] || null;
  const keysSeen = [];
  vm.forEach(e => { if (isObj(e)) for (const k of Object.keys(e)) if (k !== 'harmonized_value' && k !== 'note' && !keysSeen.includes(k)) keysSeen.push(k); });
  const ordered = K.L2_VALUE_KEYS_ORDER.filter(k => keysSeen.includes(k)).concat(keysSeen.filter(k => !K.L2_VALUE_KEYS_ORDER.includes(k)));
  const hasNote = vm.some(e => isObj(e) && 'note' in e);
  const columns = ordered.map(k => ({ key: k, isColumn: cols ? (cols.includes(k) || k.startsWith('_')) : null }));
  if (hasNote) columns.push({ key: 'note', isColumn: true, isNote: true });
  const rows = [];
  for (const hv of order) {
    const idxs = entryHv.filter(x => x[0] === hv).map(x => x[1]);
    if (!idxs.length) rows.push({ hv, entryIndex: null, flags: ['missing'] });
    idxs.forEach(i => {
      const flags = [];
      if (idxs.length > 1) flags.push('duplicate');
      if (declared.length && !declared.includes(hv) && hv !== '<any in range>') flags.push('undeclared');
      rows.push({ hv, entryIndex: i, flags });
    });
  }
  vm.forEach((e, i) => { if (!isObj(e)) rows.push({ hv: '(not an object)', entryIndex: i, flags: ['malformed'] }); });
  return { rows, columns, table, knownTable: !!cols, cdmColumns: cols || [] };
};
Core.l2ByValue = function (root) {
  const tg = Core.targets(root);
  const hvs = uniq(Core.allHarmonizedValues(root).concat(...tg.map(t => (isObj(t) && Array.isArray(t.value_map) ? t.value_map : []).filter(isObj).map(e => String(e.harmonized_value)))));
  return hvs.map(hv => ({
    hv,
    landings: tg.map((t, ti) => {
      if (!isObj(t)) return null;
      const vm = Array.isArray(t.value_map) ? t.value_map : [];
      const idx = vm.findIndex(e => isObj(e) && String(e.harmonized_value) === hv);
      return { ti, table: str(t.table), targetId: str(t.target_id), entryIndex: idx >= 0 ? idx : null, entry: idx >= 0 ? vm[idx] : null };
    }).filter(Boolean)
  }));
};

/* ── summary of one file (library, clusters, search) ── */
Core.summarize = function (id, root) {
  const name = id.split('/').pop();
  const s = {
    id, name, dir: id.includes('/') ? id.slice(0, id.lastIndexOf('/')) : '', label: Core.labelOf(root, name), schema: '', programs: [],
    nTopBlocks: 0, nBlocks: 0, nTargets: 0, nLinks: 0, nL1Entries: 0, forms: [], units: [], grains: [], entities: [], anchors: [], curie: '',
    concepts: [], tableFields: [], tables: [], srcCols: [], pins: [], hvals: [], words: [], statuses: [], definition: ''
  };
  if (!isObj(root)) return s;
  s.schema = str(root.schema_version);
  s.definition = str(root.definition);
  s.programs = Array.isArray(root.programs_covered) ? uniq(root.programs_covered.map(str)) : [];
  s.nTopBlocks = Array.isArray(root.sources) ? root.sources.length : 0;
  const bl = Core.blocks(root);
  s.nBlocks = bl.length;
  s.nTargets = Core.targets(root).length;
  s.nLinks = Array.isArray(root.links) ? root.links.length : 0;
  s.curie = str(root.harmonized_element_curie);
  const forms = [], units = [], grains = [], ents = [], anchors = [], srcCols = [], pins = [], statuses = [];
  if (str(root.unit)) units.push(str(root.unit));
  for (const { block } of bl) {
    const l1 = isObj(block.layer_1_etl) ? block.layer_1_etl : {};
    if (str(l1.value_form)) forms.push(str(l1.value_form));
    if (str(l1.unit)) units.push(str(l1.unit));
    s.nL1Entries += Core.valueMap(block).length;
    const g = Core.blockGrain(root, block);
    if (g.source === 'block' || g.source === 'element') { grains.push((g.anchor || '?') + ' → ' + (g.entity || '?')); if (g.entity) ents.push(g.entity); if (g.anchor) anchors.push(g.anchor); }
    else if (g.source === 'one_per') grains.push('one_per: ' + g.onePer.join(', '));
    const p = Core.blockPins(block);
    pins.push(...p);
    const pinKey = p.map(x => x.key).sort().join('|') || '(no pinned file)';
    const pinShort = p.map(x => x.short).join(', ') || '(no pinned file)';
    for (const lab of Core.blockLabels(block)) srcCols.push({ key: pinKey + ' :: ' + lab, label: lab, files: pinShort });
    if (str(block.status)) statuses.push(str(block.status));
  }
  s.forms = uniq(forms); s.units = uniq(units); s.grains = uniq(grains); s.entities = uniq(ents); s.anchors = uniq(anchors);
  s.srcCols = srcCols.filter((x, i, a) => a.findIndex(y => y.key === x.key) === i);
  s.pins = pins.filter((x, i, a) => a.findIndex(y => y.key === x.key) === i);
  s.statuses = uniq(statuses);
  for (const t of Core.targets(root)) {
    if (!isObj(t)) continue;
    const table = str(t.table);
    if (table) s.tables.push(table);
    const c = isObj(t.defining_concept_id) ? t.defining_concept_id : null;
    if (c && (c.id !== null && c.id !== undefined && c.id !== '')) s.concepts.push({ id: String(c.id), name: str(c.name), table, field: str(c.target_field) });
    s.tableFields.push(table + '.' + (c ? str(c.target_field) || '?' : '?'));
  }
  s.tables = uniq(s.tables); s.tableFields = uniq(s.tableFields);
  s.hvals = Core.allHarmonizedValues(root).filter(v => v !== '<any in range>');
  s.words = uniq(s.label.toLowerCase().split(/[_\W]+/).filter(w => w.length > 1));
  return s;
};

/* ── scalar leaves (search) ── */
Core.leaves = function (root, cb, p) {
  p = p || [];
  if (root === null || typeof root !== 'object') { cb(p, root); return; }
  if (Array.isArray(root)) root.forEach((v, i) => Core.leaves(v, cb, p.concat(i)));
  else for (const k of Object.keys(root)) Core.leaves(root[k], cb, p.concat(k));
};

/* ── diff between the version on disk and the current edit ── */
function kindOf(v) { return v === undefined ? 'undef' : v === null || typeof v !== 'object' ? 'scalar' : Array.isArray(v) ? 'array' : 'object'; }
Core.deepEqual = (a, b) => JSON.stringify(a) === JSON.stringify(b);
Core.diff = function (a, b, path, out) {
  path = path || []; out = out || [];
  const ka = kindOf(a), kb = kindOf(b);
  if (ka !== kb || ka === 'scalar' || ka === 'undef') {
    if (!(ka === kb && (a === b || (typeof a === 'number' && typeof b === 'number' && Object.is(a, b))))) {
      out.push({ path, kind: ka === 'undef' ? 'added' : kb === 'undef' ? 'removed' : 'changed', before: a, after: b });
    }
    return out;
  }
  if (ka === 'array') {
    if (a.length === b.length) { for (let i = 0; i < a.length; i++) Core.diff(a[i], b[i], path.concat(i), out); return out; }
    const sa = a.map(x => JSON.stringify(x)), sb = b.map(x => JSON.stringify(x));
    if (a.length * b.length > 250000) {
      const n = Math.max(a.length, b.length);
      for (let i = 0; i < n; i++) Core.diff(a[i], b[i], path.concat(i), out);
      return out;
    }
    const m = a.length, n = b.length;
    const dp = Array.from({ length: m + 1 }, () => new Uint32Array(n + 1));
    for (let x = m - 1; x >= 0; x--) for (let y = n - 1; y >= 0; y--) dp[x][y] = sa[x] === sb[y] ? dp[x + 1][y + 1] + 1 : Math.max(dp[x + 1][y], dp[x][y + 1]);
    /* Walk the longest common subsequence; inside each gap, pair items in order (an edited item),
       and report what is left over as removed or added. Paths and indexes are in the new list,
       except oldIndex; insertAt is where a removed item goes back. */
    let x = 0, y = 0;
    const gapA = [], gapB = [];
    const flush = at => {
      const k = Math.min(gapA.length, gapB.length);
      for (let i = 0; i < k; i++) Core.diff(a[gapA[i]], b[gapB[i]], path.concat(gapB[i]), out);
      for (let i = k; i < gapA.length; i++) out.push({ path: path.concat(gapA[i]), kind: 'removed', before: a[gapA[i]], after: undefined, arrayPath: path, oldIndex: gapA[i], insertAt: at });
      for (let i = k; i < gapB.length; i++) out.push({ path: path.concat(gapB[i]), kind: 'added', before: undefined, after: b[gapB[i]], arrayPath: path, newIndex: gapB[i] });
      gapA.length = 0; gapB.length = 0;
    };
    while (x < m && y < n) {
      if (sa[x] === sb[y]) { flush(y); x++; y++; }
      else if (dp[x + 1][y] >= dp[x][y + 1]) { gapA.push(x); x++; }
      else { gapB.push(y); y++; }
    }
    while (x < m) gapA.push(x++);
    while (y < n) gapB.push(y++);
    flush(n);
    return out;
  }
  const keys = uniq(Object.keys(b).concat(Object.keys(a)));
  for (const k of keys) Core.diff(a[k], b[k], path.concat(k), out);
  return out;
};
/* A readable path: names blocks by their source label, targets by table, value-map entries by value. */
Core.pathLabel = function (root, p) {
  const parts = [];
  let o = root;
  for (let i = 0; i < p.length; i++) {
    const k = p[i];
    const parentKey = i ? p[i - 1] : null;
    const next = o === null || typeof o !== 'object' ? undefined : o[k];
    if (typeof k === 'number') {
      let tag = '';
      if (parentKey === 'sources' && isObj(next)) tag = Core.blockLabels(next).join(' / ');
      else if (parentKey === 'sysbio_etl' && isObj(next)) tag = str(next.target_id) || str(next.table);
      else if (parentKey === 'value_map' && isObj(next)) tag = str('source_value' in next ? next.source_value : next.harmonized_value);
      else if (parentKey === 'links' && isObj(next)) tag = 'link ' + str(next.link_id);
      parts.push('[' + k + ']' + (tag ? ' ' + tag : ''));
    } else parts.push(k);
    o = next;
  }
  return parts.join(' › ');
};
Core.describe = function (v, max) {
  max = max || 80;
  if (v === undefined) return '(absent)';
  if (v === null) return 'null';
  if (typeof v === 'string') return v.length > max ? JSON.stringify(v.slice(0, max)) + '…' : JSON.stringify(v);
  if (typeof v !== 'object') return String(v);
  if (Core.isConcept(v)) { const c = Core.conceptOf(v); return (c.name || '(no name)') + ' · ' + (c.id === null || c.id === undefined ? 'no id' : c.id); }
  const s = JSON.stringify(v);
  return s.length > max ? s.slice(0, max) + '…' : s;
};

/* ── enumerated values seen across the loaded files (for pick lists) ── */
Core.collectEnums = function (roots) {
  const out = {};
  for (const k of Object.keys(K.ENUMS)) out[k] = new Map();
  for (const r of roots) Core.leaves(r, (p, v) => {
    if (typeof v !== 'string' || !v || v.length > 60) return;
    let key = p[p.length - 1];
    if (typeof key === 'number') key = p[p.length - 2];
    if (out[key]) out[key].set(v, (out[key].get(v) || 0) + 1);
  });
  const res = {};
  for (const k of Object.keys(out)) {
    const seen = Array.from(out[k].entries()).sort((a, b) => b[1] - a[1]).map(x => x[0]);
    res[k] = uniq(K.ENUMS[k].concat(seen));
  }
  return res;
};

/* ───────────────────────── clusters ───────────────────────── */
Core.DIMENSIONS = [
  { id: 'labelWord', name: 'Similar labels', help: 'Labels that share a word (or start with the same word, or are within a few edits of each other).' },
  { id: 'sourceColumn', name: 'Same source column', help: 'The same column of the same pinned file feeds both files.' },
  { id: 'pinnedFile', name: 'Same pinned source file', help: 'Both files read the same pinned file (matched by sha256, else accession).' },
  { id: 'valueOverlap', name: 'Overlapping harmonized values', help: 'The harmonized value sets overlap (Jaccard similarity at or above the threshold, at least 2 shared values).' },
  { id: 'l1Curie', name: 'Same Layer 1 CURIE', help: 'Same harmonized_element_curie (e.g. the same LOINC code).' },
  { id: 'l2Concept', name: 'Same Layer 2 defining concept', help: 'A target in each file has the same defining_concept_id.' },
  { id: 'grain', name: 'Same loading grain', help: 'Same anchor → entity on a source block (or the same older one_per).' },
  { id: 'l2TableField', name: 'Same Layer 2 table . concept field', help: 'A target in each file writes the same table and concept field.' }
];
function levenshtein(a, b, max) {
  if (Math.abs(a.length - b.length) > max) return max + 1;
  let prev = new Array(b.length + 1), cur = new Array(b.length + 1);
  for (let j = 0; j <= b.length; j++) prev[j] = j;
  for (let i = 1; i <= a.length; i++) {
    cur[0] = i;
    let rowMin = cur[0];
    for (let j = 1; j <= b.length; j++) {
      cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
      if (cur[j] < rowMin) rowMin = cur[j];
    }
    if (rowMin > max) return max + 1;
    [prev, cur] = [cur, prev];
  }
  return prev[b.length];
}
Core.levenshtein = levenshtein;
function components(n, edges) {
  const parent = Array.from({ length: n }, (_, i) => i);
  const find = x => { while (parent[x] !== x) { parent[x] = parent[parent[x]]; x = parent[x]; } return x; };
  for (const [a, b] of edges) { const ra = find(a), rb = find(b); if (ra !== rb) parent[ra] = rb; }
  const groups = new Map();
  for (let i = 0; i < n; i++) { const r = find(i); if (!groups.has(r)) groups.set(r, []); groups.get(r).push(i); }
  return Array.from(groups.values()).filter(g => g.length > 1);
}
function clustersFor(dim, sums, opt) {
  const keyed = new Map();
  const add = (key, label, i) => { if (!keyed.has(key)) keyed.set(key, { key, label, idx: new Set() }); keyed.get(key).idx.add(i); };
  const out = [];
  if (dim === 'labelWord') {
    const mode = opt.labelMode || 'word';
    if (mode === 'edit') {
      const max = Math.max(1, Number(opt.editDistance) || 2);
      const edges = [];
      for (let i = 0; i < sums.length; i++) for (let j = i + 1; j < sums.length; j++) if (levenshtein(sums[i].label, sums[j].label, max) <= max) edges.push([i, j]);
      for (const g of components(sums.length, edges)) out.push({ key: 'edit:' + g.map(i => sums[i].id).sort().join('|'), label: 'labels within ' + max + ' edits: ' + sums[g[0]].label + ' …', members: g });
      return out;
    }
    const maxShare = Number(opt.maxWordShare) || Infinity;
    sums.forEach((s, i) => {
      if (mode === 'first') { const w = s.label.toLowerCase().split(/[_\W]+/)[0]; if (w) add('first:' + w, 'first word “' + w + '”', i); }
      else for (const w of s.words) if (w.length >= (Number(opt.minWordLength) || 2)) add('word:' + w, 'word “' + w + '”', i);
    });
    for (const c of keyed.values()) if (c.idx.size > 1 && (mode !== 'word' || c.idx.size <= maxShare)) out.push({ key: c.key, label: c.label, members: Array.from(c.idx) });
    return out;
  }
  if (dim === 'valueOverlap') {
    const thr = Number(opt.jaccard) || 0.6;
    const sets = sums.map(s => new Set(s.hvals));
    const edges = [];
    for (let i = 0; i < sums.length; i++) {
      if (sets[i].size < 2) continue;
      for (let j = i + 1; j < sums.length; j++) {
        if (sets[j].size < 2) continue;
        let inter = 0;
        for (const v of sets[i]) if (sets[j].has(v)) inter++;
        if (inter < 2) continue;
        const jac = inter / (sets[i].size + sets[j].size - inter);
        if (jac >= thr) edges.push([i, j]);
      }
    }
    for (const g of components(sums.length, edges)) {
      const shared = Array.from(sets[g[0]]).filter(v => g.every(i => sets[i].has(v)));
      out.push({ key: 'values:' + g.map(i => sums[i].id).sort().join('|'), label: shared.length ? 'shared values: ' + shared.slice(0, 4).join(', ') + (shared.length > 4 ? ' …' : '') : 'overlapping values', members: g });
    }
    return out;
  }
  sums.forEach((s, i) => {
    if (dim === 'sourceColumn') for (const c of s.srcCols) add('col:' + c.key, 'column “' + c.label + '” in ' + c.files, i);
    else if (dim === 'pinnedFile') for (const p of s.pins) add('pin:' + p.key, 'file ' + (p.source_id ? p.source_id + ' ' : '') + (p.sha256 ? 'sha256 ' + p.sha256.slice(0, 12) + '…' : p.file), i);
    else if (dim === 'l1Curie') { if (s.curie) add('curie:' + s.curie, s.curie, i); }
    else if (dim === 'l2Concept') for (const c of s.concepts) add('concept:' + c.id, c.name + ' · ' + c.id, i);
    else if (dim === 'grain') for (const g of s.grains) add('grain:' + g, g, i);
    else if (dim === 'l2TableField') for (const tf of s.tableFields) add('tf:' + tf, tf, i);
  });
  for (const c of keyed.values()) if (c.idx.size > 1) out.push({ key: c.key, label: c.label, members: Array.from(c.idx) });
  return out;
}
/* Clusters for one or more dimensions; several dimensions = a file must share a value in every one. */
Core.clusters = function (sums, dims, opt) {
  opt = opt || {};
  if (!dims.length) return [];
  let cur = clustersFor(dims[0], sums, opt).map(c => ({ key: dims[0] + '=' + c.key, label: c.label, members: c.members.slice().sort((a, b) => a - b) }));
  for (const d of dims.slice(1)) {
    const next = clustersFor(d, sums, opt);
    const res = new Map();
    for (const a of cur) {
      const sa = new Set(a.members);
      for (const b of next) {
        const inter = b.members.filter(i => sa.has(i));
        if (inter.length < 2) continue;
        inter.sort((x, y) => x - y);
        const sig = inter.join(',');
        if (!res.has(sig)) res.set(sig, { key: a.key + ' & ' + d + '=' + b.key, label: a.label + ' + ' + b.label, members: inter });
      }
    }
    cur = Array.from(res.values());
  }
  const seen = new Map();
  for (const c of cur) {
    const sig = c.members.join(',');
    if (!seen.has(sig)) seen.set(sig, c);
  }
  return Array.from(seen.values()).map(c => ({ ...c, ids: c.members.map(i => sums[i].id) }))
    .sort((a, b) => b.members.length - a.members.length || (a.label < b.label ? -1 : 1));
};

/* Columns of the cluster comparison grid. */
Core.COMPARE_COLUMNS = [
  { id: 'forms', name: 'value_form' },
  { id: 'units', name: 'unit' },
  { id: 'grains', name: 'grain (anchor → entity)' },
  { id: 'curie', name: 'Layer 1 CURIE' },
  { id: 'srcCols', name: 'source columns' },
  { id: 'tableFields', name: 'Layer 2 table . field' },
  { id: 'concepts', name: 'Layer 2 defining concept' },
  { id: 'hvals', name: 'harmonized values' },
  { id: 'programs', name: 'programs' }
];
Core.compareCell = function (s, col) {
  switch (col) {
    case 'forms': return s.forms.join(', ');
    case 'units': return s.units.join(', ');
    case 'grains': return s.grains.join('; ');
    case 'curie': return s.curie;
    case 'srcCols': return s.srcCols.map(c => c.label).join(', ');
    case 'tableFields': return s.tableFields.join(', ');
    case 'concepts': return s.concepts.map(c => c.name + ' · ' + c.id).join('; ');
    case 'hvals': return s.hvals.length ? s.hvals.length + ': ' + s.hvals.slice(0, 6).join(', ') + (s.hvals.length > 6 ? ' …' : '') : '';
    case 'programs': return s.programs.join(', ');
  }
  return '';
};
/* Values at a field path with * for "every item", e.g. sources[*].layer_1_etl.unit */
Core.parsePattern = function (pat) {
  const out = [];
  const re = /([^.[\]]+)|\[(\*|\d+)\]/g;
  let m;
  while ((m = re.exec(pat))) out.push(m[1] !== undefined ? m[1] : m[2] === '*' ? '*' : Number(m[2]));
  return out;
};
Core.patternValues = function (root, pat) {
  const parts = Array.isArray(pat) ? pat : Core.parsePattern(pat);
  const res = [];
  (function walk(o, i, p) {
    if (i === parts.length) { res.push({ path: p, value: o }); return; }
    if (o === null || typeof o !== 'object') return;
    const k = parts[i];
    if (k === '*') { if (Array.isArray(o)) o.forEach((v, j) => walk(v, i + 1, p.concat(j))); else for (const kk of Object.keys(o)) walk(o[kk], i + 1, p.concat(kk)); }
    else if (k in o) walk(o[k], i + 1, p.concat(k));
  })(root, 0, []);
  return res;
};

return Core;
});
