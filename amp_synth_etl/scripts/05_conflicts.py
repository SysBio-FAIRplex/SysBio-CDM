#!/usr/bin/env python3
"""
Every data element where the AMP program dictionary and the SysBio dictionary DISAGREE.

Three layers can disagree, and each disagreement is a place a value can be right in one and wrong
in another:

    SysBio dictionary   sysbio.cde_dictionary.amp_value_set        (source of truth for the spec)
    AMP dictionary      pdrd/*.csv, ad/*, ark/*                    (the program's own definition)
    generator           scripts/gen/batch_*.py                     (what we actually emit)

Reports, for each element:
    sb_value_set        what the SysBio dictionary says
    amp_datatype        the AMP dictionary's declared type (Integer / Float / Enumeration / String)
    amp_value_set       the AMP dictionary's own values
    spec_type           the type the spec derived
    conflict            what disagrees
    consequence         what it does to the data

Writes reports/spec_vs_dictionary_conflicts_<ts>.tsv
"""
import csv
import glob
import json
import os
from datetime import datetime

import inputs_io  # self-contained reads (replaces the sysbio_etl DB)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AMP = os.path.join(ROOT, "inputs", "amp_dictionaries")


def amp_dicts():
    out = {}
    for f in sorted(glob.glob(os.path.join(AMP, "pdrd", "*.csv"))):
        for r in csv.DictReader(open(f, newline="", encoding="utf-8-sig")):
            out.setdefault(r["ColumnName"], {
                "datatype": r["DataType"].strip(),
                "values": (r["UniqueValues"] or r["DataTypeRange"] or "").strip(),
                "file": f"pdrd/{os.path.basename(f)}"})
    p = os.path.join(AMP, "ad", "DiverseCohorts_parsed_dictionary.tsv")
    for r in csv.DictReader(open(p, newline="", encoding="utf-8-sig"), delimiter="\t"):
        out.setdefault(r["ColumnName"], {
            "datatype": "", "values": (r["Values"] or "").strip(),
            "file": "ad/DiverseCohorts_parsed_dictionary.tsv"})
    return out


def members(s):
    """Split a value set into its members, keeping the source's own case and spelling."""
    import re
    return [t.strip() for t in re.split(r"[|;]", s or "") if t.strip()]


def norm(s):
    """Case-insensitive member set, for COMPARISON only. Never used for display."""
    return {m.lower() for m in members(s)}


def main():
    sb = {v: {"amp_variable": v, "amp_value_set": r["sb_value_set"],
              "f": json.loads(r["table_schema_field"]) if r["table_schema_field"] else {}}
          for v, r in inputs_io.specs_by_variable().items()}
    amp = amp_dicts()

    rows = []
    for var, r in sorted(sb.items()):
        a = amp.get(var)
        if not a:
            continue
        f = r["f"] or {}
        spec_type = f.get("type", "")
        c = f.get("constraints", {})
        sbv, ampv = r["amp_value_set"], a["values"]
        conflicts, consequence = [], []

        # 1. int/float disagreement
        if a["datatype"] == "Float" and spec_type == "integer":
            conflicts.append("AMP says Float, spec says integer")
            consequence.append("generator emits 30.1; spec rejects it as non-integer")
        if a["datatype"] == "Integer" and spec_type == "number":
            conflicts.append("AMP says Integer, spec says number")
            consequence.append("generator may emit a decimal where the source has whole numbers")

        # 2. value-set membership disagreement
        if sbv and ampv and a["datatype"] in ("Enumeration", ""):
            s_set, a_set = norm(sbv), norm(ampv)
            if s_set and a_set and s_set != a_set:
                # display the FULL member list in the source's own words -- no truncation,
                # no lowercasing. The report is what gets reviewed; it must not misrepresent.
                sb_only = [m for m in members(sbv) if m.lower() not in a_set]
                amp_only = [m for m in members(ampv) if m.lower() not in s_set]
                conflicts.append("value sets differ")
                if sb_only:
                    consequence.append("only in SysBio: " + " | ".join(sb_only))
                if amp_only:
                    consequence.append("only in AMP: " + " | ".join(amp_only))

        # 3. AMP enumerates, SysBio does not (or vice versa)
        if a["datatype"] == "Enumeration" and ampv and not sbv:
            conflicts.append("AMP enumerates values; SysBio value set is EMPTY")
            consequence.append("spec has no enum; values would be invented")
        if sbv and not ampv and a["datatype"] == "String":
            conflicts.append("SysBio enumerates values; AMP declares a bare String")
            consequence.append("SysBio is richer — the spec uses it (frozen precedence)")

        if conflicts:
            rows.append([var, sbv[:80], a["datatype"], ampv[:80], spec_type,
                         c.get("minimum", ""), c.get("maximum", ""),
                         " ; ".join(conflicts), " ; ".join(consequence), a["file"]])

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(ROOT, "reports", f"spec_vs_dictionary_conflicts_{ts}.tsv")
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["amp_variable", "sb_value_set", "amp_datatype", "amp_value_set",
                    "spec_type", "spec_min", "spec_max", "conflict", "consequence",
                    "amp_dictionary_file"])
        w.writerows(rows)

    from collections import Counter
    print(f"elements compared : {sum(1 for v in sb if v in amp)}")
    print(f"CONFLICTS         : {len(rows)}\n")
    kinds = Counter(c for r in rows for c in r[7].split(" ; "))
    for k, n in kinds.most_common():
        print(f"  {n:4d}  {k}")
    print(f"\nwrote {os.path.relpath(out, ROOT)}")


if __name__ == "__main__":
    main()
