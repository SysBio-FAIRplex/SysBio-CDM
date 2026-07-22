#!/usr/bin/env python3
"""
Build the AMP-RA/SLE tables and specs from the ARK data model.

ARK is AMP-RA/SLE's own dictionary and it is a proper one:

    ark.all_attributes.csv              111 attributes: Description, Valid Values, columnType,
                                        Minimum, Maximum, Pattern, Required
    model_templates/*.csv               30 TABLES -- the header row IS the column list
    ark.metadata_template_primary_keys  the key of each template

It declares CDASI, PASI, VASI, VETI, VIDA -- the disease-activity scores that were parked with the
unprovenanced batch. ARK establishes their provenance: they are real AMP-RA/SLE elements.

Only the SUBJECT-facing templates are used. The other 25 templates are file annotations for omics
outputs (fastq, FCS, Olink, scRNA-seq ...) -- they describe files, not participants.

Emits:
    config/tables_ark.tsv     table / column / role / grain, same shape as config/tables.tsv
    specs/ark_fields_<ts>.tsv Table Schema field descriptors for ark's attributes
    reports/ark_coverage_<ts>.md
"""
import csv
import json
import os
from datetime import datetime

import inputs_io  # self-contained reads (replaces the sysbio_etl DB)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARK = os.path.join(ROOT, "inputs", "amp_dictionaries", "ark", "data_model-main")

# Templates that describe a PARTICIPANT. Everything else in model_templates/ annotates an omics
# FILE (fastq / FCS / Olink / scRNA-seq / snATAC ...), which is not subject data.
SUBJECT_TEMPLATES = {
    "ark.ClinicalMetadataTemplate.csv": "ClinicalMetadataTemplate.csv",
    "ark.BiospecimenMetadataTemplate.csv": "BiospecimenMetadataTemplate.csv",
}

# ARK's `visitID` is "Ordinal ID distinguishing different patient visits", so the clinical table
# has one row per participant-visit. The primary_keys file names `individualID` as the entity
# identifier; it is not a uniqueness constraint over the table.
GRAIN = {
    "ClinicalMetadataTemplate.csv": ("visit", ["individualID", "visitID"]),
    "BiospecimenMetadataTemplate.csv": ("subject", ["individualID", "biospecimenID"]),
}


def field(name, type_, enum=None, minimum=None, maximum=None):
    f = {"name": name, "type": type_}
    c = {}
    if enum:
        c["enum"] = enum
    if minimum is not None:
        c["minimum"] = minimum
    if maximum is not None:
        c["maximum"] = maximum
    if c:
        f["constraints"] = c
    return f


def sb_ranges():
    """Ranges from the SysBio rows that were parked with the unprovenanced batch.

    ARK declares CDASI / PASI / VASI / VETI / VIDA and age -- so they are NOT unprovenanced; ARK
    IS their provenance. But ARK states no range for them (columnType=string, no Valid Values).
    The parked SysBio rows do:  CDASI 0-100, PASI 0-72, VASI 0-100, VETI 0-100, VIDA 0-6,
    age 0-120. The two sources are complementary: ARK gives the tables, keys and enums; SysBio
    gives the bounds. Neither is invented.
    """
    import re
    rng = {}
    for r in inputs_io.dict_rows(parked=True):
        if r["source"] != "AMP-RA-SLE":
            continue
        m = re.search(r"(-?\d+(?:\.\d+)?)\s*-\s*(-?\d+(?:\.\d+)?)", r["amp_value_set"] or "")
        if m:
            rng[r["amp_variable"]] = (float(m.group(1)), float(m.group(2)))
    return rng


SB_RANGE = None


# ARK's annotation_maps/*.csv are properly-quoted, authoritative value lists. The model's own
# `Valid Values` field is a COMMA-JOINED string, which physically cannot represent a value that
# CONTAINS a comma -- and 123 Cell Ontology labels do ('CD4-positive, alpha-beta T cell'). Splitting
# it on commas shattered them into fragments: 'human', 'CD25-positive', 'alpha-beta regulatory
# T cell' all became enum members in their own right (2551 members for a 2388-value list).
#
# So where a map declares an attribute AND its values contain commas, the MAP is the value set.
# Where they do not (anatomicalSite, biospecimenType), the model's list is fine and is kept --
# a map is a crosswalk, not always the full value set (diagnosis-DOID holds only the 11 diagnoses
# that HAVE a DOID, but ARK's diagnosis has 16 values including 'control' and 'unknown').
def map_value_sets():
    import glob
    out = {}
    for fp in glob.glob(os.path.join(ARK, "annotation_maps", "*.csv")):
        rows = list(csv.DictReader(open(fp, newline="", encoding="utf-8-sig")))
        for col in (rows[0].keys() if rows else []):
            vals = [r[col] for r in rows if r.get(col)]
            if any("," in v for v in vals):          # the model's comma-joined form cannot hold it
                out[col] = sorted(set(vals))
    return out


MAPPED = None


def instrument_ranges():
    """config/instrument_ranges.tsv -- ranges the SOURCE omits but the INSTRUMENT defines.
    Applied only where ARK is silent, and only with the citation the file carries."""
    out = {}
    fp = os.path.join(ROOT, "config", "instrument_ranges.tsv")
    if os.path.exists(fp):
        for line in open(fp, encoding="utf-8"):
            if line.startswith("#") or not line.strip():
                continue
            c = line.rstrip("\n").split("\t")
            if len(c) >= 5 and c[0] == "ark":      # scoped: `height` also exists in CMD, in cm
                out[c[1]] = (c[2], float(c[3]), float(c[4]))
    return out


