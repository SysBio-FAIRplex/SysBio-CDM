# Lineage design — current implementation

This document defines the three record-linkage mechanisms in the SysBio CDM as they stand now, with
the reason for each. It is the binding design reference for the real build (`amp_real_etl`, for
AMP-PD PDRD, 692 participants, and AMP-CMD Kidney, 77 donors). It states the current design only.
How the design got here, and what each ruling replaced, is recorded in
`LINEAGE_DESIGN_DECISIONS.md`. When a ruling changes the design, this document is rewritten
throughout to match, and the ruling is logged there.

Related records: `DECISIONS_landings_and_conventions.md` §21ad, §21ci, §21y, §21ae;
`amp_real_etl/STATE_2026-09-15.md` (dated before the 2026-10-22 lineage ruling).

**RULE** — every concept in a linkage chain is either a Standard OMOP concept or a declared local
field concept in OMOP's reserved 2-billion range — nothing in between. All three mechanisms follow
this one principle. Off-label vocabulary is never used.

**WARRANT** — OMOP's conventions only guarantee record-linkage meaning for Standard concepts, and
the 2-billion range is the only local space OMOP reserves; §1 carries the vocabulary measurement
showing the tempting alternatives are non-standard.

## 0. The rules that govern every bridge below

**RULE** — **the defining concept's DOMAIN must match the table it lands in.** A concept written to
`measurement_concept_id` is `domain_id = 'Measurement'`; one written to `observation_concept_id` is
`domain_id = 'Observation'`. No exceptions, and this outranks any specific concept named in this
document.

**WARRANT** — Alan, 2026-09-24. A domain that disagrees with its table is a record asserting it is
one kind of fact while sitting in the table for another, and nothing in the CDM reconciles the two.

**EVIDENCE** `2026-09-24` — **70 of 524** table-typed `sysbio_etl` records across the mapping tree
carried a defining concept whose domain did not match its table (59 into `observation`, 6 into
`measurement`, 5 into `specimen`), and no check in `36_rulings.py` looked for it. One of them is
`AMP-CMD/sample_acquisition.json` record_2 — see the Pattern section at the end.

**RULE** — **the concept is chosen by GRANULARITY.** Pick the concept that states the most specific
true thing about the record — specimen acquisition, a particular preparation, a particular tissue —
and the vocabulary carries many at several levels. It is decided case by case, per element. Concepts
named in this document are examples of the pattern, with one exception: the two specimen identifier
concepts in §1 ('Unique identifier [Identifier] of Initial sample' for the harvested specimen,
'Unique identifier for Current sample' for every derived specimen) are fixed.

**RULE** — **a bridge may be a MEASUREMENT or an OBSERVATION.** Both tables carry the event-field
mechanism (`measurement_event_id` / `meas_event_field_concept_id`, `observation_event_id` /
`obs_event_field_concept_id`) and both have established `fact_relationship` pairs. The granularity of
the available concept usually decides which table. What does not vary is the shape: a bridge row
whose event field points at one record and whose reciprocal `fact_relationship` pair points at the
other. Specimen identifier rows (§1) are always in `cdm.measurement`: their concepts are
Measurement-domain, and the only Specimen-facing relationship pair has a measurement on its other
side.

**RULE** — **an event id and a `fact_relationship` fact id are the CDM PRIMARY KEY of the target
table, never a source identifier.** In a specimen identifier row, `measurement_event_id` holds
`cdm.procedure_occurrence.procedure_occurrence_id`, the integer surrogate key — not a source
procedure identifier. A specimen fact id in `fact_relationship` is `cdm.specimen.specimen_id` — not
`specimen_source_id`, not the provider's label. Likewise for every `fact_id_1` / `fact_id_2`.

**WARRANT** — those keys do not exist until the rows are inserted, which is why every specimen-side
linkage in this document is written by `34_load.py` and never by the emitter. It is a property of
the mechanism, not a gap in the emitter.

## 1. Specimen identity and derivation: one identifier row per specimen, anchored on its procedure

**RULE** (Alan, 2026-10-22, clarified 2026-10-26) — **every specimen has one identifier row** in
`cdm.measurement`, whose event pointer names the PROCEDURE that produced the specimen (biopsy,
dissection, dissociation, library preparation):

