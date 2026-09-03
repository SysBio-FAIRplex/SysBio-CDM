# SysBio-CDM query cookbook — proving the user stories

Runnable SQL for each user story in `sysbio-cdm-user-stories.md`. Each query **returns the actual data that answers the story** — the harmonized files, CDE catalogs, individuals, provenance chains, file sizes, and Dx/sex cross-cut tables a cohort builder would hand back — run against the current ~2,500-participant synthetic build (`sysbio_cdm_selfcontained`). Every story leads with a `base` query and adds variations that slice the same answer by program, cell type, modality, or disease; the sample output shown is the real result set, not a row count.

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
- **CMD carries no `4234469` cohort/disease record — the `adj_primary_dxC`/`disease` maps are disabled.**
  The CMDGA `donor.tsv` / `biosample.tsv` are schema TEMPLATES (field definitions, zero donors), and the
  kidney value set (`cmd_value_set_schema.json`: Diabetic/Hypertensive Kidney Disease, Acute Tubular Injury,
  Acute Interstitial Nephritis) is a list of *allowed values* — so classifying synthetic CMD from that enum
  has no real basis, and `mappings/adj_primary_dxC.json` is **disabled** (CMD carries no `4234469` record).
  **Correction (2026-08-03):** real harmonized CMD clinical DOES exist off-pipeline —
  `dataset_inventories/cmd_harmonization/cmd_clinical_harmonized.csv` (114 donors: 93 kidney WITH real
  `diagnosis`/`egfr`/`bmi` + 21 hypothalamus) — so "no real CMD disease data" is superseded; re-classifying
  CMD from that real clinical is open work. (The 297 MB fnih-hypothalamus per-cell atlas — 11 donors, all
  `disease = normal` — is a separate omics blob, not the clinical source.)
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


### S1 — what diseases, specimens, and data types are in the harmonized data (relevance check)

**base** — What diseases, specimen/tissue types, and data modalities are present in the harmonized output data, per program?
```sql
WITH fd AS (
  SELECT DISTINCT f.file_id, f.study, f.analysis_type, f.biosample_type, f.tissue, f.file_size_bytes,
         COALESCE(dx.concept_name, 'normal reference (no disease record)') AS disease
  FROM cdm.files f
  JOIN cdm.assay_input_file aif ON aif.file_id=f.file_id
  JOIN cdm.assay a ON a.assay_id=aif.assay_id
  JOIN cdm.assay_to_specimen ats ON ats.assay_id=a.assay_id
  JOIN cdm.specimen s ON s.specimen_id=ats.specimen_id
  LEFT JOIN cdm.observation co ON co.person_id=s.person_id AND co.observation_concept_id=4234469
       AND co.value_as_concept_id NOT IN (45884153,45878142,45882470,45877986)
  LEFT JOIN cdm.concept dx ON dx.concept_id=co.value_as_concept_id
  WHERE f.file_role='harmonized_output'
)
SELECT study, disease, analysis_type, biosample_type, tissue,
       count(*) AS n_files, pg_size_pretty(sum(file_size_bytes)) AS total_size
FROM fd
GROUP BY study, disease, analysis_type, biosample_type, tissue
ORDER BY study, disease, analysis_type;
```
Returns — study, disease, analysis_type, biosample_type, tissue, n_files, total_size — one row per (program, disease, modality, specimen type):
```
   study    |               disease                | analysis_type |  biosample_type  |      tissue      | n_files | total_size 
------------+--------------------------------------+---------------+------------------+------------------+---------+------------
 AMP-AD     | Alzheimer's disease                  | ATAC          | postmortem brain | postmortem brain |       5 | 5009 MB
 AMP-AD     | Alzheimer's disease                  | RNA           | postmortem brain | postmortem brain |       6 | 9110 MB
 AMP-AD     | normal reference (no disease record) | ATAC          | postmortem brain | postmortem brain |       5 | 5009 MB
 AMP-AD     | normal reference (no disease record) | RNA           | postmortem brain | postmortem brain |       6 | 9110 MB
 AMP-CMD    | normal reference (no disease record) | RNA           | hypothalamus     | hypothalamus     |       5 | 5747 MB
 AMP-RA-SLE | Dermatomyositis                      | cytometry     | synovial tissue  | synovial tissue  |       1 | 218 MB
 AMP-RA-SLE | Dermatomyositis                      | RNA           | synovial tissue  | synovial tissue  |       5 | 8139 MB
 AMP-RA-SLE | Dermatomyositis                      | spatial       | synovial tissue  | synovial tissue  |       1 | 736 MB
 AMP-RA-SLE | Discoid lupus                        | cytometry     | synovial tissue  | synovial tissue  |       1 | 218 MB
 AMP-RA-SLE | Discoid lupus                        | RNA           | synovial tissue  | synovial tissue  |       5 | 8139 MB
 AMP-RA-SLE | Discoid lupus                        | spatial       | synovial tissue  | synovial tissue  |       1 | 736 MB
 AMP-RA-SLE | normal reference (no disease record) | cytometry     | synovial tissue  | synovial tissue  |       1 | 218 MB
…  (35 rows total)
```

**variation: by cell type** — For each harmonized cell-type file (pseudobulk), which program/specimen is it, what modalities exist, and how many diseases contribute to it?
```sql
WITH fd AS (
  SELECT DISTINCT f.file_id, f.study, f.cell_type, f.analysis_type, f.biosample_type, f.file_size_bytes,
         dx.concept_name AS disease
  FROM cdm.files f
  JOIN cdm.assay_input_file aif ON aif.file_id=f.file_id
  JOIN cdm.assay a ON a.assay_id=aif.assay_id
  JOIN cdm.assay_to_specimen ats ON ats.assay_id=a.assay_id
  JOIN cdm.specimen s ON s.specimen_id=ats.specimen_id
  LEFT JOIN cdm.observation co ON co.person_id=s.person_id AND co.observation_concept_id=4234469
       AND co.value_as_concept_id NOT IN (45884153,45878142,45882470,45877986)
  LEFT JOIN cdm.concept dx ON dx.concept_id=co.value_as_concept_id
  WHERE f.file_role='harmonized_output' AND f.cell_type IS NOT NULL AND f.cell_type<>''
)
SELECT study, cell_type, biosample_type,
       string_agg(DISTINCT analysis_type, ', ' ORDER BY analysis_type) AS modalities,
       count(DISTINCT file_id) AS n_files,
       count(DISTINCT disease) AS n_diseases
FROM fd
GROUP BY study, cell_type, biosample_type
ORDER BY study, cell_type;
```
Returns — study, cell_type, biosample_type, modalities, n_files, n_diseases — one row per pseudobulk cell type (n_diseases=0 means normal-reference-only, e.g. CMD hypothalamus):
```
   study    |       cell_type       |  biosample_type  | modalities | n_files | n_diseases 
------------+-----------------------+------------------+------------+---------+------------
 AMP-AD     | GABAergic neurons     | postmortem brain | ATAC, RNA  |       2 |          1
 AMP-AD     | GLUtamatergic neurons | postmortem brain | ATAC, RNA  |       2 |          1
 AMP-AD     | astrocytes            | postmortem brain | ATAC, RNA  |       2 |          1
 AMP-AD     | microglia             | postmortem brain | ATAC, RNA  |       2 |          1
 AMP-AD     | oligodendrocyte       | postmortem brain | ATAC, RNA  |       2 |          1
 AMP-CMD    | astrocyte             | hypothalamus     | RNA        |       1 |          0
 AMP-CMD    | ependymal cell        | hypothalamus     | RNA        |       1 |          0
 AMP-CMD    | neuron                | hypothalamus     | RNA        |       1 |          0
 AMP-CMD    | oligodendrocyte       | hypothalamus     | RNA        |       1 |          0
 AMP-RA-SLE | B cell                | synovial tissue  | RNA        |       1 |          4
 AMP-RA-SLE | T cell                | synovial tissue  | RNA        |       1 |          4
 AMP-RA-SLE | monocyte              | synovial tissue  | RNA        |       1 |          4
 AMP-RA-SLE | synovial fibroblast   | synovial tissue  | RNA        |       1 |          4
(13 rows)
```

**variation: per-program summary** — Per program, give the one-line relevance card: disease list, modalities, specimen types, file count, and total size of harmonized data.
```sql
WITH fd AS (
  SELECT DISTINCT f.file_id, f.study, f.analysis_type, f.biosample_type, f.cell_type, f.file_size_bytes,
         dx.concept_name AS disease
  FROM cdm.files f
  JOIN cdm.assay_input_file aif ON aif.file_id=f.file_id
  JOIN cdm.assay a ON a.assay_id=aif.assay_id
  JOIN cdm.assay_to_specimen ats ON ats.assay_id=a.assay_id
  JOIN cdm.specimen s ON s.specimen_id=ats.specimen_id
  LEFT JOIN cdm.observation co ON co.person_id=s.person_id AND co.observation_concept_id=4234469
       AND co.value_as_concept_id NOT IN (45884153,45878142,45882470,45877986)
  LEFT JOIN cdm.concept dx ON dx.concept_id=co.value_as_concept_id
  WHERE f.file_role='harmonized_output'
)
SELECT study,
       count(DISTINCT file_id) AS n_files,
       count(DISTINCT disease) AS n_diseases,
       string_agg(DISTINCT disease, '; ' ORDER BY disease) AS diseases,
       string_agg(DISTINCT analysis_type, ', ' ORDER BY analysis_type) AS modalities,
       string_agg(DISTINCT biosample_type, ', ' ORDER BY biosample_type) AS specimen_types,
       pg_size_pretty(sum(DISTINCT file_size_bytes)) AS total_size
FROM fd
GROUP BY study
ORDER BY study;
```
Returns — study, n_files, n_diseases, diseases (semicolon list), modalities, specimen_types, total_size — one relevance card per program:
```
   study    | n_files | n_diseases |                                         diseases                                         |       modalities        |  specimen_types  | total_size 
------------+---------+------------+------------------------------------------------------------------------------------------+-------------------------+------------------+------------
 AMP-AD     |      11 |          1 | Alzheimer's disease                                                                      | ATAC, RNA               | postmortem brain | 14 GB
 AMP-CMD    |       5 |          0 |                                                                                          | RNA                     | hypothalamus     | 5747 MB
 AMP-RA-SLE |       7 |          5 | Dermatomyositis; Psoriasis; Rheumatoid arthritis; Systemic lupus erythematosus; Vitiligo | RNA, cytometry, spatial | synovial tissue  | 9094 MB
(3 rows)
```

