#!/usr/bin/env python3
"""
Render the person-first cohort into the two staging objects the in-repo map-driven ETL reads --
staging.amp_clinical and staging.person_map -- plus the cdm.person / cdm.visit_occurrence rows
they anchor.

    Orchestrated by scripts/10_build_cdm_delivery.py --all. Not run by hand.

════════════════════════════════════════════════════════════════════════════════════════════════
 WHY THIS EXISTS
════════════════════════════════════════════════════════════════════════════════════════════════

scripts/09_map_etl.py consumes staging.amp_clinical to emit cdm.observation / cdm.measurement,
replacing the shared repo's transform/amp_to_cdm_load_queries.sql. scripts/10_build_cdm_delivery.py
then assembles this staging SQL with the map-driven facts, concept seed, extensions and governance
into cdm_load.sql.

The staging table is the STABLE INTERFACE: the map-driven ETL reads staging.amp_clinical exactly
where the shared-repo ETL did, which is why this script did not change when the ETL was swapped.

The ETL reads exactly TWO objects:

    FROM staging.amp_clinical
    JOIN staging.person_map

This script produces those two tables (plus the cdm.person and cdm.visit_occurrence rows they
depend on) as ONE self-contained .sql file. Nothing outside this pipeline is written.

The cohort is built PERSON-FIRST, so the output files are a VIEW of it. This is simply another
view -- a wide, per-(person, visit) pivot. Not a translation, not a re-generation.

════════════════════════════════════════════════════════════════════════════════════════════════
 THE FOUR CONSTRAINTS THAT SILENTLY CORRUPT THE LOAD IF MISSED
════════════════════════════════════════════════════════════════════════════════════════════════

1. visit_date must be NOT NULL on EVERY row. The ETL writes it straight into observation_date /
   measurement_date, which are DATE NOT NULL, and its WHERE clause guards the value column and
   person_source_value -- never the date. A null date is a hard abort.

2. person_map.person_id must ALREADY EXIST in cdm.person or the FK kills the run. data.sql preloads
   only 1-200 and 900001-900009. We have 500 people, so we emit our own cdm.person rows. person is
   DATA-FREE (a CHECK pins 4 of its 5 columns to 0), so that is trivial.

3. The person join is INNER. Anyone missing from person_map is dropped SILENTLY.

4. The visit join is LEFT. A visit_source_value with no cdm.visit_occurrence row loads with
   visit_occurrence_id = NULL and NO ERROR. This is already happening in the repo today: the fixture
   has no _V4 rows, so 33 visits' facts are orphaned. We emit our own visit_occurrence rows.

TWO NAME TRAPS, both real:
  * `Age` and `age` are DIFFERENT COLUMNS. staging.cde_program: Age -> AMP-CMD, age -> AMP-RA-SLE.
    Case-normalising would inject RA/SLE ages into the CMD column. We match case-exactly.
  * `height` is supplied by BOTH AMP-CMD_subject (cm) and AMP-RA-SLE_visit (inches/feet/cm).
    staging.cde_program declares height -> AMP-CMD. RA/SLE's height therefore has NO staging column
    and is NOT written. Reported, not silently unioned.
"""
import csv
import glob
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "cdm_load")
CFG = json.load(open(os.path.join(ROOT, "config", "cohort.json")))

PID_COL = "participant_id"
KEYS = {"participant_id", "visit_name", "visit_month", "biospecimenID", "parentBiospecimenID"}

# person_id == participant_id (100001..). Disjoint from the fixture's 1-200 and 900001-900009,
# so our cohort cannot collide with theirs.
VISIT_OCCURRENCE_ID_BASE = 1_000_000
VISIT_TYPE_CONCEPT_ID = 32035      # the fixture's convention for synthetic visits
VISIT_CONCEPT_ID = 32036           # ditto
CONFLICTED = set()                 # columns whose meaning DIFFERS between the programmes supplying them


