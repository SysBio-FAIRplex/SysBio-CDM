"""Extract the AMP-PD reference node's CDM into flat, rebranded Synapse tables.

READ-ONLY. Every statement runs in a read-only transaction against the node's
Postgres, with every access group granted for the session so RLS exposes the
complete dataset (the same scope the node itself uses for global metadata).

Outputs, under --out (default ./out):
  tables/<name>.csv    one CSV per Synapse table, values already rebranded
  manifest.json        Synapse column specs per table (consumed by load.py)
  data_models.json     the node's GA4GH data_model per typed row route
  expected.json        unfiltered aggregates, as parity oracles for the connector

Usage:
  PGURL=postgresql://... .venv/bin/python extract.py [--out out]
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import psycopg
from psycopg.rows import dict_row

import node_sql
from poc_config import ID_COLUMNS, ID_OFFSET, SOURCE_PROGRAM, TARGET_PROGRAM

JSON_SCHEMA_DRAFT_07 = "http://json-schema.org/draft-07/schema#"

# --- data_model: a port of amp-reference jsonSchemaFromPgOid -----------------

_PG_OID_SCHEMA: Dict[int, Dict[str, Any]] = {
    16: {"type": "boolean"},
    20: {"type": ["integer", "string"], "pattern": "^-?[0-9]+$"},
    21: {"type": "integer"},
    23: {"type": "integer"},
    26: {"type": "integer"},
    700: {"type": "number"},
    701: {"type": "number"},
    1700: {"type": ["number", "string"]},
    1082: {"type": "string", "format": "date"},
    1114: {"type": "string", "format": "date-time"},
    1184: {"type": "string", "format": "date-time"},
}
_PG_ARRAY_ELEMENTS = {
    1000: 16, 1005: 21, 1007: 23, 1009: 25, 1014: 1042, 1015: 1043,
    1016: 20, 1021: 700, 1022: 701, 1028: 26, 1231: 1700,
}


def json_schema_from_oid(oid: int) -> Dict[str, Any]:
    """Mirror of the node's mapping, so the proxy sees identical models."""
    element = _PG_ARRAY_ELEMENTS.get(oid)
    if element is not None:
        schema: Dict[str, Any] = {"type": "array", "items": json_schema_from_oid(element)}
    else:
        schema = dict(_PG_OID_SCHEMA.get(oid, {"type": "string"}))
    types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
    return {**schema, "type": [*types, "null"]}


def data_model(description: Iterable[Any]) -> Dict[str, Any]:
    return {
        "$schema": JSON_SCHEMA_DRAFT_07,
        "type": "object",
        "properties": {col.name: json_schema_from_oid(col.type_code) for col in description},
    }


# --- rebranding --------------------------------------------------------------

_URI_ID = re.compile(r"^(drs://[^/]+/)(\d+)$")


def rebrand(column: str, value: Any) -> Any:
    """Relabel AMP-PD as AMP-ABC and shift every entity id out of PD's range."""
    if value is None:
        return None
    if isinstance(value, list):
        return [rebrand(column, item) for item in value]
    if column in ID_COLUMNS and isinstance(value, int):
        return value + ID_OFFSET
    if isinstance(value, str):
        if value == SOURCE_PROGRAM:
            return TARGET_PROGRAM
        if column == "uri":
            match = _URI_ID.match(value)
            if match:
                return f"{match.group(1)}{int(match.group(2)) + ID_OFFSET}"
    return value


# --- Synapse column specs ----------------------------------------------------

# Postgres numeric output columns are stored as text so the connector returns
# the node's exact representation (pg serializes numeric as a string).
_TEXT_NUMERIC = {"age_at_baseline"}


def synapse_type(oid: int, column: str) -> str:
    element = _PG_ARRAY_ELEMENTS.get(oid)
    if element is not None:
        return "INTEGER_LIST" if element in (20, 21, 23, 26) else "STRING_LIST"
    if oid in (20, 21, 23, 26):
        return "INTEGER"
    if oid in (700, 701):
        return "DOUBLE"
    if oid == 1700:
        return "STRING" if column in _TEXT_NUMERIC else "DOUBLE"
    if oid == 16:
        return "BOOLEAN"
    if oid in (1082, 1114, 1184):
        return "DATE"
    return "STRING"


