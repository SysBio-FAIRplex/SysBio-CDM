"""Unfiltered copies of the AMP reference node's CDM builder SQL.

Each constant is the node's builder (fairplex-amp-reference
src/modules/query/cdm/queries.ts, facets.ts, cdeCatalog.ts, cdeValues.ts) with
the filter predicates removed. Running them against the node's own database
yields exactly the rows -- and, through the cursor description, exactly the
column types -- the node returns for an unfiltered request. The Synapse tables
store those rows, so a Synapse-backed source serves the same values under the
same data_model as the Postgres node it was cloned from.

Keep each projection byte-identical to its builder. A renamed or retyped column
here becomes a data_model mismatch at the proxy, which fails the whole page.
"""

FILE_ASSAYS_SQL = """SELECT f.file_id, f.assay_id
  FROM files f
  WHERE f.assay_id IS NOT NULL
  UNION
  SELECT aif.file_id, aif.assay_id
  FROM assay_input_file aif"""

# buildParticipantSearch, no filters, no clinical fields, not longitudinal.
PARTICIPANTS_SQL = f"""SELECT DISTINCT
  person_id,
  dataset_ids,
  sex,
  race,
  ethnicity,
  age_at_baseline,
  diagnoses,
  study_groups,
  diagnosis_concept_ids,
  diagnosis_qualifiers,
  diagnosis_qualifier_concept_ids,
  diagnosis_qualifier_source_values
FROM (
SELECT
  p.person_id,
  study_values.dataset_ids,
  demographic_values.sex,
  demographic_values.race,
  demographic_values.ethnicity,
  demographic_values.age_at_baseline,
  diagnosis_values.diagnoses,
  study_group_values.study_groups,
  diagnosis_values.diagnosis_concept_ids,
  diagnosis_values.diagnosis_qualifiers,
  diagnosis_values.diagnosis_qualifier_concept_ids,
  diagnosis_values.diagnosis_qualifier_source_values
FROM person p
LEFT JOIN LATERAL (
  SELECT ARRAY_AGG(DISTINCT f.study) FILTER (WHERE f.study IS NOT NULL) AS dataset_ids
  FROM files f
  JOIN ({FILE_ASSAYS_SQL}) fa_study ON fa_study.file_id = f.file_id
  JOIN assay_to_specimen ats_study
  ON ats_study.assay_id = fa_study.assay_id
JOIN specimen study_specimen
  ON study_specimen.specimen_id = ats_study.specimen_id
  WHERE study_specimen.person_id = p.person_id
) study_values ON TRUE
LEFT JOIN LATERAL (
  SELECT
    MAX(o.value_as_string) FILTER (WHERE o.observation_source_value = 'sex') AS sex,
    MAX(o.value_as_string) FILTER (WHERE o.observation_source_value = 'race') AS race,
    MAX(o.value_as_string) FILTER (WHERE o.observation_source_value = 'ethnicity') AS ethnicity,
    MAX(o.value_as_number) FILTER (WHERE o.observation_source_value = 'age_at_baseline') AS age_at_baseline
  FROM observation o
  WHERE o.person_id = p.person_id
) demographic_values ON TRUE
LEFT JOIN LATERAL (
  SELECT ARRAY_AGG(
    DISTINCT COALESCE(study_group_concept.concept_name, study_group.value_as_string)
  ) FILTER (
    WHERE COALESCE(study_group_concept.concept_name, study_group.value_as_string) IS NOT NULL
  ) AS study_groups
  FROM observation study_group
  LEFT JOIN concept study_group_concept
    ON study_group_concept.concept_id = study_group.value_as_concept_id
  WHERE study_group.person_id = p.person_id
    AND study_group.observation_source_value = 'study_arm'
) study_group_values ON TRUE
LEFT JOIN LATERAL (
  SELECT
    ARRAY_AGG(DISTINCT dx.concept_name) FILTER (WHERE dx.concept_name IS NOT NULL) AS diagnoses,
    ARRAY_AGG(DISTINCT diagnosis.value_as_concept_id) FILTER (WHERE diagnosis.value_as_concept_id IS NOT NULL) AS diagnosis_concept_ids,
    ARRAY_AGG(DISTINCT qualifier.concept_name) FILTER (WHERE qualifier.concept_name IS NOT NULL) AS diagnosis_qualifiers,
    ARRAY_AGG(DISTINCT diagnosis.qualifier_concept_id) FILTER (WHERE diagnosis.qualifier_concept_id IS NOT NULL) AS diagnosis_qualifier_concept_ids,
    ARRAY_AGG(DISTINCT diagnosis.qualifier_source_value) FILTER (WHERE diagnosis.qualifier_source_value IS NOT NULL) AS diagnosis_qualifier_source_values
  FROM observation diagnosis
  LEFT JOIN concept dx ON dx.concept_id = diagnosis.value_as_concept_id
  LEFT JOIN concept qualifier ON qualifier.concept_id = diagnosis.qualifier_concept_id
  WHERE diagnosis.person_id = p.person_id
    AND diagnosis.observation_concept_id = 4234469
) diagnosis_values ON TRUE
) participant_rows"""

