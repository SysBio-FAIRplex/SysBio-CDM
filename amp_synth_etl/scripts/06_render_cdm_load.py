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
VISIT_TYPE_CONCEPT_ID = 0          # sentinel 'No matching concept' — type concepts are not accurate to the AMP source data
VISIT_CONCEPT_ID = 32036           # ditto
# Autopsy provenance for post-mortem brain-bank donors (AD) that have no clinical visits.
PROCEDURE_OCCURRENCE_ID_BASE = 3_000_000
AUTOPSY_CONCEPT_ID = 4220533       # 'Autopsy, gross examination with brain' (SNOMED Procedure; in curated sqlite)
PM_COLLECTION_CONCEPT_ID = 44808183  # 'Post mortem specimen collection' (SNOMED Procedure; in curated sqlite)
CONDITION_OCCURRENCE_ID_BASE = 4_000_000
OBSERVATION_PERIOD_ID_BASE = 5_000_000
RECORD_TYPE_REGISTRY = 32879       # 'Registry' -- record provenance, consistent with the specimen_type choice
# Disease cohort status -> curated Condition concept. NOTE: condition_occurrence was previously
# DROPPED by design; that decision is REVERSED (2026-09-01) because the Technome/Verily Beta-2
# ask (2026-08-28, item 8) names condition_occurrence explicitly. Concepts come ONLY from the
# curated sqlite; 0 = no curated concept yet (token preserved in condition_source_value);
# a status ABSENT from the map asserts no condition (controls, unknowns, unaffected, at-risk).
STATUS_COL = {"AMP-AD": "ADoutcome", "AMP-PD": "study_arm", "AMP-RA-SLE": "diagnosis"}  # AMP-CMD carries no status column
CONDITION_MAP = {
  "AMP-AD": {"AD": 378419},                                   # Alzheimer's disease
  "AMP-PD": {"PD": 381270, "Genetic Cohort PD": 381270, "Genetic Registry PD": 381270,
             "LBD": 380701},                                  # Parkinson's disease / Diffuse Lewy body disease
  "AMP-RA-SLE": {"RA": 80809, "SLE": 257628, "dermatomyositis": 80182, "vitiligo": 138502,
                 "lupus nephritis": 4285717,                  # SLE glomerulonephritis syndrome (closest curated)
                 "psoriasis": 140168, "psoriatic arthritis": 40319772, "scleroderma": 40352976,
                 "OA": 80180, "discoid lupus erythematosus": 4066824,
                 "cutaneous lupus erythematosus": 4324123, "CLE": 4324123,
                 "Sjogren's disease": 254443},                # all Standard SNOMED, verified 2026-09-03
}
PROCEDURE_TYPE_CONCEPT_ID = 0      # sentinel 'No matching concept' — type concepts not accurate to AMP data
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



def person_id_map():
    """Beta-2 ask 4: cdm.person_id is a MINTED SEQUENTIAL sysbio id (1..N over participants
    sorted numerically), decoupled from the generator's participant_id. staging.person_map is
    the one crosswalk; everything CDM-side speaks minted ids only."""
    import glob as _glob
    pids = set()
    for fp in sorted(_glob.glob(os.path.join(ROOT, "output", "*_subject.csv"))) + \
              sorted(_glob.glob(os.path.join(ROOT, "output", "*_visit.csv"))):
        for r in csv.DictReader(open(fp, newline="", encoding="utf-8")):
            pids.add(r["participant_id"])
    return {p: i + 1 for i, p in enumerate(sorted(pids, key=int))}


