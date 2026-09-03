#!/usr/bin/env python3
"""Render the CDM extension load -> cdm_load/extensions_load.sql (COPY FROM stdin; self-contained).
Reads ONLY output/*.csv + inputs/biospecimen_type_crosswalk.tsv. No DB. Deterministic.
Emits: cdm.specimen (AD tissue + RA-SLE biospecimen, concept via crosswalk), cdm.assay, cdm.files,
cdm.assay_to_specimen, cdm.assay_input_file, and (Beta-2 ask 7, ruled 2026-09-02) one
cdm.observation row per (file, donor) carrying the file name, pointed at cdm.files through the
CDM event-linkage pair (observation_event_id + obs_event_field_concept_id).
Surrogate ids are the deterministic ids minted in gen.
person_id is the MINTED sequential sysbio id (staging.person_map is the crosswalk; Beta-2 ask 4). Run AFTER concept_seed + staging + facts.
"""
import csv, io, json, os, sys
from datetime import date, timedelta
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT  = os.path.join(ROOT, "output")
SQL  = os.path.join(ROOT, "cdm_load", "extensions_load.sql")
PROGS = ["AMP-AD", "AMP-PD", "AMP-CMD", "AMP-RA-SLE"]
# specimen_date is derived from the person's own visit, using the SAME deterministic rule as
# 06_render_cdm_load.py so a specimen and its visit agree. Falls back to the person's enrolment
# date when the specimen names no visit we hold.
CFG = json.load(open(os.path.join(ROOT, "config", "cohort.json")))


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


def enrolment_date(pid):
    """Beta-2 contract: baseline visit anchored at the 1900-01-01 sentinel; same rule as 06."""
    return date(1900, 1, 1)

def visit_months():
    """(participant_id, visit_name) -> visit_month, from the generated visit CSVs."""
    m = {}
    for prog in PROGS:
        try:
            for r in rd(f"{prog}_visit.csv"):
                m[(r["participant_id"], r.get("visit_name") or "")] = r.get("visit_month") or "0"
        except FileNotFoundError:
            pass
    return m

def specimen_date(pid, visit_name, vmonths):
    enrol = enrolment_date(pid)
    mo = vmonths.get((pid, visit_name or ""))
    if mo is None:
        return enrol
    return enrol + timedelta(days=int(round(float(mo or 0) * 30.44)))
SPECIMEN_TYPE = 32879            # 'Registry' — these specimens come from cohort/brain-bank registries, not a clinical lab
# ---- Beta-2 ask 7 (ruled 2026-09-02): file_name -> cdm.observation, one row per (file, donor).
# In this generator every file belongs to exactly one participant, so (file x donor) == one row per file.
FILE_OBS_ID_BASE   = 6_000_000   # dedicated id range; mapped-ETL observation ids (sequences) stay far below
FILE_OBS_CONCEPT   = 4303445     # 'Research data collection' (SNOMED, Observation domain, Standard; curated)
FILE_OBS_QUALIFIER = 1091809     # 'Molecular biology report Document' (LOINC 104487-4, Standard) — omics qualifier; seeded in exports sqlite
FILE_FIELD_CONCEPT = 2000000001  # 'files.file_id' — SysBio 2B-range field concept (table/field-defining minting, ruled in); seeded in exports sqlite
FILE_OBS_TYPE      = 32879       # 'Registry' — house record-type convention
# anatomic site source_value -> OMOP Spec Anatomic Site concept. Fluids (blood, plasma) have NO
# anatomic site concept in OMOP -- they are specimen types, so the concept is legitimately NULL.
ANATOMIC_SITE = {"hypothalamus": 4195703}   # 'Hypothalamic structure' (SNOMED, standard, valid)
# specimen-derivation lineage (REDESIGNED 2026-09-03, maintainer ruling): the old 32554/32553
# 'Sub-specimen of' pair is NON-STANDARD (only 10 Relationship concepts are Standard; that pair
# is not among them). Replacement — fully standard end to end: one cdm.measurement row per
# derivation pair carrying the PARENT specimen identifier, its event fields pointing at the
# CHILD specimen, reinforced through fact_relationship with the standard Measurement<->Specimen
# pair to the PARENT.
SPECIMEN_DOMAIN     = 36          # 'Specimen' domain concept (fact_relationship.domain_concept_id_*)
MEASUREMENT_DOMAIN  = 21          # 'Measurement' domain concept
LINEAGE_MEAS_ID_BASE = 7_000_000  # id range for derivation measurements (map-ETL ids stay far below)
LINEAGE_MEAS_CONCEPT = 1176306    # 'Unique identifier [Identifier] of Initial sample' (LOINC, S; curated)
SPECIMEN_FIELD_CONCEPT = 1147049  # 'specimen.specimen_id' (CDM vocabulary, Standard Field concept)
REL_MEAS_TO_SPECIMEN = 32668      # 'Measurement to Specimen' — one of the 10 STANDARD Relationship concepts
REL_SPECIMEN_TO_MEAS = 32669      # 'Specimen to Measurement' — its standard reciprocal

