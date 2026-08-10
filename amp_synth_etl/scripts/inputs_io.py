#!/usr/bin/env python3
"""
Read the vendored inputs. SELF-CONTAINED: no database, no external filesystem paths.

This replaces every read the generation pipeline used to make against the sysbio_etl Postgres
database. The CDE dictionary now lives in the repo:

    inputs/cde_dictionary.jsonl  the canonical dictionary (one JSON object per line); 8 AMP columns:
                                 cde_id, amp_variable, amp_variable_description, amp_value_set,
                                 amp_extended_definition_comments, amp_units, source, source_file.
                                 Vendored in-repo; no external refresh step ships here.
                                 (inputs/cde_dictionary.tsv is a legacy mirror kept identical.)

The derived transformation spec is written by 01_build_specs.py to specs/table_schema_fields*.tsv
and read back here. It used to round-trip through the DB -- that round-trip is gone; the spec
file is read directly.
"""
import csv
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DICT_JSONL = os.path.join(ROOT, "inputs", "cde_dictionary.jsonl")   # canonical: 8 AMP columns
DICT_TSV = os.path.join(ROOT, "inputs", "cde_dictionary.tsv")       # legacy mirror
MAPS = os.path.join(ROOT, "mappings")


def mapped_variables(approved_only=True):
    """The set of amp_variables that have a mapping file under mappings/ (searched RECURSIVELY --
    the tree is organised into per-program subdirectories). With approved_only, keep only maps whose
    `manual_approval` is truthy. This is the SINGLE generation+landing gate: an element with no
    approved map is neither generated (03_generate) nor landed (09_map_etl). Mirrors 09's _approved."""
    out = set()
    for p in glob.glob(os.path.join(MAPS, "**", "*.json"), recursive=True):
        m = json.load(open(p, encoding="utf-8"))
        v = m.get("variable")
        if not v:
            continue
        if approved_only:
            a = m.get("manual_approval")
            if not (a is True or (isinstance(a, str) and a.strip().upper() in ("TRUE", "YES", "1"))):
                continue
        out.add(v)
    return out


def _norm_row(r):
    """Coerce a JSONL row to the exact shape the old TSV DictReader produced: every value a
    string, NULL -> '' (matches the old coalesce(...,''))."""
    out = {}
    for k, v in r.items():
        if v is None:
            out[k] = ""
        elif isinstance(v, bool):
            out[k] = "true" if v else "false"
        else:
            out[k] = str(v)
    return out


def dict_rows():
    """Every row of the canonical CDE dictionary. Prefers inputs/cde_dictionary.jsonl (one JSON
    object per line; JSONL is immune to the delimiter/quoting corruption that CSV/TSV suffer); falls
    back to the legacy TSV. NULL is '' (matches the old coalesce(...,''))."""
    if os.path.exists(DICT_JSONL):
        with open(DICT_JSONL, encoding="utf-8") as fh:
            rows = [_norm_row(json.loads(line)) for line in fh if line.strip()]
    elif os.path.exists(DICT_TSV):
        with open(DICT_TSV, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh, delimiter="\t"))
    else:
        raise FileNotFoundError(
            f"neither {DICT_JSONL} nor {DICT_TSV} found -- both ship vendored "
            f"in inputs/; restore them from version control")
    return rows


def _spec_path():
    f = sorted(glob.glob(os.path.join(ROOT, "specs", "table_schema_fields.tsv")))
    if not f:
        raise FileNotFoundError(
            "specs/table_schema_fields*.tsv not found -- run scripts/01_build_specs.py first")
    return f[-1]


def specs_by_variable():
    """One spec row per amp_variable (keyed by amp_variable), from specs/table_schema_fields*.tsv.

    Reproduces exactly what the DB round-trip produced: ONE spec per
    amp_variable in the dictionary -- setdefault() over the (amp_variable, source)-ordered spec
    file, i.e. the row with the SMALLEST `source` -- and 03/04/05 read it back via
    DISTINCT ON (amp_variable). So here: per amp_variable, keep the row with the smallest sb_source.
    `source` values are simple ASCII (AMP-AD < AMP-CMD < AMP-PD < AMP-RA-SLE), so a plain string
    comparison matches the DB collation; this is order-independent (no reliance on file order).
    """
    best = {}
    with open(_spec_path(), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            v = r["amp_variable"]
            if v not in best or r["sb_source"] < best[v]["sb_source"]:
                best[v] = r
    return best
