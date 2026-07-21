-- cdm_load/governance_rls.sql — Postgres row-level security for the SysBio-CDM governed entities.
--
-- Enforces the record-level ACLs that governance_load.sql populated: a governed row is visible to a
-- role IFF that role shares an access group with the row (via <entity>_access + user_access_groups).
-- Governed entities (per resources/sysbio-dbml.dbml): observation, measurement, specimen, files,
-- procedure_occurrence. All other tables (person, visit_occurrence, observation_period, concept,
-- assay, assay_* junctions, fact_relationship, cdm_source, access_groups, user_access_groups) are
-- UNGOVERNED / always-readable.
--
-- Runs LAST in cdm_load.sql, after governance_load.sql. Idempotent within a fresh DB.
--   * Roles are CLUSTER-GLOBAL (they survive the throwaway DB drop in build_selfcontained.sh), so
--     their creation is guarded — re-running a build must not error on "role already exists".
--   * FORCE (not merely ENABLE) because the self-contained build connects as the table OWNER/superuser.
--     A superuser BYPASSES RLS entirely; the governance TEST proves enforcement by `SET ROLE <role>`
--     (which drops superuser), and FORCE additionally subjects the owner itself to the policies.
SET search_path = cdm, public;

-- ---- test roles (SYNTHETIC FIXTURES: the minimum needed to exercise RLS; NOT AMP access policy) ----
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ad_user')          THEN CREATE ROLE ad_user; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rasle_user')       THEN CREATE ROLE rasle_user; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'consortium_admin') THEN CREATE ROLE consortium_admin; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'no_access_user')   THEN CREATE ROLE no_access_user; END IF;
END $$;

-- The policy expressions read <entity>_access + user_access_groups, so the roles need plain SELECT on
-- every table; RLS then filters the 5 governed ones per policy. Ungoverned tables stay fully readable.
GRANT USAGE  ON SCHEMA cdm                TO ad_user, rasle_user, consortium_admin, no_access_user;
GRANT SELECT ON ALL TABLES IN SCHEMA cdm  TO ad_user, rasle_user, consortium_admin, no_access_user;

-- ---- enable + FORCE RLS on the 5 governed entities ----
ALTER TABLE cdm.observation           ENABLE ROW LEVEL SECURITY;
ALTER TABLE cdm.observation           FORCE  ROW LEVEL SECURITY;
ALTER TABLE cdm.measurement           ENABLE ROW LEVEL SECURITY;
ALTER TABLE cdm.measurement           FORCE  ROW LEVEL SECURITY;
ALTER TABLE cdm.specimen              ENABLE ROW LEVEL SECURITY;
ALTER TABLE cdm.specimen              FORCE  ROW LEVEL SECURITY;
ALTER TABLE cdm.files                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE cdm.files                 FORCE  ROW LEVEL SECURITY;
ALTER TABLE cdm.procedure_occurrence  ENABLE ROW LEVEL SECURITY;
ALTER TABLE cdm.procedure_occurrence  FORCE  ROW LEVEL SECURITY;

-- ---- one SELECT policy per governed table: visible iff current_user shares a group with the row ----
DROP POLICY IF EXISTS p_observation_acl ON cdm.observation;
CREATE POLICY p_observation_acl ON cdm.observation FOR SELECT USING (
  EXISTS (SELECT 1 FROM cdm.observation_access a
            JOIN cdm.user_access_groups u ON u.access_group_id = a.access_group_id
           WHERE a.observation_id = cdm.observation.observation_id
             AND u.user_id = current_user));

DROP POLICY IF EXISTS p_measurement_acl ON cdm.measurement;
CREATE POLICY p_measurement_acl ON cdm.measurement FOR SELECT USING (
  EXISTS (SELECT 1 FROM cdm.measurement_access a
            JOIN cdm.user_access_groups u ON u.access_group_id = a.access_group_id
           WHERE a.measurement_id = cdm.measurement.measurement_id
             AND u.user_id = current_user));

DROP POLICY IF EXISTS p_specimen_acl ON cdm.specimen;
CREATE POLICY p_specimen_acl ON cdm.specimen FOR SELECT USING (
  EXISTS (SELECT 1 FROM cdm.specimen_access a
            JOIN cdm.user_access_groups u ON u.access_group_id = a.access_group_id
           WHERE a.specimen_id = cdm.specimen.specimen_id
             AND u.user_id = current_user));

DROP POLICY IF EXISTS p_files_acl ON cdm.files;
CREATE POLICY p_files_acl ON cdm.files FOR SELECT USING (
  EXISTS (SELECT 1 FROM cdm.file_access a
            JOIN cdm.user_access_groups u ON u.access_group_id = a.access_group_id
           WHERE a.file_id = cdm.files.file_id
             AND u.user_id = current_user));

DROP POLICY IF EXISTS p_procedure_acl ON cdm.procedure_occurrence;
CREATE POLICY p_procedure_acl ON cdm.procedure_occurrence FOR SELECT USING (
  EXISTS (SELECT 1 FROM cdm.procedure_occurrence_access a
            JOIN cdm.user_access_groups u ON u.access_group_id = a.access_group_id
           WHERE a.procedure_occurrence_id = cdm.procedure_occurrence.procedure_occurrence_id
             AND u.user_id = current_user));
