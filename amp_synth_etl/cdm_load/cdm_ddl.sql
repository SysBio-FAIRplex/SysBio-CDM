-- SysBio-CDM DDL — GENERATED STRICTLY FROM resources/sysbio-dbml.dbml (the canonical in-repo schema).
-- SOURCE OF TRUTH = that DBML file ONLY. No database was queried to produce this.
-- See WARNING_sourcingFromOutsideOfRepoIsForbidden.
--
-- Faithful to the DBML, including:
--   * person is a DATA-FREE anchor: gender/race/ethnicity_concept_id + year_of_birth pinned to 0 via CHECK
--     (real demographics belong in GOVERNED observation rows, per the DBML header). The ETL must load
--     person as all-zeros or this CHECK will reject the row.
--   * FKs are "real FKs only" (person / assay / specimen / file / access). *_concept_id columns are
--     INTENTIONALLY NOT foreign-keyed to concept — the DBML declares no such refs.
--   * Record-level access = access_groups + user_access_groups + per-entity <e>_access. The DBML says
--     this is enforced via Postgres ROW-LEVEL SECURITY; the RLS POLICIES are a separate governance step
--     and are NOT created here (this file is structure only).
--   * TYPES: structure/keys/widths are the DBML's. The DBML's VARCHAR(50/60) caps on the SOURCE/VALUE
--     columns (*_source_value, value_as_string, value_source_value, *_source_id) are WIDENED TO TEXT here,
--     because real data exceeds them (a 52-char variable name, a 76-char source cell) and Postgres text
--     has no meaningful length limit (~1 GB) -- so varchar would only ever break the load, never help.
--     This also matches CLAUDE.md's standing "truncate nothing -> TEXT" rule. All other types are the DBML's.

CREATE SCHEMA IF NOT EXISTS cdm;
SET search_path = cdm, public;

-- ===== governance =====
CREATE TABLE cdm.access_groups (
    id                        serial       PRIMARY KEY,
    code                      text         NOT NULL,
    name                      text         NOT NULL,
    description               text,
    program                   text,
    disease_focus             text,
    dul                       text,
    data_access_instructions  text,
    created_at                timestamp(3) NOT NULL
);

CREATE TABLE cdm.user_access_groups (
    user_id                   text         NOT NULL,
    access_group_id           integer      NOT NULL,
    granted_at                timestamp(3) NOT NULL,
    granted_by                text,
    PRIMARY KEY (user_id, access_group_id)
);

-- ===== OMOP core =====
CREATE TABLE cdm.concept (
    concept_id                integer      PRIMARY KEY,
    concept_name              varchar(255) NOT NULL,
    domain_id                 varchar(20)  NOT NULL,
    vocabulary_id             varchar(20)  NOT NULL,
    concept_class_id          varchar(20)  NOT NULL,
    standard_concept          varchar(1),
    concept_code              varchar(50)  NOT NULL,
    valid_start_date          date         NOT NULL,
    valid_end_date            date         NOT NULL,
    invalid_reason            varchar(1)
);

CREATE TABLE cdm.person (
    person_id                 integer      PRIMARY KEY,
    gender_concept_id         integer      NOT NULL,
    year_of_birth             integer      NOT NULL,
    race_concept_id           integer      NOT NULL,
    ethnicity_concept_id      integer      NOT NULL,
    CONSTRAINT person_data_free CHECK (gender_concept_id = 0 AND year_of_birth = 0
                                       AND race_concept_id = 0 AND ethnicity_concept_id = 0)
);

CREATE TABLE cdm.observation_period (
    observation_period_id            integer PRIMARY KEY,
    person_id                        integer NOT NULL,
    observation_period_start_date    date    NOT NULL,
    observation_period_end_date      date    NOT NULL,
    period_type_concept_id           integer NOT NULL
);

CREATE TABLE cdm.visit_occurrence (
    visit_occurrence_id            integer      PRIMARY KEY,
    person_id                      integer      NOT NULL,
    visit_concept_id               integer      NOT NULL,
    visit_start_date               date         NOT NULL,
    visit_start_datetime           timestamp(3),
    visit_end_date                 date         NOT NULL,
    visit_end_datetime             timestamp(3),
    visit_type_concept_id          integer      NOT NULL,
    provider_id                    integer,
    care_site_id                   integer,
    visit_source_value             text,
    visit_source_concept_id        integer,
    admitted_from_concept_id       integer,
    admitted_from_source_value     text,
    discharged_to_concept_id       integer,
    discharged_to_source_value     text,
    preceding_visit_occurrence_id  integer
);

