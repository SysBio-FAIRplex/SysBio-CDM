# SysBio-CDM

A customized OMOP CDM v5.4 for AMP data: the schema, the AMP-to-CDM mapping, and a synthetic dataset to try it on.

## Layout
- `data_model/` — the schema. `sysbio-dbml.dbml` is the source of truth (paste into dbdiagram.io to view); `sysbio-cdm-ddl.sql` is the runnable PostgreSQL DDL generated from it.
- `transform/` — the AMP-to-CDM mapping. `data_dictionary.tsv` is the per-variable spec (AMP variable to OMOP concept/table/field), `amp_to_cdm_load_queries.sql` is the executable ETL, `collected_omop_concepts.tsv` is the concept set.
- `synthetic/` — a synthetic dataset (not patient data) plus worked user-story queries. See `synthetic/README.md`.
- `reference/` — OMOP conventions.
- `archive/` — retired files kept for reference, not current.

## Using the data
- Look at it: open `synthetic/sysbio_cdm_synth.sqlite` in any SQLite client.
- Build it in PostgreSQL: create a schema, run `data_model/sysbio-cdm-ddl.sql`, then `synthetic/data.sql`.