def staging_contract():
    """The 523 AMP-variable columns of staging.amp_clinical, and the DDL, lifted VERBATIM from the
    CDM repo. Never retyped: if their column set changes, ours follows."""
    ddl = open(os.path.join(ROOT, "cdm_load", "_amp_clinical_ddl.sql"), encoding="utf-8").read()
    m = re.search(r"CREATE TABLE staging\.amp_clinical \(.*?\);", ddl, re.S)
    if m: ddl = m.group(0)
    cols = re.findall(r'^\s+"?([A-Za-z_][\w.]*)"?\s+(?:text|date),?$', ddl, re.M)
    keys = ["person_source_value", "visit_source_value", "visit_date"]
    return ddl, [c for c in cols if c not in keys]


def cde_program():
    """staging.cde_program -- the AUTHORITATIVE (amp_variable -> programme) map, from the CDM repo.
    This is what says `height` belongs to AMP-CMD and not to AMP-RA/SLE."""
    owner = defaultdict(set)
    for ln in open(os.path.join(ROOT, "inputs", "cde_dictionary.jsonl"), encoding="utf-8"):
        r = json.loads(ln)
        if r.get("amp_variable") and r.get("source"):
            owner[r["amp_variable"]].add(r["source"])
    # Curated SINGLE authoritative owner for conflicted shared columns: the dict lists these under more
    # than one programme (e.g. `height` in both AMP-CMD-cm and AMP-RA-SLE-inches), but the staging column
    # carries ONE programme's meaning. A new conflict from conflicted() needs an entry here.
    CONFLICT_OWNER = {"height": "AMP-CMD"}
    for var, prog in CONFLICT_OWNER.items():
        owner[var] = {prog}
    return owner


def conflicted(people, var_cols):
    """Columns supplied by MORE THAN ONE of our programmes whose DECLARED SPEC DIFFERS.

    A shared column is not automatically a conflict: our participants are disjoint across
    programmes, so if AMP-PD and AMP-AD declare `race` with the same value set, a union is exact.
    It is a conflict only when the programmes mean different things -- `height` is centimetres in
    AMP-CMD and inches/feet in AMP-RA/SLE. Detected by comparing the Table Schema field descriptors,
    not asserted by me.
    """
    import glob as _g
    spec = defaultdict(dict)                      # column -> {programme: spec-json}
    base = {}
    f = sorted(_g.glob(os.path.join(ROOT, "specs", "table_schema_fields.tsv")))
    if f:
        for r in csv.DictReader(open(f[-1], newline="", encoding="utf-8"), delimiter="\t"):
            base.setdefault(r["amp_variable"], r["table_schema_field"])
    for pat, prog in (("ark_fields_*.tsv", "AMP-RA-SLE"), ("cmd_fields_*.tsv", "AMP-CMD")):
        f = sorted(_g.glob(os.path.join(ROOT, "specs", pat)))
        if f:
            for r in csv.DictReader(open(f[-1], newline="", encoding="utf-8"), delimiter="\t"):
                spec[r["amp_variable"]][prog] = r["table_schema_field"]
    for c in var_cols:
        for prog in ("AMP-PD", "AMP-AD"):
            if c in base:
                spec[c].setdefault(prog, base[c])

    supplied = defaultdict(set)                   # column -> the programmes WE supply it from
    for p in people.values():
        for c in list(p["subject"]) + ([k for v in p["visits"] for k in v] if p["visits"] else []):
            supplied[c].add(p["program"])

    out = set()
    for c in var_cols:
        progs = supplied.get(c, set())
        if len(progs) < 2:
            continue
        # A NUMERIC column whose RANGE differs between programmes is a UNITS/SCALE mismatch, and
        # that is the only thing that actually corrupts: RA/SLE's height of 5.8 (feet) written into
        # a column the ETL reads as centimetres becomes a 5.8 cm person.
        #
        # A CODED column whose value set differs is NOT corruption. The ETL maps source values to
        # concepts; a value it does not recognise simply does not load. `race` and `sex` are the same
        # concept everywhere, and our participants are disjoint, so unioning them is exact --
        # suppressing them would discard 1094 real values to prevent a harm that does not exist.
        shapes = set()
        for pr in progs:
            if pr not in spec.get(c, {}):
                continue
            f = json.loads(spec[c][pr])
            if f.get("type") not in ("integer", "number"):
                shapes.clear()
                break                             # coded/string -> never a units conflict
            k = f.get("constraints", {})
            shapes.add((k.get("minimum"), k.get("maximum")))
        if len(shapes) > 1:
            out.add(c)
    return out