# Per-person filter columns the connector evaluates directly in Synapse SQL.
# Each mirrors one predicate of personConditions/longitudinalConditions or one
# participant breakdown, precomputed because Synapse SQL has no correlated
# subqueries. Lists hold EVERY value a person has, so `HAS` reproduces the
# node's EXISTS semantics.
PARTICIPANT_FILTERS_SQL = f"""SELECT
  p.person_id,
  (SELECT ARRAY_AGG(DISTINCT LOWER(o.value_as_string)) FILTER (WHERE o.value_as_string IS NOT NULL)
     FROM observation o WHERE o.person_id = p.person_id AND o.observation_source_value = 'sex') AS sex_keys,
  (SELECT ARRAY_AGG(DISTINCT LOWER(o.value_as_string)) FILTER (WHERE o.value_as_string IS NOT NULL)
     FROM observation o WHERE o.person_id = p.person_id AND o.observation_source_value = 'race') AS race_keys,
  (SELECT ARRAY_AGG(DISTINCT LOWER(o.value_as_string)) FILTER (WHERE o.value_as_string IS NOT NULL)
     FROM observation o WHERE o.person_id = p.person_id AND o.observation_source_value = 'ethnicity') AS ethnicity_keys,
  (SELECT ARRAY_AGG(DISTINCT LOWER(COALESCE(c.concept_name, o.value_as_string)))
          FILTER (WHERE COALESCE(c.concept_name, o.value_as_string) IS NOT NULL)
     FROM observation o LEFT JOIN concept c ON c.concept_id = o.value_as_concept_id
     WHERE o.person_id = p.person_id AND o.observation_source_value = 'study_arm') AS study_group_keys,
  (SELECT ARRAY_AGG(DISTINCT COALESCE(o.value_as_concept_id::text, '') || ':' || COALESCE(o.qualifier_concept_id::text, ''))
     FROM observation o WHERE o.person_id = p.person_id AND o.observation_concept_id = 4234469) AS diagnosis_pairs,
  (SELECT MIN(o.value_as_number)::float8
     FROM observation o WHERE o.person_id = p.person_id AND o.observation_source_value = 'age_at_baseline') AS age_min,
  (SELECT MAX(o.value_as_number)::float8
     FROM observation o WHERE o.person_id = p.person_id AND o.observation_source_value = 'age_at_baseline') AS age_max,
  (SELECT COUNT(DISTINCT v.visit_occurrence_id) FROM visit_occurrence v WHERE v.person_id = p.person_id) AS visit_count,
  (SELECT COALESCE(MAX(v.visit_start_date) - MIN(v.visit_start_date), 0)
     FROM visit_occurrence v WHERE v.person_id = p.person_id) AS follow_up_days,
  CASE
    WHEN EXISTS (
      SELECT 1 FROM observation case_diagnosis
      WHERE case_diagnosis.person_id = p.person_id
        AND case_diagnosis.observation_concept_id = 4234469
        AND case_diagnosis.value_as_concept_id IS NOT NULL
        AND case_diagnosis.qualifier_concept_id = 1989833
    ) THEN 'case'
    WHEN EXISTS (
      SELECT 1 FROM observation control_diagnosis
      WHERE control_diagnosis.person_id = p.person_id
        AND control_diagnosis.observation_concept_id = 4234469
        AND control_diagnosis.value_as_concept_id IS NOT NULL
        AND control_diagnosis.qualifier_concept_id = 44804027
    ) THEN 'control'
    ELSE 'other'
  END AS case_control,
  (SELECT ARRAY_AGG(DISTINCT COALESCE(sex_concept.concept_name, sex.value_as_string, 'Unknown'))
     FROM (SELECT 1) one
     LEFT JOIN observation sex ON sex.person_id = p.person_id AND sex.observation_source_value = 'sex'
     LEFT JOIN concept sex_concept ON sex_concept.concept_id = sex.value_as_concept_id) AS sex_buckets,
  (SELECT MIN(ag.code) FROM observation o
     JOIN observation_access oa ON oa.observation_id = o.observation_id
     JOIN access_group ag ON ag.id = oa.access_group_id
     WHERE o.person_id = p.person_id) AS access_group
FROM person p"""