def rd(name):
    p = os.path.join(OUT, name)
    return list(csv.DictReader(open(p, newline="", encoding="utf-8"))) if os.path.exists(p) else []

def crosswalk():
    lines = [l for l in open(os.path.join(ROOT, "inputs", "biospecimen_type_crosswalk.tsv"), encoding="utf-8")
             if not l.startswith("#")]
    return {r["source_value"]: int(r["specimen_concept_id"])
            for r in csv.DictReader(io.StringIO("".join(lines)), delimiter="\t")}

def esc(v):
    if v is None or v == "": return "\\N"
    return str(v).replace("\\", "\\\\").replace("\t", " ").replace("\n", " ").replace("\r", " ")

def copy_block(f, table, cols, rows):
    if not rows: return 0
    f.write(f"COPY cdm.{table} ({', '.join(cols)}) FROM stdin;\n")
    for r in rows:
        f.write("\t".join(esc(r.get(c.strip(chr(34)))) for c in cols) + "\n")
    f.write("\\.\n\n")
    return len(rows)

def main():
    xw = crosswalk()
    def concept_for(v): return xw.get(v, 0)
    vmonths = visit_months()
    PMAP = person_id_map()          # same mint rule as 06 -- minted sysbio person_id
    specimens, assays, files, a2s, aif = [], [], [], [], []
    lineage_pairs = []   # (child_specimen_id, parent_specimen_id) from RA-SLE parentBiospecimenID

    for prog in PROGS:
        # specimen: AMP-AD/PD/CMD from {prog}_specimen.csv (the omics specimens_* shape);
        # AMP-RA-SLE from the ARK specimen CSV (biospecimenType + parentBiospecimenID lineage).
        if prog == "AMP-RA-SLE":
            for r in rd("AMP-RA-SLE_specimen.csv"):
                bid = r.get("biospecimenID")
                if not bid: continue
                specimens.append({"specimen_id": bid, "person_id": PMAP[r["participant_id"]],
                    "specimen_concept_id": concept_for(r.get("biospecimenType") or ""),
                    "specimen_type_concept_id": SPECIMEN_TYPE,
                    "specimen_date": specimen_date(r["participant_id"], r.get("visit_name"), vmonths).isoformat(),
                    "specimen_source_id": "",   # Beta-2 ask 6: blanked (\N)
                    "specimen_source_value": r.get("biospecimenType") or "",
                    "anatomic_site_concept_id": ANATOMIC_SITE.get((r.get("anatomicalSite") or "").strip().lower(), ""),
                    "anatomic_site_source_value": r.get("anatomicalSite") or ""})
                parent = (r.get("parentBiospecimenID") or "").strip()
                if parent:
                    lineage_pairs.append((bid, parent))
        else:
            for r in rd(f"{prog}_specimen.csv"):
                specimens.append({"specimen_id": r["specimen_id"], "person_id": PMAP[r["participant_id"]],
                    "specimen_concept_id": concept_for(r["specimen_source_value"]),
                    "specimen_type_concept_id": SPECIMEN_TYPE,
                    "specimen_date": specimen_date(r["participant_id"], r.get("visit_name"), vmonths).isoformat(),
                    "specimen_source_id": "",   # Beta-2 ask 6: blanked (\N)
                    "specimen_source_value": r["specimen_source_value"],
                    "anatomic_site_concept_id": ANATOMIC_SITE.get((r.get("anatomic_site_source_value") or "").strip().lower(), ""),
                    "anatomic_site_source_value": r.get("anatomic_site_source_value") or ""})
        assays += rd(f"{prog}_assay.csv")
        files  += rd(f"{prog}_file.csv")
        a2s    += rd(f"{prog}_assay_to_specimen.csv")
        aif    += rd(f"{prog}_assay_input_file.csv")

    # GATE: every specimen must resolve through the crosswalk. specimen_concept_id = 0 means an
    # unmapped source value — either the generator emitted a token outside its programme's
    # vocabulary (the 2026-09 tissue bug: a pooled fidelity draw put CMD/KPMP tissue on 92% of
    # AD specimens, 31% of cdm.specimen at concept 0) or the crosswalk is missing a row. Both
    # are build errors, not data: fail loudly instead of shipping concept-0 rows.
    zero = [s["specimen_source_value"] for s in specimens if not s["specimen_concept_id"]]
    if zero:
        from collections import Counter
        top = Counter(zero).most_common(10)
        sys.exit(f"FATAL: {len(zero)}/{len(specimens)} specimen rows have specimen_concept_id=0 "
                 f"(unmapped source values, top: {top}) — add crosswalk rows or fix the generator")

    # Beta-2 ask 7: file-name observation rows, one per (file, donor). The generator mints
    # per-participant files, so the donor is the file's own participant. qualifier layer:
    # concept = omics document, source_value = the assay's modality for sortability.
    # DATA FILES ONLY (maintainer ruling 2026-09-03): dictionaries, protocols, templates, READMEs
    # and similar documentation must never enter cdm.files. The generator mints only data files
    # today; this guard makes that a property, not an accident.
    NON_DATA = ("dictionary", "protocol", "template", "readme", "codebook", "datadictionary",
                "data_dictionary", "manifest.", "changelog", "release_note")
    n_before = len(files)
    files = [r for r in files if not any(t in (r.get("file_name") or "").lower() for t in NON_DATA)]
    if len(files) != n_before:
        print(f"files guard: excluded {n_before - len(files)} non-data files (dictionary/protocol/etc.)")

    assay_type = {a["assay_id"]: a.get("assay_type") or "" for a in assays}
    # donor resolution, in order: the file's own participant; the owners of its assay's
    # specimens; else (cohort-level harmonized products with no assay of their own) the owners
    # of all specimens behind the assays that CONTRIBUTE to it via assay_input_file.
    spec_owner = {s["specimen_id"]: s["person_id"] for s in specimens}
    assay_donors = {}
    for e in a2s:
        p = spec_owner.get(e["specimen_id"])
        if p is not None:
            assay_donors.setdefault(e["assay_id"], set()).add(p)
    file_contrib = {}
    for e in aif:
        file_contrib.setdefault(e["file_id"], set()).add(e["assay_id"])
    # Biospecimen metadata file records (ruling 2026-09-03): a specimen exists because a file
    # attests it. Assay outputs only evidence ASSAYED specimens; each programme's biospecimen
    # metadata file is the evidence for the rest — banked and parent specimens included. One
    # record per programme; EVERY participant of the programme is a member (their specimen rows
    # live in that file), so no specimen is file-less and all participants appear in >=1 file.
    META_FILE_BASE = 159_000_000
    meta_members = {}                               # file_id -> minted person ids
    for i, prog in enumerate(PROGS):
        subj = rd(f"{prog}_subject.csv")
        if not subj:
            continue
        fid = META_FILE_BASE + i + 1
        files.append({"participant_id": "", "file_id": fid, "assay_id": "",
                      "file_name": f"{prog}_biospecimen_metadata.csv",
                      "file_role": "source_metadata", "analysis_type": "metadata",
                      "file_format": "csv", "biosample_type": "", "tissue": "", "cell_type": "",
                      "species": "Homo sapiens", "study": prog, "grant": prog,
                      "file_size_bytes": 4096 + 512 * len(subj), "drs_id": f"drs://sysbio/{fid}"})
        meta_members[fid] = sorted(PMAP[r["participant_id"]] for r in subj)

    file_obs, skipped_no_donor = [], 0
    oid = FILE_OBS_ID_BASE
    for r in sorted(files, key=lambda x: int(x["file_id"])):
        pid_raw = (r.get("participant_id") or "").strip()
        is_meta = int(r["file_id"]) > META_FILE_BASE
        if is_meta:
            donors = meta_members[r["file_id"]]
        elif pid_raw:
            donors = [PMAP[pid_raw]]
        else:
            donors = sorted(assay_donors.get(r.get("assay_id") or "", ()))
            if not donors:
                agg = set()
                for aid in file_contrib.get(r["file_id"], ()):
                    agg |= assay_donors.get(aid, set())
                donors = sorted(agg)
        if not donors:
            skipped_no_donor += 1
            continue
        for donor in donors:
            file_obs.append({
                "observation_id": oid,
                "person_id": donor,
                "observation_concept_id": FILE_OBS_CONCEPT,
                "observation_date": enrolment_date(pid_raw).isoformat(),
                "observation_type_concept_id": FILE_OBS_TYPE,
                "value_as_string": r["file_name"],
                "qualifier_concept_id": "" if is_meta else FILE_OBS_QUALIFIER,
                "observation_source_value": "file_name",
                "qualifier_source_value": ("biospecimen_metadata" if is_meta
                                           else assay_type.get(r.get("assay_id") or "", "")),
                "value_source_value": r.get("file_role") or "",
                "observation_event_id": r["file_id"],
                "obs_event_field_concept_id": FILE_FIELD_CONCEPT,
            })
            oid += 1
    if skipped_no_donor:
        print(f"file_name obs: {skipped_no_donor} cohort-level files skipped (no participant and no specimen-linked assay)")

    # specimen derivation lineage — standard-concepts-only design (RA-SLE parent links, AD single-autopsy):
    # measurement row per pair (states the parent id, event fields -> child specimen) + standard
    # Measurement<->Specimen fact_relationship pair to the parent.
    spec_ids = {s["specimen_id"] for s in specimens}
    spec_owner_l = {s["specimen_id"]: s["person_id"] for s in specimens}
    frels, lineage_meas = [], []
    for i, (child, parent) in enumerate(sorted(set(lineage_pairs))):
        if child in spec_ids and parent in spec_ids:
            mid = LINEAGE_MEAS_ID_BASE + i
            lineage_meas.append({
                "measurement_id": mid,
                "person_id": spec_owner_l[child],
                "measurement_concept_id": LINEAGE_MEAS_CONCEPT,
                "measurement_date": date(1900, 1, 1).isoformat(),
                "measurement_type_concept_id": SPECIMEN_TYPE,      # 32879 'Registry', house convention
                "measurement_source_value": "parent_specimen_id",
                "value_source_value": parent,                       # minted synthetic id, join-safe
                "measurement_event_id": child,
                "meas_event_field_concept_id": SPECIMEN_FIELD_CONCEPT,
            })
            frels.append({"domain_concept_id_1": MEASUREMENT_DOMAIN, "fact_id_1": mid,
                          "domain_concept_id_2": SPECIMEN_DOMAIN, "fact_id_2": parent,
                          "relationship_concept_id": REL_MEAS_TO_SPECIMEN})
            frels.append({"domain_concept_id_1": SPECIMEN_DOMAIN, "fact_id_1": parent,
                          "domain_concept_id_2": MEASUREMENT_DOMAIN, "fact_id_2": mid,
                          "relationship_concept_id": REL_SPECIMEN_TO_MEAS})

    with open(SQL, "w", encoding="utf-8") as f:
        f.write("-- GENERATED by scripts/11_render_extensions.py — CDM extension load (specimen/assay/files).\n")
        f.write("-- Self-contained; reads no DB. Run after concept_seed + staging + facts.\n")
        f.write("SET search_path = cdm, public;\n\n")
        ns = copy_block(f, "specimen",
            ["specimen_id","person_id","specimen_concept_id","specimen_type_concept_id","specimen_date",
             "specimen_source_id","specimen_source_value","anatomic_site_concept_id",
             "anatomic_site_source_value"], specimens)
        nfr = copy_block(f, "fact_relationship",
            ["domain_concept_id_1","fact_id_1","domain_concept_id_2","fact_id_2","relationship_concept_id"], frels)
        na = copy_block(f, "assay",
            ["assay_id","assay_source_value","assay_type","platform","suspension_type","analyte_type","analysis_pipeline"], assays)
        nf = copy_block(f, "files",
            ["file_id","file_name","assay_id","file_role","study","\"grant\"","analysis_type","biosample_type",
             "tissue","cell_type","species","file_format","file_size_bytes","drs_id"],
            [{**r, "grant": r.get("grant")} for r in files])
        n2 = copy_block(f, "assay_to_specimen", ["assay_id","specimen_id"], a2s)
        ni = copy_block(f, "assay_input_file", ["assay_id","file_id"], aif)
        no = copy_block(f, "observation",
            ["observation_id","person_id","observation_concept_id","observation_date",
             "observation_type_concept_id","value_as_string","qualifier_concept_id",
             "observation_source_value","qualifier_source_value","value_source_value",
             "observation_event_id","obs_event_field_concept_id"], file_obs)
        nl = copy_block(f, "measurement",
            ["measurement_id","person_id","measurement_concept_id","measurement_date",
             "measurement_type_concept_id","measurement_source_value","value_source_value",
             "measurement_event_id","meas_event_field_concept_id"], lineage_meas)
    print(f"extensions_load.sql: specimen={ns} fact_relationship={nfr} assay={na} files={nf} "
          f"assay_to_specimen={n2} assay_input_file={ni} file_name_obs={no} lineage_meas={nl}")

if __name__ == "__main__":
    main()
