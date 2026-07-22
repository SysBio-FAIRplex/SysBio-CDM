#!/usr/bin/env bash
# End-to-end pipeline: generate synthetic AMP data, assemble the CDM, load it into a
# throwaway Postgres database, and verify governance -- one command, start to finish.
#
#   bash run_pipeline.sh [db_name]       # default db: sysbio_cdm_selfcontained
#
# DB connection comes from PGHOST / PGPORT / PGUSER / PGPASSWORD in the environment
# (defaults localhost / 5433 / postgres). In the Docker bench these are preset.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
DB="${1:-sysbio_cdm_selfcontained}"

step() { echo; echo ">>> $*"; }

# --- generation ---
step "1/9 build specs";                python scripts/01_build_specs.py
step "2/9 build tables";               python scripts/02_build_tables.py
step "3/9 build ARK";                  python scripts/02c_build_ark.py
step "4/9 build ARK conditional";      python scripts/02f_build_ark_conditional.py
step "5/9 generate synthetic data";    python scripts/03_generate.py
step "6/9 QC (fails hard on error)";   python scripts/04_qc.py

# --- CDM delivery (10 orchestrates 06/08/09/11/12 and assembles cdm_load.sql) ---
step "7/9 assemble CDM delivery";      python scripts/10_build_cdm_delivery.py

# --- load + verify ---
step "8/9 load throwaway DB ($DB)";    bash cdm_load/build_selfcontained.sh "$DB"
step "9/9 verify governance";          python scripts/13_verify_governance.py "$DB"
step "acceptance: user stories";       python scripts/14_verify_user_stories.py "$DB"

echo
echo ">>> DONE -- CDM built, governance-verified, and user-story acceptance passed in '$DB'."
