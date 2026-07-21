#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════════════════════════════
#  ENUMERATED COLUMN GROUPS
#
#  Every column the generator treats specially is named here, EXPLICITLY, ONCE.
#
#  There is NO name matching, NO suffix rule, NO regex and NO column-order inference anywhere in
#  the rule paths. A column not named in this file is drawn from its spec and nothing else is
#  done with it.
#
#  Every name carries the SOURCE TEXT that justifies it, quoted verbatim from the dictionary.
#  A name with no quoted source is an assumption and is marked ASSUMED.
#
#  ── WHY THIS FILE EXISTS ────────────────────────────────────────────────────────────────────
#  The generator used to find its derived scores with a suffix rule:
#      DERIVED_MARK = ("_total_score", "_summary_score", "_sub_score", "_subscore")
#  and find their items by COLUMN ORDER ("the items are the columns just before the total").
#
#  Both are unsound, and the MMSE proves it. Three of its columns end in `_score`:
#
#      mms103_repeat_objects_score      "MMSE - Repeat Three Unrelated Objects Score"   0-3   ITEM
#      mms105_recall_score              "MMSE - Recall Score"                           0-3   ITEM
#      mms104_attention_calculat_score  "MMSE - Attention and Calculation Subtotal"     0-5   AGGREGATE
#
#  Same suffix. Opposite meaning. No name rule can separate them; only reading them can. The
#  suffix rule also missed all four UPDRS sub-totals (they end in a bare `_score`), which were
#  therefore drawn independently of their own items and wrong on ~949 of 950 rows -- while QC,
#  which reads the config the rule produced, reported zero failures. The absence of a rule and
#  the satisfaction of a rule looked identical.
# ══════════════════════════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════════════════════════
#  1. AGGREGATE COLUMNS -- NOT EMITTED
#
#  By specification: sub-totals, sub-scores, sub-domain scores and summary scores are not wanted.
#  The ITEMS are emitted; a consumer sums them. Nothing here is computed, and nothing here is
#  drawn -- these columns simply do not appear in the output.
#
#  Enumerated by reading the `Description` field of every column of every AMP-PD dictionary.
#  The quoted text is that Description.
# ══════════════════════════════════════════════════════════════════════════════════════════════

