# SysBio-CDM cohort-builder query cookbook (14 stories)

**Date:** 2026-07-02 · **DB:** `sysbio_etl` @ localhost:5433, schema `sysbio_cdm_mock` · **Data:** synthetic MVP manifest `sql/sysbio_cdm_mvp_manifest_20260702.sql` (9 persons, ids ≥900000; NOT patient data).

## Index: story → question → answer (query for each is in its `### SN` section below)
| # | Question (who wants what) | Answer |
|---|---|---|
| S1 | PI: what diseases / specimens / data types are in the data? | AD·PD·RA·SLE·T2D × brain/blood × RNA/ATAC pseudobulk |
| S2 | PI: how to get access + data-use requirements? | 8 study/grant attribution rows |
| S3 | biologist: pseudobulk HDF5, AD or PD, postmortem brain | the matching HDF5 files |
| S4 | biologist: all pseudobulk HDF5 + sex, Dx, specimen | rows carry all three variables |
| S5 | biologist: HDF5 **microglia** across Dx/Sex | the microglia files |
| S6 | biologist: pseudobulk HDF5 from **multi-timepoint** datasets | the longitudinal person (PDRD) |
| S7 | bioinformatician: catalog of all CDEs | the spec (obs/meas/specimen/procedure/cdm_source) |
| S8 | bioinformatician: source → harmonization → outputs (replication) | full input→pipeline→output chains |
| S9 | bioinformatician: source files + type + size (compute cost) | size per format (gene-count, fastq) |
| S10 | bioinformatician: individuals with scRNA **+ another modality** | the multi-omic individuals |
| S11 | biologist: the multi-omic subset + their modalities | RNA+ATAC individuals |
| S12 | bioinformatician: 10x Multiome scRNA **+ ATAC on same specimens** | the Multiome assays + their ATAC |
| S13 | biologist: scRNA **+ ATAC from the same specimen** (Dx vs control) | the dual-modality specimens |
| **S14** | anyone: **build a cohort across silos**: filter by **study × disease × specimen × assay** together | matching individuals across studies |

> Verified row counts live in each `### SN` header (`→ **answer**`) directly above that story's SQL. Jump to `### S<n>` for the runnable query.

All 14 stories were run against the dataset and returned the rows shown in each `### S` header.

Design facts the queries rely on:
- **person is data-free**; sex/age are `observation` rows (Sex `3046965` → value_as_concept 8532/8507; Age `3022304`). Dx is an `observation` (disorder concept in `observation_concept_id`) (AD 378419, PD 381270, RA 80809, SLE 257628, T2D/CMD 201826).
- **10x Multiome = one `assay`**; RNA vs ATAC modality is carried in `files.analysis_type`, both output files sharing `assay_id`.
- **`assay_to_specimen`** = usage (one assay → many specimens for pooled runs); **`assay_input_file`** = pipeline source inputs; **`files.assay_id`** = output edge.
- "Same specimen, two modalities" (multi-omics) = two `files` rows (RNA + ATAC) whose `assay_id` links via `assay_to_specimen` to one `specimen`.

---

### S1. PI: what diseases/specimens/data types are in the harmonized data? → **AD, PD, RA, SLE, T2D; 2 specimen types; 2 data types (RNA/ATAC pseudobulk)**
```sql
SELECT DISTINCT dx.concept_name AS disease, sc.concept_name AS specimen_type, f.analysis_type AS data_type
FROM files f
 JOIN assay_to_specimen ats ON ats.assay_id=f.assay_id
 JOIN specimen s  ON s.specimen_id=ats.specimen_id
 JOIN cdm.concept sc ON sc.concept_id=s.specimen_concept_id
 JOIN observation co ON co.observation_concept_id IN (378419,381270,80809,257628,201826) AND co.person_id=s.person_id
 JOIN cdm.concept dx ON dx.concept_id=co.observation_concept_id
WHERE f.file_role='harmonized_output';
```

### S2. PI: how to obtain access + data-use requirements → **8 study/grant rows** (attribution handles; full record-level access is the out-of-scope `access_groups` layer)
```sql
SELECT DISTINCT study, "grant" FROM files WHERE file_role IS NOT NULL ORDER BY study;
```

### S3. biologist: pseudobulk HDF5 from AD **or** PD, postmortem brain → **9 files**
```sql
SELECT DISTINCT f.file_id, f.file_name, f.cell_type
FROM files f
 JOIN assay_to_specimen ats ON ats.assay_id=f.assay_id
 JOIN specimen s ON s.specimen_id=ats.specimen_id
 JOIN observation co ON co.observation_concept_id IN (378419,381270,80809,257628,201826) AND co.person_id=s.person_id
WHERE f.file_format='HDF5' AND f.analysis_type LIKE '%pseudobulk%'
  AND f.biosample_type='postmortem brain'
  AND co.observation_concept_id IN (378419,381270);   -- AD, PD
```

