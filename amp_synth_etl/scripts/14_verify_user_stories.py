#!/usr/bin/env python3
"""
Acceptance test: the SysBio-CDM cohort-builder USER STORIES.

Runs the 13 user-story queries (S1-S13) plus a cross-silo cohort check (S14) against the loaded
CDM, using the CURRENT model, and asserts each returns MEANINGFUL data -- not merely >= 1 row.

Model this test enforces (a query that ignores it is a bug, not a pass):
  * Disease / cohort status is the uniform record `observation_concept_id = 4234469`; the disease is
    in `value_as_concept_id`, controls carry `qualifier_concept_id = 44804027`. Filtering disease as
    `observation_concept_id IN (...)` finds only the legacy AD record and returns Alzheimer's-only --
    that regression is exactly what S1's `>= 5 distinct diseases` threshold now catches.
  * Harmonized/aggregate outputs link to assays via `assay_input_file` (M:N); source files via the
    scalar `files.assay_id`. `10x Multiome` is `assay.assay_source_value`, not `platform`.

Thresholds are minimum-meaningful, not 1: S1 must span >=5 diseases (AD-only = 1 -> FAIL); S4 must
cover >=3 harmonized programmes; S13 must resolve to BOTH a case and a control. Documented, runnable
long-form versions of every query are in resources/query_cookbook.md.

    python scripts/14_verify_user_stories.py [db=sysbio_cdm_selfcontained]

Exit code 0 iff every story meets its minimum. Connection from PGHOST/PGPORT/PGUSER/PGPASSWORD
(defaults localhost/5433/postgres) -- same convention as 13_verify_governance.py.
"""
import os, sys, subprocess

DB = sys.argv[1] if len(sys.argv) > 1 else "sysbio_cdm_selfcontained"

def scalar(sql):
    env = dict(os.environ)   # PGPASSWORD from the environment / ~/.pgpass
    out = subprocess.run(["psql", "-h", os.environ.get("PGHOST", "localhost"),
                          "-p", os.environ.get("PGPORT", "5433"),
                          "-U", os.environ.get("PGUSER", "postgres"), "-d", DB,
                          "-tAqc", sql], capture_output=True, text=True, env=env)
    if out.returncode != 0:
        raise RuntimeError(f"psql failed: {out.stderr.strip()}\n  SQL: {sql}")
    return int((out.stdout.strip() or "0"))

# The uniform status record and the non-disease values that live under it (Normal / Other /
# Not applicable / Unknown). Disease queries MUST exclude these or they count status as disease.
DX = 4234469                                              # observation_concept_id "Diagnosis"
STATUS_NOISE = "45884153,45878142,45882470,45877986"     # Normal, Other, Not applicable, Unknown
AD_OR_PD = "36311271,381270"                              # Alzheimer's disease, Parkinson's disease

# Reusable join: harmonized file -> assay -> specimen -> person -> status record.
HARM_TO_DX = f"""
  cdm.files f
  JOIN cdm.assay_input_file aif ON aif.file_id = f.file_id
  JOIN cdm.assay a              ON a.assay_id   = aif.assay_id
  JOIN cdm.assay_to_specimen ats ON ats.assay_id = a.assay_id
  JOIN cdm.specimen s          ON s.specimen_id = ats.specimen_id
  JOIN cdm.observation co      ON co.person_id  = s.person_id AND co.observation_concept_id = {DX}"""

