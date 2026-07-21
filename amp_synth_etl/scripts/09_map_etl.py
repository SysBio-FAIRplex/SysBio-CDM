#!/usr/bin/env python3
"""Map-DRIVEN ETL engine.  Reads mappings/*.json and EMITS cdm_load/cdm_facts_load.sql — one generic
INSERT…SELECT per map into cdm.observation / cdm.measurement.  There is NO per-variable hardcoding: the
table, concept, value routing, anchors and links all come from the map.  `derived_from` is a GENERATION
concern and is ignored here.  Each source value fans out into its OWN record (one -> many, never many -> one).

FK integrity is kept intact: person_id (inner join), visit_occurrence_id (the SPECIFIC visit for visit-grain,
the participant's BASELINE visit for subject-grain — never dropped when a visit exists), and every
*_concept_id resolves to a seeded concept.

  python scripts/09_map_etl.py            # DEFAULT: approved-only (manual_approval == true)
  python scripts/09_map_etl.py --all       # dev override: every map (still skips concept-less)
"""
import argparse, glob, json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAPS = os.path.join(ROOT, "mappings")
OUT  = os.path.join(ROOT, "cdm_load", "cdm_facts_load.sql")
TYPE_CONCEPT = 32817                                        # 'EHR' — the type concept the in-repo ETL uses
ABBR = {"observation": "obs", "measurement": "meas"}
# CDM-Field concept id -> (target table, its PK column)  [ground truth from the live schema]
FIELD = {1147165: ("observation", "observation_id"), 1147138: ("measurement", "measurement_id"),
         1147026: ("person", "person_id"), 1147070: ("visit_occurrence", "visit_occurrence_id"),
         1147082: ("procedure_occurrence", "procedure_occurrence_id"),
         1147127: ("condition_occurrence", "condition_occurrence_id"), 1147049: ("specimen", "specimen_id")}

def sq(v):   return "'" + str(v).replace("'", "''") + "'"        # SQL string literal
def ident(v): return '"' + str(v).replace('"', '""') + '"'      # quoted identifier
def numlit(v):
    if v is None: return "\\N"
    try:
        f = float(v); return str(int(f)) if f == int(f) else repr(f)
    except (TypeError, ValueError): return "\\N"
def txt(v):  return "\\N" if v is None else str(v).replace("\\","\\\\").replace("\t"," ").replace("\n"," ").replace("\r"," ")

def staging_columns():
    """The AMP-variable columns that actually exist in staging.amp_clinical (in-repo DDL copy)."""
    ddl = open(os.path.join(ROOT, "cdm_load", "_amp_clinical_ddl.sql"), encoding="utf-8").read()
    return set(re.findall(r'^\s+"?([A-Za-z_][\w.]*)"?\s+(?:text|date),?$', ddl, re.M))

def defining(m):
    t = (m.get("lands") or {}).get("table")
    if t not in ("observation", "measurement"): return None, None
    c = m["lands"].get(f"{t}_concept_id")
    if not isinstance(c, dict) or not c.get("id"): return t, None
    return t, int(c["id"])

