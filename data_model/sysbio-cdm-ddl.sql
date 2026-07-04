-- SysBio-CDM DDL. GENERATED from data_model/sysbio-dbml.dbml — do not hand-edit.
-- Run inside your target schema, e.g.  SET search_path = my_schema;
-- Faithful to the DBML: tables, columns, PKs, FKs, and the person data-free
-- CHECK named in the DBML header. No triggers, RLS, or views.

CREATE TABLE access_groups (
  id SERIAL,
  code TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  program TEXT,
  disease_focus TEXT,
  dul TEXT,
  data_access_instructions TEXT,
  created_at TIMESTAMP(3) NOT NULL,
  PRIMARY KEY (id)
);

CREATE TABLE user_access_groups (
  user_id TEXT NOT NULL,
  access_group_id INTEGER NOT NULL,
  granted_at TIMESTAMP(3) NOT NULL,
  granted_by TEXT,
  PRIMARY KEY (user_id, access_group_id)
);

CREATE TABLE concept (
  concept_id INTEGER,
  concept_name VARCHAR(255) NOT NULL,
  domain_id VARCHAR(20) NOT NULL,
  vocabulary_id VARCHAR(20) NOT NULL,
  concept_class_id VARCHAR(20) NOT NULL,
  standard_concept VARCHAR(1),
  concept_code VARCHAR(50) NOT NULL,
  valid_start_date DATE NOT NULL,
  valid_end_date DATE NOT NULL,
  invalid_reason VARCHAR(1),
  PRIMARY KEY (concept_id)
);

CREATE TABLE person (
  person_id INTEGER,
  gender_concept_id INTEGER NOT NULL,
  year_of_birth INTEGER NOT NULL,
  race_concept_id INTEGER NOT NULL,
  ethnicity_concept_id INTEGER NOT NULL,
  PRIMARY KEY (person_id),
  CONSTRAINT person_data_free CHECK (gender_concept_id = 0 AND year_of_birth = 0 AND race_concept_id = 0 AND ethnicity_concept_id = 0)
);

CREATE TABLE observation_period (
  observation_period_id INTEGER,
  person_id INTEGER NOT NULL,
  observation_period_start_date DATE NOT NULL,
  observation_period_end_date DATE NOT NULL,
  period_type_concept_id INTEGER NOT NULL,
  PRIMARY KEY (observation_period_id)
);

CREATE TABLE visit_occurrence (
  visit_occurrence_id INTEGER,
  person_id INTEGER NOT NULL,
  visit_concept_id INTEGER NOT NULL,
  visit_start_date DATE NOT NULL,
  visit_start_datetime TIMESTAMP(3),
  visit_end_date DATE NOT NULL,
  visit_end_datetime TIMESTAMP(3),
  visit_type_concept_id INTEGER NOT NULL,
  provider_id INTEGER,
  care_site_id INTEGER,
  visit_source_value VARCHAR(50),
  visit_source_concept_id INTEGER,
  admitted_from_concept_id INTEGER,
  admitted_from_source_value VARCHAR(50),
  discharged_to_concept_id INTEGER,
  discharged_to_source_value VARCHAR(50),
  preceding_visit_occurrence_id INTEGER,
  PRIMARY KEY (visit_occurrence_id)
);

CREATE TABLE condition_occurrence (
  condition_occurrence_id INTEGER,
  person_id INTEGER NOT NULL,
  condition_concept_id INTEGER NOT NULL,
  condition_start_date DATE NOT NULL,
  condition_start_datetime TIMESTAMP(3),
  condition_end_date DATE,
  condition_end_datetime TIMESTAMP(3),
  condition_type_concept_id INTEGER NOT NULL,
  condition_status_concept_id INTEGER,
  stop_reason VARCHAR(20),
  provider_id INTEGER,
  visit_occurrence_id INTEGER,
  visit_detail_id INTEGER,
  condition_source_value VARCHAR(50),
  condition_source_concept_id INTEGER,
  condition_status_source_value VARCHAR(50),
  PRIMARY KEY (condition_occurrence_id)
);