DROP_AGGREGATE = {
    "UPDRS.csv": [
        "updrs1_ment_behav_mood_score",        # "UPDRS - Mentation, Behavior and Mood Sub-total (UPD145)"   0-16
        "updrs2_adl_score",                    # "UPDRS - Activities of Daily Living Sub-total (UPD146)"     0-52
        "updrs3_motor_examination_score",      # "UPDRS - Motor Examination Sub-total (UPD147)"              0-108
        "updrs4_therapy_complications_score",  # "UPDRS - Complications of Therapy: Sub-total"               0-30
    ],
    "MDS_UPDRS_Part_I.csv": [
        "mds_updrs_part_i_sub_score",            # "MDS-UPDRS Part I Questions 1-6 Summary Sub-Score"        0-24
        "mds_updrs_part_i_pat_quest_sub_score",  # "MDS-UPDRS Part I Patient Questionnaire Q7-13 Summary"    0-24
        "mds_updrs_part_i_summary_score",        # "MDS-UPDRS Part I Summary Score"                          0-48
    ],
    "MDS_UPDRS_Part_II.csv": [
        "mds_updrs_part_ii_summary_score",       # "MDS-UPDRS Part II Summary Score"                         0-52
    ],
    "MDS_UPDRS_Part_III.csv": [
        "mds_updrs_part_iii_summary_score",      # "MDS-UPDRS Part III Summary Score"                        0-132
    ],
    "MDS_UPDRS_Part_IV.csv": [
        "mds_updrs_part_iv_summary_score",       # "MDS-UPDRS Part IV Summary Score"                         0-24
    ],
    "MOCA.csv": [
        "moca_visuospatial_executive_subscore",  # "MOCA: Visuospatial And Executive Subscore"               0-5
        "moca_naming_subscore",                  # "MOCA: Naming Subscore"                                   0-3
        "moca_attention_digits_subscore",        # "MOCA: Attention Forward-Backward Repeat Lists Of Digits" 0-2
        "moca_language_subscore",                # "MOCA: Language Subscore"                                 0-3
        "moca_abstraction_subscore",             # "MOCA: Abstraction subscore ..."                          0-2
        "moca_delayed_recall_subscore",          # "MOCA: Delayed Recall Subscore Uncued"                    0-5
        "moca_orientation_subscore",             # "MOCA: Orientation Subscore"                              0-6
        "moca_total_score",                      # "MOCA Total Score"                                        0-31
        # The two OPTIONAL recall scorings. Not sums -- they are the SAME recall re-scored with a
        # cue. Dropped with the rest of the aggregates: a consumer scoring recall can do so from
        # the items.
        "moca_delayed_recall_subscore_optnl_cat_cue",     # "MOCA: Delayed Recall Subscore Optional Category Cue"
        "moca_delayed_recall_subscore_optnl_mult_choice", # "MOCA: Delayed Recall Subscore Optional Multiple Choice Cue"
    ],
    "MMSE.csv": [
        "mms104_attention_calculat_score",       # "MMSE - Attention and Calculation Subtotal (MMS104)"      0-5
        "mms112_total_score",                    # "MMSE - Total Score (MMS112)"                             13-30
    ],
    "PDQ_39.csv": [
        # Each is "PDQ-39-Total Score-<domain>", 0-100. These are PERCENTAGES -- (sum of the
        # domain's items / that domain's maximum) x 100 -- not sums.
        "pdq39_mobility_score",       # "PDQ-39-Total Score-Mobility"
        "pdq39_adl_score",            # "PDQ-39-Total Score-Activities Of Daily Living (ADL)"
        "pdq39_emotional_score",      # "PDQ-39-Total Score-Emotional Well Being"
        "pdq39_stigma_score",         # "PDQ-39-Total Score-Stigma"
        "pdq39_social_score",         # "PDQ-39-Total Score-Social Support"
        "pdq39_cognition_score",      # "PDQ-39-Total Score-Cognitive Impairment (Cognitions)"
        "pdq39_communication_score",  # "PDQ-39-Total Score-Communication"
        "pdq39_discomfort_score",     # "PDQ-39-Total Score-Bodily Discomfort"
    ],
    "Epworth_Sleepiness_Scale.csv": [
        "ess_summary_score",          # "Epworth Sleepiness Scale (ESS) - Total Score"                       0-24
    ],
    "REM_Sleep_Behavior_Disorder_Questionnaire_Stiasny_Kolster.csv": [
        "rbd_summary_score",          # "RBD Summary Score"                                                  0-13
    ],
    "UPSIT.csv": [
        "upsit_total_score",          # "UPSIT Total Score"                                                  0-40
    ],
    "LBD_Cohort_Clinical_Data.csv": [
        "smell_detail",               # "UPSIT 40 smell test score" -- a CROSS-TABLE copy of upsit_total_score
    ],
}


# ── The look-alikes. These END in `_score`/`_subscore` but are ITEMS. They ARE emitted. ────────
#
#  This list exists so the distinction is on the record. It is not read by
#  the generator -- it is documentation of a decision, and the reason a name rule cannot be used.
#
#  mms103_repeat_objects_score        "MMSE - Repeat Three Unrelated Objects Score"        0-3
#                                     One MMSE task. Not a sum.
#  mms105_recall_score                "MMSE - Recall Score - Repeat Three Objects Again"   0-3
#                                     One MMSE task. Not a sum.
#  moca22_orientation_date_score      "MOCA: 22. Orientation - Date Score"                 0-1
#  moca23_orientation_month_score     "MOCA: 23. Orientation - Month Score"                0-1
#  moca24_orientation_year_score      "MOCA: 24. Orientation - Year Score"                 0-1
#  moca25_orientation_day_score       "MOCA: 25. Orientation - Day Score"                  0-1
#  moca26_orientation_place_score     "MOCA: 26. Orientation - Place Score"                0-1
#  moca27_orientation_city_score      "MOCA: 27. Orientation - City Score"                 0-1
#                                     Six individual questions. moca_orientation_subscore is
#                                     their sum and IS dropped.
#  score_from_booklet_1..4            "UPSIT Score From Booklet #N"                        0-10 each
#                                     The 40 individual smell items are NOT in the dictionary, so
#                                     the booklet scores ARE the item-level data available.
#                                     upsit_total_score (their sum) IS dropped.
#  mod_schwab_england_pct_adl_score   "Modified Schwab And England Percent ADL Score"      0-100
#                                     A single clinician rating on a 0-100% scale. Not a sum of
#                                     anything -- there are no items.
#  path_cerad                         "CERAD score" -- a neuropathology staging value, not a sum.
# ──────────────────────────────────────────────────────────────────────────────────────────────


