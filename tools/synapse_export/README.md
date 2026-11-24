# Synapse federation POC (AMP-ABC)

Loads a clearly synthetic program, **AMP-ABC**, into Synapse so the FAIRplex
Query Proxy can federate it alongside the AMP-PD and AMP-CMD reference nodes.
AMP-ABC is the AMP-PD reference node's harmonized CDM, rebranded and with every
entity id offset by 9,000,000,000 so its rows never collide with real AMP-PD
rows in a merged result.

The proxy side is `fairplex-query-proxy/src/query_proxy/connectors/synapse/`.

## Pipeline

1. `extract.py` (read-only). Runs the reference node's own builder SQL
   (`node_sql.py`, unfiltered copies of `fairplex-amp-reference`
   `src/modules/query/cdm/queries.ts`, `facets.ts`, `cdeCatalog.ts`,
   `cdeValues.ts`) against the node's Postgres in a READ ONLY transaction,
   with every access group granted for the session. Writes:
   - `out/tables/*.csv`, one per Synapse table, already rebranded
   - `out/manifest.json`, Synapse column specs sized from the data
   - `out/data_models.json`, the node's GA4GH data_model per typed route
     (copied into the proxy connector; the proxy fails a page whose sources
     disagree on column types)
   - `out/expected.json`, unfiltered oracle numbers for the live smoke test
2. `load.py` (dry run by default). `--apply` creates one table per CSV in the
   root of project `syn78779360` (the Synapse UI's Tables tab lists only
   root-level tables), uploads, and snapshots each table. Tables an earlier
   load left in the `dw_amp_abc` folder are moved to the root, keeping their
   ids. It only touches `dw_`-prefixed entities; `--replace` trashes and
   recreates existing tables (restorable from the Synapse trash for 30 days).

```bash
cd tools/synapse_export
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
PGURL=postgresql://... .venv/bin/python extract.py
SYNAPSE_PERSONAL_ACCESS_TOKEN=... .venv/bin/python load.py           # dry run
SYNAPSE_PERSONAL_ACCESS_TOKEN=... .venv/bin/python load.py --apply   # writes
```

## Tables

| Table | Grain | Serves |
| --- | --- | --- |
| `dw_participants` | person | participant search/summary; person-level filter columns (`*_keys`, `diagnosis_pairs`, `age_min/max`, `visit_count`, `follow_up_days`, `case_control`, `sex_buckets`) |
| `dw_files` | file | file/dataset search and summaries; assay attributes as lists |
| `dw_relationships` | person → specimen → assay → file path | linkage cohorts, relationship evidence, file detail summary |
| `dw_clinical` | observation/measurement value | clinical criteria cohorts and `_clinical_n` projections, with `is_latest` flags |
| `dw_datasets` | program | access-group metadata for dataset rows |
| `dw_concepts` | concept | disease/qualifier labels |
| `dw_visits` | visit | reserved for longitudinal search (not served yet) |
| `dw_facets`, `dw_cde_catalog`, `dw_cde_values` | — | global metadata, precomputed with the node's own SQL |

## Known divergences from the Postgres node

- File assay filters match a file with ANY assay holding each value, not ONE
  assay holding all of them.
- `age_min`/`age_max` compare against a person's age range (identical when a
  person has one age row, as every seed person does).
- Not yet served from Synapse: longitudinal search (empty page) and file
  provenance (empty list). The rest of the federation still answers.
- Synapse sorts NULLs first; every typed sort key is a non-null id here.
- Access control is the Synapse folder ACL (all-or-nothing per program). The
  node's per-row tier groups are carried as `access_group` but not enforced;
  splitting tiers into separately-permissioned folders is the next step.
