"""Check mapping specs against the registry's rules. Deterministic; no judgement.

    spec_check.py <registry dir or spec files...> [--tsv <report.tsv>] [--quiet]

A spec PASSES when: it parses and its registry_label matches the file name; the definition is one plain sentence without
process text or bracketed citations; every source block names its program and column, pins at least one file by sha256,
declares loading_grain {anchor, entity, attribute} with the element's own label as attribute, and carries value lines unless
its value_form is continuous, identifier, date or text; the wording of harmonized values is the specification author's and is not checked; every value line maps onto the declared value
domain; Layer 2 has at least one target whose defining concept's domain matches its table and whose anchored_to names
person_id; and, when CDM_VOCAB_DSN is set, every concept id exists in the vocabulary, is Standard, and carries the
vocabulary's name. Exit code 1 when any spec fails."""
import json, os, sys, csv, subprocess, re

DOMAIN_FOR_TABLE = {"measurement": "Measurement", "observation": "Observation", "specimen": "Specimen", "procedure_occurrence": "Procedure",
                    "condition_occurrence": "Condition", "drug_exposure": "Drug", "device_exposure": "Device", "visit_occurrence": "Visit"}
CONCEPT_FIELD_FOR_TABLE = {"measurement": "measurement_concept_id", "observation": "observation_concept_id", "specimen": "specimen_concept_id",
                           "procedure_occurrence": "procedure_concept_id", "condition_occurrence": "condition_concept_id", "drug_exposure": "drug_concept_id",
                           "device_exposure": "device_concept_id", "visit_occurrence": "visit_concept_id"}
FIELD_DOMAIN = {"anatomic_site_concept_id": "Spec Anatomic Site", "unit_concept_id": "Unit", "disease_status_concept_id": None}   # specimen columns with their own domains
def wanted_domain(table, field):
    if field in FIELD_DOMAIN: return FIELD_DOMAIN[field]
    return DOMAIN_FOR_TABLE.get(table)
DEMOGRAPHIC_DOMAINS = {"Race", "Ethnicity", "Gender"}       # demographic facts are observation rows; the person table carries only the subject identifier
def domain_ok(table, field, domain, paired=False):
    want = wanted_domain(table, field)
    # a yes/no symptom keeps its observation row (the answer either way) beside a condition_occurrence row that fires only on the
    # affirmative value, both on the same Condition concept
    return (not want) or domain == want or (table == "observation" and (domain in DEMOGRAPHIC_DOMAINS or (domain == "Condition" and paired)))
def condition_pairs(j):
    return {str((r.get("defining_concept_id") or {}).get("id")) for r in (j.get("sysbio_etl") or []) if isinstance(r, dict) and r.get("table") == "condition_occurrence" and isinstance(r.get("defining_concept_id"), dict)}
def field_ok(table, field):
    return field == CONCEPT_FIELD_FOR_TABLE.get(table) or (table == "specimen" and field in FIELD_DOMAIN)
FILE_KINDS = {"csv", "tsv", "xlsx", "jsonl", "json", "sidecar", "fields", "soft", "rds"}
ONTOLOGY_LABEL_SUFFIXES = ("_curie_label", "_ontology_label", "_term_name")        # an ontology's own wording is kept as the ontology writes it
# companions land nothing of their own at Layer 2: a unit rides its parent's row as unit_concept_id, an ontology identifier or label stays a Layer 1 column
COMPANION_SUFFIXES = ("_units", "_unit", "_unit_ontology_label", "_curie_id", "_curie_label", "_ontology_id", "_ontology_term_id", "_ontology_label", "_term_id")
ANCHORS = {"participant_id", "specimen_id", "library_id", "assay_id", "sample_id", "file_id", "dataset_id"}
EXTENSION_TABLES = {"assay", "file", "files", "assay_to_specimen", "assay_input_file"}
ENTITIES = {"participant", "participant_visit", "specimen", "library", "assay", "file", "dataset"}
NO_VALUE_LINES_NEEDED = {"continuous", "identifier", "date", "text"}
PROCESS_WORDS = ("ruling", "session", "generated", "added 20", "review", "todo", "retired", "blanked", "draft -", "source column(s)", "20" + "26-")
def has_citation(text):
    """A dictionary citation is a bracketed reference to a file or a field, like [file.tsv::field]; an interval such as [60,70) is not."""
    i = 0
    while True:
        a = text.find("[", i)
        if a < 0: return False
        b = text.find("]", a + 1)
        if b < 0: return False
        inner = text[a + 1:b]
        if "::" in inner or any(inner.lower().endswith(ext) or ext + " " in inner.lower() for ext in (".tsv", ".csv", ".json", ".xlsx", ".jsonl", ".txt", ".pdf")): return True
        i = b + 1

FILE_TOKEN = re.compile(r"\S+\.(?:xlsx|csv|tsv|jsonl|rds|soft\.gz|h5ad|txt)\b", re.I)
def names_a_file(text): return bool(FILE_TOKEN.search(str(text or "")))
def is_curie(tok): 
    a, _, b = tok.partition(":"); return bool(a) and bool(b) and a.isalpha() and a[0].isupper() and b.replace("_", "").isalnum()