def emit_insert(m, var, tbl, cid):
    visit = "visit_occurrence_id" in (m.get("anchored_to") or {})
    vm = m.get("value_map") or []
    numeric = len(vm) == 1 and vm[0].get("value") == "<any in range>"
    has_vas = (tbl == "observation")
    C = ident(var)
    cols = [f"{tbl}_id", "person_id", f"{tbl}_concept_id", f"{tbl}_date", f"{tbl}_type_concept_id"]
    sel  = [f"NEXTVAL('cdm.{tbl}_id_seq')", "p.person_id", str(cid), "src.visit_date", str(TYPE_CONCEPT)]
    if numeric:
        rng = (m.get("reads_as") or {}).get("range") or {}
        case = f"CASE WHEN src.{C} ~ '^-?[0-9]+(\\.[0-9]+)?$'"
        if rng.get("min") is not None and rng.get("max") is not None:
            case += f" AND src.{C}::numeric BETWEEN {rng['min']} AND {rng['max']}"
        case += f" THEN src.{C}::numeric END"
        cols.append("value_as_number"); sel.append(case)
    else:
        cols.append("value_as_number"); sel.append("vm.value_as_number")
        if has_vas: cols.append("value_as_string"); sel.append("vm.value_as_string")
        cols.append("value_as_concept_id"); sel.append("vm.value_as_concept_id")
        if has_vas: cols.append("qualifier_concept_id"); sel.append("vm.qualifier_concept_id")
    cols += [f"{tbl}_source_value", "value_source_value", "visit_occurrence_id"]
    sel  += [sq(var), f"(src.{C})::text", "vo.visit_occurrence_id"]

    if visit:
        frm = ("FROM staging.amp_clinical src\n"
               "JOIN staging.person_map p ON p.person_source_value = src.person_source_value\n"
               "LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value = src.visit_source_value AND vo.person_id = p.person_id\n")
        where_ne = (f"  AND NOT EXISTS (SELECT 1 FROM cdm.{tbl} t WHERE t.person_id = p.person_id "
                    f"AND t.{tbl}_concept_id = {cid} AND t.{tbl}_source_value = {sq(var)} "
                    f"AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id)")
    else:  # subject-grain: one fact/person, anchored to the participant's baseline (earliest) visit
        frm = (f"FROM (SELECT DISTINCT ON (person_source_value) person_source_value, visit_source_value, visit_date, {C}\n"
               f"        FROM staging.amp_clinical WHERE {C} IS NOT NULL\n"
               f"        ORDER BY person_source_value, visit_date) src\n"
               "JOIN staging.person_map p ON p.person_source_value = src.person_source_value\n"
               "LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value = src.visit_source_value AND vo.person_id = p.person_id\n")
        where_ne = (f"  AND NOT EXISTS (SELECT 1 FROM cdm.{tbl} t WHERE t.person_id = p.person_id "
                    f"AND t.{tbl}_concept_id = {cid} AND t.{tbl}_source_value = {sq(var)})")
    if not numeric:
        frm += f"LEFT JOIN _valuemap vm ON vm.variable = {sq(var)} AND vm.source_value = src.{C}\n"
    return (f"-- [{var}] -> {tbl} {cid}  ({'numeric' if numeric else 'coded'}, {'visit' if visit else 'subject'})\n"
            f"INSERT INTO cdm.{tbl} (\n    " + ", ".join(cols) + ")\nSELECT\n    " + ",\n    ".join(sel) + "\n" + frm +
            f"WHERE src.{C} IS NOT NULL AND src.person_source_value IS NOT NULL\n" + where_ne + ";\n")

def emit_link(m, var, tbl, cid, L):
    mech = L.get("mechanism")                                   # e.g. observation_event_id
    fld = next((vv.get("id") for k, vv in L.items()
                if k.endswith("_event_field_concept_id") and isinstance(vv, dict)), None)
    if not mech or not fld or fld not in FIELD: return None
    ptbl, ppk = FIELD[fld]
    tgt = ((L.get("points_to") or {}).get("concept") or {}).get("id")
    if not tgt: return None
    abbr = ABBR[tbl]
    same = f"\n  AND parent.{ppk} <> child.{tbl}_id" if ptbl == tbl else ""
    return (f"-- PASS 2 [{var}] realized event-FK: {mech} -> {ptbl}.{ppk} of the concept-{tgt} record\n"
            f"UPDATE cdm.{tbl} child SET {mech} = parent.{ppk}, {abbr}_event_field_concept_id = {fld}\n"
            f"FROM cdm.{ptbl} parent\n"
            f"WHERE child.{tbl}_source_value = {sq(var)} AND child.{tbl}_concept_id = {cid}\n"
            f"  AND parent.person_id = child.person_id AND parent.{ptbl}_concept_id = {tgt}{same}\n"
            f"  AND child.{mech} IS NULL;\n")

def _approved(v):
    return v is True or (isinstance(v, str) and v.strip().upper() in ("TRUE", "YES", "1"))

