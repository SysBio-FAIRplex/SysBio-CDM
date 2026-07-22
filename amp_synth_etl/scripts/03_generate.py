#!/usr/bin/env python3
"""
Generate the synthetic AMP source data. PERSON-FIRST.

    python scripts/03_generate.py

════════════════════════════════════════════════════════════════════════════════════════════════
 THE STRUCTURE, AND WHY IT CHANGED
════════════════════════════════════════════════════════════════════════════════════════════════

This used to loop TABLE -> SUBJECT -> COLUMN, emitting one output file per AMP dictionary (25 of
them for AMP-PD alone). That meant a single participant was CREATED 25 SEPARATE TIMES, by 25
independent passes -- once while writing Demographics.csv, again while writing UPDRS.csv, again
for MOCA.csv. At no point did "participant 100007" exist as a whole. They existed only as scattered
rows produced by different passes, and the only thing holding them together was a cache dict.

Every collision came from that. `project` was drawn twice for one ARK person and disagreed in 31 of
34 cases. `sex` was drawn while writing Adipose_Emont and then reused while writing FUSION -- whose
workbook declares no value set for sex at all. The cache key could never be right: keyed by NAME it
leaked across programmes, keyed by TABLE it collided within one. Both are wrong, because a fact
about a person must not be drawn inside a table loop.

The AMP dictionaries are NOT 25 studies. They are one study, documented in 25 subject-matter
files -- UPDRS here, MOCA there. That is FILING. It is not structure, and it never obliged us to
emit 25 files.

The only real division is GRAIN -- what a row IS:

    subject    one row per person     sex, race, diagnosis, age at death
    visit      one row per visit      UPDRS items, MOCA items, blood pressure, age at visit
    specimen   one row per specimen   the ARK biospecimen lineage

So: build each participant ONCE, completely. Then project the cohort onto the files by grain. The
files are a VIEW of the cohort, not the thing that creates it.

THE GUARANTEE: a person-fact resolves to exactly ONE column in ONE subject row. Two dictionaries
both declaring `sex` cannot yield two values, because there is nowhere for a second one to go. A
collision is not prevented -- it cannot be stated. There is nothing to cache, because nothing is
carried between passes: there is only one pass.

════════════════════════════════════════════════════════════════════════════════════════════════

Every column treated specially is named in scripts/enumerated.py. Nothing here infers a rule from
a column's NAME or its POSITION.

Writes only into output/. Deterministic: every draw is seeded on (element, subject, visit).
"""
import csv
import glob
import hashlib
import importlib
import json
import os
import random
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "gen"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import enumerated as E          # noqa: E402  -- the only source of special behaviour
import fidelity                 # noqa: E402  -- real-world distributions (draw realistic values)
import inputs_io                # noqa: E402  -- self-contained reads (replaces the sysbio_etl DB)
import lineage                  # noqa: E402
import omics                    # noqa: E402

OUT = os.path.join(ROOT, "output")
CFG = json.load(open(os.path.join(ROOT, "config", "cohort.json")))
SEED = CFG["seed"]

# The subject key. The dictionaries use several names for it -- participant_id, GUID, individualID,
# projid, subject_id, donor_id -- and the generator gave every one of them the same value, so they
# were aliases of a single number. One name, once.
PID = "participant_id"
ALIASES = {"GUID", "individualID", "projid", "subject_id", "donor_id", "Sample_ID", "biosample_id"}
VISIT_KEYS = ["visit_name", "visit_month"]
SPECIMEN_KEYS = ["biospecimenID", "parentBiospecimenID"]


def rng_for(*parts):
    h = hashlib.sha256("\x1f".join((SEED,) + tuple(map(str, parts))).encode()).digest()
    return random.Random(int.from_bytes(h[:8], "big"))


# ---------------------------------------------------------------- inputs

