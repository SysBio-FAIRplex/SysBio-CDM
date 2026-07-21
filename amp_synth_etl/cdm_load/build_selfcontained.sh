#!/usr/bin/env bash
# Build the self-contained CDM in a FRESH throwaway database. In-repo only; no shared repo.
#   bash cdm_load/build_selfcontained.sh [db_name=sysbio_cdm_selfcontained]
set -euo pipefail
DB="${1:-sysbio_cdm_selfcontained}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# PGPASSWORD is taken from the environment (or ~/.pgpass); it is not stored in this repo.
P=(psql -h "${PGHOST:-localhost}" -p "${PGPORT:-5433}" -U "${PGUSER:-postgres}")
"${P[@]}" -d postgres -q -c "DROP DATABASE IF EXISTS $DB"
"${P[@]}" -d postgres -q -c "CREATE DATABASE $DB"
echo ">> schema";  "${P[@]}" -d "$DB" -v ON_ERROR_STOP=1 -q -f "$ROOT/cdm_load/cdm_ddl.sql"
echo ">> load";    "${P[@]}" -d "$DB" -v ON_ERROR_STOP=1 -q -f "$ROOT/cdm_load/cdm_load.sql" | tail -3
echo ">> built $DB:"
"${P[@]}" -d "$DB" -tAF'|' -c "SELECT 'person',count(*) FROM cdm.person UNION ALL SELECT 'visit_occurrence',count(*) FROM cdm.visit_occurrence UNION ALL SELECT 'observation',count(*) FROM cdm.observation UNION ALL SELECT 'measurement',count(*) FROM cdm.measurement UNION ALL SELECT 'concept',count(*) FROM cdm.concept;"