def load_parked():
    """Variables to EXCLUDE from the load — the separate parked list (config/parked_variables.tsv)."""
    parked, fp = set(), os.path.join(os.path.dirname(MAPS), "config", "parked_variables.tsv")
    if os.path.exists(fp):
        for i, line in enumerate(open(fp, encoding="utf-8")):
            t = line.rstrip("\n")
            if not t.strip() or t.startswith("#"): continue
            if i == 0 and t.lower().startswith("variable"): continue
            parked.add(t.split("\t")[0].strip())
    return parked

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--all", action="store_true"); a = ap.parse_args()
    stcols = staging_columns()
    inserts, links, valuemap = [], [], {}
    n_scope = n_concept_less = n_numeric = n_coded = n_subject = n_no_source = n_parked = 0
    parked = load_parked()
    for p in sorted(glob.glob(os.path.join(MAPS, "*.json"))):
        m = json.load(open(p, encoding="utf-8"))
        var = m.get("variable")
        if var in parked:
            n_parked += 1; continue
        if not a.all and not _approved(m.get("manual_approval")):
            continue
        n_scope += 1
        tbl, cid = defining(m)
        if var not in stcols:
            n_no_source += 1; continue          # no such column in staging.amp_clinical
        if not tbl or not cid:
            n_concept_less += 1; continue
        inserts.append(emit_insert(m, var, tbl, cid))
        vm = m.get("value_map") or []
        numeric = len(vm) == 1 and vm[0].get("value") == "<any in range>"
        if numeric: n_numeric += 1
        else:
            n_coded += 1
            for e in vm:
                v = e.get("value"); w = e.get("write") or {}
                if v is None: continue
                vc = (w.get("value_as_concept_id") or {}).get("id") if isinstance(w.get("value_as_concept_id"), dict) else None
                qc = (w.get("qualifier_concept_id") or {}).get("id") if isinstance(w.get("qualifier_concept_id"), dict) else None
                valuemap[(var, str(v))] = (vc, w.get("value_as_string"), w.get("value_as_number"), qc)
        if "visit_occurrence_id" not in (m.get("anchored_to") or {}): n_subject += 1
        for L in m.get("links") or []:
            if L.get("kind") == "realized":
                u = emit_link(m, var, tbl, cid, L)
                if u: links.append(u)

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("-- GENERATED by scripts/09_map_etl.py — map-driven AMP->CDM fact load. Self-contained.\n")
        f.write(f"-- scope: {'ALL maps (--all)' if a.all else 'approved-only'}; "
                f"{len(inserts)} facts, {n_coded} coded / {n_numeric} numeric, {n_subject} subject-anchored, "
                f"{len(links)} realized links; {n_concept_less} skipped (no defining concept).\n")
        f.write("\\set ON_ERROR_STOP on\nSET search_path = cdm, public;\n")
        f.write("CREATE SEQUENCE IF NOT EXISTS cdm.observation_id_seq;\nCREATE SEQUENCE IF NOT EXISTS cdm.measurement_id_seq;\n\n")
        f.write("CREATE TEMP TABLE _valuemap (variable text, source_value text, value_as_concept_id integer, value_as_string text, value_as_number numeric, qualifier_concept_id integer);\n")
        f.write("COPY _valuemap (variable, source_value, value_as_concept_id, value_as_string, value_as_number, qualifier_concept_id) FROM stdin;\n")
        for (var, val), (vc, vas, vn, qc) in sorted(valuemap.items()):
            f.write("\t".join([txt(var), txt(val),
                               (str(int(vc)) if vc else "\\N"), txt(vas), numlit(vn),
                               (str(int(qc)) if qc else "\\N")]) + "\n")
        f.write("\\.\nCREATE INDEX ON _valuemap (variable, source_value);\n\n")
        f.write("\\echo '>> pass 1: facts'\n")
        for s in inserts: f.write(s + "\n")
        if links:
            f.write("\\echo '>> pass 2: realized event-links'\n")
            for u in links: f.write(u + "\n")
        f.write("\\echo '>> row counts:'\n")
        f.write("SELECT 'observation' tbl, count(*) FROM cdm.observation UNION ALL SELECT 'measurement', count(*) FROM cdm.measurement;\n")

    print(f"wrote {os.path.relpath(OUT, ROOT)}")
    print(f"scope={'ALL' if a.all else 'approved-only'}: {n_scope} in scope, {len(inserts)} facts "
          f"({n_coded} coded / {n_numeric} numeric, {n_subject} subject-anchored), "
          f"{len(valuemap)} value-map rows, {len(links)} realized links, {n_concept_less} skipped (concept-less), {n_parked} parked")

if __name__ == "__main__":
    main()