CREATE TABLE cdm.measurement (
    measurement_id                 integer        PRIMARY KEY,
    person_id                      integer        NOT NULL,
    measurement_concept_id         integer        NOT NULL,
    measurement_date               date           NOT NULL,
    measurement_datetime           timestamp(3),
    measurement_time               varchar(10),
    measurement_type_concept_id    integer        NOT NULL,
    operator_concept_id            integer,
    value_as_number                numeric(65,30),
    value_as_concept_id            integer,
    unit_concept_id                integer,
    range_low                      numeric(65,30),
    range_high                     numeric(65,30),
    provider_id                    integer,
    visit_occurrence_id            integer,
    visit_detail_id                integer,
    measurement_source_value       text,
    measurement_source_concept_id  integer,
    unit_source_value              text,
    unit_source_concept_id         integer,
    value_source_value             text,
    measurement_event_id           integer,
    meas_event_field_concept_id    integer
);

CREATE TABLE cdm.observation (
    observation_id                 integer        PRIMARY KEY,
    person_id                      integer        NOT NULL,
    observation_concept_id         integer        NOT NULL,
    observation_date               date           NOT NULL,
    observation_datetime           timestamp(3),
    observation_type_concept_id    integer        NOT NULL,
    value_as_number                numeric(65,30),
    value_as_string                text,
    value_as_concept_id            integer,
    qualifier_concept_id           integer,
    unit_concept_id                integer,
    provider_id                    integer,
    visit_occurrence_id            integer,
    visit_detail_id                integer,
    observation_source_value       text,
    observation_source_concept_id  integer,
    unit_source_value              text,
    qualifier_source_value         text,
    value_source_value             text,
    observation_event_id           integer,
    obs_event_field_concept_id     integer
);

CREATE TABLE cdm.specimen (
    specimen_id                    integer        PRIMARY KEY,
    person_id                      integer        NOT NULL,
    specimen_concept_id            integer        NOT NULL,
    specimen_type_concept_id       integer        NOT NULL,
    specimen_date                  date           NOT NULL,
    specimen_datetime              timestamp(3),
    quantity                       numeric(65,30),
    unit_concept_id                integer,
    anatomic_site_concept_id       integer,
    disease_status_concept_id      integer,
    specimen_source_id             text,
    specimen_source_value          text,
    unit_source_value              text,
    anatomic_site_source_value     text,
    disease_status_source_value    text
);

CREATE TABLE cdm.procedure_occurrence (
    procedure_occurrence_id        integer      PRIMARY KEY,
    person_id                      integer      NOT NULL,
    procedure_concept_id           integer      NOT NULL,
    procedure_date                 date         NOT NULL,
    procedure_datetime             timestamp(3),
    procedure_end_date             date,
    procedure_end_datetime         timestamp(3),
    procedure_type_concept_id      integer      NOT NULL,
    modifier_concept_id            integer,
    quantity                       integer,
    provider_id                    integer,
    visit_occurrence_id            integer,
    visit_detail_id                integer,
    procedure_source_value         text,
    procedure_source_concept_id    integer,
    modifier_source_value          text
);

CREATE TABLE cdm.fact_relationship (
    domain_concept_id_1        integer NOT NULL,
    fact_id_1                  integer NOT NULL,
    domain_concept_id_2        integer NOT NULL,
    fact_id_2                  integer NOT NULL,
    relationship_concept_id    integer NOT NULL,
    PRIMARY KEY (domain_concept_id_1, fact_id_1, domain_concept_id_2, fact_id_2, relationship_concept_id)
);

CREATE TABLE cdm.cdm_source (
    cdm_source_name                 text    PRIMARY KEY,
    cdm_source_abbreviation         text    NOT NULL,
    cdm_holder                      text    NOT NULL,
    source_description              text,
    source_documentation_reference  text,
    cdm_etl_reference               text,
    source_release_date             date    NOT NULL,
    cdm_release_date                date    NOT NULL,
    cdm_version                     text,
    cdm_version_concept_id          integer NOT NULL,
    vocabulary_version              text    NOT NULL
);

-- ===== omics extensions =====
CREATE TABLE cdm.files (
    file_id             integer      PRIMARY KEY,
    file_name           text         NOT NULL,
    current_version     integer,
    assay_id            integer,
    file_role           text,
    study               text,
    "grant"             text,
    array_type          text,
    analysis_type       text,
    biosample_type      text,
    tissue              text,
    cell_type           text,
    species             text,
    processing_status   text,
    file_format         text,
    file_size_bytes     bigint,
    created_on          timestamp(3),
    modified_on         timestamp(3),
    drs_id              text         NOT NULL
);

CREATE TABLE cdm.assay (
    assay_id            integer PRIMARY KEY,
    assay_source_value  text,
    assay_type          text    NOT NULL,
    platform            text    NOT NULL,
    suspension_type     text,
    analyte_type        text,
    analysis_pipeline   text
);

