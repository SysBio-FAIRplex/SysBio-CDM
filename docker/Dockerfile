# Development bench image for the AMP synthetic-data + CDM ETL pipeline.
#
# Toolchain only. The repository itself is bind-mounted at runtime (see
# docker-compose.yml at the repo root) so edits on the host and in the
# container are the same files. Nothing about the pipeline is baked in.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# postgresql-client: the load/verify steps shell out to `psql`.
# git: in-container version control.  make: the `make` front door (see amp_synth_etl/Makefile).
RUN apt-get update \
 && apt-get install -y --no-install-recommends postgresql-client git make \
 && rm -rf /var/lib/apt/lists/*

# The pipeline is stdlib-only; pytest is the sole dependency (for tests/).
COPY amp_synth_etl/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

WORKDIR /app/amp_synth_etl
