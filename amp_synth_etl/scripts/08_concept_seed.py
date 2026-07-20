#!/usr/bin/env python3
"""Build the self-contained concept seed → cdm_load/concept_seed.sql (COPY cdm.concept FROM stdin).

Union of in-repo concept sources + every concept referenced by mappings/*.json, so the fact load has
ZERO dangling FKs. NO omop DB is used.
  base : exports/curated_concept_tables.sqlite :: curated_concept  (SINGLE SOURCE OF TRUTH)
  +    : exports/*.sqlite curated_concept  — for referenced ids not in base (e.g. the 5 LOINC ordinals)
  +    : synthesize referenced ids in NEITHER, from the maps' embedded {id,name,domain}
  +    : concept 0 ('No matching concept') — always (person demographics + concept-less obs maps land 0)
"""
import csv, glob, json, os, sqlite3, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQLITE = os.path.join(ROOT, "exports", "curated_concept_tables.sqlite")  # SINGLE SOURCE OF TRUTH for concepts
MAPS = os.path.join(ROOT, "mappings")
OUT  = os.path.join(ROOT, "cdm_load", "concept_seed.sql")
COLS = ["concept_id","concept_name","domain_id","vocabulary_id","concept_class_id",
        "standard_concept","concept_code","valid_start_date","valid_end_date","invalid_reason"]
LOINC = {40768112: ["Alternatively pronate and supinate right hand - 10 times [PhenX]","Observation","LOINC","Clinical Observation","S","65416-0","2011-05-02","2099-12-31",""],
         40768330: ["Alternatively pronate and supinate left hand - 10 times [PhenX]","Observation","LOINC","Clinical Observation","S","65639-7","2011-05-05","2099-12-31",""]}

def esc(v):
    if v is None or v == "": return "\\N"
    return str(v).replace("\\","\\\\").replace("\t"," ").replace("\n"," ").replace("\r"," ")

# 1. base from the SINGLE SOURCE OF TRUTH: exports/curated_concept_tables.sqlite :: curated_concept
rows = {}
_con = sqlite3.connect(SQLITE)
_have = [c[1] for c in _con.execute("PRAGMA table_info(curated_concept)")]
_sel = ",".join(c if c in _have else f"NULL AS {c}" for c in COLS)
for _row in _con.execute(f"SELECT {_sel} FROM curated_concept"):
    rows[int(_row[0])] = [("" if x is None else str(x)) for x in _row]
_con.close()
base_count = len(rows)

# 2. gather every concept id referenced by the maps + its embedded name/domain
ref = {}
def note(cid, name=None, domain=None):
    if cid in (None, ""): return
    cid = int(cid); e = ref.setdefault(cid, [None, None])
    if name and not e[0]: e[0] = name
    if domain and not e[1]: e[1] = domain
for p in glob.glob(os.path.join(MAPS, "*.json")):
    d = json.load(open(p, encoding="utf-8"))
    for v in d.get("lands", {}).values():
        if isinstance(v, dict) and v.get("id"): note(v["id"], v.get("name"), v.get("domain"))
    for vm in d.get("value_map", []):
        for key in ("value_as_concept_id", "unit_concept_id"):
            c = (vm.get("write") or {}).get(key)
            if isinstance(c, dict) and c.get("id"): note(c["id"], c.get("name"))
    for L in d.get("links", []):
        for kk, vv in L.items():
            if kk.endswith("_event_field_concept_id") and isinstance(vv, dict) and vv.get("id"): note(vv["id"], vv.get("name"))
        pt = (L.get("points_to") or {}).get("concept")
        if isinstance(pt, dict) and pt.get("id"): note(pt["id"], pt.get("name"), pt.get("domain"))
        rc = L.get("related_concept")
        if isinstance(rc, dict) and rc.get("id"): note(rc["id"], rc.get("name"), rc.get("domain"))
for cid in (0, 32035, 32036, 32817): note(cid)

# 3. supplement referenced-but-missing ids from any exports/*.sqlite curated_concept
missing = [c for c in ref if c not in rows]
supp = 0
for db in sorted(glob.glob(os.path.join(ROOT, "exports", "*.sqlite"))):
    if not missing: break
    try:
        con = sqlite3.connect(db); cur = con.cursor()
        tabs = [t[0] for t in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        if "curated_concept" not in tabs: con.close(); continue
        have = [c[1] for c in cur.execute("PRAGMA table_info(curated_concept)")]
        sel = ",".join(c if c in have else f"NULL AS {c}" for c in COLS)
        for row in cur.execute(f"SELECT {sel} FROM curated_concept WHERE concept_id IN ({','.join(map(str,missing))})"):
            cid = int(row[0])
            if cid not in rows: rows[cid] = [("" if x is None else str(x)) for x in row]; supp += 1
        con.close()
    except Exception as e:
        sys.stderr.write(f"[sqlite {os.path.basename(db)}] {e}\n")
    missing = [c for c in ref if c not in rows]

# 4. synthesize whatever is still missing from the maps' embedded {id,name,domain}
synth = []
for cid in sorted(c for c in missing if c != 0):
    if cid in LOINC:
        rows[cid] = [str(cid)] + LOINC[cid]
    else:
        nm, dom = ref[cid]
        rows[cid] = [str(cid), nm or f"AMP concept {cid}", dom or "Meas Value", "AMP Local",
                     "AMP Supplement", "", f"AMP:{cid}", "1970-01-01", "2099-12-31", ""]
    synth.append(cid)

# 5. concept 0 — always
if 0 not in rows:
    rows[0] = ["0","No matching concept","Metadata","None","Undefined","","No matching concept","1970-01-01","2099-12-31",""]

with open(OUT, "w", encoding="utf-8") as f:
    f.write("-- GENERATED by scripts/08_concept_seed.py — in-repo concept seed (0 dangling FKs).\n")
    f.write("SET search_path = cdm, public;\n")
    f.write("COPY cdm.concept (" + ",".join(COLS) + ") FROM stdin;\n")
    DFLT = {1: None, 2: "Metadata", 3: "None", 4: "Undefined", 6: None, 7: "1970-01-01", 8: "2099-12-31"}
    for cid in sorted(rows):
        row = list(rows[cid]) + [""]*(10 - len(rows[cid]))
        for i, dv in DFLT.items():                       # fill NOT-NULL columns the base TSV leaves blank
            if row[i] is None or str(row[i]).strip() == "":
                row[i] = dv if dv is not None else str(cid)   # concept_name/concept_code default to the id
        f.write("\t".join(esc(x) for x in row) + "\n")
    f.write("\\.\n")

print(f"concept_seed.sql: {len(rows)} rows (base {base_count}, +sqlite {supp}, +synth {len(synth)}, +concept0 1)")
print(f"  referenced by maps: {len(ref)} distinct ids")
print(f"  synthesized (in no in-repo source): {synth}")