def column_specs(
    description: Iterable[Any], rows: List[Dict[str, Any]], overrides: Dict[str, str]
) -> List[Dict[str, Any]]:
    """Synapse ColumnModels sized from the data (Synapse caps STRING at 1000)."""
    specs = []
    for col in description:
        kind = overrides.get(col.name) or synapse_type(col.type_code, col.name)
        spec: Dict[str, Any] = {"name": col.name, "columnType": kind}
        values = [row.get(col.name) for row in rows]
        if kind in ("STRING", "STRING_LIST"):
            items = [
                str(v)
                for value in values
                if value is not None
                for v in (value if isinstance(value, list) else [value])
                if v is not None
            ]
            longest = max((len(item) for item in items), default=1)
            if kind == "STRING" and longest > 1000:
                spec["columnType"] = "LARGETEXT"
            else:
                spec["maximumSize"] = min(1000, max(50, _round_up(longest)))
        if kind.endswith("_LIST"):
            longest_list = max((len(v) for v in values if isinstance(v, list)), default=1)
            spec["maximumListLength"] = max(10, _round_up(longest_list))
        specs.append(spec)
    return specs


def _round_up(n: int) -> int:
    """Headroom so a reload with slightly longer values still fits."""
    return int(n * 1.5) + 5


# --- CSV ---------------------------------------------------------------------


def csv_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return json.dumps([_jsonable(v) for v in value if v is not None])
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:10]
    return str(value)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def write_csv(path: Path, columns: List[str], rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([csv_cell(row.get(c)) for c in columns])


# --- extraction --------------------------------------------------------------


def run(cur: psycopg.Cursor, sql: str) -> Tuple[List[Dict[str, Any]], Any]:
    cur.execute(sql)
    rows = cur.fetchall()
    return rows, cur.description


def rebrand_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{k: rebrand(k, v) for k, v in row.items()} for row in rows]


def cde_values_rows(cur: psycopg.Cursor) -> Tuple[List[Dict[str, Any]], Any]:
    """One row per CDE: the node's value profile with options as JSON."""
    totals, _ = run(cur, node_sql.CDE_TOTALS_SQL)
    options, _ = run(cur, node_sql.CDE_OPTIONS_SQL)
    by_cde: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for option in options:
        by_cde.setdefault((option["domain"], option["source_value"]), []).append(option)
    out = []
    for total in totals:
        key = (total["domain"], total["source_value"])
        # The node orders by COUNT(*) DESC, then text_value ASC NULLS LAST.
        ranked = sorted(
            by_cde.get(key, []),
            key=lambda o: (-o["row_count"], o["text_value"] is None, o["text_value"] or ""),
        )
        out.append(
            {
                "domain": total["domain"],
                "source_value": total["source_value"],
                "participant_count": total["participant_count"],
                "row_count": total["row_count"],
                "numeric_row_count": total["numeric_row_count"],
                "numeric_min": _as_float(total["numeric_min"]),
                "numeric_max": _as_float(total["numeric_max"]),
                "options_truncated": len(ranked) > 200,
                "options_json": json.dumps(
                    [
                        {
                            "text_value": o["text_value"],
                            "concept_id": o["concept_id"],
                            "concept_name": o["concept_name"],
                            "participant_count": o["participant_count"],
                            "row_count": o["row_count"],
                        }
                        for o in ranked[:200]
                    ]
                ),
            }
        )
    return out, None


def _as_float(value: Any) -> float | None:
    return None if value is None else float(value)


CDE_VALUES_SPECS = [
    {"name": "domain", "columnType": "STRING", "maximumSize": 20},
    {"name": "source_value", "columnType": "STRING", "maximumSize": 200},
    {"name": "participant_count", "columnType": "INTEGER"},
    {"name": "row_count", "columnType": "INTEGER"},
    {"name": "numeric_row_count", "columnType": "INTEGER"},
    {"name": "numeric_min", "columnType": "DOUBLE"},
    {"name": "numeric_max", "columnType": "DOUBLE"},
    {"name": "options_truncated", "columnType": "BOOLEAN"},
    {"name": "options_json", "columnType": "LARGETEXT"},
]


