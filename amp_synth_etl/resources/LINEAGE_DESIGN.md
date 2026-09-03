# Lineage design — why links look the way they do

This note explains and defends the three record-linkage mechanisms in the synthetic CDM.
All three follow one principle: **every concept in a linkage chain is either a Standard OMOP
concept or a declared local field concept in OMOP's reserved 2-billion range — nothing in
between.** Off-label vocabulary is never used.

## 1. Specimen derivation: measurement-mediated, standard concepts end to end

A derived specimen (an aliquot, a sub-sample, an autopsy derivative) is linked to its parent
through one `cdm.measurement` row per derivation:

```
measurement_concept_id      = 1176306   'Unique identifier [Identifier] of Initial sample' (LOINC, Standard)
value_source_value          = <parent specimen id>          -- states the initial/parent sample
measurement_event_id        = <child specimen id>           -- CDM event-linkage pair:
meas_event_field_concept_id = 1147049   'specimen.specimen_id' (CDM vocabulary, Standard)
```

reinforced through `cdm.fact_relationship` to the parent with the **standard**
Measurement↔Specimen pair:

```
(21, measurement_id, 36, parent_specimen_id, 32668)   -- 'Measurement to Specimen'
(36, parent_specimen_id, 21, measurement_id, 32669)   -- 'Specimen to Measurement'
```

**Why not a direct specimen↔specimen fact_relationship row?** Because no Standard
relationship concept exists for it. The Relationship vocabulary contains exactly ten Standard
concepts (verified against vocabulary release 2026.2): Measurement↔Specimen (32668/32669),
Observation↔Measurement (581410/581411), Parent↔Child Measurement (581436/581437),
Diastolic↔Systolic BP (46233682/46233683), and Relevant-condition (46233684/46233685). The
`fact_relationship` convention requires a Standard relationship concept; the seemingly natural
'Sub-specimen of' pair (32554/32553) is non-standard SNOMED-Vet vocabulary machinery whose
home is `concept_relationship`, not record linkage. An earlier draft used it; this design
replaced it. The measurement route is the only specimen-lineage pattern that is compliant at
every hop: a Standard measurement concept, a Standard CDM field concept, and the one
relationship pair OHDSI actually blessed for specimen linkage.

**Why measurement and not observation?** It has been suggested that sensitive content be
confined to the observation table. That restriction is neither feasible nor desirable here.
The measurement table is the semantically correct home for an identifier *measurement* about a
sample, and OMOP's own vocabulary agrees — 1176306 is a Measurement-domain concept, and
32668/32669 exist specifically to tie measurements to specimens. Sensitivity is not managed by
table choice: **every governed table (measurement and observation alike) carries a per-record
access table and row-level security**, and a row's visibility follows its access-group grants
regardless of which table holds it. The CDM is restrictive enough without additional arbitrary
constraints; the access layer exists precisely so that governance and table semantics stay
independent concerns.

## 2. File records: observation rows with the CDM event-linkage pair

Per the Beta-2 data contract, every data file yields one `cdm.observation` row **per (file,
donor)**: concept 4303445 'Research data collection' (Standard, uniform so retrieval is a
single equality), qualifier 1091809 'Molecular biology report Document' marking omics content
with the assay modality in `qualifier_source_value`, the file name in `value_as_string`, and
the event pair `observation_event_id → files.file_id` with `obs_event_field_concept_id =
2000000001` — a declared local Field concept ('files.file_id', SysBio vocabulary). `files` is
an extension table, so no CDM-vocabulary field concept exists for it; the 2-billion range is
OMOP's reserved local-extension space, and table/field-defining concepts are the one category
of local minting this project permits. Donors of cohort-level products (harmonized matrices,
pseudobulk outputs) resolve through `assay_input_file` → contributing assays → specimen
owners, so every participant carries a record for every file they are in — one query returns
a participant's complete file footprint (see the query cookbook).

The `files` table holds **data files only**: dictionaries, protocols, templates, READMEs,
codebooks, manifests and changelogs are excluded at emission by an enforced guard.

## 3. Assay and visit linkage

Assay↔specimen and assay↔file links are dedicated join tables (`assay_to_specimen`,
`assay_input_file`) — self-describing, foreign-key enforced, requiring no relationship
vocabulary at all. Visit linkage rides `(person_id, visit_source_value)` with bare visit
names, per the data contract's masking rules.
