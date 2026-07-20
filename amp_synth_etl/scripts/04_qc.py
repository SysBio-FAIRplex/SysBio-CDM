#!/usr/bin/env python3
"""
QC the synthetic AMP source. Exits non-zero on any failure.

The generator is PERSON-FIRST: each participant is built once, then projected onto files by GRAIN.
That removes a whole class of check -- a person-fact CANNOT vary across a person's rows, because
there is only one subject row for it to sit in. What remains is checked here.

  STRUCTURE    subject:  exactly ONE row per person, and no visit column
               visit:    visit_month increasing per person; visit_name agrees with visit_month
               every participant_id in a visit or specimen row exists in the subject file
  CONFORMANCE  every cell matches its column's Table Schema field descriptor (enum / range / type)
  CONTRACT     the data honours scripts/enumerated.py -- no aggregate column in any file; every
               gated column empty when its gate is off; nobody stops before they start; ARK's
               assessment scores appear only on the disease they measure
  SEMANTIC     the specimen lineage: every parent resolves, belongs to the same person and visit,
               no cycles, primaryCellSource equals the parent's material
               the Krenn Synovitis Score equals the sum of its three components
  HYGIENE      no dictionary prose in a data cell; integer columns hold integers
"""
import csv
import glob
import json
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import enumerated as E                    # noqa: E402  -- the contract the data is tested against
import inputs_io                          # noqa: E402  -- self-contained reads (replaces the DB)

OUT = os.path.join(ROOT, "output")
fail = []
PID = "participant_id"


def specs():
    """programme -> {column: spec}.

    PER PROGRAMME, not a flat dict. Loading ARK's spec file OVER the SysBio one in a single
    name-keyed dict makes QC validate AMP-AD's `race` against ARK's race enum -- ARK offers
    'Hispanic' and 'Mixed Race'; AMP-AD offers 'Unknown' and 'Multiracial'. Every AMP-AD row then
    "fails". That is the same bare-name collision the generator was rebuilt to make impossible, and
    it has no business reappearing in the thing that checks for it.
    """
    # was a read of sysbio.cde_dictionary; now the derived spec file. specs_by_variable reproduces
    # the old DISTINCT ON / 01b dedup (one spec per amp_variable). v = the raw amp_value_set.
    base = {v: {"amp_variable": v, "f": json.loads(r["table_schema_field"]),
                "v": r["sb_value_set"]}
            for v, r in inputs_io.specs_by_variable().items()}
    S = {p: dict(base) for p in ("AMP-PD", "AMP-AD", "AMP-CMD", "AMP-RA-SLE")}
    f = sorted(glob.glob(os.path.join(ROOT, "specs", "ark_fields_*.tsv")))
    if f:
        for r in csv.DictReader(open(f[-1], newline="", encoding="utf-8"), delimiter="\t"):
            S["AMP-RA-SLE"][r["amp_variable"]] = {"f": json.loads(r["table_schema_field"]), "v": ""}
    f = sorted(glob.glob(os.path.join(ROOT, "specs", "cmd_fields_*.tsv")))
    if f:
        # CMD's sheets disagree with each other, and the merged subject row carries the UNION --
        # exactly what the generator writes. Union them here too, independently.
        for r in csv.DictReader(open(f[-1], newline="", encoding="utf-8"), delimiter="\t"):
            sp = json.loads(r["table_schema_field"])
            cur = S["AMP-CMD"].get(r["amp_variable"])
            if cur and cur.get("f", {}).get("constraints", {}).get("enum") and \
                    sp.get("constraints", {}).get("enum"):
                merged = list(dict.fromkeys(list(cur["f"]["constraints"]["enum"]) +
                                            list(sp["constraints"]["enum"])))
                sp = dict(sp, constraints=dict(sp["constraints"], enum=merged))
            S["AMP-CMD"][r["amp_variable"]] = {"f": sp, "v": ""}
    return S


def load(name):
    p = os.path.join(OUT, name)
    return list(csv.DictReader(open(p, newline="", encoding="utf-8"))) if os.path.exists(p) else None