# buildFileSearch with no WHERE: every file, every role.
FILES_SQL = f"""SELECT DISTINCT
  file_id,
  file_role,
  dataset_id,
  study,
  analysis_type,
  array_type,
  biosample_type,
  tissue,
  cell_type,
  species,
  processing_status,
  file_format,
  file_size_bytes,
  uri,
  assay_source_values,
  assay_types,
  platforms,
  suspension_types,
  analyte_types,
  analysis_pipelines,
  specimen_source_values,
  anatomic_site_source_values
FROM (
SELECT
  f.file_id,
  f.file_role,
  f.study AS dataset_id,
  f.study,
  f.analysis_type,
  f.array_type,
  f.biosample_type,
  f.tissue,
  f.cell_type,
  f.species,
  f.processing_status,
  f.file_format,
  f.file_size_bytes,
  f.uri,
  assay_values.assay_source_values,
  assay_values.assay_types,
  assay_values.platforms,
  assay_values.suspension_types,
  assay_values.analyte_types,
  assay_values.analysis_pipelines,
  specimen_values.specimen_source_values,
  specimen_values.anatomic_site_source_values
FROM files f
LEFT JOIN LATERAL (
  SELECT
    ARRAY_AGG(DISTINCT a.assay_source_value) FILTER (WHERE a.assay_source_value IS NOT NULL) AS assay_source_values,
    ARRAY_AGG(DISTINCT a.assay_type) FILTER (WHERE a.assay_type IS NOT NULL) AS assay_types,
    ARRAY_AGG(DISTINCT a.platform) FILTER (WHERE a.platform IS NOT NULL) AS platforms,
    ARRAY_AGG(DISTINCT a.suspension_type) FILTER (WHERE a.suspension_type IS NOT NULL) AS suspension_types,
    ARRAY_AGG(DISTINCT a.analyte_type) FILTER (WHERE a.analyte_type IS NOT NULL) AS analyte_types,
    ARRAY_AGG(DISTINCT a.analysis_pipeline) FILTER (WHERE a.analysis_pipeline IS NOT NULL) AS analysis_pipelines
  FROM ({FILE_ASSAYS_SQL}) fa
  JOIN assay a ON a.assay_id = fa.assay_id
  WHERE fa.file_id = f.file_id
) assay_values ON TRUE
LEFT JOIN LATERAL (
  SELECT
    ARRAY_AGG(DISTINCT s.specimen_source_value)
      FILTER (WHERE s.specimen_source_value IS NOT NULL) AS specimen_source_values,
    ARRAY_AGG(DISTINCT s.anatomic_site_source_value)
      FILTER (WHERE s.anatomic_site_source_value IS NOT NULL) AS anatomic_site_source_values
  FROM ({FILE_ASSAYS_SQL}) fa
  JOIN assay_to_specimen ats
  ON ats.assay_id = fa.assay_id
JOIN specimen s
  ON s.specimen_id = ats.specimen_id
  WHERE fa.file_id = f.file_id
) specimen_values ON TRUE
) file_rows"""