def is_number(tok): return tok.replace(".", "", 1).replace("-", "", 1).replace(",", "").isdigit()
def check(path, vocab_rows=None):
    """Return (label, [problems])."""
    label = os.path.splitext(os.path.basename(path))[0]; P = []
    try: j = json.load(open(path, encoding="utf-8"))
    except Exception as e: return label, [f"does not parse: {type(e).__name__}"]
    if not isinstance(j, dict): return label, ["not a JSON object"]
    if j.get("registry_label") != label: P.append(f"registry_label {j.get('registry_label')!r} differs from the file name")
    if not j.get("schema_version"): P.append("no schema_version")
    d = str(j.get("definition") or "").strip(); low = " " + d.lower() + " "
    if not d: P.append("no definition")
    else:
        if any(w in low for w in PROCESS_WORDS): P.append("definition carries process text")
        if has_citation(d): P.append("definition carries a dictionary citation; the citation belongs in src_dictionary")
        if names_a_file(d): P.append("definition names a data file")
    if not j.get("programs_covered"): P.append("no programs_covered")
    hv = j.get("harmonized_values")
    if not isinstance(hv, list): P.append("no harmonized_values list"); hv = []
    blocks = [s for s in (j.get("sources") or []) if isinstance(s, dict)]
    if not blocks: P.append("no source blocks")
    for i, s in enumerate(blocks):
        where = f"block {i} ({s.get('program')}:{s.get('source_label')})"
        if not s.get("program"): P.append(f"{where}: no program")
        if s.get("source_label") in (None, ""): P.append(f"{where}: no source_label")
        l1 = s.get("layer_1_etl") or {}
        lay = s.get("layout") or {}
        if isinstance(lay, dict) and lay.get("file_type") not in (None, "") and lay["file_type"] not in FILE_KINDS: P.append(f"{where}: layout file_type {lay['file_type']!r} is not a kind the loader reads")
        pins = [x for x in (l1.get("data_files") or []) if isinstance(x, dict)]
        if not any(x.get("sha256") for x in pins): P.append(f"{where}: no file pinned by sha256")
        g = s.get("loading_grain")
        if not isinstance(g, dict): P.append(f"{where}: no loading_grain")
        else:
            if g.get("anchor") not in ANCHORS: P.append(f"{where}: loading_grain.anchor {g.get('anchor')!r} not one of {sorted(ANCHORS)}")
            if g.get("entity") not in ENTITIES: P.append(f"{where}: loading_grain.entity {g.get('entity')!r} not one of {sorted(ENTITIES)}")
            if g.get("attribute") != label: P.append(f"{where}: loading_grain.attribute is not the element's label")
        vf = l1.get("value_form"); vm = [e for e in (l1.get("value_map") or []) if isinstance(e, dict)]
        if not vm and vf not in NO_VALUE_LINES_NEEDED and not l1.get("range"): P.append(f"{where}: no value lines and value_form {vf!r} needs them")
        for e in vm:
            h = e.get("harmonized_value")
            if h in (None, ""): P.append(f"{where}: value line {e.get('source_value')!r} has no harmonized value"); break
            if hv and h not in hv and h != "<any in range>": P.append(f"{where}: value {h!r} is not in harmonized_values"); break
    recs = [r for r in (j.get("sysbio_etl") or []) if isinstance(r, dict)]
    if not recs and not label.endswith(COMPANION_SUFFIXES): P.append("no Layer 2 target")
    for i, r in enumerate(recs):
        t = str(r.get("table") or ""); dc = r.get("defining_concept_id") or {}
        if "target_id" not in r: P.append(f"target {i}: no target_id key")
        if not t: P.append(f"target {i}: no table")
        if t in EXTENSION_TABLES:                      # an extension-table target names table and column; no OMOP concept
            if not r.get("column"): P.append(f"target {i} ({t}): extension-table target without a column")
            if not isinstance(r.get("anchored_to"), dict): P.append(f"target {i} ({t}): anchored_to missing")
            continue
        if t == "parent":                              # a parent-riding target names the parent element and the column it fills
            if not r.get("parent_label") or not r.get("column"): P.append(f"target {i}: parent target needs parent_label and column")
            elif not os.path.exists(os.path.join(os.path.dirname(path), str(r["parent_label"]) + ".json")): P.append(f"target {i}: parent element {r['parent_label']!r} is not in the registry")
            continue
        if not isinstance(dc, dict) or not dc.get("id"): P.append(f"target {i} ({t}): no defining concept")
        else:
            want = wanted_domain(t, dc.get("target_field"))
            if want and dc.get("domain") and not domain_ok(t, dc.get("target_field"), dc["domain"], str(dc.get("id")) in condition_pairs(j)): P.append(f"target {i}: defining concept domain {dc['domain']} in table {t} (must be {want})")
            if DOMAIN_FOR_TABLE.get(t) and dc.get("target_field") and not field_ok(t, dc["target_field"]): P.append(f"target {i}: target_field {dc['target_field']} is not {CONCEPT_FIELD_FOR_TABLE.get(t)}")
        a = r.get("anchored_to")
        if not isinstance(a, dict) or "person_id" not in a: P.append(f"target {i} ({t}): anchored_to does not name person_id")
        for e in r.get("value_map") or []:
            h = e.get("harmonized_value") if isinstance(e, dict) else None
            if h not in (None, "<any in range>") and hv and h not in hv: P.append(f"target {i}: value {h!r} is not in harmonized_values"); break
    if vocab_rows is not None:
        for cid, name, role, t, *rest in iter_concepts(j):
            field = rest[0] if rest else None
            v = vocab_rows.get(str(cid))
            if not v: P.append(f"concept {cid} ({role}) is not in the vocabulary"); continue
            if v[5] != "S": P.append(f"concept {cid} {v[1]!r} ({role}) is not Standard")
            if name and v[1].strip().lower() != str(name).strip().lower(): P.append(f"concept {cid} ({role}) is named {name!r}; the vocabulary says {v[1]!r}")
            if role == "defining" and not domain_ok(t, field, v[2], str(cid) in condition_pairs(j)): P.append(f"concept {cid} ({role}) has domain {v[2]} but sits in table {t}")
    return label, P