def load_specs():
    # PD/AD specs from specs/table_schema_fields*.tsv (was sysbio.cde_dictionary via the DB round-
    # trip). specs_by_variable reproduces the old DISTINCT ON / 01b dedup: one spec per amp_variable.
    specs = {v: json.loads(r["table_schema_field"])
             for v, r in inputs_io.specs_by_variable().items()}
    ark, cmd = {}, {}
    f = sorted(glob.glob(os.path.join(ROOT, "specs", "ark_fields.tsv")))
    if f:
        for r in csv.DictReader(open(f[-1], newline="", encoding="utf-8"), delimiter="\t"):
            ark[r["amp_variable"]] = json.loads(r["table_schema_field"])
    f = sorted(glob.glob(os.path.join(ROOT, "specs", "cmd_fields_*.tsv")))
    if f:
        for r in csv.DictReader(open(f[-1], newline="", encoding="utf-8"), delimiter="\t"):
            cmd[(r["spec_origin"].split("/")[-1], r["amp_variable"])] = \
                json.loads(r["table_schema_field"])
    return specs, ark, cmd


def load_dictionaries():
    """The AMP dictionaries: which columns each declares, and at what grain. They are documentation
    organised by subject matter -- 25 of them for AMP-PD. They are NOT 25 studies."""
    out = []
    for fp in ("tables.tsv", "tables_ark.tsv", "tables_cmd.tsv"):
        p = os.path.join(ROOT, "config", fp)
        if os.path.exists(p):
            out += list(csv.DictReader(open(p, newline="", encoding="utf-8"), delimiter="\t"))
    return out


def load_overrides():
    fns = defaultdict(dict)
    for i in range(1, 20):
        try:
            m = importlib.import_module(f"batch_{i:02d}")
        except ModuleNotFoundError:
            continue
        for prog in getattr(m, "SCOPE", ()):
            fns[prog].update(getattr(m, f"BATCH_{i:02d}", {}))
    return fns


def load_parked():
    """(table, column) -> parked. KEYED BY TABLE.

    This was flattened to a bare column-name SET during the person-first rewrite, and it wiped a
    whole feature. config/parked.tsv parks AMP-PD's PD_Medical_History.diagnosis -- AMP-PD's
    dictionary declares no value set for it. Flattened, `diagnosis` was parked in EVERY programme,
    so ARK's own declared 16-value diagnosis vanished; the diagnosis gate then read None, matched no
    trigger, and nulled VASI/VETI/VIDA/PASI/CDASI on every row. All five appeared in zero output
    files, and QC still reported zero failures.

    That is the bare-name collision this whole rewrite exists to make impossible -- reintroduced in
    the loader for the fix that was itself created to solve a bare-name problem. parked.tsv's own
    header says it exists because "the SysBio dictionary keys `diagnosis` by NAME ALONE".
    """
    park = set()
    p = os.path.join(ROOT, "config", "parked.tsv")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            if line.startswith("#") or not line.strip():
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 2:
                park.add((parts[0], parts[1]))      # (table, column)
    return park


def load_conditional():
    """ARK: a column belongs to a KIND of specimen. krennSynovitisScore exists for 'synovial
    tissue' and nothing else."""
    cond = {}
    p = os.path.join(ROOT, "config", "ark_conditional.tsv")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            if line.startswith("#") or not line.strip():
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 3 and parts[0] != "trigger_column":
                for dep in parts[2].split(","):
                    cond.setdefault(dep.strip(), []).append((parts[0], parts[1]))
    return cond


# ---------------------------------------------------------------- the column model