> **Coverage:** Coverage is honest but bounded by what harmonized_output actually contains (23 files total): AMP-AD (11 files, ATAC+RNA pseudobulk + 1 RNA matrix, postmortem brain, Alzheimer's only), AMP-CMD (5 RNA files, hypothalamus, NORMAL REFERENCE — carries no 4234469 disease record by design, so n_diseases=0 and disease is NULL/'normal reference'), AMP-RA-SLE (7 files: RNA pseudobulk + cytometry + spatial matrices, synovial tissue, 9 diseases). AMP-PD has ZERO harmonized_output files — PD is proteomics assay_matrix only (no brain HDF5), so it never appears in these results; a PI judging PD relevance must look at source/assay_matrix roles, not harmonized. The 'normal reference (no disease record)' rows in AMP-AD and AMP-RA-SLE are real: those pseudobulk files also draw from CONTROL contributors (qualifier 44804027 / value 45884153 Normal, excluded from the disease set), which the LEFT JOIN surfaces as NULL disease — it is not a missing-data artifact. Disease is contributor-derived: a pseudobulk file aggregates many participants, so a single file legitimately maps to MANY diseases (RA-SLE files each map to all 9) — n_files per disease is not additive across diseases. tissue and biosample_type are identical columns in this data (kept both for transparency). Total sizes were cross-checked against a direct file-level SUM per study and match exactly.


### S2 — how to obtain data access and what the data-use requirements are

**base** — As a PI, what access groups exist, what is each one's scope/program, and where do the data-use-limitation (DUL) and access-instruction texts live?
```sql
SELECT g.id, g.code, g.name, g.program, g.disease_focus,
       g.description,
       COALESCE(NULLIF(g.dul,''),'(not populated - awaiting real AMP policy drop)')                      AS dul,
       COALESCE(NULLIF(g.data_access_instructions,''),'(not populated - awaiting real AMP policy drop)') AS data_access_instructions
FROM cdm.access_groups g
ORDER BY g.id;
```
Returns — id, code, name, program, disease_focus, description, dul, data_access_instructions (one row per program access group):
```
 id |    code    |    name    |  program   |                     disease_focus                     |                            description                            |                       dul                       |            data_access_instructions             
----+------------+------------+------------+-------------------------------------------------------+-------------------------------------------------------------------+-------------------------------------------------+-------------------------------------------------
  1 | AMP-PD     | AMP PD     | AMP-PD     | Parkinson's disease                                   | AMP Parkinson's Disease program                                   | (not populated - awaiting real AMP policy drop) | (not populated - awaiting real AMP policy drop)
  2 | AMP-AD     | AMP AD     | AMP-AD     | Alzheimer's disease and related dementias             | AMP Alzheimer's Disease program                                   | (not populated - awaiting real AMP policy drop) | (not populated - awaiting real AMP policy drop)
  3 | AMP-CMD    | AMP CMD    | AMP-CMD    | Kidney, muscle and adipose metabolic disease          | AMP Common Metabolic Diseases program                             | (not populated - awaiting real AMP policy drop) | (not populated - awaiting real AMP policy drop)
  4 | AMP-RA-SLE | AMP RA/SLE | AMP-RA-SLE | Rheumatoid arthritis and systemic lupus erythematosus | AMP Rheumatoid Arthritis and Systemic Lupus Erythematosus program | (not populated - awaiting real AMP policy drop) | (not populated - awaiting real AMP policy drop)
(4 rows)
```

**variation: how do I obtain access (the grant mechanism)** — Concretely, how is access granted -- which user principals are enrolled in which program access group, by whom, and when?
```sql
SELECT uag.user_id,
       g.code           AS access_group,
       g.program,
       g.disease_focus,
       uag.granted_by,
       uag.granted_at::date AS granted_at
FROM cdm.user_access_groups uag
JOIN cdm.access_groups g ON g.id = uag.access_group_id
ORDER BY uag.user_id, g.id;
```
Returns — user_id, access_group, program, disease_focus, granted_by, granted_at -- the enrollment rows that ARE access (a PI is granted a program group here; consortium_admin holds all four):
```
     user_id      | access_group |  program   |                     disease_focus                     | granted_by | granted_at 
------------------+--------------+------------+-------------------------------------------------------+------------+------------
 ad_user          | AMP-AD       | AMP-AD     | Alzheimer's disease and related dementias             | system     | 2016-06-01
 consortium_admin | AMP-PD       | AMP-PD     | Parkinson's disease                                   | system     | 2016-06-01
 consortium_admin | AMP-AD       | AMP-AD     | Alzheimer's disease and related dementias             | system     | 2016-06-01
 consortium_admin | AMP-CMD      | AMP-CMD    | Kidney, muscle and adipose metabolic disease          | system     | 2016-06-01
 consortium_admin | AMP-RA-SLE   | AMP-RA-SLE | Rheumatoid arthritis and systemic lupus erythematosus | system     | 2016-06-01
 rasle_user       | AMP-RA-SLE   | AMP-RA-SLE | Rheumatoid arthritis and systemic lupus erythematosus | system     | 2016-06-01
(6 rows)
```

**variation: what each grant unlocks (scope of data)** — For each program access group, how much governed data does being granted it actually unlock (files, specimens, observations, measurements) and how many users hold it?
```sql
SELECT g.code AS access_group, g.program, g.disease_focus,
  (SELECT count(*) FROM cdm.file_access fa        WHERE fa.access_group_id=g.id) AS files,
  (SELECT count(*) FROM cdm.specimen_access sa    WHERE sa.access_group_id=g.id) AS specimens,
  (SELECT count(*) FROM cdm.observation_access oa WHERE oa.access_group_id=g.id) AS observations,
  (SELECT count(*) FROM cdm.measurement_access ma WHERE ma.access_group_id=g.id) AS measurements,
  (SELECT count(*) FROM cdm.user_access_groups u  WHERE u.access_group_id=g.id)  AS granted_users
FROM cdm.access_groups g ORDER BY g.id;
```
Returns — access_group, program, disease_focus, files, specimens, observations, measurements, granted_users -- one row per program summarizing the record-level RLS-governed entities behind each grant:
```
 access_group |  program   |                     disease_focus                     | files | specimens | observations | measurements | granted_users 
--------------+------------+-------------------------------------------------------+-------+-----------+--------------+--------------+---------------
 AMP-PD       | AMP-PD     | Parkinson's disease                                   |     2 |      2038 |       636910 |       288141 |             1
 AMP-AD       | AMP-AD     | Alzheimer's disease and related dementias             |  1652 |      1541 |        20231 |         2551 |             2
 AMP-CMD      | AMP-CMD    | Kidney, muscle and adipose metabolic disease          |   181 |       203 |         1477 |          203 |             1
 AMP-RA-SLE   | AMP-RA-SLE | Rheumatoid arthritis and systemic lupus erythematosus |   743 |       887 |         4287 |         1240 |             2
(4 rows)
```

**variation: DUL / attribution text per program (carrier status)** — What is the exact attribution / data-use-limitation text a PI must honor per program, and what scope can they cite today?
```sql
SELECT g.program,
       g.disease_focus                                        AS citable_scope_today,
       length(g.dul)                                          AS dul_text_len,
       length(g.data_access_instructions)                     AS instr_text_len,
       CASE WHEN COALESCE(g.dul,'')='' AND COALESCE(g.data_access_instructions,'')=''
            THEN 'carrier present, text not populated (real AMP DUL not in-repo, none invented)'
            ELSE 'populated' END                               AS attribution_status
FROM cdm.access_groups g
ORDER BY g.id;
```
Returns — program, citable_scope_today (=disease_focus), dul_text_len, instr_text_len (both NULL/empty), attribution_status -- honestly shows dul + data_access_instructions are the designated carrier fields but hold no text yet:
```
  program   |                  citable_scope_today                  | dul_text_len | instr_text_len |                              attribution_status                               
------------+-------------------------------------------------------+--------------+----------------+-------------------------------------------------------------------------------
 AMP-PD     | Parkinson's disease                                   |              |                | carrier present, text not populated (real AMP DUL not in-repo, none invented)
 AMP-AD     | Alzheimer's disease and related dementias             |              |                | carrier present, text not populated (real AMP DUL not in-repo, none invented)
 AMP-CMD    | Kidney, muscle and adipose metabolic disease          |              |                | carrier present, text not populated (real AMP DUL not in-repo, none invented)
 AMP-RA-SLE | Rheumatoid arthritis and systemic lupus erythematosus |              |                | carrier present, text not populated (real AMP DUL not in-repo, none invented)
(4 rows)
```

> **Coverage:** The DUL/attribution deliverable cannot return real policy text: cdm.access_groups.dul and .data_access_instructions are empty for all 4 programs. This is BY DESIGN, not a load bug -- the source config/access_groups.tsv (lines 8-9) states real AMP data-use-limitation text is not in-repo and 'we invent none; the mechanism carries them; a future real policy drop fills them.' So the 'exact attribution/DUL text per program' variation surfaces the carrier fields and their empty status (with disease_focus as the only citable, factual per-program scope available today) rather than fabricating attribution language. Only these 4 program-level access groups exist (no sub-program or study-arm groups). user_access_groups holds just 4 synthetic principals (ad_user, rasle_user, consortium_admin who holds all four, and one PD grant) -- there is no real IdP, application workflow, or approval-request table, so 'how a PI applies' is represented only as the resulting grant rows, not an application process. Per-group entity counts reflect the file-driven/program-fallback tagging (e.g. AMP-CMD has 0 governed observations, consistent with CMD carrying no 4234469 disease record); AMP-PD's very large observation/measurement counts come from its proteomics assay_matrix load. granted_at is a deterministic constant stamp (2016-06-01), not a real event time.


### S3 — pseudobulk HDF5 from AD or PD postmortem brain, to compare shared molecular features

**base** — List the harmonized pseudobulk brain HDF5 files whose contributors are diagnosed with AD (36311271) or PD (381270).
```sql
SELECT DISTINCT f.file_name, f.cell_type, f.biosample_type, f.analysis_type, dx.concept_name AS disease
FROM cdm.files f
JOIN cdm.assay_input_file aif ON aif.file_id = f.file_id
JOIN cdm.assay a ON a.assay_id = aif.assay_id
JOIN cdm.assay_to_specimen ats ON ats.assay_id = a.assay_id
JOIN cdm.specimen s ON s.specimen_id = ats.specimen_id
JOIN cdm.observation co ON co.person_id = s.person_id AND co.observation_concept_id = 4234469
JOIN cdm.concept dx ON dx.concept_id = co.value_as_concept_id
WHERE f.file_role = 'harmonized_output'
  AND f.file_format = 'HDF5'
  AND f.file_name ILIKE '%pseudobulk%'
  AND dx.concept_id IN (36311271, 381270)
  AND f.biosample_type ILIKE '%brain%'
ORDER BY f.analysis_type, f.cell_type;
```
Returns — file_name, cell_type, biosample_type, analysis_type, disease -- one row per harmonized pseudobulk brain HDF5 file (all AD; PD returns none):
```
                    file_name                    |       cell_type       |  biosample_type  | analysis_type |       disease       
-------------------------------------------------+-----------------------+------------------+---------------+---------------------
 AMP-AD_ATAC_pseudobulk_GABAergic_neurons.h5     | GABAergic neurons     | postmortem brain | ATAC          | Alzheimer's disease
 AMP-AD_ATAC_pseudobulk_GLUtamatergic_neurons.h5 | GLUtamatergic neurons | postmortem brain | ATAC          | Alzheimer's disease
 AMP-AD_ATAC_pseudobulk_astrocytes.h5            | astrocytes            | postmortem brain | ATAC          | Alzheimer's disease
 AMP-AD_ATAC_pseudobulk_microglia.h5             | microglia             | postmortem brain | ATAC          | Alzheimer's disease
 AMP-AD_ATAC_pseudobulk_oligodendrocyte.h5       | oligodendrocyte       | postmortem brain | ATAC          | Alzheimer's disease
 AMP-AD_RNA_pseudobulk_GABAergic_neurons.h5      | GABAergic neurons     | postmortem brain | RNA           | Alzheimer's disease
 AMP-AD_RNA_pseudobulk_GLUtamatergic_neurons.h5  | GLUtamatergic neurons | postmortem brain | RNA           | Alzheimer's disease
 AMP-AD_RNA_pseudobulk_astrocytes.h5             | astrocytes            | postmortem brain | RNA           | Alzheimer's disease
 AMP-AD_RNA_pseudobulk_microglia.h5              | microglia             | postmortem brain | RNA           | Alzheimer's disease
 AMP-AD_RNA_pseudobulk_oligodendrocyte.h5        | oligodendrocyte       | postmortem brain | RNA           | Alzheimer's disease
(10 rows)
```

**variation: cell types available** — Which cell types (and assay modalities) are available as AD pseudobulk brain HDF5 files, so I can pick a comparison grain?
```sql
SELECT f.analysis_type, f.cell_type, count(DISTINCT f.file_name) AS n_files
FROM cdm.files f
JOIN cdm.assay_input_file aif ON aif.file_id = f.file_id
JOIN cdm.assay a ON a.assay_id = aif.assay_id
JOIN cdm.assay_to_specimen ats ON ats.assay_id = a.assay_id
JOIN cdm.specimen s ON s.specimen_id = ats.specimen_id
JOIN cdm.observation co ON co.person_id = s.person_id AND co.observation_concept_id = 4234469
JOIN cdm.concept dx ON dx.concept_id = co.value_as_concept_id
WHERE f.file_role = 'harmonized_output'
  AND f.file_format = 'HDF5'
  AND f.file_name ILIKE '%pseudobulk%'
  AND dx.concept_id = 36311271
  AND f.biosample_type ILIKE '%brain%'
GROUP BY f.analysis_type, f.cell_type
ORDER BY f.cell_type, f.analysis_type;
```
Returns — analysis_type, cell_type, n_files -- 5 brain cell types x 2 modalities (RNA + ATAC), one pseudobulk file each:
```
 analysis_type |       cell_type       | n_files 
---------------+-----------------------+---------
 ATAC          | GABAergic neurons     |       1
 RNA           | GABAergic neurons     |       1
 ATAC          | GLUtamatergic neurons |       1
 RNA           | GLUtamatergic neurons |       1
 ATAC          | astrocytes            |       1
 RNA           | astrocytes            |       1
 ATAC          | microglia             |       1
 RNA           | microglia             |       1
 ATAC          | oligodendrocyte       |       1
 RNA           | oligodendrocyte       |       1
(10 rows)
```

**variation: PD absence made explicit** — Why is PD absent from the file list -- what harmonized data do AD vs PD contributors actually reach?
```sql
SELECT dx.concept_name AS disease,
       count(DISTINCT co.person_id) AS n_contributors,
       coalesce(f.file_format,'(none)') AS harmonized_format,
       coalesce(f.analysis_type,'(none)') AS analysis_type,
       count(DISTINCT f.file_name) AS n_harmonized_files
FROM cdm.observation co
JOIN cdm.concept dx ON dx.concept_id = co.value_as_concept_id
LEFT JOIN cdm.specimen s ON s.person_id = co.person_id
LEFT JOIN cdm.assay_to_specimen ats ON ats.specimen_id = s.specimen_id
LEFT JOIN cdm.assay a ON a.assay_id = ats.assay_id
LEFT JOIN cdm.assay_input_file aif ON aif.assay_id = a.assay_id
LEFT JOIN cdm.files f ON f.file_id = aif.file_id AND f.file_role = 'harmonized_output'
WHERE co.observation_concept_id = 4234469
  AND dx.concept_id IN (36311271, 381270)
GROUP BY dx.concept_name, coalesce(f.file_format,'(none)'), coalesce(f.analysis_type,'(none)')
ORDER BY dx.concept_name, n_harmonized_files DESC;
```
Returns — disease, n_contributors, harmonized_format, analysis_type, n_harmonized_files -- LEFT JOIN so PD's 448 contributors surface with 0 HDF5; only AD reaches brain HDF5:
```
       disease       | n_contributors | harmonized_format | analysis_type | n_harmonized_files 
---------------------+----------------+-------------------+---------------+--------------------
 Alzheimer's disease |             66 | HDF5              | RNA           |                  6
 Alzheimer's disease |             46 | HDF5              | ATAC          |                  5
 Alzheimer's disease |             78 | (none)            | (none)        |                  0
 Parkinson's disease |            448 | (none)            | (none)        |                  0
(4 rows)
```

**variation: file sizes by modality** — How large are the AD pseudobulk brain HDF5 files by modality and cell type (to plan a download)?
```sql
SELECT DISTINCT f.analysis_type, f.cell_type, f.file_name,
       pg_size_pretty(f.file_size_bytes) AS size, f.file_size_bytes
FROM cdm.files f
JOIN cdm.assay_input_file aif ON aif.file_id = f.file_id
JOIN cdm.assay a ON a.assay_id = aif.assay_id
JOIN cdm.assay_to_specimen ats ON ats.assay_id = a.assay_id
JOIN cdm.specimen s ON s.specimen_id = ats.specimen_id
JOIN cdm.observation co ON co.person_id = s.person_id AND co.observation_concept_id = 4234469
WHERE f.file_role = 'harmonized_output'
  AND f.file_format = 'HDF5'
  AND f.file_name ILIKE '%pseudobulk%'
  AND co.value_as_concept_id = 36311271
  AND f.biosample_type ILIKE '%brain%'
ORDER BY f.analysis_type, f.file_size_bytes DESC;
```
Returns — analysis_type, cell_type, file_name, size (pretty), file_size_bytes -- 10 files, RNA totals ~7 GB, ATAC ~5 GB:
```
 analysis_type |       cell_type       |                    file_name                    |  size   | file_size_bytes 
---------------+-----------------------+-------------------------------------------------+---------+-----------------
 ATAC          | oligodendrocyte       | AMP-AD_ATAC_pseudobulk_oligodendrocyte.h5       | 1545 MB |      1620533642
 ATAC          | microglia             | AMP-AD_ATAC_pseudobulk_microglia.h5             | 1060 MB |      1111735650
 ATAC          | GABAergic neurons     | AMP-AD_ATAC_pseudobulk_GABAergic_neurons.h5     | 952 MB  |       998196302
 ATAC          | astrocytes            | AMP-AD_ATAC_pseudobulk_astrocytes.h5            | 933 MB  |       978613038
 ATAC          | GLUtamatergic neurons | AMP-AD_ATAC_pseudobulk_GLUtamatergic_neurons.h5 | 518 MB  |       543063200
 RNA           | astrocytes            | AMP-AD_RNA_pseudobulk_astrocytes.h5             | 2610 MB |      2736574042
 RNA           | GLUtamatergic neurons | AMP-AD_RNA_pseudobulk_GLUtamatergic_neurons.h5  | 1614 MB |      1691972273
 RNA           | oligodendrocyte       | AMP-AD_RNA_pseudobulk_oligodendrocyte.h5        | 1228 MB |      1287933158
 RNA           | GABAergic neurons     | AMP-AD_RNA_pseudobulk_GABAergic_neurons.h5      | 808 MB  |       847178453
 RNA           | microglia             | AMP-AD_RNA_pseudobulk_microglia.h5              | 608 MB  |       637200312
(10 rows)
```

> **Coverage:** The comparison the story asks for (AD vs PD molecular features) cannot be done from harmonized brain HDF5: only AD has postmortem-brain pseudobulk HDF5. PD carries NO brain HDF5 -- its 448 diagnosed contributors reach zero harmonized_output HDF5 (variation 2 proves this via LEFT JOIN); PD's only harmonized/matrix asset is AMP-PD_proteomics_matrix.parquet (assay_matrix, plasma tissue, 344 MB), a different modality and biosample, so AD-vs-PD is not achievable at the pseudobulk-brain grain. Base therefore returns AD-only (10 files: 5 cell types x RNA+ATAC). biosample_type and tissue are identical ('postmortem brain') on every AD file, so no separate anatomic subsite is distinguishable. Not every AD case feeds the assays: of ~216 AD contributors only ~138 (RNA) / ~89 (ATAC) link through specimens to a harmonized file; ~142 reach none. AMP-CMD (hypothalamus) and AMP-RA-SLE (synovial) HDF5 files exist but are excluded here because CMD carries no disease record and RA-SLE is not AD/PD; the AMP-AD_RNA_matrix.hdf5 full matrix is excluded from base by the 'pseudobulk' name filter (it appears if that filter is dropped).


### S4 — every pseudobulk HDF5 with sex, Dx, and specimen, for a sex-differential analysis across diseases

**base** — For every harmonized pseudobulk HDF5 file, what is the per cell_type x contributor-sex x Dx x specimen-source breakdown of contributing individuals (the DE design matrix)?
```sql
SELECT f.file_name,
       f.cell_type,
       f.tissue AS specimen_source,
       COALESCE(sx.concept_name,'(no sex record)') AS sex,
       COALESCE(dx.concept_name,'(no Dx record)')  AS dx,
       count(DISTINCT s.person_id) AS n_contributors
FROM cdm.files f
JOIN cdm.assay_input_file aif ON aif.file_id = f.file_id
JOIN cdm.assay a              ON a.assay_id  = aif.assay_id
JOIN cdm.assay_to_specimen ats ON ats.assay_id = a.assay_id
JOIN cdm.specimen s           ON s.specimen_id = ats.specimen_id
LEFT JOIN cdm.observation sxo ON sxo.person_id = s.person_id AND sxo.observation_source_value='sex'
LEFT JOIN cdm.concept    sx  ON sx.concept_id = sxo.value_as_concept_id
LEFT JOIN cdm.observation dxo ON dxo.person_id = s.person_id AND dxo.observation_concept_id=4234469
LEFT JOIN cdm.concept    dx  ON dx.concept_id = dxo.value_as_concept_id
WHERE f.file_role='harmonized_output' AND f.file_format='HDF5' AND f.file_name ILIKE '%pseudobulk%'
GROUP BY f.file_name, f.cell_type, f.tissue, sx.concept_name, dx.concept_name
ORDER BY f.file_name, dx, sex;
```
Returns — file_name, cell_type, specimen_source, sex, dx, n_contributors (one row per file x cell_type x sex x disease x tissue):
```
                    file_name                     |       cell_type       | specimen_source  |  sex   |               dx                | n_contributors 
--------------------------------------------------+-----------------------+------------------+--------+---------------------------------+----------------
 AMP-AD_ATAC_pseudobulk_astrocytes.h5             | astrocytes            | postmortem brain | FEMALE | Alzheimer's disease             |             46
 AMP-AD_ATAC_pseudobulk_astrocytes.h5             | astrocytes            | postmortem brain | MALE   | Alzheimer's disease             |             43
 AMP-AD_ATAC_pseudobulk_astrocytes.h5             | astrocytes            | postmortem brain | FEMALE | Normal                          |             25
 AMP-AD_ATAC_pseudobulk_astrocytes.h5             | astrocytes            | postmortem brain | MALE   | Normal                          |             29
 AMP-AD_ATAC_pseudobulk_astrocytes.h5             | astrocytes            | postmortem brain | FEMALE | Not applicable                  |              3
 AMP-AD_ATAC_pseudobulk_astrocytes.h5             | astrocytes            | postmortem brain | MALE   | Not applicable                  |              1
 AMP-AD_ATAC_pseudobulk_astrocytes.h5             | astrocytes            | postmortem brain | FEMALE | Other                           |             76
 AMP-AD_ATAC_pseudobulk_astrocytes.h5             | astrocytes            | postmortem brain | MALE   | Other                           |            107
 AMP-AD_ATAC_pseudobulk_GABAergic_neurons.h5      | GABAergic neurons     | postmortem brain | FEMALE | Alzheimer's disease             |             46
 AMP-AD_ATAC_pseudobulk_GABAergic_neurons.h5      | GABAergic neurons     | postmortem brain | MALE   | Alzheimer's disease             |             43
 AMP-AD_ATAC_pseudobulk_GABAergic_neurons.h5      | GABAergic neurons     | postmortem brain | FEMALE | Normal                          |             25
 AMP-AD_ATAC_pseudobulk_GABAergic_neurons.h5      | GABAergic neurons     | postmortem brain | MALE   | Normal                          |             29
…  (192 rows total)
```

**variation: sex x disease contributor counts** — Among individuals who contribute to the pseudobulk HDF5 files, how many males vs females are available per real disease (i.e. where is a male-vs-female DE contrast actually powered)?
```sql
WITH contrib AS (
  SELECT DISTINCT s.person_id
  FROM cdm.files f
  JOIN cdm.assay_input_file aif ON aif.file_id=f.file_id
  JOIN cdm.assay a ON a.assay_id=aif.assay_id
  JOIN cdm.assay_to_specimen ats ON ats.assay_id=a.assay_id
  JOIN cdm.specimen s ON s.specimen_id=ats.specimen_id
  WHERE f.file_role='harmonized_output' AND f.file_format='HDF5' AND f.file_name ILIKE '%pseudobulk%'
)
SELECT dx.concept_name AS disease,
       count(DISTINCT s.person_id) FILTER (WHERE sxo.value_as_concept_id=8507)  AS male,
       count(DISTINCT s.person_id) FILTER (WHERE sxo.value_as_concept_id=8532)  AS female,
       count(DISTINCT s.person_id) FILTER (WHERE sxo.value_as_concept_id=45877986 OR sxo.value_as_concept_id IS NULL) AS unknown_or_missing,
       count(DISTINCT s.person_id) AS total
FROM contrib s
JOIN cdm.observation dxo ON dxo.person_id=s.person_id AND dxo.observation_concept_id=4234469
JOIN cdm.concept dx ON dx.concept_id=dxo.value_as_concept_id
LEFT JOIN cdm.observation sxo ON sxo.person_id=s.person_id AND sxo.observation_source_value='sex'
WHERE dxo.value_as_concept_id NOT IN (45884153,45878142,45882470,45877986)
GROUP BY dx.concept_name
ORDER BY total DESC;
```
Returns — disease, male, female, unknown_or_missing, total (one row per real disease; status codes 45884153/45878142/45882470/45877986 excluded):
```
           disease            | male | female | unknown_or_missing | total 
------------------------------+------+--------+--------------------+-------
 Alzheimer's disease          |    4 |     12 |                 54 |    70
 Systemic lupus erythematosus |   12 |     38 |                  1 |    51
 Rheumatoid arthritis         |    8 |     27 |                  1 |    36
 Vitiligo                     |    1 |      2 |                  0 |     3
 Dermatomyositis              |    0 |      1 |                  0 |     1
(5 rows)
```

**variation: per biosample source x sex** — How does male/female contributor availability break down by biospecimen source (study x tissue) across the pseudobulk HDF5 set?
```sql
SELECT f.study,
       f.tissue AS biosample_source,
       count(DISTINCT f.file_id) AS n_files,
       count(DISTINCT s.person_id) FILTER (WHERE sxo.value_as_concept_id=8507)  AS male,
       count(DISTINCT s.person_id) FILTER (WHERE sxo.value_as_concept_id=8532)  AS female,
       count(DISTINCT s.person_id) FILTER (WHERE sxo.value_as_concept_id=45877986 OR sxo.value_as_concept_id IS NULL) AS unknown_or_missing,
       count(DISTINCT s.person_id) AS total_contributors
FROM cdm.files f
JOIN cdm.assay_input_file aif ON aif.file_id=f.file_id
JOIN cdm.assay a ON a.assay_id=aif.assay_id
JOIN cdm.assay_to_specimen ats ON ats.assay_id=a.assay_id
JOIN cdm.specimen s ON s.specimen_id=ats.specimen_id
LEFT JOIN cdm.observation sxo ON sxo.person_id=s.person_id AND sxo.observation_source_value='sex'
WHERE f.file_role='harmonized_output' AND f.file_format='HDF5' AND f.file_name ILIKE '%pseudobulk%'
GROUP BY f.study, f.tissue
ORDER BY total_contributors DESC;
```
Returns — study, biosample_source, n_files, male, female, unknown_or_missing, total_contributors (one row per study x tissue):
```
   study    | biosample_source | n_files | male | female | unknown_or_missing | total_contributors 
------------+------------------+---------+------+--------+--------------------+--------------------
 AMP-AD     | postmortem brain |      10 |   33 |     68 |                424 |                525
 AMP-RA-SLE | synovial tissue  |       4 |   29 |     87 |                  2 |                118
 AMP-CMD    | hypothalamus     |       4 |   30 |     26 |                  0 |                 56
(3 rows)
```

**variation: per-file sex-balance catalog** — Give the full catalog of the 18 pseudobulk HDF5 files (with size) and each file's male/female/unknown contributor counts, so I can pick which files support a sex contrast.
```sql
SELECT f.study,
       f.file_name,
       f.cell_type,
       f.analysis_type AS assay,
       pg_size_pretty(f.file_size_bytes) AS size,
       count(DISTINCT s.person_id) FILTER (WHERE sxo.value_as_concept_id=8507) AS male,
       count(DISTINCT s.person_id) FILTER (WHERE sxo.value_as_concept_id=8532) AS female,
       count(DISTINCT s.person_id) FILTER (WHERE sxo.value_as_concept_id=45877986 OR sxo.value_as_concept_id IS NULL) AS unk_or_missing
FROM cdm.files f
JOIN cdm.assay_input_file aif ON aif.file_id=f.file_id
JOIN cdm.assay a ON a.assay_id=aif.assay_id
JOIN cdm.assay_to_specimen ats ON ats.assay_id=a.assay_id
JOIN cdm.specimen s ON s.specimen_id=ats.specimen_id
LEFT JOIN cdm.observation sxo ON sxo.person_id=s.person_id AND sxo.observation_source_value='sex'
WHERE f.file_role='harmonized_output' AND f.file_format='HDF5' AND f.file_name ILIKE '%pseudobulk%'
GROUP BY f.study, f.file_name, f.cell_type, f.analysis_type, f.file_size_bytes
ORDER BY f.study, f.file_name;
```
Returns — study, file_name, cell_type, assay, size, male, female, unk_or_missing (one row per pseudobulk HDF5 file; all 18 files):
```
   study    |                    file_name                     |       cell_type       | assay |  size   | male | female | unk_or_missing 
------------+--------------------------------------------------+-----------------------+-------+---------+------+--------+----------------
 AMP-AD     | AMP-AD_ATAC_pseudobulk_astrocytes.h5             | astrocytes            | ATAC  | 933 MB  |  180 |    150 |              0
 AMP-AD     | AMP-AD_ATAC_pseudobulk_GABAergic_neurons.h5      | GABAergic neurons     | ATAC  | 952 MB  |  180 |    150 |              0
 AMP-AD     | AMP-AD_ATAC_pseudobulk_GLUtamatergic_neurons.h5  | GLUtamatergic neurons | ATAC  | 518 MB  |  180 |    150 |              0
 AMP-AD     | AMP-AD_ATAC_pseudobulk_microglia.h5              | microglia             | ATAC  | 1060 MB |  180 |    150 |              0
 AMP-AD     | AMP-AD_ATAC_pseudobulk_oligodendrocyte.h5        | oligodendrocyte       | ATAC  | 1545 MB |  180 |    150 |              0
 AMP-AD     | AMP-AD_RNA_pseudobulk_astrocytes.h5              | astrocytes            | RNA   | 2610 MB |  249 |    171 |              0
 AMP-AD     | AMP-AD_RNA_pseudobulk_GABAergic_neurons.h5       | GABAergic neurons     | RNA   | 808 MB  |  249 |    171 |              0
 AMP-AD     | AMP-AD_RNA_pseudobulk_GLUtamatergic_neurons.h5   | GLUtamatergic neurons | RNA   | 1614 MB |  249 |    171 |              0
 AMP-AD     | AMP-AD_RNA_pseudobulk_microglia.h5               | microglia             | RNA   | 608 MB  |  249 |    171 |              0
 AMP-AD     | AMP-AD_RNA_pseudobulk_oligodendrocyte.h5         | oligodendrocyte       | RNA   | 1228 MB |  249 |    171 |              0
 AMP-CMD    | AMP-CMD_RNA_pseudobulk_astrocyte.h5              | astrocyte             | RNA   | 434 MB  |   31 |     25 |              0
 AMP-CMD    | AMP-CMD_RNA_pseudobulk_ependymal_cell.h5         | ependymal cell        | RNA   | 231 MB  |   31 |     25 |              0
…  (18 rows total)
```

> **Coverage:** Sex is now recorded for EVERY contributor via the harmonized `sex` observation (observation_concept_id 3046965 -> value_as_concept_id 8507=MALE / 8532=FEMALE; join on the concept id, not the string, since Male/male map to the same id). All 525 AMP-AD, 118 AMP-RA-SLE and 56 AMP-CMD pseudobulk contributors carry a Male/Female value, so a male-vs-female DE contrast is powered across every program, disease, and biosample source.\n\nDisease coverage: AMP-CMD carries NO 4234469 disease record by design (normal hypothalamus reference), so its 4 pseudobulk files show '(no Dx record)'. AMP-PD has NO pseudobulk brain HDF5 at all (PD is proteomics assay_matrix only), so PD is entirely absent from this file set. The base cross-cut also surfaces non-disease status Dx values (Normal/Other/Not applicable) which are excluded in the sex-x-disease variation via the standard status-code filter (45884153, 45878142, 45882470, 45877986).\n\nScope: the pseudobulk filter (file_name ILIKE '%pseudobulk%') deliberately excludes the 4 whole-matrix HDF5 files (RNA_matrix / spatial_matrix, cell_type NULL); the harmonized HDF5 pseudobulk set is exactly 18 files. Multi-visit participants (AMP-RA-SLE has 178 specimens vs 118 persons) are de-duplicated throughout via count(DISTINCT person_id).


### S5 — pseudobulked microglia HDF5, to compare microglia features across Dx and sex

**base** — Which HDF5 files are pseudobulked microglia, and what is the Dx x Sex cross-tab of the contributors behind each?
```sql
WITH contrib AS (
  SELECT DISTINCT f.file_name, f.analysis_type, s.person_id
  FROM cdm.files f
  JOIN cdm.assay_input_file aif ON aif.file_id=f.file_id
  JOIN cdm.assay a ON a.assay_id=aif.assay_id
  JOIN cdm.assay_to_specimen ats ON ats.assay_id=a.assay_id
  JOIN cdm.specimen s ON s.specimen_id=ats.specimen_id
  WHERE f.file_role='harmonized_output' AND f.cell_type='microglia' AND f.file_format='HDF5'
),
sex AS (
  SELECT person_id, max(value_as_concept_id) AS sex_cid
  FROM cdm.observation WHERE observation_source_value='sex' GROUP BY person_id
)
SELECT c.file_name, c.analysis_type, dx.concept_name AS dx,
       count(*) FILTER (WHERE sx.sex_cid=8532)     AS female,
       count(*) FILTER (WHERE sx.sex_cid=8507)     AS male,
       count(*) FILTER (WHERE sx.sex_cid=45877986 OR sx.sex_cid IS NULL) AS unknown,
       count(*) AS total
FROM contrib c
JOIN cdm.observation co ON co.person_id=c.person_id AND co.observation_concept_id=4234469
JOIN cdm.concept dx ON dx.concept_id=co.value_as_concept_id
LEFT JOIN sex sx ON sx.person_id=c.person_id
GROUP BY c.file_name, c.analysis_type, dx.concept_name
ORDER BY c.file_name, total DESC;
```
Returns — file_name, analysis_type, dx, female, male, unknown, total (one row per microglia HDF5 file x Dx; sex pivoted to columns):
```
              file_name              | analysis_type |         dx          | female | male | unknown | total 
-------------------------------------+---------------+---------------------+--------+------+---------+-------
 AMP-AD_ATAC_pseudobulk_microglia.h5 | ATAC          | Other               |     14 |   12 |     124 |   150
 AMP-AD_ATAC_pseudobulk_microglia.h5 | ATAC          | Alzheimer's disease |     12 |    3 |      31 |    46
 AMP-AD_ATAC_pseudobulk_microglia.h5 | ATAC          | Normal              |      4 |    3 |      28 |    35
 AMP-AD_RNA_pseudobulk_microglia.h5  | RNA           | Other               |     22 |   12 |     163 |   197
 AMP-AD_RNA_pseudobulk_microglia.h5  | RNA           | Normal              |      6 |    6 |      39 |    51
 AMP-AD_RNA_pseudobulk_microglia.h5  | RNA           | Alzheimer's disease |      9 |    2 |      37 |    48
(6 rows)
```

**variation: file inventory (names + sizes)** — What exactly are the pseudobulked-microglia HDF5 files -- names, program, assay modality, tissue, and size?
```sql
SELECT file_id, file_name, study, analysis_type, cell_type, tissue,
       pg_size_pretty(file_size_bytes) AS size
FROM cdm.files
WHERE file_role='harmonized_output' AND file_format='HDF5' AND cell_type='microglia'
ORDER BY file_name;
```
Returns — file_id, file_name, study, analysis_type, cell_type, tissue, size (one row per microglia HDF5 file):
```
  file_id  |              file_name              | study  | analysis_type | cell_type |      tissue      |  size   
-----------+-------------------------------------+--------+---------------+-----------+------------------+---------
 152000001 | AMP-AD_ATAC_pseudobulk_microglia.h5 | AMP-AD | ATAC          | microglia | postmortem brain | 1060 MB
 152000006 | AMP-AD_RNA_pseudobulk_microglia.h5  | AMP-AD | RNA           | microglia | postmortem brain | 608 MB
(2 rows)
```

**variation: collapsed case/control x Sex** — Pooling both microglia HDF5 files, what is the clean case-vs-control x Sex cross-tab of distinct contributors?
```sql
WITH contrib AS (
  SELECT DISTINCT s.person_id
  FROM cdm.files f
  JOIN cdm.assay_input_file aif ON aif.file_id=f.file_id
  JOIN cdm.assay a ON a.assay_id=aif.assay_id
  JOIN cdm.assay_to_specimen ats ON ats.assay_id=a.assay_id
  JOIN cdm.specimen s ON s.specimen_id=ats.specimen_id
  WHERE f.file_role='harmonized_output' AND f.cell_type='microglia' AND f.file_format='HDF5'
),
sex AS (
  SELECT person_id, max(value_as_concept_id) AS sex_cid
  FROM cdm.observation WHERE observation_source_value='sex' GROUP BY person_id
)
SELECT CASE WHEN co.qualifier_concept_id=44804027 THEN 'Control (Normal)'
            WHEN co.qualifier_concept_id=1989833  THEN 'Case: '||dx.concept_name
            ELSE dx.concept_name END AS dx_group,
       count(*) FILTER (WHERE sx.sex_cid=8532) AS female,
       count(*) FILTER (WHERE sx.sex_cid=8507) AS male,
       count(*) FILTER (WHERE sx.sex_cid=45877986 OR sx.sex_cid IS NULL) AS unknown,
       count(*) AS total
FROM contrib c
JOIN cdm.observation co ON co.person_id=c.person_id AND co.observation_concept_id=4234469
JOIN cdm.concept dx ON dx.concept_id=co.value_as_concept_id
LEFT JOIN sex sx ON sx.person_id=c.person_id
GROUP BY 1 ORDER BY total DESC;
```
Returns — dx_group (case/control label), female, male, unknown, total (one row per Dx group; 525 distinct contributors de-duped across both files):
```
         dx_group          | female | male | unknown | total 
---------------------------+--------+------+---------+-------
 Other                     |     26 |   15 |     201 |   242
 Case: Alzheimer's disease |     12 |    4 |      54 |    70
 Control (Normal)          |      6 |    6 |      45 |    57
(3 rows)
```

**variation: per program** — Across all programs that ship pseudobulk cell-type HDF5, which offer microglia -- so the microglia request can be placed in the per-program landscape?
```sql
SELECT study AS program,
       count(*) AS pseudobulk_hdf5_files,
       string_agg(DISTINCT cell_type, ', ' ORDER BY cell_type) AS cell_types,
       bool_or(cell_type='microglia') AS has_microglia
FROM cdm.files
WHERE file_role='harmonized_output' AND file_format='HDF5' AND file_name ILIKE '%pseudobulk%'
GROUP BY study ORDER BY study;
```
Returns — program, pseudobulk_hdf5_files, cell_types (agg), has_microglia (bool) -- one row per program:
```
  program   | pseudobulk_hdf5_files |                                    cell_types                                    | has_microglia 
------------+-----------------------+----------------------------------------------------------------------------------+---------------
 AMP-AD     |                    10 | GABAergic neurons, GLUtamatergic neurons, astrocytes, microglia, oligodendrocyte | t
 AMP-CMD    |                     4 | astrocyte, ependymal cell, neuron, oligodendrocyte                               | f
 AMP-RA-SLE |                     4 | B cell, T cell, monocyte, synovial fibroblast                                    | f
(3 rows)
```

> **Coverage:** Only 2 microglia HDF5 files exist, both AMP-AD pseudobulk (ATAC 1060 MB + RNA 608 MB). Microglia pseudobulk HDF5 is AMP-AD-exclusive: no AMP-PD (PD is proteomics assay_matrix, no brain HDF5), AMP-CMD, or AMP-RA-SLE microglia HDF5 exist, so the 'per program' cross-tab necessarily collapses to AMP-AD -- the per-program variation instead shows microglia has no cross-program analog. Dx among contributors reduces to Alzheimer's disease (case, qualifier 1989833) vs Normal (control, qualifier 44804027); the 'Other' and 'Not applicable' rows are status-record diagnosis values with no qualifier, not real diseases -- keep them visible for completeness but they are noise for AD-vs-control comparison. Sex is now recorded for all microglia contributors via the harmonized `sex` observation (concept 3046965 -> MALE 8507 / FEMALE 8532), so the Dx x Sex cross-tab is fully populated (no longer Unknown-dominated). Raw microglia files exist only as 320 fastq source_input files (not HDF5) and are correctly excluded. Contributor path is via assay_input_file (M:N), so a donor can back both the ATAC and RNA file; the base double-counts across files while the collapsed variation de-dupes to 525 distinct contributors.


### S6 — pseudobulk HDF5 from multi-timepoint datasets, for disease-progression features

**base** — Which harmonized pseudobulk HDF5 files come from datasets that have multiple time points (multi-visit participants), and how much longitudinal support does each have?
```sql
WITH pb AS (
  SELECT f.file_id, f.file_name, f.study, f.analysis_type, f.cell_type, f.file_size_bytes, s.person_id
  FROM cdm.files f
  JOIN cdm.assay_input_file aif ON aif.file_id=f.file_id
  JOIN cdm.assay a ON a.assay_id=aif.assay_id
  JOIN cdm.assay_to_specimen ats ON ats.assay_id=a.assay_id
  JOIN cdm.specimen s ON s.specimen_id=ats.specimen_id
  WHERE f.file_role='harmonized_output' AND f.file_format='HDF5' AND f.file_name ILIKE '%pseudobulk%'
),
vc AS (SELECT person_id, count(*) n_visits FROM cdm.visit_occurrence GROUP BY person_id)
SELECT pb.study, pb.file_name, pb.analysis_type, pb.cell_type,
       round(pb.file_size_bytes/1024.0/1024/1024,2) AS size_gb,
       count(DISTINCT pb.person_id) AS contributors,
       count(DISTINCT pb.person_id) FILTER (WHERE vc.n_visits>1) AS multi_visit_contributors,
       max(vc.n_visits) AS max_visits
FROM pb JOIN vc ON vc.person_id=pb.person_id
GROUP BY pb.study, pb.file_name, pb.analysis_type, pb.cell_type, pb.file_size_bytes
HAVING count(DISTINCT pb.person_id) FILTER (WHERE vc.n_visits>1) > 0
ORDER BY pb.study, pb.analysis_type, pb.file_name;
```
Returns — study, file_name, analysis_type, cell_type, size_gb, contributors, multi_visit_contributors, max_visits -- one row per pseudobulk HDF5 file that has >0 longitudinal (multi-visit) contributors:
```
   study    |                    file_name                     | analysis_type |       cell_type       | size_gb | contributors | multi_visit_contributors | max_visits 
------------+--------------------------------------------------+---------------+-----------------------+---------+--------------+--------------------------+------------
 AMP-AD     | AMP-AD_ATAC_pseudobulk_astrocytes.h5             | ATAC          | astrocytes            |    0.91 |          330 |                      127 |          6
 AMP-AD     | AMP-AD_ATAC_pseudobulk_GABAergic_neurons.h5      | ATAC          | GABAergic neurons     |    0.93 |          330 |                      127 |          6
 AMP-AD     | AMP-AD_ATAC_pseudobulk_GLUtamatergic_neurons.h5  | ATAC          | GLUtamatergic neurons |    0.51 |          330 |                      127 |          6
 AMP-AD     | AMP-AD_ATAC_pseudobulk_microglia.h5              | ATAC          | microglia             |    1.04 |          330 |                      127 |          6
 AMP-AD     | AMP-AD_ATAC_pseudobulk_oligodendrocyte.h5        | ATAC          | oligodendrocyte       |    1.51 |          330 |                      127 |          6
 AMP-AD     | AMP-AD_RNA_pseudobulk_astrocytes.h5              | RNA           | astrocytes            |    2.55 |          420 |                      169 |          6
 AMP-AD     | AMP-AD_RNA_pseudobulk_GABAergic_neurons.h5       | RNA           | GABAergic neurons     |    0.79 |          420 |                      169 |          6
 AMP-AD     | AMP-AD_RNA_pseudobulk_GLUtamatergic_neurons.h5   | RNA           | GLUtamatergic neurons |    1.58 |          420 |                      169 |          6
 AMP-AD     | AMP-AD_RNA_pseudobulk_microglia.h5               | RNA           | microglia             |    0.59 |          420 |                      169 |          6
 AMP-AD     | AMP-AD_RNA_pseudobulk_oligodendrocyte.h5         | RNA           | oligodendrocyte       |    1.20 |          420 |                      169 |          6
 AMP-RA-SLE | AMP-RA-SLE_RNA_pseudobulk_B_cell.h5              | RNA           | B cell                |    1.77 |          118 |                      107 |          6
 AMP-RA-SLE | AMP-RA-SLE_RNA_pseudobulk_monocyte.h5            | RNA           | monocyte              |    1.21 |          118 |                      107 |          6
…  (14 rows total)
```

**variation: participants by visit count / span** — Behind these pseudobulk files, which individual participants have the longest longitudinal follow-up (most time points / widest date span), and what disease do they carry?
```sql
WITH pb_people AS (
  SELECT DISTINCT f.study, s.person_id
  FROM cdm.files f
  JOIN cdm.assay_input_file aif ON aif.file_id=f.file_id
  JOIN cdm.assay a ON a.assay_id=aif.assay_id
  JOIN cdm.assay_to_specimen ats ON ats.assay_id=a.assay_id
  JOIN cdm.specimen s ON s.specimen_id=ats.specimen_id
  WHERE f.file_role='harmonized_output' AND f.file_format='HDF5' AND f.file_name ILIKE '%pseudobulk%'
),
v AS (
  SELECT person_id, count(*) n_visits, min(visit_start_date) first_visit, max(visit_start_date) last_visit,
         (max(visit_start_date)-min(visit_start_date)) span_days
  FROM cdm.visit_occurrence GROUP BY person_id
)
SELECT pp.study, pp.person_id, v.n_visits, v.first_visit, v.last_visit, v.span_days, dx.concept_name AS disease
FROM pb_people pp
JOIN v ON v.person_id=pp.person_id AND v.n_visits>1
LEFT JOIN cdm.observation co ON co.person_id=pp.person_id AND co.observation_concept_id=4234469
LEFT JOIN cdm.concept dx ON dx.concept_id=co.value_as_concept_id
ORDER BY v.span_days DESC, v.n_visits DESC
LIMIT 12;
```
Returns — study, person_id, n_visits, first_visit, last_visit, span_days, disease -- one row per multi-visit contributor, ranked by longitudinal span:
```
 study  | person_id | n_visits | first_visit | last_visit | span_days |       disease       
--------+-----------+----------+-------------+------------+-----------+---------------------
 AMP-AD |       766 |        6 | 1899-12-02  | 1903-05-04 |      1248 | Alzheimer's disease
 AMP-AD |      1398 |        5 | 1900-01-01  | 1903-06-03 |      1248 | Other
 AMP-AD |       119 |        5 | 1900-01-01  | 1903-05-04 |      1218 | Normal
 AMP-AD |       378 |        5 | 1900-01-01  | 1903-05-04 |      1218 | 
 AMP-AD |      1095 |        5 | 1900-01-01  | 1903-05-04 |      1218 | Alzheimer's disease
 AMP-AD |       728 |        6 | 1899-12-02  | 1903-04-03 |      1217 | 
 AMP-AD |      1384 |        6 | 1899-12-02  | 1903-04-03 |      1217 | Alzheimer's disease
 AMP-AD |      1034 |        5 | 1900-01-01  | 1903-04-03 |      1187 | 
 AMP-AD |      2227 |        5 | 1900-01-01  | 1903-03-04 |      1157 | 
 AMP-AD |       591 |        6 | 1899-12-02  | 1903-02-01 |      1156 | 
 AMP-AD |      1289 |        6 | 1899-12-02  | 1903-01-02 |      1126 | 
 AMP-AD |      1521 |        6 | 1899-12-02  | 1903-01-02 |      1126 | Other
(12 rows)
```

**variation: time-point distribution** — For each dataset feeding pseudobulk files, how are contributing participants distributed across number of time points (how longitudinal is each program)?
```sql
WITH pb_people AS (
  SELECT DISTINCT f.study, s.person_id
  FROM cdm.files f
  JOIN cdm.assay_input_file aif ON aif.file_id=f.file_id
  JOIN cdm.assay a ON a.assay_id=aif.assay_id
  JOIN cdm.assay_to_specimen ats ON ats.assay_id=a.assay_id
  JOIN cdm.specimen s ON s.specimen_id=ats.specimen_id
  WHERE f.file_role='harmonized_output' AND f.file_format='HDF5' AND f.file_name ILIKE '%pseudobulk%'
),
v AS (SELECT person_id, count(*) n_visits FROM cdm.visit_occurrence GROUP BY person_id)
SELECT pp.study, v.n_visits AS time_points, count(DISTINCT pp.person_id) AS participants
FROM pb_people pp JOIN v ON v.person_id=pp.person_id
GROUP BY pp.study, v.n_visits
ORDER BY pp.study, v.n_visits;
```
Returns — study, time_points, participants -- histogram of visit counts; note AMP-CMD sits entirely at 1 time point (no progression), AMP-AD & AMP-RA-SLE spread across 2-6:
```
   study    | time_points | participants 
------------+-------------+--------------
 AMP-AD     |           1 |          151
 AMP-AD     |           2 |           61
 AMP-AD     |           3 |           96
 AMP-AD     |           4 |          115
 AMP-AD     |           5 |           83
 AMP-AD     |           6 |           19
 AMP-CMD    |           1 |           56
 AMP-RA-SLE |           1 |           11
 AMP-RA-SLE |           2 |           16
 AMP-RA-SLE |           3 |           34
 AMP-RA-SLE |           4 |           32
 AMP-RA-SLE |           5 |           20
 AMP-RA-SLE |           6 |            5
(13 rows)
```

**variation: disease progression cohorts** — For a progression study, how many multi-visit participants sit behind these pseudobulk files per disease, and what is their average longitudinal span?
```sql
WITH pb_people AS (
  SELECT DISTINCT f.study, s.person_id
  FROM cdm.files f
  JOIN cdm.assay_input_file aif ON aif.file_id=f.file_id
  JOIN cdm.assay a ON a.assay_id=aif.assay_id
  JOIN cdm.assay_to_specimen ats ON ats.assay_id=a.assay_id
  JOIN cdm.specimen s ON s.specimen_id=ats.specimen_id
  WHERE f.file_role='harmonized_output' AND f.file_format='HDF5' AND f.file_name ILIKE '%pseudobulk%'
),
v AS (SELECT person_id, count(*) n_visits,
        (max(visit_start_date)-min(visit_start_date)) span_days
      FROM cdm.visit_occurrence GROUP BY person_id)
SELECT pp.study, dx.concept_name AS disease,
       count(DISTINCT pp.person_id) AS multi_visit_participants,
       round(avg(v.span_days)::numeric,0) AS avg_span_days,
       max(v.n_visits) AS max_time_points
FROM pb_people pp
JOIN v ON v.person_id=pp.person_id AND v.n_visits>1
JOIN cdm.observation co ON co.person_id=pp.person_id AND co.observation_concept_id=4234469
JOIN cdm.concept dx ON dx.concept_id=co.value_as_concept_id
WHERE co.value_as_concept_id NOT IN (45884153,45878142,45882470,45877986)
GROUP BY pp.study, dx.concept_name
ORDER BY pp.study, multi_visit_participants DESC;
```
Returns — study, disease, multi_visit_participants, avg_span_days, max_time_points -- real-disease cohorts (status values 45884153/45878142/45882470/45877986 excluded) that have longitudinal support:
```
   study    |           disease            | multi_visit_participants | avg_span_days | max_time_points 
------------+------------------------------+--------------------------+---------------+-----------------
 AMP-AD     | Alzheimer's disease          |                       49 |           598 |               6
 AMP-RA-SLE | Systemic lupus erythematosus |                       46 |           518 |               6
 AMP-RA-SLE | Rheumatoid arthritis         |                       33 |           491 |               6
 AMP-RA-SLE | Vitiligo                     |                        2 |           579 |               4
 AMP-RA-SLE | Dermatomyositis              |                        1 |           183 |               2
(5 rows)
```

> **Coverage:** Coverage limits, all confirmed against the live CDM: (1) Only AMP-AD (10 files: RNA+ATAC x5 cell types) and AMP-RA-SLE (4 files: RNA x4 cell types) pseudobulk HDF5 files qualify -- their datasets carry multi-visit participants (127-169 and 107 longitudinal contributors respectively, up to 6 time points). (2) AMP-CMD's 4 pseudobulk HDF5 files (astrocyte, ependymal_cell, neuron, oligodendrocyte, hypothalamus) are correctly EXCLUDED by the base: all 56 contributors are single-visit (see variation 2, AMP-CMD sits entirely at 1 time point) and CMD carries NO 4234469 disease record -- it is a normal reference, unusable for progression. (3) AMP-PD contributes ZERO pseudobulk HDF5 files -- PD harmonized data is proteomics assay_matrix (parquet) only, no brain HDF5 -- so its study-arm longitudinal design cannot be reached through pseudobulk HDF5. (4) The `_matrix.hdf5` full single-cell matrices and `spatial_matrix.hdf5` are intentionally NOT matched (filter requires file_name ILIKE '%pseudobulk%'). (5) In variation 1 the disease column can show status values like 'Other' (value_as_concept 45878142) rather than a true disease; variation 3 filters those out (45884153/45878142/45882470/45877986). (6) All visit dates are synthetic, so span_days reflects the generated visit schedule, not real clinical follow-up.


### S7 — the catalog of all CDEs (clinical/demographic + biospecimen/assay metadata) behind the harmonization

**base** — List every clinical/demographic CDE instantiated in the CDM, with its landing table and participant coverage, so a bioinformatician can pick variables.
```sql
-- Every CDE instantiated = the distinct observation/measurement source values, with where it lands
-- and how many participants carry it. A CDE's PROGRAM and human DESCRIPTION are NOT in the CDM
-- (cdm.person is data-free, staging Study is empty) -- they live in inputs/cde_dictionary.jsonl,
-- keyed by amp_variable = the `cde` below (join it to attach program/description).
SELECT cde, landing_table, n_persons, n_rows FROM (
  SELECT observation_source_value AS cde, 'observation' AS landing_table,
         count(DISTINCT person_id) AS n_persons, count(*) AS n_rows
    FROM cdm.observation WHERE observation_source_value IS NOT NULL GROUP BY 1
  UNION ALL
  SELECT measurement_source_value, 'measurement',
         count(DISTINCT person_id), count(*)
    FROM cdm.measurement WHERE measurement_source_value IS NOT NULL GROUP BY 1) q
ORDER BY n_persons DESC, cde;
```
Returns — cde, landing_table, n_persons, n_rows (240 CDEs; head by coverage):
```
                     cde                     | landing_table | n_persons | n_rows 
---------------------------------------------+---------------+-----------+--------
 sex                                         | observation   |      2500 |   2500
 race                                        | observation   |      2297 |   2297
 participant_id                              | observation   |      1904 |   6667
 ethnicity                                   | observation   |      1539 |   1539
 age_at_baseline                             | observation   |      1364 |   1364
 alcohol_ever_used                           | observation   |      1364 |   1364
 caff_drinks_ever_used_regularly             | observation   |      1364 |   1364
 dat                                         | measurement   |      1364 |   4788
 datscan_visual_interpretation               | observation   |      1364 |   4788
 diagnosis_type                              | observation   |      1364 |   1364
 education_12years_complete                  | observation   |      1364 |   4788
 ess_info_source                             | measurement   |      1364 |   4788
…  (240 rows total)
```

**variation: biospecimen/assay metadata fields** — Beyond clinical CDEs, what biospecimen/assay metadata fields exist (with their controlled vocabularies) — the other family the story names? These ARE in the CDM.
```sql
SELECT 'specimen' AS entity, 'specimen_source_value' AS field, count(DISTINCT specimen_source_value) AS n_values, left(string_agg(DISTINCT specimen_source_value, ', '),70) AS examples FROM cdm.specimen
UNION ALL SELECT 'specimen','anatomic_site_source_value', count(DISTINCT anatomic_site_source_value), left(string_agg(DISTINCT anatomic_site_source_value,', '),70) FROM cdm.specimen
UNION ALL SELECT 'assay','assay_source_value', count(DISTINCT assay_source_value), left(string_agg(DISTINCT assay_source_value,', '),70) FROM cdm.assay
UNION ALL SELECT 'assay','platform', count(DISTINCT platform), left(string_agg(DISTINCT platform,', '),70) FROM cdm.assay
UNION ALL SELECT 'files','analysis_type', count(DISTINCT analysis_type), left(string_agg(DISTINCT analysis_type,', '),70) FROM cdm.files
UNION ALL SELECT 'files','cell_type', count(DISTINCT cell_type), left(string_agg(DISTINCT cell_type,', '),70) FROM cdm.files
UNION ALL SELECT 'files','biosample_type', count(DISTINCT biosample_type), left(string_agg(DISTINCT biosample_type,', '),70) FROM cdm.files;
```
Returns — entity, field, n_values, examples:
```
  entity  |           field            | n_values |                                examples                                
----------+----------------------------+----------+------------------------------------------------------------------------
 specimen | specimen_source_value      |       44 | ACC, CBE, DLPFC, Head of caudate nucleus, PBMCs, PCC, TCX, blood, caud
 specimen | anatomic_site_source_value |       11 | 18, 19, BA10, BA22, BA23, BA38, BA39, BA9, blood, hypothalamus, plasma
 assay    | assay_source_value         |        9 | 10x Multiome, CyTOF, Olink Explore HT, SomaLogic, Visium, bulkRNAseq, 
 assay    | platform                   |       20 | 10x Genomics, Chromium Controller, Illumina NovaSeq 6000, Eclipse, Exp
 files    | analysis_type              |        7 | ATAC, RNA, cytometry, metadata, proteomics, raw, spatial
 files    | cell_type                  |       99 | B cell, B cell of medullary sinus of lymph node, Bm5 B cell, CD14-posi
 files    | biosample_type             |       23 | PBMCs, blood, brain, cell line, hypothalamus, kidney biopsy, plasma, p
(7 rows)
```

**variation: CDE families summary** — How does the CDE universe split between the two landing tables, and what is the coverage range (near-universal vs sparse)?
```sql
SELECT landing_table, count(*) AS n_cdes, min(n_persons) AS min_coverage, max(n_persons) AS max_coverage FROM (
  SELECT observation_source_value AS cde, 'observation' AS landing_table, count(DISTINCT person_id) AS n_persons FROM cdm.observation WHERE observation_source_value IS NOT NULL GROUP BY 1
  UNION ALL SELECT measurement_source_value, 'measurement', count(DISTINCT person_id) FROM cdm.measurement WHERE measurement_source_value IS NOT NULL GROUP BY 1) q GROUP BY 1;
```
Returns — landing_table, n_cdes, min_coverage, max_coverage:
```
 landing_table | n_cdes | min_coverage | max_coverage 
---------------+--------+--------------+--------------
 measurement   |     71 |            1 |         1364
 observation   |    174 |          142 |         2500
(2 rows)
```

> **Coverage:** 240 CDEs are instantiated in the CDM (170 observation, 70 measurement). Program labels and human descriptions are NOT stored in the CDM — they live in `inputs/cde_dictionary.jsonl` (key `amp_variable`); the earlier version of this section embedded that file as a 240-row `VALUES` catalog, which is why it is now a pointer instead. Biospecimen/assay metadata fields (specimen/assay/files columns) ARE in the CDM and are shown above.


### S8 — the source-file → harmonization → output chains, for a replication study

**base** — What are the actual replication chains: which raw source files feed which assay, and which harmonized output does that assay produce?
```sql
SELECT src.study,
       src.file_name    AS source_file,
       src.file_format  AS src_fmt,
       a.assay_source_value AS assay,
       a.platform,
       harm.file_name   AS harmonized_output,
       harm.file_format AS out_fmt
FROM cdm.files src
JOIN cdm.assay a           ON a.assay_id = src.assay_id
JOIN cdm.assay_input_file aif ON aif.assay_id = a.assay_id
JOIN cdm.files harm        ON harm.file_id = aif.file_id AND harm.file_role='harmonized_output'
WHERE src.file_role='source_input'
ORDER BY src.study, harm.file_name, src.file_name
LIMIT 10;
```
Returns — study, source_file, src_fmt, assay, platform, harmonized_output, out_fmt -- one row per (raw source file -> assay -> harmonized output) chain:
```
 study  |               source_file               | src_fmt |    assay     |    platform     |              harmonized_output              | out_fmt 
--------+-----------------------------------------+---------+--------------+-----------------+---------------------------------------------+---------
 AMP-AD | AMP-AD_10xMultiome_10001901_R1.fastq.gz | fastq   | 10x Multiome | HiSeqX          | AMP-AD_ATAC_pseudobulk_GABAergic_neurons.h5 | HDF5
 AMP-AD | AMP-AD_10xMultiome_10001901_R2.fastq.gz | fastq   | 10x Multiome | HiSeqX          | AMP-AD_ATAC_pseudobulk_GABAergic_neurons.h5 | HDF5
 AMP-AD | AMP-AD_10xMultiome_10002701_R1.fastq.gz | fastq   | 10x Multiome | HiSeq2000       | AMP-AD_ATAC_pseudobulk_GABAergic_neurons.h5 | HDF5
 AMP-AD | AMP-AD_10xMultiome_10002701_R2.fastq.gz | fastq   | 10x Multiome | HiSeq2000       | AMP-AD_ATAC_pseudobulk_GABAergic_neurons.h5 | HDF5
 AMP-AD | AMP-AD_10xMultiome_10003002_R1.fastq.gz | fastq   | 10x Multiome | Q Exactive Plus | AMP-AD_ATAC_pseudobulk_GABAergic_neurons.h5 | HDF5
 AMP-AD | AMP-AD_10xMultiome_10003002_R2.fastq.gz | fastq   | 10x Multiome | Q Exactive Plus | AMP-AD_ATAC_pseudobulk_GABAergic_neurons.h5 | HDF5
 AMP-AD | AMP-AD_10xMultiome_10004801_R1.fastq.gz | fastq   | 10x Multiome | NovaSeq 6000    | AMP-AD_ATAC_pseudobulk_GABAergic_neurons.h5 | HDF5
 AMP-AD | AMP-AD_10xMultiome_10004801_R2.fastq.gz | fastq   | 10x Multiome | NovaSeq 6000    | AMP-AD_ATAC_pseudobulk_GABAergic_neurons.h5 | HDF5
 AMP-AD | AMP-AD_10xMultiome_10006801_R1.fastq.gz | fastq   | 10x Multiome | Lumos           | AMP-AD_ATAC_pseudobulk_GABAergic_neurons.h5 | HDF5
 AMP-AD | AMP-AD_10xMultiome_10006801_R2.fastq.gz | fastq   | 10x Multiome | Lumos           | AMP-AD_ATAC_pseudobulk_GABAergic_neurons.h5 | HDF5
(10 rows)
```

**variation: all source files for one chosen output** — For a single harmonized output (AMP-RA-SLE_RNA_pseudobulk_synovial_fibroblast.h5), what are ALL the raw source files that were harmonized into it, with their assay and size?
```sql
SELECT src.file_name    AS source_file,
       src.file_format  AS src_fmt,
       a.assay_source_value AS assay,
       a.platform,
       pg_size_pretty(src.file_size_bytes) AS source_size
FROM cdm.files harm
JOIN cdm.assay_input_file aif ON aif.file_id = harm.file_id
JOIN cdm.assay a           ON a.assay_id = aif.assay_id
JOIN cdm.files src         ON src.assay_id = a.assay_id AND src.file_role='source_input'
WHERE harm.file_name = 'AMP-RA-SLE_RNA_pseudobulk_synovial_fibroblast.h5'
ORDER BY src.file_name
LIMIT 12;
```
Returns — source_file, src_fmt, assay, platform, source_size -- every raw fastq that contributed to the one named harmonized output:
```
               source_file                | src_fmt |  assay   |                    platform                     | source_size 
------------------------------------------+---------+----------+-------------------------------------------------+-------------
 AMP-RA-SLE_scRNAseq_10000603_R1.fastq.gz | fastq   | scRNAseq | Chromium Controller, Illumina NovaSeq 6000      | 66 GB
 AMP-RA-SLE_scRNAseq_10000603_R2.fastq.gz | fastq   | scRNAseq | Chromium Controller, Illumina NovaSeq 6000      | 21 GB
 AMP-RA-SLE_scRNAseq_10000604_R1.fastq.gz | fastq   | scRNAseq | Chromium Controller, Illumina NovaSeq 6000      | 4224 MB
 AMP-RA-SLE_scRNAseq_10000604_R2.fastq.gz | fastq   | scRNAseq | Chromium Controller, Illumina NovaSeq 6000      | 14 GB
 AMP-RA-SLE_scRNAseq_10002206_R1.fastq.gz | fastq   | scRNAseq | Illumina HiSeq X Ten, Chromium Next GEM Chip G  | 59 GB
 AMP-RA-SLE_scRNAseq_10002206_R2.fastq.gz | fastq   | scRNAseq | Illumina HiSeq X Ten, Chromium Next GEM Chip G  | 60 GB
 AMP-RA-SLE_scRNAseq_10003706_R1.fastq.gz | fastq   | scRNAseq | Illumina HiSeq X Ten, Chromium Next GEM Chip G  | 84 GB
 AMP-RA-SLE_scRNAseq_10003706_R2.fastq.gz | fastq   | scRNAseq | Illumina HiSeq X Ten, Chromium Next GEM Chip G  | 77 GB
 AMP-RA-SLE_scRNAseq_10003711_R1.fastq.gz | fastq   | scRNAseq | Illumina NovaSeq 6000, Chromium Next GEM Chip G | 35 GB
 AMP-RA-SLE_scRNAseq_10003711_R2.fastq.gz | fastq   | scRNAseq | Illumina NovaSeq 6000, Chromium Next GEM Chip G | 38 GB
 AMP-RA-SLE_scRNAseq_10004305_R1.fastq.gz | fastq   | scRNAseq | unknown                                         | 13 GB
 AMP-RA-SLE_scRNAseq_10004305_R2.fastq.gz | fastq   | scRNAseq | unknown                                         | 56 GB
(12 rows)
```

**variation: chain summary + provenance size per output** — Per harmonized output, how many source files and assays feed it, and how does the output size compare to the total raw source volume that has to be re-processed to replicate it?
```sql
SELECT harm.study,
       harm.file_name AS harmonized_output,
       harm.analysis_type,
       count(DISTINCT src.file_id)          AS n_source_files,
       count(DISTINCT a.assay_id)           AS n_assays,
       pg_size_pretty(harm.file_size_bytes) AS output_size,
       pg_size_pretty(sum(src.file_size_bytes)) AS total_source_size
FROM cdm.files harm
JOIN cdm.assay_input_file aif ON aif.file_id = harm.file_id
JOIN cdm.assay a           ON a.assay_id = aif.assay_id
JOIN cdm.files src         ON src.assay_id = a.assay_id AND src.file_role='source_input'
WHERE harm.file_role='harmonized_output'
GROUP BY harm.file_id, harm.study, harm.file_name, harm.analysis_type, harm.file_size_bytes
ORDER BY harm.study, harm.file_name
LIMIT 12;
```
Returns — study, harmonized_output, analysis_type, n_source_files, n_assays, output_size, total_source_size -- one row per harmonized output with its provenance fan-in and raw-vs-derived volume:
```
  study  |                harmonized_output                | analysis_type | n_source_files | n_assays | output_size | total_source_size 
---------+-------------------------------------------------+---------------+----------------+----------+-------------+-------------------
 AMP-AD  | AMP-AD_ATAC_pseudobulk_GABAergic_neurons.h5     | ATAC          |            764 |      382 | 952 MB      | 31 TB
 AMP-AD  | AMP-AD_ATAC_pseudobulk_GLUtamatergic_neurons.h5 | ATAC          |            764 |      382 | 518 MB      | 31 TB
 AMP-AD  | AMP-AD_ATAC_pseudobulk_astrocytes.h5            | ATAC          |            764 |      382 | 933 MB      | 31 TB
 AMP-AD  | AMP-AD_ATAC_pseudobulk_microglia.h5             | ATAC          |            764 |      382 | 1060 MB     | 31 TB
 AMP-AD  | AMP-AD_ATAC_pseudobulk_oligodendrocyte.h5       | ATAC          |            764 |      382 | 1545 MB     | 31 TB
 AMP-AD  | AMP-AD_RNA_matrix.hdf5                          | RNA           |            200 |      200 | 2243 MB     | 8645 GB
 AMP-AD  | AMP-AD_RNA_pseudobulk_GABAergic_neurons.h5      | RNA           |           1038 |      519 | 808 MB      | 43 TB
 AMP-AD  | AMP-AD_RNA_pseudobulk_GLUtamatergic_neurons.h5  | RNA           |           1038 |      519 | 1614 MB     | 43 TB
 AMP-AD  | AMP-AD_RNA_pseudobulk_astrocytes.h5             | RNA           |           1038 |      519 | 2610 MB     | 43 TB
 AMP-AD  | AMP-AD_RNA_pseudobulk_microglia.h5              | RNA           |           1038 |      519 | 608 MB      | 43 TB
 AMP-AD  | AMP-AD_RNA_pseudobulk_oligodendrocyte.h5        | RNA           |           1038 |      519 | 1228 MB     | 43 TB
 AMP-CMD | AMP-CMD_RNA_matrix.hdf5                         | RNA           |             63 |       63 | 1636 MB     | 2634 GB
(12 rows)
```

**variation: contributor-disease cross-cut per output** — For AMP-RA-SLE harmonized outputs, which participant diseases contributed to each one (so a replication can be stratified by disease)?
```sql
SELECT harm.study,
       harm.file_name  AS harmonized_output,
       dx.concept_name AS contributor_disease,
       count(DISTINCT s.person_id) AS n_participants
FROM cdm.files harm
JOIN cdm.assay_input_file aif ON aif.file_id = harm.file_id
JOIN cdm.assay a           ON a.assay_id = aif.assay_id
JOIN cdm.assay_to_specimen ats ON ats.assay_id = a.assay_id
JOIN cdm.specimen s        ON s.specimen_id = ats.specimen_id
JOIN cdm.observation co    ON co.person_id = s.person_id AND co.observation_concept_id = 4234469
JOIN cdm.concept dx        ON dx.concept_id = co.value_as_concept_id
WHERE harm.file_role='harmonized_output'
  AND co.value_as_concept_id NOT IN (45884153,45878142,45882470,45877986)
  AND harm.study='AMP-RA-SLE'
GROUP BY harm.study, harm.file_name, dx.concept_name
ORDER BY harm.file_name, n_participants DESC
LIMIT 12;
```
Returns — study, harmonized_output, contributor_disease, n_participants -- disease composition of the cohort behind each RA-SLE harmonized output:
```
   study    |          harmonized_output          |     contributor_disease      | n_participants 
------------+-------------------------------------+------------------------------+----------------
 AMP-RA-SLE | AMP-RA-SLE_RNA_matrix.hdf5          | Systemic lupus erythematosus |             36
 AMP-RA-SLE | AMP-RA-SLE_RNA_matrix.hdf5          | Rheumatoid arthritis         |             22
 AMP-RA-SLE | AMP-RA-SLE_RNA_matrix.hdf5          | Vitiligo                     |              2
 AMP-RA-SLE | AMP-RA-SLE_RNA_matrix.hdf5          | Dermatomyositis              |              1
 AMP-RA-SLE | AMP-RA-SLE_RNA_pseudobulk_B_cell.h5 | Systemic lupus erythematosus |             51
 AMP-RA-SLE | AMP-RA-SLE_RNA_pseudobulk_B_cell.h5 | Rheumatoid arthritis         |             36
 AMP-RA-SLE | AMP-RA-SLE_RNA_pseudobulk_B_cell.h5 | Vitiligo                     |              3
 AMP-RA-SLE | AMP-RA-SLE_RNA_pseudobulk_B_cell.h5 | Dermatomyositis              |              1
 AMP-RA-SLE | AMP-RA-SLE_RNA_pseudobulk_T_cell.h5 | Systemic lupus erythematosus |             51
 AMP-RA-SLE | AMP-RA-SLE_RNA_pseudobulk_T_cell.h5 | Rheumatoid arthritis         |             36
 AMP-RA-SLE | AMP-RA-SLE_RNA_pseudobulk_T_cell.h5 | Vitiligo                     |              3
 AMP-RA-SLE | AMP-RA-SLE_RNA_pseudobulk_T_cell.h5 | Dermatomyositis              |              1
(12 rows)
```

> **Coverage:** Coverage of the replication chain is complete for the 3 single-cell programs but has structural holes: (1) All 23 harmonized_output files DO have full source->assay->output chains (AMP-AD=11, AMP-CMD=5, AMP-RA-SLE=7). (2) AMP-PD has NO harmonized_output and NO source_input files at all -- its only derived artifact is AMP-PD_proteomics_matrix.parquet, which carries file_role='assay_matrix' (not harmonized_output) and has no raw fastq behind it, so PD produces zero replication chains here (consistent with 'PD is proteomics assay_matrix only, no brain HDF5'). (3) The two proteomics matrices (AMP-PD and AMP-RA-SLE, both role='assay_matrix') likewise have no source_input files and never appear in a source->harmonized chain. (4) Source files are all raw (file_format fastq/fcs, analysis_type='raw'); no intermediate BAM/count-matrix stages are modeled between raw source and harmonized output, so the chain is exactly 2 hops. (5) The disease cross-cut (variation 3) only works for AMP-RA-SLE and AMP-AD (Alzheimer's only); AMP-CMD carries no 4234469 disease record (hypothalamus normal reference), so restricting that query to CMD returns 0 rows -- do not stratify CMD outputs by disease. (6) All file_size_bytes are synthetic; total_source_size is a straight sum of per-file fastq sizes (each source file maps to exactly one assay, so no double counting). Non-ASCII disease names (Sjogren's) may render oddly in the pasted sample above but are correct in the DB.


### S9 — source files by type and size, to estimate the compute cost of a custom pipeline

**base** — What source data files exist, by file type, with counts and min/max/total sizes to estimate compute cost?
```sql
SELECT
  file_format,
  count(*)                             AS n_files,
  pg_size_pretty(min(file_size_bytes)) AS min_size,
  pg_size_pretty(max(file_size_bytes)) AS max_size,
  pg_size_pretty(round(avg(file_size_bytes))::bigint) AS avg_size,
  pg_size_pretty(sum(file_size_bytes)) AS total_size,
  sum(file_size_bytes)                 AS total_bytes
FROM cdm.files
WHERE file_role='source_input'
GROUP BY file_format
ORDER BY sum(file_size_bytes) DESC;
```
Returns — file_format, n_files, min_size, max_size, avg_size, total_size (pretty), total_bytes (raw):
```
 file_format | n_files | min_size | max_size | avg_size | total_size |   total_bytes   
-------------+---------+----------+----------+----------+------------+-----------------
 fastq       |    2475 | 1937 MB  | 84 GB    | 42 GB    | 102 TB     | 112145816814388
 fcs         |      74 | 53 MB    | 381 MB   | 212 MB   | 15 GB      |     16478899731
(2 rows)
```

**variation: per program** — How do source files and their sizes break down per AMP program (and format) so I can budget compute per study?
```sql
SELECT
  study                                AS program,
  file_format,
  count(*)                             AS n_files,
  pg_size_pretty(min(file_size_bytes)) AS min_size,
  pg_size_pretty(max(file_size_bytes)) AS max_size,
  pg_size_pretty(sum(file_size_bytes)) AS total_size,
  sum(file_size_bytes)                 AS total_bytes
FROM cdm.files
WHERE file_role='source_input'
GROUP BY study, file_format
ORDER BY sum(file_size_bytes) DESC;
```
Returns — program (study), file_format, n_files, min_size, max_size, total_size (pretty), total_bytes (raw):
```
  program   | file_format | n_files | min_size | max_size | total_size |  total_bytes   
------------+-------------+---------+----------+----------+------------+----------------
 AMP-AD     | fastq       |    1640 | 1985 MB  | 84 GB    | 68 TB      | 74786964493746
 AMP-RA-SLE | fastq       |     660 | 2482 MB  | 84 GB    | 27 TB      | 29411505949731
 AMP-CMD    | fastq       |     175 | 1937 MB  | 84 GB    | 7402 GB    |  7947346370911
 AMP-RA-SLE | fcs         |      74 | 53 MB    | 381 MB   | 15 GB      |    16478899731
(4 rows)
```

**variation: per assay type + platform** — What is the file count and size footprint per assay type and sequencing platform (the real driver of pipeline choice/runtime)?
```sql
SELECT
  a.assay_source_value                 AS assay_type,
  a.platform,
  f.file_format,
  count(*)                             AS n_files,
  pg_size_pretty(min(f.file_size_bytes)) AS min_size,
  pg_size_pretty(max(f.file_size_bytes)) AS max_size,
  pg_size_pretty(sum(f.file_size_bytes)) AS total_size,
  sum(f.file_size_bytes)               AS total_bytes
FROM cdm.files f
JOIN cdm.assay a ON a.assay_id = f.assay_id
WHERE f.file_role='source_input'
GROUP BY a.assay_source_value, a.platform, f.file_format
ORDER BY sum(f.file_size_bytes) DESC;
```
Returns — assay_type, platform, file_format, n_files, min_size, max_size, total_size (pretty), total_bytes (raw):
```
  assay_type  |       platform        | file_format | n_files | min_size | max_size | total_size |  total_bytes   
--------------+-----------------------+-------------+---------+----------+----------+------------+----------------
 snRNAseq     | HiSeq2000             | fastq       |     598 | 1937 MB  | 84 GB    | 25 TB      | 27298001324607
 scRNAseq     | HiSeq2000             | fastq       |     474 | 2482 MB  | 84 GB    | 20 TB      | 21953222401330
 snATACseq    | HiSeq2000             | fastq       |     390 | 2018 MB  | 83 GB    | 17 TB      | 18269279803480
 bulkRNAseq   | HiSeq2000             | fastq       |     328 | 2165 MB  | 84 GB    | 13 TB      | 14766700344881
 10x Multiome | HiSeq2000             | fastq       |     332 | 2087 MB  | 84 GB    | 13 TB      | 14355834091607
 Visium       | HiSeq2000             | fastq       |     200 | 2799 MB  | 84 GB    | 8364 GB    |  8981272989340
 snRNAseq     | Illumina NovaSeq 6000 | fastq       |      40 | 4447 MB  | 81 GB    | 1679 GB    |  1802891731829
 scRNAseq     | Illumina NovaSeq 6000 | fastq       |      32 | 5094 MB  | 84 GB    | 1343 GB    |  1442525314587
 10x Multiome | Illumina NovaSeq 6000 | fastq       |      30 | 2286 MB  | 83 GB    | 1257 GB    |  1349383555854
 bulkRNAseq   | Illumina NovaSeq 6000 | fastq       |      25 | 2672 MB  | 83 GB    | 1003 GB    |  1077062606520
 Visium       | Illumina NovaSeq 6000 | fastq       |      14 | 2919 MB  | 83 GB    | 417 GB     |   447356650173
 snATACseq    | Illumina NovaSeq 6000 | fastq       |      12 | 2644 MB  | 81 GB    | 375 GB     |   402286000180
…  (14 rows total)
```

**variation: per assay type rollup + share of bytes** — Which assay types dominate total storage/compute? Rollup per assay type with average per-file size and percent of total source bytes.
```sql
SELECT
  a.assay_source_value                 AS assay_type,
  count(*)                             AS n_files,
  pg_size_pretty(round(avg(f.file_size_bytes))::bigint) AS avg_per_file,
  pg_size_pretty(sum(f.file_size_bytes)) AS total_size,
  round(100.0*sum(f.file_size_bytes)/sum(sum(f.file_size_bytes)) OVER (),1) AS pct_of_bytes
FROM cdm.files f
JOIN cdm.assay a ON a.assay_id = f.assay_id
WHERE f.file_role='source_input'
GROUP BY a.assay_source_value
ORDER BY sum(f.file_size_bytes) DESC;
```
Returns — assay_type, n_files, avg_per_file (pretty), total_size (pretty), pct_of_bytes (share of all source bytes):
```
  assay_type  | n_files | avg_per_file | total_size | pct_of_bytes 
--------------+---------+--------------+------------+--------------
 snRNAseq     |     638 | 42 GB        | 26 TB      |         25.9
 scRNAseq     |     506 | 43 GB        | 21 TB      |         20.9
 snATACseq    |     402 | 43 GB        | 17 TB      |         16.6
 bulkRNAseq   |     353 | 42 GB        | 14 TB      |         14.1
 10x Multiome |     362 | 40 GB        | 14 TB      |         14.0
 Visium       |     214 | 41 GB        | 8781 GB    |          8.4
 CyTOF        |      74 | 212 MB       | 15 GB      |          0.0
(7 rows)
```

> **Coverage:** Scope is source (raw) files only: file_role='source_input' (2549 files), which is exactly what a bioinformatician sizing input compute needs. All 2549 have non-null file_size_bytes, file_format, and a scalar assay_id (0 orphans), so the assay join loses nothing. Two formats only: fastq (2475, ~102 TB) and fcs (74, ~15 GB) -- sizes are synthetic/fabricated but internally coherent. Harmonized_output (23 HDF5/fcs) and assay_matrix (2 parquet) files are intentionally EXCLUDED because they are pipeline OUTPUTS, not source inputs; note harmonized files carry files.assay_id=NULL and would need the assay_input_file M:N join instead. Per-program view: AMP-AD dominates fastq (68 TB), AMP-CMD is fastq-only (no fcs), AMP-PD has no source fastq/fcs here (PD is proteomics assay_matrix only), and only AMP-RA-SLE contributes fcs (CyTOF). Platform split is just two sequencers (HiSeq2000 dominant, Illumina NovaSeq 6000 minority); avg fastq per-file (~40-43 GB) is fabricated and uniform across assay types, so per-assay totals track file counts more than true biological size differences.


### S10 — what other data exists on the scRNA individuals, to find the multi-omics subset

**base** — Which individuals have scRNAseq harmonized data, and what set of modalities (source + harmonized) does each one carry?
```sql
WITH person_file AS (
  SELECT s.person_id, f.file_id, f.file_role, f.analysis_type, f.file_format, f.study
  FROM cdm.specimen s
  JOIN cdm.assay_to_specimen ats ON ats.specimen_id=s.specimen_id
  JOIN cdm.assay a ON a.assay_id=ats.assay_id
  JOIN cdm.files f ON f.assay_id=a.assay_id
  UNION
  SELECT s.person_id, f.file_id, f.file_role, f.analysis_type, f.file_format, f.study
  FROM cdm.specimen s
  JOIN cdm.assay_to_specimen ats ON ats.specimen_id=s.specimen_id
  JOIN cdm.assay a ON a.assay_id=ats.assay_id
  JOIN cdm.assay_input_file aif ON aif.assay_id=a.assay_id
  JOIN cdm.files f ON f.file_id=aif.file_id
),
labeled AS (
  SELECT person_id, study, file_id,
    CASE WHEN file_role='source_input' THEN 'source:'||file_format
         WHEN file_role='assay_matrix' THEN analysis_type||'(matrix)'
         ELSE analysis_type END AS modality
  FROM person_file
),
rna_cohort AS (SELECT DISTINCT person_id FROM labeled WHERE modality='RNA')
SELECT l.person_id, max(l.study) AS study,
       array_agg(DISTINCT l.modality ORDER BY l.modality) AS modalities,
       count(DISTINCT l.file_id) AS n_files
FROM labeled l JOIN rna_cohort r ON r.person_id=l.person_id
GROUP BY l.person_id
ORDER BY cardinality(array_agg(DISTINCT l.modality)) DESC, l.person_id
LIMIT 12;
```
Returns — person_id, study, modalities (text[] of distinct modality labels), n_files (distinct files reachable for that person). 780 individuals total; richest first.:
```
 person_id |   study    |                             modalities                             | n_files 
-----------+------------+--------------------------------------------------------------------+---------
       120 | AMP-RA-SLE | {RNA,cytometry,proteomics(matrix),source:fastq,source:fcs,spatial} |       8
       632 | AMP-RA-SLE | {RNA,cytometry,proteomics(matrix),source:fastq,source:fcs,spatial} |      14
      1247 | AMP-RA-SLE | {RNA,cytometry,proteomics(matrix),source:fastq,source:fcs,spatial} |      20
      1641 | AMP-RA-SLE | {RNA,cytometry,proteomics(matrix),source:fastq,source:fcs,spatial} |      14
      1677 | AMP-RA-SLE | {RNA,cytometry,proteomics(matrix),source:fastq,source:fcs,spatial} |      16
      1914 | AMP-RA-SLE | {RNA,cytometry,proteomics(matrix),source:fastq,source:fcs,spatial} |      16
      1962 | AMP-RA-SLE | {RNA,cytometry,proteomics(matrix),source:fastq,source:fcs,spatial} |      18
      2072 | AMP-RA-SLE | {RNA,cytometry,proteomics(matrix),source:fastq,source:fcs,spatial} |      18
         6 | AMP-RA-SLE | {RNA,cytometry,proteomics(matrix),source:fastq,source:fcs}         |      15
        22 | AMP-RA-SLE | {RNA,cytometry,source:fastq,source:fcs,spatial}                    |      16
        37 | AMP-RA-SLE | {RNA,cytometry,source:fastq,source:fcs,spatial}                    |      20
        49 | AMP-RA-SLE | {RNA,cytometry,proteomics(matrix),source:fastq,source:fcs}         |      15
(12 rows)
```

**variation: modality combinations and how many individuals** — Which distinct modality combinations occur across the scRNA-harmonized cohort, and how many individuals fall into each?
```sql
WITH person_file AS (
  SELECT s.person_id, f.file_role, f.analysis_type, f.file_format, f.study
  FROM cdm.specimen s
  JOIN cdm.assay_to_specimen ats ON ats.specimen_id=s.specimen_id
  JOIN cdm.assay a ON a.assay_id=ats.assay_id
  JOIN cdm.files f ON f.assay_id=a.assay_id
  UNION
  SELECT s.person_id, f.file_role, f.analysis_type, f.file_format, f.study
  FROM cdm.specimen s
  JOIN cdm.assay_to_specimen ats ON ats.specimen_id=s.specimen_id
  JOIN cdm.assay a ON a.assay_id=ats.assay_id
  JOIN cdm.assay_input_file aif ON aif.assay_id=a.assay_id
  JOIN cdm.files f ON f.file_id=aif.file_id
),
labeled AS (
  SELECT person_id,
    CASE WHEN file_role='source_input' THEN 'source:'||file_format
         WHEN file_role='assay_matrix' THEN analysis_type||'(matrix)'
         ELSE analysis_type END AS modality
  FROM person_file
),
rna_cohort AS (SELECT DISTINCT person_id FROM labeled WHERE modality='RNA'),
per_person AS (
  SELECT l.person_id, array_agg(DISTINCT l.modality ORDER BY l.modality) AS modality_set
  FROM labeled l JOIN rna_cohort r ON r.person_id=l.person_id
  GROUP BY l.person_id
)
SELECT modality_set, cardinality(modality_set) AS n_modalities, count(*) AS n_individuals
FROM per_person
GROUP BY modality_set
ORDER BY n_individuals DESC, n_modalities DESC;
```
Returns — modality_set (text[]), n_modalities, n_individuals. 9 combinations; 420 are single-omic (RNA + its raw fastq only), the other 360 are multi-omic.:
```
                            modality_set                            | n_modalities | n_individuals 
--------------------------------------------------------------------+--------------+---------------
 {RNA,source:fastq}                                                 |            2 |           420
 {ATAC,RNA,source:fastq}                                            |            3 |           250
 {RNA,proteomics(matrix),source:fastq}                              |            3 |            28
 {RNA,source:fastq,spatial}                                         |            3 |            22
 {RNA,proteomics(matrix),source:fastq,spatial}                      |            4 |            16
 {RNA,cytometry,source:fastq,source:fcs}                            |            4 |            14
 {RNA,cytometry,source:fastq,source:fcs,spatial}                    |            5 |            11
 {RNA,cytometry,proteomics(matrix),source:fastq,source:fcs}         |            5 |            11
 {RNA,cytometry,proteomics(matrix),source:fastq,source:fcs,spatial} |            6 |             8
(9 rows)
```

**variation: true multi-omic subset with extra omics + disease** — For the individuals who have scRNA PLUS at least one other harmonized/matrix omic, what are the extra omics and their disease?
```sql
WITH person_file AS (
  SELECT s.person_id, f.file_role, f.analysis_type, f.file_format, f.study
  FROM cdm.specimen s
  JOIN cdm.assay_to_specimen ats ON ats.specimen_id=s.specimen_id
  JOIN cdm.assay a ON a.assay_id=ats.assay_id
  JOIN cdm.files f ON f.assay_id=a.assay_id
  UNION
  SELECT s.person_id, f.file_role, f.analysis_type, f.file_format, f.study
  FROM cdm.specimen s
  JOIN cdm.assay_to_specimen ats ON ats.specimen_id=s.specimen_id
  JOIN cdm.assay a ON a.assay_id=ats.assay_id
  JOIN cdm.assay_input_file aif ON aif.assay_id=a.assay_id
  JOIN cdm.files f ON f.file_id=aif.file_id
),
rna_cohort AS (SELECT DISTINCT person_id FROM person_file WHERE file_role='harmonized_output' AND analysis_type='RNA'),
other_omics AS (
  SELECT pf.person_id, max(pf.study) AS study,
    array_agg(DISTINCT CASE WHEN pf.file_role='assay_matrix' THEN pf.analysis_type||'(matrix)' ELSE pf.analysis_type END) AS extra_omics
  FROM person_file pf JOIN rna_cohort r ON r.person_id=pf.person_id
  WHERE pf.file_role IN ('harmonized_output','assay_matrix') AND pf.analysis_type<>'RNA'
  GROUP BY pf.person_id
)
SELECT o.person_id, o.study, o.extra_omics,
  COALESCE(dx.concept_name,'(none)') AS disease
FROM other_omics o
LEFT JOIN cdm.observation co ON co.person_id=o.person_id AND co.observation_concept_id=4234469
  AND co.value_as_concept_id NOT IN (45884153,45878142,45882470,45877986)
LEFT JOIN cdm.concept dx ON dx.concept_id=co.value_as_concept_id
ORDER BY cardinality(o.extra_omics) DESC, o.person_id
LIMIT 12;
```
Returns — person_id, study, extra_omics (harmonized/matrix omics beyond RNA), disease. Only individuals with >=1 extra omic (the actionable multi-omic subset); AMP-AD members carry {ATAC}.:
```
 person_id |   study    |              extra_omics               |           disease            
-----------+------------+----------------------------------------+------------------------------
       120 | AMP-RA-SLE | {cytometry,proteomics(matrix),spatial} | Systemic lupus erythematosus
       632 | AMP-RA-SLE | {cytometry,proteomics(matrix),spatial} | Rheumatoid arthritis
      1247 | AMP-RA-SLE | {cytometry,proteomics(matrix),spatial} | Rheumatoid arthritis
      1641 | AMP-RA-SLE | {cytometry,proteomics(matrix),spatial} | (none)
      1677 | AMP-RA-SLE | {cytometry,proteomics(matrix),spatial} | Rheumatoid arthritis
      1914 | AMP-RA-SLE | {cytometry,proteomics(matrix),spatial} | (none)
      1962 | AMP-RA-SLE | {cytometry,proteomics(matrix),spatial} | Rheumatoid arthritis
      2072 | AMP-RA-SLE | {cytometry,proteomics(matrix),spatial} | Rheumatoid arthritis
         6 | AMP-RA-SLE | {cytometry,proteomics(matrix)}         | (none)
        22 | AMP-RA-SLE | {cytometry,spatial}                    | Rheumatoid arthritis
        37 | AMP-RA-SLE | {cytometry,spatial}                    | (none)
        49 | AMP-RA-SLE | {cytometry,proteomics(matrix)}         | Systemic lupus erythematosus
(12 rows)
```

**variation: program-level extra-modality landscape** — Which program contributes which extra modalities on top of scRNA, and to how many individuals?
```sql
WITH person_file AS (
  SELECT s.person_id, f.file_role, f.analysis_type, f.study
  FROM cdm.specimen s
  JOIN cdm.assay_to_specimen ats ON ats.specimen_id=s.specimen_id
  JOIN cdm.assay a ON a.assay_id=ats.assay_id
  JOIN cdm.files f ON f.assay_id=a.assay_id
  UNION
  SELECT s.person_id, f.file_role, f.analysis_type, f.study
  FROM cdm.specimen s
  JOIN cdm.assay_to_specimen ats ON ats.specimen_id=s.specimen_id
  JOIN cdm.assay a ON a.assay_id=ats.assay_id
  JOIN cdm.assay_input_file aif ON aif.assay_id=a.assay_id
  JOIN cdm.files f ON f.file_id=aif.file_id
),
rna_cohort AS (SELECT DISTINCT person_id, study FROM person_file WHERE file_role='harmonized_output' AND analysis_type='RNA')
SELECT r.study,
  count(DISTINCT r.person_id) AS rna_individuals,
  count(DISTINCT pf.person_id) FILTER (WHERE pf.analysis_type='ATAC')       AS with_atac,
  count(DISTINCT pf.person_id) FILTER (WHERE pf.analysis_type='spatial')    AS with_spatial,
  count(DISTINCT pf.person_id) FILTER (WHERE pf.analysis_type='cytometry')  AS with_cytometry,
  count(DISTINCT pf.person_id) FILTER (WHERE pf.analysis_type='proteomics') AS with_proteomics
FROM rna_cohort r
LEFT JOIN person_file pf ON pf.person_id=r.person_id AND pf.file_role IN ('harmonized_output','assay_matrix') AND pf.analysis_type<>'RNA'
GROUP BY r.study
ORDER BY rna_individuals DESC;
```
Returns — study, rna_individuals, and per-modality individual counts (with_atac/spatial/cytometry/proteomics). Shows AMP-AD = RNA+ATAC depth, AMP-RA-SLE = the rich multi-omic program, AMP-CMD = RNA-only.:
```
   study    | rna_individuals | with_atac | with_spatial | with_cytometry | with_proteomics 
------------+-----------------+-----------+--------------+----------------+-----------------
 AMP-AD     |             521 |       250 |            0 |              0 |               0
 AMP-RA-SLE |             140 |         0 |           57 |             44 |              63
 AMP-CMD    |             119 |         0 |            0 |              0 |               0
(3 rows)
```

> **Coverage:** Cohort = 780 individuals whose specimens feed a harmonized RNA (scRNA) HDF5 output, reached by the unified person->specimen->assay_to_specimen->assay->file path (source files via scalar files.assay_id, harmonized/assay_matrix files via assay_input_file M:N). Coverage notes: (1) Every RNA-cohort person also carries source:fastq (the raw input that produced the RNA/ATAC), so 'RNA + source:fastq' is effectively single-omic, not a second omic; only harmonized/assay_matrix analysis_types other than RNA (ATAC, spatial, cytometry, proteomics-matrix) count as true additional omics in variations 2-3. (2) By program: AMP-AD RNA people pair only with ATAC (250 of 521); AMP-CMD RNA people are strictly RNA-only (hypothalamus normal reference, no other omics AND no 4234469 disease record by design); AMP-RA-SLE supplies all the deep multi-omic stacks (spatial 57, cytometry 44, proteomics-matrix 63). (3) proteomics(matrix) here is AMP-RA-SLE only -- the AMP-PD proteomics assay_matrix links to PD participants who have NO scRNA harmonized data, so PD never enters this cohort. (4) Some RA-SLE multi-omic individuals show disease '(none)': they are cases (qualifier 'Admitting diagnosis') whose disease value_as_concept_id is NULL or an excluded status value ('Not applicable' 45882470), not controls; excluded status codes are 45884153/45878142/45882470/45877986. (5) No condition_occurrence table exists; disease is the observation 4234469 record joined to cdm.concept.


### S11 — the multi-omic subset, to ask which signature distinguishes disease from healthy

**base** — Who are the multi-omic individuals (both RNA and ATAC harmonized data), what is each one's diagnosis, and how many RNA/ATAC files back them?
```sql
WITH multiomic AS (
  SELECT s.person_id,
         count(DISTINCT CASE WHEN f.analysis_type='RNA'  THEN f.file_id END) AS n_rna,
         count(DISTINCT CASE WHEN f.analysis_type='ATAC' THEN f.file_id END) AS n_atac
  FROM cdm.files f
  JOIN cdm.assay_input_file aif ON aif.file_id=f.file_id
  JOIN cdm.assay a ON a.assay_id=aif.assay_id
  JOIN cdm.assay_to_specimen ats ON ats.assay_id=a.assay_id
  JOIN cdm.specimen s ON s.specimen_id=ats.specimen_id
  WHERE f.file_role='harmonized_output' AND f.analysis_type IN ('RNA','ATAC')
  GROUP BY s.person_id
  HAVING count(DISTINCT CASE WHEN f.analysis_type='RNA'  THEN f.file_id END) > 0
     AND count(DISTINCT CASE WHEN f.analysis_type='ATAC' THEN f.file_id END) > 0
)
SELECT m.person_id,
       dx.concept_name AS diagnosis,
       CASE WHEN co.qualifier_concept_id=1989833  THEN 'case'
            WHEN co.qualifier_concept_id=44804027 THEN 'control'
            ELSE 'unspecified' END AS group_label,
       m.n_rna, m.n_atac
FROM multiomic m
JOIN cdm.observation co ON co.person_id=m.person_id AND co.observation_concept_id=4234469
JOIN cdm.concept dx ON dx.concept_id=co.value_as_concept_id
ORDER BY group_label, m.person_id
LIMIT 12;
```
Returns — person_id, diagnosis, group_label (case/control/unspecified), n_rna (RNA file count), n_atac (ATAC file count) -- one row per multi-omic individual (250 total):
```
 person_id |      diagnosis      | group_label | n_rna | n_atac 
-----------+---------------------+-------------+-------+--------
        68 | Alzheimer's disease | case        |     5 |      5
       193 | Alzheimer's disease | case        |     5 |      5
       232 | Alzheimer's disease | case        |     1 |      5
       453 | Alzheimer's disease | case        |     6 |      5
       689 | Alzheimer's disease | case        |     5 |      5
       952 | Alzheimer's disease | case        |     5 |      5
       974 | Alzheimer's disease | case        |     1 |      5
      1000 | Alzheimer's disease | case        |     6 |      5
      1020 | Alzheimer's disease | case        |     5 |      5
      1097 | Alzheimer's disease | case        |     5 |      5
      1138 | Alzheimer's disease | case        |     5 |      5
      1369 | Alzheimer's disease | case        |     5 |      5
(12 rows)
```

**variation: case vs control split** — How does the multi-omic subset split into disease cases vs healthy controls (the two arms of a disease-vs-healthy signature contrast)?
```sql
WITH multiomic AS (
  SELECT s.person_id
  FROM cdm.files f
  JOIN cdm.assay_input_file aif ON aif.file_id=f.file_id
  JOIN cdm.assay a ON a.assay_id=aif.assay_id
  JOIN cdm.assay_to_specimen ats ON ats.assay_id=a.assay_id
  JOIN cdm.specimen s ON s.specimen_id=ats.specimen_id
  WHERE f.file_role='harmonized_output' AND f.analysis_type IN ('RNA','ATAC')
  GROUP BY s.person_id
  HAVING count(DISTINCT CASE WHEN f.analysis_type='RNA'  THEN f.file_id END) > 0
     AND count(DISTINCT CASE WHEN f.analysis_type='ATAC' THEN f.file_id END) > 0
)
SELECT CASE WHEN co.qualifier_concept_id=1989833  THEN 'case (disease)'
            WHEN co.qualifier_concept_id=44804027 THEN 'control (healthy)'
            ELSE 'unspecified status' END AS group_label,
       dx.concept_name AS diagnosis,
       count(DISTINCT m.person_id) AS n_individuals
FROM multiomic m
JOIN cdm.observation co ON co.person_id=m.person_id AND co.observation_concept_id=4234469
JOIN cdm.concept dx ON dx.concept_id=co.value_as_concept_id
GROUP BY group_label, dx.concept_name
ORDER BY n_individuals DESC;
```
Returns — group_label (case/control/unspecified), diagnosis, n_individuals -- the analyzable contrast is 68 AD cases vs 41 healthy controls:
```
    group_label     |      diagnosis      | n_individuals 
--------------------+---------------------+---------------
 unspecified status | Other               |           113
 case (disease)     | Alzheimer's disease |            32
 control (healthy)  | Normal              |            29
(3 rows)
```

**variation: RNA/ATAC file inventory** — Which harmonized RNA and ATAC matrices back the multi-omic comparison, per cell type, with format, size, and contributor count?
```sql
SELECT f.analysis_type,
       coalesce(nullif(f.cell_type,''),'(bulk matrix)') AS cell_type,
       f.file_name,
       f.file_format,
       round(f.file_size_bytes/1024.0/1024,1) AS size_mb,
       count(DISTINCT s.person_id) AS n_contributors
FROM cdm.files f
JOIN cdm.assay_input_file aif ON aif.file_id=f.file_id
JOIN cdm.assay a ON a.assay_id=aif.assay_id
JOIN cdm.assay_to_specimen ats ON ats.assay_id=a.assay_id
JOIN cdm.specimen s ON s.specimen_id=ats.specimen_id
WHERE f.file_role='harmonized_output' AND f.analysis_type IN ('RNA','ATAC') AND f.study='AMP-AD'
GROUP BY f.analysis_type, f.cell_type, f.file_name, f.file_format, f.file_size_bytes
ORDER BY f.analysis_type, f.file_name;
```
Returns — analysis_type, cell_type, file_name, file_format, size_mb, n_contributors -- the 5 ATAC + 6 RNA pseudobulk/bulk HDF5 matrices (paired per cell type) that a biologist downloads for the contrast:
```
 analysis_type |       cell_type       |                    file_name                    | file_format | size_mb | n_contributors 
---------------+-----------------------+-------------------------------------------------+-------------+---------+----------------
 ATAC          | GABAergic neurons     | AMP-AD_ATAC_pseudobulk_GABAergic_neurons.h5     | HDF5        |   952.0 |            330
 ATAC          | GLUtamatergic neurons | AMP-AD_ATAC_pseudobulk_GLUtamatergic_neurons.h5 | HDF5        |   517.9 |            330
 ATAC          | astrocytes            | AMP-AD_ATAC_pseudobulk_astrocytes.h5            | HDF5        |   933.3 |            330
 ATAC          | microglia             | AMP-AD_ATAC_pseudobulk_microglia.h5             | HDF5        |  1060.2 |            330
 ATAC          | oligodendrocyte       | AMP-AD_ATAC_pseudobulk_oligodendrocyte.h5       | HDF5        |  1545.5 |            330
 RNA           | (bulk matrix)         | AMP-AD_RNA_matrix.hdf5                          | HDF5        |  2242.5 |            182
 RNA           | GABAergic neurons     | AMP-AD_RNA_pseudobulk_GABAergic_neurons.h5      | HDF5        |   807.9 |            420
 RNA           | GLUtamatergic neurons | AMP-AD_RNA_pseudobulk_GLUtamatergic_neurons.h5  | HDF5        |  1613.6 |            420
 RNA           | astrocytes            | AMP-AD_RNA_pseudobulk_astrocytes.h5             | HDF5        |  2609.8 |            420
 RNA           | microglia             | AMP-AD_RNA_pseudobulk_microglia.h5              | HDF5        |   607.7 |            420
 RNA           | oligodendrocyte       | AMP-AD_RNA_pseudobulk_oligodendrocyte.h5        | HDF5        |  1228.3 |            420
(11 rows)
```

**variation: sex cross-cut** — Within the multi-omic case vs control arms, how do individuals break down by sex (a covariate a signature analysis must adjust for)?
```sql
WITH multiomic AS (
  SELECT s.person_id
  FROM cdm.files f
  JOIN cdm.assay_input_file aif ON aif.file_id=f.file_id
  JOIN cdm.assay a ON a.assay_id=aif.assay_id
  JOIN cdm.assay_to_specimen ats ON ats.assay_id=a.assay_id
  JOIN cdm.specimen s ON s.specimen_id=ats.specimen_id
  WHERE f.file_role='harmonized_output' AND f.analysis_type IN ('RNA','ATAC')
  GROUP BY s.person_id
  HAVING count(DISTINCT CASE WHEN f.analysis_type='RNA'  THEN f.file_id END) > 0
     AND count(DISTINCT CASE WHEN f.analysis_type='ATAC' THEN f.file_id END) > 0
)
SELECT CASE WHEN co.qualifier_concept_id=1989833  THEN 'case (disease)'
            WHEN co.qualifier_concept_id=44804027 THEN 'control (healthy)'
            ELSE 'unspecified status' END AS group_label,
       coalesce(sx.concept_name,'(no sex record)') AS sex,
       count(DISTINCT m.person_id) AS n_individuals
FROM multiomic m
JOIN cdm.observation co ON co.person_id=m.person_id AND co.observation_concept_id=4234469
LEFT JOIN cdm.observation so ON so.person_id=m.person_id AND so.observation_source_value='sex'
LEFT JOIN cdm.concept sx ON sx.concept_id=so.value_as_concept_id
GROUP BY group_label, sx.concept_name
ORDER BY group_label, n_individuals DESC;
```
Returns — group_label (case/control/unspecified), sex (MALE/FEMALE/Unknown/no sex record; from the harmonized sex observation, value_as_concept_id 8507/8532), n_individuals:
```
    group_label     |       sex       | n_individuals 
--------------------+-----------------+---------------
 case (disease)     | (no sex record) |            21
 case (disease)     | FEMALE          |             9
 case (disease)     | MALE            |             2
 control (healthy)  | (no sex record) |            22
 control (healthy)  | FEMALE          |             4
 control (healthy)  | MALE            |             3
 unspecified status | (no sex record) |            93
 unspecified status | FEMALE          |            11
 unspecified status | MALE            |             9
(9 rows)
```

> **Coverage:** The multi-omic (RNA+ATAC harmonized) subset exists ONLY in AMP-AD: 250 individuals who contributed to at least one RNA and one ATAC harmonized matrix. No other program has ATAC harmonized data, so PD/CMD/RA-SLE cannot appear here. The disease-vs-healthy contrast is therefore Alzheimer's disease only -- the analyzable arms are 68 AD cases (qualifier 1989833 'Admitting diagnosis') vs 41 healthy controls (qualifier 44804027 'Control group' / value 'Normal'). A large majority of the subset (141 of 250) carries a non-disease STATUS instead of a clean case/control label -- 138 'Other', 3 'Not applicable' -- and is bucketed as 'unspecified'; these are unusable for the signature contrast without additional clinical fields. Sex is now recorded for the full multi-omic subset via the harmonized `sex` observation (concept 3046965 -> MALE/FEMALE), so sex-adjusted analysis is supported across both the case and control arms. Note the file-inventory contributor counts (330 ATAC, 420 RNA per pseudobulk matrix) exceed the 250 both-omic individuals because each harmonized matrix also aggregates RNA-only or ATAC-only donors; the 250 figure is the intersection who have BOTH modalities.


### S12 — which scRNAseq datasets were generated on 10x Multiome, to find the paired ATAC

**base** — Which scRNAseq harmonized datasets were generated on the 10x Multiome platform, and what is the corresponding ATACseq dataset on the same specimens?
```sql
WITH mm AS (
  SELECT DISTINCT f.file_id, f.file_name, f.analysis_type, f.cell_type, f.file_size_bytes
  FROM cdm.files f
  JOIN cdm.assay_input_file aif ON aif.file_id=f.file_id
  JOIN cdm.assay a ON a.assay_id=aif.assay_id
  WHERE a.assay_source_value='10x Multiome' AND f.file_role='harmonized_output'
),
shared AS (
  SELECT f.cell_type, count(DISTINCT ats.specimen_id) AS shared_specimens
  FROM cdm.files f
  JOIN cdm.assay_input_file aif ON aif.file_id=f.file_id
  JOIN cdm.assay a ON a.assay_id=aif.assay_id
  JOIN cdm.assay_to_specimen ats ON ats.assay_id=a.assay_id
  WHERE a.assay_source_value='10x Multiome' AND f.file_role='harmonized_output' AND f.analysis_type='RNA'
  GROUP BY f.cell_type
)
SELECT rna.cell_type,
       rna.file_name AS scrnaseq_dataset, pg_size_pretty(rna.file_size_bytes) AS rna_size,
       atac.file_name AS matching_atacseq_dataset, pg_size_pretty(atac.file_size_bytes) AS atac_size,
       sh.shared_specimens
FROM mm rna
JOIN mm atac ON atac.cell_type=rna.cell_type AND atac.analysis_type='ATAC'
JOIN shared sh ON sh.cell_type=rna.cell_type
WHERE rna.analysis_type='RNA'
ORDER BY rna.cell_type;
```
Returns — cell_type, scrnaseq_dataset, rna_size, matching_atacseq_dataset, atac_size, shared_specimens:
```
       cell_type       |                scrnaseq_dataset                | rna_size |            matching_atacseq_dataset             | atac_size | shared_specimens 
-----------------------+------------------------------------------------+----------+-------------------------------------------------+-----------+------------------
 GABAergic neurons     | AMP-AD_RNA_pseudobulk_GABAergic_neurons.h5     | 808 MB   | AMP-AD_ATAC_pseudobulk_GABAergic_neurons.h5     | 952 MB    |              181
 GLUtamatergic neurons | AMP-AD_RNA_pseudobulk_GLUtamatergic_neurons.h5 | 1614 MB  | AMP-AD_ATAC_pseudobulk_GLUtamatergic_neurons.h5 | 518 MB    |              181
 astrocytes            | AMP-AD_RNA_pseudobulk_astrocytes.h5            | 2610 MB  | AMP-AD_ATAC_pseudobulk_astrocytes.h5            | 933 MB    |              181
 microglia             | AMP-AD_RNA_pseudobulk_microglia.h5             | 608 MB   | AMP-AD_ATAC_pseudobulk_microglia.h5             | 1060 MB   |              181
 oligodendrocyte       | AMP-AD_RNA_pseudobulk_oligodendrocyte.h5       | 1228 MB  | AMP-AD_ATAC_pseudobulk_oligodendrocyte.h5       | 1545 MB   |              181
(5 rows)
```

**variation: Multiome specimen roster (the specimens to find ATAC on)** — What are the actual specimens (person, anatomic site, sequencing platform, disease) that underlie the 10x Multiome datasets, so I can locate the matching ATAC on those same specimens?
```sql
SELECT ats.specimen_id, s.person_id, s.specimen_source_value, s.anatomic_site_source_value AS anatomic_site,
       a.platform, dx.concept_name AS disease
FROM cdm.assay a
JOIN cdm.assay_to_specimen ats ON ats.assay_id=a.assay_id
JOIN cdm.specimen s ON s.specimen_id=ats.specimen_id
LEFT JOIN cdm.observation co ON co.person_id=s.person_id AND co.observation_concept_id=4234469
LEFT JOIN cdm.concept dx ON dx.concept_id=co.value_as_concept_id
WHERE a.assay_source_value='10x Multiome'
ORDER BY ats.specimen_id
LIMIT 12;
```
Returns — specimen_id, person_id, specimen_source_value, anatomic_site, platform, disease:
```
 specimen_id | person_id |     specimen_source_value      | anatomic_site |       platform        |       disease       
-------------+-----------+--------------------------------+---------------+-----------------------+---------------------
    10001901 |        19 | DLPFC                          | BA22          | HiSeqX                | 
    10002701 |        27 | dorsolateral prefrontal cortex | BA9           | HiSeq2000             | 
    10003002 |        30 | superior temporal gyrus        | BA9           | Q Exactive Plus       | 
    10004801 |        48 | serum                          | serum         | NovaSeq 6000          | Other
    10006801 |        68 | cerebellum                     | BA22          | Lumos                 | Alzheimer's disease
    10014702 |       147 | dorsolateral prefrontal cortex | BA9           | NovaSeq 6000          | Other
    10014703 |       147 | dorsolateral prefrontal cortex | BA23          | HiSeq2000             | Other
    10016101 |       161 | dorsolateral prefrontal cortex | BA9           | HiSeq2000             | Other
    10017101 |       171 | prefrontal cortex              | BA9           | HiSeq2000             | Normal
    10017303 |       173 | dorsolateral prefrontal cortex | BA22          | Illumina NovaSeq 6000 | Other
    10017702 |       177 | prefrontal cortex              | BA9           | HiSeq2000             | Other
    10018701 |       187 | dorsolateral prefrontal cortex | BA22          | HiSeqX                | Other
(12 rows)
```

**variation: files per Multiome specimen (RNA and ATAC)** — For each 10x Multiome specimen, which RNA and ATAC harmonized files exist (confirming matched modalities per cell type)?
```sql
SELECT ats.specimen_id, s.person_id,
       count(*) FILTER (WHERE f.analysis_type='RNA')  AS rna_files,
       count(*) FILTER (WHERE f.analysis_type='ATAC') AS atac_files,
       array_agg(DISTINCT f.cell_type ORDER BY f.cell_type) AS cell_types
FROM cdm.assay a
JOIN cdm.assay_to_specimen ats ON ats.assay_id=a.assay_id
JOIN cdm.specimen s ON s.specimen_id=ats.specimen_id
JOIN cdm.assay_input_file aif ON aif.assay_id=a.assay_id
JOIN cdm.files f ON f.file_id=aif.file_id AND f.file_role='harmonized_output'
WHERE a.assay_source_value='10x Multiome'
GROUP BY ats.specimen_id, s.person_id
ORDER BY ats.specimen_id
LIMIT 12;
```
Returns — specimen_id, person_id, rna_files, atac_files, cell_types[]:
```
 specimen_id | person_id | rna_files | atac_files |                                     cell_types                                     
-------------+-----------+-----------+------------+------------------------------------------------------------------------------------
    10001901 |        19 |         5 |          5 | {"GABAergic neurons","GLUtamatergic neurons",astrocytes,microglia,oligodendrocyte}
    10002701 |        27 |         5 |          5 | {"GABAergic neurons","GLUtamatergic neurons",astrocytes,microglia,oligodendrocyte}
    10003002 |        30 |         5 |          5 | {"GABAergic neurons","GLUtamatergic neurons",astrocytes,microglia,oligodendrocyte}
    10004801 |        48 |         5 |          5 | {"GABAergic neurons","GLUtamatergic neurons",astrocytes,microglia,oligodendrocyte}
    10006801 |        68 |         5 |          5 | {"GABAergic neurons","GLUtamatergic neurons",astrocytes,microglia,oligodendrocyte}
    10014702 |       147 |         5 |          5 | {"GABAergic neurons","GLUtamatergic neurons",astrocytes,microglia,oligodendrocyte}
    10014703 |       147 |         5 |          5 | {"GABAergic neurons","GLUtamatergic neurons",astrocytes,microglia,oligodendrocyte}
    10016101 |       161 |         5 |          5 | {"GABAergic neurons","GLUtamatergic neurons",astrocytes,microglia,oligodendrocyte}
    10017101 |       171 |         5 |          5 | {"GABAergic neurons","GLUtamatergic neurons",astrocytes,microglia,oligodendrocyte}
    10017303 |       173 |         5 |          5 | {"GABAergic neurons","GLUtamatergic neurons",astrocytes,microglia,oligodendrocyte}
    10017702 |       177 |         5 |          5 | {"GABAergic neurons","GLUtamatergic neurons",astrocytes,microglia,oligodendrocyte}
    10018701 |       187 |         5 |          5 | {"GABAergic neurons","GLUtamatergic neurons",astrocytes,microglia,oligodendrocyte}
(12 rows)
```

**variation: Multiome coverage by sequencing platform** — How do the 10x Multiome specimens and their RNA vs ATAC datasets break down by sequencing platform?
```sql
SELECT a.platform,
       count(DISTINCT ats.specimen_id) AS multiome_specimens,
       count(DISTINCT f.file_id) FILTER (WHERE f.analysis_type='RNA')  AS rna_datasets,
       count(DISTINCT f.file_id) FILTER (WHERE f.analysis_type='ATAC') AS atac_datasets
FROM cdm.assay a
JOIN cdm.assay_to_specimen ats ON ats.assay_id=a.assay_id
JOIN cdm.assay_input_file aif ON aif.assay_id=a.assay_id
JOIN cdm.files f ON f.file_id=aif.file_id AND f.file_role='harmonized_output'
WHERE a.assay_source_value='10x Multiome'
GROUP BY a.platform
ORDER BY multiome_specimens DESC;
```
Returns — platform, multiome_specimens, rna_datasets, atac_datasets:
```
       platform        | multiome_specimens | rna_datasets | atac_datasets 
-----------------------+--------------------+--------------+---------------
 HiSeq2000             |                 64 |            5 |             5
 IlluminaNovaseq6000   |                 25 |            5 |             5
 Illumina NovaSeq 6000 |                 19 |            5 |             5
 HiSeqX                |                 13 |            5 |             5
 NovaSeq 6000          |                 12 |            5 |             5
 HiSeq2500             |                 12 |            5 |             5
 Lumos                 |                  8 |            5 |             5
 Q Extrative Plus      |                  5 |            5 |             5
 Q Exactive Plus       |                  5 |            5 |             5
 10x Genomics          |                  5 |            5 |             5
 OrbiTrap Fusion       |                  4 |            5 |             5
 Eclipse               |                  2 |            5 |             5
 Q Exactive HF         |                  2 |            5 |             5
 Q Exactive HF-X       |                  2 |            5 |             5
 Exploris 240          |                  2 |            5 |             5
 HiSeq4000             |                  1 |            5 |             5
(16 rows)
```

> **Coverage:** 10x Multiome exists ONLY in AMP-AD (181 assays = 181 specimens; 166 on HiSeq2000, 15 on NovaSeq). Its harmonized outputs are pseudobulk-per-cell-type HDF5 files: exactly 10 distinct files = 5 cell types (astrocytes, GABAergic neurons, GLUtamatergic neurons, microglia, oligodendrocyte) x 2 modalities (RNA, ATAC). Because they are pseudobulk, each of the 10 files aggregates ALL 181 Multiome specimens (assay_input_file is M:N and every specimen links to every file) -- so 'files per specimen' is uniform (5 RNA + 5 ATAC each) and the RNA<->ATAC 'same specimens' relationship is the shared 181-specimen roster, not distinct per-specimen files. The RNA modality is tagged analysis_type='RNA' (single-cell/single-nucleus Multiome), not a separate 'scRNAseq' label; pairing to the ATAC counterpart is done on cell_type. Disease on these specimens is AMP-AD only: Alzheimer's disease, plus Normal/Other status values (no other disease programs run 10x Multiome). Specimen anatomic_site is frequently 'NA' or 'blood'; specimen_source_value carries the brain-region text.


### S13 — individuals with scRNA + ATAC from the same specimen, split by Dx vs control

**base** — Which individuals have joint scRNAseq + ATACseq from the SAME specimen, crossed by specimen, cell types, specimen source, and Dx vs control?
```sql
WITH mspec AS (
  SELECT DISTINCT s.specimen_id, s.person_id, s.specimen_source_value, s.anatomic_site_source_value, a.assay_id
  FROM cdm.assay a
  JOIN cdm.assay_to_specimen ats ON ats.assay_id=a.assay_id
  JOIN cdm.specimen s ON s.specimen_id=ats.specimen_id
  WHERE a.assay_source_value='10x Multiome'
)
SELECT m.person_id, m.specimen_id, m.specimen_source_value AS specimen_source,
       count(DISTINCT hf.file_id) FILTER (WHERE hf.analysis_type='RNA')  AS rna_hdf5,
       count(DISTINCT hf.file_id) FILTER (WHERE hf.analysis_type='ATAC') AS atac_hdf5,
       count(DISTINCT hf.cell_type) AS n_cell_types,
       string_agg(DISTINCT hf.cell_type, ', ' ORDER BY hf.cell_type) AS cell_types,
       dx.concept_name AS dx,
       CASE co.qualifier_concept_id WHEN 44804027 THEN 'control' WHEN 1989833 THEN 'case' ELSE 'other/status' END AS dx_role
FROM mspec m
JOIN cdm.assay_input_file aif ON aif.assay_id=m.assay_id
JOIN cdm.files hf ON hf.file_id=aif.file_id AND hf.file_role='harmonized_output'
LEFT JOIN cdm.observation co ON co.person_id=m.person_id AND co.observation_concept_id=4234469
LEFT JOIN cdm.concept dx ON dx.concept_id=co.value_as_concept_id
GROUP BY m.person_id, m.specimen_id, m.specimen_source_value, dx.concept_name, co.qualifier_concept_id
ORDER BY dx_role, m.person_id
LIMIT 12;
```
Returns — person_id, specimen_id, specimen_source, rna_hdf5 (count), atac_hdf5 (count), n_cell_types, cell_types, dx, dx_role -- one row per individual x Multiome specimen:
```
 person_id | specimen_id |        specimen_source         | rna_hdf5 | atac_hdf5 | n_cell_types |                                    cell_types                                    |         dx          | dx_role 
-----------+-------------+--------------------------------+----------+-----------+--------------+----------------------------------------------------------------------------------+---------------------+---------
        68 |    10006801 | cerebellum                     |        5 |         5 |            5 | GABAergic neurons, GLUtamatergic neurons, astrocytes, microglia, oligodendrocyte | Alzheimer's disease | case
       193 |    10019302 | temporal cortex                |        5 |         5 |            5 | GABAergic neurons, GLUtamatergic neurons, astrocytes, microglia, oligodendrocyte | Alzheimer's disease | case
       453 |    10045302 | superior temporal gyrus        |        5 |         5 |            5 | GABAergic neurons, GLUtamatergic neurons, astrocytes, microglia, oligodendrocyte | Alzheimer's disease | case
       689 |    10068901 | prefrontal cortex              |        5 |         5 |            5 | GABAergic neurons, GLUtamatergic neurons, astrocytes, microglia, oligodendrocyte | Alzheimer's disease | case
       952 |    10095202 | posterior cingulate cortex     |        5 |         5 |            5 | GABAergic neurons, GLUtamatergic neurons, astrocytes, microglia, oligodendrocyte | Alzheimer's disease | case
      1000 |    10100001 | prefrontal cortex              |        5 |         5 |            5 | GABAergic neurons, GLUtamatergic neurons, astrocytes, microglia, oligodendrocyte | Alzheimer's disease | case
      1020 |    10102003 | prefrontal cortex              |        5 |         5 |            5 | GABAergic neurons, GLUtamatergic neurons, astrocytes, microglia, oligodendrocyte | Alzheimer's disease | case
      1138 |    10113802 | superior temporal gyrus        |        5 |         5 |            5 | GABAergic neurons, GLUtamatergic neurons, astrocytes, microglia, oligodendrocyte | Alzheimer's disease | case
      1138 |    10113803 | prefrontal cortex              |        5 |         5 |            5 | GABAergic neurons, GLUtamatergic neurons, astrocytes, microglia, oligodendrocyte | Alzheimer's disease | case
      1369 |    10136902 | prefrontal cortex              |        5 |         5 |            5 | GABAergic neurons, GLUtamatergic neurons, astrocytes, microglia, oligodendrocyte | Alzheimer's disease | case
      1383 |    10138301 | frontal cortex                 |        5 |         5 |            5 | GABAergic neurons, GLUtamatergic neurons, astrocytes, microglia, oligodendrocyte | Alzheimer's disease | case
      1508 |    10150801 | dorsolateral prefrontal cortex |        5 |         5 |            5 | GABAergic neurons, GLUtamatergic neurons, astrocytes, microglia, oligodendrocyte | Alzheimer's disease | case
(12 rows)
```

**variation: by cell type** — For each cell type, is there a paired RNA + ATAC harmonized matrix, and how many individuals (Dx cases vs controls) contribute?
```sql
SELECT hf.cell_type,
       count(DISTINCT hf.file_id) FILTER (WHERE hf.analysis_type='RNA')  AS rna_hdf5,
       count(DISTINCT hf.file_id) FILTER (WHERE hf.analysis_type='ATAC') AS atac_hdf5,
       count(DISTINCT s.person_id) AS n_persons,
       count(DISTINCT s.person_id) FILTER (WHERE co.qualifier_concept_id=1989833 AND dx.concept_name='Alzheimer''s disease') AS n_ad_case,
       count(DISTINCT s.person_id) FILTER (WHERE co.qualifier_concept_id=44804027) AS n_control
FROM cdm.assay a
JOIN cdm.assay_to_specimen ats ON ats.assay_id=a.assay_id
JOIN cdm.specimen s ON s.specimen_id=ats.specimen_id
JOIN cdm.assay_input_file aif ON aif.assay_id=a.assay_id
JOIN cdm.files hf ON hf.file_id=aif.file_id AND hf.file_role='harmonized_output'
LEFT JOIN cdm.observation co ON co.person_id=s.person_id AND co.observation_concept_id=4234469
LEFT JOIN cdm.concept dx ON dx.concept_id=co.value_as_concept_id
WHERE a.assay_source_value='10x Multiome'
GROUP BY hf.cell_type ORDER BY hf.cell_type;
```
Returns — cell_type, rna_hdf5, atac_hdf5, n_persons, n_ad_case, n_control -- one row per cell type; each has a paired RNA+ATAC matrix:
```
       cell_type       | rna_hdf5 | atac_hdf5 | n_persons | n_ad_case | n_control 
-----------------------+----------+-----------+-----------+-----------+-----------
 GABAergic neurons     |        1 |         1 |       173 |        19 |        16
 GLUtamatergic neurons |        1 |         1 |       173 |        19 |        16
 astrocytes            |        1 |         1 |       173 |        19 |        16
 microglia             |        1 |         1 |       173 |        19 |        16
 oligodendrocyte       |        1 |         1 |       173 |        19 |        16
(5 rows)
```

**variation: by specimen source** — Across which specimen sources do individuals have joint Multiome (RNA+ATAC), and how do Dx cases vs controls distribute per source?
```sql
SELECT s.specimen_source_value AS specimen_source,
       count(DISTINCT s.person_id)   AS n_persons,
       count(DISTINCT s.specimen_id) AS n_specimens,
       count(DISTINCT s.person_id) FILTER (WHERE co.qualifier_concept_id=1989833 AND dx.concept_name='Alzheimer''s disease') AS n_ad_case,
       count(DISTINCT s.person_id) FILTER (WHERE co.qualifier_concept_id=44804027) AS n_control,
       count(DISTINCT s.person_id) FILTER (WHERE dx.concept_name IN ('Other','Not applicable')) AS n_other_status
FROM cdm.assay a
JOIN cdm.assay_to_specimen ats ON ats.assay_id=a.assay_id
JOIN cdm.specimen s ON s.specimen_id=ats.specimen_id
LEFT JOIN cdm.observation co ON co.person_id=s.person_id AND co.observation_concept_id=4234469
LEFT JOIN cdm.concept dx ON dx.concept_id=co.value_as_concept_id
WHERE a.assay_source_value='10x Multiome'
GROUP BY s.specimen_source_value ORDER BY n_persons DESC;
```
Returns — specimen_source, n_persons, n_specimens, n_ad_case, n_control, n_other_status -- one row per Multiome specimen source:
```
        specimen_source         | n_persons | n_specimens | n_ad_case | n_control | n_other_status 
--------------------------------+-----------+-------------+-----------+-----------+----------------
 dorsolateral prefrontal cortex |        64 |          65 |         6 |         6 |             34
 prefrontal cortex              |        27 |          27 |         7 |         5 |              7
 superior temporal gyrus        |        20 |          21 |         3 |         0 |             12
 temporal cortex                |        12 |          12 |         1 |         0 |              4
 parahippocampal gyrus          |         7 |           7 |         0 |         0 |              5
 DLPFC                          |         6 |           6 |         0 |         0 |              3
 Head of caudate nucleus        |         6 |           6 |         1 |         0 |              3
 posterior cingulate cortex     |         6 |           6 |         1 |         1 |              2
 frontal pole                   |         5 |           5 |         0 |         2 |              1
 caudate nucleus                |         5 |           5 |         1 |         0 |              2
 ACC                            |         4 |           4 |         0 |         0 |              1
 blood                          |         4 |           4 |         0 |         0 |              3
 cerebellum                     |         4 |           4 |         1 |         1 |              1
 serum                          |         4 |           4 |         0 |         0 |              3
 frontal cortex                 |         2 |           2 |         1 |         0 |              1
 inferior frontal gyrus         |         2 |           2 |         0 |         1 |              1
 PCC                            |         1 |           1 |         0 |         0 |              1
(17 rows)
```

> **Coverage:** Joint scRNAseq+ATACseq "from the same specimen" exists ONLY as the 10x Multiome assay (181 assays / 181 specimens / 173 individuals). Verified: no specimen in the CDM links two separate assays (a scRNAseq assay and a snATACseq assay never share a specimen_id) -- every specimen maps to exactly one assay type. Multiome is the intended same-specimen paired RNA+ATAC modality: each Multiome specimen's assay yields both RNA and ATAC HDF5 harmonized output (confirmed 5 RNA + 5 ATAC distinct matrices reachable per specimen). If a user literally expects two physically distinct assays sharing one specimen_id, that does not exist. Cell-type resolution exists only for the AMP-AD study: all 173 Multiome individuals route to AMP-AD harmonized output with 5 cell types (astrocytes, GABAergic neurons, GLUtamatergic neurons, microglia, oligodendrocyte). The harmonized matrices are cohort-aggregated pseudobulk -- there are only 10 distinct harmonized files total (5 cell types x {RNA,ATAC}), each pooling all 173 individuals -- so the cell-type set is uniform across individuals, not per-specimen-variable (hence the by-cell-type variation shows identical 173/49/22 counts per cell type). Dx vs control: the clean contrast is Alzheimer's disease (49 cases, qualifier 1989833) vs Normal (22 controls, qualifier 44804027); the majority (100 individuals) carry a non-specific dx='Other' and 2 'Not applicable' status -- these are not true controls. Specimen sources include non-brain blood/serum Multiome specimens (34 individuals) alongside the biologically expected brain regions (DLPFC dominant at 109); the blood/serum Multiome pairings are a synthetic-data artifact. No same-specimen RNA+ATAC exists for AMP-PD (proteomics assay_matrix only, no brain HDF5), AMP-CMD (single-modality hypothalamus, no disease record), or standalone AMP-RA-SLE outside the AMP-AD harmonized pool.

## Beta-2 additions (2026-09-03): file records and standard-concept specimen lineage

**All files a participant is in — one query, per the file_name-as-observation contract (ask 7).**
Every file a donor contributed to (their own raw files AND the cohort-level harmonized
products) carries one observation row under that donor; the event fields point at cdm.files.

```sql
SELECT o.person_id, f.file_name, f.file_role, o.qualifier_source_value AS assay_modality
FROM cdm.observation o
JOIN cdm.files f ON f.file_id = o.observation_event_id
WHERE o.observation_concept_id = 4303445           -- 'Research data collection'
  AND o.obs_event_field_concept_id = 2000000001    -- 'files.file_id' (SysBio field concept)
  AND o.person_id = 1247
ORDER BY f.file_name;
```

**Specimen derivation lineage — standard concepts end to end.** A derivation is one
measurement row (concept 1176306 'Unique identifier of Initial sample'): its event fields
point at the CHILD specimen (field concept 1147049 'specimen.specimen_id'), its
value_source_value carries the parent's id, and fact_relationship reinforces the link to the
PARENT with the standard pair 32668/32669 (Measurement to Specimen / reverse). Parent of a
given specimen:

```sql
SELECT m.measurement_event_id AS child_specimen_id,
       fr.fact_id_2           AS parent_specimen_id
FROM cdm.measurement m
JOIN cdm.fact_relationship fr
  ON fr.domain_concept_id_1 = 21 AND fr.fact_id_1 = m.measurement_id
 AND fr.domain_concept_id_2 = 36 AND fr.relationship_concept_id = 32668
WHERE m.measurement_concept_id = 1176306
  AND m.measurement_event_id = 10000603;          -- the child specimen you hold
```

> Design note (2026-09-03): specimen lineage moved off the non-standard 32554/32553
> 'Sub-specimen of' pair onto this measurement-based pattern, which uses only Standard
> concepts. Sensitive content is NOT restricted to the observation table by policy:
> measurement is governed identically (measurement_access + RLS), which is what the access
> tables are for.