def iter_concepts(j):
    for r in j.get("sysbio_etl") or []:
        if not isinstance(r, dict): continue
        t = str(r.get("table") or ""); d = r.get("defining_concept_id") or {}
        if isinstance(d, dict) and d.get("id"): yield d["id"], d.get("name"), "defining", t, d.get("target_field")
        for e in r.get("value_map") or []:
            if isinstance(e, dict):
                for k, v in e.items():
                    if k.endswith("_concept_id") and isinstance(v, dict) and v.get("id"): yield v["id"], v.get("name"), k, t, None
    for l in j.get("links") or []:
        for k in ("linking_mechanism_concept_id", "inverse_concept_id", "linked_defining_concept"):
            c = l.get(k) if isinstance(l, dict) else None
            if isinstance(c, dict) and c.get("id"): yield c["id"], c.get("name"), "link:" + k, ""

def vocabulary(paths):
    """With CDM_VOCAB_DSN set, fetch every concept the specs cite in one query; else None (vocabulary checks skipped)."""
    dsn = os.environ.get("CDM_VOCAB_DSN")
    if not dsn: return None
    ids = set()
    for p in paths:
        try: j = json.load(open(p, encoding="utf-8"))
        except Exception: continue
        ids |= {str(c[0]) for c in iter_concepts(j) if str(c[0]).isdigit()}
    rows = {}
    ids = sorted(ids)
    for i in range(0, len(ids), 1000):
        sql = "select concept_id, concept_name, domain_id, vocabulary_id, concept_class_id, coalesce(standard_concept,'N') from cdm.concept where concept_id in (" + ",".join(ids[i:i + 1000]) + ")"
        r = subprocess.run(["psql", dsn, "-At", "-F", "\t", "-c", sql], capture_output=True, text=True)
        if r.returncode: raise SystemExit("vocabulary query failed: " + r.stderr.strip())
        for line in r.stdout.splitlines():
            f = line.split("\t"); rows[f[0]] = f
    store = os.environ.get("CDM_CURATED_CONCEPTS")          # a curated concept store (sqlite, table curated_concept) answers for ids a vocabulary snapshot lacks
    missing = [i for i in ids if i not in rows]
    if store and missing and os.path.exists(store):
        import sqlite3
        con = sqlite3.connect(store)
        for chunk in (missing[k:k + 500] for k in range(0, len(missing), 500)):
            q = "select concept_id, concept_name, domain_id, vocabulary_id, concept_class_id, standard_concept from curated_concept where concept_id in (%s)" % ",".join("?" * len(chunk))
            for row in con.execute(q, chunk): rows[str(row[0])] = [str(x) if x is not None else "" for x in row]
        con.close()
    return rows

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]; tsv = sys.argv[sys.argv.index("--tsv") + 1] if "--tsv" in sys.argv else None; quiet = "--quiet" in sys.argv
    paths = []
    for a in args:
        if os.path.isdir(a): paths += sorted(os.path.join(a, f) for f in os.listdir(a) if f.endswith(".json"))
        else: paths.append(a)
    vocab_rows = vocabulary(paths)
    results = [check(p, vocab_rows) for p in paths]
    failed = [(l, P) for l, P in results if P]
    if tsv:
        with open(tsv, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, delimiter="\t", lineterminator="\n"); w.writerow(["element", "verdict", "problems"])
            for l, P in results: w.writerow([l, "FAIL" if P else "PASS", " | ".join(P)])
    if not quiet:
        for l, P in failed: print(f"FAIL {l}: " + " | ".join(P[:4]) + (f" | +{len(P) - 4} more" if len(P) > 4 else ""))
    print(f"{len(results) - len(failed)} pass, {len(failed)} fail of {len(results)}" + ("" if vocab_rows is not None else " (vocabulary checks skipped: CDM_VOCAB_DSN not set)"))
    sys.exit(1 if failed else 0)

if __name__ == "__main__":
    main()