def build_model(dicts, specs, ark, cmd, parked):
    """programme -> grain -> {column: spec}.

    A column's grain is the grain of the dictionary that declares it -- EXCEPT that a column named
    in E.SUBJECT_CONSTANT is a fact about the PERSON even when its dictionary is visit-grained.
    (ARK repeats sex and diagnosis on every clinical visit row. They are still properties of the
    person, and they belong in the subject row, once.)

    Several dictionaries of one programme may declare the same column. They now resolve to ONE
    column, so a disagreement between them is REPORTED, not silently resolved by whichever
    dictionary happened to be read last.
    """
    model = defaultdict(lambda: defaultdict(dict))
    seen = defaultdict(lambda: defaultdict(list))       # (prog, col) -> [(dict, enum)]
    subject_const = {c for cols in E.SUBJECT_CONSTANT.values() for c in cols}
    drops = defaultdict(list)                           # col -> [tables that drop it]
    declares = defaultdict(list)                        # col -> [tables that declare it]
    banned = {c for cols in E.DROP_AGGREGATE.values() for c in cols}

    for r in dicts:
        t, c, p, g = r["table"], r["column"], r["program"], r["grain"]
        if t in E.DROP_TABLE or c in banned:
            continue
        declares[(p, c)].append(t)
        # parked == "this DICTIONARY declares no value set for this column". Same shape as a drop,
        # and resolved HERE, where the table is still known.
        if c in E.DROP_COLUMN.get(t, []) or (t, c) in parked:
            drops[(p, c)].append(t)

    for r in dicts:
        t, c, p, g = r["table"], r["column"], r["program"], r["grain"]
        if t in E.DROP_TABLE or c in banned:
            continue
        # a column is dropped only if EVERY dictionary that declares it drops it. FUSION drops
        # `sex` because ITS workbook declares no value set -- but Adipose and HYPOMAP do declare
        # one, and under one CMD subject row there is a single, well-defined sex.
        if len(drops[(p, c)]) == len(declares[(p, c)]):
            continue   # every dictionary that declares it drops or parks it
        if c in ALIASES:
            continue                                    # a second name for participant_id
        if c == PID or c in VISIT_KEYS or c in SPECIMEN_KEYS:
            continue                                    # keys are written by the writer

        sheet = t.replace("_subject.csv", "").replace("_sample.csv", "")
        sp = (ark.get(c) if p == "AMP-RA-SLE"
              else cmd.get((sheet, c)) if p == "AMP-CMD"
              else specs.get(c))
        if sp is None:
            continue                                    # no spec -> nothing to draw

        # SPECIMEN first: tables_ark.tsv declares the biospecimen template grain='subject' (one
        # template per subject), but a ROW of it is a SPECIMEN -- a person has many.
        if t == "BiospecimenMetadataTemplate.csv":
            grain = "subject" if c in E.SUBJECT_CONSTANT.get(t, []) else "specimen"
        elif c in subject_const or g == "subject":
            grain = "subject"
        else:
            grain = "visit"
        prev = model[p][grain].get(c)
        if prev is None:
            model[p][grain][c] = sp
        elif json.dumps(prev, sort_keys=True) != json.dumps(sp, sort_keys=True):
            # two dictionaries of one programme declare this column DIFFERENTLY. Merge their value
            # sets -- a value legal in at least one declaring dictionary -- and report it.
            a = (prev.get("constraints") or {}).get("enum") or []
            b = (sp.get("constraints") or {}).get("enum") or []
            if a or b:
                merged = list(dict.fromkeys(list(a) + list(b)))
                m = dict(prev)
                m["constraints"] = dict(prev.get("constraints", {}), enum=merged)
                model[p][grain][c] = m
            seen[p][c].append((t, b or "(no value set)"))
        seen[p][c].append((t, (sp.get("constraints") or {}).get("enum") or "(no value set)"))
    return model, seen


# ---------------------------------------------------------------- drawing

def draw(var, spec, rng, st):
    """Draw a legal value. Where a real-world distribution exists for `var`, sample from it
    (scripts/fidelity.py) -- weighted over the spec's LEGAL values for a value set, or clamped to
    the declared range for a number -- so the cohort is realistic AND still legal. Absent a
    distribution, fall back to uniform (honouring integer-vs-number type)."""
    if spec is None:
        return None
    c = spec.get("constraints", {})
    cats = spec.get("categories")
    if cats:
        return fidelity.categorical(var, [e["value"] for e in cats], rng,
                                    labels=[e.get("label", "") for e in cats])
    if c.get("enum"):
        return fidelity.categorical(var, list(c["enum"]), rng)
    t = spec.get("type")
    if t in ("integer", "number"):
        lo = c.get("minimum", 0)
        hi = c.get("maximum", lo + CFG["unbounded_span"])
        return fidelity.numeric(var, lo, hi, rng, integer=(t == "integer"))
    if t == "date":
        return f"{rng.randint(1995, 2023)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"
    # A string column with no value set. The source states nothing, so there is nothing to draw.
    return None