CREATE TABLE measurement (
  measurement_id INTEGER,
  person_id INTEGER NOT NULL,
  measurement_concept_id INTEGER NOT NULL,
  measurement_date DATE NOT NULL,
  measurement_datetime TIMESTAMP(3),
  measurement_time VARCHAR(10),
  measurement_type_concept_id INTEGER NOT NULL,
  operator_concept_id INTEGER,
  value_as_number DECIMAL(65,30),
  value_as_concept_id INTEGER,
  unit_concept_id INTEGER,
  range_low DECIMAL(65,30),
  range_high DECIMAL(65,30),
  provider_id INTEGER,
  visit_occurrence_id INTEGER,
  visit_detail_id INTEGER,
  measurement_source_value VARCHAR(50),
  measurement_source_concept_id INTEGER,
  unit_source_value VARCHAR(50),
  unit_source_concept_id INTEGER,
  value_source_value VARCHAR(50),
  measurement_event_id INTEGER,
  meas_event_field_concept_id INTEGER,
  PRIMARY KEY (measurement_id)
);

CREATE TABLE observation (
  observation_id INTEGER,
  person_id INTEGER NOT NULL,
  observation_concept_id INTEGER NOT NULL,
  observation_date DATE NOT NULL,
  observation_datetime TIMESTAMP(3),
  observation_type_concept_id INTEGER NOT NULL,
  value_as_number DECIMAL(65,30),
  value_as_string VARCHAR(60),
  value_as_concept_id INTEGER,
  qualifier_concept_id INTEGER,
  unit_concept_id INTEGER,
  provider_id INTEGER,
  visit_occurrence_id INTEGER,
  visit_detail_id INTEGER,
  observation_source_value VARCHAR(50),
  observation_source_concept_id INTEGER,
  unit_source_value VARCHAR(50),
  qualifier_source_value VARCHAR(50),
  value_source_value VARCHAR(50),
  observation_event_id INTEGER,
  obs_event_field_concept_id INTEGER,
  PRIMARY KEY (observation_id)
);

CREATE TABLE specimen (
  specimen_id INTEGER,
  person_id INTEGER NOT NULL,
  specimen_concept_id INTEGER NOT NULL,
  specimen_type_concept_id INTEGER NOT NULL,
  specimen_date DATE NOT NULL,
  specimen_datetime TIMESTAMP(3),
  quantity DECIMAL(65,30),
  unit_concept_id INTEGER,
  anatomic_site_concept_id INTEGER,
  disease_status_concept_id INTEGER,
  specimen_source_id VARCHAR(50),
  specimen_source_value VARCHAR(50),
  unit_source_value VARCHAR(50),
  anatomic_site_source_value VARCHAR(50),
  disease_status_source_value VARCHAR(50),
  PRIMARY KEY (specimen_id)
);

CREATE TABLE procedure_occurrence (
  procedure_occurrence_id INTEGER,
  person_id INTEGER NOT NULL,
  procedure_concept_id INTEGER NOT NULL,
  procedure_date DATE NOT NULL,
  procedure_datetime TIMESTAMP(3),
  procedure_end_date DATE,
  procedure_end_datetime TIMESTAMP(3),
  procedure_type_concept_id INTEGER NOT NULL,
  modifier_concept_id INTEGER,
  quantity INTEGER,
  provider_id INTEGER,
  visit_occurrence_id INTEGER,
  visit_detail_id INTEGER,
  procedure_source_value VARCHAR(50),
  procedure_source_concept_id INTEGER,
  modifier_source_value VARCHAR(50),
  PRIMARY KEY (procedure_occurrence_id)
);

CREATE TABLE fact_relationship (
  domain_concept_id_1 INTEGER NOT NULL,
  fact_id_1 INTEGER NOT NULL,
  domain_concept_id_2 INTEGER NOT NULL,
  fact_id_2 INTEGER NOT NULL,
  relationship_concept_id INTEGER NOT NULL,
  PRIMARY KEY (domain_concept_id_1, fact_id_1, domain_concept_id_2, fact_id_2, relationship_concept_id)
);

