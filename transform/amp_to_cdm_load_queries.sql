-- =============================================================================
-- AMP -> SysBio-CDM ETL : clinical CDE loading queries
-- =============================================================================
-- The executable transform from AMP source variables to CDM rows. One labeled
-- INSERT ... SELECT per AMP variable:  -- [amp_variable] -> table.concept=<id>
--
-- Inputs (create a `staging` schema and land your AMP data in it):
--   staging.amp_clinical : one row per subject-visit, one column per AMP variable
--                          (column name = amp_variable), plus person_source_value.
--   staging.person_map   : person_source_value -> assigned surrogate person_id
--                          (person is data-free; ids are assigned at ingest).
-- Output: rows in the `cdm` schema (build it first from data_model/sysbio-cdm-ddl.sql
--   into a schema named `cdm`).
--
-- Provenance: generated from the mapping spec (sysbio.shape_definition); the
--   human-readable form is transform/data_dictionary.tsv (amp_variable -> concept).
-- Scope: clinical CDEs -> observation / measurement. Structural rows (person,
--   visits, specimen lineage, assays, files) are loaded by separate steps.
-- Idempotent: each INSERT carries a NOT EXISTS guard.
-- =============================================================================

-- load_queries_from_shape_20260703_232222.sql — SysBio-CDM loads generated PURELY from sysbio.shape_definition.
-- No heuristics: every choice is a 'derived' spec field; 'parked' fields are not emitted. No provider.
-- SysBio-CDM adaptations: person is DATA-FREE, so facts join staging.person_map (source_value -> assigned
--   surrogate person_id) rather than cdm.person. *_source_value is VARCHAR(50): labels >50 use a documented
--   alias (SVAL_ALIAS); over-50 VALUES are NOT silently truncated — they fail loudly on INSERT (known case: cogdx).
SET search_path = cdm, public;
CREATE SEQUENCE IF NOT EXISTS observation_id_seq START 1;
CREATE SEQUENCE IF NOT EXISTS measurement_id_seq START 1;
CREATE SEQUENCE IF NOT EXISTS procedure_occurrence_id_seq START 1;
CREATE SEQUENCE IF NOT EXISTS specimen_id_seq START 1;
CREATE SEQUENCE IF NOT EXISTS condition_occurrence_id_seq START 1;