# ══════════════════════════════════════════════════════════════════════════════════════════════
#  2. AMP-PD -- SMOKING AND ALCOHOL GATES
#
#  A column here is emitted ONLY when its gate column says the subject did the thing. Every name
#  is listed; NONE is matched by prefix.
#
#  Enumerating this table is what showed the prefix rule was unusable:
#    * `smoked_100_more_cigarettes` and the four `cigarettes_*` columns are TOBACCO columns that
#      do NOT start with "tobacco_". A `tobacco_*` prefix would have missed all five.
#    * `smoke_exposure_home` / `_work` / `_other_areas` are SECONDHAND smoke exposure -- a
#      NON-smoker is exposed to it. A `smok*` prefix would have wrongly gated them. They are
#      deliberately NOT in the gate.
#
#  ⚠ SOURCE DEFECT, reported not acted on: the AMP-PD dictionary has these two descriptions
#    SWAPPED --
#      tobacco_current_use        "Indicator of whether in your lifetime subject have smoked 100..."
#      smoked_100_more_cigarettes "Current tobacco use indicator"
#    We emit both as declared and do not silently "fix" the source.
# ══════════════════════════════════════════════════════════════════════════════════════════════

TOBACCO_GATE = {
    "table": "Smoking_and_alcohol_history.csv",
    "gate": "tobacco_ever_used",              # "Indicator of whether subject has ever used tobacco"  Yes;No;Unknown
    "gated_on": "Yes",
    "columns": [
        "tobacco_current_use",                # "Indicator of whether in your lifetime subject have smoked 10[0]..."
        "smoked_100_more_cigarettes",         # "Current tobacco use indicator"
        "tobacco_recent_use",                 # "Tobacco recent use indicator"
        "tobacco_prior_use",                  # "Indicator of the participant's/subject's past regular tobacco..."
        "tobacco_start_age",                  # "Age in years when participant/subject started using tobacco"
        "tobacco_stop_age",                   # "Age in years when participant/subject stopped using tobacco"
        # tobacco_product_type ("Type of tobacco product that has been used") is NOT here: the AMP
        # dictionary declares it String with NO UniqueValues, so it is PARKED and never emitted.
        # Gating a column we do not emit would be a rule that silently does nothing.
        "cigarettes_per_day",                 # "Average number cigarettes smoked daily"
        "cigarettes_packs_per_day",           # "Average number packs of cigarettes smoked daily"
        "cigarettes_per_day_current",         # "Current smokers: average number cigarettes per day?"
        "cigarettes_per_day_past",            # "Past smokers: average number of cigarettes smoked daily?"
    ],
    # NOT gated -- secondhand exposure applies to non-smokers:
    #   smoke_exposure_home, smoke_exposure_work, smoke_exposure_other_areas
    "ordered": [("tobacco_start_age", "tobacco_stop_age")],   # you cannot stop before you start
}

