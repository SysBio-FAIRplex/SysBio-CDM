# Synthetic SysBio-CDM dataset

Synthetic data generated to exercise the SysBio-CDM. Not patient data. Every value is fabricated.

Schema: `../data_model/sysbio-cdm-ddl.sql`, generated from `../data_model/sysbio-dbml.dbml`.
Concept and mapping references live in `../transform/`.

## Contents
- `sysbio_cdm_synth.sqlite`: the full dataset in one file. Open and query it with any SQLite client. It includes a `concept` table holding the 295 concepts the data references.
- `user_stories/query_cookbook.md`: worked cohort-builder queries, S1 to S14 (PostgreSQL dialect, same table and column names).

## Size
209 persons, 670 visits, 58,177 observations, 23,734 measurements, 417 specimens, 347 specimen_relationship edges, 407 procedures, 180 assays, 361 files. `condition_occurrence` and `fact_relationship` are empty by design.

## Tracing a row back to its AMP variable
For any row loaded from an AMP CDE, the source variable name is in the `*_source_value` column (`observation_source_value`, `measurement_source_value`), and it matches `amp_variable` in `../transform/data_dictionary.tsv`. The raw value-set text is in `value_source_value`. Rows with an empty `*_source_value` are derived records (diagnoses, demographics, QC, assay-technique) that do not come from a single AMP variable.

## Model notes
- Diagnoses and demographics are `observation` rows. `person` is data-free: gender, race, ethnicity, and year_of_birth are pinned to 0. No `condition_occurrence` data.
- `specimen_relationship` carries the derivation lineage: `specimen_id_1` derives from `specimen_id_2`, each edge backed by a `procedure_occurrence`. `anatomic_site_concept_id` holds the most specific site available, a brain region on tissue and sections, the sorted cell type on the RNA or DNA extract. Extracts reach their `assay` through `assay_to_specimen`; the assay outputs are rows in `files`.
- Record access is per row: each governed record has an `<entity>_access` row pointing to one `access_groups` entry, one group per AMP program.
- Cross-record links use the event fields (`*_event_id` with `*_event_field_concept_id`). `fact_relationship` is empty.
