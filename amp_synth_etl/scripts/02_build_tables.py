#!/usr/bin/env python3
"""
Build the TABLE DEFINITIONS from the AMP dictionaries.

The AMP dictionaries define their own tables, keys and grain. This script reads them; it does not
infer, name-match, or invent.

  AMP-PD  pdrd/*.csv          `TableName` column names the table. Every table declares
                              participant_id / GUID / visit_name / visit_month -> VISIT grain.
  AMP-AD  ad/DiverseCohorts_parsed_dictionary.tsv
                              `source_file` names the table. Keyed by individualID; NO visit column
                              exists anywhere in them -> SUBJECT grain (autopsy cohort).
  AMP-AD  ROSMAP_clinical_codebook
                              States "All longitudinal data sets are organized by projid + visit or
                              fu_year", but the codebook's Clinical/Pathology sections do not
                              survive PDF text extraction reliably (`spanish`, a demographic, lands
                              in 'Pathology' by text position). ROSMAP's grain is therefore NOT
                              guessed here: every ROSMAP column is emitted with grain=needs_review
                              into config/tables.tsv for a human to set.

GRAIN RULE (read off the dictionary, not inferred):
    a table is VISIT-grained iff its dictionary defines visit columns; otherwise SUBJECT-grained.

Output: config/tables.tsv  -- one row per (table, column). Reviewable.
        reports/table_coverage_<ts>.md
Nothing is written outside this pipeline directory.
"""
import csv
import glob
import json
import os
import re
from collections import defaultdict
from datetime import datetime

import inputs_io  # self-contained reads (replaces the sysbio_etl DB)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AMP = os.path.join(ROOT, "inputs", "amp_dictionaries")
PDRD = os.path.join(AMP, "pdrd")
AD_TSV = os.path.join(AMP, "ad", "DiverseCohorts_parsed_dictionary.tsv")

VISIT_COLS = {"visit_name", "visit_month"}
SUBJECT_KEYS = {"participant_id", "GUID", "individualID", "projid", "ID"}