ALCOHOL_GATE = {
    "table": "Smoking_and_alcohol_history.csv",
    "gate": "alcohol_ever_used",              # "Indicator of whether subject has ever used alcohol"  Yes;No;Unknown
    "gated_on": "Yes",
    "columns": [
        "alcohol_current_use",                # "Currentl alcohol use indicator" [sic]
        "alcohol_recent_use",                 # "Participant (subject) alcohol consumption past 12 months"
        "alcohol_prior_use",                  # "Indicator of the participant's/subject's alcohol consumption..."
        "alcohol_start_age",                  # "Age in years when participant/subject started ingesting alcohol"
        "alcohol_stop_age",                   # "Age in years when participant/subject stopped ingesting alcohol"
        "alcohol_use_frequency",              # "The frequency of consumption of alcohol by the participant"
        "alcohol_drinks_daily_range",         # "Alcohol drinking day average drinks consumed range"
        "alcohol_six_more_drinks_frequency",  # "Alcohol consume six or more drinks frequency"
        "alcohol_related_hospitalization",    # "Indicator of whether the participant/subject has been hospit..."
        "alcohol_drinks_day",                 # "How many drinks do you have on an average day?"
        "alcohol_consumed_years",             # "How many years consumed alcohol heavily in the past?"
        "alcohol_consumption_change",         # "Has your alcohol consumption changed over the past 10 years?"
        "alcohol_inc_dec",                    # "Has there been a general increase or decrease in your consum..."
    ],
    "ordered": [("alcohol_start_age", "alcohol_stop_age")],
}


# ══════════════════════════════════════════════════════════════════════════════════════════════
#  3. AMP-CMD / KPMP -- CONDITIONAL COLUMNS
#
#  The KPMP workbook states each condition in plain English in its own `description` cell. The
#  quoted text below IS that cell.
# ══════════════════════════════════════════════════════════════════════════════════════════════

KPMP_DIABETES_GATE = {
    "table": "KPMP_kidney_subject.csv",
    "gate": "mh_diabetes_yn",                 # "Told by provider you have diabetes?"  1=Yes; 0=No; 99=Don't know
    "gated_on": 1,
    "columns": [
        "mh_diabetes_type",                   # "Type of diabetes (if diabetic)"
        "mh_retinopathy_yn",                  # "Diabetic retinopathy / eye disease (if diabetic)"
        "mh_dm_neuropathy_yn",                # "Diabetic neuropathy (if diabetic)"
        "mh_dm_pvd",                          # "Peripheral vascular disease (if diabetic)"
        "diabetes_durationC",                 # "Diabetes duration = np_age - mh_diabetes_age"
    ],
}

KPMP_AKI_GATE = {
    "table": "KPMP_kidney_subject.csv",
    "gate": "sc_disease_type",                # "Which condition applies to this participant?"
    # 1=Diabetic kidney disease (DKD); 2=Hypertensive CKD (H-CKD); 4=AKI Percutaneous Biopsy;
    # 5=AKI Open Biopsy; 6=Diabetic Nephropathy Resistors Percutaneous Biopsy
    "gated_on": [4, 5],                       # the two AKI codes
    "columns": [
        "max_kdigo_scrC",                     # "Maximum KDIGO stage by serum creatinine (AKI only)"
    ],
}

KPMP_PERCUTANEOUS_GATE = {
    "table": "KPMP_kidney_subject.csv",
    "gate": "bp_type",                        # "Biopsy procedure type"  1=Percutaneous; 2=Open
    "gated_on": 1,
    "columns": [
        "bp_guidance",                        # "Procedure guidance (if percutaneous)"
    ],
}


# ══════════════════════════════════════════════════════════════════════════════════════════════
#  4. AMP-RA/SLE (ARK) -- ONE DIAGNOSIS PER PATIENT, AND ITS ASSESSMENT SCORES
#
#  ARK's CLINICAL model context declares these. They live in
#      model_contexts/clinical/ark.clinical_model.csv   (the `DependsOn` column)
#  and again as if/then blocks in
#      model_json_schema/ark.ClinicalMetadataTemplate.schema.json
#
#  These four rules live in the CLINICAL context, not the biospecimen context. Without them the
#  emitted data lets a Sjogren's-disease patient carry a psoriasis severity score,
#  a dermatomyositis severity score AND a vitiligo pattern, all at once.
# ══════════════════════════════════════════════════════════════════════════════════════════════

