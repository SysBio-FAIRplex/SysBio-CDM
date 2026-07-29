### 1. Prerequisites
Any machine with `curl` and `jq` (Python optional, for parsing). The CMDGA JSON API needs **no authentication** or login. Only the HTML pages sit behind Cloudflare/React and 403 to scripts — always hit the API, never the web UI.

### 2. Mental model
`hugeamp.org` (CMDKP) serves **summary results**; **`cmdga.org` (CMDGA) serves the actual files** and is an (older) ENCODE/`encoded` portal. The object graph is `Experiment (DSR…) → File (DFF…)`, and `Experiment → Biosample → Donor` for phenotype.

### 3. Endpoint reference
Append `?format=json` to any URL for machine-readable output; results live in `@graph`, the count in `.total`, and filter options in `.facets`.
```bash
curl -sS 'https://cmdga.org/experiments/DSR682903/?format=json' | jq '.accession, (.files|length)'
```

### 4. Finding datasets
Filter a `/search/` on `type=Experiment` with facet fields (`assay_title`, `organ_slims`, `award.project`, `status`), using `limit=0` for facet-only counts and `&field=` to trim the payload.
```bash
curl -sS 'https://cmdga.org/search/?type=Experiment&status=released&organ_slims=kidney&assay_title=single+cell+RNA-seq&format=json&limit=all&field=accession&field=biosample_summary&field=lab.title' | jq -c '.["@graph"][]'
```

### 5. Enumerate before download
Files are embedded in the experiment (`.files[]`) with `href`, `file_size`, `output_type`, and the gate flags `restricted` / `no_file_available` — sum sizes and split open vs. restricted before pulling anything.
```bash
curl -sS 'https://cmdga.org/search/?type=File&dataset=/experiments/DSR682903/&format=json&limit=all&field=restricted&field=no_file_available&field=file_size' \
  | jq '{files:(.["@graph"]|length), restricted:([.["@graph"][]|select(.restricted==true)]|length), total_GB:(([.["@graph"][].file_size]|add)/1e9)}'
```

### 6. Downloading
Each open file's `href` is `/files/DFF…/@@download/…`; `curl -L` follows the 302 to a presigned S3 URL and saves the file. Loop over the hrefs a query returns (no `/batch_download/` on this instance):
```bash
curl -sS 'https://cmdga.org/search/?type=File&dataset=/experiments/DSR682903/&format=json&limit=all&field=href&field=restricted&field=no_file_available' \
  | jq -r '.["@graph"][] | select(.restricted!=true and .no_file_available!=true) | "https://cmdga.org"+.href' \
  | xargs -n1 -P4 curl -sS -L -O -J
```

### 7. Restricted / individual-level tier
Files with `restricted: true` or `no_file_available: true` are the sensitive individual-level tier (raw reads/genotypes) and are stored-but-not-served — they require an MTA / controlled-access request, not a plain download. (Example: `DSR682903` has 0 restricted; many WGS/genotyping experiments will differ.)

### 8. Phenotype ↔ omics linkage
Join clinical/phenotype back to samples through `File → Experiment → Biosample → Donor`; pull the donor record directly or read the donor/biosample columns of the metadata.tsv.
```bash
curl -sS 'https://cmdga.org/human-donors/?format=json&limit=2&field=accession&field=sex&field=age&field=health_status' | jq -c '.["@graph"][]'
```

### 9. Reproducible bulk manifest
For a whole query, the metadata TSV (older **path-form** URL, not `?query`) gives one row per file — including its **File download URL** column — to drive a batch pull. It filters by the path params and scales with scope, so size it first: a lone WGS assay is ~2 KB / 4 files, while a whole assay like snATAC-seq is ~47 MB / ~31k rows.
```bash
curl -sSL 'https://cmdga.org/metadata/type=Experiment&status=released&organ_slims=kidney/metadata.tsv' -o kidney_metadata.tsv
```

### 10. Caveats
Query `status=released` only; single experiments can be large (`DSR682903` ≈ 110 GB), and the presigned S3 links **expire in minutes**, so regenerate the href list right before downloading rather than caching it.

### 11. Reliability / treating it as an endpoint
The API is sound to build against: responses are **deterministic**, it is **versioned** (`curl 'https://cmdga.org/?format=json' | jq .app_version` — pin it), and **self-describing** via `/profiles/?format=json` (JSON Schemas for every object type — standard ENCODE/`snovault`); CORS is open and no auth is needed. Two flags before depending on it in production: downloads redirect to an S3 bucket named **`…-dev`**, and **`TSTSR…` test accessions appear in `status=released` results**, so this may be a staging deployment — confirm the production endpoint with the data provider. There is **no GA4GH DRS** (`/ga4gh/drs/*` → 404); files are fetched only via `@@download`.
