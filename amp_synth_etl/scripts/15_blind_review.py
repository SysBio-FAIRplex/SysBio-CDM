#!/usr/bin/env python3
"""
15_blind_review.py — the cold-reviewer gate. Run BEFORE every push:

    python3 scripts/15_blind_review.py <database>

Asks the questions a reviewer who has never seen this pipeline asks on day one —
the "obvious thing we should not have overlooked" class of defect that 04_qc
(generation QC), 13 (governance) and 14 (user stories) do not cover:

  * Does EVERY person have visits? an observation period? a specimen?
  * Do events actually LINK to visits — observation, measurement, condition,
    procedure — or do FKs sit NULL? (Named, counted exceptions only.)
  * Are files present, and does every file reach at least one donor?
  * Are procedures and conditions populated, or silently empty?
  * Does the lineage graph use only Standard relationship concepts, with every
    endpoint resolving and every reciprocal pair complete?
  * Any specimen at concept 0? Any date before the 1899-12-01 screen floor?
  * Is any expected-nonempty table empty?

Every check prints PASS / WARN / FAIL with its numbers. Exit 0 = no FAIL.
WARNs are review prompts, not blockers — they carry their explanation inline.

Known, principled exceptions (counted, never waved through silently):
  * measurement rows with concept 1176306 (specimen-lineage derivation records)
    carry no visit — they are linkage facts, not clinical events.
  * observation rows with concept 4303445 (file-membership records, Beta-2 ask 7)
    carry no visit — file membership is not a visit event.
"""
import subprocess
import sys

LINEAGE_MEAS_CONCEPT = 1176306   # 'Unique identifier of Initial sample' — derivation records
FILE_OBS_CONCEPT = 4303445       # 'Research data collection' — file-membership records (ask 7)
STANDARD_REL_PAIRS = (32668, 32669, 581410, 581411, 581436, 581437,
                      46233682, 46233683, 46233684, 46233685)
DATE_FLOOR = "1899-12-01"        # pre-baseline screens legitimately land 1899-12-02

db = sys.argv[1] if len(sys.argv) > 1 else "v6check"
results = {"PASS": 0, "WARN": 0, "FAIL": 0}


