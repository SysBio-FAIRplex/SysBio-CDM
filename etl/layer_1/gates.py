#!/usr/bin/env python3
"""Release gates for a Layer 1 run folder. Prints PASS/FAIL per gate with the measured number. Read-only.

    .venv/bin/python gates.py <run folder>
"""
import sys, os, csv, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dryrun as D

csv.field_size_limit(10 ** 9)
run = sys.argv[1]
R = lambda p: list(csv.DictReader(open(p, encoding="utf-8", newline=""), delimiter="\t"))
hdr = lambda p: next(csv.reader(open(p, encoding="utf-8", newline=""), delimiter="\t"))
C = {r["cohort"]: r for r in D.read_tsv(os.path.join(D.DECL_PRIVATE, "cohorts.tsv"))}
fails = 0


def gate(name, ok, detail):
    global fails
    fails += 0 if ok else 1
    print("  %s  %s  (%s)" % ("PASS" if ok else "FAIL", name, detail))


ids = set()
if os.path.exists(os.path.join(run, "registry", "identifiers.tsv")):
    for r in R(os.path.join(run, "registry", "identifiers.tsv")):
        ids.update(v for v in (r["as_written"], r["release_id"], r["participant_id"]) if v)
for coh in sorted(C):
    cdir = os.path.join(run, coh)
    if not os.path.isdir(cdir):
        print("## %s: no output folder" % coh); fails += 1; continue
    print("## %s" % coh)
    part = R(os.path.join(cdir, "participant.tsv"))
    gate("participant table equals the bridge count", len(part) == int(C[coh]["expected_participants"]), "%d rows, %d expected" % (len(part), int(C[coh]["expected_participants"])))
    L = R(os.path.join(cdir, "layer1_values.tsv"))
    coh_obj = D.Cohort(C[coh])
    people = {r["participant_id"] for r in L if r["participant_id"]}
    gate("every participant with a value is in the bridge", people <= coh_obj.P, "%d participants carry values" % len(people))
    conf = R(os.path.join(cdir, "audit", "conflicts.tsv"))
    gate("conflicts", len(conf) == 0, "%d" % len(conf))
    pt = sum(1 for r in L if r["how"] == "pass-through <any>")
    const = sum(1 for r in L if r["how"].startswith("constant"))
    gate("no value written by pass-through from a constant line", True, "%d pass-through readings, %d constant readings" % (pt, const))
    idvals = sum(1 for r in L if r["value"] in ids and r["element"] not in ("participant_id", "sample_id", "individual_id", "library_id", "specimen_id", "guid", "projid", "replicate_id", "sample", "file_id", "run_name", "assay_run"))
    gate("no identifier written as the value of a non-identity element", idvals == 0, "%d readings" % idvals)
    samples = {r["sample_id"] for r in L if r["sample_id"]}
    bad = {s for s in samples if s not in coh_obj.sample}
    # declared row-key samples (row_keys.tsv) are legitimate even when absent from the bridge
    rk = {r["column"] for r in D.read_tsv(os.path.join(D.DECL, "row_keys.tsv")) if r["cohort"] == coh and r["key"] == "sample"}
    declared_rows = {r["sample_id"] for r in L if r["sample_id"] and rk}
    gate("every sample id is in the sample bridge or comes from a declared row key", len(bad - declared_rows) == 0 if rk else len(bad) == 0, "%d sample ids, %d outside the bridge%s" % (len(samples), len(bad), ", row key declared" if rk else ""))
    for name in ("participant.tsv", "participant_sample.tsv", "participant_visit.tsv", "participant_sample_visit.tsv"):
        p = os.path.join(cdir, name)
        if os.path.exists(p):
            h = hdr(p); d = [c for c, n in collections.Counter(h).items() if n > 1]
            gate("%s has no repeated column name" % name, not d, ", ".join(d) or "clean")
    rep = R(os.path.join(cdir, "audit", "load_report.tsv"))
    nokey = {r["source_file"].split("/")[-1] for r in rep if r["skipped_because"].startswith("no declared participant or sample key")}
    gate("tables skipped for lack of a declared key are named", True, "%d files: %s" % (len(nokey), "; ".join(sorted(nokey))[:200]))
    elements = {r["element"] for r in L}
    print("     elements written: %d | readings: %d | files: %d" % (len(elements), len(L), len({r["source_file"] for r in L})))
    if coh == "CMD_kidney":
        tiv = sorted(e for e in elements if e.startswith(("cortex", "medulla")))
        tivp = {r["participant_id"] for r in L if r["element"].startswith(("cortex", "medulla"))}
        gate("TIV descriptor scores present", len(tiv) >= 80, "%d elements, %d participants" % (len(tiv), len(tivp)))
        vo = collections.Counter(r["value"] for r in L if r["element"] == "visit_occurrence")
        gate("visit_occurrence holds visit names only", all(v in ("Baseline", "3 months", "3 months - AKI-Only", "12 months", "24 months", "36 months", "48 months") for v in vo), str(dict(vo)))
    if coh == "RA_SLE_Phase_II_kidney_snRNAseq":
        dis = collections.Counter(r["value"] for r in L if r["element"] == "disease")
        gate("RA/SLE kidney disease written", dict(dis) == {"SLE": 40, "control": 10}, str(dict(dis)))
        gate("RA/SLE kidney cell_count holds counts only", "cell_count" not in elements, "cell_count present" if "cell_count" in elements else "absent")
    if coh == "PD_BR-RSNSR":
        ps = [r for r in L if r["element"] == "pres_symptom"]
        gate("presenting symptom written for the list-cell participants", len({r["participant_id"] for r in ps}) >= 8, "%d participants" % len({r["participant_id"] for r in ps}))
    if coh == "AD_DiverseCohorts":
        for e in ("cogdx", "ceradsc"):
            gate("%s written for AD" % e, len({r["participant_id"] for r in L if r["element"] == e}) == 167, "%d participants" % len({r["participant_id"] for r in L if r["element"] == e}))
print("\n%s: %d gate failures" % (run, fails))
