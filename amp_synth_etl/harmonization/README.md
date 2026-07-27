# Harmonization layer — the pre-ETL variable crosswalk

**Why this exists.** Every AMP program — and every file within it — encodes the same concept
differently. `sex` alone appears in **five** forms across the datasets: Title-case `Male/Female`
(AD, PD), lowercase `male/female` (CMD, RA-SLE), numeric `np_gender` `1/2` (CMD), PATO ontology IDs
(CMD), and the inconsistent ROSMAP `msex` (`F/M/Male/Female`, when the real form is `1/0`). A core
selling point of the project is that we **harmonize every source to one flat layer first, then ETL that
single harmonized layer into the SysBio CDM** — instead of burying per-source special-casing inside the
ETL, where it can't be seen or audited.

**What this is.** `variable_crosswalk.tsv` is the flat, auditable registry of that harmonization,
tracked **by harmonized variable × program × file × column**, with the value map from each source
representation to the harmonized target. Open it in any spreadsheet to see, at a glance, how one concept
is represented across every dataset and exactly how each is normalized.

Columns: `harmonized_variable, harmonized_target, program, source_file, source_column, encoding,
source_values, to_harmonized, notes`.

**How it's used.**
- **ETL** (source → CDM): `to_harmonized` is applied so the harmonized value lands, then maps to a concept.

**Status.** Seeded with `sex`/`msex` as the template case. Other multi-representation variables
(`race`, `ethnicity`, `diagnosis`, age units, …) are added incrementally — the msex case is the pattern
to follow. The long-term fix for `msex`
specifically is upstream: give generation one canonical value set so no cleanup is needed at all.
