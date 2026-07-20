#!/usr/bin/env python3
"""
Build a Frictionless Table Schema FIELD DESCRIPTOR for every SysBio Dictionary row, plus
`example_source_value` -- a value read back out of the descriptor showing how that variable is
expected to appear in the AMP program's original source data.

STANDARD: Frictionless Table Schema (https://specs.frictionlessdata.io/table-schema/).
Chosen because it is the recognised standard for describing the columns of a tabular data
dictionary, and because it carries `categories` -- a first-class code->label map, which is the
whole reason this column exists and the one thing plain JSON Schema cannot express natively.

FIELD DESCRIPTOR (the value of `table_schema_field`):
  {"name": "<amp_variable>",
   "type": "integer" | "number" | "string" | "date" | "boolean" | "any",
   "constraints": {"enum": [...], "minimum": <n>, "maximum": <n>},   # only what the source states
   "categories": [{"value": <code>, "label": "<label>"}, ...]}       # coded value sets only

  type          integer/number   a numeric column
                string           free text, identifiers, and label-valued enumerations
                date             ISO date (format defaults to %Y-%m-%d)
                any              the source does not state a type
  constraints.enum        the legal cell values, verbatim from the source
  constraints.minimum/maximum   the range, only when the source gives one
  categories    present iff the source assigns a CODE to each value. `value` is what the data
                cell holds; `label` is what it means. Where the source lists a bare value with no
                code (e.g. "missing or unknown"), value == label, per the AMP convention.

SOURCES (inputs/amp_dictionaries -- vendored in-repo):
  pdrd/*.csv    24 AMP-PD/PDRD instrument dictionaries: DataType | DataTypeRange | UniqueValues
  ad/DiverseCohorts_parsed_dictionary.tsv    AMP-AD: Values (";"-delimited, "22 = E2E2; ...")
  ark/data_model-main/ark.all_attributes.csv AMP-RA/SLE: Valid Values (","), columnType
  ROSMAP_clinical_codebook.pdf   not re-parsed; where the SysBio Dictionary names it as
                                 source_file, its value set is taken as matching the codebook.

Where no AMP source covers a variable the SysBio value set is parsed instead, and the row is
marked `sb_fallback`.

Also writes one real Table Schema document per AMP source dictionary, so the output is usable by
any Frictionless tool.

READ-ONLY against the DB. Does not modify sysbio.cde_dictionary.

PRECEDENCE — FROZEN 2026-07-13. Do not change without saying so out loud.

    sysbio.cde_dictionary.amp_value_set IS THE SOURCE OF TRUTH for the spec.

The AMP program dictionaries are used to CORRECT that column (amyCerad and braaksc were fixed
that way), never to override it at build time. Overriding produced specs that disagreed with the
dictionary they claim to describe -- Braak, amyThal and amyAny each ended up with an enum the
dictionary does not list, and QC failed 988 cells.

This rule was rewritten four times in one session. Each rewrite silently rebuilt all 445 field
descriptors underneath a review that was already done. That is why it is frozen and why the specs
are now versioned instead of overwritten.
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
SPECS = os.path.join(ROOT, "specs")
AMP = os.path.join(ROOT, "inputs", "amp_dictionaries")
PDRD = os.path.join(AMP, "pdrd")
AD_TSV = os.path.join(AMP, "ad", "DiverseCohorts_parsed_dictionary.tsv")
ARK = os.path.join(AMP, "ark", "data_model-main", "ark.all_attributes.csv")
ROSMAP_FILE = "ROSMAP_clinical_codebook.pdf"

NUM_RANGE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*-\s*(-?\d+(?:\.\d+)?)\s*$")

# DiverseCohortsOutcomes.pdf. These two are absent from DiverseCohorts_parsed_dictionary.tsv, so
# without this they fall through to the SysBio value set -- whose ADoutcome entry is corrupted (a
# prior session's programmatic "fix" injected a `|`, so the three newline-separated criteria read
# as two mangled categories). The PDF states the derivation criteria; the DATA carries the
# resulting class, which is what a Table Schema describes.
DC_OUTCOMES = {
    "ADoutcome": ["AD", "Control", "Other"],
    "derivedOutcomeBasedOnMayoDx": ["AD", "Control", "Other"],
    "mayoDx": ["AD", "Control", "other", "not applicable"],
}

# ROSMAP_clinical_codebook.pdf (RADC data set 754), transcribed rather than re-parsed each run.
# The SysBio value sets for these were rewritten at some point and LOST THEIR STORED CODES:
#   msex     SysBio "Male | Female | M | F | Unknown"  -- codes gone, M/F/Unknown not in the source
#   spanish  SysBio "True | False | 1 | 0"             -- source codes are 1=Yes, 2=No
# The data cell holds the CODE, so a spec built from the SysBio text would tell an ETL to read the
# wrong thing. Only the two variables the user authorised are corrected here.
#   braaksc  SysBio "0 | I | II | III | IV | V | VI"   -- those are the LABELS; the cell holds 0-6
ROSMAP_CODED = {
    "msex": {1: "Male", 0: "Female"},
    "spanish": {1: "Yes", 2: "No"},
    "braaksc": {0: "0", 1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI"},
}


# Tokens the AMP sources use to mark a value as absent. They are declared as `missingValues`,
# NOT as enum members: a reader turns them into null, so a coded column stays `integer` instead of
# being forced to `string` by the presence of a phrase. No in-band sentinel is ever minted.
#
# "not applicable" is deliberately NOT here -- in mayoDx it is a real category ("participant is not
# from a Mayo Clinic cohort"), not a missing marker.
MISSING_TOKENS = {"na", "n/a", "missing", "unknown", "missing or unknown", "not available"}


def is_missing(tok):
    """Always False.

    The synthetic files are a faithful copy of the AMP SOURCE. A cell in a real AMP file contains
    the literal string 'missing or unknown' / 'Unknown' / 'NA', so the synthetic file must too.
    Filing those under `missingValues` removed them from the enum and gave amyThal 6 values where
    the AMP file lists 7.

    Nulling them is an ETL decision, made downstream against the target schema. It is not a
    property of the source and must not be baked into the source spec.
    """
    return False


def field(name, type_, enum=None, minimum=None, maximum=None, categories=None,
          missing_values=None):
    """Assemble a Table Schema field descriptor, omitting anything the source does not state."""
    f = {"name": name, "type": type_}
    constraints = {}
    if enum:
        constraints["enum"] = enum
    if minimum is not None:
        constraints["minimum"] = minimum
    if maximum is not None:
        constraints["maximum"] = maximum
    if constraints:
        f["constraints"] = constraints
    if categories:
        f["categories"] = categories
    if missing_values:
        f["missingValues"] = missing_values
    return f


def as_number(tok):
    """Cast a code to int/float when it is numeric, so `type` and the cell values agree."""
    try:
        return int(tok)
    except ValueError:
        try:
            return float(tok)
        except ValueError:
            return tok


def parse_values(text, delim=";"):
    """Split a source value list into (pairs, missing).

    'X = label' -> (X, label). A bare token that is not a missing marker -> (token, token): the
    value and its label are the same thing. A bare missing marker is separated out; it becomes
    `missingValues`, never a category.
    """
    pairs, missing = [], []
    for p in [p.strip() for p in text.split(delim) if p.strip()]:
        if "=" in p:
            k, lab = p.split("=", 1)
            pairs.append((k.strip(), lab.strip()))
        else:
            pairs.append((p, p))          # a bare value IS a value; nothing is diverted
    return pairs, missing


def enum_field(name, text, delim=";"):
    """A value-set column -> enum + categories (value -> label) + missingValues.

    `categories` is emitted for every enumeration. Where the source assigns a code the value is
    that code; where it does not, value == label. Type is `integer` when every value is an
    integer -- which is what keeps a coded column numeric once the missing markers are pulled out.
    """
    pairs, missing = parse_values(text, delim)
    if not pairs:
        return field(name, "any", missing_values=missing or None)
    # Cast the codes all-or-nothing. Casting per token would emit a MIXED enum whenever one value
    # merely looks numeric -- braaksc's labels are "0, I, II, ... VI", and casting only the "0"
    # produced [0,"I","II",...], which then forces the whole field to `string`.
    raw = [v for v, _ in pairs]
    numeric = all(re.fullmatch(r"-?\d+", v) for v in raw)
    vals = [int(v) for v in raw] if numeric else raw
    cats = [{"value": v, "label": lab} for v, (_, lab) in zip(vals, pairs)]
    return field(name, "integer" if numeric else "string", enum=vals, categories=cats,
                 missing_values=missing or None)


# ------------------------------------------------------------------ AMP source readers

def read_pdrd():
    out = {}
    for f in sorted(glob.glob(os.path.join(PDRD, "*.csv"))):
        for r in csv.DictReader(open(f, newline="", encoding="utf-8-sig")):
            out.setdefault(r["ColumnName"], (r, os.path.basename(f)))
    return out


def field_pdrd(name, r):
    dt = (r.get("DataType") or "").strip()
    rng = (r.get("DataTypeRange") or "").strip()
    uv = (r.get("UniqueValues") or "").strip()
    if dt == "Enumeration":
        return enum_field(name, uv) if uv else field(name, "any")
    if dt in ("Integer", "Float"):
        type_ = "integer" if dt == "Integer" else "number"
        m = NUM_RANGE.match(rng)
        if m:
            cast = int if dt == "Integer" else float
            return field(name, type_, minimum=cast(float(m.group(1))),
                         maximum=cast(float(m.group(2))))
        # UniqueValues may list several assay-specific ranges (test_value). Those are ranges, not
        # categories: the column stays numeric and unbounded.
        return field(name, type_)
    if dt == "String":
        return field(name, "string")
    return field(name, "any")


def read_ad():
    out = {}
    for r in csv.DictReader(open(AD_TSV, newline="", encoding="utf-8-sig"), delimiter="\t"):
        out.setdefault(r["ColumnName"], r)
    if "apoeGenotype" in out:                       # camelCase in the PDF, snake_case in SysBio
        out.setdefault("apoe_genotype", out["apoeGenotype"])
    return out


def field_ad(name, r):
    """AMP-AD. An EMPTY Values cell means the source states no value set -- the column is an
    identifier or a free measurement (individualID, pmi, ageDeath). This dictionary carries no
    DataType column, so it cannot say which. Emit `any` and let untyped_elements.tsv declare it;
    do NOT fall back to the SysBio prose, which is the layer we know to be corrupt."""
    v = (r.get("Values") or "").strip()
    return enum_field(name, v) if v else field(name, "any")


def read_ark():
    return {r["Attribute"]: r for r in csv.DictReader(open(ARK, newline="", encoding="utf-8-sig"))}


def field_ark(name, r):
    vv = (r.get("Valid Values") or "").strip()
    ct = (r.get("columnType") or "").strip().lower()
    if vv:
        return enum_field(name, vv, ",")
    if ct in ("integer", "int"):
        return field(name, "integer")
    if ct in ("number", "float", "double", "decimal"):
        return field(name, "number")
    if ct in ("string", "text"):
        return field(name, "string")
    return field(name, "any")


# ------------------------------------------------------------------ SysBio fallback

def field_sb(name, vs):
    v = (vs or "").strip()
    if not v:
        return field(name, "any")
    low = v.lower()
    if low in ("required", "nullable", "optional"):
        return field(name, "any")
    if low in ("string", "text", "free text", "identifier"):
        return field(name, "string")
    if low == "continuous":
        # the source states a continuous measure and no bounds
        return field(name, "number")

    try:
        m = json.loads(v)
        if isinstance(m, dict) and m:
            cats = [{"value": as_number(k), "label": str(x)} for k, x in m.items()
                    if not is_missing(k)]
            miss = [k for k in m if is_missing(k)]
            vals = [c["value"] for c in cats]
            type_ = "integer" if all(isinstance(x, int) for x in vals) else "string"
            return field(name, type_, enum=vals, categories=cats, missing_values=miss or None)
    except Exception:
        pass

    # "[0-30] | NA" -- a bracketed range, optionally followed by missing markers
    m = re.match(r"^\[\s*(-?\d+(?:\.\d+)?)\s*-\s*(-?\d+(?:\.\d+)?)\s*\]", v)
    if m:
        a, b = m.group(1), m.group(2)
        is_int = "." not in a and "." not in b
        cast = int if is_int else float
        miss = [t.strip() for t in re.split(r"[|;,]", v)[1:] if t.strip() and is_missing(t)]
        f = field(name, "integer" if is_int else "number",
                  minimum=cast(float(a)), maximum=cast(float(b)))
        if miss:
            f["missingValues"] = miss
        return f

    # "0-3 (0=<5%, 1=5-33%, ...)" -- must precede the bare-range rule
    m = re.match(r"^-?\d+\s*-\s*-?\d+\s*\((.+)\)$", v)
    if m and len(re.findall(r"(-?\d+)\s*=", m.group(1))) >= 2:
        pairs = re.findall(r"(-?\d+)\s*=\s*([^,)]+)", m.group(1))
        cats = [{"value": as_number(k), "label": lab.strip()} for k, lab in pairs]
        return field(name, "integer", enum=[c["value"] for c in cats], categories=cats)

    for delim in ("|", ";", ","):
        if delim in v:
            pairs, _ = parse_values(v, delim)
            if len(pairs) >= 2 and all("=" in p for p in v.split(delim) if p.strip()
                                       and not is_missing(p)):
                return enum_field(name, v, delim)

    m = re.match(r"^range\s*:?\s*(-?\d+(?:\.\d+)?)\s*-\s*(-?\d+(?:\.\d+)?)", low) or NUM_RANGE.match(v)
    if m:
        a, b = m.group(1), m.group(2)
        is_int = "." not in a and "." not in b
        cast = int if is_int else float
        return field(name, "integer" if is_int else "number",
                     minimum=cast(float(a)), maximum=cast(float(b)))

    if "iso 8601" in low or re.search(r"yyyy\s*-\s*mm\s*-\s*dd", low):
        return field(name, "date")

    m = re.match(r"^enumerat\w*(?:\s+values)?\s*:\s*(.+)$", v, re.I)
    if m and "," in m.group(1):
        return enum_field(name, m.group(1), ",")

    m = re.search(r"\(\s*e\.g\.?,?\s*(.+?)\s*\)$", v, re.I)
    if m and "," in m.group(1):
        return enum_field(name, m.group(1), ",")

    for delim in ("|", ";", ","):
        parts = [p.strip() for p in v.split(delim) if p.strip()]
        if len(parts) >= 2 and all(len(p) <= 40 for p in parts):
            return enum_field(name, v, delim)

    if any(k in low for k in ("unique", "identifier", "free text", "free-text")):
        return field(name, "string")

    return field(name, "any")


# ------------------------------------------------------------------ descriptor -> example

def example_source_value(f):
    """Read a value back out of the descriptor: what an AMP source data cell holds."""
    c = f.get("constraints", {})
    if f.get("categories"):
        return str(f["categories"][0]["value"])
    if c.get("enum"):
        return str(c["enum"][0])
    if f["type"] in ("integer", "number"):
        lo, hi = c.get("minimum"), c.get("maximum")
        if lo is None:
            return ""
        mid = (lo + hi) / 2
        return str(int(mid)) if f["type"] == "integer" else f"{mid:.1f}"
    if f["type"] == "date":
        return "2014-03-22"
    if f["type"] == "string":
        return f"{f['name']}_0001"
    return ""


TYPES = {"integer", "number", "string", "date", "boolean", "any"}


ALLOWED = {"name", "type", "constraints", "categories", "missingValues"}


def validate(f):
    if set(f) - ALLOWED:
        return f"unexpected keys: {sorted(set(f) - ALLOWED)}"
    if f.get("type") not in TYPES:
        return f"type {f.get('type')!r} not a Table Schema type"
    c = f.get("constraints", {})
    if set(c) - {"enum", "minimum", "maximum"}:
        return f"unexpected constraints: {sorted(set(c) - {'enum', 'minimum', 'maximum'})}"
    if "minimum" in c and "maximum" in c and c["minimum"] > c["maximum"]:
        return "minimum > maximum"
    for cat in f.get("categories", []):
        if set(cat) != {"value", "label"}:
            return "each category must be {value, label}"
    if f.get("categories") and "enum" in c:
        if [x["value"] for x in f["categories"]] != c["enum"]:
            return "categories values and constraints.enum disagree"
    return ""


def main():
    pdrd, ad, ark = read_pdrd(), read_ad(), read_ark()
    # CDE dictionary, from the vendored inputs/cde_dictionary.tsv (active rows only). Replaces a
    # read of sysbio.cde_dictionary; a NULL column reads as '' here, matching the old coalesce.
    sb = inputs_io.dict_rows(parked=False)

    rows, invalid = [], 0
    seen_vars = set()
    schemas = defaultdict(dict)          # source dictionary -> {amp_variable: field descriptor}
    for row in sb:
        cde_id, var = row["cde_id"], row["amp_variable"]
        source, source_file, vs = row["source"], row["source_file"], row["amp_value_set"]
        # ── PRECEDENCE (FROZEN 2026-07-13) ────────────────────────────────────────────────
        # sysbio.cde_dictionary.amp_value_set IS THE SOURCE OF TRUTH.
        # The AMP program dictionaries are used to CORRECT that column (amyCerad, braaksc were
        # fixed that way), never to override it here. Overriding gave Braak / amyThal / amyAny
        # enums the dictionary does not list, and QC failed 988 cells.
        # Do not reorder these branches without saying so out loud.
        sb = field_sb(var, vs) if vs.strip() else None
        if sb is not None and sb["type"] != "any":
            f, origin = sb, "SB:amp_value_set"
            # NARROW EXCEPTION to the frozen precedence, and the only one.
            # The dictionary writes a range as "1 - 51". That notation has no way to say whether
            # the column is a float -- the decimal point is the only signal, and the dictionary
            # does not use one. The AMP dictionary DOES say: DataType = Float. So the AMP file is
            # the authority on int-vs-float, exactly as it is the authority on which VALUES
            # appear. The bounds still come from the dictionary; only the numeric type does not.
            # This affects 87 elements (the pdq39_* scores, the DTI roi*/ref* measures, the
            # smoking and alcohol counts).
            if f["type"] == "integer" and var in pdrd:
                if pdrd[var][0].get("DataType", "").strip() == "Float":
                    c = dict(f.get("constraints", {}))
                    if "minimum" in c:
                        c["minimum"] = float(c["minimum"])
                        c["maximum"] = float(c["maximum"])
                    f = dict(f, type="number", constraints=c)
                    origin = "SB:amp_value_set + AMP:DataType=Float"
        elif var in ROSMAP_CODED:
            cats = [{"value": k, "label": lab} for k, lab in ROSMAP_CODED[var].items()]
            f = field(var, "integer", enum=[c["value"] for c in cats], categories=cats)
            origin = f"AMP:ad/{ROSMAP_FILE}"
        elif var in DC_OUTCOMES:
            vals = DC_OUTCOMES[var]
            f = field(var, "string", enum=vals,
                      categories=[{"value": x, "label": x} for x in vals])
            origin = "AMP:ad/DiverseCohortsOutcomes.pdf"
        elif var in pdrd:
            r, fname = pdrd[var]
            f, origin = field_pdrd(var, r), f"AMP:pdrd/{fname}"
        elif var in ad:
            f, origin = field_ad(var, ad[var]), "AMP:ad/DiverseCohorts_parsed_dictionary.tsv"
        elif var in ark:
            f, origin = field_ark(var, ark[var]), "AMP:ark/ark.all_attributes.csv"
        elif ROSMAP_FILE in source_file:
            f, origin = field_sb(var, vs), f"AMP:ad/{ROSMAP_FILE} (via SB)"
        else:
            f, origin = field_sb(var, vs), "SB:amp_value_set"

        # AMP-PD marks sample_type / test_name / test_units as Enumeration with an EMPTY
        # UniqueValues -- the source contradicts itself, so its value list is genuinely absent
        # there and the SysBio list is the only one. That single case still falls back. An AMP-AD
        # column with an empty Values cell does NOT: the source is simply silent, and silence is
        # answered by untyped_elements.tsv, not by the corrupt SysBio prose.
        # The AMP source can name a column and state nothing useful about it -- DataType=String
        # with an empty Values cell (mmse, smell_detail, diagnosis). Where the SysBio value set
        # DOES carry an enum or a range, it is the better spec and wins.
        amp_is_bare = (f["type"] in ("any", "string")
                       and not f.get("categories")
                       and not f.get("constraints"))
        if amp_is_bare and origin.startswith("AMP:") and vs.strip():
            fb = field_sb(var, vs)
            better = (fb.get("categories") or fb.get("constraints")
                      or (fb.get("type") not in ("any", "string")))
            if better:
                f, origin = fb, "SB:amp_value_set"

        err = validate(f)
        if err:
            invalid += 1
        status = ("unspecified" if f["type"] == "any"
                  else "amp_sourced" if origin.startswith("AMP:") else "sb_fallback")

        rows.append([cde_id, var, source,
                     json.dumps(f, ensure_ascii=False, separators=(",", ":")),
                     example_source_value(f), origin, status, err, vs])
        seen_vars.add(var)
        # The SysBio Dictionary is keyed on (amp_variable, source) -- `sex`, `race`, `GUID` etc.
        # each appear under several programs. A Table Schema describes ONE physical file, and its
        # field names must be unique, so a variable is emitted once per source dictionary.
        if origin.startswith("AMP:"):
            doc = schemas[origin.split(":", 1)[1]]
            if var not in doc:
                doc[var] = f

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(SPECS, exist_ok=True)
    # Never overwrite a spec. Each build is a new timestamped file, so a change to a field
    # descriptor is a visible diff, not a silent rewrite. Six earlier versions were destroyed
    # by `rm -rf specs/*` before this was fixed.
    out = os.path.join(SPECS, f"table_schema_fields_{ts}.tsv")
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["cde_id", "amp_variable", "sb_source", "table_schema_field",
                    "example_source_value", "spec_origin", "spec_status", "schema_error",
                    "sb_value_set"])
        w.writerows(rows)

    # real Table Schema documents, one per AMP source dictionary
    sdir = os.path.join(SPECS, f"table_schemas_{ts}")
    os.makedirs(sdir, exist_ok=True)
    for src, fields in sorted(schemas.items()):
        stem = re.sub(r"[^A-Za-z0-9]+", "_", src).strip("_")
        doc = {"$schema": "https://datapackage.org/profiles/2.0/tableschema.json",
               "name": stem.lower(), "fields": list(fields.values())}
        with open(os.path.join(sdir, f"{stem}.schema.json"), "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=2)

    from collections import Counter
    print(f"wrote {out}  ({len(rows)} rows)")
    print(f"wrote {sdir}/  ({len(schemas)} Table Schema documents)")
    print(f"schema violations: {invalid}\n")
    print("spec_status:")
    for k, n in Counter(r[6] for r in rows).most_common():
        print(f"  {k:16s} {n}")
    print("\ntype:")
    for k, n in Counter(json.loads(r[3])["type"] for r in rows).most_common():
        print(f"  {k:10s} {n}")
    print("\nfields with a code->label `categories` map: "
          f"{sum(1 for r in rows if 'categories' in json.loads(r[3]))}")


if __name__ == "__main__":
    main()