def value(col, spec, fns, rng, st):
    if col in fns:
        st["_spec"] = spec
        return fns[col](rng, st)
    return draw(col, spec, rng, st)


# ---------------------------------------------------------------- the rules (enumerated.py)

ALL_GATES = [E.TOBACCO_GATE, E.ALCOHOL_GATE, E.KPMP_DIABETES_GATE, E.KPMP_AKI_GATE,
             E.KPMP_PERCUTANEOUS_GATE]


def apply_gates(row, person=None):
    """A gated column is emitted ONLY when its gate column holds the gating value.

    The gate is read from the PERSON first, then the row. Grain split them: `tobacco_ever_used` is
    a lifetime fact and now lives on the SUBJECT row, while `cigarettes_per_day` is a per-visit
    status and lives on a VISIT row. A gate that only looked at the row would never fire.
    """
    for g in ALL_GATES:
        if person is not None and g["gate"] in person["subject"]:
            v = person["subject"][g["gate"]]
        elif g["gate"] in row:
            v = row[g["gate"]]
        else:
            continue
        want = g["gated_on"]
        ok = (v in want) if isinstance(want, list) else (str(v) == str(want))
        if not ok:
            for c in g["columns"]:
                if c in row:
                    row[c] = None
        for lo, hi in g.get("ordered", []):            # you cannot stop before you start
            if row.get(lo) is not None and row.get(hi) is not None and row[hi] < row[lo]:
                row[lo], row[hi] = row[hi], row[lo]
    return row


def apply_diagnosis_gates(row, person):
    """ARK's clinical DependsOn rules: an assessment score exists only for the disease it measures.
    The diagnosis is read from the PERSON, not from the row -- it is a property of the person, and
    the assessment sits on a visit row."""
    for spec in (E.ARK_DIAGNOSIS_SCORES, E.ARK_COMORBIDITY_SCORES):
        held = person["subject"].get(spec["gate"])
        for trigger, gated in spec["rules"].items():
            if trigger == held:
                continue
            for c in gated:
                if c in row:
                    row[c] = None
    return row


def apply_conditionals(row, cond):
    for c in list(row):
        trig = cond.get(c)
        if trig and not any(t in row and str(row[t]) == v for t, v in trig):
            row[c] = None
    return row


# ---------------------------------------------------------------- the cohort

