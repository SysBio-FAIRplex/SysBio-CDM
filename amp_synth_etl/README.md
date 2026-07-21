# amp_synth_etl

Synthetic AMP source data generator and OMOP CDM ETL.

Generates a synthetic cohort from the AMP program data dictionaries, then loads it
into an OMOP CDM instance. Self-contained: no external repositories, no source
database, no network access. Everything it needs is in this directory.

## Requirements

- Python 3.13 (stdlib only; `pytest` for tests)
- `psql` client on `PATH` — the load and verify steps shell out to it
- A PostgreSQL server for the load/verify steps — connection via `PGHOST`/`PGPORT`/`PGUSER`
  (defaults `localhost` / `5433` / `postgres`); the Docker path sets these automatically

```sh
conda env create -f environment.yml
conda activate amp-synth
```

or

```sh
pip install -r requirements.txt   # plus: apt-get install postgresql-client
```

`PGPASSWORD` is read from the environment or `~/.pgpass`. It is not stored in this
repository.

## Run with Docker (recommended for a fresh clone)

From the **repository root** (where `docker-compose.yml` lives) — no local Python or
Postgres needed, only Docker:

```sh
export PGPASSWORD=<choose one>
docker compose up -d --build     # starts a Postgres service + the pipeline bench
docker compose exec bench bash   # opens a shell in /app/amp_synth_etl
```

Then run the pipeline exactly as in Quick start below. Postgres runs as its own
service with a persistent named volume, reachable at `db:5432` from inside the
bench. It is not published to a host port (so it will not clash with a Postgres you
may already run locally); to inspect it from the host, use
`docker compose exec db psql -U postgres`. Tear down with `docker compose down`
(add `-v` to also drop the database volume).

## Quick start

```sh
export PGPASSWORD=...
make            # list all targets (make help)
make all        # whole pipeline: generation -> CDM delivery -> DB load -> verify
```

`make all` and `bash run_pipeline.sh` are equivalent -- the latter needs no `make`. Run
one part with `make generate`, `make cdm`, `make load`, `make verify`, or `make test`.
Or run the stages individually:

```sh
export PGPASSWORD=...

python scripts/01_build_specs.py
python scripts/02_build_tables.py
python scripts/02c_build_ark.py
python scripts/02f_build_ark_conditional.py
python scripts/03_generate.py
python scripts/04_qc.py

python scripts/10_build_cdm_delivery.py
bash   cdm_load/build_selfcontained.sh
python scripts/13_verify_governance.py
```

`build_selfcontained.sh` drops and recreates a throwaway database
(`sysbio_cdm_selfcontained` by default; pass a name to override). It does not touch
any existing database.

## Pipeline

The `make` / `run_pipeline.sh` front door runs everything in order; this section maps the
pieces. Each script has one of three roles:

- **Run directly** (or via `make`): generation stages `01`-`04`, then `10_build_cdm_delivery.py`
  -> `cdm_load/build_selfcontained.sh` -> `13_verify_governance.py`.
- **Orchestrated** -- run *for* you by `10`, never directly: `06`, `08`, `09`, `11`, `12`.
- **Helper / imported** -- never run on their own: `inputs_io.py`, `fidelity.py`,
  `enumerated.py`, and everything under `scripts/gen/`.

`05_conflicts.py` is a standalone, optional report.

### Specs

| Script | Purpose |
| --- | --- |
| `01_build_specs.py` | Field descriptors for every SysBio Dictionary row |
| `02_build_tables.py` | Table definitions, keys and grain from the AMP dictionaries |
| `02c_build_ark.py` | AMP-RA/SLE tables and specs from the ARK data model |
| `02f_build_ark_conditional.py` | ARK conditional rules and Cell Ontology value set |

### Generation

| Script | Purpose |
| --- | --- |
| `03_generate.py` | Generates the synthetic cohort, person-first, into `output/` |
| `04_qc.py` | QC gate. Exits non-zero on failure |

### CDM delivery

`10_build_cdm_delivery.py` orchestrates the following. Do not run them directly.