# buildDatasetSearch over every file (no role filter) -- the access-group
# metadata per program. The connector re-derives which programs match a filter
# from the files table and joins this metadata on dataset_id.
DATASETS_SQL = """SELECT
  f.study AS dataset_id,
  f.study AS code,
  f.study AS program,
  ARRAY_AGG(DISTINCT ag.code) FILTER (WHERE ag.code IS NOT NULL) AS access_group_codes,
  ARRAY_AGG(DISTINCT ag.name) FILTER (WHERE ag.name IS NOT NULL) AS access_group_names,
  ARRAY_AGG(DISTINCT ag.description) FILTER (WHERE ag.description IS NOT NULL) AS access_group_descriptions,
  ARRAY_AGG(DISTINCT ag.program) FILTER (WHERE ag.program IS NOT NULL) AS access_group_programs,
  ARRAY_AGG(DISTINCT ag.disease_focus) FILTER (WHERE ag.disease_focus IS NOT NULL) AS access_group_disease_focuses,
  ARRAY_AGG(DISTINCT ag.dul) FILTER (WHERE ag.dul IS NOT NULL) AS access_group_duls
FROM files f
JOIN file_access fa ON fa.file_id = f.file_id
JOIN access_group ag ON ag.id = fa.access_group_id
WHERE f.study IS NOT NULL
GROUP BY dataset_id"""

# buildRelationshipSearch with no anchor and no filters: every concrete
# person -> specimen -> assay -> file path, plus observation-only membership.
RELATIONSHIPS_SQL = f"""SELECT DISTINCT
  person_id,
  sex,
  race,
  ethnicity,
  diagnoses,
  diagnosis_concept_ids,
  diagnosis_qualifiers,
  diagnosis_qualifier_concept_ids,
  specimen_id,
  specimen_source_value,
  anatomic_site_source_value,
  assay_id,
  assay_source_value,
  assay_type,
  platform,
  suspension_type,
  analyte_type,
  analysis_pipeline,
  file_id,
  file_role,
  dataset_id,
  analysis_type,
  cell_type,
  tissue,
  biosample_type,
  file_format,
  file_size_bytes,
  uri
FROM (
SELECT
  p.person_id,
  demographic_values.sex,
  demographic_values.race,
  demographic_values.ethnicity,
  diagnosis_values.diagnoses,
  diagnosis_values.diagnosis_concept_ids,
  diagnosis_values.diagnosis_qualifiers,
  diagnosis_values.diagnosis_qualifier_concept_ids,
  s.specimen_id,
  s.specimen_source_value,
  s.anatomic_site_source_value,
  a.assay_id,
  a.assay_source_value,
  a.assay_type,
  a.platform,
  a.suspension_type,
  a.analyte_type,
  a.analysis_pipeline,
  f.file_id,
  f.file_role,
  f.study AS dataset_id,
  f.analysis_type,
  f.cell_type,
  f.tissue,
  f.biosample_type,
  f.file_format,
  f.file_size_bytes,
  f.uri
FROM files f
JOIN (
  SELECT fa_links.file_id, linked_specimen.person_id,
    linked_specimen.specimen_id, fa_links.assay_id
  FROM ({FILE_ASSAYS_SQL}) fa_links
  JOIN assay_to_specimen ats_links
  ON ats_links.assay_id = fa_links.assay_id
JOIN specimen linked_specimen
  ON linked_specimen.specimen_id = ats_links.specimen_id
  UNION
  SELECT membership.observation_event_id AS file_id, membership.person_id,
    NULL::integer AS specimen_id, NULL::integer AS assay_id
  FROM observation membership
  WHERE membership.observation_concept_id = 4303445
    AND membership.obs_event_field_concept_id = 2000000001
) evidence ON evidence.file_id = f.file_id
LEFT JOIN assay a ON a.assay_id = evidence.assay_id
LEFT JOIN specimen s ON s.specimen_id = evidence.specimen_id
JOIN person p ON p.person_id = evidence.person_id
LEFT JOIN LATERAL (
  SELECT
    MAX(o.value_as_string) FILTER (WHERE o.observation_source_value = 'sex') AS sex,
    MAX(o.value_as_string) FILTER (WHERE o.observation_source_value = 'race') AS race,
    MAX(o.value_as_string) FILTER (WHERE o.observation_source_value = 'ethnicity') AS ethnicity
  FROM observation o
  WHERE o.person_id = p.person_id
) demographic_values ON TRUE
LEFT JOIN LATERAL (
  SELECT
    ARRAY_AGG(DISTINCT dx.concept_name) FILTER (WHERE dx.concept_name IS NOT NULL) AS diagnoses,
    ARRAY_AGG(DISTINCT diagnosis.value_as_concept_id) FILTER (WHERE diagnosis.value_as_concept_id IS NOT NULL) AS diagnosis_concept_ids,
    ARRAY_AGG(DISTINCT qualifier.concept_name) FILTER (WHERE qualifier.concept_name IS NOT NULL) AS diagnosis_qualifiers,
    ARRAY_AGG(DISTINCT diagnosis.qualifier_concept_id) FILTER (WHERE diagnosis.qualifier_concept_id IS NOT NULL) AS diagnosis_qualifier_concept_ids
  FROM observation diagnosis
  LEFT JOIN concept dx ON dx.concept_id = diagnosis.value_as_concept_id
  LEFT JOIN concept qualifier ON qualifier.concept_id = diagnosis.qualifier_concept_id
  WHERE diagnosis.person_id = p.person_id
    AND diagnosis.observation_concept_id = 4234469
) diagnosis_values ON TRUE
) relationship_rows"""