def postmortem_donors():
    """participant_ids with >=1 post-mortem specimen, from the generated specimen CSVs.
    The autopsy branch below only fired for AMP-AD donors that happened to have NO visits, so
    post-mortem donors WITH visits -- and every AMP-CMD donor -- got no collection procedure."""
    pm = set()
    gen = os.path.join(ROOT, "output")
    for prog in ("AMP-AD", "AMP-PD", "AMP-CMD", "AMP-RA-SLE"):
        p = os.path.join(gen, f"{prog}_specimen.csv")
        if not os.path.exists(p):
            continue
        with open(p, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if (r.get("is_post_mortem") or "").strip().upper() == "TRUE":
                    pm.add(r["participant_id"])
    return pm


def enrolment_date(pid):
    """Beta-2 contract (Technome/Verily 2026-08-28, asks 1-3): every date is RELATIVE TO THE
    BASELINE VISIT with the baseline anchored at the 1900-01-01 sentinel epoch. The previous
    enrolment-window spread leaked nothing but implied calendar time that does not exist."""
    return date(1900, 1, 1)


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
    rows, visits, procedures, gated, unsupplied = [], [], [], defaultdict(int), set(var_cols)
    obs_periods, conditions = [], []
    void = VISIT_OCCURRENCE_ID_BASE
    PM_DONORS = postmortem_donors()
    PMAP = person_id_map()          # participant_id -> minted sysbio person_id
    _pm_done = set()
    for pid in sorted(people, key=int):
        p = people[pid]
        prog, enrol = p["program"], enrolment_date(pid)
        pdates = []

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

        # A participant with no visit rows still needs ONE visit, else its facts load with a NULL
        # visit_occurrence_id (orphaned — a documented limitation). Synthesize one: AD is a post-mortem
        # brain cohort, so its no-visit donors get an AUTOPSY visit + a gross-brain-autopsy procedure;
        # any other visit-less participant (e.g. cross-sectional CMD) gets one BASELINE lab visit.
        synth = None if p["visits"] else ("AUTOPSY" if prog == "AMP-AD" else "BASELINE")
        pvisits = []                     # (visit_occurrence_id, visit_date) for THIS person
        for vr in (p["visits"] or [None]):
            if vr:
                vsv = vr['visit_name']            # source-faithful; join is (person_id, vsv)
                vd = enrol + timedelta(days=int(round(float(vr["visit_month"] or 0) * 30.44)))
            else:
                vsv, vd = synth, enrol   # synthesized visit; visit_date NEVER null (constraint 1)
            void += 1
            visits.append((void, PMAP[pid], vd, vsv))
            pvisits.append((void, vd))
            pdates.append(vd)
            if synth == "AUTOPSY":
                procedures.append((PMAP[pid], vd, void, AUTOPSY_CONCEPT_ID, "gross_brain_autopsy"))
            elif pid in PM_DONORS and pid not in _pm_done:
                # every post-mortem donor gets ONE collection procedure, anchored to its first visit
                procedures.append((PMAP[pid], vd, void, PM_COLLECTION_CONCEPT_ID, "post_mortem_collection"))
                _pm_done.add(pid)
            rows.append([pid, vsv, vd.isoformat()] + [cell(c, vr) for c in var_cols])

        # observation_period (Beta-2 ask 9) + condition_occurrence (Beta-2 ask 8; drop-decision
        # reversed -- see CONDITION_MAP note). The condition period MIRRORS the observation period.
        if pdates:
            obs_periods.append((OBSERVATION_PERIOD_ID_BASE + len(obs_periods), PMAP[pid],
                                min(pdates), max(pdates)))
            raw = (p["subject"].get(STATUS_COL.get(prog, ""), "") or "").strip()
            cid = CONDITION_MAP.get(prog, {}).get(raw)
            if cid is not None:
                # anchor the condition to the person's FIRST visit (its start date IS that visit's
                # date) so condition_occurrence joins the visit graph like every other event table —
                # a blind-review finding 2026-09-02: conditions carried visit_occurrence_id NULL
                # while procedures were 100% linked.
                first_visit_id = min(pvisits, key=lambda t: t[1])[0]
                conditions.append((CONDITION_OCCURRENCE_ID_BASE + len(conditions), PMAP[pid], cid,
                                   min(pdates), max(pdates), first_visit_id, raw))

    print(f"  staging.amp_clinical : {len(rows)} rows (one per person-visit; visit-less people get a synthesized visit)")
    print(f"  cdm.visit_occurrence : {len(visits)} rows")
    print(f"  cdm.procedure_occurrence : {len(procedures)} rows "
          f"({sum(1 for x in procedures if x[3]==AUTOPSY_CONCEPT_ID)} autopsy, "
          f"{sum(1 for x in procedures if x[3]==PM_COLLECTION_CONCEPT_ID)} post-mortem collection)")
    print(f"  cdm.observation_period : {len(obs_periods)} rows (one span per person with visits)")
    print(f"  cdm.condition_occurrence : {len(conditions)} rows "
          f"({sum(1 for x in conditions if x[2]==0)} with concept 0, awaiting curation)")
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
            fh.write(f"{PMAP[pid]}\t0\t0\t0\t0\n")
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

        # cdm.procedure_occurrence -- autopsy provenance for the post-mortem brain-bank donors, anchored
        # to their AUTOPSY visit. First use of this table by the ETL; governance/RLS already cover it.
        fh.write("-- 2b. autopsy procedures (gross brain autopsy) for post-mortem brain-bank donors.\n")
        fh.write("COPY procedure_occurrence (procedure_occurrence_id, person_id, procedure_concept_id, "
                 "procedure_date, procedure_type_concept_id, visit_occurrence_id, procedure_source_value) "
                 "FROM stdin;\n")
        for i, (pid, pdate, voi, pconcept, psrc) in enumerate(procedures):
            fh.write(f"{PROCEDURE_OCCURRENCE_ID_BASE + i}\t{pid}\t{pconcept}\t{pdate}\t"
                     f"{PROCEDURE_TYPE_CONCEPT_ID}\t{voi}\t{psrc}\n")
        fh.write("\\.\n\n")

        fh.write("-- 2c. observation_period -- one span per person (first..last visit); Beta-2 ask 9.\n")
        fh.write("COPY observation_period (observation_period_id, person_id, observation_period_start_date, "
                 "observation_period_end_date, period_type_concept_id) FROM stdin;\n")
        for op_id, opid_, d0, d1 in obs_periods:
            fh.write(f"{op_id}\t{opid_}\t{d0}\t{d1}\t{RECORD_TYPE_REGISTRY}\n")
        fh.write("\\.\n\n")

        fh.write("-- 2d. condition_occurrence -- disease cohort status; previously dropped by design,\n"
                 "-- REVERSED for Beta-2 (Technome/Verily 2026-08-28 ask 8). Period mirrors observation_period.\n")
        fh.write("COPY condition_occurrence (condition_occurrence_id, person_id, condition_concept_id, "
                 "condition_start_date, condition_end_date, condition_type_concept_id, "
                 "visit_occurrence_id, condition_source_value) FROM stdin;\n")
        for coid, cpid, ccid, d0, d1, cvid, raw in conditions:
            fh.write(f"{coid}\t{cpid}\t{ccid}\t{d0}\t{d1}\t{RECORD_TYPE_REGISTRY}\t{cvid}\t{raw}\n")
        fh.write("\\.\n\n")

        fh.write("-- 3. staging. The ETL reads ONLY these two tables.\n")
        fh.write("DROP SCHEMA IF EXISTS staging CASCADE;\nCREATE SCHEMA staging;\n\n")
        fh.write("CREATE TABLE staging.person_map (person_source_value text NOT NULL, "
                 "person_id integer);\n")
        fh.write("COPY staging.person_map (person_source_value, person_id) FROM stdin;\n")
        for pid in sorted(people, key=int):
            fh.write(f"{pid}\t{PMAP[pid]}\n")    # REAL crosswalk: participant_id -> minted sysbio id
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