def build_person(pid, prog, model, fns, cond, mono):
    """ONE participant, built ONCE, completely.

    Order: visits first, then the subject row. A subject-level fact may SUMMARISE the visit series
    (cogdx is the final dcfdx), so the series must exist before it is closed over. The shared state
    dict lets a visit-level function pull a subject-level fact it needs (age_at_visit needs
    age_death), and that fact is then held for the subject row.
    """
    F = fns.get(prog, {})
    st = {}
    # SEPARATE stream. main() already consumed rng_for("cohort", pid) to pick the programme; reusing
    # the same key here made a subject's visit count a function of the same random word as their
    # programme, correlating the two.
    r = rng_for("visits", pid)
    n = r.choice(CFG["visits_per_subject"])
    visits, month = [], 0
    if r.random() < CFG["p_screening_visit"]:
        visits.append(("SC", -1.0))          # per AMP's own definition of visit_name/visit_month
    for _ in range(n):
        visits.append((f"M{month}", float(month)))
        month += r.randint(*CFG["visit_interval_months"])
    if prog == "AMP-AD":
        st["cohort"] = fidelity.categorical("cohort", CFG["amp_ad_cohorts"], rng_for("cohort", pid))

    person = {"id": pid, "program": prog, "state": st, "visits": visits,
              "subject": {}, "visit_rows": [], "specimens": [],
              "ad_specimens": [], "assays": [], "files": [], "a2s": [], "aif": []}

    # ---- subject facts, PRE-PASS -------------------------------------------------------------
    # A VISIT-level hand function may need a SUBJECT-level fact: batch_06.height() reads the
    # subject's heightUnits to know whether to draw centimetres or inches. Those facts must exist
    # before the visit loop, or the lookup misses and silently falls back to a default -- which is
    # what happened: every ARK height came out on the centimetre scale regardless of the unit the
    # subject reports.
    #
    # The hand functions look for "_const_<column>", the key the deleted cell() used to write.
    st["visit_month"] = 0.0
    for c, sp in model[prog]["subject"].items():
        st["_const_" + c] = value(c, sp, F, rng_for(c, pid), st)

    # ---- visit rows -------------------------------------------------------------------------
    for vname, vmonth in visits:
        st["visit_month"] = vmonth
        row = {PID: pid, "visit_name": vname, "visit_month": vmonth}
        for c, sp in model[prog]["visit"].items():
            v = value(c, sp, F, rng_for(c, pid, vname), st)
            # MONOTONE (scripts/enumerated.py): non-decreasing across a subject's visits. Nobody
            # gets younger. This was DECLARED and never read -- a dead rule, which the file's own
            # notes call worse than no rule because it looks like protection.
            if c in mono and isinstance(v, (int, float)):
                prev = st.get("_mono_" + c)
                if prev is not None and v < prev:
                    v = prev
                st["_mono_" + c] = v
            row[c] = v
        person["visit_rows"].append(row)

    # ---- the subject row: drawn ONCE. There is nowhere for a second value to go. -------------
    # Drawn AGAIN after the visits, because a subject fact may SUMMARISE the visit series (cogdx is
    # the final dcfdx). Both passes are idempotent: a hand function caches on first call, and a
    # spec draw is seeded on (column, subject), so the value is identical. Only a visit-summarising
    # function changes -- which is the point.
    st["visit_month"] = 0.0
    for c, sp in model[prog]["subject"].items():
        person["subject"][c] = value(c, sp, F, rng_for(c, pid), st)
    person["subject"][PID] = pid

    # gates run after the facts exist; the diagnosis gate reads the PERSON.
    # apply_diagnosis_gates runs on the SUBJECT row too: vitiligoPattern and diabetesType are
    # SUBJECT_CONSTANT, so they live here, not on a visit row. Gating only the visit rows left every
    # subject carrying a vitiligoPattern and 33 of 34 carrying a diabetesType with no diabetes --
    # the exact defect the gate was written to fix.
    apply_gates(person["subject"], person)
    if prog == "AMP-RA-SLE":
        apply_diagnosis_gates(person["subject"], person)
    for row in person["visit_rows"]:
        apply_gates(row, person)
        if prog == "AMP-RA-SLE":
            apply_diagnosis_gates(row, person)

    # AMP-AD: a ROSMAP-only column exists only for a subject from the ROS or MAP brain bank.
    g = E.AMP_AD_ROSMAP_GATE
    if prog == g["program"]:
        if st.get(g["gate"]) not in g["gated_on"]:
            for row in [person["subject"]] + person["visit_rows"]:
                for c in g["columns"]:
                    if c in row:
                        row[c] = None

    # ---- specimens (ARK): a lineage, one row per specimen ------------------------------------
    if prog == "AMP-RA-SLE" and model[prog]["specimen"]:
        for sp_ in lineage.plan(rng_for("lineage", pid), pid, visits):
            st["_specimen"] = sp_
            row = {PID: pid, "visit_name": sp_["visitID"]}
            row.update({k: sp_[k] for k in SPECIMEN_KEYS if k in sp_})
            row["biospecimenType"] = sp_["biospecimenType"]
            row["biospecimenSubtype"] = sp_["biospecimenSubtype"]
            row["primaryCellSource"] = sp_["primaryCellSource"]
            for c, spec in model[prog]["specimen"].items():
                if c in row:
                    continue
                row[c] = value(c, spec, F, rng_for(c, pid, sp_["_seq"]), st)
            # ARK's own program value gates visitID; the person carries the programme
            for c in ("program", "project"):
                if c in model[prog]["specimen"]:
                    row[c] = person["subject"].get(c, row.get(c))
            person["specimens"].append(apply_conditionals(row, cond))

    # ---- omics extension: AD specimens, and assays -> files for AD + RA-SLE (cohort-builder graph)
    if prog == "AMP-AD":
        person["ad_specimens"] = omics.specimens_ad(rng_for("ad_specimen", pid), pid, visits)
        spec_for_omics = person["ad_specimens"]
    elif prog == "AMP-RA-SLE":
        spec_for_omics = [{"specimen_id": int(s["biospecimenID"]),
                           "specimen_source_value": s.get("biospecimenType") or "",
                           "organ": "", "cell_type": s.get("cellType") or ""}
                          for s in person["specimens"] if s.get("biospecimenID") not in (None, "")]
    else:
        spec_for_omics = []
    if spec_for_omics:
        person["assays"], person["files"], person["a2s"] = \
            omics.assays_and_files(rng_for("assay", pid), pid, prog, spec_for_omics)
    return person