# Long clinical table: one row per observation/measurement value, with the
# node's display expression (clinicalValueProjection) and latest-row flags
# (latestRowCondition) precomputed.
CLINICAL_SQL = """SELECT
  'observation' AS domain,
  o.observation_id AS clinical_row_id,
  o.person_id,
  o.observation_concept_id AS concept_id,
  o.observation_source_value AS source_value,
  o.value_as_number::float8 AS value_as_number,
  o.value_as_string AS value_text,
  o.value_as_concept_id,
  o.visit_occurrence_id,
  o.observation_date AS row_date,
  COALESCE(c.concept_name, CAST(o.value_as_number AS TEXT), o.value_as_string) AS display_value,
  ROW_NUMBER() OVER (
    PARTITION BY o.person_id, o.observation_source_value
    ORDER BY o.observation_date DESC NULLS LAST, o.observation_id DESC) = 1 AS is_latest,
  ROW_NUMBER() OVER (
    PARTITION BY o.person_id, o.observation_source_value, o.observation_concept_id
    ORDER BY o.observation_date DESC NULLS LAST, o.observation_id DESC) = 1 AS is_latest_concept
FROM observation o
LEFT JOIN concept c ON c.concept_id = o.value_as_concept_id
WHERE o.observation_source_value IS NOT NULL
UNION ALL
SELECT
  'measurement',
  m.measurement_id,
  m.person_id,
  m.measurement_concept_id,
  m.measurement_source_value,
  m.value_as_number::float8,
  m.value_source_value,
  m.value_as_concept_id,
  m.visit_occurrence_id,
  m.measurement_date,
  COALESCE(c.concept_name, CAST(m.value_as_number AS TEXT), m.value_source_value),
  ROW_NUMBER() OVER (
    PARTITION BY m.person_id, m.measurement_source_value
    ORDER BY m.measurement_date DESC NULLS LAST, m.measurement_id DESC) = 1,
  ROW_NUMBER() OVER (
    PARTITION BY m.person_id, m.measurement_source_value, m.measurement_concept_id
    ORDER BY m.measurement_date DESC NULLS LAST, m.measurement_id DESC) = 1
FROM measurement m
LEFT JOIN concept c ON c.concept_id = m.value_as_concept_id
WHERE m.measurement_source_value IS NOT NULL"""

