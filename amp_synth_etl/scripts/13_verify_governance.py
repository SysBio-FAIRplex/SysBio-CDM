#!/usr/bin/env python3
"""End-to-end GOVERNANCE TEST for the SysBio-CDM self-contained build.

Proves the record-level RLS actually restricts — it does NOT trust the loader. Expected per-program
person sets are computed INDEPENDENTLY from output/*_subject.csv (shares NO code / spec / assumption with
the render or ETL — structural independence by design), then compared against what
each Postgres role can actually SELECT.

Connects ONLY to the throwaway build DB that build_selfcontained.sh just created (default
sysbio_cdm_selfcontained). That is EXECUTING THE PIPELINE'S OWN TEST against its own throwaway output —
NOT sourcing schema/data from a standing DB (which is forbidden). Each check is its own `psql` session,
so `SET ROLE` cannot leak between checks. Exits non-zero on any failure.

  python scripts/13_verify_governance.py [db=sysbio_cdm_selfcontained]
"""
import csv, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT  = os.path.join(ROOT, "output")
DB   = sys.argv[1] if len(sys.argv) > 1 else "sysbio_cdm_selfcontained"

SUBJECT_FILES = {"AMP-PD": "AMP-PD_subject.csv", "AMP-AD": "AMP-AD_subject.csv",
                 "AMP-CMD": "AMP-CMD_subject.csv", "AMP-RA-SLE": "AMP-RA-SLE_subject.csv"}

GOVERNED   = ["observation", "measurement", "specimen", "files", "procedure_occurrence"]
UNGOVERNED = ["person", "visit_occurrence", "concept", "assay", "fact_relationship"]

FAIL = []


def persons_by_program():
    m = {}
    for prog, fn in SUBJECT_FILES.items():
        p = os.path.join(OUT, fn)
        if os.path.exists(p):
            m[prog] = {int(r["participant_id"]) for r in csv.DictReader(open(p, newline="", encoding="utf-8"))}
    return m


def q(role, sql):
    """Run sql (optionally under SET ROLE) in a fresh psql session; return list of output lines."""
    prefix = f"SET ROLE {role}; " if role else ""
    env = dict(os.environ)          # PGPASSWORD comes from the environment / ~/.pgpass
    out = subprocess.run(["psql", "-h", "localhost", "-p", "5433", "-U", "postgres", "-d", DB,
                          "-tAqc", prefix + sql], capture_output=True, text=True, env=env)
    if out.returncode != 0:
        raise RuntimeError(f"psql failed (role={role}): {out.stderr.strip()}\n  SQL: {sql}")
    return [l for l in out.stdout.splitlines() if l != ""]


def scalar(role, sql):
    return int(q(role, sql)[0])


def col(role, sql):
    return set(int(x) for x in q(role, sql))


def studies(role):
    return set(q(role, "SELECT DISTINCT study FROM cdm.files"))


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  — {detail}" if (detail and not ok) else ""))
    if not ok:
        FAIL.append(name)


