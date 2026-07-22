# SysBio-CDM cohort-builder query cookbook

Runnable queries for the 14 user stories against the **current** `amp_synth_etl` CDM
(schema `cdm`). Rewritten for the M:N linkage model — the old cookbook's joins were
written for a superseded schema and silently returned 0. The counts each query returns
are gated in `scripts/14_verify_user_stories.py` (run `make verify-stories`).

## Model facts the queries rely on
- **Harmonized-output files have `assay_id = NULL`**; they link to their producing assays via
  **`cdm.assay_input_file`** (M:N). To reach a person from a harmonized file, traverse:
  `files → assay_input_file → assay → assay_to_specimen → specimen → person`.
- **Harmonized single-cell RNA/ATAC are pseudobulk HDF5, one file PER cell type** (`files.cell_type`),
  multi-specimen. Proteomics is plate-level (`assay_matrix`); raw sequencing is per-sample (`source_input`).
- **`10x Multiome` is `assay.assay_source_value`** (the technology), NOT `assay.platform` (the sequencer).
- **Disease is an `observation`** (AD `378419`; PD `381270`; RA `80809`; SLE `257628`; T2D `201826`).
  Sex is observation `3046965` (value_as_concept 8532 F / 8507 M).
- **Access / data-use** live in `cdm.access_groups`; **specimen lineage** in `cdm.fact_relationship`
  (`32554` "Sub-specimen of", `32553` "Includes sub-specimen"; Specimen domain `36`).

---

### S1 — PI: what diseases / specimens / data types are in the harmonized data?
```sql
SELECT DISTINCT dx.concept_name AS disease, sc.concept_name AS specimen_type, f.analysis_type AS data_type
FROM cdm.files f
 JOIN cdm.assay_input_file aif ON aif.file_id = f.file_id
 JOIN cdm.assay a              ON a.assay_id = aif.assay_id
 JOIN cdm.assay_to_specimen ats ON ats.assay_id = a.assay_id
 JOIN cdm.specimen s           ON s.specimen_id = ats.specimen_id
 JOIN cdm.concept sc           ON sc.concept_id = s.specimen_concept_id
 JOIN cdm.observation co       ON co.person_id = s.person_id
                              AND co.observation_concept_id IN (378419,381270,80809,257628,201826)
 JOIN cdm.concept dx           ON dx.concept_id = co.observation_concept_id
WHERE f.file_role = 'harmonized_output';
```

### S2 — PI: how to obtain access + data-use requirements
```sql
SELECT code, name, disease_focus, dul, data_access_instructions FROM cdm.access_groups ORDER BY code;
```

### S3 — biologist: pseudobulk HDF5 from AD or PD, postmortem brain
```sql
SELECT DISTINCT f.file_id, f.file_name, f.cell_type
FROM cdm.files f
 JOIN cdm.assay_input_file aif ON aif.file_id = f.file_id
 JOIN cdm.assay a              ON a.assay_id = aif.assay_id
 JOIN cdm.assay_to_specimen ats ON ats.assay_id = a.assay_id
 JOIN cdm.specimen s           ON s.specimen_id = ats.specimen_id
 JOIN cdm.observation co       ON co.person_id = s.person_id AND co.observation_concept_id IN (378419,381270)
WHERE f.file_role='harmonized_output' AND f.file_format='HDF5'
  AND f.cell_type <> '' AND f.biosample_type='postmortem brain';
```

### S4 — biologist: all pseudobulk HDF5 (per cell type)
```sql
SELECT file_id, file_name, study, cell_type, analysis_type
FROM cdm.files WHERE file_role='harmonized_output' AND file_format='HDF5' AND cell_type <> '';
```

### S5 — biologist: pseudobulked microglia HDF5
```sql
SELECT file_id, file_name, study FROM cdm.files
WHERE file_role='harmonized_output' AND file_format='HDF5' AND cell_type='microglia';
```

### S6 — biologist: pseudobulk HDF5 from multi-timepoint datasets
```sql
SELECT DISTINCT f.file_id, f.file_name
FROM cdm.files f
 JOIN cdm.assay_input_file aif ON aif.file_id = f.file_id
 JOIN cdm.assay a              ON a.assay_id = aif.assay_id
 JOIN cdm.assay_to_specimen ats ON ats.assay_id = a.assay_id
 JOIN cdm.specimen s           ON s.specimen_id = ats.specimen_id
WHERE f.file_role='harmonized_output'
  AND s.person_id IN (SELECT person_id FROM cdm.visit_occurrence GROUP BY person_id HAVING count(*) > 1);
```

### S7 — bioinformatician: catalog of all CDEs
The CDE dictionary ships in-repo (`inputs/cde_dictionary.tsv`/`.jsonl`). CDEs represented in a built CDM:
```sql
SELECT DISTINCT v FROM (SELECT observation_source_value v FROM cdm.observation
                        UNION SELECT measurement_source_value FROM cdm.measurement) q WHERE v IS NOT NULL;
```