```
measurement_concept_id      = harvested specimen: 'Unique identifier [Identifier] of Initial sample' (LOINC, Standard, 1176306)
                              derived specimen:   'Unique identifier for Current sample' (LOINC, Standard) — never 'Initial sample'
value_source_value          = <this specimen's own identifier>
measurement_event_id        = <procedure_occurrence_id of the procedure that produced this specimen>   -- CDM primary key
meas_event_field_concept_id = 'procedure_occurrence.procedure_occurrence_id' (CDM vocabulary, Standard, 1147082)
```

**WARRANT** (Alan) — "Initial sample" on a derivative "would obscure which one is the actual parent
specimen"; the event pointer lands on the procedure because the procedure minted the identifier
(the grain rule: anchor = the procedure that produced the thing).

**RULE** — the row is tied to **its own specimen** by the **standard** Measurement↔Specimen pair:

```
(21, this_measurement_id, 36, this_specimen_id, 'Measurement to Specimen')   -- 32668
(36, this_specimen_id, 21, this_measurement_id, 'Specimen to Measurement')   -- 32669
```

**WARRANT** (Alan) — "make it clear that the specimen record IS the child's record."

**RULE** — a derived specimen's row is linked to its parent's row by the **standard**
Measurement↔Measurement pair that exists for exactly this meaning:

```
(21, parent_measurement_id, 21, child_measurement_id, 'Parent to Child Measurement')   -- 581436
(21, child_measurement_id,  21, parent_measurement_id, 'Child to Parent Measurement')   -- 581437
```

**WARRANT** (Alan) — "built in, standard, explicitly defines what it is."

**RULE** — **fan-in.** Each child's row carries its own pair to the one parent row; a parent row
never lists its children. There is no separate bridge row for the harvested specimen: its
identifier row IS the link to the procedure that produced it. Walk from any specimen:
Specimen-to-Measurement pair → its identifier row → Child-to-Parent pair → parent's identifier row →
Measurement-to-Specimen pair → parent specimen, recursively; the event pointer at every row names
the procedure that produced that specimen.

**RULE** — a derived specimen is never linked to its parent by a direct
specimen↔specimen `fact_relationship` row. Route it through the identifier rows above.

**WARRANT** — `fact_relationship` requires a **Standard** relationship concept, and no Standard
concept describes specimen→specimen derivation. The seemingly natural 'Sub-specimen of' pair
(*Sub-specimen of (SNOMED Vet)*, 32554 / *Includes sub-specimen (SNOMED Vet)*, 32553) is
**non-standard** SNOMED-Vet vocabulary machinery whose home is `concept_relationship` — the table
that relates CONCEPTS to each other — not `fact_relationship`, the table that relates RECORDS. A
non-standard concept in a record-linkage row is not a join target, so the link would be invisible
to the query it exists to answer (the general form of that is
`DECISIONS_landings_and_conventions.md` §21y).

**EVIDENCE** `2026-09-15` `sysbio_etl.cdm.concept, vocabulary_id='Relationship', standard_concept='S'` —
the Relationship vocabulary holds **fourteen** Standard concepts, seven reciprocal pairs:

```
 32668 / 32669      Measurement to Specimen  /  Specimen to Measurement
581410 / 581411     Observation to Measurement  /  Measurement to Observation
581436 / 581437     Parent to Child Measurement  /  Child to Parent Measurement
46233680 / 46233681 Patient moved to  /  Patient moved from
46233682 / 46233683 Diastolic to systolic blood pressure measurement  /  Systolic to diastolic
46233684 / 46233685 Relevant condition of  /  Condition relevant to
46233688 / 46233689 Care Site is part of Care Site  /  Care Site contains Care Site
```

Exactly one pair relates a measurement to a specimen — Measurement to Specimen / Specimen to
Measurement — and exactly one relates a measurement to a measurement as parent and child. The same
query confirmed that the two 'Sub-specimen of' concepts carry an EMPTY `standard_concept` column,
i.e. non-standard.

**WARRANT** — the identifier-row route is compliant at every hop: Standard Measurement-domain
identifier concepts, a Standard CDM field concept for the event pointer, and the two Standard
relationship pairs OHDSI provides for measurement-to-specimen and parent-to-child measurement
linkage.

**DESIGN** — why measurement and not observation? It has been suggested that sensitive content be
confined to the observation table. That restriction is neither feasible nor desirable here. The
measurement table is the semantically correct home for an identifier *measurement* about a sample,
and OMOP's own vocabulary agrees — both identifier concepts ('Unique identifier [Identifier] of
Initial sample' and 'Unique identifier for Current sample') are Measurement-domain LOINC concepts,
and the Measurement to Specimen / Specimen to Measurement pair exists specifically to tie
measurements to specimens.

