# SysBio-CDM query cookbook — proving the user stories

Runnable SQL for each user story in `sysbio-cdm-user-stories.md`, with the row counts
observed against the built CDM (`sysbio_cdm_selfcontained`). These are the queries that
*prove* the stories are answerable. Counts are from the current synthetic build.

## Model notes (why the joins look the way they do)

- **Disease / cohort status** is one uniform record per participant:
  `observation_concept_id = 4234469` ("Diagnosis"); the disease is in `value_as_concept_id`,
  controls carry `qualifier_concept_id = 44804027` ("Control group") + value `45884153`
  ("Normal"), non-control cases carry `qualifier_concept_id = 1989833` ("Admitting diagnosis").
  **Do not** filter disease as `observation_concept_id IN (…disease ids…)` — that only finds the
  legacy `age_first_ad_dx` record and returns Alzheimer's-only.
- **Harmonized/aggregate outputs link to assays via `assay_input_file` (M:N)**, and carry
  `assay_id = NULL`. Source (raw) files use the scalar `files.assay_id`. Never join a harmonized
  file on `files.assay_id`.
- **Omics programs:** AMP-AD + AMP-RA-SLE + AMP-CMD produce harmonized outputs; AMP-PD produces a
  proteomics `assay_matrix`. `10x Multiome` is `assay.assay_source_value`, not `platform`.

## Data-coverage caveats (the stories were authored from program scope, not the delivered data)

The user stories were written by collaborators describing what the AMP programs *intend* to deliver,
without looking at this synthetic cohort — which carries a subset. Where a proving query returns
"AD-only" or "all-normal", that is a **data-coverage fact, not a query bug**; both are recorded here so
the two are never confused:

- **AD-vs-PD single-cell (S3).** AMP-PD delivers a proteomics `assay_matrix`, not brain single-cell,
  so the "AD or PD, postmortem brain HDF5" comparison resolves to **AD only** (all 11 HDF5 are AD).
- **CMD has NO cohort/disease record — because there is no real CMD disease data.** The CMDGA
  `donor.tsv` / `biosample.tsv` are schema TEMPLATES (field definitions, zero donors), and the kidney
  value set (`cmd_value_set_schema.json`: Diabetic/Hypertensive Kidney Disease, Acute Tubular Injury,
  Acute Interstitial Nephritis) is a list of *allowed values* with no participant-level diagnosis. The
  only real CMD data is a **separate** dataset — the fnih-hypothalamus single-cell atlas (Tadross et
  al., *Nature* 2024; 11 donors, all `disease = normal` / Reference), a normal-brain reference map that
  shares no participants with any kidney cohort. `mappings/adj_primary_dxC.json` (which fabricated
  kidney diagnoses from the value set) is therefore **disabled** — CMD carries no `4234469` record.