# (id, one-line story, min, sql-returning-a-single-count)
STORIES = [
  ("S1", "harmonized data spans MULTIPLE diseases (AD-only = FAIL)", 5, f"""
    SELECT count(DISTINCT co.value_as_concept_id)
    FROM {HARM_TO_DX}
    WHERE f.file_role='harmonized_output'
      AND co.value_as_concept_id IS NOT NULL AND co.value_as_concept_id NOT IN ({STATUS_NOISE})"""),

  ("S2", "access groups + data-use requirements published", 4,
    "SELECT count(*) FROM cdm.access_groups"),

  ("S3", "pseudobulk HDF5 from AD or PD, postmortem brain", 5, f"""
    SELECT count(DISTINCT f.file_id)
    FROM {HARM_TO_DX}
    WHERE f.file_role='harmonized_output' AND f.file_format='HDF5'
      AND f.biosample_type ILIKE '%brain%' AND co.value_as_concept_id IN ({AD_OR_PD})"""),

  ("S4", "pseudobulk HDF5 across MULTIPLE programmes, per cell type", 3, """
    SELECT count(DISTINCT study) FROM cdm.files
    WHERE file_role='harmonized_output' AND file_format='HDF5' AND coalesce(cell_type,'')<>''"""),

  ("S5", "pseudobulked microglia HDF5", 1,
    "SELECT count(*) FROM cdm.files WHERE file_role='harmonized_output' AND file_format='HDF5' AND cell_type='microglia'"),

  ("S6", "harmonized HDF5 from multi-timepoint participants", 5, """
    SELECT count(DISTINCT f.file_id) FROM cdm.files f
    JOIN cdm.assay_input_file aif ON aif.file_id=f.file_id
    JOIN cdm.assay a ON a.assay_id=aif.assay_id
    JOIN cdm.assay_to_specimen ats ON ats.assay_id=a.assay_id
    JOIN cdm.specimen s ON s.specimen_id=ats.specimen_id
    WHERE f.file_role='harmonized_output'
      AND s.person_id IN (SELECT person_id FROM cdm.visit_occurrence GROUP BY 1 HAVING count(*)>1)"""),

  ("S7", "catalog of CDEs represented in the CDM", 100, """
    SELECT count(*) FROM (SELECT observation_source_value v FROM cdm.observation
                          UNION SELECT measurement_source_value FROM cdm.measurement) q WHERE v IS NOT NULL"""),

  ("S8", "source -> harmonization -> output replication chains", 100, """
    SELECT count(*) FROM (SELECT srcf.file_id, outf.file_id FROM cdm.assay a
      JOIN cdm.files srcf ON srcf.assay_id=a.assay_id AND srcf.file_role='source_input'
      JOIN cdm.assay_input_file aif ON aif.assay_id=a.assay_id
      JOIN cdm.files outf ON outf.file_id=aif.file_id) q"""),

  ("S9", "source file formats carry a size (compute-cost estimate)", 2, """
    SELECT count(DISTINCT file_format) FROM cdm.files
    WHERE file_role='source_input' AND file_size_bytes IS NOT NULL AND file_size_bytes > 0"""),

  ("S10", "individuals with scRNA + another modality (multi-omic)", 10, """
    SELECT count(*) FROM (SELECT s.person_id FROM cdm.specimen s
      JOIN cdm.assay_to_specimen ats ON ats.specimen_id=s.specimen_id
      JOIN cdm.assay_input_file aif ON aif.assay_id=ats.assay_id
      JOIN cdm.files f ON f.file_id=aif.file_id AND f.file_role='harmonized_output'
      GROUP BY 1 HAVING count(DISTINCT f.analysis_type)>1) q"""),

  ("S11", "multi-omic subset carrying BOTH RNA and ATAC", 10, """
    SELECT count(*) FROM (SELECT s.person_id FROM cdm.specimen s
      JOIN cdm.assay_to_specimen ats ON ats.specimen_id=s.specimen_id
      JOIN cdm.assay_input_file aif ON aif.assay_id=ats.assay_id
      JOIN cdm.files f ON f.file_id=aif.file_id AND f.file_role='harmonized_output'
      GROUP BY 1 HAVING bool_or(f.analysis_type='RNA') AND bool_or(f.analysis_type='ATAC')) q"""),

  ("S12", "scRNA datasets on 10x Multiome", 10,
    "SELECT count(*) FROM cdm.assay WHERE assay_source_value='10x Multiome'"),

  ("S13", "scRNA+ATAC same specimen resolves to BOTH case AND control", 2, f"""
    WITH multi AS (SELECT s.person_id, s.specimen_id FROM cdm.specimen s
      JOIN cdm.assay_to_specimen ats ON ats.specimen_id=s.specimen_id
      JOIN cdm.assay_input_file aif ON aif.assay_id=ats.assay_id
      JOIN cdm.files f ON f.file_id=aif.file_id AND f.file_role='harmonized_output'
      GROUP BY 1,2 HAVING bool_or(f.analysis_type='RNA') AND bool_or(f.analysis_type='ATAC'))
    SELECT count(DISTINCT CASE WHEN o.qualifier_concept_id=44804027 THEN 'control' ELSE 'case' END)
    FROM multi m JOIN cdm.observation o ON o.person_id=m.person_id AND o.observation_concept_id={DX}"""),

  ("S14", "cross-silo cohort: disease x harmonized-file x specimen x assay", 5, f"""
    SELECT count(DISTINCT s.person_id)
    FROM {HARM_TO_DX}
    WHERE f.file_role='harmonized_output'
      AND co.value_as_concept_id IS NOT NULL AND co.value_as_concept_id NOT IN ({STATUS_NOISE})"""),
]

def main():
    print(f"== USER-STORY ACCEPTANCE TEST  (db={DB}) ==")
    fails = 0
    for sid, desc, need, sql in STORIES:
        try:
            n = scalar(sql)
        except Exception as e:
            print(f"  {sid:4} ERROR  {desc}\n         {e}")
            fails += 1
            continue
        ok = n >= need
        print(f"  {sid:4} {'PASS' if ok else 'FAIL'}  value={n:<6} (need >= {need})  {desc}")
        if not ok:
            fails += 1
    print(f"== {len(STORIES)-fails}/{len(STORIES)} stories pass ==")
    return 1 if fails else 0

if __name__ == "__main__":
    sys.exit(main())
