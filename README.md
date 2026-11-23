# SysBio CDM

*** SysBio CDM Preprint is available here: https://doi.org/10.64898/2026.08.31.26361831 ***

The SysBio common data model: its schema, the mapping specifications that harmonize the
AMP programs' data (AMP-AD, AMP-PD, AMP-CMD, AMP-RA/SLE) into it, and the specification-driven
ETL that loads them.

This repository holds code and specifications only. It contains no participant or sample
data, no identifiers and no data file names. Pinned source files are referenced by sha256.

## Layout

- `docs/harmonized-element-2.7-TEMPLATE.json` — the mapping specification schema: one annotated
  example of every field, with the rule for each.
- `registry/` — one JSON file per harmonized element, the mapping specification: definition,
  source blocks (program, source column, pinned files by hash, value map, loading grain),
  harmonized value set, and the Layer 2 OMOP landing.
- `schema/` — the CDM itself: `sysbio-dbml.dbml` (the canonical schema), `cdm_ddl.sql`
  (Postgres DDL generated from it), `governance_rls.sql` (row-level security for the governed
  tables), and the entity-relationship diagram `sysbio-cdm-erd-20260611.png` (drawn 2026-06-11;
  the DBML has changed since and is the source of truth).
- `tools/cde_registry_browser/` — a browser for reading and editing mapping specifications.
- `etl/layer_1/` — the pipeline:
  - `spec_check.py` — the gate every specification must pass (structure).
  - `dryrun.py` — validates the specifications against the files of a run; reads only.
  - `load.py` — writes harmonized values per cohort, at measured grain, with lineage.
  - `gates.py` — release checks on a run folder.
  - `quality_table.py` — one row per specification: completeness and unmapped source values.
  - `dictionary_lookup.py`, `stage_registry.py` — dictionary lookup, and the staging of
    specifications into this repository.

## Running a load

The input is an ETL input manifest: a TSV with one row per file to process. Columns:
`file` (path relative to the data root, or absolute), and optionally `cohort`, `sheet` and
`sha256`. Every mapping block that pins a listed file is applied to it; nothing else decides
what is read. Values are mapped only through each block's value map, source value to
harmonized value, exactly as written; missing-value tokens are only those a block declares.

Environment:

- `ETL_INPUT_MANIFEST` — the manifest (default `<declarations>/etl_input_manifest.tsv`).
- `CDM_SYSBIO` — the data root holding the source files, never inside this repository.
- `CDM_REGISTRY` — the specifications to run (default `registry/`).
- `CDM_DECL` — the declarations folder: `cohorts.tsv` names each cohort and its participant
  bridge; a cohort without a bridge processes whole files with keys as written.
- `CDM_OUT` — the run folder that receives every output, outside this repository.
- `CDM_VOCAB_DSN` — optional database connection for the vocabulary checks of `spec_check.py`.

```
python etl/layer_1/spec_check.py registry
python etl/layer_1/dryrun.py
python etl/layer_1/load.py
python etl/layer_1/gates.py $CDM_OUT
```

Outputs per cohort: a long table of every value with its keys and full lineage, one wide
table per grain, and an `audit/` folder (load report, conflicts, unmapped values, columns
not read, source files by hash).

## Specification rules

A specification passes the gate when its definition is one plain sentence, every pinned
file carries a hash, every block declares its source column and loading grain, every value
map line has a source value and a harmonized value, and the Layer 2 target names a table
and, where required, a concept of the matching domain.