- **Harmonized disease richness = AD (1, Alzheimer's) + RA-SLE (7).** The pseudobulk files are
  whole-cohort (each spans AD/control/other, or the full RA-SLE cohort); disease is resolved **per
  participant** via the `4234469` record, so a cohort-builder subsets individuals within a file — the
  file-level disease filter means "this file *contains* disease D", not "disease-D-only".

**RA-SLE source ↔ synthetic alignment.** The synthetic RA-SLE diseases are the ARK `diagnosis` source
values, mapped to concepts under the uniform record: RA, SLE, dermatomyositis, discoid lupus, psoriasis,
scleroderma, vitiligo, Sjögren's, lupus nephritis. Three real ARK diseases remain **string-only** —
*osteoarthritis*, *cutaneous lupus erythematosus*, *psoriatic arthritis* — because `curated_concept`
has no matching concept_id; they need ids to take the disease shape. `At-Risk RA` is a risk status, not
a disease. Disease-control designation (case vs. disease-control) is **deferred**: every non-control
diagnosis carries the same `1989833` ("Admitting diagnosis") qualifier for now.

**Unidentifiable cohort (a valid "unknown").** Three RA-SLE subjects (`100037, 100076, 100222`) carry
`diagnosis = "Not Applicable"` — a legitimate value in the ARK value set, not an error. They have no
cohort membership **by design and are kept as-is**: real ARK data will carry the same, so an
"unknown cohort" is a case downstream must handle rather than something to patch away.

**CMD cohort/disease — none (no real data).** AMP-CMD has no cohort-defining `4234469` record. The
kidney classification (`adj_primary_dxC` → DKD/HKD/AIN) was fabricated from `cmd_value_set_schema.json`
with no participant-level source, and CMD's only real omics is the fnih-hypothalamus normal-reference
atlas — a **separate** dataset (all donors `normal`, no shared participants). Both CMD disease maps are
therefore disabled: `adj_primary_dxC.json` (fabricated kidney dx) and `disease.json` (the fnih `normal`
reference status). Re-enable only when real CMD participant-level diagnosis data exists.

---

### S1 — diseases, specimens, and data types in the harmonized data  → 21 rows
Real diseases only (excludes the Normal/Other/Not-applicable/Unknown status values). CMD carries no
cohort record (`adj_primary_dxC` disabled — no real CMD disease data), so no CMD disease appears;
the list is AD (Alzheimer's) + the RA-SLE diseases.
```sql
SELECT DISTINCT dx.concept_name AS disease, f.study AS program, f.analysis_type
FROM cdm.files f
JOIN cdm.assay_input_file aif ON aif.file_id = f.file_id
JOIN cdm.assay a             ON a.assay_id   = aif.assay_id
JOIN cdm.assay_to_specimen ats ON ats.assay_id = a.assay_id
JOIN cdm.specimen s          ON s.specimen_id = ats.specimen_id
JOIN cdm.observation co      ON co.person_id = s.person_id
                            AND co.observation_concept_id = 4234469
                            AND co.value_as_concept_id NOT IN (45884153, 45878142, 45882470, 45877986)
JOIN cdm.concept dx          ON dx.concept_id = co.value_as_concept_id
WHERE f.file_role = 'harmonized_output'
ORDER BY 2, 1;
```
Returns Alzheimer's (AMP-AD), and Rheumatoid arthritis / SLE / Dermatomyositis / Discoid lupus /
Psoriasis / Scleroderma / Vitiligo (AMP-RA-SLE), across RNA / ATAC / cytometry / spatial.

### S2 — how to obtain access + data-use requirements  → 4
```sql
SELECT access_group_id, name, description FROM cdm.access_groups;
```

### S3 — pseudobulk HDF5 from AD or PD, postmortem brain  → 11
```sql
SELECT count(DISTINCT f.file_id)
FROM cdm.files f
JOIN cdm.assay_input_file aif ON aif.file_id = f.file_id
JOIN cdm.assay a             ON a.assay_id = aif.assay_id
JOIN cdm.assay_to_specimen ats ON ats.assay_id = a.assay_id
JOIN cdm.specimen s          ON s.specimen_id = ats.specimen_id
JOIN cdm.observation co      ON co.person_id = s.person_id
                            AND co.observation_concept_id = 4234469
                            AND co.value_as_concept_id IN (36311271, 381270)   -- AD, PD
WHERE f.file_role = 'harmonized_output' AND f.file_format = 'HDF5'
  AND f.biosample_type ILIKE '%brain%';
```
(All 11 are AD — AMP-PD has proteomics, not brain HDF5.)

### S4 — all pseudobulk HDF5 per cell type, with Dx joinable  → AD 10, CMD 4, RA-SLE 4
```sql
SELECT f.study, count(*) AS hdf5_pseudobulk
FROM cdm.files f
WHERE f.file_role = 'harmonized_output' AND f.file_format = 'HDF5' AND coalesce(f.cell_type,'') <> ''
GROUP BY 1 ORDER BY 1;
-- Dx per file's participants joins through assay_input_file -> assay_to_specimen -> specimen.person_id
-- -> observation(4234469), exactly as in S1.
```

### S5 — pseudobulked microglia HDF5  → 2
```sql
SELECT count(*) FROM cdm.files
WHERE file_role = 'harmonized_output' AND file_format = 'HDF5' AND cell_type = 'microglia';
```

### S6 — harmonized HDF5 from multi-timepoint participants  → 18
```sql
SELECT count(DISTINCT f.file_id)
FROM cdm.files f
JOIN cdm.assay_input_file aif ON aif.file_id = f.file_id
JOIN cdm.assay a             ON a.assay_id = aif.assay_id
JOIN cdm.assay_to_specimen ats ON ats.assay_id = a.assay_id
JOIN cdm.specimen s          ON s.specimen_id = ats.specimen_id
WHERE f.file_role = 'harmonized_output'
  AND s.person_id IN (SELECT person_id FROM cdm.visit_occurrence GROUP BY 1 HAVING count(*) > 1);
```

### S7 — catalog of all CDEs represented in the CDM  → 241
```sql
SELECT count(*) FROM (
  SELECT observation_source_value v FROM cdm.observation
  UNION SELECT measurement_source_value FROM cdm.measurement) q
WHERE v IS NOT NULL;
```

### S8 — source → harmonization → output chains (replication)  → 2246
```sql
SELECT count(*) FROM (
  SELECT srcf.file_id AS source_file, outf.file_id AS output_file
  FROM cdm.assay a
  JOIN cdm.files srcf          ON srcf.assay_id = a.assay_id AND srcf.file_role = 'source_input'
  JOIN cdm.assay_input_file aif ON aif.assay_id = a.assay_id
  JOIN cdm.files outf          ON outf.file_id = aif.file_id) q;
```

### S9 — source files by type + size (compute-cost estimate)  → fastq 490 (≤84 GB), fcs 20 (≤368 MB)
```sql
SELECT file_format, count(*) AS n,
       pg_size_pretty(min(file_size_bytes)::numeric) AS min_size,
       pg_size_pretty(max(file_size_bytes)::numeric) AS max_size
FROM cdm.files WHERE file_role = 'source_input' GROUP BY 1 ORDER BY 2 DESC;
```

### S10 — individuals with scRNA + another modality (multi-omic)  → 64
```sql
SELECT count(*) FROM (
  SELECT s.person_id
  FROM cdm.specimen s
  JOIN cdm.assay_to_specimen ats ON ats.specimen_id = s.specimen_id
  JOIN cdm.assay_input_file aif  ON aif.assay_id = ats.assay_id
  JOIN cdm.files f               ON f.file_id = aif.file_id AND f.file_role = 'harmonized_output'
  GROUP BY 1 HAVING count(DISTINCT f.analysis_type) > 1) q;
```

### S11 — the multi-omic subset carrying BOTH RNA and ATAC  → 48
```sql
SELECT count(*) FROM (
  SELECT s.person_id
  FROM cdm.specimen s
  JOIN cdm.assay_to_specimen ats ON ats.specimen_id = s.specimen_id
  JOIN cdm.assay_input_file aif  ON aif.assay_id = ats.assay_id
  JOIN cdm.files f               ON f.file_id = aif.file_id AND f.file_role = 'harmonized_output'
  GROUP BY 1 HAVING bool_or(f.analysis_type = 'RNA') AND bool_or(f.analysis_type = 'ATAC')) q;
```

### S12 — scRNA datasets generated on 10x Multiome  → 34
```sql
SELECT count(*) FROM cdm.assay WHERE assay_source_value = '10x Multiome';
```

### S13 — scRNA + ATAC from the same specimen, split Dx vs control  → Other 19, AD 11, control 3
```sql
WITH multi AS (
  SELECT s.person_id, s.specimen_id
  FROM cdm.specimen s
  JOIN cdm.assay_to_specimen ats ON ats.specimen_id = s.specimen_id
  JOIN cdm.assay_input_file aif  ON aif.assay_id = ats.assay_id
  JOIN cdm.files f               ON f.file_id = aif.file_id AND f.file_role = 'harmonized_output'
  GROUP BY 1, 2 HAVING bool_or(f.analysis_type = 'RNA') AND bool_or(f.analysis_type = 'ATAC'))
SELECT CASE WHEN o.qualifier_concept_id = 44804027 THEN 'control'
            ELSE coalesce(dx.concept_name, '(case)') END AS dx_or_control,
       count(DISTINCT m.person_id) AS individuals
FROM multi m
LEFT JOIN cdm.observation o ON o.person_id = m.person_id AND o.observation_concept_id = 4234469
LEFT JOIN cdm.concept dx    ON dx.concept_id = o.value_as_concept_id
GROUP BY 1 ORDER BY 2 DESC;
```