CREATE TABLE cdm.assay_to_specimen (
    assay_id     integer NOT NULL,
    specimen_id  integer NOT NULL,
    PRIMARY KEY (assay_id, specimen_id)
);

CREATE TABLE cdm.assay_input_file (
    assay_id  integer NOT NULL,
    file_id   integer NOT NULL,
    PRIMARY KEY (assay_id, file_id)
);

-- ===== per-entity access junctions =====
CREATE TABLE cdm.procedure_occurrence_access (
    procedure_occurrence_id  integer NOT NULL,
    access_group_id          integer NOT NULL,
    PRIMARY KEY (procedure_occurrence_id, access_group_id)
);

CREATE TABLE cdm.measurement_access (
    measurement_id   integer NOT NULL,
    access_group_id  integer NOT NULL,
    PRIMARY KEY (measurement_id, access_group_id)
);

CREATE TABLE cdm.observation_access (
    observation_id   integer NOT NULL,
    access_group_id  integer NOT NULL,
    PRIMARY KEY (observation_id, access_group_id)
);

CREATE TABLE cdm.specimen_access (
    specimen_id      integer NOT NULL,
    access_group_id  integer NOT NULL,
    PRIMARY KEY (specimen_id, access_group_id)
);

CREATE TABLE cdm.file_access (
    file_id          integer NOT NULL,
    access_group_id  integer NOT NULL,
    PRIMARY KEY (file_id, access_group_id)
);

-- ===== Relationships (real FKs only — exactly the DBML Ref: block) =====
ALTER TABLE cdm.user_access_groups          ADD FOREIGN KEY (access_group_id)         REFERENCES cdm.access_groups(id);
ALTER TABLE cdm.observation_period          ADD FOREIGN KEY (person_id)               REFERENCES cdm.person(person_id);
ALTER TABLE cdm.visit_occurrence            ADD FOREIGN KEY (person_id)               REFERENCES cdm.person(person_id);
ALTER TABLE cdm.measurement                 ADD FOREIGN KEY (person_id)               REFERENCES cdm.person(person_id);
ALTER TABLE cdm.observation                 ADD FOREIGN KEY (person_id)               REFERENCES cdm.person(person_id);
ALTER TABLE cdm.specimen                    ADD FOREIGN KEY (person_id)               REFERENCES cdm.person(person_id);
ALTER TABLE cdm.procedure_occurrence        ADD FOREIGN KEY (person_id)               REFERENCES cdm.person(person_id);
ALTER TABLE cdm.files                       ADD FOREIGN KEY (assay_id)                REFERENCES cdm.assay(assay_id);
ALTER TABLE cdm.assay_to_specimen           ADD FOREIGN KEY (assay_id)                REFERENCES cdm.assay(assay_id);
ALTER TABLE cdm.assay_to_specimen           ADD FOREIGN KEY (specimen_id)             REFERENCES cdm.specimen(specimen_id);
ALTER TABLE cdm.assay_input_file            ADD FOREIGN KEY (assay_id)                REFERENCES cdm.assay(assay_id);
ALTER TABLE cdm.assay_input_file            ADD FOREIGN KEY (file_id)                 REFERENCES cdm.files(file_id);
ALTER TABLE cdm.procedure_occurrence_access ADD FOREIGN KEY (procedure_occurrence_id) REFERENCES cdm.procedure_occurrence(procedure_occurrence_id);
ALTER TABLE cdm.procedure_occurrence_access ADD FOREIGN KEY (access_group_id)         REFERENCES cdm.access_groups(id);
ALTER TABLE cdm.measurement_access          ADD FOREIGN KEY (measurement_id)          REFERENCES cdm.measurement(measurement_id);
ALTER TABLE cdm.measurement_access          ADD FOREIGN KEY (access_group_id)         REFERENCES cdm.access_groups(id);
ALTER TABLE cdm.observation_access          ADD FOREIGN KEY (observation_id)          REFERENCES cdm.observation(observation_id);
ALTER TABLE cdm.observation_access          ADD FOREIGN KEY (access_group_id)         REFERENCES cdm.access_groups(id);
ALTER TABLE cdm.specimen_access             ADD FOREIGN KEY (specimen_id)             REFERENCES cdm.specimen(specimen_id);
ALTER TABLE cdm.specimen_access             ADD FOREIGN KEY (access_group_id)         REFERENCES cdm.access_groups(id);
ALTER TABLE cdm.file_access                 ADD FOREIGN KEY (file_id)                 REFERENCES cdm.files(file_id);
ALTER TABLE cdm.file_access                 ADD FOREIGN KEY (access_group_id)         REFERENCES cdm.access_groups(id);
