"""Load the extracted AMP-ABC tables into the Synapse sandbox project.

Dry run by default: logs in, inspects the target folder and prints exactly what
--apply would create. Nothing is written without --apply.

--apply creates one TableEntity per extracted table in the project root (where
the Synapse UI's Tables tab lists them), uploads each CSV, and snapshots every
table. A table left in the legacy `dw_amp_abc` folder by an earlier load is
re-created in the root and its folder copy then moved to the Synapse trash. It only ever touches
entities named with the `dw_` prefix. An existing table is left alone
unless --replace is also given, in which case it is moved to the trash and
recreated (Synapse trash is restorable for 30 days).

Usage:
  SYNAPSE_PERSONAL_ACCESS_TOKEN=... .venv/bin/python load.py [--out out]
  SYNAPSE_PERSONAL_ACCESS_TOKEN=... .venv/bin/python load.py --apply [--replace]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

import synapseclient
from synapseclient import Column, Schema, Table

from poc_config import PREFIX, SYNAPSE_FOLDER_NAME, SYNAPSE_PROJECT_ID, TARGET_PROGRAM

# Synapse adds these system columns to every table; a user column of the same
# name (case-insensitive) is rejected when the table schema is stored.
RESERVED_COLUMNS = {
    "ROW_ID",
    "ROW_VERSION",
    "ROW_ETAG",
    "ROW_BENEFACTOR",
    "ROW_HASH_CODE",
    "ROW_SEARCH_CONTENT",
}

TABLE_DESCRIPTION = (
    f"SYNTHETIC POC DATA. {TARGET_PROGRAM} is a rebranded clone of the AMP-PD "
    "reference node's synthetic harmonized CDM, used to prove Query Proxy "
    "federation to Synapse. Not real participant data."
)


def login() -> synapseclient.Synapse:
    token = os.environ.get("SYNAPSE_PERSONAL_ACCESS_TOKEN")
    if not token:
        sys.exit("SYNAPSE_PERSONAL_ACCESS_TOKEN is required")
    syn = synapseclient.Synapse(skip_checks=True, silent=True)
    syn.login(authToken=token, silent=True)
    return syn


def find_child(syn: synapseclient.Synapse, name: str, parent: str) -> str | None:
    return syn.findEntityId(name, parent=parent)


def load(out: Path, apply: bool, replace: bool) -> None:
    manifest: Dict[str, Any] = json.loads((out / "manifest.json").read_text())
    bad = [name for name in manifest if not name.startswith(PREFIX)]
    if bad:
        sys.exit(f"Refusing to load tables without the {PREFIX!r} prefix: {bad}")
    reserved = [
        f"{table}.{column['name']}"
        for table, entry in manifest.items()
        for column in entry["columns"]
        if column["name"].upper() in RESERVED_COLUMNS
    ]
    if reserved:
        sys.exit(f"Columns collide with Synapse system columns: {reserved}")

    syn = login()
    profile = syn.getUserProfile()
    print(f"Logged in as {profile['userName']}; project {SYNAPSE_PROJECT_ID}")

    # Tables live in the project root: the Synapse UI's Tables tab lists only
    # root-level tables. Earlier loads used the dw_amp_abc folder; any table
    # still there is re-created in the root from the same CSV and the folder
    # copy is then moved to the trash. (A true move would keep the id, but
    # Synapse requires CHANGE_PERMISSIONS for it, which only the project
    # admin has.) New ids are harmless: the connector resolves tables by name.
    legacy_folder = find_child(syn, SYNAPSE_FOLDER_NAME, SYNAPSE_PROJECT_ID)

    plan = []
    for name, entry in manifest.items():
        existing = find_child(syn, name, SYNAPSE_PROJECT_ID)
        in_folder = find_child(syn, name, legacy_folder) if legacy_folder else None
        if existing and in_folder:
            sys.exit(f"{name} exists both in the root ({existing}) and in the folder ({in_folder})")
        if in_folder:
            action = f"recreate in project root, then trash {SYNAPSE_FOLDER_NAME} copy {in_folder}"
        elif existing and not replace:
            action = f"skip (exists as {existing}; pass --replace to recreate)"
        elif existing:
            action = f"replace {existing} (trash + recreate)"
        else:
            action = "create"
        plan.append((name, entry, existing, in_folder, action))
        print(f"  {name:<18} {entry['rows']:>7} rows {len(entry['columns']):>3} cols  {action}")

    if not apply:
        print("\nDry run only. Re-run with --apply to write to Synapse.")
        return

    ids: Dict[str, Any] = {"parent": SYNAPSE_PROJECT_ID, "tables": {}}
    for name, entry, existing, in_folder, _ in plan:
        if existing and not replace:
            ids["tables"][name] = {"id": existing}
            continue
        if existing:
            syn.delete(existing)
        schema = syn.store(
            Schema(
                name=name,
                columns=[Column(**spec) for spec in entry["columns"]],
                parent=SYNAPSE_PROJECT_ID,
                description=TABLE_DESCRIPTION,
            )
        )
        csv_path = out / "tables" / f"{name}.csv"
        syn.store(Table(schema, str(csv_path)))
        version = syn.create_snapshot_version(
            schema.id, comment=f"{TARGET_PROGRAM} POC load"
        )
        # Build the query index now: the first query on a freshly loaded table
        # can take longer than the proxy's node timeout.
        syn.tableQuery(f"SELECT COUNT(*) FROM {schema.id}", resultsAs="rowset")
        ids["tables"][name] = {"id": schema.id, "version": version}
        print(f"  loaded {name} -> {schema.id}.{version}")
        if in_folder:
            # Only after the root copy is fully loaded, so there is no gap.
            syn.delete(in_folder)
            print(f"  trashed {SYNAPSE_FOLDER_NAME} copy {in_folder}")

    (out / "synapse_ids.json").write_text(json.dumps(ids, indent=2))
    print(f"\nDone. Ids written to {out / 'synapse_ids.json'}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="out", type=Path)
    parser.add_argument("--apply", action="store_true", help="write to Synapse")
    parser.add_argument("--replace", action="store_true", help="recreate existing tables")
    args = parser.parse_args()
    load(args.out, args.apply, args.replace)
    return 0


if __name__ == "__main__":
    sys.exit(main())