def q(sql):
    r = subprocess.run(["psql", "-d", db, "-At", "-c", sql], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  [FAIL] query error: {r.stderr.strip()[:160]}")
        results["FAIL"] += 1
        return None
    return [row.split("|") for row in r.stdout.strip().split("\n")] if r.stdout.strip() else []


def check(label, ok, detail, warn=False):
    tag = "PASS" if ok else ("WARN" if warn else "FAIL")
    results[tag] += 1
    print(f"  [{tag}] {label} — {detail}")


def one(sql):
    r = q(sql)
    return r[0][0] if r else None


print(f"== BLIND REVIEW of {db} — the questions a cold reviewer asks first ==\n")

# ---- 1. population coverage -------------------------------------------------
print("1. Does every person have the basics?")
n_person = int(one("SELECT COUNT(*) FROM cdm.person"))
for what, sql in (
        ("a visit",              "SELECT COUNT(DISTINCT person_id) FROM cdm.visit_occurrence"),
        ("an observation_period","SELECT COUNT(DISTINCT person_id) FROM cdm.observation_period"),
        ("a specimen",           "SELECT COUNT(DISTINCT person_id) FROM cdm.specimen"),
        ("an observation",       "SELECT COUNT(DISTINCT person_id) FROM cdm.observation")):
    n = int(one(sql))
    check(f"every person has {what}", n == n_person, f"{n}/{n_person}")
n_file_persons = int(one(f"SELECT COUNT(DISTINCT person_id) FROM cdm.observation WHERE observation_concept_id={FILE_OBS_CONCEPT}"))
check("persons appearing in at least one data file", n_file_persons >= n_person * 0.5,
      f"{n_file_persons}/{n_person} — only assayed specimens yield files; below 50% would mean the file layer broke",
      warn=(n_file_persons < n_person))

# ---- 2. event -> visit linkage ---------------------------------------------
print("\n2. Do events link to visits?")
for tbl, exc_sql, exc_name in (
        ("observation",          f"observation_concept_id={FILE_OBS_CONCEPT}",   "file-membership records"),
        ("measurement",          f"measurement_concept_id={LINEAGE_MEAS_CONCEPT}", "lineage derivation records"),
        ("condition_occurrence", "FALSE", None),
        ("procedure_occurrence", "FALSE", None)):
    r = q(f"SELECT COUNT(*), COUNT(visit_occurrence_id) FROM cdm.{tbl} WHERE NOT ({exc_sql})")
    total, linked = int(r[0][0]), int(r[0][1])
    check(f"cdm.{tbl}: every non-exempt row carries visit_occurrence_id",
          total == linked, f"{linked}/{total} linked")
    if exc_name:
        n_exc = int(one(f"SELECT COUNT(*) FROM cdm.{tbl} WHERE {exc_sql}"))
        n_exc_linked = int(one(f"SELECT COUNT(visit_occurrence_id) FROM cdm.{tbl} WHERE {exc_sql}"))
        check(f"cdm.{tbl}: exempt rows ({exc_name}) stay visit-less by design",
              n_exc_linked == 0, f"{n_exc} exempt rows, {n_exc_linked} unexpectedly visit-linked", warn=True)
orph = int(one("""SELECT COUNT(*) FROM (
    SELECT visit_occurrence_id v FROM cdm.observation WHERE visit_occurrence_id IS NOT NULL
    UNION ALL SELECT visit_occurrence_id FROM cdm.measurement WHERE visit_occurrence_id IS NOT NULL
    UNION ALL SELECT visit_occurrence_id FROM cdm.condition_occurrence WHERE visit_occurrence_id IS NOT NULL
    UNION ALL SELECT visit_occurrence_id FROM cdm.procedure_occurrence WHERE visit_occurrence_id IS NOT NULL) x
    LEFT JOIN cdm.visit_occurrence vo ON vo.visit_occurrence_id = x.v WHERE vo.visit_occurrence_id IS NULL"""))
check("no event points at a visit that does not exist", orph == 0, f"{orph} orphan visit references")

# ---- 3. the file layer ------------------------------------------------------
print("\n3. Is the file layer whole?")
n_files = int(one("SELECT COUNT(*) FROM cdm.files"))
check("cdm.files is populated", n_files > 0, f"{n_files} files")
# THE rule this gate exists for: no specimen without a file — a file is the only way a
# specimen is known to exist. Evidence is either an assay product (per-sample raw file or a
# cohort matrix the specimen's assay feeds) or the owner's membership in the programme's
# biospecimen metadata file (banked / parent specimens).
dangling = int(one(f"""SELECT COUNT(*) FROM cdm.specimen s WHERE NOT EXISTS (
    SELECT 1 FROM cdm.assay_to_specimen a2s JOIN cdm.assay a ON a.assay_id = a2s.assay_id
    WHERE a2s.specimen_id = s.specimen_id
      AND (EXISTS (SELECT 1 FROM cdm.files f WHERE f.assay_id = a.assay_id)
           OR EXISTS (SELECT 1 FROM cdm.assay_input_file aif WHERE aif.assay_id = a.assay_id)))
    AND NOT EXISTS (
    SELECT 1 FROM cdm.observation o JOIN cdm.files f ON f.file_id = o.observation_event_id
    WHERE o.person_id = s.person_id AND o.observation_concept_id = {FILE_OBS_CONCEPT}
      AND f.file_name LIKE '%biospecimen_metadata%')"""))
n_spec = int(one("SELECT COUNT(*) FROM cdm.specimen"))
check("NO specimen without an attesting file (assay product or metadata)", dangling == 0,
      f"{dangling}/{n_spec} specimens with no file evidence")
unreached = int(one(f"""SELECT COUNT(*) FROM cdm.files f LEFT JOIN cdm.observation o
    ON o.observation_event_id = f.file_id AND o.observation_concept_id = {FILE_OBS_CONCEPT}
    WHERE o.observation_id IS NULL"""))
check("every file reaches at least one donor (ask-7 observation)", unreached == 0,
      f"{unreached}/{n_files} files with NO donor record")
img_orph = int(one(f"""SELECT COUNT(*) FROM cdm.observation o LEFT JOIN cdm.files f
    ON f.file_id = o.observation_event_id
    WHERE o.observation_concept_id = {FILE_OBS_CONCEPT} AND f.file_id IS NULL"""))
check("every file-membership record points at a real file", img_orph == 0, f"{img_orph} orphans")

# ---- 4. procedures & conditions --------------------------------------------
print("\n4. Procedures and conditions — present, not placeholders?")
for tbl, ccol in (("procedure_occurrence", "procedure_concept_id"),
                  ("condition_occurrence", "condition_concept_id")):
    n = int(one(f"SELECT COUNT(*) FROM cdm.{tbl}"))
    z = int(one(f"SELECT COUNT(*) FROM cdm.{tbl} WHERE {ccol}=0"))
    check(f"cdm.{tbl} populated", n > 0, f"{n} rows")
    check(f"cdm.{tbl} concept-0 rate", z == 0,
          f"{z}/{n} at concept 0" + ("" if z == 0 else " — declared draft stubs awaiting curation"),
          warn=(z > 0))

# ---- 5. lineage graph -------------------------------------------------------
print("\n5. Does the lineage graph hold up?")
nonstd = int(one(f"""SELECT COUNT(*) FROM cdm.fact_relationship
    WHERE relationship_concept_id NOT IN {STANDARD_REL_PAIRS}"""))
check("fact_relationship uses ONLY Standard relationship concepts", nonstd == 0, f"{nonstd} non-standard rows")
fr_orph = int(one("""SELECT COUNT(*) FROM cdm.fact_relationship fr
    WHERE (fr.domain_concept_id_1=21 AND NOT EXISTS (SELECT 1 FROM cdm.measurement m WHERE m.measurement_id=fr.fact_id_1))
       OR (fr.domain_concept_id_1=36 AND NOT EXISTS (SELECT 1 FROM cdm.specimen s WHERE s.specimen_id=fr.fact_id_1))
       OR (fr.domain_concept_id_2=21 AND NOT EXISTS (SELECT 1 FROM cdm.measurement m WHERE m.measurement_id=fr.fact_id_2))
       OR (fr.domain_concept_id_2=36 AND NOT EXISTS (SELECT 1 FROM cdm.specimen s WHERE s.specimen_id=fr.fact_id_2))"""))
check("every fact_relationship endpoint resolves", fr_orph == 0, f"{fr_orph} dangling endpoints")
f, r = (int(x) for x in q("""SELECT
    COUNT(*) FILTER (WHERE relationship_concept_id=32668),
    COUNT(*) FILTER (WHERE relationship_concept_id=32669) FROM cdm.fact_relationship""")[0])
check("Measurement↔Specimen reciprocals complete", f == r and f > 0, f"{f} forward / {r} reverse")
lin_orph = int(one(f"""SELECT COUNT(*) FROM cdm.measurement m
    WHERE m.measurement_concept_id={LINEAGE_MEAS_CONCEPT}
      AND NOT EXISTS (SELECT 1 FROM cdm.specimen s WHERE s.specimen_id=m.measurement_event_id)"""))
check("every lineage record's child specimen exists", lin_orph == 0, f"{lin_orph} orphans")

# ---- 6. specimen & dates ----------------------------------------------------
print("\n6. Specimens and dates")
z = int(one("SELECT COUNT(*) FROM cdm.specimen WHERE specimen_concept_id=0"))
check("no specimen at concept 0", z == 0, f"{z} rows")
nullsv = int(one("SELECT COUNT(*) FROM cdm.specimen WHERE specimen_source_value IS NULL OR specimen_source_value=''"))
check("every specimen carries its source value", nullsv == 0, f"{nullsv} blank")
early = int(one(f"""SELECT (SELECT COUNT(*) FROM cdm.visit_occurrence WHERE visit_start_date < '{DATE_FLOOR}')
    + (SELECT COUNT(*) FROM cdm.specimen WHERE specimen_date < '{DATE_FLOOR}')
    + (SELECT COUNT(*) FROM cdm.observation WHERE observation_date < '{DATE_FLOOR}')
    + (SELECT COUNT(*) FROM cdm.measurement WHERE measurement_date < '{DATE_FLOOR}')"""))
check(f"no event predates the {DATE_FLOOR} screen floor", early == 0, f"{early} rows")

# ---- 7. nothing silently empty ---------------------------------------------
print("\n7. Is anything silently empty?")
for tbl in ("person", "visit_occurrence", "observation", "measurement", "specimen", "files",
            "assay", "assay_to_specimen", "assay_input_file", "procedure_occurrence",
            "condition_occurrence", "observation_period", "fact_relationship", "concept"):
    n = int(one(f"SELECT COUNT(*) FROM cdm.{tbl}"))
    check(f"cdm.{tbl}", n > 0, f"{n} rows")

print(f"\n== {results['PASS']} pass · {results['WARN']} warn · {results['FAIL']} fail ==")
if results["FAIL"]:
    print("BLIND REVIEW FAILED — fix before pushing.")
    sys.exit(1)
print("BLIND REVIEW CLEAN — warnings above are review prompts, not blockers.")
