"""Shared constants for the Synapse federation POC (extract + load).

The POC clones the AMP-PD reference node's harmonized CDM into Synapse as a
clearly separate, clearly synthetic program so the Query Proxy can federate it
alongside the real AMP-PD and AMP-CMD nodes.
"""

# Rebranding: every AMP-PD program label becomes AMP-ABC.
SOURCE_PROGRAM = "AMP-PD"
TARGET_PROGRAM = "AMP-ABC"

# Added to every entity id (person, specimen, assay, file, visit, clinical row)
# so AMP-ABC rows can never collide with the real AMP-PD rows they were cloned
# from when the proxy merges both into one result. PD ids top out near 1.1e9;
# the offset keeps every id below 2^53 (JSON/JS safe) while clearly separate.
ID_OFFSET = 9_000_000_000

ID_COLUMNS = frozenset(
    {
        "person_id",
        "specimen_id",
        "assay_id",
        "file_id",
        "visit_occurrence_id",
        "clinical_row_id",
    }
)

# Every table, view and folder this POC creates carries this prefix so it is
# distinguishable from other experiments in the shared sandbox project.
PREFIX = "dw_"
SYNAPSE_PROJECT_ID = "syn78779360"
SYNAPSE_FOLDER_NAME = "dw_amp_abc"

# Observation concept that marks a diagnosis record (SysBio ETL convention).
DIAGNOSIS_CONCEPT_ID = 4234469
CASE_QUALIFIER_CONCEPT_ID = 1989833
CONTROL_QUALIFIER_CONCEPT_ID = 44804027