CREATE TABLE cdm_source (
  cdm_source_name TEXT,
  cdm_source_abbreviation TEXT NOT NULL,
  cdm_holder TEXT NOT NULL,
  source_description TEXT,
  source_documentation_reference TEXT,
  cdm_etl_reference TEXT,
  source_release_date DATE NOT NULL,
  cdm_release_date DATE NOT NULL,
  cdm_version TEXT,
  cdm_version_concept_id INTEGER NOT NULL,
  vocabulary_version TEXT NOT NULL,
  PRIMARY KEY (cdm_source_name)
);

CREATE TABLE files (
  file_id INTEGER,
  file_name TEXT NOT NULL,
  current_version INTEGER,
  assay_id INTEGER,
  file_role TEXT,
  study TEXT,
  "grant" TEXT,
  array_type TEXT,
  analysis_type TEXT,
  biosample_type TEXT,
  tissue TEXT,
  cell_type TEXT,
  species TEXT,
  processing_status TEXT,
  file_format TEXT,
  file_size_bytes BIGINT,
  created_on TIMESTAMP(3),
  modified_on TIMESTAMP(3),
  drs_id TEXT NOT NULL,
  PRIMARY KEY (file_id)
);

CREATE TABLE assay (
  assay_id INTEGER,
  assay_source_value TEXT,
  assay_type TEXT NOT NULL,
  platform TEXT NOT NULL,
  suspension_type TEXT,
  analyte_type TEXT,
  analysis_pipeline TEXT,
  PRIMARY KEY (assay_id)
);

CREATE TABLE assay_to_specimen (
  assay_id INTEGER NOT NULL,
  specimen_id INTEGER NOT NULL,
  PRIMARY KEY (assay_id, specimen_id)
);

CREATE TABLE assay_input_file (
  assay_id INTEGER NOT NULL,
  file_id INTEGER NOT NULL,
  PRIMARY KEY (assay_id, file_id)
);

CREATE TABLE specimen_relationship (
  specimen_id_1 INTEGER NOT NULL,
  specimen_id_2 INTEGER NOT NULL,
  relationship_concept_id INTEGER,
  procedure_occurrence_id INTEGER NOT NULL,
  PRIMARY KEY (specimen_id_1, specimen_id_2)
);

CREATE TABLE condition_occurrence_access (
  condition_occurrence_id INTEGER NOT NULL,
  access_group_id INTEGER NOT NULL,
  PRIMARY KEY (condition_occurrence_id, access_group_id)
);

CREATE TABLE procedure_occurrence_access (
  procedure_occurrence_id INTEGER NOT NULL,
  access_group_id INTEGER NOT NULL,
  PRIMARY KEY (procedure_occurrence_id, access_group_id)
);

CREATE TABLE measurement_access (
  measurement_id INTEGER NOT NULL,
  access_group_id INTEGER NOT NULL,
  PRIMARY KEY (measurement_id, access_group_id)
);

CREATE TABLE observation_access (
  observation_id INTEGER NOT NULL,
  access_group_id INTEGER NOT NULL,
  PRIMARY KEY (observation_id, access_group_id)
);

CREATE TABLE specimen_access (
  specimen_id INTEGER NOT NULL,
  access_group_id INTEGER NOT NULL,
  PRIMARY KEY (specimen_id, access_group_id)
);

CREATE TABLE file_access (
  file_id INTEGER NOT NULL,
  access_group_id INTEGER NOT NULL,
  PRIMARY KEY (file_id, access_group_id)
);