ARK_DIAGNOSIS_SCORES = {
    "table": "ClinicalMetadataTemplate.csv",
    "gate": "diagnosis",
    "rules": {
        # ARK: DependsOn -- diagnosis == <value> brings <columns>
        "vitiligo":        ["vitiligoPattern",   # vitiligo subtype
                            "VIDA",              # Vitiligo Disease Activity
                            "VASI",              # Vitiligo Area Scoring Index
                            "VETI"],             # Vitiligo Extent Tensity Index
        "psoriasis":       ["PASI"],             # Psoriasis Area and Severity Index
        "dermatomyositis": ["CDASI"],            # Cutaneous Dermatomyositis Disease Area & Severity Index
    },
}

ARK_COMORBIDITY_SCORES = {
    "table": "ClinicalMetadataTemplate.csv",
    "gate": "comorbidities",                  # ARK: "Any diseases ... in addition to `diagnosis`"
    "rules": {
        "diabetes": ["diabetesType"],         # ARK: DependsOn -- comorbidities == 'diabetes' -> diabetesType
    },
}

# ══════════════════════════════════════════════════════════════════════════════════════════════
#  COLUMNS DRAWN ONCE PER SUBJECT
#
#  Keyed by TABLE. Never by a bare column name: the subject-constant cache used to be keyed by
#  bare name and subject state persists ACROSS TABLES, so Adipose_Emont drew `sex` first and
#  FUSION and HYPOMAP then returned Adipose's value without ever consulting their own spec --
#  identical row-for-row, all 40 subjects, using a value set FUSION never declared.
# ══════════════════════════════════════════════════════════════════════════════════════════════