def main():
    prog = persons_by_program()
    ad, rasle = prog.get("AMP-AD", set()), prog.get("AMP-RA-SLE", set())
    print(f"expected persons (from output CSVs): AMP-AD={len(ad)}  AMP-RA-SLE={len(rasle)}\n")

    # Unrestricted totals (superuser bypasses RLS) — the ground truth to compare role-scoped views against.
    tot = {t: scalar(None, f"SELECT count(*) FROM cdm.{t}") for t in GOVERNED + UNGOVERNED}
    print(f"unrestricted totals: " + " ".join(f"{t}={tot[t]}" for t in GOVERNED) + "\n")

    # ---- ad_user isolation: sees ONLY AMP-AD governed rows ----
    ad_obs_p  = col("ad_user", "SELECT DISTINCT person_id FROM cdm.observation")
    ad_meas_p = col("ad_user", "SELECT DISTINCT person_id FROM cdm.measurement")
    ad_spec_p = col("ad_user", "SELECT DISTINCT person_id FROM cdm.specimen")
    check("ad_user: observation persons ⊆ AMP-AD", ad_obs_p <= ad, f"stray={sorted(ad_obs_p - ad)[:5]}")
    check("ad_user: measurement persons ⊆ AMP-AD", ad_meas_p <= ad, f"stray={sorted(ad_meas_p - ad)[:5]}")
    check("ad_user: specimen persons ⊆ AMP-AD", ad_spec_p <= ad, f"stray={sorted(ad_spec_p - ad)[:5]}")
    check("ad_user: files.study all = AMP-AD", studies("ad_user") <= {"AMP-AD"}, f"studies={studies('ad_user')}")
    check("ad_user: sees some observations (non-empty)", len(ad_obs_p) > 0)

    # ---- rasle_user isolation: sees ONLY AMP-RA-SLE governed rows ----
    ra_obs_p  = col("rasle_user", "SELECT DISTINCT person_id FROM cdm.observation")
    ra_spec_p = col("rasle_user", "SELECT DISTINCT person_id FROM cdm.specimen")
    check("rasle_user: observation persons ⊆ AMP-RA-SLE", ra_obs_p <= rasle, f"stray={sorted(ra_obs_p - rasle)[:5]}")
    check("rasle_user: specimen persons ⊆ AMP-RA-SLE", ra_spec_p <= rasle, f"stray={sorted(ra_spec_p - rasle)[:5]}")
    check("rasle_user: files.study all = AMP-RA-SLE", studies("rasle_user") <= {"AMP-RA-SLE"}, f"studies={studies('rasle_user')}")

    # ---- the two views are DISJOINT (RLS partitions, does not merely subset) ----
    check("ad_user vs rasle_user observation persons are disjoint", ad_obs_p.isdisjoint(ra_obs_p),
          f"overlap={sorted(ad_obs_p & ra_obs_p)[:5]}")

    # ---- RLS is genuinely filtering (not a no-op): ad_user governed count < unrestricted ----
    ad_obs_n = scalar("ad_user", "SELECT count(*) FROM cdm.observation")
    check("RLS filters: ad_user observation count < unrestricted", ad_obs_n < tot["observation"],
          f"{ad_obs_n} vs {tot['observation']}")

    # ---- no_access_user NEGATIVE control: 0 governed rows, FULL ungoverned tables ----
    gov0 = {t: scalar("no_access_user", f"SELECT count(*) FROM cdm.{t}") for t in GOVERNED}
    check("no_access_user: 0 rows in EVERY governed table", all(v == 0 for v in gov0.values()), f"{gov0}")
    ung = {t: scalar("no_access_user", f"SELECT count(*) FROM cdm.{t}") for t in UNGOVERNED}
    check("no_access_user: ungoverned tables fully visible", all(ung[t] == tot[t] for t in UNGOVERNED),
          f"{ung} vs {{t: tot[t] for t in UNGOVERNED}}")

    # ---- consortium_admin POSITIVE control: sees ALL governed rows (every row has a covering group) ----
    adm = {t: scalar("consortium_admin", f"SELECT count(*) FROM cdm.{t}") for t in ["observation", "measurement", "specimen", "files"]}
    check("consortium_admin: sees all governed rows (full coverage, no dark rows)",
          all(adm[t] == tot[t] for t in adm), f"{adm} vs {{t: tot[t] for t in adm}}")

    # ---- cross-entity coherence: specimens reachable from ad_user's visible files are themselves visible ----
    reachable = col("ad_user", "SELECT DISTINCT a2s.specimen_id FROM cdm.files f "
                               "JOIN cdm.assay_to_specimen a2s ON a2s.assay_id = f.assay_id")
    visible_spec = col("ad_user", "SELECT specimen_id FROM cdm.specimen")
    check("ad_user: specimens reachable from visible files are visible",
          reachable <= visible_spec, f"missing={sorted(reachable - visible_spec)[:5]}")

    print()
    if FAIL:
        print(f"GOVERNANCE TEST FAILED — {len(FAIL)} check(s): {FAIL}")
        sys.exit(1)
    print("GOVERNANCE TEST PASSED — RLS isolates AD/RA-SLE (disjoint), denies no_access_user, "
          "admits consortium_admin to all, and stays graph-coherent.")


if __name__ == "__main__":
    main()