# ---------------------------------------------------------------- writing

def write(path, cols, rows, manifest, prog, grain, dropped):
    """A column empty on EVERY row is not emitted -- but it is REPORTED.

    Silently dropping it makes a column that a rule wrongly nulled indistinguishable from one the
    source never declared. Concrete failure mode: VASI/VETI/VIDA/PASI/CDASI nulled on every row
    vanish from the file, and QC reports zero failures.
    """
    live = [c for c in cols if any(r.get(c) not in (None, "") for r in rows)]
    for c in cols:
        if c not in live:
            dropped.append((prog, grain, c))
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(live)
        for r in rows:
            w.writerow(["" if r.get(c) is None else r.get(c) for c in live])
    manifest.append([prog, grain, os.path.basename(path), len(rows), len(live),
                     hashlib.sha256(open(path, "rb").read()).hexdigest()])
    return len(live)


def write_fixed(path, cols, rows, manifest, prog, grain):
    """Fixed-schema writer for the omics extension CSVs -- keeps ALL columns (unlike write(), which
    drops all-empty ones) so the CDM render layer sees a stable schema."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(cols)
        for r in rows:
            w.writerow(["" if r.get(c) is None else r.get(c) for c in cols])
    manifest.append([prog, grain, os.path.basename(path), len(rows), len(cols),
                     hashlib.sha256(open(path, "rb").read()).hexdigest()])


OMICS_GRAINS = [
    ("specimen", ["participant_id", "specimen_id", "visit_name", "organ",
                  "specimen_source_value", "anatomic_site_source_value", "cell_type",
                  "nucleic_acid_source", "sample_status", "is_post_mortem"],
     lambda p: p.get("ad_specimens", [])),
    ("assay", ["participant_id", "assay_id", "assay_source_value", "assay_type", "platform",
               "suspension_type", "analyte_type", "analysis_pipeline"],
     lambda p: p.get("assays", [])),
    ("file", ["participant_id", "file_id", "assay_id", "file_name", "file_role", "analysis_type",
              "file_format", "biosample_type", "tissue", "cell_type", "species", "study", "grant",
              "file_size_bytes", "drs_id"],
     lambda p: p.get("files", [])),
    ("assay_to_specimen", ["assay_id", "specimen_id"], lambda p: p.get("a2s", [])),
    ("assay_input_file", ["assay_id", "file_id"], lambda p: p.get("aif", [])),
]


def main():
    specs, ark, cmd = load_specs()
    parked = load_parked()
    model, disagreements = build_model(load_dictionaries(), specs, ark, cmd, parked)
    fns, cond = load_overrides(), load_conditional()

    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        os.remove(os.path.join(OUT, f))

    # ---- the cohort: every participant built ONCE ---------------------------------------------
    people = []
    for i in range(CFG["n_subjects"]):
        pid = CFG["first_id"] + i
        prog = _weighted(rng_for("program", pid), CFG["program_weights"])
        people.append(build_person(pid, prog, model, fns, cond,
                                   set(E.MONOTONE.get("ClinicalMetadataTemplate.csv", []))
                                   if prog == "AMP-RA-SLE" else set()))

    # ---- the files: a VIEW of the cohort, by grain --------------------------------------------
    manifest, total, dropped = [], 0, []
    for prog in sorted({p["program"] for p in people}):
        mine = [p for p in people if p["program"] == prog]
        gates = {}
        for grain, keys, getter in (
                ("subject",  [PID], lambda p: [p["subject"]]),
                ("visit",    [PID] + VISIT_KEYS, lambda p: p["visit_rows"]),
                ("specimen", [PID, "visit_name"] + SPECIMEN_KEYS, lambda p: p["specimens"])):
            cols = keys + [c for c in model[prog][grain] if c not in keys]
            rows = [r for p in mine for r in getter(p)]
            # A row carrying nothing but keys is not a row. AMP-AD's entire visit grain is ROSMAP's
            # clinical follow-up, so a subject from any other brain bank has no follow-up at all --
            # they are an autopsy case. They were getting empty visit rows.
            data = [c for c in cols if c not in keys]
            rows = [r for r in rows if any(r.get(c) not in (None, "") for c in data)]
            if not rows or len(cols) == len(keys):
                continue
            n = write(os.path.join(OUT, f"{prog}_{grain}.csv"), cols, rows, manifest, prog, grain,
                      dropped)
            gates[grain] = (len(rows), n)
            total += len(rows)
        # cohort/plate-level files span MANY assays (proteomics NPX plate, harmonized matrices) -- minted
        # once across the whole programme, not one-per-assay. Injected into the file / assay_input_file grains.
        all_assays = [a for p in mine for a in p.get("assays", [])]
        cohort_f, cohort_aif = omics.cohort_files(rng_for("cohort_files", prog), prog, all_assays)
        omics_extra = {"file": cohort_f, "assay_input_file": cohort_aif}
        for grain, cols, getter in OMICS_GRAINS:
            rows = [r for p in mine for r in getter(p)] + omics_extra.get(grain, [])
            if rows:
                write_fixed(os.path.join(OUT, f"{prog}_{grain}.csv"), cols, rows, manifest, prog, grain)
                gates[grain] = (len(rows), len(cols))
                total += len(rows)
        print(f"  {prog:12s} " + "  ".join(f"{g}: {r} rows x {c} cols"
                                            for g, (r, c) in gates.items()))

    with open(os.path.join(OUT, "MANIFEST.tsv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["program", "grain", "file", "rows", "cols", "sha256"])
        w.writerows(manifest)

    dis = {(p, c): v for p, cs in disagreements.items() for c, v in cs.items()
           if len({str(e) for _, e in v}) > 1}
    if dis:
        print(f"\n  columns DECLARED DIFFERENTLY by two dictionaries of one programme "
              f"({len(dis)}) -- value sets merged, and reported rather than silently resolved:")
        for (p, c), v in sorted(dis.items()):
            print(f"    [{p}] {c}")
            for t, e in v:
                print(f"        {t:34s} {str(e)[:56]}")

    if dropped:
        print(f"\n  columns MODELLED but EMPTY on every row, so not emitted ({len(dropped)}) --")
        print(f"  reported, not silent: a column a rule wrongly nulled looks exactly like a column")
        print(f"  the source never declared, so an empty column is reported explicitly.")
        for pr, gr, c in dropped:
            print(f"      [{pr} {gr}] {c}")

    print(f"\n  people : {len(people)}")
    print(f"  rows   : {total}")
    print(f"  files  : {len(manifest)}")
    return 0


def _weighted(rng, weights):
    x, acc = rng.random(), 0.0
    for k, w in weights.items():
        acc += w
        if x <= acc:
            return k
    return list(weights)[-1]


if __name__ == "__main__":
    sys.exit(main())