-- ---- foreign keys ----
ALTER TABLE user_access_groups ADD CONSTRAINT user_access_groups_access_group_id_fkey FOREIGN KEY (access_group_id) REFERENCES access_groups (id);
ALTER TABLE observation_period ADD CONSTRAINT observation_period_person_id_fkey FOREIGN KEY (person_id) REFERENCES person (person_id);
ALTER TABLE visit_occurrence ADD CONSTRAINT visit_occurrence_person_id_fkey FOREIGN KEY (person_id) REFERENCES person (person_id);
ALTER TABLE condition_occurrence ADD CONSTRAINT condition_occurrence_person_id_fkey FOREIGN KEY (person_id) REFERENCES person (person_id);
ALTER TABLE measurement ADD CONSTRAINT measurement_person_id_fkey FOREIGN KEY (person_id) REFERENCES person (person_id);
ALTER TABLE observation ADD CONSTRAINT observation_person_id_fkey FOREIGN KEY (person_id) REFERENCES person (person_id);
ALTER TABLE specimen ADD CONSTRAINT specimen_person_id_fkey FOREIGN KEY (person_id) REFERENCES person (person_id);
ALTER TABLE procedure_occurrence ADD CONSTRAINT procedure_occurrence_person_id_fkey FOREIGN KEY (person_id) REFERENCES person (person_id);
ALTER TABLE files ADD CONSTRAINT files_assay_id_fkey FOREIGN KEY (assay_id) REFERENCES assay (assay_id);
ALTER TABLE assay_to_specimen ADD CONSTRAINT assay_to_specimen_assay_id_fkey FOREIGN KEY (assay_id) REFERENCES assay (assay_id);
ALTER TABLE assay_to_specimen ADD CONSTRAINT assay_to_specimen_specimen_id_fkey FOREIGN KEY (specimen_id) REFERENCES specimen (specimen_id);
ALTER TABLE assay_input_file ADD CONSTRAINT assay_input_file_assay_id_fkey FOREIGN KEY (assay_id) REFERENCES assay (assay_id);
ALTER TABLE assay_input_file ADD CONSTRAINT assay_input_file_file_id_fkey FOREIGN KEY (file_id) REFERENCES files (file_id);
ALTER TABLE specimen_relationship ADD CONSTRAINT specimen_relationship_specimen_id_1_fkey FOREIGN KEY (specimen_id_1) REFERENCES specimen (specimen_id);
ALTER TABLE specimen_relationship ADD CONSTRAINT specimen_relationship_specimen_id_2_fkey FOREIGN KEY (specimen_id_2) REFERENCES specimen (specimen_id);
ALTER TABLE specimen_relationship ADD CONSTRAINT specimen_relationship_procedure_occurrence_id_fkey FOREIGN KEY (procedure_occurrence_id) REFERENCES procedure_occurrence (procedure_occurrence_id);
ALTER TABLE condition_occurrence_access ADD CONSTRAINT condition_occurrence_access_condition_occurrence_id_fkey FOREIGN KEY (condition_occurrence_id) REFERENCES condition_occurrence (condition_occurrence_id);
ALTER TABLE condition_occurrence_access ADD CONSTRAINT condition_occurrence_access_access_group_id_fkey FOREIGN KEY (access_group_id) REFERENCES access_groups (id);
ALTER TABLE procedure_occurrence_access ADD CONSTRAINT procedure_occurrence_access_procedure_occurrence_id_fkey FOREIGN KEY (procedure_occurrence_id) REFERENCES procedure_occurrence (procedure_occurrence_id);
ALTER TABLE procedure_occurrence_access ADD CONSTRAINT procedure_occurrence_access_access_group_id_fkey FOREIGN KEY (access_group_id) REFERENCES access_groups (id);
ALTER TABLE measurement_access ADD CONSTRAINT measurement_access_measurement_id_fkey FOREIGN KEY (measurement_id) REFERENCES measurement (measurement_id);
ALTER TABLE measurement_access ADD CONSTRAINT measurement_access_access_group_id_fkey FOREIGN KEY (access_group_id) REFERENCES access_groups (id);
ALTER TABLE observation_access ADD CONSTRAINT observation_access_observation_id_fkey FOREIGN KEY (observation_id) REFERENCES observation (observation_id);
ALTER TABLE observation_access ADD CONSTRAINT observation_access_access_group_id_fkey FOREIGN KEY (access_group_id) REFERENCES access_groups (id);
ALTER TABLE specimen_access ADD CONSTRAINT specimen_access_specimen_id_fkey FOREIGN KEY (specimen_id) REFERENCES specimen (specimen_id);
ALTER TABLE specimen_access ADD CONSTRAINT specimen_access_access_group_id_fkey FOREIGN KEY (access_group_id) REFERENCES access_groups (id);
ALTER TABLE file_access ADD CONSTRAINT file_access_file_id_fkey FOREIGN KEY (file_id) REFERENCES files (file_id);
ALTER TABLE file_access ADD CONSTRAINT file_access_access_group_id_fkey FOREIGN KEY (access_group_id) REFERENCES access_groups (id);
