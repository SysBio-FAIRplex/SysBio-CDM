# Front door for the AMP synthetic-data + CDM ETL pipeline.
# Run `make` (or `make help`) to see everything.
# Override the throwaway DB name on any target:  make load DB=my_db
.DEFAULT_GOAL := help
DB ?= sysbio_cdm_selfcontained

.PHONY: help all generate cdm load verify verify-stories test

help:
	@echo "Pipeline targets (DB name overridable via DB=..., default $(DB)):"
	@echo "  make all       Full pipeline end to end: generation -> CDM delivery -> load -> verify"
	@echo "  make generate  Generate + QC the synthetic source data (scripts 01-04)"
	@echo "  make cdm        Assemble the CDM load SQL (10 orchestrates 06/08/09/11/12)"
	@echo "  make load       Build a throwaway DB and load the CDM (run 'make cdm' first)"
	@echo "  make verify     Verify record-level governance on the loaded DB"
	@echo "  make verify-stories  Run the 13 user-story acceptance queries on the loaded DB"
	@echo "  make test       Run the pytest suite"
	@echo ""
	@echo "PGPASSWORD (and optionally PGHOST/PGPORT/PGUSER) must be set in the environment."

all:
	bash run_pipeline.sh $(DB)

generate:
	python scripts/01_build_specs.py
	python scripts/02_build_tables.py
	python scripts/02c_build_ark.py
	python scripts/02f_build_ark_conditional.py
	python scripts/03_generate.py
	python scripts/04_qc.py

cdm:
	python scripts/10_build_cdm_delivery.py

load:
	bash cdm_load/build_selfcontained.sh $(DB)

verify:
	python scripts/13_verify_governance.py $(DB)

verify-stories:
	python scripts/14_verify_user_stories.py $(DB)

test:
	pytest tests/ -q