def structure(prog, subj, visit, spec):
    ids = [r[PID] for r in subj]
    if len(ids) != len(set(ids)):
        fail.append(f"{prog}: subject file has {len(ids)-len(set(ids))} duplicate participants")
    if subj and ("visit_name" in subj[0] or "visit_month" in subj[0]):
        fail.append(f"{prog}: the SUBJECT file carries a visit column")
    known = set(ids)
    for what, rows in (("visit", visit), ("specimen", spec)):
        for r in rows or []:
            if r[PID] not in known:
                fail.append(f"{prog}: a {what} row references participant {r[PID]}, who is not in "
                            f"the subject file")
    per = defaultdict(list)
    for r in visit or []:
        per[r[PID]].append(r)
    for pid, rs in per.items():
        months = [float(r["visit_month"]) for r in rs if r.get("visit_month")]
        if months != sorted(months):
            fail.append(f"{prog}: participant {pid}: visit_month not increasing {months}")
        for r in rs:
            vn, vm = r.get("visit_name"), r.get("visit_month")
            if vn and vm and vn != "SC" and vn != f"M{int(float(vm))}":
                fail.append(f"{prog}: visit_name {vn!r} disagrees with visit_month {vm}")


def conformance(prog, grain, rows, S):
    n = 0
    for i, r in enumerate(rows, start=2):
        for col, val in r.items():
            if val == "":
                continue
            n += 1
            sp = S.get(col)
            if not sp:
                continue
            f, vs = sp["f"], (sp.get("v") or "")
            if vs and val.strip() == vs.strip():
                fail.append(f"{prog}_{grain}:{i}: {col} contains its own dictionary prose {val!r}")
            c = f.get("constraints", {})
            enum = c.get("enum")
            if enum:
                if val not in [str(x) for x in enum]:
                    fail.append(f"{prog}_{grain}:{i}: {col}={val!r} not in enum {enum[:5]}")
            elif f.get("type") in ("integer", "number"):
                try:
                    x = float(val)
                except ValueError:
                    fail.append(f"{prog}_{grain}:{i}: {col}={val!r} is not numeric")
                    continue
                if "minimum" in c and x < c["minimum"]:
                    fail.append(f"{prog}_{grain}:{i}: {col}={val} below minimum {c['minimum']}")
                if "maximum" in c and x > c["maximum"]:
                    fail.append(f"{prog}_{grain}:{i}: {col}={val} above maximum {c['maximum']}")
                if f["type"] == "integer" and "." in str(val):
                    fail.append(f"{prog}_{grain}:{i}: {col}={val} is integer-typed but has a decimal")
    return n


def contract(prog, subj, visit, spec):
    """The data must honour scripts/enumerated.py. Without this, that file is a note rather than a
    contract, and would rot into a description of what the code used to do."""
    banned = {c for cols in E.DROP_AGGREGATE.values() for c in cols}
    for grain, rows in (("subject", subj), ("visit", visit), ("specimen", spec)):
        if rows:
            for c in banned & set(rows[0]):
                fail.append(f"{prog}_{grain} emits {c!r}, which is on DROP_AGGREGATE -- no "
                            f"sub-total, sub-score or summary score is emitted, in any file")

    by_pid = {r[PID]: r for r in subj or []}
    for g in (E.TOBACCO_GATE, E.ALCOHOL_GATE, E.KPMP_DIABETES_GATE, E.KPMP_AKI_GATE,
              E.KPMP_PERCUTANEOUS_GATE):
        want = g["gated_on"]
        want = [str(x) for x in want] if isinstance(want, list) else [str(want)]
        for grain, rows in (("subject", subj), ("visit", visit)):
            for i, r in enumerate(rows or [], start=2):
                # GRAIN SPLITS THE GATE: tobacco_ever_used is a lifetime fact and sits on the
                # SUBJECT row, while cigarettes_per_day is a per-visit status. Read the gate from
                # the person, then the row.
                v = by_pid.get(r[PID], {}).get(g["gate"], r.get(g["gate"]))
                if v in (None, "") or v in want:
                    continue
                for c in g["columns"]:
                    if r.get(c):
                        fail.append(f"{prog}_{grain}:{i}: {c}={r[c]!r} but its gate "
                                    f"{g['gate']}={v!r} (gated on {want})")
            for lo, hi in g.get("ordered", []):
                for i, r in enumerate(rows or [], start=2):
                    if r.get(lo) and r.get(hi) and float(r[hi]) < float(r[lo]):
                        fail.append(f"{prog}_{grain}:{i}: {hi}={r[hi]} is before {lo}={r[lo]}")

    if prog == "AMP-RA-SLE":
        for i, r in enumerate(visit or [], start=2):
            person = by_pid.get(r[PID], {})
            for s in (E.ARK_DIAGNOSIS_SCORES, E.ARK_COMORBIDITY_SCORES):
                held = person.get(s["gate"])
                for trigger, gated in s["rules"].items():
                    for c in gated:
                        if r.get(c) and held != trigger:
                            fail.append(f"{prog}_visit:{i}: {c}={r[c]!r} but {s['gate']}={held!r}, "
                                        f"not {trigger!r}")