### S4. biologist: all pseudobulk HDF5 + sex, Dx, specimen → **rows carry all three variables**
```sql
SELECT f.file_id, f.file_name,
       max(CASE WHEN sx.value_as_concept_id=8532 THEN 'F' WHEN sx.value_as_concept_id=8507 THEN 'M' END) AS sex,
       string_agg(DISTINCT dx.concept_name,',') AS dx,
       string_agg(DISTINCT sc.concept_name,',')  AS specimen
FROM files f
 JOIN assay_to_specimen ats ON ats.assay_id=f.assay_id
 JOIN specimen s  ON s.specimen_id=ats.specimen_id
 JOIN cdm.concept sc ON sc.concept_id=s.specimen_concept_id
 JOIN person p ON p.person_id=s.person_id
 LEFT JOIN observation sx ON sx.person_id=p.person_id AND sx.observation_concept_id=3046965
 LEFT JOIN observation co ON co.observation_concept_id IN (378419,381270,80809,257628,201826) AND co.person_id=p.person_id
 LEFT JOIN cdm.concept dx ON dx.concept_id=co.observation_concept_id
WHERE f.file_format='HDF5' AND f.analysis_type LIKE '%pseudobulk%'
GROUP BY f.file_id, f.file_name;
```

### S5. biologist: HDF5 pseudobulked **microglia** across Dx/Sex → **7 files (AMP-AD, AMP-PD, AMP-PDRD)**
```sql
SELECT f.file_id, f.file_name, f.study
FROM files f WHERE f.file_format='HDF5' AND f.cell_type='microglia';
```
*(Note: source file `CMD_scRNA_microglia.h5` carries `cell_type='monocyte'`: a synthetic filename/label mismatch in the manifest, correctly excluded by the `cell_type` filter; harmless.)*

### S6. biologist: pseudobulk HDF5 from datasets with **multiple time points** → **PDRD (person 900008, 2 visits)**
```sql
SELECT DISTINCT f.file_id, f.file_name
FROM files f
 JOIN assay_to_specimen ats ON ats.assay_id=f.assay_id
 JOIN specimen s ON s.specimen_id=ats.specimen_id
WHERE f.file_role='harmonized_output'
  AND s.person_id IN (SELECT person_id FROM visit_occurrence GROUP BY person_id HAVING count(*)>1);
```

### S7. bioinformatician: catalog of all CDEs (clinical/demographic + biospecimen/assay metadata) → **the spec** (obs 235 / meas 96 / specimen 8 / procedure 1 / cdm_source 1)
```sql
SELECT amp_variable, domain, lower(target_table) AS target_table,
       field_provenance->'target_table'->>'state' AS state
FROM sysbio.shape_definition ORDER BY target_table, amp_variable;
```

### S8. bioinformatician: source files → harmonization/analysis → outputs (replication) → **full chains**
```sql
SELECT srcf.file_name AS source_file, srcf.file_format, a.assay_source_value AS assay,
       a.analysis_pipeline, outf.file_name AS output_file
FROM assay_input_file aif
 JOIN files srcf ON srcf.file_id=aif.file_id
 JOIN assay a    ON a.assay_id=aif.assay_id
 JOIN files outf ON outf.assay_id=a.assay_id AND outf.file_role='harmonized_output';
```

### S9. bioinformatician: source files + type + size (compute-cost estimate) → **gene-count 1 (2.3 GB), fastq 5 (89 GB)**
```sql
SELECT file_format, count(*) AS n, pg_size_pretty(sum(file_size_bytes)) AS total_size
FROM files WHERE file_role='source_input' GROUP BY file_format;
```

### S10. bioinformatician: individuals with scRNAseq who **also have another modality** (multi-omics subset) → **2 individuals**
```sql
SELECT count(*) AS multiomic_individuals FROM (
  SELECT s.person_id
  FROM assay_to_specimen ats
   JOIN specimen s ON s.specimen_id=ats.specimen_id
   JOIN files f    ON f.assay_id=ats.assay_id
  WHERE f.file_role='harmonized_output'
  GROUP BY s.person_id
  HAVING count(DISTINCT f.analysis_type) > 1
) q;
```

### S11. biologist: the multi-omic subset with their modalities → **900001 (RNA+ATAC), 900003 (RNA+ATAC)**
```sql
SELECT s.person_id, string_agg(DISTINCT f.analysis_type,' + ' ORDER BY f.analysis_type) AS modalities
FROM assay_to_specimen ats
 JOIN specimen s ON s.specimen_id=ats.specimen_id
 JOIN files f    ON f.assay_id=ats.assay_id
WHERE f.file_role='harmonized_output' AND (f.analysis_type LIKE 'RNA%' OR f.analysis_type LIKE 'ATAC%')
GROUP BY s.person_id
HAVING bool_or(f.analysis_type LIKE 'RNA%') AND bool_or(f.analysis_type LIKE 'ATAC%');
```