def load_cohort():
    """The 8 grain files -> {pid: {"program", "subject": {...}, "visits": [{...}]}}"""
    people = {}
    for fp in sorted(glob.glob(os.path.join(ROOT, "output", "*.csv"))):
        name = os.path.basename(fp)[:-4]
        if "_" not in name:
            continue
        prog, grain = name.rsplit("_", 1)
        if grain not in ("subject", "visit"):
            continue                                    # specimen has no home in amp_clinical
        for r in csv.DictReader(open(fp, newline="", encoding="utf-8")):
            pid = r[PID_COL]
            p = people.setdefault(pid, {"program": prog, "subject": {}, "visits": []})
            if grain == "subject":
                p["subject"] = {k: v for k, v in r.items() if k not in KEYS and v != ""}
            else:
                p["visits"].append(r)
    for p in people.values():
        p["visits"].sort(key=lambda r: float(r.get("visit_month") or 0))
    return people


def enrolment_date(pid):
    """Deterministic per person, from a GENERATION PARAMETER -- not invented per row."""
    lo = date.fromisoformat(CFG["enrolment_window"][0])
    hi = date.fromisoformat(CFG["enrolment_window"][1])
    span = (hi - lo).days
    return lo + timedelta(days=(int(pid) * 7919) % span)   # stable, spread


def sql_lit(v):
    return "\\N" if v in (None, "") else str(v).replace("\\", "\\\\").replace("\t", " ")\
        .replace("\n", " ").replace("\r", " ")