### S8 — bioinformatician: source files → harmonization → outputs (replication chains)
```sql
SELECT srcf.file_name AS source_file, a.assay_source_value AS assay, outf.file_name AS output_file
FROM cdm.assay a
 JOIN cdm.files srcf           ON srcf.assay_id = a.assay_id AND srcf.file_role='source_input'
 JOIN cdm.assay_input_file aif ON aif.assay_id = a.assay_id
 JOIN cdm.files outf           ON outf.file_id = aif.file_id AND outf.file_role='harmonized_output';
```

### S9 — bioinformatician: source files + type + size (compute-cost estimate)
```sql
SELECT file_format, count(*) AS n, pg_size_pretty(sum(file_size_bytes)) AS total_size
FROM cdm.files WHERE file_role='source_input' GROUP BY file_format;
```

### S10 — bioinformatician: individuals with scRNA + another modality (multi-omic)
```sql
SELECT s.person_id, count(DISTINCT f.analysis_type) AS modalities
FROM cdm.specimen s
 JOIN cdm.assay_to_specimen ats ON ats.specimen_id = s.specimen_id
 JOIN cdm.assay_input_file aif  ON aif.assay_id = ats.assay_id
 JOIN cdm.files f               ON f.file_id = aif.file_id AND f.file_role='harmonized_output'
GROUP BY s.person_id HAVING count(DISTINCT f.analysis_type) > 1;
```

### S11 — biologist: the multi-omic subset with their modalities
```sql
SELECT s.person_id, string_agg(DISTINCT f.analysis_type, ' + ' ORDER BY f.analysis_type) AS modalities
FROM cdm.specimen s
 JOIN cdm.assay_to_specimen ats ON ats.specimen_id = s.specimen_id
 JOIN cdm.assay_input_file aif  ON aif.assay_id = ats.assay_id
 JOIN cdm.files f               ON f.file_id = aif.file_id AND f.file_role='harmonized_output'
GROUP BY s.person_id
HAVING bool_or(f.analysis_type='RNA') AND bool_or(f.analysis_type='ATAC');
```

### S12 — bioinformatician: scRNA datasets on 10x Multiome (+ the ATAC on the same specimens)
```sql
SELECT a.assay_source_value, s.specimen_source_id, f.file_name AS atac_file
FROM cdm.assay a
 JOIN cdm.assay_to_specimen ats ON ats.assay_id = a.assay_id
 JOIN cdm.specimen s            ON s.specimen_id = ats.specimen_id
 JOIN cdm.assay_input_file aif  ON aif.assay_id = a.assay_id
 JOIN cdm.files f               ON f.file_id = aif.file_id AND f.file_role='harmonized_output' AND f.analysis_type='ATAC'
WHERE a.assay_source_value = '10x Multiome';
```

### S13 — biologist: individuals with scRNA + ATAC from the same specimen
```sql
SELECT s.specimen_id, s.person_id
FROM cdm.specimen s
 JOIN cdm.assay_to_specimen ats ON ats.specimen_id = s.specimen_id
 JOIN cdm.assay_input_file aif  ON aif.assay_id = ats.assay_id
 JOIN cdm.files f               ON f.file_id = aif.file_id AND f.file_role='harmonized_output'
GROUP BY s.specimen_id, s.person_id
HAVING bool_or(f.analysis_type='RNA') AND bool_or(f.analysis_type='ATAC');
```

### S14 — cohort builder: aggregate across silos (study × disease × specimen × assay)
```sql
SELECT DISTINCT s.person_id, f.study, a.assay_source_value AS assay, f.analysis_type AS data
FROM cdm.files f
 JOIN cdm.assay_input_file aif ON aif.file_id = f.file_id
 JOIN cdm.assay a              ON a.assay_id = aif.assay_id
 JOIN cdm.assay_to_specimen ats ON ats.assay_id = a.assay_id
 JOIN cdm.specimen s           ON s.specimen_id = ats.specimen_id
 JOIN cdm.observation co       ON co.person_id = s.person_id AND co.observation_concept_id IN (378419,381270)
WHERE f.file_role='harmonized_output' AND a.assay_source_value='10x Multiome' AND f.analysis_type='RNA';
```

### Bonus — specimen derivation lineage (`cdm.fact_relationship`)
```sql
WITH RECURSIVE lineage(descendant, ancestor, levels) AS (
  SELECT fact_id_1, fact_id_2, 1 FROM cdm.fact_relationship WHERE relationship_concept_id = 32554  -- 'Sub-specimen of'
  UNION ALL
  SELECT l.descendant, fr.fact_id_2, l.levels + 1
  FROM lineage l JOIN cdm.fact_relationship fr
    ON fr.fact_id_1 = l.ancestor AND fr.relationship_concept_id = 32554)
SELECT * FROM lineage;
```