| Script | Purpose |
| --- | --- |
| `06_render_cdm_load.py` | Staging objects and the `person` / `visit_occurrence` rows they anchor |
| `08_concept_seed.py` | Concept seed covering every concept the load references |
| `09_map_etl.py` | Map-driven ETL. Emits `observation` / `measurement` facts |
| `11_render_extensions.py` | Biospecimen and assay extension load |
| `12_render_governance.py` | Governance and access-group load |

Output is `cdm_load/cdm_load.sql`, applied after `cdm_load/cdm_ddl.sql`.

### Verification

| Script | Purpose |
| --- | --- |
| `13_verify_governance.py` | Proves record-level RLS restricts. Recomputes expected access independently of the loader |
| `05_conflicts.py` | Standalone report of AMP vs SysBio dictionary disagreements. Not part of the chain |

## Layout

```
config/      cohort parameters, access groups, parked variables, table overrides
inputs/      AMP program dictionaries (vendored), CDE dictionary, fidelity distributions
mappings/    one JSON per AMP variable — the ETL logic
specs/       generated field specs (timestamped)
scripts/     pipeline
scripts/gen/ per-domain generators used by 03_generate
cdm_load/    schema DDL, governance RLS, and generated load SQL
exports/     curated_concept_tables.sqlite — concept source of truth (required)
tests/       pytest suite with a golden manifest
output/      generated synthetic CSVs (created at runtime)
```

## How the ETL works

`mappings/*.json` are the ETL. `09_map_etl.py` reads them and emits one generic
`INSERT … SELECT` per mapping — there is no per-variable logic in the code. To change
how a variable lands in the CDM, edit its mapping, not the script.

`staging.amp_clinical` is the stable interface between generation and load.
`06_render_cdm_load.py` writes it; `09_map_etl.py` reads it. The two are decoupled,
which is why the ETL could be replaced without touching the renderer.

Mappings are gated on `manual_approval`. The default run loads approved mappings only;
`--all` bypasses the gate and is a development override.

```sh
python scripts/10_build_cdm_delivery.py         # approved only (default)
python scripts/10_build_cdm_delivery.py --all   # every mapping
```

Variables listed in `config/parked_variables.tsv` are excluded regardless.

## Generated vs. committed

Generated at runtime, not committed: `output/`, `cdm_load/cdm_load.sql`,
`cdm_load/01_staging_and_structure.sql`, `cdm_load/cdm_facts_load.sql`,
`cdm_load/concept_seed.sql`.

Committed inputs: `exports/curated_concept_tables.sqlite`, `inputs/`, `config/`,
`mappings/`, `resources/sysbio-dbml.dbml`, `cdm_load/cdm_ddl.sql`,
`cdm_load/governance_rls.sql`.

`specs/table_schema_fields_<timestamp>.tsv` is regenerated by `01_build_specs.py` on
every run. Readers glob `table_schema_fields_*.tsv` and take the most recent, so the
timestamp is load-bearing — renaming to a fixed filename requires changing the writer
and all readers together.

## Tests

```sh
pytest tests/ -q
```

Tests assert on output bytes rather than on the model that produced them, and include
a meta-test that a deliberately broken cohort fails QC.

## Reference figures

A full run produces:

```
person                500
visit_occurrence     1312
observation        128939
measurement         60243
concept              1322
```

254 of 258 mappings in scope; 4 excluded by `config/parked_variables.tsv`.

## Known limitations

- `visit_occurrence_id` is nullable. Autopsy and cross-sectional subjects load facts
  with a NULL visit (~0.4% of observations, ~0.5% of measurements) because specimens
  are not chained through a harvesting `procedure_occurrence` to a visit. Every
  participant should have at least one visit; an autopsy counts as a visit.
- No round-trip verification. The cell-for-cell verifier was coupled to the previous
  external ETL and was removed with it. Reconstructing expected cells from the
  map-driven load is outstanding.
- `04_qc.py` and `13_verify_governance.py` are the pipeline's own checks. They
  validate internal consistency and access control, not clinical validity.