CONCEPTS_SQL = "SELECT concept_id, concept_name FROM concept"

VISITS_SQL = """SELECT visit_occurrence_id, person_id, visit_start_date
FROM visit_occurrence"""

# facets.ts FACETS_SQL, verbatim.
FACETS_SQL = """SELECT 'dataset_ids' AS facet, f.study AS value, NULL::INTEGER AS concept_id, COUNT(DISTINCT f.file_id) AS count
  FROM files f WHERE f.file_role IN ('harmonized_output', 'assay_matrix') AND f.study IS NOT NULL GROUP BY f.study
  UNION ALL SELECT 'file_roles', f.file_role, NULL::INTEGER, COUNT(DISTINCT f.file_id) FROM files f WHERE f.file_role IN ('harmonized_output', 'assay_matrix') AND f.file_role IS NOT NULL GROUP BY f.file_role
  UNION ALL SELECT 'analysis_types', f.analysis_type, NULL::INTEGER, COUNT(DISTINCT f.file_id) FROM files f WHERE f.file_role IN ('harmonized_output', 'assay_matrix') AND f.analysis_type IS NOT NULL GROUP BY f.analysis_type
  UNION ALL SELECT 'file_formats', f.file_format, NULL::INTEGER, COUNT(DISTINCT f.file_id) FROM files f WHERE f.file_role IN ('harmonized_output', 'assay_matrix') AND f.file_format IS NOT NULL GROUP BY f.file_format
  UNION ALL SELECT 'tissues', f.tissue, NULL::INTEGER, COUNT(DISTINCT f.file_id) FROM files f WHERE f.file_role IN ('harmonized_output', 'assay_matrix') AND f.tissue IS NOT NULL GROUP BY f.tissue
  UNION ALL SELECT 'biosample_types', f.biosample_type, NULL::INTEGER, COUNT(DISTINCT f.file_id) FROM files f WHERE f.file_role IN ('harmonized_output', 'assay_matrix') AND f.biosample_type IS NOT NULL GROUP BY f.biosample_type
  UNION ALL SELECT 'cell_types', f.cell_type, NULL::INTEGER, COUNT(DISTINCT f.file_id) FROM files f WHERE f.file_role IN ('harmonized_output', 'assay_matrix') AND f.cell_type IS NOT NULL GROUP BY f.cell_type
  UNION ALL SELECT 'assay_source_values', a.assay_source_value, NULL::INTEGER, COUNT(DISTINCT f.file_id) FROM files f JOIN assay a ON (
    a.assay_id = f.assay_id OR EXISTS (
      SELECT 1 FROM assay_input_file aif
      WHERE aif.file_id = f.file_id AND aif.assay_id = a.assay_id
    )
  ) WHERE f.file_role IN ('harmonized_output', 'assay_matrix') AND a.assay_source_value IS NOT NULL GROUP BY a.assay_source_value
  UNION ALL SELECT 'assay_types', a.assay_type, NULL::INTEGER, COUNT(DISTINCT f.file_id) FROM files f JOIN assay a ON (
    a.assay_id = f.assay_id OR EXISTS (
      SELECT 1 FROM assay_input_file aif
      WHERE aif.file_id = f.file_id AND aif.assay_id = a.assay_id
    )
  ) WHERE f.file_role IN ('harmonized_output', 'assay_matrix') AND a.assay_type IS NOT NULL GROUP BY a.assay_type
  UNION ALL SELECT 'platforms', a.platform, NULL::INTEGER, COUNT(DISTINCT f.file_id) FROM files f JOIN assay a ON (
    a.assay_id = f.assay_id OR EXISTS (
      SELECT 1 FROM assay_input_file aif
      WHERE aif.file_id = f.file_id AND aif.assay_id = a.assay_id
    )
  ) WHERE f.file_role IN ('harmonized_output', 'assay_matrix') AND a.platform IS NOT NULL GROUP BY a.platform
  UNION ALL SELECT 'suspension_types', a.suspension_type, NULL::INTEGER, COUNT(DISTINCT f.file_id) FROM files f JOIN assay a ON (
    a.assay_id = f.assay_id OR EXISTS (
      SELECT 1 FROM assay_input_file aif
      WHERE aif.file_id = f.file_id AND aif.assay_id = a.assay_id
    )
  ) WHERE f.file_role IN ('harmonized_output', 'assay_matrix') AND a.suspension_type IS NOT NULL GROUP BY a.suspension_type
  UNION ALL SELECT 'analyte_types', a.analyte_type, NULL::INTEGER, COUNT(DISTINCT f.file_id) FROM files f JOIN assay a ON (
    a.assay_id = f.assay_id OR EXISTS (
      SELECT 1 FROM assay_input_file aif
      WHERE aif.file_id = f.file_id AND aif.assay_id = a.assay_id
    )
  ) WHERE f.file_role IN ('harmonized_output', 'assay_matrix') AND a.analyte_type IS NOT NULL GROUP BY a.analyte_type
  UNION ALL SELECT 'analysis_pipelines', a.analysis_pipeline, NULL::INTEGER, COUNT(DISTINCT f.file_id) FROM files f JOIN assay a ON (
    a.assay_id = f.assay_id OR EXISTS (
      SELECT 1 FROM assay_input_file aif
      WHERE aif.file_id = f.file_id AND aif.assay_id = a.assay_id
    )
  ) WHERE f.file_role IN ('harmonized_output', 'assay_matrix') AND a.analysis_pipeline IS NOT NULL GROUP BY a.analysis_pipeline
  UNION ALL SELECT 'specimen_source_values', s.specimen_source_value, NULL::INTEGER, COUNT(DISTINCT f.file_id) FROM files f JOIN (SELECT f.file_id, f.assay_id
  FROM files f
  WHERE f.assay_id IS NOT NULL
  UNION
  SELECT aif.file_id, aif.assay_id
  FROM assay_input_file aif) fa ON fa.file_id=f.file_id JOIN assay_to_specimen ats ON ats.assay_id=fa.assay_id JOIN specimen s ON s.specimen_id=ats.specimen_id WHERE f.file_role IN ('harmonized_output', 'assay_matrix') AND s.specimen_source_value IS NOT NULL GROUP BY s.specimen_source_value
  UNION ALL SELECT 'anatomic_site_source_values', s.anatomic_site_source_value, NULL::INTEGER, COUNT(DISTINCT f.file_id) FROM files f JOIN (SELECT f.file_id, f.assay_id
  FROM files f
  WHERE f.assay_id IS NOT NULL
  UNION
  SELECT aif.file_id, aif.assay_id
  FROM assay_input_file aif) fa ON fa.file_id=f.file_id JOIN assay_to_specimen ats ON ats.assay_id=fa.assay_id JOIN specimen s ON s.specimen_id=ats.specimen_id WHERE f.file_role IN ('harmonized_output', 'assay_matrix') AND s.anatomic_site_source_value IS NOT NULL GROUP BY s.anatomic_site_source_value
  UNION ALL
  SELECT 'diagnoses', c.concept_name, c.concept_id, COUNT(DISTINCT o.person_id)
  FROM observation o JOIN concept c ON c.concept_id=o.value_as_concept_id
  WHERE o.observation_concept_id=4234469 GROUP BY c.concept_id, c.concept_name
  UNION ALL
  SELECT 'study_arms', COALESCE(c.concept_name, o.value_as_string), NULL::INTEGER, COUNT(DISTINCT o.person_id)
  FROM observation o LEFT JOIN concept c ON c.concept_id=o.value_as_concept_id
  WHERE o.observation_source_value='study_arm'
    AND COALESCE(c.concept_name, o.value_as_string) IS NOT NULL
  GROUP BY COALESCE(c.concept_name, o.value_as_string)
  UNION ALL SELECT 'sexes', LOWER(o.value_as_string), NULL::INTEGER, COUNT(DISTINCT o.person_id) FROM observation o WHERE o.observation_source_value='sex' AND o.value_as_string IS NOT NULL GROUP BY LOWER(o.value_as_string)
  UNION ALL SELECT 'races', o.value_as_string, NULL::INTEGER, COUNT(DISTINCT o.person_id) FROM observation o WHERE o.observation_source_value='race' AND o.value_as_string IS NOT NULL GROUP BY o.value_as_string
  UNION ALL SELECT 'ethnicities', o.value_as_string, NULL::INTEGER, COUNT(DISTINCT o.person_id) FROM observation o WHERE o.observation_source_value='ethnicity' AND o.value_as_string IS NOT NULL GROUP BY o.value_as_string
  ORDER BY 1, 2"""