SUBJECT_CONSTANT = {
    # ── AMP-PD ────────────────────────────────────────────────────────────────────────────────
    # Every AMP-PD dictionary is visit-grained (they all carry visit_name/visit_month), so WITHOUT
    # this list every one of these facts would be redrawn at every visit -- a person's education
    # level and their mother's Parkinson's status changing between clinic appointments.
    #
    # GRAIN CANNOT BE INFERRED FROM THE FILE. It is a property of the COLUMN. Split by reading each
    # dictionary's own Description; the quoted text is that Description.
    "Demographics.csv": [
        "age_at_baseline",       # "Age At Baseline"          -- a baseline is fixed by definition
        "sex",                   # "Sex"
        "ethnicity",             # "Ethnicity"
        "race",                  # "Race"
        "education_level_years", # "Education Level Years"
    ],
    "Family_History_PD.csv": [
        "biological_mother_with_pd",   # "Mother Has Or Had Parkinson's Disease" -- parents do not
        "biological_father_with_pd",   # "Father Has Or Had Parkinson's Disease"    change between
        "other_relative_with_pd",      # "Other Relative Has Or Had Parkinson's Disease"   visits
    ],
    "Enrollment.csv": [
        "enrollment_months_after_baseline",        # enrolment happens ONCE
        "informed_consent_months_after_baseline",  # consent is given ONCE
        "study_arm",             # "Cohort (PD, healthy control, ...)" -- the arm you are enrolled in
        "prodromal_category",    # "At-risk for PD individuals..."
    ],
    "LBD_Cohort_Path_Data.csv": [
        "path_cerad",            # "CERAD score"                        -- ONE autopsy, post-mortem
        "path_braak_nft",        # "BRAAK stage for neurofibrillary tangle pathology"
        "path_braak_lb",         # "BRAAK stage for Lewy body pathology"
        "path_dlb_prob",         # "Likelihood of DLB based on McKeith criteria"
    ],
    "PD_Medical_History.csv": [
        # ONE-TIME EVENTS. "months after baseline at which X occurred" cannot be re-answered later.
        "initial_diagnosis",                              # "Initial Diagnosis"
        "age_at_diagnosis",                               # "Age At Parkinson's Disease Diagnosis"
        "diagnosis_type",                                 # "How was diagnosis made?"
        "pd_diagnosis_months_after_baseline",             # when PD was diagnosed
        "change_in_diagnosis",                            # "Change In Diagnosis Indicator"
        "change_in_diagnosis_months_after_baseline",      # when it changed
        "pd_medication_initiation_months_after_baseline", # when medication was first started
        "pd_medication_start_months_after_baseline",
        "surgery_for_parkinson_disease",                  # "Type Of Surgery For Parkinson Disease"
        # NOT here (they are per-visit status, and DO change): most_recent_diagnosis,
        # use_of_pd_medication, on_levodopa, on_dopamine_agonist, on_other_pd_medications,
        # pd_medication_recent_use_months_after_baseline
    ],
    "Smoking_and_alcohol_history.csv": [
        # LIFETIME facts. "Age when the subject STARTED using tobacco" has one answer, forever.
        "tobacco_ever_used",     # "whether subject has EVER used tobacco"
        "tobacco_start_age",     # "Age in years when participant STARTED using tobacco"
        "tobacco_stop_age",      # "Age in years when participant STOPPED using tobacco"
        "tobacco_prior_use",     # "past regular tobacco use"
        "smoked_100_more_cigarettes",
        "alcohol_ever_used",     # "whether subject has EVER used alcohol"
        "alcohol_start_age",     # "Age when participant STARTED ingesting alcohol"
        "alcohol_stop_age",      # "Age when participant STOPPED ingesting alcohol"
        "alcohol_prior_use",     # "alcohol consumption PRIOR to the past 12 months"
        "alcohol_consumed_years",        # "How many years consumed alcohol heavily IN THE PAST?"
        "alcohol_related_hospitalization",  # "HAS BEEN hospitalized" -- a lifetime indicator
        # NOT here (current status, and DOES change between visits): tobacco_current_use,
        # tobacco_recent_use, cigarettes_per_day, cigarettes_packs_per_day,
        # cigarettes_per_day_current, cigarettes_per_day_past, alcohol_current_use,
        # alcohol_recent_use, alcohol_use_frequency, alcohol_drinks_daily_range,
        # alcohol_drinks_day, alcohol_six_more_drinks_frequency, alcohol_consumption_change,
        # alcohol_inc_dec, smoke_exposure_home / _work / _other_areas
    ],
    "Caffeine_history.csv": [
        "caff_drinks_ever_used_regularly",   # "whether subject has EVER used caffeinated drinks"
        # NOT here: caff_drinks_current_use -- "CURRENT regular use", a per-visit status
    ],

    # ── AMP-CMD / AMP-AD / AMP-RA-SLE ─────────────────────────────────────────────────────────
    "Adipose_Emont_subject.csv": [
        "sex",                   # self-reported at enrolment
    ],
    "Hypothalamus_HYPOMAP_subject.csv": [
        "sex",                   # self-reported at enrolment
    ],
    # FUSION_muscle_subject.csv is deliberately absent: its `sex` is DROPPED (its workbook declares
    # no value set for it), so holding it constant would be a rule that does nothing.
    "DiverseCohorts_DataDictionary.pdf": [
        "sex",                   # self-reported at enrolment
        "race",                  # self-reported at enrolment
    ],
    "BiospecimenMetadataTemplate.csv": [
        "program",               # the funding programme the subject was enrolled under
        "project",               # the sub-study within that programme
    ],
    "ClinicalMetadataTemplate.csv": [
        # ARK: "the disease status of an INDIVIDUAL." A property of the person, not of the visit.
        # Redrawn per visit, 31 of 34 individuals changed diagnosis between visits -- 100033 was
        # At-Risk RA, then SLE, then control, then dermatomyositis.
        #
        # WHICH diagnosis a subject gets does not matter: ARK subjects are ONE cohort and are not
        # partitioned by programme. It is drawn from ARK's own value set. What matters is that it
        # never changes, and that the assessment scores correspond to it (ARK_DIAGNOSIS_SCORES).
        "diagnosis",
        "sex",                   # self-reported at enrolment
        "race",                  # self-reported at enrolment
        "ethnicity",             # self-reported at enrolment
        "species",               # Homo sapiens
        "program",               # the funding programme the subject was enrolled under
        "project",               # the sub-study within that programme
        "ageUnits",              # a reporting unit, fixed per record source
        "heightUnits",           # a reporting unit
        "weightUnits",           # a reporting unit
        "comorbidities",         # the subject's standing comorbidity list
        "diabetesType",          # a diagnosis, not a per-visit measurement
        "vitiligoPattern",       # a disease subtype, not an activity score
    ],
}