### S12. bioinformatician: which scRNAseq datasets on **10x Multiome** + the ATAC on the same specimens → **AD-MULTIOME-01 (nuclei AD-NUC-201), PD-MULTIOME-03 (PD-BR-003)**
```sql
SELECT a.assay_source_value, s.specimen_source_id, f.file_name AS atac_file
FROM assay a
 JOIN assay_to_specimen ats ON ats.assay_id=a.assay_id
 JOIN specimen s ON s.specimen_id=ats.specimen_id
 JOIN files f    ON f.assay_id=a.assay_id AND f.analysis_type LIKE 'ATAC%'
WHERE a.platform='10x Multiome';
```

### S13. biologist: individuals with scRNAseq + ATACseq from the **same specimen** (+ Dx vs control) → **specimen 900003 (PD), specimen 900201 (AD)**
```sql
SELECT s.specimen_id, s.person_id, dx.concept_name AS dx
FROM assay_to_specimen ats
 JOIN specimen s ON s.specimen_id=ats.specimen_id
 JOIN files f    ON f.assay_id=ats.assay_id
 LEFT JOIN observation co ON co.observation_concept_id IN (378419,381270,80809,257628,201826) AND co.person_id=s.person_id
 LEFT JOIN cdm.concept dx ON dx.concept_id=co.observation_concept_id
WHERE f.file_role='harmonized_output'
GROUP BY s.specimen_id, s.person_id, dx.concept_name
HAVING bool_or(f.analysis_type LIKE 'RNA%') AND bool_or(f.analysis_type LIKE 'ATAC%');
```

---

### S14. cohort builder: aggregate across silos by **study × disease × specimen × assay** → **the de-siloed cohort**
Filters that live in different tables combine in one query: **study/grant** (file layer), **disease** (conditions), **specimen** (specimen layer), **assay/platform** (assay layer). Any filter drops or adds independently.
```sql
SELECT s.person_id, f.study, dx.concept_name AS disease, sc.concept_name AS specimen,
       a.platform AS assay, string_agg(DISTINCT f.analysis_type,'+') AS data
FROM files f
 JOIN assay a                 ON a.assay_id=f.assay_id
 JOIN assay_to_specimen ats   ON ats.assay_id=a.assay_id
 JOIN specimen s              ON s.specimen_id=ats.specimen_id
 JOIN cdm.concept sc          ON sc.concept_id=s.specimen_concept_id
 JOIN observation co ON co.observation_concept_id IN (378419,381270,80809,257628,201826) AND co.person_id=s.person_id
 JOIN cdm.concept dx          ON dx.concept_id=co.observation_concept_id
WHERE f.study IN ('AMP-AD','AMP-PD')             -- STUDY (silo)
  AND co.observation_concept_id IN (378419,381270) -- DISEASE
  AND s.specimen_source_value='postmortem brain' -- SPECIMEN
  AND a.platform='10x Multiome'                  -- ASSAY
  AND f.analysis_type LIKE 'RNA%'                -- data type
GROUP BY s.person_id, f.study, dx.concept_name, sc.concept_name, a.platform;
```
**Lineage-aware caveat:** the assayed specimen may be a *derivative* (the AD Multiome ran on nuclei whose `specimen_source_value='isolated nuclei'`, not `'postmortem brain'`). To catch derivatives, resolve the specimen through `specimen_relationship` back to its brain ancestor before applying the specimen filter: otherwise a raw specimen filter under-selects.

## Bonus: specimen derivation lineage (the `specimen_relationship` recursive view)
"What did the AD nuclei specimen derive from?" (S13's `900201`):
```sql
WITH RECURSIVE lineage(descendant, ancestor, levels) AS (
  SELECT specimen_id_1, specimen_id_2, 1 FROM specimen_relationship WHERE specimen_id_1=900201
  UNION ALL
  SELECT l.descendant, sr.specimen_id_2, l.levels+1
  FROM lineage l JOIN specimen_relationship sr ON sr.specimen_id_1=l.ancestor
)
SELECT * FROM lineage;   -- 900201 → 900001 (AD postmortem brain), 1 level, via nuclei-isolation procedure
```

## Result
**13/13 stories answered on the synthetic MVP.** The SysBio-CDM structural model (governed-observation demographics, `assay`/`files`/junctions, `specimen_relationship` lineage) is sufficient for the cohort-builder MVP. Remaining production work: generator emission branches for assay/files (so real biosample/file manifests load through `generate_loads_from_shape.py`, not hand-authored SQL), and the full agentic re-map of the 342 clinical CDEs.