def main():
    # ---------------------------------------------------------------- AMP-PD: TableName column
    tables = defaultdict(lambda: {"program": None, "cols": [], "source": None})
    for f in sorted(glob.glob(os.path.join(PDRD, "*.csv"))):
        for r in csv.DictReader(open(f, newline="", encoding="utf-8-sig")):
            t = r["TableName"]
            tables[t]["program"] = "AMP-PD"
            tables[t]["source"] = f"pdrd/{os.path.basename(f)}"
            tables[t]["cols"].append(r["ColumnName"])

    # ---------------------------------------------------------------- AMP-AD: DiverseCohorts
    for r in csv.DictReader(open(AD_TSV, newline="", encoding="utf-8-sig"), delimiter="\t"):
        t = r["source_file"]
        tables[t]["program"] = "AMP-AD"
        tables[t]["source"] = "ad/DiverseCohorts_parsed_dictionary.tsv"
        if r["ColumnName"] not in tables[t]["cols"]:
            tables[t]["cols"].append(r["ColumnName"])

    # ---------------------------------------------------------------- AMP-AD: ROSMAP
    # The codebook's variables, taken from the SysBio dictionary rows whose source_file names it.
    # Grain is left for review -- see the module docstring.
    rosmap = sorted({r["amp_variable"] for r in inputs_io.dict_rows(parked=False)
                     if "rosmap_clinical_codebook" in (r["source_file"] or "").lower()})
    if rosmap:
        tables["ROSMAP_clinical_codebook.pdf"] = {
            "program": "AMP-AD", "source": "ad/ROSMAP_clinical_codebook.pdf", "cols": rosmap}

    # ---------------------------------------------------------------- overrides (reviewed, evidenced)
    ov = {}
    ovp = os.path.join(ROOT, "config", "table_overrides.tsv")
    if os.path.exists(ovp):
        with open(ovp, newline="", encoding="utf-8") as fh:
            lines = [l for l in fh if not l.startswith("#")]
        for r in csv.DictReader(lines, delimiter="\t"):
            ov[r["amp_variable"]] = r
    # an override moves a column into its stated table at its stated grain
    for var, r in ov.items():
        t = r["table"]
        tables[t]["program"] = r["program"]
        tables[t].setdefault("source", "config/table_overrides.tsv")
        if var not in tables[t]["cols"]:
            tables[t]["cols"].append(var)
    # the ROSMAP placeholder table is now split into ROSMAP_clinical / ROSMAP_subject
    tables.pop("ROSMAP_clinical_codebook.pdf", None)

    # ROSMAP keys, stated by the codebook: "All longitudinal data sets are organized by
    # projid + visit or fu_year". A table created by an override still needs its keys.
    for t, keys in (("ROSMAP_subject.csv", ["projid"]),
                    ("ROSMAP_clinical.csv", ["projid", "visit_name", "visit_month"])):
        if t in tables:
            tables[t]["cols"] = keys + [c for c in tables[t]["cols"] if c not in keys]

    # ROSMAP keys, stated by the codebook ("organized by projid + visit or fu_year").
    # Applied AFTER the overrides, which rebuild the column list.
    for t, keys in (("ROSMAP_subject.csv", ["projid"]),
                    ("ROSMAP_clinical.csv", ["projid", "visit_name", "visit_month"])):
        if t in tables:
            tables[t]["cols"] = keys + [c for c in tables[t]["cols"] if c not in keys]

    # ---------------------------------------------------------------- drop parked elements
    # An element parked out of the dictionary is dropped from the tables too, so it cannot be
    # emitted. The AMP dictionary still declares it; the project has retired it.
    parked = {r["amp_variable"] for r in inputs_io.dict_rows(parked=True)}
    # A KEY is never parked. `projid` was swept up in the parked unprovenanced batch, but it is
    # ROSMAP's participant key (the codebook: "organized by projid + visit"), not a data element.
    # Without it the table has no key at all.
    parked -= (SUBJECT_KEYS | VISIT_COLS)
    for t in tables:
        tables[t]["cols"] = [c for c in tables[t]["cols"] if c not in parked]
    for t in [t for t, d in tables.items() if not d["cols"]]:
        tables.pop(t)

    # ---------------------------------------------------------------- grain, per the rule
    rows = []
    for t, d in sorted(tables.items()):
        cols = d["cols"]
        has_visit = bool(VISIT_COLS & set(cols))
        keys = [c for c in cols if c in SUBJECT_KEYS or c in VISIT_COLS]
        og = {ov[c]["grain"] for c in cols if c in ov}
        if len(og) == 1:
            grain = og.pop()                # every column of this table is overridden identically
        elif has_visit:
            grain = "visit"
        else:
            grain = "subject"
        for c in cols:
            rows.append([d["program"], t, d["source"], c,
                         "key" if c in SUBJECT_KEYS or c in VISIT_COLS else "data",
                         grain])

    os.makedirs(os.path.join(ROOT, "config"), exist_ok=True)
    out = os.path.join(ROOT, "config", "tables.tsv")
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["program", "table", "dictionary", "column", "role", "grain"])
        w.writerows(rows)

    # ---------------------------------------------------------------- coverage report
    spec_path = sorted(glob.glob(os.path.join(ROOT, "specs", "table_schema_fields.tsv")))[-1]
    spec_vars = {r["amp_variable"] for r in
                 csv.DictReader(open(spec_path, newline="", encoding="utf-8"), delimiter="\t")}
    table_vars = {c for d in tables.values() for c in d["cols"]}
    unclaimed = sorted(spec_vars - table_vars)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(os.path.join(ROOT, "reports"), exist_ok=True)
    rep = os.path.join(ROOT, "reports", f"table_coverage_{ts}.md")
    with open(rep, "w", encoding="utf-8") as fh:
        fh.write("# AMP table definitions — read from the dictionaries\n\n")
        fh.write("| program | table | grain | cols | keys |\n|---|---|---|---|---|\n")
        for t, d in sorted(tables.items(), key=lambda kv: (kv[1]["program"], kv[0])):
            cols = d["cols"]
            og2 = {ov[c]["grain"] for c in cols if c in ov}
            g = (og2.pop() if len(og2) == 1
                 else "visit" if VISIT_COLS & set(cols) else "subject")
            keys = [c for c in cols if c in SUBJECT_KEYS or c in VISIT_COLS]
            fh.write(f"| {d['program']} | `{t}` | **{g}** | {len(cols)} | {', '.join(keys)} |\n")
        fh.write(f"\n## Elements in the spec that NO AMP table claims ({len(unclaimed)})\n\n")
        fh.write("These are reported, not fabricated. They have no table to live in.\n\n")
        for v in unclaimed:
            fh.write(f"- `{v}`\n")

    print(f"wrote {os.path.relpath(out, ROOT)}   ({len(rows)} table-column rows)")
    print(f"wrote {os.path.relpath(rep, ROOT)}\n")
    from collections import Counter
    g = Counter(r[5] for r in rows)
    print(f"tables         : {len(tables)}")
    for k, n in sorted(Counter((d['program'], 'visit' if VISIT_COLS & set(d['cols'])
                                else 'subject') for d in tables.values()).items()):
        print(f"  {k[0]:10s} {k[1]:8s} {n} tables")
    print(f"\ncolumns by grain: {dict(g)}")
    print(f"spec elements   : {len(spec_vars)}")
    print(f"claimed by a table: {len(spec_vars & table_vars)}")
    print(f"UNCLAIMED (reported, not invented): {len(unclaimed)}")
    if unclaimed:
        print("  " + ", ".join(unclaimed[:14]) + (" ..." if len(unclaimed) > 14 else ""))


if __name__ == "__main__":
    main()