# Non-decreasing across a subject's visits.
MONOTONE = {
    "ClinicalMetadataTemplate.csv": [
        "age",                   # nobody gets younger between visits
    ],
}

# DEAD RULES from the old flat config/subject_constant.tsv, deliberately NOT carried over. A rule
# that cannot fire is worse than no rule: it looks like protection and is not.
#   individualID   -- listed as subject-constant, but it is a KEY. _key() resolves it before the
#                     constant cache is ever reached, so the rule never ran.
#   sex @ FUSION   -- the column is dropped, so holding it constant does nothing.


# ══════════════════════════════════════════════════════════════════════════════════════════════
#  4b. AMP-AD -- THE ROSMAP COHORT GATE
#
#  AMP-AD's DiverseCohorts is a HARMONISATION LAYER over 14 brain banks. ROSMAP (= the ROS and MAP
#  banks) is one of them, and it is the only one with its own native clinical follow-up and
#  genotype data. So a ROSMAP-only column exists ONLY for a subject whose brain bank is ROS or MAP.
#
#  The person-first rewrite DROPPED this (it lived in cohort.json's `cohort_gates`, keyed by the old
#  table names), so every one of the 150 AMP-AD subjects was carrying ROSMAP's apoe_genotype, educ,
#  msex, spanish, braaksc, ceradsc and cogdx -- though only 28 are in ROS or MAP. It is enumerated
#  here rather than left in a config key the new code no longer reads.
#
#  The list is exactly (columns declared by ROSMAP_subject.csv or ROSMAP_clinical.csv) MINUS
#  (columns declared by DiverseCohorts). `pmi` is declared by BOTH and so is NOT gated.
# ══════════════════════════════════════════════════════════════════════════════════════════════

AMP_AD_ROSMAP_GATE = {
    "program": "AMP-AD",
    "gate": "cohort",              # the brain bank the subject came from
    "gated_on": ["ROS", "MAP"],    # ROS + MAP together ARE ROSMAP
    "columns": [
        "apoe_genotype",   # ROSMAP's own genotyping
        "educ",            # ROSMAP's own education field
        "msex",            # ROSMAP's own sex coding
        "spanish",         # ROSMAP's own ethnicity field
        "age_death",       # ROSMAP-native; DiverseCohorts does not declare it
        "age_first_ad_dx",
        "braaksc",         # ROSMAP's coded Braak
        "ceradsc",         # ROSMAP's coded CERAD
        "cogdx",           # the final clinical cognitive diagnosis
        "age_at_visit",    # ROSMAP clinical follow-up
        "dcfdx",           # ROSMAP clinical follow-up
    ],
}


# ══════════════════════════════════════════════════════════════════════════════════════════════
#  5. TABLES NOT EMITTED
# ══════════════════════════════════════════════════════════════════════════════════════════════

DROP_TABLE = [
    # grain=sample is a value the generator never knew, so these fell into the VISIT branch and
    # got one row per visit per subject: 144 rows over 40 sample IDs -- SIX rows per ID, each
    # with different values. FUSION's has no ID column at all.
    "Adipose_Emont_sample.csv",
    "FUSION_muscle_sample.csv",
    "Hypothalamus_HYPOMAP_sample.csv",
    # 3 of its 22 columns survived (individualID, cohort, BrodmannArea). Carries no information.
    "DiverseCohorts_DataDictionary_ExtNeuropath.pdf",
]