def lineage_and_krenn(prog, spec):
    if not spec or "biospecimenID" not in spec[0]:
        return                              # only the ARK (RA-SLE) specimen grain carries lineage/krenn;
                                            # the AD omics specimen grain has no parent/child lineage
    byid = {r["biospecimenID"]: r for r in spec}
    if len(byid) != len(spec):
        fail.append(f"{prog}: biospecimenID is not unique")
    for r in spec:
        p = r.get("parentBiospecimenID")
        if p:
            if p not in byid:
                fail.append(f"{prog}: specimen {r['biospecimenID']} has parent {p}, not a specimen")
            else:
                if byid[p][PID] != r[PID]:
                    fail.append(f"{prog}: specimen {r['biospecimenID']}'s parent belongs to "
                                f"another participant")
                if byid[p].get("visit_name") != r.get("visit_name"):
                    fail.append(f"{prog}: specimen {r['biospecimenID']} and its parent are on "
                                f"different visits")
                src = r.get("primaryCellSource")
                if src and src != byid[p].get("biospecimenType"):
                    fail.append(f"{prog}: specimen {r['biospecimenID']} cultured from {src!r} but "
                                f"its parent is {byid[p].get('biospecimenType')!r}")
                seen, cur, d = {r["biospecimenID"]}, p, 0
                while cur and d < 50:
                    if cur in seen:
                        fail.append(f"{prog}: specimen {r['biospecimenID']} is its own ancestor")
                        break
                    seen.add(cur)
                    cur = byid.get(cur, {}).get("parentBiospecimenID")
                    d += 1
        if r.get("krennSynovitisScore"):
            parts = [r.get(k) for k in ("krennLining", "krennStroma", "krennInflammatory")]
            if all(x not in (None, "") for x in parts):
                parts = [int(x) for x in parts]
                got = int(r["krennSynovitisScore"])
                if any(x < 0 for x in parts):
                    if got != -1:
                        fail.append(f"{prog}: {r['biospecimenID']}: krennSynovitisScore={got} but "
                                    f"a component is unknown (-1)")
                elif got != sum(parts):
                    fail.append(f"{prog}: {r['biospecimenID']}: krennSynovitisScore={got} but its "
                                f"components {parts} sum to {sum(parts)}")
    if not any(r.get("parentBiospecimenID") for r in spec):
        fail.append(f"{prog}: no specimen has a parent -- the lineage is absent")


def main():
    SP = specs()
    # Enumerate programmes from the one-per-programme subject file. (rsplit on *_*.csv breaks now that
    # omics grains carry underscores -- 'AMP-AD_assay_to_specimen' would mint a bogus programme.)
    progs = sorted({os.path.basename(f)[:-len("_subject.csv")]
                    for f in glob.glob(os.path.join(OUT, "*_subject.csv"))})
    rows_n = cells_n = 0
    print(f"  {'programme':14s} {'subject':>9s} {'visit':>9s} {'specimen':>9s}")
    for prog in progs:
        subj = load(f"{prog}_subject.csv") or []
        visit = load(f"{prog}_visit.csv")
        spec = load(f"{prog}_specimen.csv")
        print(f"  {prog:14s} {len(subj):>9d} {len(visit or []):>9d} {len(spec or []):>9d}")
        structure(prog, subj, visit, spec)
        contract(prog, subj, visit, spec)
        lineage_and_krenn(prog, spec)
        for grain, rows in (("subject", subj), ("visit", visit), ("specimen", spec)):
            if rows:
                rows_n += len(rows)
                cells_n += conformance(prog, grain, rows, SP[prog])

    print(f"\n  rows         : {rows_n}")
    print(f"  cells filled : {cells_n}")
    print(f"\n--- FAIL ({len(fail)}) ---")
    if not fail:
        print("  none — structure, conformance, the enumerated contract, the specimen lineage "
              "and hygiene all pass")
    for f in fail[:30]:
        print(f"  {f}")
    if len(fail) > 30:
        print(f"  ... and {len(fail)-30} more")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