-- ==================== MEASUREMENT (98) ====================
-- [BMI] -> measurement.measurement_concept_id=4245997  [number in [10.0,100.0]; out-of-range int -> value_as_concept_id] [+unit 9531]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, unit_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    4245997,
    src.visit_date,
    32817,
    'BMI',
    (src."BMI")::text,
    CASE WHEN src."BMI" ~ '^-?[0-9.]+$' AND src."BMI"::numeric BETWEEN 10.0 AND 100.0 THEN src."BMI"::numeric END,
    CASE WHEN src."BMI" ~ '^-?[0-9]+$' AND NOT (src."BMI"::numeric BETWEEN 10.0 AND 100.0) THEN src."BMI"::int END,
    9531,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."BMI" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=4245997 AND t.measurement_source_value='BMI' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [CDASI] -> measurement.measurement_concept_id=3655499  [number in [0.0,100.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    3655499,
    src.visit_date,
    32817,
    'CDASI',
    (src."CDASI")::text,
    CASE WHEN src."CDASI" ~ '^-?[0-9.]+$' AND src."CDASI"::numeric BETWEEN 0.0 AND 100.0 THEN src."CDASI"::numeric END,
    CASE WHEN src."CDASI" ~ '^-?[0-9]+$' AND NOT (src."CDASI"::numeric BETWEEN 0.0 AND 100.0) THEN src."CDASI"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."CDASI" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=3655499 AND t.measurement_source_value='CDASI' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [Fibrosis.stage] -> measurement.measurement_concept_id=3048563
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    3048563,
    src.visit_date,
    32817,
    'Fibrosis.stage',
    (src."Fibrosis.stage")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."Fibrosis.stage" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=3048563 AND t.measurement_source_value='Fibrosis.stage' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [Lobular.inflammation] -> measurement.measurement_concept_id=0  [value_as_number (no explicit range)]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    0,
    src.visit_date,
    32817,
    'Lobular.inflammation',
    (src."Lobular.inflammation")::text,
    CASE WHEN src."Lobular.inflammation" ~ '^-?[0-9]+(\.[0-9]+)?$' THEN src."Lobular.inflammation"::numeric END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."Lobular.inflammation" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=0 AND t.measurement_source_value='Lobular.inflammation' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [PASI] -> measurement.measurement_concept_id=44809997  [number in [0.0,72.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    44809997,
    src.visit_date,
    32817,
    'PASI',
    (src."PASI")::text,
    CASE WHEN src."PASI" ~ '^-?[0-9.]+$' AND src."PASI"::numeric BETWEEN 0.0 AND 72.0 THEN src."PASI"::numeric END,
    CASE WHEN src."PASI" ~ '^-?[0-9]+$' AND NOT (src."PASI"::numeric BETWEEN 0.0 AND 72.0) THEN src."PASI"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."PASI" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=44809997 AND t.measurement_source_value='PASI' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [Portal.inflammation] -> measurement.measurement_concept_id=0  [value_as_number (no explicit range)]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    0,
    src.visit_date,
    32817,
    'Portal.inflammation',
    (src."Portal.inflammation")::text,
    CASE WHEN src."Portal.inflammation" ~ '^-?[0-9]+(\.[0-9]+)?$' THEN src."Portal.inflammation"::numeric END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."Portal.inflammation" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=0 AND t.measurement_source_value='Portal.inflammation' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [Steatosis.grade] -> measurement.measurement_concept_id=0  [number in [0.0,3.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    0,
    src.visit_date,
    32817,
    'Steatosis.grade',
    (src."Steatosis.grade")::text,
    CASE WHEN src."Steatosis.grade" ~ '^-?[0-9.]+$' AND src."Steatosis.grade"::numeric BETWEEN 0.0 AND 3.0 THEN src."Steatosis.grade"::numeric END,
    CASE WHEN src."Steatosis.grade" ~ '^-?[0-9]+$' AND NOT (src."Steatosis.grade"::numeric BETWEEN 0.0 AND 3.0) THEN src."Steatosis.grade"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."Steatosis.grade" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=0 AND t.measurement_source_value='Steatosis.grade' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [VETI] -> measurement.measurement_concept_id=0  [number in [0.0,100.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    0,
    src.visit_date,
    32817,
    'VETI',
    (src."VETI")::text,
    CASE WHEN src."VETI" ~ '^-?[0-9.]+$' AND src."VETI"::numeric BETWEEN 0.0 AND 100.0 THEN src."VETI"::numeric END,
    CASE WHEN src."VETI" ~ '^-?[0-9]+$' AND NOT (src."VETI"::numeric BETWEEN 0.0 AND 100.0) THEN src."VETI"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."VETI" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=0 AND t.measurement_source_value='VETI' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [VIDA] -> measurement.measurement_concept_id=0  [number in [0.0,6.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    0,
    src.visit_date,
    32817,
    'VIDA',
    (src."VIDA")::text,
    CASE WHEN src."VIDA" ~ '^-?[0-9.]+$' AND src."VIDA"::numeric BETWEEN 0.0 AND 6.0 THEN src."VIDA"::numeric END,
    CASE WHEN src."VIDA" ~ '^-?[0-9]+$' AND NOT (src."VIDA"::numeric BETWEEN 0.0 AND 6.0) THEN src."VIDA"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."VIDA" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=0 AND t.measurement_source_value='VIDA' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [amyCerad] -> measurement.measurement_concept_id=3519134
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    3519134,
    src.visit_date,
    32817,
    'amyCerad',
    (src."amyCerad")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."amyCerad" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=3519134 AND t.measurement_source_value='amyCerad' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [amyThal] -> measurement.measurement_concept_id=3170911  [number in [0.0,5.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    3170911,
    src.visit_date,
    32817,
    'amyThal',
    (src."amyThal")::text,
    CASE WHEN src."amyThal" ~ '^-?[0-9.]+$' AND src."amyThal"::numeric BETWEEN 0.0 AND 5.0 THEN src."amyThal"::numeric END,
    CASE WHEN src."amyThal" ~ '^-?[0-9]+$' AND NOT (src."amyThal"::numeric BETWEEN 0.0 AND 5.0) THEN src."amyThal"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."amyThal" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=3170911 AND t.measurement_source_value='amyThal' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [apoe_genotype] -> measurement.measurement_concept_id=37397776
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    37397776,
    src.visit_date,
    32817,
    'apoe_genotype',
    (src."apoe_genotype")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."apoe_genotype" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=37397776 AND t.measurement_source_value='apoe_genotype' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [bmi.range] -> measurement.measurement_concept_id=40490382
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    40490382,
    src.visit_date,
    32817,
    'bmi.range',
    (src."bmi.range")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."bmi.range" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=40490382 AND t.measurement_source_value='bmi.range' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [braaksc] -> measurement.measurement_concept_id=3187187
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    3187187,
    src.visit_date,
    32817,
    'braaksc',
    (src."braaksc")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."braaksc" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=3187187 AND t.measurement_source_value='braaksc' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [ceradsc] -> measurement.measurement_concept_id=3168054
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    3168054,
    src.visit_date,
    32817,
    'ceradsc',
    (src."ceradsc")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."ceradsc" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=3168054 AND t.measurement_source_value='ceradsc' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [cts_mmse30_first_ad_dx] -> measurement.measurement_concept_id=4169175  [number in [0.0,30.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    4169175,
    src.visit_date,
    32817,
    'cts_mmse30_first_ad_dx',
    (src."cts_mmse30_first_ad_dx")::text,
    CASE WHEN src."cts_mmse30_first_ad_dx" ~ '^-?[0-9.]+$' AND src."cts_mmse30_first_ad_dx"::numeric BETWEEN 0.0 AND 30.0 THEN src."cts_mmse30_first_ad_dx"::numeric END,
    CASE WHEN src."cts_mmse30_first_ad_dx" ~ '^-?[0-9]+$' AND NOT (src."cts_mmse30_first_ad_dx"::numeric BETWEEN 0.0 AND 30.0) THEN src."cts_mmse30_first_ad_dx"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."cts_mmse30_first_ad_dx" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=4169175 AND t.measurement_source_value='cts_mmse30_first_ad_dx' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [dat] -> measurement.measurement_concept_id=4327116
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    4327116,
    src.visit_date,
    32817,
    'dat',
    (src."dat")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."dat" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=4327116 AND t.measurement_source_value='dat' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [datscan_visual_interpretation] -> measurement.measurement_concept_id=4327116
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    4327116,
    src.visit_date,
    32817,
    'datscan_visual_interpretation',
    (src."datscan_visual_interpretation")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."datscan_visual_interpretation" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=4327116 AND t.measurement_source_value='datscan_visual_interpretation' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [dcfdx_lv] -> measurement.measurement_concept_id=3185659
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    3185659,
    src.visit_date,
    32817,
    'dcfdx_lv',
    (src."dcfdx_lv")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."dcfdx_lv" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=3185659 AND t.measurement_source_value='dcfdx_lv' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [donor_id] -> measurement.measurement_concept_id=1616447
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    1616447,
    src.visit_date,
    32817,
    'donor_id',
    (src."donor_id")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."donor_id" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=1616447 AND t.measurement_source_value='donor_id' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [eGFR] -> measurement.measurement_concept_id=44806420  [number in [0.0,200.0]; out-of-range int -> value_as_concept_id] [+unit 720870]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, unit_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    44806420,
    src.visit_date,
    32817,
    'eGFR',
    (src."eGFR")::text,
    CASE WHEN src."eGFR" ~ '^-?[0-9.]+$' AND src."eGFR"::numeric BETWEEN 0.0 AND 200.0 THEN src."eGFR"::numeric END,
    CASE WHEN src."eGFR" ~ '^-?[0-9]+$' AND NOT (src."eGFR"::numeric BETWEEN 0.0 AND 200.0) THEN src."eGFR"::int END,
    720870,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."eGFR" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=44806420 AND t.measurement_source_value='eGFR' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [ess_info_source] -> measurement.measurement_concept_id=3048270
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    3048270,
    src.visit_date,
    32817,
    'ess_info_source',
    (src."ess_info_source")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."ess_info_source" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=3048270 AND t.measurement_source_value='ess_info_source' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [height] -> measurement.measurement_concept_id=4093975
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    4093975,
    src.visit_date,
    32817,
    'height',
    (src."height")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."height" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=4093975 AND t.measurement_source_value='height' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [moca12_attention_serial_7s] -> measurement.measurement_concept_id=4158754  [number in [0.0,3.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    4158754,
    src.visit_date,
    32817,
    'moca12_attention_serial_7s',
    (src."moca12_attention_serial_7s")::text,
    CASE WHEN src."moca12_attention_serial_7s" ~ '^-?[0-9.]+$' AND src."moca12_attention_serial_7s"::numeric BETWEEN 0.0 AND 3.0 THEN src."moca12_attention_serial_7s"::numeric END,
    CASE WHEN src."moca12_attention_serial_7s" ~ '^-?[0-9]+$' AND NOT (src."moca12_attention_serial_7s"::numeric BETWEEN 0.0 AND 3.0) THEN src."moca12_attention_serial_7s"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."moca12_attention_serial_7s" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=4158754 AND t.measurement_source_value='moca12_attention_serial_7s' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [mod_schwab_england_pct_adl_score] -> measurement.measurement_concept_id=46236405  [number in [0.0,100.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    46236405,
    src.visit_date,
    32817,
    'mod_schwab_england_pct_adl_score',
    (src."mod_schwab_england_pct_adl_score")::text,
    CASE WHEN src."mod_schwab_england_pct_adl_score" ~ '^-?[0-9.]+$' AND src."mod_schwab_england_pct_adl_score"::numeric BETWEEN 0.0 AND 100.0 THEN src."mod_schwab_england_pct_adl_score"::numeric END,
    CASE WHEN src."mod_schwab_england_pct_adl_score" ~ '^-?[0-9]+$' AND NOT (src."mod_schwab_england_pct_adl_score"::numeric BETWEEN 0.0 AND 100.0) THEN src."mod_schwab_england_pct_adl_score"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."mod_schwab_england_pct_adl_score" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=46236405 AND t.measurement_source_value='mod_schwab_england_pct_adl_score' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [path_braak_lb] -> measurement.measurement_concept_id=3190069
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    3190069,
    src.visit_date,
    32817,
    'path_braak_lb',
    (src."path_braak_lb")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."path_braak_lb" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=3190069 AND t.measurement_source_value='path_braak_lb' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [pmi] -> measurement.measurement_concept_id=3029815  [number in [0.0,72.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    3029815,
    src.visit_date,
    32817,
    'pmi',
    (src."pmi")::text,
    CASE WHEN src."pmi" ~ '^-?[0-9.]+$' AND src."pmi"::numeric BETWEEN 0.0 AND 72.0 THEN src."pmi"::numeric END,
    CASE WHEN src."pmi" ~ '^-?[0-9]+$' AND NOT (src."pmi"::numeric BETWEEN 0.0 AND 72.0) THEN src."pmi"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."pmi" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=3029815 AND t.measurement_source_value='pmi' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [rbd10f_depression] -> measurement.measurement_concept_id=4064377
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    4064377,
    src.visit_date,
    32817,
    'rbd10f_depression',
    (src."rbd10f_depression")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."rbd10f_depression" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=4064377 AND t.measurement_source_value='rbd10f_depression' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [rbd_info_source] -> measurement.measurement_concept_id=3048270
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    3048270,
    src.visit_date,
    32817,
    'rbd_info_source',
    (src."rbd_info_source")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."rbd_info_source" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=3048270 AND t.measurement_source_value='rbd_info_source' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [sampleStatus] -> measurement.measurement_concept_id=37021329
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    37021329,
    src.visit_date,
    32817,
    'sampleStatus',
    (src."sampleStatus")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."sampleStatus" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=37021329 AND t.measurement_source_value='sampleStatus' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [scan_months_after_baseline] -> measurement.measurement_concept_id=4327116  [value_as_number (no explicit range)]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    4327116,
    src.visit_date,
    32817,
    'scan_months_after_baseline',
    (src."scan_months_after_baseline")::text,
    CASE WHEN src."scan_months_after_baseline" ~ '^-?[0-9]+(\.[0-9]+)?$' THEN src."scan_months_after_baseline"::numeric END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."scan_months_after_baseline" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=4327116 AND t.measurement_source_value='scan_months_after_baseline' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [score_from_booklet_1] -> measurement.measurement_concept_id=3654978  [number in [0.0,10.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    3654978,
    src.visit_date,
    32817,
    'score_from_booklet_1',
    (src."score_from_booklet_1")::text,
    CASE WHEN src."score_from_booklet_1" ~ '^-?[0-9.]+$' AND src."score_from_booklet_1"::numeric BETWEEN 0.0 AND 10.0 THEN src."score_from_booklet_1"::numeric END,
    CASE WHEN src."score_from_booklet_1" ~ '^-?[0-9]+$' AND NOT (src."score_from_booklet_1"::numeric BETWEEN 0.0 AND 10.0) THEN src."score_from_booklet_1"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."score_from_booklet_1" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=3654978 AND t.measurement_source_value='score_from_booklet_1' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [score_from_booklet_2] -> measurement.measurement_concept_id=3654978  [number in [0.0,10.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    3654978,
    src.visit_date,
    32817,
    'score_from_booklet_2',
    (src."score_from_booklet_2")::text,
    CASE WHEN src."score_from_booklet_2" ~ '^-?[0-9.]+$' AND src."score_from_booklet_2"::numeric BETWEEN 0.0 AND 10.0 THEN src."score_from_booklet_2"::numeric END,
    CASE WHEN src."score_from_booklet_2" ~ '^-?[0-9]+$' AND NOT (src."score_from_booklet_2"::numeric BETWEEN 0.0 AND 10.0) THEN src."score_from_booklet_2"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."score_from_booklet_2" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=3654978 AND t.measurement_source_value='score_from_booklet_2' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [score_from_booklet_3] -> measurement.measurement_concept_id=3654978  [number in [0.0,10.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    3654978,
    src.visit_date,
    32817,
    'score_from_booklet_3',
    (src."score_from_booklet_3")::text,
    CASE WHEN src."score_from_booklet_3" ~ '^-?[0-9.]+$' AND src."score_from_booklet_3"::numeric BETWEEN 0.0 AND 10.0 THEN src."score_from_booklet_3"::numeric END,
    CASE WHEN src."score_from_booklet_3" ~ '^-?[0-9]+$' AND NOT (src."score_from_booklet_3"::numeric BETWEEN 0.0 AND 10.0) THEN src."score_from_booklet_3"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."score_from_booklet_3" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=3654978 AND t.measurement_source_value='score_from_booklet_3' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [score_from_booklet_4] -> measurement.measurement_concept_id=3654978  [number in [0.0,10.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    3654978,
    src.visit_date,
    32817,
    'score_from_booklet_4',
    (src."score_from_booklet_4")::text,
    CASE WHEN src."score_from_booklet_4" ~ '^-?[0-9.]+$' AND src."score_from_booklet_4"::numeric BETWEEN 0.0 AND 10.0 THEN src."score_from_booklet_4"::numeric END,
    CASE WHEN src."score_from_booklet_4" ~ '^-?[0-9]+$' AND NOT (src."score_from_booklet_4"::numeric BETWEEN 0.0 AND 10.0) THEN src."score_from_booklet_4"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."score_from_booklet_4" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=3654978 AND t.measurement_source_value='score_from_booklet_4' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [smell_detail] -> measurement.measurement_concept_id=3654978
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    3654978,
    src.visit_date,
    32817,
    'smell_detail',
    (src."smell_detail")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."smell_detail" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=3654978 AND t.measurement_source_value='smell_detail' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [test_name] -> measurement.measurement_concept_id=0
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    0,
    src.visit_date,
    32817,
    'test_name',
    (src."test_name")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."test_name" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=0 AND t.measurement_source_value='test_name' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [test_value] -> measurement.measurement_concept_id=0  [number in [-10.0,713.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    0,
    src.visit_date,
    32817,
    'test_value',
    (src."test_value")::text,
    CASE WHEN src."test_value" ~ '^-?[0-9.]+$' AND src."test_value"::numeric BETWEEN -10.0 AND 713.0 THEN src."test_value"::numeric END,
    CASE WHEN src."test_value" ~ '^-?[0-9]+$' AND NOT (src."test_value"::numeric BETWEEN -10.0 AND 713.0) THEN src."test_value"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."test_value" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=0 AND t.measurement_source_value='test_value' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [tissueVolume] -> measurement.measurement_concept_id=4013576  [value_as_number (no explicit range)] [+unit 8582]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, unit_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    4013576,
    src.visit_date,
    32817,
    'tissueVolume',
    (src."tissueVolume")::text,
    CASE WHEN src."tissueVolume" ~ '^-?[0-9]+(\.[0-9]+)?$' THEN src."tissueVolume"::numeric END,
    8582,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."tissueVolume" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=4013576 AND t.measurement_source_value='tissueVolume' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [tissueWeight] -> measurement.measurement_concept_id=3020366  [value_as_number (no explicit range)]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    3020366,
    src.visit_date,
    32817,
    'tissueWeight',
    (src."tissueWeight")::text,
    CASE WHEN src."tissueWeight" ~ '^-?[0-9]+(\.[0-9]+)?$' THEN src."tissueWeight"::numeric END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."tissueWeight" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=3020366 AND t.measurement_source_value='tissueWeight' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [tobacco_start_age] -> measurement.measurement_concept_id=40765292  [number in [6.0,75.0]; out-of-range int -> value_as_concept_id] [+unit 9448]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, unit_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    40765292,
    src.visit_date,
    32817,
    'tobacco_start_age',
    (src."tobacco_start_age")::text,
    CASE WHEN src."tobacco_start_age" ~ '^-?[0-9.]+$' AND src."tobacco_start_age"::numeric BETWEEN 6.0 AND 75.0 THEN src."tobacco_start_age"::numeric END,
    CASE WHEN src."tobacco_start_age" ~ '^-?[0-9]+$' AND NOT (src."tobacco_start_age"::numeric BETWEEN 6.0 AND 75.0) THEN src."tobacco_start_age"::int END,
    9448,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."tobacco_start_age" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=40765292 AND t.measurement_source_value='tobacco_start_age' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd101_intellect_impairment] -> measurement.measurement_concept_id=46236376  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    46236376,
    src.visit_date,
    32817,
    'upd101_intellect_impairment',
    (src."upd101_intellect_impairment")::text,
    CASE WHEN src."upd101_intellect_impairment" ~ '^-?[0-9.]+$' AND src."upd101_intellect_impairment"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd101_intellect_impairment"::numeric END,
    CASE WHEN src."upd101_intellect_impairment" ~ '^-?[0-9]+$' AND NOT (src."upd101_intellect_impairment"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd101_intellect_impairment"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd101_intellect_impairment" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=46236376 AND t.measurement_source_value='upd101_intellect_impairment' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd102_thought_disorder] -> measurement.measurement_concept_id=46236377  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    46236377,
    src.visit_date,
    32817,
    'upd102_thought_disorder',
    (src."upd102_thought_disorder")::text,
    CASE WHEN src."upd102_thought_disorder" ~ '^-?[0-9.]+$' AND src."upd102_thought_disorder"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd102_thought_disorder"::numeric END,
    CASE WHEN src."upd102_thought_disorder" ~ '^-?[0-9]+$' AND NOT (src."upd102_thought_disorder"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd102_thought_disorder"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd102_thought_disorder" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=46236377 AND t.measurement_source_value='upd102_thought_disorder' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd103_depression] -> measurement.measurement_concept_id=46236378  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    46236378,
    src.visit_date,
    32817,
    'upd103_depression',
    (src."upd103_depression")::text,
    CASE WHEN src."upd103_depression" ~ '^-?[0-9.]+$' AND src."upd103_depression"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd103_depression"::numeric END,
    CASE WHEN src."upd103_depression" ~ '^-?[0-9]+$' AND NOT (src."upd103_depression"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd103_depression"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd103_depression" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=46236378 AND t.measurement_source_value='upd103_depression' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd104_motivation] -> measurement.measurement_concept_id=46236379  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    46236379,
    src.visit_date,
    32817,
    'upd104_motivation',
    (src."upd104_motivation")::text,
    CASE WHEN src."upd104_motivation" ~ '^-?[0-9.]+$' AND src."upd104_motivation"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd104_motivation"::numeric END,
    CASE WHEN src."upd104_motivation" ~ '^-?[0-9]+$' AND NOT (src."upd104_motivation"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd104_motivation"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd104_motivation" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=46236379 AND t.measurement_source_value='upd104_motivation' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd105_speech] -> measurement.measurement_concept_id=46236380  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    46236380,
    src.visit_date,
    32817,
    'upd105_speech',
    (src."upd105_speech")::text,
    CASE WHEN src."upd105_speech" ~ '^-?[0-9.]+$' AND src."upd105_speech"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd105_speech"::numeric END,
    CASE WHEN src."upd105_speech" ~ '^-?[0-9]+$' AND NOT (src."upd105_speech"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd105_speech"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd105_speech" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=46236380 AND t.measurement_source_value='upd105_speech' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd106_salivation] -> measurement.measurement_concept_id=46236381  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    46236381,
    src.visit_date,
    32817,
    'upd106_salivation',
    (src."upd106_salivation")::text,
    CASE WHEN src."upd106_salivation" ~ '^-?[0-9.]+$' AND src."upd106_salivation"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd106_salivation"::numeric END,
    CASE WHEN src."upd106_salivation" ~ '^-?[0-9]+$' AND NOT (src."upd106_salivation"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd106_salivation"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd106_salivation" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=46236381 AND t.measurement_source_value='upd106_salivation' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd107_swallowing] -> measurement.measurement_concept_id=46236382  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    46236382,
    src.visit_date,
    32817,
    'upd107_swallowing',
    (src."upd107_swallowing")::text,
    CASE WHEN src."upd107_swallowing" ~ '^-?[0-9.]+$' AND src."upd107_swallowing"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd107_swallowing"::numeric END,
    CASE WHEN src."upd107_swallowing" ~ '^-?[0-9]+$' AND NOT (src."upd107_swallowing"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd107_swallowing"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd107_swallowing" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=46236382 AND t.measurement_source_value='upd107_swallowing' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd108_handwriting] -> measurement.measurement_concept_id=46236383  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    46236383,
    src.visit_date,
    32817,
    'upd108_handwriting',
    (src."upd108_handwriting")::text,
    CASE WHEN src."upd108_handwriting" ~ '^-?[0-9.]+$' AND src."upd108_handwriting"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd108_handwriting"::numeric END,
    CASE WHEN src."upd108_handwriting" ~ '^-?[0-9]+$' AND NOT (src."upd108_handwriting"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd108_handwriting"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd108_handwriting" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=46236383 AND t.measurement_source_value='upd108_handwriting' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd109_cutting_food] -> measurement.measurement_concept_id=46236384  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    46236384,
    src.visit_date,
    32817,
    'upd109_cutting_food',
    (src."upd109_cutting_food")::text,
    CASE WHEN src."upd109_cutting_food" ~ '^-?[0-9.]+$' AND src."upd109_cutting_food"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd109_cutting_food"::numeric END,
    CASE WHEN src."upd109_cutting_food" ~ '^-?[0-9]+$' AND NOT (src."upd109_cutting_food"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd109_cutting_food"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd109_cutting_food" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=46236384 AND t.measurement_source_value='upd109_cutting_food' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd110_dressing] -> measurement.measurement_concept_id=46236385  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    46236385,
    src.visit_date,
    32817,
    'upd110_dressing',
    (src."upd110_dressing")::text,
    CASE WHEN src."upd110_dressing" ~ '^-?[0-9.]+$' AND src."upd110_dressing"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd110_dressing"::numeric END,
    CASE WHEN src."upd110_dressing" ~ '^-?[0-9]+$' AND NOT (src."upd110_dressing"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd110_dressing"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd110_dressing" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=46236385 AND t.measurement_source_value='upd110_dressing' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd111_hygiene] -> measurement.measurement_concept_id=46236386  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    46236386,
    src.visit_date,
    32817,
    'upd111_hygiene',
    (src."upd111_hygiene")::text,
    CASE WHEN src."upd111_hygiene" ~ '^-?[0-9.]+$' AND src."upd111_hygiene"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd111_hygiene"::numeric END,
    CASE WHEN src."upd111_hygiene" ~ '^-?[0-9]+$' AND NOT (src."upd111_hygiene"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd111_hygiene"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd111_hygiene" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=46236386 AND t.measurement_source_value='upd111_hygiene' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd112_turning_in_bed] -> measurement.measurement_concept_id=46236387  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    46236387,
    src.visit_date,
    32817,
    'upd112_turning_in_bed',
    (src."upd112_turning_in_bed")::text,
    CASE WHEN src."upd112_turning_in_bed" ~ '^-?[0-9.]+$' AND src."upd112_turning_in_bed"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd112_turning_in_bed"::numeric END,
    CASE WHEN src."upd112_turning_in_bed" ~ '^-?[0-9]+$' AND NOT (src."upd112_turning_in_bed"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd112_turning_in_bed"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd112_turning_in_bed" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=46236387 AND t.measurement_source_value='upd112_turning_in_bed' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd113_falling] -> measurement.measurement_concept_id=46236388  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    46236388,
    src.visit_date,
    32817,
    'upd113_falling',
    (src."upd113_falling")::text,
    CASE WHEN src."upd113_falling" ~ '^-?[0-9.]+$' AND src."upd113_falling"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd113_falling"::numeric END,
    CASE WHEN src."upd113_falling" ~ '^-?[0-9]+$' AND NOT (src."upd113_falling"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd113_falling"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd113_falling" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=46236388 AND t.measurement_source_value='upd113_falling' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd114_freezing_walking] -> measurement.measurement_concept_id=46236389  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    46236389,
    src.visit_date,
    32817,
    'upd114_freezing_walking',
    (src."upd114_freezing_walking")::text,
    CASE WHEN src."upd114_freezing_walking" ~ '^-?[0-9.]+$' AND src."upd114_freezing_walking"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd114_freezing_walking"::numeric END,
    CASE WHEN src."upd114_freezing_walking" ~ '^-?[0-9]+$' AND NOT (src."upd114_freezing_walking"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd114_freezing_walking"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd114_freezing_walking" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=46236389 AND t.measurement_source_value='upd114_freezing_walking' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd115_walking] -> measurement.measurement_concept_id=46236390  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    46236390,
    src.visit_date,
    32817,
    'upd115_walking',
    (src."upd115_walking")::text,
    CASE WHEN src."upd115_walking" ~ '^-?[0-9.]+$' AND src."upd115_walking"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd115_walking"::numeric END,
    CASE WHEN src."upd115_walking" ~ '^-?[0-9]+$' AND NOT (src."upd115_walking"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd115_walking"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd115_walking" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=46236390 AND t.measurement_source_value='upd115_walking' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd116_tremor] -> measurement.measurement_concept_id=46236391  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    46236391,
    src.visit_date,
    32817,
    'upd116_tremor',
    (src."upd116_tremor")::text,
    CASE WHEN src."upd116_tremor" ~ '^-?[0-9.]+$' AND src."upd116_tremor"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd116_tremor"::numeric END,
    CASE WHEN src."upd116_tremor" ~ '^-?[0-9]+$' AND NOT (src."upd116_tremor"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd116_tremor"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd116_tremor" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=46236391 AND t.measurement_source_value='upd116_tremor' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd117_sensory_complaints] -> measurement.measurement_concept_id=46236392  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    46236392,
    src.visit_date,
    32817,
    'upd117_sensory_complaints',
    (src."upd117_sensory_complaints")::text,
    CASE WHEN src."upd117_sensory_complaints" ~ '^-?[0-9.]+$' AND src."upd117_sensory_complaints"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd117_sensory_complaints"::numeric END,
    CASE WHEN src."upd117_sensory_complaints" ~ '^-?[0-9]+$' AND NOT (src."upd117_sensory_complaints"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd117_sensory_complaints"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd117_sensory_complaints" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=46236392 AND t.measurement_source_value='upd117_sensory_complaints' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd120b_tremor_rest_hand_rt] -> measurement.measurement_concept_id=40768719  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    40768719,
    src.visit_date,
    32817,
    'upd120b_tremor_rest_hand_rt',
    (src."upd120b_tremor_rest_hand_rt")::text,
    CASE WHEN src."upd120b_tremor_rest_hand_rt" ~ '^-?[0-9.]+$' AND src."upd120b_tremor_rest_hand_rt"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd120b_tremor_rest_hand_rt"::numeric END,
    CASE WHEN src."upd120b_tremor_rest_hand_rt" ~ '^-?[0-9]+$' AND NOT (src."upd120b_tremor_rest_hand_rt"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd120b_tremor_rest_hand_rt"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd120b_tremor_rest_hand_rt" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=40768719 AND t.measurement_source_value='upd120b_tremor_rest_hand_rt' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd120c_tremor_rest_hand_lt] -> measurement.measurement_concept_id=40768870  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    40768870,
    src.visit_date,
    32817,
    'upd120c_tremor_rest_hand_lt',
    (src."upd120c_tremor_rest_hand_lt")::text,
    CASE WHEN src."upd120c_tremor_rest_hand_lt" ~ '^-?[0-9.]+$' AND src."upd120c_tremor_rest_hand_lt"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd120c_tremor_rest_hand_lt"::numeric END,
    CASE WHEN src."upd120c_tremor_rest_hand_lt" ~ '^-?[0-9]+$' AND NOT (src."upd120c_tremor_rest_hand_lt"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd120c_tremor_rest_hand_lt"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd120c_tremor_rest_hand_lt" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=40768870 AND t.measurement_source_value='upd120c_tremor_rest_hand_lt' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd120d_tremor_rest_feet_rt] -> measurement.measurement_concept_id=40768871  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    40768871,
    src.visit_date,
    32817,
    'upd120d_tremor_rest_feet_rt',
    (src."upd120d_tremor_rest_feet_rt")::text,
    CASE WHEN src."upd120d_tremor_rest_feet_rt" ~ '^-?[0-9.]+$' AND src."upd120d_tremor_rest_feet_rt"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd120d_tremor_rest_feet_rt"::numeric END,
    CASE WHEN src."upd120d_tremor_rest_feet_rt" ~ '^-?[0-9]+$' AND NOT (src."upd120d_tremor_rest_feet_rt"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd120d_tremor_rest_feet_rt"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd120d_tremor_rest_feet_rt" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=40768871 AND t.measurement_source_value='upd120d_tremor_rest_feet_rt' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd120e_tremor_rest_feet_lt] -> measurement.measurement_concept_id=40768872  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    40768872,
    src.visit_date,
    32817,
    'upd120e_tremor_rest_feet_lt',
    (src."upd120e_tremor_rest_feet_lt")::text,
    CASE WHEN src."upd120e_tremor_rest_feet_lt" ~ '^-?[0-9.]+$' AND src."upd120e_tremor_rest_feet_lt"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd120e_tremor_rest_feet_lt"::numeric END,
    CASE WHEN src."upd120e_tremor_rest_feet_lt" ~ '^-?[0-9]+$' AND NOT (src."upd120e_tremor_rest_feet_lt"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd120e_tremor_rest_feet_lt"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd120e_tremor_rest_feet_lt" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=40768872 AND t.measurement_source_value='upd120e_tremor_rest_feet_lt' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd122a_rigidity_neck] -> measurement.measurement_concept_id=40768721  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    40768721,
    src.visit_date,
    32817,
    'upd122a_rigidity_neck',
    (src."upd122a_rigidity_neck")::text,
    CASE WHEN src."upd122a_rigidity_neck" ~ '^-?[0-9.]+$' AND src."upd122a_rigidity_neck"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd122a_rigidity_neck"::numeric END,
    CASE WHEN src."upd122a_rigidity_neck" ~ '^-?[0-9]+$' AND NOT (src."upd122a_rigidity_neck"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd122a_rigidity_neck"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd122a_rigidity_neck" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=40768721 AND t.measurement_source_value='upd122a_rigidity_neck' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd122b_rigidity_up_extrem_rt] -> measurement.measurement_concept_id=40768873  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    40768873,
    src.visit_date,
    32817,
    'upd122b_rigidity_up_extrem_rt',
    (src."upd122b_rigidity_up_extrem_rt")::text,
    CASE WHEN src."upd122b_rigidity_up_extrem_rt" ~ '^-?[0-9.]+$' AND src."upd122b_rigidity_up_extrem_rt"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd122b_rigidity_up_extrem_rt"::numeric END,
    CASE WHEN src."upd122b_rigidity_up_extrem_rt" ~ '^-?[0-9]+$' AND NOT (src."upd122b_rigidity_up_extrem_rt"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd122b_rigidity_up_extrem_rt"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd122b_rigidity_up_extrem_rt" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=40768873 AND t.measurement_source_value='upd122b_rigidity_up_extrem_rt' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd122c_rigidity_up_extrem_lt] -> measurement.measurement_concept_id=40768874  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    40768874,
    src.visit_date,
    32817,
    'upd122c_rigidity_up_extrem_lt',
    (src."upd122c_rigidity_up_extrem_lt")::text,
    CASE WHEN src."upd122c_rigidity_up_extrem_lt" ~ '^-?[0-9.]+$' AND src."upd122c_rigidity_up_extrem_lt"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd122c_rigidity_up_extrem_lt"::numeric END,
    CASE WHEN src."upd122c_rigidity_up_extrem_lt" ~ '^-?[0-9]+$' AND NOT (src."upd122c_rigidity_up_extrem_lt"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd122c_rigidity_up_extrem_lt"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd122c_rigidity_up_extrem_lt" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=40768874 AND t.measurement_source_value='upd122c_rigidity_up_extrem_lt' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd122d_rigidity_low_extrem_rt] -> measurement.measurement_concept_id=40768875  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    40768875,
    src.visit_date,
    32817,
    'upd122d_rigidity_low_extrem_rt',
    (src."upd122d_rigidity_low_extrem_rt")::text,
    CASE WHEN src."upd122d_rigidity_low_extrem_rt" ~ '^-?[0-9.]+$' AND src."upd122d_rigidity_low_extrem_rt"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd122d_rigidity_low_extrem_rt"::numeric END,
    CASE WHEN src."upd122d_rigidity_low_extrem_rt" ~ '^-?[0-9]+$' AND NOT (src."upd122d_rigidity_low_extrem_rt"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd122d_rigidity_low_extrem_rt"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd122d_rigidity_low_extrem_rt" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=40768875 AND t.measurement_source_value='upd122d_rigidity_low_extrem_rt' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd122e_rigidity_low_extrem_lt] -> measurement.measurement_concept_id=40768876  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    40768876,
    src.visit_date,
    32817,
    'upd122e_rigidity_low_extrem_lt',
    (src."upd122e_rigidity_low_extrem_lt")::text,
    CASE WHEN src."upd122e_rigidity_low_extrem_lt" ~ '^-?[0-9.]+$' AND src."upd122e_rigidity_low_extrem_lt"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd122e_rigidity_low_extrem_lt"::numeric END,
    CASE WHEN src."upd122e_rigidity_low_extrem_lt" ~ '^-?[0-9]+$' AND NOT (src."upd122e_rigidity_low_extrem_lt"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd122e_rigidity_low_extrem_lt"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd122e_rigidity_low_extrem_lt" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=40768876 AND t.measurement_source_value='upd122e_rigidity_low_extrem_lt' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2101_cognitive_impairment] -> measurement.measurement_concept_id=46236376
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    46236376,
    src.visit_date,
    32817,
    'upd2101_cognitive_impairment',
    (src."upd2101_cognitive_impairment")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2101_cognitive_impairment" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=46236376 AND t.measurement_source_value='upd2101_cognitive_impairment' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2102_hallucinations_and_psychosis] -> measurement.measurement_concept_id=46236377
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    46236377,
    src.visit_date,
    32817,
    'upd2102_hallucinations_and_psychosis',
    (src."upd2102_hallucinations_and_psychosis")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2102_hallucinations_and_psychosis" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=46236377 AND t.measurement_source_value='upd2102_hallucinations_and_psychosis' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2103_depressed_mood] -> measurement.measurement_concept_id=46236378
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    46236378,
    src.visit_date,
    32817,
    'upd2103_depressed_mood',
    (src."upd2103_depressed_mood")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2103_depressed_mood" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=46236378 AND t.measurement_source_value='upd2103_depressed_mood' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2105_apathy] -> measurement.measurement_concept_id=46236379
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    46236379,
    src.visit_date,
    32817,
    'upd2105_apathy',
    (src."upd2105_apathy")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2105_apathy" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=46236379 AND t.measurement_source_value='upd2105_apathy' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2109_pat_quest_pain_and_other_sensations] -> measurement.measurement_concept_id=46236392
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    46236392,
    src.visit_date,
    32817,
    'upd2109_pat_quest_pain_and_other_sensations',
    (src."upd2109_pat_quest_pain_and_other_sensations")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2109_pat_quest_pain_and_other_sensations" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=46236392 AND t.measurement_source_value='upd2109_pat_quest_pain_and_other_sensations' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2202_saliva_and_drooling] -> measurement.measurement_concept_id=46236381
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    46236381,
    src.visit_date,
    32817,
    'upd2202_saliva_and_drooling',
    (src."upd2202_saliva_and_drooling")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2202_saliva_and_drooling" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=46236381 AND t.measurement_source_value='upd2202_saliva_and_drooling' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2203_chewing_and_swallowing] -> measurement.measurement_concept_id=46236382
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    46236382,
    src.visit_date,
    32817,
    'upd2203_chewing_and_swallowing',
    (src."upd2203_chewing_and_swallowing")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2203_chewing_and_swallowing" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=46236382 AND t.measurement_source_value='upd2203_chewing_and_swallowing' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2205_dressing] -> measurement.measurement_concept_id=46236385
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    46236385,
    src.visit_date,
    32817,
    'upd2205_dressing',
    (src."upd2205_dressing")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2205_dressing" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=46236385 AND t.measurement_source_value='upd2205_dressing' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2206_hygiene] -> measurement.measurement_concept_id=46236386
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    46236386,
    src.visit_date,
    32817,
    'upd2206_hygiene',
    (src."upd2206_hygiene")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2206_hygiene" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=46236386 AND t.measurement_source_value='upd2206_hygiene' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2207_handwriting] -> measurement.measurement_concept_id=46236383
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    46236383,
    src.visit_date,
    32817,
    'upd2207_handwriting',
    (src."upd2207_handwriting")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2207_handwriting" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=46236383 AND t.measurement_source_value='upd2207_handwriting' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2209_turning_in_bed] -> measurement.measurement_concept_id=46236387
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    46236387,
    src.visit_date,
    32817,
    'upd2209_turning_in_bed',
    (src."upd2209_turning_in_bed")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2209_turning_in_bed" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=46236387 AND t.measurement_source_value='upd2209_turning_in_bed' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2210_tremor] -> measurement.measurement_concept_id=46236391
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    46236391,
    src.visit_date,
    32817,
    'upd2210_tremor',
    (src."upd2210_tremor")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2210_tremor" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=46236391 AND t.measurement_source_value='upd2210_tremor' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2212_walking_and_balance] -> measurement.measurement_concept_id=46236390
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    46236390,
    src.visit_date,
    32817,
    'upd2212_walking_and_balance',
    (src."upd2212_walking_and_balance")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2212_walking_and_balance" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=46236390 AND t.measurement_source_value='upd2212_walking_and_balance' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2213_freezing] -> measurement.measurement_concept_id=46236389
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    46236389,
    src.visit_date,
    32817,
    'upd2213_freezing',
    (src."upd2213_freezing")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2213_freezing" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=46236389 AND t.measurement_source_value='upd2213_freezing' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2303a_rigidity_neck] -> measurement.measurement_concept_id=40768721
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    40768721,
    src.visit_date,
    32817,
    'upd2303a_rigidity_neck',
    (src."upd2303a_rigidity_neck")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2303a_rigidity_neck" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=40768721 AND t.measurement_source_value='upd2303a_rigidity_neck' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2303b_rigidity_rt_upper_extremity] -> measurement.measurement_concept_id=40768873
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    40768873,
    src.visit_date,
    32817,
    'upd2303b_rigidity_rt_upper_extremity',
    (src."upd2303b_rigidity_rt_upper_extremity")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2303b_rigidity_rt_upper_extremity" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=40768873 AND t.measurement_source_value='upd2303b_rigidity_rt_upper_extremity' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2303c_rigidity_left_upper_extremity] -> measurement.measurement_concept_id=40768874
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    40768874,
    src.visit_date,
    32817,
    'upd2303c_rigidity_left_upper_extremity',
    (src."upd2303c_rigidity_left_upper_extremity")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2303c_rigidity_left_upper_extremity" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=40768874 AND t.measurement_source_value='upd2303c_rigidity_left_upper_extremity' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2303d_rigidity_rt_lower_extremity] -> measurement.measurement_concept_id=40768875
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    40768875,
    src.visit_date,
    32817,
    'upd2303d_rigidity_rt_lower_extremity',
    (src."upd2303d_rigidity_rt_lower_extremity")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2303d_rigidity_rt_lower_extremity" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=40768875 AND t.measurement_source_value='upd2303d_rigidity_rt_lower_extremity' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2303e_rigidity_left_lower_extremity] -> measurement.measurement_concept_id=40768876
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    40768876,
    src.visit_date,
    32817,
    'upd2303e_rigidity_left_lower_extremity',
    (src."upd2303e_rigidity_left_lower_extremity")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2303e_rigidity_left_lower_extremity" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=40768876 AND t.measurement_source_value='upd2303e_rigidity_left_lower_extremity' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2311_freezing_of_gait] -> measurement.measurement_concept_id=46236389
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    46236389,
    src.visit_date,
    32817,
    'upd2311_freezing_of_gait',
    (src."upd2311_freezing_of_gait")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2311_freezing_of_gait" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=46236389 AND t.measurement_source_value='upd2311_freezing_of_gait' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2315a_postural_tremor_of_right_hand] -> measurement.measurement_concept_id=40768720
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    40768720,
    src.visit_date,
    32817,
    'upd2315a_postural_tremor_of_right_hand',
    (src."upd2315a_postural_tremor_of_right_hand")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2315a_postural_tremor_of_right_hand" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=40768720 AND t.measurement_source_value='upd2315a_postural_tremor_of_right_hand' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2315b_postural_tremor_of_left_hand] -> measurement.measurement_concept_id=40768877
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    40768877,
    src.visit_date,
    32817,
    'upd2315b_postural_tremor_of_left_hand',
    (src."upd2315b_postural_tremor_of_left_hand")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2315b_postural_tremor_of_left_hand" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=40768877 AND t.measurement_source_value='upd2315b_postural_tremor_of_left_hand' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2317a_rest_tremor_amplitude_right_upper_extremity] -> measurement.measurement_concept_id=40768719
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    40768719,
    src.visit_date,
    32817,
    'upd2317a_rest_tremor_amp_r_upper_extremity',
    (src."upd2317a_rest_tremor_amplitude_right_upper_extremity")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2317a_rest_tremor_amplitude_right_upper_extremity" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=40768719 AND t.measurement_source_value='upd2317a_rest_tremor_amp_r_upper_extremity' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2317c_rest_tremor_amplitude_right_lower_extremity] -> measurement.measurement_concept_id=40768871
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    40768871,
    src.visit_date,
    32817,
    'upd2317c_rest_tremor_amp_r_lower_extremity',
    (src."upd2317c_rest_tremor_amplitude_right_lower_extremity")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2317c_rest_tremor_amplitude_right_lower_extremity" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=40768871 AND t.measurement_source_value='upd2317c_rest_tremor_amp_r_lower_extremity' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2317d_rest_tremor_amplitude_left_lower_extremity] -> measurement.measurement_concept_id=40768872
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    40768872,
    src.visit_date,
    32817,
    'upd2317d_rest_tremor_amp_l_lower_extremity',
    (src."upd2317d_rest_tremor_amplitude_left_lower_extremity")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2317d_rest_tremor_amplitude_left_lower_extremity" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=40768872 AND t.measurement_source_value='upd2317d_rest_tremor_amp_l_lower_extremity' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2317e_rest_tremor_amplitude_lip_or_jaw] -> measurement.measurement_concept_id=40768724
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    40768724,
    src.visit_date,
    32817,
    'upd2317e_rest_tremor_amplitude_lip_or_jaw',
    (src."upd2317e_rest_tremor_amplitude_lip_or_jaw")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2317e_rest_tremor_amplitude_lip_or_jaw" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=40768724 AND t.measurement_source_value='upd2317e_rest_tremor_amplitude_lip_or_jaw' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [updrs1_ment_behav_mood_score] -> measurement.measurement_concept_id=46236408  [number in [0.0,16.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    46236408,
    src.visit_date,
    32817,
    'updrs1_ment_behav_mood_score',
    (src."updrs1_ment_behav_mood_score")::text,
    CASE WHEN src."updrs1_ment_behav_mood_score" ~ '^-?[0-9.]+$' AND src."updrs1_ment_behav_mood_score"::numeric BETWEEN 0.0 AND 16.0 THEN src."updrs1_ment_behav_mood_score"::numeric END,
    CASE WHEN src."updrs1_ment_behav_mood_score" ~ '^-?[0-9]+$' AND NOT (src."updrs1_ment_behav_mood_score"::numeric BETWEEN 0.0 AND 16.0) THEN src."updrs1_ment_behav_mood_score"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."updrs1_ment_behav_mood_score" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=46236408 AND t.measurement_source_value='updrs1_ment_behav_mood_score' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [updrs3_motor_examination_score] -> measurement.measurement_concept_id=46236410  [number in [0.0,108.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    46236410,
    src.visit_date,
    32817,
    'updrs3_motor_examination_score',
    (src."updrs3_motor_examination_score")::text,
    CASE WHEN src."updrs3_motor_examination_score" ~ '^-?[0-9.]+$' AND src."updrs3_motor_examination_score"::numeric BETWEEN 0.0 AND 108.0 THEN src."updrs3_motor_examination_score"::numeric END,
    CASE WHEN src."updrs3_motor_examination_score" ~ '^-?[0-9]+$' AND NOT (src."updrs3_motor_examination_score"::numeric BETWEEN 0.0 AND 108.0) THEN src."updrs3_motor_examination_score"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."updrs3_motor_examination_score" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=46236410 AND t.measurement_source_value='updrs3_motor_examination_score' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [updrs4_therapy_complications_score] -> measurement.measurement_concept_id=46236411  [number in [0.0,30.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    46236411,
    src.visit_date,
    32817,
    'updrs4_therapy_complications_score',
    (src."updrs4_therapy_complications_score")::text,
    CASE WHEN src."updrs4_therapy_complications_score" ~ '^-?[0-9.]+$' AND src."updrs4_therapy_complications_score"::numeric BETWEEN 0.0 AND 30.0 THEN src."updrs4_therapy_complications_score"::numeric END,
    CASE WHEN src."updrs4_therapy_complications_score" ~ '^-?[0-9]+$' AND NOT (src."updrs4_therapy_complications_score"::numeric BETWEEN 0.0 AND 30.0) THEN src."updrs4_therapy_complications_score"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."updrs4_therapy_complications_score" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=46236411 AND t.measurement_source_value='updrs4_therapy_complications_score' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upsit_total_score] -> measurement.measurement_concept_id=3654978  [number in [0.0,40.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    3654978,
    src.visit_date,
    32817,
    'upsit_total_score',
    (src."upsit_total_score")::text,
    CASE WHEN src."upsit_total_score" ~ '^-?[0-9.]+$' AND src."upsit_total_score"::numeric BETWEEN 0.0 AND 40.0 THEN src."upsit_total_score"::numeric END,
    CASE WHEN src."upsit_total_score" ~ '^-?[0-9]+$' AND NOT (src."upsit_total_score"::numeric BETWEEN 0.0 AND 40.0) THEN src."upsit_total_score"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upsit_total_score" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=3654978 AND t.measurement_source_value='upsit_total_score' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [weightUnits] -> measurement.measurement_concept_id=0
INSERT INTO cdm.measurement (
    measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id, measurement_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('measurement_id_seq'),
    p.person_id,
    0,
    src.visit_date,
    32817,
    'weightUnits',
    (src."weightUnits")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."weightUnits" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.measurement t WHERE t.person_id=p.person_id AND t.measurement_concept_id=0 AND t.measurement_source_value='weightUnits' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);

-- ==================== OBSERVATION (234) ====================
-- [ADoutcome] -> observation.observation_concept_id=3187945
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    3187945,
    src.visit_date,
    32817,
    'ADoutcome',
    (src."ADoutcome")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."ADoutcome" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=3187945 AND t.observation_source_value='ADoutcome' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [Age] -> observation.observation_concept_id=3022304  [number in [0.0,120.0]; out-of-range int -> value_as_concept_id] [+unit 9448]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, unit_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    3022304,
    src.visit_date,
    32817,
    'Age',
    (src."Age")::text,
    CASE WHEN src."Age" ~ '^-?[0-9.]+$' AND src."Age"::numeric BETWEEN 0.0 AND 120.0 THEN src."Age"::numeric END,
    CASE WHEN src."Age" ~ '^-?[0-9]+$' AND NOT (src."Age"::numeric BETWEEN 0.0 AND 120.0) THEN src."Age"::int END,
    9448,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."Age" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=3022304 AND t.observation_source_value='Age' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [Age_binned] -> observation.observation_concept_id=3053159  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    3053159,
    src.visit_date,
    32817,
    'Age_binned',
    (src."Age_binned")::text,
    (src."Age_binned")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."Age_binned" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=3053159 AND t.observation_source_value='Age_binned' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [Ballooning] -> observation.observation_concept_id=4150811  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4150811,
    src.visit_date,
    32817,
    'Ballooning',
    (src."Ballooning")::text,
    (src."Ballooning")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."Ballooning" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4150811 AND t.observation_source_value='Ballooning' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [Braak] -> observation.observation_concept_id=3172933  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    3172933,
    src.visit_date,
    32817,
    'Braak',
    (src."Braak")::text,
    (src."Braak")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."Braak" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=3172933 AND t.observation_source_value='Braak' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [Fat.distribution] -> observation.observation_concept_id=4093857  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4093857,
    src.visit_date,
    32817,
    'Fat.distribution',
    (src."Fat.distribution")::text,
    (src."Fat.distribution")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."Fat.distribution" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4093857 AND t.observation_source_value='Fat.distribution' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [GUID] -> observation.observation_concept_id=42528934  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    42528934,
    src.visit_date,
    32817,
    'GUID',
    (src."GUID")::text,
    (src."GUID")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."GUID" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=42528934 AND t.observation_source_value='GUID' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [Hepatocyte.necrosis] -> observation.observation_concept_id=4280654
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4280654,
    src.visit_date,
    32817,
    'Hepatocyte.necrosis',
    (src."Hepatocyte.necrosis")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."Hepatocyte.necrosis" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4280654 AND t.observation_source_value='Hepatocyte.necrosis' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [ID] -> observation.observation_concept_id=42528934  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    42528934,
    src.visit_date,
    32817,
    'ID',
    (src."ID")::text,
    (src."ID")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."ID" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=42528934 AND t.observation_source_value='ID' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [Study] -> observation.observation_concept_id=21492138  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    21492138,
    src.visit_date,
    32817,
    'Study',
    (src."Study")::text,
    (src."Study")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."Study" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=21492138 AND t.observation_source_value='Study' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [age] -> observation.observation_concept_id=3022304  [number in [0.0,120.0]; out-of-range int -> value_as_concept_id] [+unit 9448]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, unit_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    3022304,
    src.visit_date,
    32817,
    'age',
    (src."age")::text,
    CASE WHEN src."age" ~ '^-?[0-9.]+$' AND src."age"::numeric BETWEEN 0.0 AND 120.0 THEN src."age"::numeric END,
    CASE WHEN src."age" ~ '^-?[0-9]+$' AND NOT (src."age"::numeric BETWEEN 0.0 AND 120.0) THEN src."age"::int END,
    9448,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."age" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=3022304 AND t.observation_source_value='age' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [age.range] -> observation.observation_concept_id=3053159  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    3053159,
    src.visit_date,
    32817,
    'age.range',
    (src."age.range")::text,
    (src."age.range")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."age.range" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=3053159 AND t.observation_source_value='age.range' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [ageUnits] -> observation.observation_concept_id=9448
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    9448,
    src.visit_date,
    32817,
    'ageUnits',
    (src."ageUnits")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."ageUnits" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=9448 AND t.observation_source_value='ageUnits' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [age_at_diagnosis_pd] -> observation.observation_concept_id=43530536  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    43530536,
    src.visit_date,
    32817,
    'age_at_diagnosis_pd',
    (src."age_at_diagnosis_pd")::text,
    (src."age_at_diagnosis_pd")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."age_at_diagnosis_pd" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=43530536 AND t.observation_source_value='age_at_diagnosis_pd' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [age_at_visit] -> observation.observation_concept_id=3022304  [number in [0.0,120.0]; out-of-range int -> value_as_concept_id] [+unit 9448]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, unit_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    3022304,
    src.visit_date,
    32817,
    'age_at_visit',
    (src."age_at_visit")::text,
    CASE WHEN src."age_at_visit" ~ '^-?[0-9.]+$' AND src."age_at_visit"::numeric BETWEEN 0.0 AND 120.0 THEN src."age_at_visit"::numeric END,
    CASE WHEN src."age_at_visit" ~ '^-?[0-9]+$' AND NOT (src."age_at_visit"::numeric BETWEEN 0.0 AND 120.0) THEN src."age_at_visit"::int END,
    9448,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."age_at_visit" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=3022304 AND t.observation_source_value='age_at_visit' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [age_at_visit_max] -> observation.observation_concept_id=40766621  [value_as_number (no explicit range)] [+unit 9448]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, unit_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40766621,
    src.visit_date,
    32817,
    'age_at_visit_max',
    (src."age_at_visit_max")::text,
    CASE WHEN src."age_at_visit_max" ~ '^-?[0-9]+(\.[0-9]+)?$' THEN src."age_at_visit_max"::numeric END,
    9448,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."age_at_visit_max" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40766621 AND t.observation_source_value='age_at_visit_max' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [age_death] -> observation.observation_concept_id=3038421  [number in [0.0,120.0]; out-of-range int -> value_as_concept_id] [+unit 9448]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, unit_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    3038421,
    src.visit_date,
    32817,
    'age_death',
    (src."age_death")::text,
    CASE WHEN src."age_death" ~ '^-?[0-9.]+$' AND src."age_death"::numeric BETWEEN 0.0 AND 120.0 THEN src."age_death"::numeric END,
    CASE WHEN src."age_death" ~ '^-?[0-9]+$' AND NOT (src."age_death"::numeric BETWEEN 0.0 AND 120.0) THEN src."age_death"::int END,
    9448,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."age_death" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=3038421 AND t.observation_source_value='age_death' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [alcohol_consumed_years] -> observation.observation_concept_id=44786670  [number in [1.0,51.0]; out-of-range int -> value_as_concept_id] [+unit 9448]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, unit_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    44786670,
    src.visit_date,
    32817,
    'alcohol_consumed_years',
    (src."alcohol_consumed_years")::text,
    CASE WHEN src."alcohol_consumed_years" ~ '^-?[0-9.]+$' AND src."alcohol_consumed_years"::numeric BETWEEN 1.0 AND 51.0 THEN src."alcohol_consumed_years"::numeric END,
    CASE WHEN src."alcohol_consumed_years" ~ '^-?[0-9]+$' AND NOT (src."alcohol_consumed_years"::numeric BETWEEN 1.0 AND 51.0) THEN src."alcohol_consumed_years"::int END,
    9448,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."alcohol_consumed_years" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=44786670 AND t.observation_source_value='alcohol_consumed_years' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [alcohol_consumption_change] -> observation.observation_concept_id=35810233  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    35810233,
    src.visit_date,
    32817,
    'alcohol_consumption_change',
    (src."alcohol_consumption_change")::text,
    (src."alcohol_consumption_change")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."alcohol_consumption_change" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=35810233 AND t.observation_source_value='alcohol_consumption_change' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [alcohol_current_use] -> observation.observation_concept_id=4074035  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4074035,
    src.visit_date,
    32817,
    'alcohol_current_use',
    (src."alcohol_current_use")::text,
    (src."alcohol_current_use")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."alcohol_current_use" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4074035 AND t.observation_source_value='alcohol_current_use' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [alcohol_drinks_daily_range] -> observation.observation_concept_id=35811099  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    35811099,
    src.visit_date,
    32817,
    'alcohol_drinks_daily_range',
    (src."alcohol_drinks_daily_range")::text,
    (src."alcohol_drinks_daily_range")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."alcohol_drinks_daily_range" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=35811099 AND t.observation_source_value='alcohol_drinks_daily_range' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [alcohol_drinks_day] -> observation.observation_concept_id=40771104  [number in [0.0,10.0]; out-of-range int -> value_as_concept_id] [+unit 8512]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, unit_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40771104,
    src.visit_date,
    32817,
    'alcohol_drinks_day',
    (src."alcohol_drinks_day")::text,
    CASE WHEN src."alcohol_drinks_day" ~ '^-?[0-9.]+$' AND src."alcohol_drinks_day"::numeric BETWEEN 0.0 AND 10.0 THEN src."alcohol_drinks_day"::numeric END,
    CASE WHEN src."alcohol_drinks_day" ~ '^-?[0-9]+$' AND NOT (src."alcohol_drinks_day"::numeric BETWEEN 0.0 AND 10.0) THEN src."alcohol_drinks_day"::int END,
    8512,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."alcohol_drinks_day" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40771104 AND t.observation_source_value='alcohol_drinks_day' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [alcohol_ever_used] -> observation.observation_concept_id=619635  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    619635,
    src.visit_date,
    32817,
    'alcohol_ever_used',
    (src."alcohol_ever_used")::text,
    (src."alcohol_ever_used")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."alcohol_ever_used" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=619635 AND t.observation_source_value='alcohol_ever_used' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [alcohol_inc_dec] -> observation.observation_concept_id=35810233  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    35810233,
    src.visit_date,
    32817,
    'alcohol_inc_dec',
    (src."alcohol_inc_dec")::text,
    (src."alcohol_inc_dec")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."alcohol_inc_dec" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=35810233 AND t.observation_source_value='alcohol_inc_dec' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [alcohol_prior_use] -> observation.observation_concept_id=4220362  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4220362,
    src.visit_date,
    32817,
    'alcohol_prior_use',
    (src."alcohol_prior_use")::text,
    (src."alcohol_prior_use")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."alcohol_prior_use" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4220362 AND t.observation_source_value='alcohol_prior_use' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [alcohol_six_more_drinks_frequency] -> observation.observation_concept_id=35811112  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    35811112,
    src.visit_date,
    32817,
    'alcohol_six_more_drinks_frequency',
    (src."alcohol_six_more_drinks_frequency")::text,
    (src."alcohol_six_more_drinks_frequency")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."alcohol_six_more_drinks_frequency" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=35811112 AND t.observation_source_value='alcohol_six_more_drinks_frequency' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [alcohol_start_age] -> observation.observation_concept_id=40766358  [number in [1.0,75.0]; out-of-range int -> value_as_concept_id] [+unit 9448]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, unit_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40766358,
    src.visit_date,
    32817,
    'alcohol_start_age',
    (src."alcohol_start_age")::text,
    CASE WHEN src."alcohol_start_age" ~ '^-?[0-9.]+$' AND src."alcohol_start_age"::numeric BETWEEN 1.0 AND 75.0 THEN src."alcohol_start_age"::numeric END,
    CASE WHEN src."alcohol_start_age" ~ '^-?[0-9]+$' AND NOT (src."alcohol_start_age"::numeric BETWEEN 1.0 AND 75.0) THEN src."alcohol_start_age"::int END,
    9448,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."alcohol_start_age" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40766358 AND t.observation_source_value='alcohol_start_age' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [alcohol_stop_age] -> observation.observation_concept_id=36031408  [number in [9.0,85.0]; out-of-range int -> value_as_concept_id] [+unit 9448]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, unit_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    36031408,
    src.visit_date,
    32817,
    'alcohol_stop_age',
    (src."alcohol_stop_age")::text,
    CASE WHEN src."alcohol_stop_age" ~ '^-?[0-9.]+$' AND src."alcohol_stop_age"::numeric BETWEEN 9.0 AND 85.0 THEN src."alcohol_stop_age"::numeric END,
    CASE WHEN src."alcohol_stop_age" ~ '^-?[0-9]+$' AND NOT (src."alcohol_stop_age"::numeric BETWEEN 9.0 AND 85.0) THEN src."alcohol_stop_age"::int END,
    9448,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."alcohol_stop_age" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=36031408 AND t.observation_source_value='alcohol_stop_age' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [alcohol_use_frequency] -> observation.observation_concept_id=35811110  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    35811110,
    src.visit_date,
    32817,
    'alcohol_use_frequency',
    (src."alcohol_use_frequency")::text,
    (src."alcohol_use_frequency")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."alcohol_use_frequency" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=35811110 AND t.observation_source_value='alcohol_use_frequency' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [amyAny] -> observation.observation_concept_id=4288616  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4288616,
    src.visit_date,
    32817,
    'amyAny',
    (src."amyAny")::text,
    (src."amyAny")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."amyAny" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4288616 AND t.observation_source_value='amyAny' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [ancestry] -> observation.observation_concept_id=0  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    0,
    src.visit_date,
    32817,
    'ancestry',
    (src."ancestry")::text,
    (src."ancestry")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."ancestry" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=0 AND t.observation_source_value='ancestry' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [ancestry__ontology_id] -> observation.observation_concept_id=0
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    0,
    src.visit_date,
    32817,
    'ancestry__ontology_id',
    (src."ancestry__ontology_id")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."ancestry__ontology_id" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=0 AND t.observation_source_value='ancestry__ontology_id' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [ancestry__ontology_label] -> observation.observation_concept_id=0
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    0,
    src.visit_date,
    32817,
    'ancestry__ontology_label',
    (src."ancestry__ontology_label")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."ancestry__ontology_label" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=0 AND t.observation_source_value='ancestry__ontology_label' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [caff_drinks_ever_used_regularly] -> observation.observation_concept_id=37153131  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    37153131,
    src.visit_date,
    32817,
    'caff_drinks_ever_used_regularly',
    (src."caff_drinks_ever_used_regularly")::text,
    (src."caff_drinks_ever_used_regularly")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."caff_drinks_ever_used_regularly" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=37153131 AND t.observation_source_value='caff_drinks_ever_used_regularly' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [change_in_diagnosis] -> observation.observation_concept_id=0
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    0,
    src.visit_date,
    32817,
    'change_in_diagnosis',
    (src."change_in_diagnosis")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."change_in_diagnosis" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=0 AND t.observation_source_value='change_in_diagnosis' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [cigarettes_per_day_current] -> observation.observation_concept_id=35810373  [number in [0.0,250.0]; out-of-range int -> value_as_concept_id] [+unit 8512]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, unit_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    35810373,
    src.visit_date,
    32817,
    'cigarettes_per_day_current',
    (src."cigarettes_per_day_current")::text,
    CASE WHEN src."cigarettes_per_day_current" ~ '^-?[0-9.]+$' AND src."cigarettes_per_day_current"::numeric BETWEEN 0.0 AND 250.0 THEN src."cigarettes_per_day_current"::numeric END,
    CASE WHEN src."cigarettes_per_day_current" ~ '^-?[0-9]+$' AND NOT (src."cigarettes_per_day_current"::numeric BETWEEN 0.0 AND 250.0) THEN src."cigarettes_per_day_current"::int END,
    8512,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."cigarettes_per_day_current" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=35810373 AND t.observation_source_value='cigarettes_per_day_current' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [cigarettes_per_day_past] -> observation.observation_concept_id=35810326  [number in [0.0,80.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    35810326,
    src.visit_date,
    32817,
    'cigarettes_per_day_past',
    (src."cigarettes_per_day_past")::text,
    CASE WHEN src."cigarettes_per_day_past" ~ '^-?[0-9.]+$' AND src."cigarettes_per_day_past"::numeric BETWEEN 0.0 AND 80.0 THEN src."cigarettes_per_day_past"::numeric END,
    CASE WHEN src."cigarettes_per_day_past" ~ '^-?[0-9]+$' AND NOT (src."cigarettes_per_day_past"::numeric BETWEEN 0.0 AND 80.0) THEN src."cigarettes_per_day_past"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."cigarettes_per_day_past" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=35810326 AND t.observation_source_value='cigarettes_per_day_past' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [cogdx] -> observation.observation_concept_id=4162723
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4162723,
    src.visit_date,
    32817,
    'cogdx',
    (src."cogdx")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."cogdx" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4162723 AND t.observation_source_value='cogdx' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [cohort] -> observation.observation_concept_id=0  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    0,
    src.visit_date,
    32817,
    'cohort',
    (src."cohort")::text,
    (src."cohort")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."cohort" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=0 AND t.observation_source_value='cohort' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [comorbidities] -> observation.observation_concept_id=4160039
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4160039,
    src.visit_date,
    32817,
    'comorbidities',
    (src."comorbidities")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."comorbidities" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4160039 AND t.observation_source_value='comorbidities' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [cts_mmse30_lv] -> observation.observation_concept_id=42869861  [number in [0.0,30.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    42869861,
    src.visit_date,
    32817,
    'cts_mmse30_lv',
    (src."cts_mmse30_lv")::text,
    CASE WHEN src."cts_mmse30_lv" ~ '^-?[0-9.]+$' AND src."cts_mmse30_lv"::numeric BETWEEN 0.0 AND 30.0 THEN src."cts_mmse30_lv"::numeric END,
    CASE WHEN src."cts_mmse30_lv" ~ '^-?[0-9]+$' AND NOT (src."cts_mmse30_lv"::numeric BETWEEN 0.0 AND 30.0) THEN src."cts_mmse30_lv"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."cts_mmse30_lv" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=42869861 AND t.observation_source_value='cts_mmse30_lv' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [dcfdx] -> observation.observation_concept_id=4162723
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4162723,
    src.visit_date,
    32817,
    'dcfdx',
    (src."dcfdx")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."dcfdx" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4162723 AND t.observation_source_value='dcfdx' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [derivedOutcomeBasedOnMayoDx] -> observation.observation_concept_id=4107185  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4107185,
    src.visit_date,
    32817,
    'derivedOutcomeBasedOnMayoDx',
    (src."derivedOutcomeBasedOnMayoDx")::text,
    (src."derivedOutcomeBasedOnMayoDx")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."derivedOutcomeBasedOnMayoDx" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4107185 AND t.observation_source_value='derivedOutcomeBasedOnMayoDx' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [development_stage] -> observation.observation_concept_id=3053159
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    3053159,
    src.visit_date,
    32817,
    'development_stage',
    (src."development_stage")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."development_stage" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=3053159 AND t.observation_source_value='development_stage' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [diabetes_history] -> observation.observation_concept_id=40769338  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40769338,
    src.visit_date,
    32817,
    'diabetes_history',
    (src."diabetes_history")::text,
    (src."diabetes_history")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."diabetes_history" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40769338 AND t.observation_source_value='diabetes_history' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [diagnosis_type] -> observation.observation_concept_id=1988354  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    1988354,
    src.visit_date,
    32817,
    'diagnosis_type',
    (src."diagnosis_type")::text,
    (src."diagnosis_type")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."diagnosis_type" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=1988354 AND t.observation_source_value='diagnosis_type' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [disease] -> observation.observation_concept_id=436670
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    436670,
    src.visit_date,
    32817,
    'disease',
    (src."disease")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."disease" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=436670 AND t.observation_source_value='disease' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [disease__ontology_id] -> observation.observation_concept_id=4234469  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4234469,
    src.visit_date,
    32817,
    'disease__ontology_id',
    (src."disease__ontology_id")::text,
    (src."disease__ontology_id")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."disease__ontology_id" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4234469 AND t.observation_source_value='disease__ontology_id' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [disease__ontology_label] -> observation.observation_concept_id=4234469
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4234469,
    src.visit_date,
    32817,
    'disease__ontology_label',
    (src."disease__ontology_label")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."disease__ontology_label" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4234469 AND t.observation_source_value='disease__ontology_label' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [disease_category] -> observation.observation_concept_id=436670
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    436670,
    src.visit_date,
    32817,
    'disease_category',
    (src."disease_category")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."disease_category" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=436670 AND t.observation_source_value='disease_category' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [disease_ontology_term_id] -> observation.observation_concept_id=4234469
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4234469,
    src.visit_date,
    32817,
    'disease_ontology_term_id',
    (src."disease_ontology_term_id")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."disease_ontology_term_id" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4234469 AND t.observation_source_value='disease_ontology_term_id' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [disease_status] -> observation.observation_concept_id=1989567  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    1989567,
    src.visit_date,
    32817,
    'disease_status',
    (src."disease_status")::text,
    (src."disease_status")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."disease_status" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=1989567 AND t.observation_source_value='disease_status' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [diseasetype] -> observation.observation_concept_id=436670
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    436670,
    src.visit_date,
    32817,
    'diseasetype',
    (src."diseasetype")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."diseasetype" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=436670 AND t.observation_source_value='diseasetype' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [dti_measure] -> observation.observation_concept_id=4104285  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4104285,
    src.visit_date,
    32817,
    'dti_measure',
    (src."dti_measure")::text,
    (src."dti_measure")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."dti_measure" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4104285 AND t.observation_source_value='dti_measure' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [education_12years_complete] -> observation.observation_concept_id=36031310  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    36031310,
    src.visit_date,
    32817,
    'education_12years_complete',
    (src."education_12years_complete")::text,
    (src."education_12years_complete")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."education_12years_complete" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=36031310 AND t.observation_source_value='education_12years_complete' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [ethnicity] -> observation.observation_concept_id=40771985
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40771985,
    src.visit_date,
    32817,
    'ethnicity',
    (src."ethnicity")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."ethnicity" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40771985 AND t.observation_source_value='ethnicity' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [ethnicity__ontology_id] -> observation.observation_concept_id=4271761  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4271761,
    src.visit_date,
    32817,
    'ethnicity__ontology_id',
    (src."ethnicity__ontology_id")::text,
    (src."ethnicity__ontology_id")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."ethnicity__ontology_id" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4271761 AND t.observation_source_value='ethnicity__ontology_id' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [ethnicity__ontology_label] -> observation.observation_concept_id=4271761  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4271761,
    src.visit_date,
    32817,
    'ethnicity__ontology_label',
    (src."ethnicity__ontology_label")::text,
    (src."ethnicity__ontology_label")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."ethnicity__ontology_label" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4271761 AND t.observation_source_value='ethnicity__ontology_label' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [exclude] -> observation.observation_concept_id=0
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    0,
    src.visit_date,
    32817,
    'exclude',
    (src."exclude")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."exclude" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=0 AND t.observation_source_value='exclude' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [exec_dys] -> observation.observation_concept_id=42537141  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    42537141,
    src.visit_date,
    32817,
    'exec_dys',
    (src."exec_dys")::text,
    (src."exec_dys")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."exec_dys" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=42537141 AND t.observation_source_value='exec_dys' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [fastingState] -> observation.observation_concept_id=3031632  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    3031632,
    src.visit_date,
    32817,
    'fastingState',
    (src."fastingState")::text,
    (src."fastingState")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."fastingState" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=3031632 AND t.observation_source_value='fastingState' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [hypertension] -> observation.observation_concept_id=316866
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    316866,
    src.visit_date,
    32817,
    'hypertension',
    (src."hypertension")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."hypertension" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=316866 AND t.observation_source_value='hypertension' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [individualID] -> observation.observation_concept_id=42528934  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    42528934,
    src.visit_date,
    32817,
    'individualID',
    (src."individualID")::text,
    (src."individualID")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."individualID" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=42528934 AND t.observation_source_value='individualID' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [isHispanic] -> observation.observation_concept_id=38003563
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    38003563,
    src.visit_date,
    32817,
    'isHispanic',
    (src."isHispanic")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."isHispanic" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=38003563 AND t.observation_source_value='isHispanic' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [isPostMortem] -> observation.observation_concept_id=44808081  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    44808081,
    src.visit_date,
    32817,
    'isPostMortem',
    (src."isPostMortem")::text,
    (src."isPostMortem")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."isPostMortem" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=44808081 AND t.observation_source_value='isPostMortem' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [is_primary_data] -> observation.observation_concept_id=46235134  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    46235134,
    src.visit_date,
    32817,
    'is_primary_data',
    (src."is_primary_data")::text,
    (src."is_primary_data")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."is_primary_data" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=46235134 AND t.observation_source_value='is_primary_data' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [mayoDx] -> observation.observation_concept_id=3187945
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    3187945,
    src.visit_date,
    32817,
    'mayoDx',
    (src."mayoDx")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."mayoDx" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=3187945 AND t.observation_source_value='mayoDx' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [mms101a_year] -> observation.observation_concept_id=1260024  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    1260024,
    src.visit_date,
    32817,
    'mms101a_year',
    (src."mms101a_year")::text,
    (src."mms101a_year")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."mms101a_year" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=1260024 AND t.observation_source_value='mms101a_year' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [mms101b_season] -> observation.observation_concept_id=3184143  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    3184143,
    src.visit_date,
    32817,
    'mms101b_season',
    (src."mms101b_season")::text,
    (src."mms101b_season")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."mms101b_season" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=3184143 AND t.observation_source_value='mms101b_season' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [mms101c_month] -> observation.observation_concept_id=1260104  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    1260104,
    src.visit_date,
    32817,
    'mms101c_month',
    (src."mms101c_month")::text,
    (src."mms101c_month")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."mms101c_month" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=1260104 AND t.observation_source_value='mms101c_month' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [mms101d_day] -> observation.observation_concept_id=1260032  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    1260032,
    src.visit_date,
    32817,
    'mms101d_day',
    (src."mms101d_day")::text,
    (src."mms101d_day")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."mms101d_day" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=1260032 AND t.observation_source_value='mms101d_day' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [mms112_total_score] -> observation.observation_concept_id=42869860  [number in [13.0,30.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    42869860,
    src.visit_date,
    32817,
    'mms112_total_score',
    (src."mms112_total_score")::text,
    CASE WHEN src."mms112_total_score" ~ '^-?[0-9.]+$' AND src."mms112_total_score"::numeric BETWEEN 13.0 AND 30.0 THEN src."mms112_total_score"::numeric END,
    CASE WHEN src."mms112_total_score" ~ '^-?[0-9]+$' AND NOT (src."mms112_total_score"::numeric BETWEEN 13.0 AND 30.0) THEN src."mms112_total_score"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."mms112_total_score" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=42869860 AND t.observation_source_value='mms112_total_score' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [mmse] -> observation.observation_concept_id=42869861  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    42869861,
    src.visit_date,
    32817,
    'mmse',
    (src."mmse")::text,
    (src."mmse")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."mmse" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=42869861 AND t.observation_source_value='mmse' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [moca22_orientation_date_score] -> observation.observation_concept_id=4013819  [number in [0.0,1.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4013819,
    src.visit_date,
    32817,
    'moca22_orientation_date_score',
    (src."moca22_orientation_date_score")::text,
    CASE WHEN src."moca22_orientation_date_score" ~ '^-?[0-9.]+$' AND src."moca22_orientation_date_score"::numeric BETWEEN 0.0 AND 1.0 THEN src."moca22_orientation_date_score"::numeric END,
    CASE WHEN src."moca22_orientation_date_score" ~ '^-?[0-9]+$' AND NOT (src."moca22_orientation_date_score"::numeric BETWEEN 0.0 AND 1.0) THEN src."moca22_orientation_date_score"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."moca22_orientation_date_score" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4013819 AND t.observation_source_value='moca22_orientation_date_score' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [moca23_orientation_month_score] -> observation.observation_concept_id=4012956  [number in [0.0,1.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4012956,
    src.visit_date,
    32817,
    'moca23_orientation_month_score',
    (src."moca23_orientation_month_score")::text,
    CASE WHEN src."moca23_orientation_month_score" ~ '^-?[0-9.]+$' AND src."moca23_orientation_month_score"::numeric BETWEEN 0.0 AND 1.0 THEN src."moca23_orientation_month_score"::numeric END,
    CASE WHEN src."moca23_orientation_month_score" ~ '^-?[0-9]+$' AND NOT (src."moca23_orientation_month_score"::numeric BETWEEN 0.0 AND 1.0) THEN src."moca23_orientation_month_score"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."moca23_orientation_month_score" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4012956 AND t.observation_source_value='moca23_orientation_month_score' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [moca25_orientation_day_score] -> observation.observation_concept_id=4153986  [number in [0.0,1.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4153986,
    src.visit_date,
    32817,
    'moca25_orientation_day_score',
    (src."moca25_orientation_day_score")::text,
    CASE WHEN src."moca25_orientation_day_score" ~ '^-?[0-9.]+$' AND src."moca25_orientation_day_score"::numeric BETWEEN 0.0 AND 1.0 THEN src."moca25_orientation_day_score"::numeric END,
    CASE WHEN src."moca25_orientation_day_score" ~ '^-?[0-9]+$' AND NOT (src."moca25_orientation_day_score"::numeric BETWEEN 0.0 AND 1.0) THEN src."moca25_orientation_day_score"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."moca25_orientation_day_score" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4153986 AND t.observation_source_value='moca25_orientation_day_score' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [moca26_orientation_place_score] -> observation.observation_concept_id=4012679  [number in [0.0,1.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4012679,
    src.visit_date,
    32817,
    'moca26_orientation_place_score',
    (src."moca26_orientation_place_score")::text,
    CASE WHEN src."moca26_orientation_place_score" ~ '^-?[0-9.]+$' AND src."moca26_orientation_place_score"::numeric BETWEEN 0.0 AND 1.0 THEN src."moca26_orientation_place_score"::numeric END,
    CASE WHEN src."moca26_orientation_place_score" ~ '^-?[0-9]+$' AND NOT (src."moca26_orientation_place_score"::numeric BETWEEN 0.0 AND 1.0) THEN src."moca26_orientation_place_score"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."moca26_orientation_place_score" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4012679 AND t.observation_source_value='moca26_orientation_place_score' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [moca27_orientation_city_score] -> observation.observation_concept_id=0  [number in [0.0,1.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    0,
    src.visit_date,
    32817,
    'moca27_orientation_city_score',
    (src."moca27_orientation_city_score")::text,
    CASE WHEN src."moca27_orientation_city_score" ~ '^-?[0-9.]+$' AND src."moca27_orientation_city_score"::numeric BETWEEN 0.0 AND 1.0 THEN src."moca27_orientation_city_score"::numeric END,
    CASE WHEN src."moca27_orientation_city_score" ~ '^-?[0-9]+$' AND NOT (src."moca27_orientation_city_score"::numeric BETWEEN 0.0 AND 1.0) THEN src."moca27_orientation_city_score"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."moca27_orientation_city_score" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=0 AND t.observation_source_value='moca27_orientation_city_score' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [moca_delayed_recall_subscore] -> observation.observation_concept_id=4153990  [number in [0.0,5.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4153990,
    src.visit_date,
    32817,
    'moca_delayed_recall_subscore',
    (src."moca_delayed_recall_subscore")::text,
    CASE WHEN src."moca_delayed_recall_subscore" ~ '^-?[0-9.]+$' AND src."moca_delayed_recall_subscore"::numeric BETWEEN 0.0 AND 5.0 THEN src."moca_delayed_recall_subscore"::numeric END,
    CASE WHEN src."moca_delayed_recall_subscore" ~ '^-?[0-9]+$' AND NOT (src."moca_delayed_recall_subscore"::numeric BETWEEN 0.0 AND 5.0) THEN src."moca_delayed_recall_subscore"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."moca_delayed_recall_subscore" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4153990 AND t.observation_source_value='moca_delayed_recall_subscore' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [moca_total_score] -> observation.observation_concept_id=43054915  [number in [0.0,31.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    43054915,
    src.visit_date,
    32817,
    'moca_total_score',
    (src."moca_total_score")::text,
    CASE WHEN src."moca_total_score" ~ '^-?[0-9.]+$' AND src."moca_total_score"::numeric BETWEEN 0.0 AND 31.0 THEN src."moca_total_score"::numeric END,
    CASE WHEN src."moca_total_score" ~ '^-?[0-9]+$' AND NOT (src."moca_total_score"::numeric BETWEEN 0.0 AND 31.0) THEN src."moca_total_score"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."moca_total_score" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=43054915 AND t.observation_source_value='moca_total_score' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [modality] -> observation.observation_concept_id=40757633  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40757633,
    src.visit_date,
    32817,
    'modality',
    (src."modality")::text,
    (src."modality")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."modality" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40757633 AND t.observation_source_value='modality' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [mood_dis] -> observation.observation_concept_id=444100
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    444100,
    src.visit_date,
    32817,
    'mood_dis',
    (src."mood_dis")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."mood_dis" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=444100 AND t.observation_source_value='mood_dis' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [most_recent_diagnosis] -> observation.observation_concept_id=0  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    0,
    src.visit_date,
    32817,
    'most_recent_diagnosis',
    (src."most_recent_diagnosis")::text,
    (src."most_recent_diagnosis")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."most_recent_diagnosis" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=0 AND t.observation_source_value='most_recent_diagnosis' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [msex] -> observation.observation_concept_id=3046965
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    3046965,
    src.visit_date,
    32817,
    'msex',
    (src."msex")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."msex" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=3046965 AND t.observation_source_value='msex' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [msq01b_patient_injured] -> observation.observation_concept_id=42689795
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    42689795,
    src.visit_date,
    32817,
    'msq01b_patient_injured',
    (src."msq01b_patient_injured")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."msq01b_patient_injured" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=42689795 AND t.observation_source_value='msq01b_patient_injured' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [msq01c_bedpartner_injured] -> observation.observation_concept_id=40768319  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40768319,
    src.visit_date,
    32817,
    'msq01c_bedpartner_injured',
    (src."msq01c_bedpartner_injured")::text,
    (src."msq01c_bedpartner_injured")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."msq01c_bedpartner_injured" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40768319 AND t.observation_source_value='msq01c_bedpartner_injured' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [msq01d_told_dreams] -> observation.observation_concept_id=0
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    0,
    src.visit_date,
    32817,
    'msq01d_told_dreams',
    (src."msq01d_told_dreams")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."msq01d_told_dreams" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=0 AND t.observation_source_value='msq01d_told_dreams' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [msq02_legs_jerk] -> observation.observation_concept_id=40767223
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40767223,
    src.visit_date,
    32817,
    'msq02_legs_jerk',
    (src."msq02_legs_jerk")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."msq02_legs_jerk" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40767223 AND t.observation_source_value='msq02_legs_jerk' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [msq03_restless_legs] -> observation.observation_concept_id=73754
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    73754,
    src.visit_date,
    32817,
    'msq03_restless_legs',
    (src."msq03_restless_legs")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."msq03_restless_legs" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=73754 AND t.observation_source_value='msq03_restless_legs' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [msq04b_walked_asleep] -> observation.observation_concept_id=40767237
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40767237,
    src.visit_date,
    32817,
    'msq04b_walked_asleep',
    (src."msq04b_walked_asleep")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."msq04b_walked_asleep" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40767237 AND t.observation_source_value='msq04b_walked_asleep' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [msq05_snorted_awake] -> observation.observation_concept_id=40767217
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40767217,
    src.visit_date,
    32817,
    'msq05_snorted_awake',
    (src."msq05_snorted_awake")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."msq05_snorted_awake" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40767217 AND t.observation_source_value='msq05_snorted_awake' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [msq06_stop_breathing] -> observation.observation_concept_id=40767199
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40767199,
    src.visit_date,
    32817,
    'msq06_stop_breathing',
    (src."msq06_stop_breathing")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."msq06_stop_breathing" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40767199 AND t.observation_source_value='msq06_stop_breathing' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [msq06a_treated_for_stop_breathing] -> observation.observation_concept_id=43528875  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    43528875,
    src.visit_date,
    32817,
    'msq06a_treated_for_stop_breathing',
    (src."msq06a_treated_for_stop_breathing")::text,
    (src."msq06a_treated_for_stop_breathing")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."msq06a_treated_for_stop_breathing" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=43528875 AND t.observation_source_value='msq06a_treated_for_stop_breathing' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [msq07_leg_cramps] -> observation.observation_concept_id=40768776  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40768776,
    src.visit_date,
    32817,
    'msq07_leg_cramps',
    (src."msq07_leg_cramps")::text,
    (src."msq07_leg_cramps")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."msq07_leg_cramps" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40768776 AND t.observation_source_value='msq07_leg_cramps' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [msq08_rate_of_alertness] -> observation.observation_concept_id=4093835  [number in [0.0,10.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4093835,
    src.visit_date,
    32817,
    'msq08_rate_of_alertness',
    (src."msq08_rate_of_alertness")::text,
    CASE WHEN src."msq08_rate_of_alertness" ~ '^-?[0-9.]+$' AND src."msq08_rate_of_alertness"::numeric BETWEEN 0.0 AND 10.0 THEN src."msq08_rate_of_alertness"::numeric END,
    CASE WHEN src."msq08_rate_of_alertness" ~ '^-?[0-9]+$' AND NOT (src."msq08_rate_of_alertness"::numeric BETWEEN 0.0 AND 10.0) THEN src."msq08_rate_of_alertness"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."msq08_rate_of_alertness" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4093835 AND t.observation_source_value='msq08_rate_of_alertness' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [msq_distracting_sleep_behaviors] -> observation.observation_concept_id=4204989  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4204989,
    src.visit_date,
    32817,
    'msq_distracting_sleep_behaviors',
    (src."msq_distracting_sleep_behaviors")::text,
    (src."msq_distracting_sleep_behaviors")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."msq_distracting_sleep_behaviors" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4204989 AND t.observation_source_value='msq_distracting_sleep_behaviors' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [msq_info_source] -> observation.observation_concept_id=42529257
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    42529257,
    src.visit_date,
    32817,
    'msq_info_source',
    (src."msq_info_source")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."msq_info_source" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=42529257 AND t.observation_source_value='msq_info_source' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [msq_interviewee_live_with_subject] -> observation.observation_concept_id=40760162  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40760162,
    src.visit_date,
    32817,
    'msq_interviewee_live_with_subject',
    (src."msq_interviewee_live_with_subject")::text,
    (src."msq_interviewee_live_with_subject")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."msq_interviewee_live_with_subject" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40760162 AND t.observation_source_value='msq_interviewee_live_with_subject' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [neurolep_sens] -> observation.observation_concept_id=443340  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    443340,
    src.visit_date,
    32817,
    'neurolep_sens',
    (src."neurolep_sens")::text,
    (src."neurolep_sens")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."neurolep_sens" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=443340 AND t.observation_source_value='neurolep_sens' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [observation_joinid] -> observation.observation_concept_id=0
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    0,
    src.visit_date,
    32817,
    'observation_joinid',
    (src."observation_joinid")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."observation_joinid" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=0 AND t.observation_source_value='observation_joinid' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [on_dopamine_agonist] -> observation.observation_concept_id=4170593
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4170593,
    src.visit_date,
    32817,
    'on_dopamine_agonist',
    (src."on_dopamine_agonist")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."on_dopamine_agonist" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4170593 AND t.observation_source_value='on_dopamine_agonist' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [on_other_pd_medications] -> observation.observation_concept_id=0
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    0,
    src.visit_date,
    32817,
    'on_other_pd_medications',
    (src."on_other_pd_medications")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."on_other_pd_medications" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=0 AND t.observation_source_value='on_other_pd_medications' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [organ__ontology_label] -> observation.observation_concept_id=596878  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    596878,
    src.visit_date,
    32817,
    'organ__ontology_label',
    (src."organ__ontology_label")::text,
    (src."organ__ontology_label")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."organ__ontology_label" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=596878 AND t.observation_source_value='organ__ontology_label' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [other_relative_with_pd] -> observation.observation_concept_id=4182334
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4182334,
    src.visit_date,
    32817,
    'other_relative_with_pd',
    (src."other_relative_with_pd")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."other_relative_with_pd" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4182334 AND t.observation_source_value='other_relative_with_pd' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [parkinsonism] -> observation.observation_concept_id=4126631  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4126631,
    src.visit_date,
    32817,
    'parkinsonism',
    (src."parkinsonism")::text,
    (src."parkinsonism")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."parkinsonism" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4126631 AND t.observation_source_value='parkinsonism' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [participant_id] -> observation.observation_concept_id=40768976  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40768976,
    src.visit_date,
    32817,
    'participant_id',
    (src."participant_id")::text,
    (src."participant_id")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."participant_id" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40768976 AND t.observation_source_value='participant_id' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [path_braak_nft] -> observation.observation_concept_id=3172933  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    3172933,
    src.visit_date,
    32817,
    'path_braak_nft',
    (src."path_braak_nft")::text,
    (src."path_braak_nft")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."path_braak_nft" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=3172933 AND t.observation_source_value='path_braak_nft' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [path_cerad] -> observation.observation_concept_id=3519134  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    3519134,
    src.visit_date,
    32817,
    'path_cerad',
    (src."path_cerad")::text,
    (src."path_cerad")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."path_cerad" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=3519134 AND t.observation_source_value='path_cerad' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [path_dlb_prob] -> observation.observation_concept_id=3188920  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    3188920,
    src.visit_date,
    32817,
    'path_dlb_prob',
    (src."path_dlb_prob")::text,
    (src."path_dlb_prob")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."path_dlb_prob" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=3188920 AND t.observation_source_value='path_dlb_prob' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [pd_medication_start_months_after_baseline] -> observation.observation_concept_id=4141652  [value_as_number (no explicit range)]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4141652,
    src.visit_date,
    32817,
    'pd_medication_start_months_after_baseline',
    (src."pd_medication_start_months_after_baseline")::text,
    CASE WHEN src."pd_medication_start_months_after_baseline" ~ '^-?[0-9]+(\.[0-9]+)?$' THEN src."pd_medication_start_months_after_baseline"::numeric END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."pd_medication_start_months_after_baseline" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4141652 AND t.observation_source_value='pd_medication_start_months_after_baseline' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [pdq39_01_doing_leisure_activity] -> observation.observation_concept_id=4116025  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4116025,
    src.visit_date,
    32817,
    'pdq39_01_doing_leisure_activity',
    (src."pdq39_01_doing_leisure_activity")::text,
    (src."pdq39_01_doing_leisure_activity")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."pdq39_01_doing_leisure_activity" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4116025 AND t.observation_source_value='pdq39_01_doing_leisure_activity' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [pdq39_04_walking_half_mile] -> observation.observation_concept_id=36714126  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    36714126,
    src.visit_date,
    32817,
    'pdq39_04_walking_half_mile',
    (src."pdq39_04_walking_half_mile")::text,
    (src."pdq39_04_walking_half_mile")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."pdq39_04_walking_half_mile" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=36714126 AND t.observation_source_value='pdq39_04_walking_half_mile' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [pdq39_05_walking_100_yards] -> observation.observation_concept_id=40764451  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40764451,
    src.visit_date,
    32817,
    'pdq39_05_walking_100_yards',
    (src."pdq39_05_walking_100_yards")::text,
    (src."pdq39_05_walking_100_yards")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."pdq39_05_walking_100_yards" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40764451 AND t.observation_source_value='pdq39_05_walking_100_yards' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [pdq39_06_getting_around_house] -> observation.observation_concept_id=4052960  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4052960,
    src.visit_date,
    32817,
    'pdq39_06_getting_around_house',
    (src."pdq39_06_getting_around_house")::text,
    (src."pdq39_06_getting_around_house")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."pdq39_06_getting_around_house" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4052960 AND t.observation_source_value='pdq39_06_getting_around_house' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [pdq39_07_getting_around_in_public] -> observation.observation_concept_id=42870053  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    42870053,
    src.visit_date,
    32817,
    'pdq39_07_getting_around_in_public',
    (src."pdq39_07_getting_around_in_public")::text,
    (src."pdq39_07_getting_around_in_public")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."pdq39_07_getting_around_in_public" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=42870053 AND t.observation_source_value='pdq39_07_getting_around_in_public' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [pdq39_09_worried_about_falling] -> observation.observation_concept_id=1616659  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    1616659,
    src.visit_date,
    32817,
    'pdq39_09_worried_about_falling',
    (src."pdq39_09_worried_about_falling")::text,
    (src."pdq39_09_worried_about_falling")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."pdq39_09_worried_about_falling" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=1616659 AND t.observation_source_value='pdq39_09_worried_about_falling' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [pdq39_10_confined_to_house] -> observation.observation_concept_id=4052962  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4052962,
    src.visit_date,
    32817,
    'pdq39_10_confined_to_house',
    (src."pdq39_10_confined_to_house")::text,
    (src."pdq39_10_confined_to_house")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."pdq39_10_confined_to_house" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4052962 AND t.observation_source_value='pdq39_10_confined_to_house' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [pdq39_12_dressing] -> observation.observation_concept_id=4110925  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4110925,
    src.visit_date,
    32817,
    'pdq39_12_dressing',
    (src."pdq39_12_dressing")::text,
    (src."pdq39_12_dressing")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."pdq39_12_dressing" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4110925 AND t.observation_source_value='pdq39_12_dressing' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [pdq39_13_buttons_and_shoelaces] -> observation.observation_concept_id=46235617  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    46235617,
    src.visit_date,
    32817,
    'pdq39_13_buttons_and_shoelaces',
    (src."pdq39_13_buttons_and_shoelaces")::text,
    (src."pdq39_13_buttons_and_shoelaces")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."pdq39_13_buttons_and_shoelaces" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=46235617 AND t.observation_source_value='pdq39_13_buttons_and_shoelaces' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [pdq39_14_writing] -> observation.observation_concept_id=4012111  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4012111,
    src.visit_date,
    32817,
    'pdq39_14_writing',
    (src."pdq39_14_writing")::text,
    (src."pdq39_14_writing")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."pdq39_14_writing" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4012111 AND t.observation_source_value='pdq39_14_writing' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [pdq39_15_cutting_food] -> observation.observation_concept_id=4004997  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4004997,
    src.visit_date,
    32817,
    'pdq39_15_cutting_food',
    (src."pdq39_15_cutting_food")::text,
    (src."pdq39_15_cutting_food")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."pdq39_15_cutting_food" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4004997 AND t.observation_source_value='pdq39_15_cutting_food' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [pdq39_16_spill_drink] -> observation.observation_concept_id=4139244  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4139244,
    src.visit_date,
    32817,
    'pdq39_16_spill_drink',
    (src."pdq39_16_spill_drink")::text,
    (src."pdq39_16_spill_drink")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."pdq39_16_spill_drink" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4139244 AND t.observation_source_value='pdq39_16_spill_drink' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [pdq39_17_depressed] -> observation.observation_concept_id=40546087  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40546087,
    src.visit_date,
    32817,
    'pdq39_17_depressed',
    (src."pdq39_17_depressed")::text,
    (src."pdq39_17_depressed")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."pdq39_17_depressed" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40546087 AND t.observation_source_value='pdq39_17_depressed' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [pdq39_20_angry] -> observation.observation_concept_id=4327815  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4327815,
    src.visit_date,
    32817,
    'pdq39_20_angry',
    (src."pdq39_20_angry")::text,
    (src."pdq39_20_angry")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."pdq39_20_angry" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4327815 AND t.observation_source_value='pdq39_20_angry' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [pdq39_21_anxious] -> observation.observation_concept_id=4117364  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4117364,
    src.visit_date,
    32817,
    'pdq39_21_anxious',
    (src."pdq39_21_anxious")::text,
    (src."pdq39_21_anxious")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."pdq39_21_anxious" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4117364 AND t.observation_source_value='pdq39_21_anxious' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [pdq39_22_worried_about_future] -> observation.observation_concept_id=1989000  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    1989000,
    src.visit_date,
    32817,
    'pdq39_22_worried_about_future',
    (src."pdq39_22_worried_about_future")::text,
    (src."pdq39_22_worried_about_future")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."pdq39_22_worried_about_future" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=1989000 AND t.observation_source_value='pdq39_22_worried_about_future' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [pdq39_24_avoid_eat_drink_in_public] -> observation.observation_concept_id=42868862  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    42868862,
    src.visit_date,
    32817,
    'pdq39_24_avoid_eat_drink_in_public',
    (src."pdq39_24_avoid_eat_drink_in_public")::text,
    (src."pdq39_24_avoid_eat_drink_in_public")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."pdq39_24_avoid_eat_drink_in_public" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=42868862 AND t.observation_source_value='pdq39_24_avoid_eat_drink_in_public' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [pdq39_25_embarassed_in_public] -> observation.observation_concept_id=40770700
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40770700,
    src.visit_date,
    32817,
    'pdq39_25_embarassed_in_public',
    (src."pdq39_25_embarassed_in_public")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."pdq39_25_embarassed_in_public" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40770700 AND t.observation_source_value='pdq39_25_embarassed_in_public' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [pdq39_26_worried_about_reactions] -> observation.observation_concept_id=1703891  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    1703891,
    src.visit_date,
    32817,
    'pdq39_26_worried_about_reactions',
    (src."pdq39_26_worried_about_reactions")::text,
    (src."pdq39_26_worried_about_reactions")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."pdq39_26_worried_about_reactions" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=1703891 AND t.observation_source_value='pdq39_26_worried_about_reactions' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [pdq39_27_close_personal_relations] -> observation.observation_concept_id=439664
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    439664,
    src.visit_date,
    32817,
    'pdq39_27_close_personal_relations',
    (src."pdq39_27_close_personal_relations")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."pdq39_27_close_personal_relations" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=439664 AND t.observation_source_value='pdq39_27_close_personal_relations' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [pdq39_28_support_from_spouse] -> observation.observation_concept_id=0
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    0,
    src.visit_date,
    32817,
    'pdq39_28_support_from_spouse',
    (src."pdq39_28_support_from_spouse")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."pdq39_28_support_from_spouse" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=0 AND t.observation_source_value='pdq39_28_support_from_spouse' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [pdq39_29_support_from_family] -> observation.observation_concept_id=45771438  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    45771438,
    src.visit_date,
    32817,
    'pdq39_29_support_from_family',
    (src."pdq39_29_support_from_family")::text,
    (src."pdq39_29_support_from_family")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."pdq39_29_support_from_family" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=45771438 AND t.observation_source_value='pdq39_29_support_from_family' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [pdq39_30_sleep_in_day] -> observation.observation_concept_id=4086495  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4086495,
    src.visit_date,
    32817,
    'pdq39_30_sleep_in_day',
    (src."pdq39_30_sleep_in_day")::text,
    (src."pdq39_30_sleep_in_day")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."pdq39_30_sleep_in_day" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4086495 AND t.observation_source_value='pdq39_30_sleep_in_day' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [pdq39_31_problem_with_concentration] -> observation.observation_concept_id=21494460  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    21494460,
    src.visit_date,
    32817,
    'pdq39_31_problem_with_concentration',
    (src."pdq39_31_problem_with_concentration")::text,
    (src."pdq39_31_problem_with_concentration")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."pdq39_31_problem_with_concentration" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=21494460 AND t.observation_source_value='pdq39_31_problem_with_concentration' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [pdq39_32_memory_is_failing] -> observation.observation_concept_id=4076654  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4076654,
    src.visit_date,
    32817,
    'pdq39_32_memory_is_failing',
    (src."pdq39_32_memory_is_failing")::text,
    (src."pdq39_32_memory_is_failing")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."pdq39_32_memory_is_failing" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4076654 AND t.observation_source_value='pdq39_32_memory_is_failing' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [pdq39_34_speaking] -> observation.observation_concept_id=4114720  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4114720,
    src.visit_date,
    32817,
    'pdq39_34_speaking',
    (src."pdq39_34_speaking")::text,
    (src."pdq39_34_speaking")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."pdq39_34_speaking" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4114720 AND t.observation_source_value='pdq39_34_speaking' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [pdq39_35_unable_to_communicate] -> observation.observation_concept_id=42869237  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    42869237,
    src.visit_date,
    32817,
    'pdq39_35_unable_to_communicate',
    (src."pdq39_35_unable_to_communicate")::text,
    (src."pdq39_35_unable_to_communicate")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."pdq39_35_unable_to_communicate" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=42869237 AND t.observation_source_value='pdq39_35_unable_to_communicate' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [pdq39_36_felt_ignored] -> observation.observation_concept_id=4112996  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4112996,
    src.visit_date,
    32817,
    'pdq39_36_felt_ignored',
    (src."pdq39_36_felt_ignored")::text,
    (src."pdq39_36_felt_ignored")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."pdq39_36_felt_ignored" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4112996 AND t.observation_source_value='pdq39_36_felt_ignored' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [pdq39_39_hot_or_cold] -> observation.observation_concept_id=4012122  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4012122,
    src.visit_date,
    32817,
    'pdq39_39_hot_or_cold',
    (src."pdq39_39_hot_or_cold")::text,
    (src."pdq39_39_hot_or_cold")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."pdq39_39_hot_or_cold" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4012122 AND t.observation_source_value='pdq39_39_hot_or_cold' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [pdq39_stigma_score] -> observation.observation_concept_id=40770510  [number in [0.0,100.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40770510,
    src.visit_date,
    32817,
    'pdq39_stigma_score',
    (src."pdq39_stigma_score")::text,
    CASE WHEN src."pdq39_stigma_score" ~ '^-?[0-9.]+$' AND src."pdq39_stigma_score"::numeric BETWEEN 0.0 AND 100.0 THEN src."pdq39_stigma_score"::numeric END,
    CASE WHEN src."pdq39_stigma_score" ~ '^-?[0-9]+$' AND NOT (src."pdq39_stigma_score"::numeric BETWEEN 0.0 AND 100.0) THEN src."pdq39_stigma_score"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."pdq39_stigma_score" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40770510 AND t.observation_source_value='pdq39_stigma_score' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [phase] -> observation.observation_concept_id=0  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    0,
    src.visit_date,
    32817,
    'phase',
    (src."phase")::text,
    (src."phase")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."phase" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=0 AND t.observation_source_value='phase' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [program] -> observation.observation_concept_id=42528934  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    42528934,
    src.visit_date,
    32817,
    'program',
    (src."program")::text,
    (src."program")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."program" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=42528934 AND t.observation_source_value='program' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [project] -> observation.observation_concept_id=0
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    0,
    src.visit_date,
    32817,
    'project',
    (src."project")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."project" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=0 AND t.observation_source_value='project' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [projid] -> observation.observation_concept_id=0
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    0,
    src.visit_date,
    32817,
    'projid',
    (src."projid")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."projid" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=0 AND t.observation_source_value='projid' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [psychosis] -> observation.observation_concept_id=436073
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    436073,
    src.visit_date,
    32817,
    'psychosis',
    (src."psychosis")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."psychosis" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=436073 AND t.observation_source_value='psychosis' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [race] -> observation.observation_concept_id=3046853  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    3046853,
    src.visit_date,
    32817,
    'race',
    (src."race")::text,
    (src."race")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."race" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=3046853 AND t.observation_source_value='race' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [rbd] -> observation.observation_concept_id=439007  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    439007,
    src.visit_date,
    32817,
    'rbd',
    (src."rbd")::text,
    (src."rbd")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."rbd" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=439007 AND t.observation_source_value='rbd' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [rbd01_vivid_dreams] -> observation.observation_concept_id=4092272
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4092272,
    src.visit_date,
    32817,
    'rbd01_vivid_dreams',
    (src."rbd01_vivid_dreams")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."rbd01_vivid_dreams" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4092272 AND t.observation_source_value='rbd01_vivid_dreams' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [rbd03_nocturnal_behaviour] -> observation.observation_concept_id=4229575  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4229575,
    src.visit_date,
    32817,
    'rbd03_nocturnal_behaviour',
    (src."rbd03_nocturnal_behaviour")::text,
    (src."rbd03_nocturnal_behaviour")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."rbd03_nocturnal_behaviour" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4229575 AND t.observation_source_value='rbd03_nocturnal_behaviour' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [rbd05_hurt_bed_partner] -> observation.observation_concept_id=40768319  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40768319,
    src.visit_date,
    32817,
    'rbd05_hurt_bed_partner',
    (src."rbd05_hurt_bed_partner")::text,
    (src."rbd05_hurt_bed_partner")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."rbd05_hurt_bed_partner" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40768319 AND t.observation_source_value='rbd05_hurt_bed_partner' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [rbd06_1_speaking_in_sleep] -> observation.observation_concept_id=4263778  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4263778,
    src.visit_date,
    32817,
    'rbd06_1_speaking_in_sleep',
    (src."rbd06_1_speaking_in_sleep")::text,
    (src."rbd06_1_speaking_in_sleep")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."rbd06_1_speaking_in_sleep" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4263778 AND t.observation_source_value='rbd06_1_speaking_in_sleep' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [rbd10_nervous_system_disease] -> observation.observation_concept_id=3046374  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    3046374,
    src.visit_date,
    32817,
    'rbd10_nervous_system_disease',
    (src."rbd10_nervous_system_disease")::text,
    (src."rbd10_nervous_system_disease")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."rbd10_nervous_system_disease" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=3046374 AND t.observation_source_value='rbd10_nervous_system_disease' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [rbd10a_stroke] -> observation.observation_concept_id=21491926
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    21491926,
    src.visit_date,
    32817,
    'rbd10a_stroke',
    (src."rbd10a_stroke")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."rbd10a_stroke" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=21491926 AND t.observation_source_value='rbd10a_stroke' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [rbd10b_head_trauma] -> observation.observation_concept_id=375415  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    375415,
    src.visit_date,
    32817,
    'rbd10b_head_trauma',
    (src."rbd10b_head_trauma")::text,
    (src."rbd10b_head_trauma")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."rbd10b_head_trauma" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=375415 AND t.observation_source_value='rbd10b_head_trauma' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [rbd10e_narcolepsy] -> observation.observation_concept_id=436100  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    436100,
    src.visit_date,
    32817,
    'rbd10e_narcolepsy',
    (src."rbd10e_narcolepsy")::text,
    (src."rbd10e_narcolepsy")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."rbd10e_narcolepsy" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=436100 AND t.observation_source_value='rbd10e_narcolepsy' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [rbd10g_epilepsy] -> observation.observation_concept_id=380378  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    380378,
    src.visit_date,
    32817,
    'rbd10g_epilepsy',
    (src."rbd10g_epilepsy")::text,
    (src."rbd10g_epilepsy")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."rbd10g_epilepsy" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=380378 AND t.observation_source_value='rbd10g_epilepsy' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [rbd10h_brain_inflammatory_disease] -> observation.observation_concept_id=378143  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    378143,
    src.visit_date,
    32817,
    'rbd10h_brain_inflammatory_disease',
    (src."rbd10h_brain_inflammatory_disease")::text,
    (src."rbd10h_brain_inflammatory_disease")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."rbd10h_brain_inflammatory_disease" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=378143 AND t.observation_source_value='rbd10h_brain_inflammatory_disease' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [rbd10i_other] -> observation.observation_concept_id=1384430  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    1384430,
    src.visit_date,
    32817,
    'rbd10i_other',
    (src."rbd10i_other")::text,
    (src."rbd10i_other")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."rbd10i_other" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=1384430 AND t.observation_source_value='rbd10i_other' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [ref1_left_reference] -> observation.observation_concept_id=0  [number in [0.0,1.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    0,
    src.visit_date,
    32817,
    'ref1_left_reference',
    (src."ref1_left_reference")::text,
    CASE WHEN src."ref1_left_reference" ~ '^-?[0-9.]+$' AND src."ref1_left_reference"::numeric BETWEEN 0.0 AND 1.0 THEN src."ref1_left_reference"::numeric END,
    CASE WHEN src."ref1_left_reference" ~ '^-?[0-9]+$' AND NOT (src."ref1_left_reference"::numeric BETWEEN 0.0 AND 1.0) THEN src."ref1_left_reference"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."ref1_left_reference" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=0 AND t.observation_source_value='ref1_left_reference' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [sample] -> observation.observation_concept_id=4163138  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4163138,
    src.visit_date,
    32817,
    'sample',
    (src."sample")::text,
    (src."sample")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."sample" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4163138 AND t.observation_source_value='sample' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [sample_id] -> observation.observation_concept_id=4163138  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4163138,
    src.visit_date,
    32817,
    'sample_id',
    (src."sample_id")::text,
    (src."sample_id")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."sample_id" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4163138 AND t.observation_source_value='sample_id' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [samplingAge] -> observation.observation_concept_id=3034297  [value_as_number (no explicit range)] [+unit 9448]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, unit_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    3034297,
    src.visit_date,
    32817,
    'samplingAge',
    (src."samplingAge")::text,
    CASE WHEN src."samplingAge" ~ '^-?[0-9]+(\.[0-9]+)?$' THEN src."samplingAge"::numeric END,
    9448,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."samplingAge" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=3034297 AND t.observation_source_value='samplingAge' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [samplingDate] -> observation.observation_concept_id=3045429  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    3045429,
    src.visit_date,
    32817,
    'samplingDate',
    (src."samplingDate")::text,
    (src."samplingDate")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."samplingDate" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=3045429 AND t.observation_source_value='samplingDate' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [self_reported_ethnicity_ontology_term_id] -> observation.observation_concept_id=4271761
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4271761,
    src.visit_date,
    32817,
    'self_reported_ethnicity_ontology_term_id',
    (src."self_reported_ethnicity_ontology_term_id")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."self_reported_ethnicity_ontology_term_id" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4271761 AND t.observation_source_value='self_reported_ethnicity_ontology_term_id' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [sex_ontology_term_id] -> observation.observation_concept_id=46235213  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    46235213,
    src.visit_date,
    32817,
    'sex_ontology_term_id',
    (src."sex_ontology_term_id")::text,
    (src."sex_ontology_term_id")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."sex_ontology_term_id" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=46235213 AND t.observation_source_value='sex_ontology_term_id' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [smoke_exposure_home] -> observation.observation_concept_id=40766593  [number in [0.0,15.0]; out-of-range int -> value_as_concept_id] [+unit 8512]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, unit_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40766593,
    src.visit_date,
    32817,
    'smoke_exposure_home',
    (src."smoke_exposure_home")::text,
    CASE WHEN src."smoke_exposure_home" ~ '^-?[0-9.]+$' AND src."smoke_exposure_home"::numeric BETWEEN 0.0 AND 15.0 THEN src."smoke_exposure_home"::numeric END,
    CASE WHEN src."smoke_exposure_home" ~ '^-?[0-9]+$' AND NOT (src."smoke_exposure_home"::numeric BETWEEN 0.0 AND 15.0) THEN src."smoke_exposure_home"::int END,
    8512,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."smoke_exposure_home" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40766593 AND t.observation_source_value='smoke_exposure_home' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [smoke_exposure_other_areas] -> observation.observation_concept_id=40766591  [number in [0.0,10.0]; out-of-range int -> value_as_concept_id] [+unit 8512]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, unit_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40766591,
    src.visit_date,
    32817,
    'smoke_exposure_other_areas',
    (src."smoke_exposure_other_areas")::text,
    CASE WHEN src."smoke_exposure_other_areas" ~ '^-?[0-9.]+$' AND src."smoke_exposure_other_areas"::numeric BETWEEN 0.0 AND 10.0 THEN src."smoke_exposure_other_areas"::numeric END,
    CASE WHEN src."smoke_exposure_other_areas" ~ '^-?[0-9]+$' AND NOT (src."smoke_exposure_other_areas"::numeric BETWEEN 0.0 AND 10.0) THEN src."smoke_exposure_other_areas"::int END,
    8512,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."smoke_exposure_other_areas" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40766591 AND t.observation_source_value='smoke_exposure_other_areas' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [smoke_exposure_work] -> observation.observation_concept_id=40766593  [number in [0.0,10.0]; out-of-range int -> value_as_concept_id] [+unit 8512]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, unit_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40766593,
    src.visit_date,
    32817,
    'smoke_exposure_work',
    (src."smoke_exposure_work")::text,
    CASE WHEN src."smoke_exposure_work" ~ '^-?[0-9.]+$' AND src."smoke_exposure_work"::numeric BETWEEN 0.0 AND 10.0 THEN src."smoke_exposure_work"::numeric END,
    CASE WHEN src."smoke_exposure_work" ~ '^-?[0-9]+$' AND NOT (src."smoke_exposure_work"::numeric BETWEEN 0.0 AND 10.0) THEN src."smoke_exposure_work"::int END,
    8512,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."smoke_exposure_work" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40766593 AND t.observation_source_value='smoke_exposure_work' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [species] -> observation.observation_concept_id=4259632  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4259632,
    src.visit_date,
    32817,
    'species',
    (src."species")::text,
    (src."species")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."species" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4259632 AND t.observation_source_value='species' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [specimenIdSource] -> observation.observation_concept_id=0  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    0,
    src.visit_date,
    32817,
    'specimenIdSource',
    (src."specimenIdSource")::text,
    (src."specimenIdSource")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."specimenIdSource" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=0 AND t.observation_source_value='specimenIdSource' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [specimenMetadataSource] -> observation.observation_concept_id=0  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    0,
    src.visit_date,
    32817,
    'specimenMetadataSource',
    (src."specimenMetadataSource")::text,
    (src."specimenMetadataSource")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."specimenMetadataSource" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=0 AND t.observation_source_value='specimenMetadataSource' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [study_arm] -> observation.observation_concept_id=618771  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    618771,
    src.visit_date,
    32817,
    'study_arm',
    (src."study_arm")::text,
    (src."study_arm")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."study_arm" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=618771 AND t.observation_source_value='study_arm' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [tissue__ontology_label] -> observation.observation_concept_id=596879  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    596879,
    src.visit_date,
    32817,
    'tissue__ontology_label',
    (src."tissue__ontology_label")::text,
    (src."tissue__ontology_label")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."tissue__ontology_label" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=596879 AND t.observation_source_value='tissue__ontology_label' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [tobacco_current_use] -> observation.observation_concept_id=40766306  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40766306,
    src.visit_date,
    32817,
    'tobacco_current_use',
    (src."tobacco_current_use")::text,
    (src."tobacco_current_use")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."tobacco_current_use" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40766306 AND t.observation_source_value='tobacco_current_use' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [tobacco_ever_used] -> observation.observation_concept_id=44786669  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    44786669,
    src.visit_date,
    32817,
    'tobacco_ever_used',
    (src."tobacco_ever_used")::text,
    (src."tobacco_ever_used")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."tobacco_ever_used" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=44786669 AND t.observation_source_value='tobacco_ever_used' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [tobacco_prior_use] -> observation.observation_concept_id=3012697  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    3012697,
    src.visit_date,
    32817,
    'tobacco_prior_use',
    (src."tobacco_prior_use")::text,
    (src."tobacco_prior_use")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."tobacco_prior_use" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=3012697 AND t.observation_source_value='tobacco_prior_use' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [tobacco_product_type] -> observation.observation_concept_id=37172639  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    37172639,
    src.visit_date,
    32817,
    'tobacco_product_type',
    (src."tobacco_product_type")::text,
    (src."tobacco_product_type")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."tobacco_product_type" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=37172639 AND t.observation_source_value='tobacco_product_type' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [tobacco_recent_use] -> observation.observation_concept_id=44786481  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    44786481,
    src.visit_date,
    32817,
    'tobacco_recent_use',
    (src."tobacco_recent_use")::text,
    (src."tobacco_recent_use")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."tobacco_recent_use" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=44786481 AND t.observation_source_value='tobacco_recent_use' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd118_speech] -> observation.observation_concept_id=40768722  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40768722,
    src.visit_date,
    32817,
    'upd118_speech',
    (src."upd118_speech")::text,
    CASE WHEN src."upd118_speech" ~ '^-?[0-9.]+$' AND src."upd118_speech"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd118_speech"::numeric END,
    CASE WHEN src."upd118_speech" ~ '^-?[0-9]+$' AND NOT (src."upd118_speech"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd118_speech"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd118_speech" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40768722 AND t.observation_source_value='upd118_speech' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd119_facial_expression] -> observation.observation_concept_id=40768723  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40768723,
    src.visit_date,
    32817,
    'upd119_facial_expression',
    (src."upd119_facial_expression")::text,
    CASE WHEN src."upd119_facial_expression" ~ '^-?[0-9.]+$' AND src."upd119_facial_expression"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd119_facial_expression"::numeric END,
    CASE WHEN src."upd119_facial_expression" ~ '^-?[0-9]+$' AND NOT (src."upd119_facial_expression"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd119_facial_expression"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd119_facial_expression" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40768723 AND t.observation_source_value='upd119_facial_expression' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd123a_finger_taps_right] -> observation.observation_concept_id=40768384  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40768384,
    src.visit_date,
    32817,
    'upd123a_finger_taps_right',
    (src."upd123a_finger_taps_right")::text,
    CASE WHEN src."upd123a_finger_taps_right" ~ '^-?[0-9.]+$' AND src."upd123a_finger_taps_right"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd123a_finger_taps_right"::numeric END,
    CASE WHEN src."upd123a_finger_taps_right" ~ '^-?[0-9]+$' AND NOT (src."upd123a_finger_taps_right"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd123a_finger_taps_right"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd123a_finger_taps_right" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40768384 AND t.observation_source_value='upd123a_finger_taps_right' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd123b_finger_taps_left] -> observation.observation_concept_id=40768385  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40768385,
    src.visit_date,
    32817,
    'upd123b_finger_taps_left',
    (src."upd123b_finger_taps_left")::text,
    CASE WHEN src."upd123b_finger_taps_left" ~ '^-?[0-9.]+$' AND src."upd123b_finger_taps_left"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd123b_finger_taps_left"::numeric END,
    CASE WHEN src."upd123b_finger_taps_left" ~ '^-?[0-9]+$' AND NOT (src."upd123b_finger_taps_left"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd123b_finger_taps_left"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd123b_finger_taps_left" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40768385 AND t.observation_source_value='upd123b_finger_taps_left' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd124a_hand_grips_right] -> observation.observation_concept_id=0  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    0,
    src.visit_date,
    32817,
    'upd124a_hand_grips_right',
    (src."upd124a_hand_grips_right")::text,
    CASE WHEN src."upd124a_hand_grips_right" ~ '^-?[0-9.]+$' AND src."upd124a_hand_grips_right"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd124a_hand_grips_right"::numeric END,
    CASE WHEN src."upd124a_hand_grips_right" ~ '^-?[0-9]+$' AND NOT (src."upd124a_hand_grips_right"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd124a_hand_grips_right"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd124a_hand_grips_right" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=0 AND t.observation_source_value='upd124a_hand_grips_right' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd124b_hand_grips_left] -> observation.observation_concept_id=40768387  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40768387,
    src.visit_date,
    32817,
    'upd124b_hand_grips_left',
    (src."upd124b_hand_grips_left")::text,
    CASE WHEN src."upd124b_hand_grips_left" ~ '^-?[0-9.]+$' AND src."upd124b_hand_grips_left"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd124b_hand_grips_left"::numeric END,
    CASE WHEN src."upd124b_hand_grips_left" ~ '^-?[0-9]+$' AND NOT (src."upd124b_hand_grips_left"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd124b_hand_grips_left"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd124b_hand_grips_left" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40768387 AND t.observation_source_value='upd124b_hand_grips_left' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd125a_hand_pronate_supinate_rt] -> observation.observation_concept_id=40768388
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40768388,
    src.visit_date,
    32817,
    'upd125a_hand_pronate_supinate_rt',
    (src."upd125a_hand_pronate_supinate_rt")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd125a_hand_pronate_supinate_rt" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40768388 AND t.observation_source_value='upd125a_hand_pronate_supinate_rt' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd125b_hand_pronate_supinate_lt] -> observation.observation_concept_id=40768389  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40768389,
    src.visit_date,
    32817,
    'upd125b_hand_pronate_supinate_lt',
    (src."upd125b_hand_pronate_supinate_lt")::text,
    CASE WHEN src."upd125b_hand_pronate_supinate_lt" ~ '^-?[0-9.]+$' AND src."upd125b_hand_pronate_supinate_lt"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd125b_hand_pronate_supinate_lt"::numeric END,
    CASE WHEN src."upd125b_hand_pronate_supinate_lt" ~ '^-?[0-9]+$' AND NOT (src."upd125b_hand_pronate_supinate_lt"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd125b_hand_pronate_supinate_lt"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd125b_hand_pronate_supinate_lt" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40768389 AND t.observation_source_value='upd125b_hand_pronate_supinate_lt' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd126a_leg_agility_rt] -> observation.observation_concept_id=40768390  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40768390,
    src.visit_date,
    32817,
    'upd126a_leg_agility_rt',
    (src."upd126a_leg_agility_rt")::text,
    CASE WHEN src."upd126a_leg_agility_rt" ~ '^-?[0-9.]+$' AND src."upd126a_leg_agility_rt"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd126a_leg_agility_rt"::numeric END,
    CASE WHEN src."upd126a_leg_agility_rt" ~ '^-?[0-9]+$' AND NOT (src."upd126a_leg_agility_rt"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd126a_leg_agility_rt"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd126a_leg_agility_rt" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40768390 AND t.observation_source_value='upd126a_leg_agility_rt' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd126b_leg_agility_lt] -> observation.observation_concept_id=40768391  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40768391,
    src.visit_date,
    32817,
    'upd126b_leg_agility_lt',
    (src."upd126b_leg_agility_lt")::text,
    CASE WHEN src."upd126b_leg_agility_lt" ~ '^-?[0-9.]+$' AND src."upd126b_leg_agility_lt"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd126b_leg_agility_lt"::numeric END,
    CASE WHEN src."upd126b_leg_agility_lt" ~ '^-?[0-9]+$' AND NOT (src."upd126b_leg_agility_lt"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd126b_leg_agility_lt"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd126b_leg_agility_lt" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40768391 AND t.observation_source_value='upd126b_leg_agility_lt' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd127_arising_from_chair] -> observation.observation_concept_id=40768392  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40768392,
    src.visit_date,
    32817,
    'upd127_arising_from_chair',
    (src."upd127_arising_from_chair")::text,
    CASE WHEN src."upd127_arising_from_chair" ~ '^-?[0-9.]+$' AND src."upd127_arising_from_chair"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd127_arising_from_chair"::numeric END,
    CASE WHEN src."upd127_arising_from_chair" ~ '^-?[0-9]+$' AND NOT (src."upd127_arising_from_chair"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd127_arising_from_chair"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd127_arising_from_chair" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40768392 AND t.observation_source_value='upd127_arising_from_chair' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd128_posture] -> observation.observation_concept_id=40768393  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40768393,
    src.visit_date,
    32817,
    'upd128_posture',
    (src."upd128_posture")::text,
    CASE WHEN src."upd128_posture" ~ '^-?[0-9.]+$' AND src."upd128_posture"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd128_posture"::numeric END,
    CASE WHEN src."upd128_posture" ~ '^-?[0-9]+$' AND NOT (src."upd128_posture"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd128_posture"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd128_posture" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40768393 AND t.observation_source_value='upd128_posture' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd129_gait] -> observation.observation_concept_id=40768394  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40768394,
    src.visit_date,
    32817,
    'upd129_gait',
    (src."upd129_gait")::text,
    CASE WHEN src."upd129_gait" ~ '^-?[0-9.]+$' AND src."upd129_gait"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd129_gait"::numeric END,
    CASE WHEN src."upd129_gait" ~ '^-?[0-9]+$' AND NOT (src."upd129_gait"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd129_gait"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd129_gait" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40768394 AND t.observation_source_value='upd129_gait' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd130_postural_stability] -> observation.observation_concept_id=40768395  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40768395,
    src.visit_date,
    32817,
    'upd130_postural_stability',
    (src."upd130_postural_stability")::text,
    CASE WHEN src."upd130_postural_stability" ~ '^-?[0-9.]+$' AND src."upd130_postural_stability"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd130_postural_stability"::numeric END,
    CASE WHEN src."upd130_postural_stability" ~ '^-?[0-9]+$' AND NOT (src."upd130_postural_stability"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd130_postural_stability"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd130_postural_stability" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40768395 AND t.observation_source_value='upd130_postural_stability' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd131_body_bradykinesia] -> observation.observation_concept_id=40768499  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40768499,
    src.visit_date,
    32817,
    'upd131_body_bradykinesia',
    (src."upd131_body_bradykinesia")::text,
    CASE WHEN src."upd131_body_bradykinesia" ~ '^-?[0-9.]+$' AND src."upd131_body_bradykinesia"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd131_body_bradykinesia"::numeric END,
    CASE WHEN src."upd131_body_bradykinesia" ~ '^-?[0-9]+$' AND NOT (src."upd131_body_bradykinesia"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd131_body_bradykinesia"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd131_body_bradykinesia" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40768499 AND t.observation_source_value='upd131_body_bradykinesia' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd132_dyskinesias_duration] -> observation.observation_concept_id=46236393  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    46236393,
    src.visit_date,
    32817,
    'upd132_dyskinesias_duration',
    (src."upd132_dyskinesias_duration")::text,
    CASE WHEN src."upd132_dyskinesias_duration" ~ '^-?[0-9.]+$' AND src."upd132_dyskinesias_duration"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd132_dyskinesias_duration"::numeric END,
    CASE WHEN src."upd132_dyskinesias_duration" ~ '^-?[0-9]+$' AND NOT (src."upd132_dyskinesias_duration"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd132_dyskinesias_duration"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd132_dyskinesias_duration" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=46236393 AND t.observation_source_value='upd132_dyskinesias_duration' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd133_dyskinesias_disability] -> observation.observation_concept_id=46236394  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    46236394,
    src.visit_date,
    32817,
    'upd133_dyskinesias_disability',
    (src."upd133_dyskinesias_disability")::text,
    CASE WHEN src."upd133_dyskinesias_disability" ~ '^-?[0-9.]+$' AND src."upd133_dyskinesias_disability"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd133_dyskinesias_disability"::numeric END,
    CASE WHEN src."upd133_dyskinesias_disability" ~ '^-?[0-9]+$' AND NOT (src."upd133_dyskinesias_disability"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd133_dyskinesias_disability"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd133_dyskinesias_disability" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=46236394 AND t.observation_source_value='upd133_dyskinesias_disability' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd134_dyskinesias_painful] -> observation.observation_concept_id=46236395  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    46236395,
    src.visit_date,
    32817,
    'upd134_dyskinesias_painful',
    (src."upd134_dyskinesias_painful")::text,
    CASE WHEN src."upd134_dyskinesias_painful" ~ '^-?[0-9.]+$' AND src."upd134_dyskinesias_painful"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd134_dyskinesias_painful"::numeric END,
    CASE WHEN src."upd134_dyskinesias_painful" ~ '^-?[0-9]+$' AND NOT (src."upd134_dyskinesias_painful"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd134_dyskinesias_painful"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd134_dyskinesias_painful" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=46236395 AND t.observation_source_value='upd134_dyskinesias_painful' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd135_dyskinesias_dystonia] -> observation.observation_concept_id=46236396  [number in [0.0,1.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    46236396,
    src.visit_date,
    32817,
    'upd135_dyskinesias_dystonia',
    (src."upd135_dyskinesias_dystonia")::text,
    CASE WHEN src."upd135_dyskinesias_dystonia" ~ '^-?[0-9.]+$' AND src."upd135_dyskinesias_dystonia"::numeric BETWEEN 0.0 AND 1.0 THEN src."upd135_dyskinesias_dystonia"::numeric END,
    CASE WHEN src."upd135_dyskinesias_dystonia" ~ '^-?[0-9]+$' AND NOT (src."upd135_dyskinesias_dystonia"::numeric BETWEEN 0.0 AND 1.0) THEN src."upd135_dyskinesias_dystonia"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd135_dyskinesias_dystonia" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=46236396 AND t.observation_source_value='upd135_dyskinesias_dystonia' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd136_off_periods_predictable] -> observation.observation_concept_id=46236397  [number in [0.0,1.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    46236397,
    src.visit_date,
    32817,
    'upd136_off_periods_predictable',
    (src."upd136_off_periods_predictable")::text,
    CASE WHEN src."upd136_off_periods_predictable" ~ '^-?[0-9.]+$' AND src."upd136_off_periods_predictable"::numeric BETWEEN 0.0 AND 1.0 THEN src."upd136_off_periods_predictable"::numeric END,
    CASE WHEN src."upd136_off_periods_predictable" ~ '^-?[0-9]+$' AND NOT (src."upd136_off_periods_predictable"::numeric BETWEEN 0.0 AND 1.0) THEN src."upd136_off_periods_predictable"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd136_off_periods_predictable" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=46236397 AND t.observation_source_value='upd136_off_periods_predictable' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd137_off_periods_unpredictable] -> observation.observation_concept_id=46236398  [number in [0.0,1.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    46236398,
    src.visit_date,
    32817,
    'upd137_off_periods_unpredictable',
    (src."upd137_off_periods_unpredictable")::text,
    CASE WHEN src."upd137_off_periods_unpredictable" ~ '^-?[0-9.]+$' AND src."upd137_off_periods_unpredictable"::numeric BETWEEN 0.0 AND 1.0 THEN src."upd137_off_periods_unpredictable"::numeric END,
    CASE WHEN src."upd137_off_periods_unpredictable" ~ '^-?[0-9]+$' AND NOT (src."upd137_off_periods_unpredictable"::numeric BETWEEN 0.0 AND 1.0) THEN src."upd137_off_periods_unpredictable"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd137_off_periods_unpredictable" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=46236398 AND t.observation_source_value='upd137_off_periods_unpredictable' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd138_off_periods_sudden] -> observation.observation_concept_id=46236399  [number in [0.0,1.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    46236399,
    src.visit_date,
    32817,
    'upd138_off_periods_sudden',
    (src."upd138_off_periods_sudden")::text,
    CASE WHEN src."upd138_off_periods_sudden" ~ '^-?[0-9.]+$' AND src."upd138_off_periods_sudden"::numeric BETWEEN 0.0 AND 1.0 THEN src."upd138_off_periods_sudden"::numeric END,
    CASE WHEN src."upd138_off_periods_sudden" ~ '^-?[0-9]+$' AND NOT (src."upd138_off_periods_sudden"::numeric BETWEEN 0.0 AND 1.0) THEN src."upd138_off_periods_sudden"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd138_off_periods_sudden" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=46236399 AND t.observation_source_value='upd138_off_periods_sudden' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd139_clin_fluctu_off_periods] -> observation.observation_concept_id=46236400  [number in [0.0,4.0]; out-of-range int -> value_as_concept_id] [+unit 8512]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, unit_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    46236400,
    src.visit_date,
    32817,
    'upd139_clin_fluctu_off_periods',
    (src."upd139_clin_fluctu_off_periods")::text,
    CASE WHEN src."upd139_clin_fluctu_off_periods" ~ '^-?[0-9.]+$' AND src."upd139_clin_fluctu_off_periods"::numeric BETWEEN 0.0 AND 4.0 THEN src."upd139_clin_fluctu_off_periods"::numeric END,
    CASE WHEN src."upd139_clin_fluctu_off_periods" ~ '^-?[0-9]+$' AND NOT (src."upd139_clin_fluctu_off_periods"::numeric BETWEEN 0.0 AND 4.0) THEN src."upd139_clin_fluctu_off_periods"::int END,
    8512,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd139_clin_fluctu_off_periods" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=46236400 AND t.observation_source_value='upd139_clin_fluctu_off_periods' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd140_anorexia_nausea_vomit] -> observation.observation_concept_id=46236401  [number in [0.0,1.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    46236401,
    src.visit_date,
    32817,
    'upd140_anorexia_nausea_vomit',
    (src."upd140_anorexia_nausea_vomit")::text,
    CASE WHEN src."upd140_anorexia_nausea_vomit" ~ '^-?[0-9.]+$' AND src."upd140_anorexia_nausea_vomit"::numeric BETWEEN 0.0 AND 1.0 THEN src."upd140_anorexia_nausea_vomit"::numeric END,
    CASE WHEN src."upd140_anorexia_nausea_vomit" ~ '^-?[0-9]+$' AND NOT (src."upd140_anorexia_nausea_vomit"::numeric BETWEEN 0.0 AND 1.0) THEN src."upd140_anorexia_nausea_vomit"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd140_anorexia_nausea_vomit" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=46236401 AND t.observation_source_value='upd140_anorexia_nausea_vomit' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd141_sleep_disturbances] -> observation.observation_concept_id=46236402  [number in [0.0,1.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    46236402,
    src.visit_date,
    32817,
    'upd141_sleep_disturbances',
    (src."upd141_sleep_disturbances")::text,
    CASE WHEN src."upd141_sleep_disturbances" ~ '^-?[0-9.]+$' AND src."upd141_sleep_disturbances"::numeric BETWEEN 0.0 AND 1.0 THEN src."upd141_sleep_disturbances"::numeric END,
    CASE WHEN src."upd141_sleep_disturbances" ~ '^-?[0-9]+$' AND NOT (src."upd141_sleep_disturbances"::numeric BETWEEN 0.0 AND 1.0) THEN src."upd141_sleep_disturbances"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd141_sleep_disturbances" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=46236402 AND t.observation_source_value='upd141_sleep_disturbances' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd143_mod_hoehn_and_yahr_stage] -> observation.observation_concept_id=46236404  [number in [0.0,5.0]; out-of-range int -> value_as_concept_id]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_number, value_as_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    46236404,
    src.visit_date,
    32817,
    'upd143_mod_hoehn_and_yahr_stage',
    (src."upd143_mod_hoehn_and_yahr_stage")::text,
    CASE WHEN src."upd143_mod_hoehn_and_yahr_stage" ~ '^-?[0-9.]+$' AND src."upd143_mod_hoehn_and_yahr_stage"::numeric BETWEEN 0.0 AND 5.0 THEN src."upd143_mod_hoehn_and_yahr_stage"::numeric END,
    CASE WHEN src."upd143_mod_hoehn_and_yahr_stage" ~ '^-?[0-9]+$' AND NOT (src."upd143_mod_hoehn_and_yahr_stage"::numeric BETWEEN 0.0 AND 5.0) THEN src."upd143_mod_hoehn_and_yahr_stage"::int END,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd143_mod_hoehn_and_yahr_stage" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=46236404 AND t.observation_source_value='upd143_mod_hoehn_and_yahr_stage' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2107_pat_quest_sleep_problems] -> observation.observation_concept_id=46236402  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    46236402,
    src.visit_date,
    32817,
    'upd2107_pat_quest_sleep_problems',
    (src."upd2107_pat_quest_sleep_problems")::text,
    (src."upd2107_pat_quest_sleep_problems")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2107_pat_quest_sleep_problems" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=46236402 AND t.observation_source_value='upd2107_pat_quest_sleep_problems' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2108_pat_quest_daytime_sleepiness] -> observation.observation_concept_id=0
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    0,
    src.visit_date,
    32817,
    'upd2108_pat_quest_daytime_sleepiness',
    (src."upd2108_pat_quest_daytime_sleepiness")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2108_pat_quest_daytime_sleepiness" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=0 AND t.observation_source_value='upd2108_pat_quest_daytime_sleepiness' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2201_speech] -> observation.observation_concept_id=40768722  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40768722,
    src.visit_date,
    32817,
    'upd2201_speech',
    (src."upd2201_speech")::text,
    (src."upd2201_speech")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2201_speech" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40768722 AND t.observation_source_value='upd2201_speech' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2301_speech_problems] -> observation.observation_concept_id=40768722  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40768722,
    src.visit_date,
    32817,
    'upd2301_speech_problems',
    (src."upd2301_speech_problems")::text,
    (src."upd2301_speech_problems")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2301_speech_problems" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40768722 AND t.observation_source_value='upd2301_speech_problems' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2302_facial_expression] -> observation.observation_concept_id=40768723  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40768723,
    src.visit_date,
    32817,
    'upd2302_facial_expression',
    (src."upd2302_facial_expression")::text,
    (src."upd2302_facial_expression")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2302_facial_expression" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40768723 AND t.observation_source_value='upd2302_facial_expression' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2304a_right_finger_tapping] -> observation.observation_concept_id=40768384  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40768384,
    src.visit_date,
    32817,
    'upd2304a_right_finger_tapping',
    (src."upd2304a_right_finger_tapping")::text,
    (src."upd2304a_right_finger_tapping")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2304a_right_finger_tapping" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40768384 AND t.observation_source_value='upd2304a_right_finger_tapping' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2304b_left_finger_tapping] -> observation.observation_concept_id=40768385  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40768385,
    src.visit_date,
    32817,
    'upd2304b_left_finger_tapping',
    (src."upd2304b_left_finger_tapping")::text,
    (src."upd2304b_left_finger_tapping")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2304b_left_finger_tapping" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40768385 AND t.observation_source_value='upd2304b_left_finger_tapping' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2305a_right_hand_movements] -> observation.observation_concept_id=40768386  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40768386,
    src.visit_date,
    32817,
    'upd2305a_right_hand_movements',
    (src."upd2305a_right_hand_movements")::text,
    (src."upd2305a_right_hand_movements")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2305a_right_hand_movements" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40768386 AND t.observation_source_value='upd2305a_right_hand_movements' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2305b_left_hand_movements] -> observation.observation_concept_id=40768387
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40768387,
    src.visit_date,
    32817,
    'upd2305b_left_hand_movements',
    (src."upd2305b_left_hand_movements")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2305b_left_hand_movements" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40768387 AND t.observation_source_value='upd2305b_left_hand_movements' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2306a_pron_sup_movement_right_hand] -> observation.observation_concept_id=40768388
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40768388,
    src.visit_date,
    32817,
    'upd2306a_pron_sup_movement_right_hand',
    (src."upd2306a_pron_sup_movement_right_hand")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2306a_pron_sup_movement_right_hand" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40768388 AND t.observation_source_value='upd2306a_pron_sup_movement_right_hand' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2306b_pron_sup_movement_left_hand] -> observation.observation_concept_id=40768330  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40768330,
    src.visit_date,
    32817,
    'upd2306b_pron_sup_movement_left_hand',
    (src."upd2306b_pron_sup_movement_left_hand")::text,
    (src."upd2306b_pron_sup_movement_left_hand")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2306b_pron_sup_movement_left_hand" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40768330 AND t.observation_source_value='upd2306b_pron_sup_movement_left_hand' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2308a_right_leg_agility] -> observation.observation_concept_id=40768390  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40768390,
    src.visit_date,
    32817,
    'upd2308a_right_leg_agility',
    (src."upd2308a_right_leg_agility")::text,
    (src."upd2308a_right_leg_agility")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2308a_right_leg_agility" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40768390 AND t.observation_source_value='upd2308a_right_leg_agility' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2308b_left_leg_agility] -> observation.observation_concept_id=40768391  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40768391,
    src.visit_date,
    32817,
    'upd2308b_left_leg_agility',
    (src."upd2308b_left_leg_agility")::text,
    (src."upd2308b_left_leg_agility")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2308b_left_leg_agility" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40768391 AND t.observation_source_value='upd2308b_left_leg_agility' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2309_arising_from_chair] -> observation.observation_concept_id=40768392  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40768392,
    src.visit_date,
    32817,
    'upd2309_arising_from_chair',
    (src."upd2309_arising_from_chair")::text,
    (src."upd2309_arising_from_chair")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2309_arising_from_chair" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40768392 AND t.observation_source_value='upd2309_arising_from_chair' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2310_gait] -> observation.observation_concept_id=40768394  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40768394,
    src.visit_date,
    32817,
    'upd2310_gait',
    (src."upd2310_gait")::text,
    (src."upd2310_gait")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2310_gait" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40768394 AND t.observation_source_value='upd2310_gait' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2312_postural_stability] -> observation.observation_concept_id=40768395  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40768395,
    src.visit_date,
    32817,
    'upd2312_postural_stability',
    (src."upd2312_postural_stability")::text,
    (src."upd2312_postural_stability")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2312_postural_stability" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40768395 AND t.observation_source_value='upd2312_postural_stability' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2313_posture] -> observation.observation_concept_id=40768393  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40768393,
    src.visit_date,
    32817,
    'upd2313_posture',
    (src."upd2313_posture")::text,
    (src."upd2313_posture")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2313_posture" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40768393 AND t.observation_source_value='upd2313_posture' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2314_body_bradykinesia] -> observation.observation_concept_id=40768499  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40768499,
    src.visit_date,
    32817,
    'upd2314_body_bradykinesia',
    (src."upd2314_body_bradykinesia")::text,
    (src."upd2314_body_bradykinesia")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2314_body_bradykinesia" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40768499 AND t.observation_source_value='upd2314_body_bradykinesia' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2401_time_spent_with_dyskinesias] -> observation.observation_concept_id=46236393  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    46236393,
    src.visit_date,
    32817,
    'upd2401_time_spent_with_dyskinesias',
    (src."upd2401_time_spent_with_dyskinesias")::text,
    (src."upd2401_time_spent_with_dyskinesias")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2401_time_spent_with_dyskinesias" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=46236393 AND t.observation_source_value='upd2401_time_spent_with_dyskinesias' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2402_functional_impact_of_dyskinesias] -> observation.observation_concept_id=46236394
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    46236394,
    src.visit_date,
    32817,
    'upd2402_functional_impact_of_dyskinesias',
    (src."upd2402_functional_impact_of_dyskinesias")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2402_functional_impact_of_dyskinesias" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=46236394 AND t.observation_source_value='upd2402_functional_impact_of_dyskinesias' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2403_time_spent_in_the_off_state] -> observation.observation_concept_id=46236400  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    46236400,
    src.visit_date,
    32817,
    'upd2403_time_spent_in_the_off_state',
    (src."upd2403_time_spent_in_the_off_state")::text,
    (src."upd2403_time_spent_in_the_off_state")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2403_time_spent_in_the_off_state" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=46236400 AND t.observation_source_value='upd2403_time_spent_in_the_off_state' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2404_functional_impact_of_fluctuations] -> observation.observation_concept_id=0
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    0,
    src.visit_date,
    32817,
    'upd2404_functional_impact_of_fluctuations',
    (src."upd2404_functional_impact_of_fluctuations")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2404_functional_impact_of_fluctuations" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=0 AND t.observation_source_value='upd2404_functional_impact_of_fluctuations' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2405_complexity_of_motor_fluctuations] -> observation.observation_concept_id=0
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    0,
    src.visit_date,
    32817,
    'upd2405_complexity_of_motor_fluctuations',
    (src."upd2405_complexity_of_motor_fluctuations")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2405_complexity_of_motor_fluctuations" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=0 AND t.observation_source_value='upd2405_complexity_of_motor_fluctuations' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2406_painful_off_state_dystonia] -> observation.observation_concept_id=46236396  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    46236396,
    src.visit_date,
    32817,
    'upd2406_painful_off_state_dystonia',
    (src."upd2406_painful_off_state_dystonia")::text,
    (src."upd2406_painful_off_state_dystonia")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2406_painful_off_state_dystonia" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=46236396 AND t.observation_source_value='upd2406_painful_off_state_dystonia' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2da_dyskinesias_during_exam] -> observation.observation_concept_id=4319906
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    4319906,
    src.visit_date,
    32817,
    'upd2da_dyskinesias_during_exam',
    (src."upd2da_dyskinesias_during_exam")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2da_dyskinesias_during_exam" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=4319906 AND t.observation_source_value='upd2da_dyskinesias_during_exam' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upd2hy_hoehn_and_yahr_stage] -> observation.observation_concept_id=46236404  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    46236404,
    src.visit_date,
    32817,
    'upd2hy_hoehn_and_yahr_stage',
    (src."upd2hy_hoehn_and_yahr_stage")::text,
    (src."upd2hy_hoehn_and_yahr_stage")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upd2hy_hoehn_and_yahr_stage" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=46236404 AND t.observation_source_value='upd2hy_hoehn_and_yahr_stage' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [upsit_performed] -> observation.observation_concept_id=3654978  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    3654978,
    src.visit_date,
    32817,
    'upsit_performed',
    (src."upsit_performed")::text,
    (src."upsit_performed")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."upsit_performed" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=3654978 AND t.observation_source_value='upsit_performed' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [use_of_pd_medication] -> observation.observation_concept_id=43528862
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    43528862,
    src.visit_date,
    32817,
    'use_of_pd_medication',
    (src."use_of_pd_medication")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."use_of_pd_medication" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=43528862 AND t.observation_source_value='use_of_pd_medication' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [visitNumber] -> observation.observation_concept_id=46235855  [value_as_string]
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, value_as_string, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    46235855,
    src.visit_date,
    32817,
    'visitNumber',
    (src."visitNumber")::text,
    (src."visitNumber")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."visitNumber" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=46235855 AND t.observation_source_value='visitNumber' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [vitiligoType] -> observation.observation_concept_id=138502
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, value_source_value, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    138502,
    src.visit_date,
    32817,
    'vitiligoType',
    (src."vitiligoType")::text,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."vitiligoType" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=138502 AND t.observation_source_value='vitiligoType' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);

-- ==================== COMPOSITES (2 elements, 3 INSERTs) ====================
-- [age_at_baseline] composite (single observation; qualifier/unit attrs)
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, value_as_number, observation_source_value, value_source_value, qualifier_concept_id, unit_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    35815526,
    src.visit_date,
    32817,
    CASE WHEN src."age_at_baseline" ~ '^-?[0-9]+(\.[0-9]+)?$' THEN src."age_at_baseline"::numeric END,
    'age_at_baseline',
    (src."age_at_baseline")::text,
    45884169,
    9448,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."age_at_baseline" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=35815526 AND t.observation_source_value='age_at_baseline' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [age_first_ad_dx] composite record 1/2: disorder as OBSERVATION (378419)
INSERT INTO cdm.observation (observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, observation_source_value, visit_occurrence_id)
SELECT NEXTVAL('observation_id_seq'), p.person_id, 378419, src.visit_date, 32817, 'age_first_ad_dx', vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
WHERE src."age_first_ad_dx" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=378419 AND t.observation_source_value='age_first_ad_dx' AND t.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id);
-- [age_first_ad_dx] composite record 2/2: observation linked to the disorder-observation via event-FK (field 1147165)
INSERT INTO cdm.observation (
    observation_id, person_id, observation_concept_id, observation_date, observation_type_concept_id, value_as_number, observation_source_value, value_source_value, qualifier_concept_id, unit_concept_id, observation_event_id, obs_event_field_concept_id, visit_occurrence_id)
SELECT
    NEXTVAL('observation_id_seq'),
    p.person_id,
    40766652,
    src.visit_date,
    32817,
    CASE WHEN src."age_first_ad_dx" ~ '^-?[0-9]+(\.[0-9]+)?$' THEN src."age_first_ad_dx"::numeric END,
    'age_first_ad_dx',
    (src."age_first_ad_dx")::text,
    4112230,
    9448,
    co.observation_id,
    1147165,
    vo.visit_occurrence_id
FROM staging.amp_clinical src
JOIN staging.person_map p ON p.person_source_value=src.person_source_value
LEFT JOIN cdm.visit_occurrence vo ON vo.visit_source_value=src.visit_source_value AND vo.person_id=p.person_id
JOIN cdm.observation co ON co.person_id=p.person_id AND co.observation_concept_id=378419 AND co.observation_source_value='age_first_ad_dx' AND co.visit_occurrence_id IS NOT DISTINCT FROM vo.visit_occurrence_id
WHERE src."age_first_ad_dx" IS NOT NULL AND src.person_source_value IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cdm.observation t WHERE t.person_id=p.person_id AND t.observation_concept_id=40766652 AND t.observation_source_value='age_first_ad_dx' AND t.observation_event_id=co.observation_id);
