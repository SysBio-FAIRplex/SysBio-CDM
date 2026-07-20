"""
Pipeline tests for the synthetic AMP generator. Run in the amp-synth env:

    conda run -n amp-synth pytest tests/ -q

Design principle (learned the hard way): assert on the OUTPUT BYTES, not on the model that produced
them. Each test reads output/*.csv directly. The meta-test at the end proves QC actually catches a
broken cohort -- so a green suite is meaningful.
"""
import csv
import glob
import hashlib
import os
import subprocess
import sys
from collections import Counter, defaultdict

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")
PY = sys.executable


def run(script):
    return subprocess.run([PY, os.path.join(ROOT, "scripts", script)],
                          capture_output=True, text=True)


def load(fname):
    with open(os.path.join(OUT, fname), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def programs():
    # One subject file per programme. (rsplit on *_*.csv would mint bogus programmes from the omics
    # grains that carry underscores, e.g. 'AMP-AD_assay_to_specimen' -> 'AMP-AD_assay_to'.)
    return sorted({os.path.basename(f)[:-len("_subject.csv")]
                   for f in glob.glob(os.path.join(OUT, "*_subject.csv"))})


@pytest.fixture(scope="session", autouse=True)
def generated():
    """Generate the cohort once for the whole session (self-contained: no DB)."""
    r = run("03_generate.py")
    assert r.returncode == 0, "03_generate failed:\n" + r.stderr[-2000:]


# ── determinism (metamorphic) ────────────────────────────────────────────────
def test_determinism():
    def hashes():
        return {os.path.basename(f): hashlib.sha256(open(f, "rb").read()).hexdigest()
                for f in glob.glob(os.path.join(OUT, "*.csv"))}
    run("03_generate.py"); a = hashes()
    run("03_generate.py"); b = hashes()
    assert a == b, "generation is not byte-deterministic across runs"


# ── conformance: the QC gate must pass ───────────────────────────────────────
def test_qc_passes():
    r = run("04_qc.py")
    assert r.returncode == 0, "04_qc reported failures:\n" + r.stdout[-2500:]


# ── structure ────────────────────────────────────────────────────────────────
def test_subject_participant_unique():
    for prog in programs():
        subj = load(f"{prog}_subject.csv")
        ids = [r["participant_id"] for r in subj]
        assert len(ids) == len(set(ids)), f"{prog}_subject: duplicate participant_id"


def test_referential_integrity():
    for prog in programs():
        known = {r["participant_id"] for r in load(f"{prog}_subject.csv")}
        for grain in ("visit", "specimen"):
            p = os.path.join(OUT, f"{prog}_{grain}.csv")
            if os.path.exists(p):
                for r in load(f"{prog}_{grain}.csv"):
                    assert r["participant_id"] in known, \
                        f"{prog}_{grain}: participant {r['participant_id']} not in subject file"


def test_visit_month_increasing():
    for prog in programs():
        p = os.path.join(OUT, f"{prog}_visit.csv")
        if not os.path.exists(p):
            continue
        per = defaultdict(list)
        for r in load(f"{prog}_visit.csv"):
            if r.get("visit_month"):
                per[r["participant_id"]].append(float(r["visit_month"]))
        for pid, months in per.items():
            assert months == sorted(months), f"{prog}: participant {pid} visit_month not increasing"


# ── person-first grain separation ────────────────────────────────────────────
def test_subject_file_has_no_visit_columns():
    for prog in programs():
        rows = load(f"{prog}_subject.csv")
        if rows:
            assert "visit_month" not in rows[0] and "visit_name" not in rows[0], \
                f"{prog}_subject carries a visit column (person-first violation)"


# ── completeness: no column is emitted entirely empty ────────────────────────
def test_no_all_empty_columns():
    for f in glob.glob(os.path.join(OUT, "*.csv")):
        rows = load(os.path.basename(f))
        if not rows:
            continue
        for col in rows[0]:
            assert any((r.get(col) or "") != "" for r in rows), \
                f"{os.path.basename(f)}: column {col!r} is entirely empty"


# ── fidelity sanity: distributions are real, not uniform ─────────────────────
def test_fidelity_apoe_e3e3_dominant():
    rows = load("AMP-AD_subject.csv")
    apoe = Counter(r["apoe_genotype"] for r in rows if r.get("apoe_genotype"))
    if apoe:  # only ROS/MAP subjects carry it
        top, _ = apoe.most_common(1)[0]
        assert str(top) == "33", f"APOE not E3E3(33)-dominant (uniform draw?): {dict(apoe)}"


# ── golden row/column counts (regression tripwire) ───────────────────────────
def test_golden_manifest():
    golden_path = os.path.join(ROOT, "tests", "golden_manifest.tsv")
    if not os.path.exists(golden_path):
        pytest.skip("no golden_manifest.tsv (freeze one with tests/freeze_golden.sh)")
    golden = {}
    with open(golden_path, newline="") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            golden[r["file"]] = (int(r["rows"]), int(r["cols"]))
    for f in glob.glob(os.path.join(OUT, "*.csv")):
        b = os.path.basename(f)
        rows = load(b)
        cols = len(rows[0]) if rows else 0
        assert b in golden, f"{b} is new since the golden was frozen"
        assert (len(rows), cols) == golden[b], \
            f"{b}: {(len(rows), cols)} != golden {golden[b]} (intentional? re-freeze the golden)"


# ── META-TEST: prove QC catches a broken cohort ──────────────────────────────
def test_qc_catches_a_broken_cohort():
    """A duplicated participant must make 04_qc fail. If it doesn't, the whole suite is blind."""
    subj = glob.glob(os.path.join(OUT, "*_subject.csv"))[0]
    original = open(subj, encoding="utf-8").read()
    try:
        lines = original.splitlines()
        with open(subj, "w", encoding="utf-8") as fh:
            fh.write(original.rstrip("\n") + "\n" + lines[1] + "\n")  # duplicate the first data row
        r = run("04_qc.py")
        assert r.returncode != 0, "04_qc did NOT catch a duplicate participant -- the tests are blind"
    finally:
        with open(subj, "w", encoding="utf-8") as fh:
            fh.write(original)
        run("03_generate.py")  # restore a clean cohort for any later run