def expected_aggregates(cur: psycopg.Cursor) -> Dict[str, Any]:
    """Unfiltered numbers the connector must reproduce (pre-rebrand counts)."""
    default_roles = "('harmonized_output', 'assay_matrix')"
    linked = f"""SELECT COUNT(DISTINCT s.person_id) AS n FROM files f
      JOIN ({node_sql.FILE_ASSAYS_SQL}) fa ON fa.file_id = f.file_id
      JOIN assay_to_specimen ats ON ats.assay_id = fa.assay_id
      JOIN specimen s ON s.specimen_id = ats.specimen_id
      WHERE f.file_role IN {default_roles}"""
    files = f"""SELECT COUNT(*) AS n, COALESCE(SUM(file_size_bytes), 0) AS bytes
      FROM files WHERE file_role IN {default_roles}"""
    cur.execute("SELECT COUNT(*) AS n FROM person")
    persons = cur.fetchone()["n"]
    cur.execute(linked)
    contributors = cur.fetchone()["n"]
    cur.execute(files)
    file_row = cur.fetchone()
    return {
        "clinical_participant_count": persons,
        "default_roles_participant_count": contributors,
        "default_roles_file_count": file_row["n"],
        "default_roles_file_size_bytes": int(file_row["bytes"]),
    }


# Each table: (sql, Synapse type overrides). Participants merge a second query.
TABLES = {
    "dw_files": (node_sql.FILES_SQL, {}),
    "dw_relationships": (node_sql.RELATIONSHIPS_SQL, {}),
    "dw_datasets": (node_sql.DATASETS_SQL, {}),
    "dw_clinical": (node_sql.CLINICAL_SQL, {}),
    "dw_concepts": (node_sql.CONCEPTS_SQL, {}),
    "dw_visits": (node_sql.VISITS_SQL, {}),
    "dw_facets": (node_sql.FACETS_SQL, {}),
    "dw_cde_catalog": (node_sql.CDE_CATALOG_SQL, {}),
}

DATA_MODEL_ROUTES = {
    "/datasets/search": "dw_datasets",
    "/files/search": "dw_files",
    "/participants/search": "dw_participants",
    "/files/{file_id}/relationships/search": "dw_relationships",
    "/participants/{person_id}/relationships/search": "dw_relationships",
}


def extract(pg_url: str, out: Path) -> None:
    manifest: Dict[str, Any] = {}
    models: Dict[str, Any] = {}
    descriptions: Dict[str, Any] = {}

    with psycopg.connect(pg_url, row_factory=dict_row, autocommit=False) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            cur.execute("SET LOCAL search_path TO harmonized")
            cur.execute(
                "SELECT set_config('app.access_groups', "
                "(SELECT string_agg(id::text, ',') FROM public.access_groups), true)"
            )

            # Participants: the node's row projection plus filter columns.
            rows, desc = run(cur, node_sql.PARTICIPANTS_SQL)
            descriptions["dw_participants"] = desc
            extra_rows, extra_desc = run(cur, node_sql.PARTICIPANT_FILTERS_SQL)
            extras = {r["person_id"]: r for r in extra_rows}
            merged = [{**row, **extras[row["person_id"]]} for row in rows]
            merged.sort(key=lambda r: r["person_id"])
            all_desc = list(desc) + [c for c in extra_desc if c.name != "person_id"]
            _emit(out, manifest, "dw_participants", all_desc, merged, {})

            for name, (sql, overrides) in TABLES.items():
                rows, desc = run(cur, sql)
                descriptions[name] = desc
                _emit(out, manifest, name, desc, rows, overrides)

            cde_rows, _ = cde_values_rows(cur)
            columns = [spec["name"] for spec in CDE_VALUES_SPECS]
            write_csv(out / "tables" / "dw_cde_values.csv", columns, cde_rows)
            manifest["dw_cde_values"] = {"columns": CDE_VALUES_SPECS, "rows": len(cde_rows)}

            expected = expected_aggregates(cur)
        conn.rollback()

    for route, table in DATA_MODEL_ROUTES.items():
        models[route] = data_model(descriptions[table])
    # Participant clinical projections are ARRAY_AGG(DISTINCT <text>) columns.
    models["_clinical_column"] = json_schema_from_oid(1009)

    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (out / "data_models.json").write_text(json.dumps(models, indent=2))
    (out / "expected.json").write_text(json.dumps(expected, indent=2))
    for name, entry in manifest.items():
        print(f"  {name:<18} {entry['rows']:>7} rows  {len(entry['columns'])} cols")
    print(f"  expected: {expected}")


def _emit(out, manifest, name, desc, rows, overrides) -> None:
    branded = rebrand_rows(rows)
    specs = column_specs(desc, branded, overrides)
    columns = [spec["name"] for spec in specs]
    write_csv(out / "tables" / f"{name}.csv", columns, branded)
    manifest[name] = {"columns": specs, "rows": len(branded)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="out", type=Path)
    args = parser.parse_args()
    pg_url = os.environ.get("PGURL")
    if not pg_url:
        print("PGURL is required", file=sys.stderr)
        return 2
    extract(pg_url, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