INSTR = None


def spec_from_ark(a):
    """One ARK attribute -> a Table Schema field descriptor. Nothing is invented."""
    global MAPPED, INSTR
    if MAPPED is None:
        MAPPED = map_value_sets()
    if INSTR is None:
        INSTR = instrument_ranges()
    name = a["Attribute"]
    if name in INSTR:                       # ARK states no range; the instrument does
        t, lo, hi = INSTR[name]
        cast = int if t == "integer" else float
        return field(name, t, minimum=cast(lo), maximum=cast(hi))
    ct = (a.get("columnType") or "").strip().lower()
    vv = (a.get("Valid Values") or "").strip()
    mn = (a.get("Minimum") or "").strip()
    mx = (a.get("Maximum") or "").strip()

    if name in MAPPED:
        return field(name, "string", enum=MAPPED[name])   # ARK's own quoted map -- see above
    if vv:
        vals = [v.strip() for v in vv.split(",") if v.strip()]
        return field(name, "string", enum=vals)
    if ct in ("integer", "int"):
        return field(name, "integer",
                     minimum=int(mn) if mn else None, maximum=int(mx) if mx else None)
    if ct in ("number", "float", "double"):
        lo = float(mn) if mn else (SB_RANGE.get(name) or (None, None))[0]
        hi = float(mx) if mx else (SB_RANGE.get(name) or (None, None))[1]
        return field(name, "number", minimum=lo, maximum=hi)
    # ARK types the disease-activity scores (CDASI, PASI, VASI, VIDA) as `string` and gives no
    # values. They are numeric indices; the parked SysBio rows carry their ranges.
    if name in SB_RANGE:
        lo, hi = SB_RANGE[name]
        is_int = lo == int(lo) and hi == int(hi)
        return field(name, "integer" if is_int else "number",
                     minimum=int(lo) if is_int else lo, maximum=int(hi) if is_int else hi)
    return field(name, "string")          # string / string_list / unstated


def main():
    global SB_RANGE
    SB_RANGE = sb_ranges()
    attrs = {r["Attribute"]: r for r in csv.DictReader(
        open(os.path.join(ARK, "ark.all_attributes.csv"), newline="", encoding="utf-8-sig"))}

    rows, specs, gaps = [], [], []
    for fname, table in sorted(SUBJECT_TEMPLATES.items()):
        path = os.path.join(ARK, "model_templates", fname)
        cols = next(csv.reader(open(path, newline="", encoding="utf-8-sig")))
        grain, keys = GRAIN[table]
        for c in cols:
            if c == "Component":          # schematic's own template marker, not data
                continue
            a = attrs.get(c)
            if not a:
                gaps.append((table, c, "not in ark.all_attributes"))
                continue
            rows.append(["AMP-RA-SLE", table, "ark/model_templates/" + fname, c,
                         "key" if c in keys else "data", grain])
            f = spec_from_ark(a)
            specs.append([c, json.dumps(f, ensure_ascii=False, separators=(",", ":")),
                          f"AMP:ark/{fname}", (a.get("Description") or "")[:110]])
            cons = f.get("constraints", {})
            if not cons and f["type"] == "string":
                gaps.append((table, c, f"ARK declares columnType={a.get('columnType')!r} "
                                       f"with NO valid values and no range — values not specified"))
            elif f["type"] in ("integer", "number") and "minimum" not in cons:
                gaps.append((table, c, f"numeric, ARK states no Minimum/Maximum"))

    os.makedirs(os.path.join(ROOT, "config"), exist_ok=True)
    tpath = os.path.join(ROOT, "config", "tables_ark.tsv")
    with open(tpath, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["program", "table", "dictionary", "column", "role", "grain"])
        w.writerows(rows)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    spath = os.path.join(ROOT, "specs", "ark_fields.tsv")
    with open(spath, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["amp_variable", "table_schema_field", "spec_origin", "description"])
        w.writerows(sorted(set(map(tuple, specs))))

    rpath = os.path.join(ROOT, "reports", f"ark_coverage_{ts}.md")
    with open(rpath, "w", encoding="utf-8") as fh:
        fh.write("# AMP-RA/SLE from the ARK data model\n\n")
        fh.write("| table | grain | columns | keys |\n|---|---|---|---|\n")
        for t, (g, k) in GRAIN.items():
            n = sum(1 for r in rows if r[1] == t)
            fh.write(f"| `{t}` | **{g}** | {n} | {', '.join(k)} |\n")
        fh.write(f"\n## Elements ARK does not fully specify ({len(gaps)})\n\n")
        fh.write("Reported, not invented.\n\n")
        for t, c, why in gaps:
            fh.write(f"- **`{c}`** ({t}) — {why}\n")

    from collections import Counter
    print(f"tables  : {len(GRAIN)}   ({', '.join(GRAIN)})")
    print(f"columns : {len(rows)}")
    print(f"specs   : {len(set(map(tuple, specs)))} distinct ARK attributes")
    kinds = Counter(json.loads(s[1])["type"] for s in specs)
    print(f"types   : {dict(kinds)}")
    enums = sum(1 for s in specs if "enum" in json.loads(s[1]).get("constraints", {}))
    print(f"with an enum : {enums}")
    print(f"\nNOT fully specified by ARK: {len(gaps)}")
    for t, c, why in gaps:
        print(f"  {c:18s} {why}")
    print(f"\nwrote config/tables_ark.tsv, {os.path.relpath(spath, ROOT)}, "
          f"{os.path.relpath(rpath, ROOT)}")


if __name__ == "__main__":
    main()
