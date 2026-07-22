#!/usr/bin/env python3
"""
Acceptance test: the SysBio-CDM cohort-builder USER STORIES.

Runs the 13 user-story queries -- rewritten for the CURRENT M:N model (harmonized files link to
assays via `assay_input_file`, not `files.assay_id`; `10x Multiome` is `assay.assay_source_value`,
not `platform`) -- against the loaded CDM and asserts each returns data. This is the
"do we meet the MVP threshold?" gate; run it after cdm_load/build_selfcontained.sh.

    python scripts/14_verify_user_stories.py [db=sysbio_cdm_selfcontained]

Exit code 0 iff every story meets its minimum. Connection from PGHOST/PGPORT/PGUSER/PGPASSWORD
(defaults localhost/5433/postgres) -- same convention as 13_verify_governance.py.

NOTE: S3/S4/S5 (per-cell-type "pseudobulk" HDF5) are EXPECTED to fail until the cohort_files()
granularity fix lands -- that is the point of a red test driving the fix.
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

# Disease dx concepts: AD 378419, PD 381270, RA 80809, SLE 257628, T2D 201826.
DX = "378419,381270,80809,257628,201826"

# (id, one-line story, min_rows, sql-returning-a-single-count)
STORIES = [
  ("S1", "diseases / specimens / data types in the harmonized data", 1, f"""
    SELECT count(*) FROM (SELECT DISTINCT dx.concept_name, sc.concept_name, f.analysis_type
      FROM cdm.files f
      JOIN cdm.assay_input_file aif ON aif.file_id=f.file_id
      JOIN cdm.assay a ON a.assay_id=aif.assay_id
      JOIN cdm.assay_to_specimen ats ON ats.assay_id=a.assay_id
      JOIN cdm.specimen s ON s.specimen_id=ats.specimen_id
      JOIN cdm.concept sc ON sc.concept_id=s.specimen_concept_id
      JOIN cdm.observation co ON co.person_id=s.person_id AND co.observation_concept_id IN ({DX})
      JOIN cdm.concept dx ON dx.concept_id=co.observation_concept_id
      WHERE f.file_role='harmonized_output') q"""),

  ("S2", "how to obtain access + data-use requirements", 1,
    "SELECT count(*) FROM cdm.access_groups"),

  ("S3", "pseudobulk HDF5 from AD or PD, postmortem brain", 1, f"""
    SELECT count(DISTINCT f.file_id) FROM cdm.files f
      JOIN cdm.assay_input_file aif ON aif.file_id=f.file_id
      JOIN cdm.assay a ON a.assay_id=aif.assay_id
      JOIN cdm.assay_to_specimen ats ON ats.assay_id=a.assay_id
      JOIN cdm.specimen s ON s.specimen_id=ats.specimen_id
      JOIN cdm.observation co ON co.person_id=s.person_id AND co.observation_concept_id IN (378419,381270)
      WHERE f.file_role='harmonized_output' AND f.file_format='HDF5'
        AND coalesce(f.cell_type,'')<>'' AND f.biosample_type='postmortem brain'"""),

  ("S4", "all pseudobulk HDF5 (per cell type)", 1,
    "SELECT count(*) FROM cdm.files WHERE file_role='harmonized_output' AND file_format='HDF5' AND coalesce(cell_type,'')<>''"),

  ("S5", "pseudobulked microglia HDF5", 1,
    "SELECT count(*) FROM cdm.files WHERE file_role='harmonized_output' AND file_format='HDF5' AND cell_type='microglia'"),

  ("S6", "pseudobulk HDF5 from multi-timepoint datasets", 1, """
    SELECT count(DISTINCT f.file_id) FROM cdm.files f
      JOIN cdm.assay_input_file aif ON aif.file_id=f.file_id
      JOIN cdm.assay a ON a.assay_id=aif.assay_id
      JOIN cdm.assay_to_specimen ats ON ats.assay_id=a.assay_id
      JOIN cdm.specimen s ON s.specimen_id=ats.specimen_id
      WHERE f.file_role='harmonized_output'
        AND s.person_id IN (SELECT person_id FROM cdm.visit_occurrence GROUP BY person_id HAVING count(*)>1)"""),

  ("S7", "catalog of all CDEs represented in the CDM", 50, """
    SELECT count(*) FROM (SELECT observation_source_value v FROM cdm.observation
                          UNION SELECT measurement_source_value FROM cdm.measurement) q
    WHERE v IS NOT NULL"""),

  ("S8", "source files -> harmonization -> outputs (replication chains)", 1, """
    SELECT count(*) FROM (
      SELECT srcf.file_id, outf.file_id FROM cdm.assay a
      JOIN cdm.files srcf ON srcf.assay_id=a.assay_id AND srcf.file_role='source_input'
      JOIN cdm.assay_input_file aif ON aif.assay_id=a.assay_id
      JOIN cdm.files outf ON outf.file_id=aif.file_id AND outf.file_role='harmonized_output') q"""),

  ("S9", "source files + type + size (compute-cost estimate)", 1,
    "SELECT count(*) FROM (SELECT file_format FROM cdm.files WHERE file_role='source_input' GROUP BY file_format) q"),

  ("S10", "individuals with scRNA + another modality (multi-omic)", 1, """
    SELECT count(*) FROM (
      SELECT s.person_id FROM cdm.specimen s
      JOIN cdm.assay_to_specimen ats ON ats.specimen_id=s.specimen_id
      JOIN cdm.assay_input_file aif ON aif.assay_id=ats.assay_id
      JOIN cdm.files f ON f.file_id=aif.file_id AND f.file_role='harmonized_output'
      GROUP BY s.person_id HAVING count(DISTINCT f.analysis_type) > 1) q"""),

  ("S11", "the multi-omic subset with their modalities", 1, """
    SELECT count(*) FROM (
      SELECT s.person_id FROM cdm.specimen s
      JOIN cdm.assay_to_specimen ats ON ats.specimen_id=s.specimen_id
      JOIN cdm.assay_input_file aif ON aif.assay_id=ats.assay_id
      JOIN cdm.files f ON f.file_id=aif.file_id AND f.file_role='harmonized_output'
      GROUP BY s.person_id
      HAVING bool_or(f.analysis_type='RNA') AND bool_or(f.analysis_type='ATAC')) q"""),

  ("S12", "scRNA datasets on 10x Multiome", 1,
    "SELECT count(*) FROM cdm.assay WHERE assay_source_value='10x Multiome'"),

  ("S13", "individuals with scRNA + ATAC from the same specimen", 1, """
    SELECT count(*) FROM (
      SELECT s.specimen_id FROM cdm.specimen s
      JOIN cdm.assay_to_specimen ats ON ats.specimen_id=s.specimen_id
      JOIN cdm.assay_input_file aif ON aif.assay_id=ats.assay_id
      JOIN cdm.files f ON f.file_id=aif.file_id AND f.file_role='harmonized_output'
      GROUP BY s.specimen_id
      HAVING bool_or(f.analysis_type='RNA') AND bool_or(f.analysis_type='ATAC')) q"""),

  ("S14", "cohort across silos (study x disease x specimen x assay)", 1, """
    SELECT count(*) FROM (
      SELECT DISTINCT s.person_id FROM cdm.files f
      JOIN cdm.assay_input_file aif ON aif.file_id=f.file_id
      JOIN cdm.assay a ON a.assay_id=aif.assay_id
      JOIN cdm.assay_to_specimen ats ON ats.assay_id=a.assay_id
      JOIN cdm.specimen s ON s.specimen_id=ats.specimen_id
      JOIN cdm.observation co ON co.person_id=s.person_id AND co.observation_concept_id IN (378419,381270)
      WHERE f.file_role='harmonized_output' AND a.assay_source_value='10x Multiome' AND f.analysis_type='RNA') q"""),
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
        print(f"  {sid:4} {'PASS' if ok else 'FAIL'}  rows={n:<6} (need >= {need})  {desc}")
        if not ok:
            fails += 1
    print(f"== {len(STORIES)-fails}/{len(STORIES)} stories pass ==")
    return 1 if fails else 0

if __name__ == "__main__":
    sys.exit(main())