# cdeCatalog.ts CATALOG_SQL, verbatim (MAX_CDES = 5000).
CDE_CATALOG_SQL = """SELECT
  'observation' AS domain,
  o.observation_source_value AS source_value,
  o.observation_concept_id AS concept_id,
  o.observation_source_concept_id AS source_concept_id,
  c.concept_name,
  COUNT(DISTINCT o.person_id) AS participant_count,
  COUNT(*) AS row_count
FROM observation o
LEFT JOIN concept c ON c.concept_id = o.observation_concept_id
WHERE o.observation_source_value IS NOT NULL
GROUP BY o.observation_source_value, o.observation_concept_id, o.observation_source_concept_id, c.concept_name
UNION ALL
SELECT
  'measurement',
  m.measurement_source_value,
  m.measurement_concept_id,
  m.measurement_source_concept_id,
  c.concept_name,
  COUNT(DISTINCT m.person_id),
  COUNT(*)
FROM measurement m
LEFT JOIN concept c ON c.concept_id = m.measurement_concept_id
WHERE m.measurement_source_value IS NOT NULL
GROUP BY m.measurement_source_value, m.measurement_concept_id, m.measurement_source_concept_id, c.concept_name
ORDER BY 6 DESC, 2
LIMIT 5001"""

# cdeValues.ts totalsSql/optionsSql, grouped over every CDE at once instead of
# run per CDE. Per-CDE option ordering and the 200-option cap are applied in
# Python exactly as the node's ORDER BY / LIMIT do.
CDE_TOTALS_SQL = """SELECT 'observation' AS domain, observation_source_value AS source_value,
  COUNT(DISTINCT person_id) AS participant_count, COUNT(*) AS row_count,
  COUNT(value_as_number) AS numeric_row_count,
  MIN(value_as_number) AS numeric_min, MAX(value_as_number) AS numeric_max
FROM observation WHERE observation_source_value IS NOT NULL GROUP BY observation_source_value
UNION ALL
SELECT 'measurement', measurement_source_value,
  COUNT(DISTINCT person_id), COUNT(*), COUNT(value_as_number),
  MIN(value_as_number), MAX(value_as_number)
FROM measurement WHERE measurement_source_value IS NOT NULL GROUP BY measurement_source_value"""

CDE_OPTIONS_SQL = """SELECT 'observation' AS domain, v.observation_source_value AS source_value,
  v.value_as_string AS text_value, v.value_as_concept_id AS concept_id, c.concept_name,
  COUNT(DISTINCT v.person_id) AS participant_count, COUNT(*) AS row_count
FROM observation v LEFT JOIN concept c ON c.concept_id = v.value_as_concept_id
WHERE v.observation_source_value IS NOT NULL
  AND (v.value_as_string IS NOT NULL OR v.value_as_concept_id IS NOT NULL)
GROUP BY v.observation_source_value, v.value_as_string, v.value_as_concept_id, c.concept_name
UNION ALL
SELECT 'measurement', v.measurement_source_value,
  v.value_source_value, v.value_as_concept_id, c.concept_name,
  COUNT(DISTINCT v.person_id), COUNT(*)
FROM measurement v LEFT JOIN concept c ON c.concept_id = v.value_as_concept_id
WHERE v.measurement_source_value IS NOT NULL
  AND (v.value_source_value IS NOT NULL OR v.value_as_concept_id IS NOT NULL)
GROUP BY v.measurement_source_value, v.value_source_value, v.value_as_concept_id, c.concept_name"""