def main():
    os.makedirs(OUT, exist_ok=True)
    ddl, var_cols = staging_contract()
    owner = cde_program()
    people = load_cohort()
    global CONFLICTED
    CONFLICTED = conflicted(people, var_cols)
    print(f"  staging.amp_clinical : {len(var_cols)} AMP-variable columns (lifted verbatim)")
    print(f"  cohort               : {len(people)} people")

    # ── the pivot ────────────────────────────────────────────────────────────────────────────
    rows, visits, gated, unsupplied = [], [], defaultdict(int), set(var_cols)
    void = VISIT_OCCURRENCE_ID_BASE
    for pid in sorted(people, key=int):
        p = people[pid]
        prog, enrol = p["program"], enrolment_date(pid)

        def cell(col, visit_row):
            # what this person's own files hold for this column
            v = None
            if visit_row and col in visit_row and visit_row[col] != "":
                v = visit_row[col]
            elif p["subject"].get(col) not in (None, ""):
                v = p["subject"][col]
            if v is None:
                return None

            # A shared column is only a CONFLICT if the programmes MEAN different things by it.
            # `height` is centimetres in AMP-CMD and inches/feet in AMP-RA/SLE -- unioning them puts
            # RA/SLE inches under CMD's concept, in cm. `race` and `sex` are the SAME concept with
            # the same value set, and our participants are disjoint, so a union is exact.
            #
            # We do NOT gate on staging.cde_program alone: it under-declares (it lists `race` and
            # `ethnicity` for AMP-AD only, though AMP-PD's Demographics declares them too), and
            # gating on it would silently discard 1094 real values.
            if col in CONFLICTED:
                own = owner.get(col, set())
                if prog not in own:
                    gated[col] += 1
                    return None
            unsupplied.discard(col)
            return v

        vs = p["visits"] or [None]                  # no visits -> ONE visit-less row (LEFT JOIN safe)
        for vr in vs:
            if vr:
                vsv = f"{pid}_{vr['visit_name']}"
                vd = enrol + timedelta(days=int(round(float(vr["visit_month"] or 0) * 30.44)))
                void += 1
                visits.append((void, pid, vd, vsv))
            else:
                vsv, vd = None, enrol               # visit_date is NEVER null -- constraint 1
            rows.append([pid, vsv, vd.isoformat()] + [cell(c, vr) for c in var_cols])

    print(f"  staging.amp_clinical : {len(rows)} rows (one per person-visit; visit-less people get one)")
    print(f"  cdm.visit_occurrence : {len(visits)} rows")
    print(f"  columns we supply    : {len(var_cols) - len(unsupplied)} / {len(var_cols)}")
    print(f"\n  columns supplied by >1 programme whose SPEC DIFFERS (a real conflict): "
          f"{sorted(CONFLICTED) if CONFLICTED else 'none'}")
    if gated:
        print(f"  values suppressed to avoid writing one programme's meaning under another's concept:")
        for c, n in sorted(gated.items(), key=lambda kv: -kv[1]):
            print(f"      {c:22s} {n:4d} dropped — staging.cde_program gives this column to "
                  f"{sorted(owner.get(c, []))}")

    # ── emit ONE self-contained .sql ─────────────────────────────────────────────────────────
    p = os.path.join(OUT, "01_staging_and_structure.sql")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("-- GENERATED by amp-synthetic-data/scripts/06_render_cdm_load.py.\n"
                 "-- Produces the two objects the SysBio-CDM ETL reads (staging.amp_clinical,\n"
                 "-- staging.person_map) plus the cdm.person / cdm.visit_occurrence rows they need.\n"
                 "-- Self-contained: COPY FROM stdin, no external file paths.\n"
                 "-- The shared repo is NOT modified by this or by anything that runs it.\n\n")
        fh.write("\\set ON_ERROR_STOP on\nSET search_path = cdm, public;\n\n")

        # cdm.person -- DATA-FREE: a CHECK pins gender/yob/race/ethnicity to 0.
        fh.write("-- 1. our cohort's persons. DATA-FREE by CHECK: person_id is the only carrier.\n")
        fh.write("COPY person (person_id, gender_concept_id, year_of_birth, race_concept_id, "
                 "ethnicity_concept_id) FROM stdin;\n")
        for pid in sorted(people, key=int):
            fh.write(f"{pid}\t0\t0\t0\t0\n")
        fh.write("\\.\n\n")

        # cdm.visit_occurrence -- the ETL never inserts these. Without them every fact gets
        # visit_occurrence_id = NULL, silently (the LEFT JOIN).
        fh.write("-- 2. visits. The ETL LEFT JOINs these; a missing row = a silently orphaned fact.\n")
        fh.write("COPY visit_occurrence (visit_occurrence_id, person_id, visit_concept_id, "
                 "visit_start_date, visit_end_date, visit_type_concept_id, visit_source_value) "
                 "FROM stdin;\n")
        for voi, pid, vd, vsv in visits:
            fh.write(f"{voi}\t{pid}\t{VISIT_CONCEPT_ID}\t{vd}\t{vd}\t{VISIT_TYPE_CONCEPT_ID}\t{vsv}\n")
        fh.write("\\.\n\n")

        fh.write("-- 3. staging. The ETL reads ONLY these two tables.\n")
        fh.write("DROP SCHEMA IF EXISTS staging CASCADE;\nCREATE SCHEMA staging;\n\n")
        fh.write("CREATE TABLE staging.person_map (person_source_value text NOT NULL, "
                 "person_id integer);\n")
        fh.write("COPY staging.person_map (person_source_value, person_id) FROM stdin;\n")
        for pid in sorted(people, key=int):
            fh.write(f"{pid}\t{pid}\n")          # person_source_value == person_id, both numeric
        fh.write("\\.\n\n")

        fh.write("-- lifted VERBATIM from the CDM repo so the column set cannot drift:\n")
        fh.write(ddl + "\n\n")
        quoted = ", ".join(['person_source_value', 'visit_source_value', 'visit_date']
                           + [f'"{c}"' for c in var_cols])
        fh.write(f"COPY staging.amp_clinical ({quoted}) FROM stdin;\n")
        for r in rows:
            fh.write("\t".join(sql_lit(x) for x in r) + "\n")
        fh.write("\\.\n\n")
        fh.write("CREATE INDEX ON staging.amp_clinical (person_source_value, visit_source_value);\n")
        fh.write("CREATE INDEX ON staging.person_map (person_source_value);\n")
    print(f"\n  wrote {os.path.relpath(p, ROOT)}  ({os.path.getsize(p)/1e6:.1f} MB)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