**RULE** — sensitivity is not managed by table choice: **every governed table (measurement and
observation alike) carries a per-record access table and row-level security**, and a row's
visibility follows its access-group grants regardless of which table holds it. The CDM is
restrictive enough without additional arbitrary constraints; the access layer exists precisely so
that governance and table semantics stay independent concerns.

## 2. File records: observation rows with the CDM event-linkage pair

**RULE** — per the Beta-2 data contract, every data file yields one `cdm.observation` row **per
(file, donor)**: concept 'Research data collection' (4303445, Standard, uniform so retrieval is a
single equality), qualifier 'Molecular biology report Document' (1091809) marking omics content with
the assay modality in `qualifier_source_value`, the file name in `value_as_string`, and the event
pair `observation_event_id → files.file_id` with `obs_event_field_concept_id` = the declared local
Field concept 'files.file_id' (2000000001, SysBio vocabulary).

**WARRANT** — `files` is an extension table, so no CDM-vocabulary field concept exists for it; the
2-billion range is OMOP's reserved local-extension space.

**RULE** — table/field-defining concepts are the one category of local minting this project
permits.

**DESIGN** — donors of cohort-level products (harmonized matrices, pseudobulk outputs) resolve
through `assay_input_file` → contributing assays → specimen owners, so every participant carries a
record for every file they are in — one query returns a participant's complete file footprint:
**`amp_real_etl/QUERY_BOOK.md` section D, query D3** *("Every file a participant appears in — the
footprint, via the file record")*, generated by `amp_real_etl/bin/11_query_book.py`.

**RULE** — `amp_real_etl/QUERY_BOOK.md` is the only query inventory for this work, and it is
generated — never hand-edited. The synthetic generator's cookbook
(`sysbio-cdm-defined-repo/amp_synth_etl/resources/query_cookbook.md`) describes a different cohort
and a different schema and is not specification for this build
(`DECISIONS_landings_and_conventions.md` §21ae).

**RULE** — the `files` table holds **data files only**: dictionaries, protocols, templates,
READMEs, codebooks, manifests and changelogs are excluded at emission by an enforced guard.

## 3. Assay and visit linkage

**DESIGN** — assay↔specimen and assay↔file links are dedicated join tables (`assay_to_specimen`,
`assay_input_file`) — self-describing, foreign-key enforced, requiring no relationship vocabulary
at all.

**RULE** — visit linkage rides `(person_id, visit_source_value)` with bare visit names, per the
data contract's masking rules.

**WARRANT** — that form is fixed by the data contract's masking rules, not chosen here.

---

## Pattern: joining a PROCEDURE to the SPECIMEN it produced

`cdm.procedure_occurrence` and `cdm.specimen` have no column that joins them, and OMOP has no
Relationship concept for Procedure to Specimen. The join is the specimen's own identifier row in
`cdm.measurement` (§1); there is no separate bridge row.

- **The row.** For the harvested specimen, `measurement_concept_id` = 'Unique identifier
  [Identifier] of Initial sample'; for a derived specimen, 'Unique identifier for Current sample'.
  `value_source_value` carries that specimen's own identifier.

- **The event fields name the procedure.** `measurement_event_id` holds the
  `procedure_occurrence_id` of the procedure that produced the specimen, and
  `meas_event_field_concept_id` holds 'procedure_occurrence.procedure_occurrence_id' (1147082) to
  say what that integer is. The map declares this; `33_emit.py` resolves it. **These ids are CDM
  primary keys, never source ids.**

- **The fact_relationship pair names the specimen, and is required.** Measurement to Specimen /
  Specimen to Measurement tie the row to its own specimen. Because the event fields point at the
  procedure, this pair is the only link from the row to the specimen. It is written by
  `34_load.py :: link_acquisition_to_specimen()` rather than by the emitter, because the specimen
  is rail-minted and has no emitted fact_key for the emitter to point at.

**Known gap.** `AMP-CMD/sample_acquisition.json` record_2 is the harvested specimen's identifier
row. It currently carries 'Specimen collection procedure' (602279) as `measurement_concept_id`;
that concept is `domain_id = 'Observation'`, `concept_class_id = 'Observable Entity'` (verified
against `sysbio_etl.cdm.concept` on 2026-09-24), so it breaks the domain rule in §0. Its concept is
'Unique identifier [Identifier] of Initial sample'.