# ══════════════════════════════════════════════════════════════════════════════════════════════
#  6. COLUMNS NOT EMITTED -- a declared derivation we will not compute
#
#  By specification: do not salvage a derivation that is causing problems. Each of these is DECLARED
#  by its source as a function of other columns, and was being drawn independently of them.
#  Rather than compute them, we drop them -- the operands are all emitted, so a consumer can.
# ══════════════════════════════════════════════════════════════════════════════════════════════

DROP_COLUMN = {
    "KPMP_kidney_subject.csv": [
        "disease_categoryC",   # "Condition (derived from sc_disease_type)" -- sc_disease_type IS emitted
        "ckd_stageC",          # "CKD stage / KDIGO risk (CKD or DN-Resistor; from uACR & eGFR)"
        "op_egfrcr",           # "eGFR (CKD-EPI creatinine, 2021)"        -- op_cre, np_age emitted
        "op_egfrcys",          # "eGFR (CKD-EPI cystatin C)"              -- op_cystc emitted
        "op_egfrcrcys",        # "eGFR (CKD-EPI creatinine + cystatin C, 2021)"
        # Three FORMULAS over one blood draw, drawn as three unrelated numbers: within the same
        # patient the creatinine- and cystatin-C-based estimates differed by a mean of 46
        # mL/min/1.73m2 -- the span from normal kidney function to kidney failure.
        "ah_hd_yn",            # "Hemodialysis at any time during AKI hospitalization" -- an OR over
        "ah_crrt_yn",          # "CRRT at any time during AKI hospitalization"          the day series
        "raceC",               # "Race (derived from np_race checkboxes)" -- np_race is NOT in the
                               # workbook, so this is not derivable at all.
    ],
    "FUSION_muscle_subject.csv": [
        "bmi",                 # "Body mass index" (kg/m^2). height and weight are BOTH in this table,
                               # so bmi = weight/(height/100)^2. Drawn instead: wrong on 38/40 rows
                               # (186.4 cm, 66.4 kg -> true 19.1, emitted 54.5).
        "sex",                 # FUSION's workbook declares NO value set for sex. It was being filled
                               # with Adipose's {female, male} via a bare-name cache -- a value set
                               # FUSION never declared.
    ],
    "Adipose_Emont_subject.csv": [
        "bmi",                 # "BMI". No declared range -> generic 0-100 window -> emitted 0.9 to
                               # 97.1, and contradicting its own bmi_group band on 35/40 rows.
    ],
    "BiospecimenMetadataTemplate.csv": [
        "anatomicalSite",      # ARK: "the anatomical site from which the biospecimen was collected."
                               # Drawn uniformly over all 847 FMA terms, uncorrelated with the
                               # specimen: ('synovial tissue', 'Upper lip'). ARK ships no
                               # site-to-specimen crosswalk, so honouring it means INVENTING one.
    ],
}


# ══════════════════════════════════════════════════════════════════════════════════════════════
#  SELF-CHECK -- a duplicate key in any literal above is a HARD ERROR.
#
#  Python takes the LAST duplicate in a dict literal and silently discards the earlier one. That
#  is exactly what happened here: a second "Demographics.csv" entry overwrote the first, so the
#  AMP-PD person-facts (age_at_baseline, education_level_years) were dropped without a word and
#  went on being redrawn at every visit. A list whose entries can vanish in silence is not a
#  contract.
# ══════════════════════════════════════════════════════════════════════════════════════════════
import ast as _ast
import io as _io


def _no_duplicate_keys():
    src = open(__file__, encoding="utf-8").read()
    tree = _ast.parse(src)
    bad = []
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Assign) and isinstance(node.value, _ast.Dict):
            name = getattr(node.targets[0], "id", "?")
            keys = [k.value for k in node.value.keys
                    if isinstance(k, _ast.Constant) and isinstance(k.value, str)]
            for k in {x for x in keys if keys.count(x) > 1}:
                bad.append(f"{name}[{k!r}] is declared {keys.count(k)} times -- "
                           f"Python keeps only the LAST and silently discards the rest")
    if bad:
        raise AssertionError("scripts/enumerated.py: duplicate keys\n  " + "\n  ".join(bad))


_no_duplicate_keys()
