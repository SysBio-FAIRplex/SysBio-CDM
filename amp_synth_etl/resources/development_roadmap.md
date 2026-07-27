# SysBio-CDM — Development Roadmap & Data-Fidelity Tally

**Audience:** platform development team receiving the synthetic hand-off.
**Goal of the hand-off:** synthetic data that resembles the *real* AMP deliverables closely enough —
ideally **by the same file names and column shapes** — that adapting the ingestion to real data is a
*minor* change, not a rewrite.

This doc has two parts: (1) an honest **tally** of which actual files we represent and how faithfully,
and (2) a **roadmap** of action items + open decisions. Nothing here is committed automatically.

---

## 1. How to read this — the current representation model

The pipeline generates a synthetic cohort and loads it into a self-contained **OMOP CDM**. Its
intermediate artifacts live in `output/` as **one uniform set per program**:

```
output/{PROG}_subject.csv   {PROG}_visit.csv   {PROG}_specimen.csv
       {PROG}_assay.csv     {PROG}_file.csv    {PROG}_assay_to_specimen.csv
       {PROG}_assay_input_file.csv                 (PROG ∈ AMP-AD / AMP-PD / AMP-CMD / AMP-RA-SLE)
```

These are **CDM-oriented**, not facsimiles of the source deliverables. So today:

- **Content fidelity** (fields, assay types, specimen lineage, disease/cohort) — **partial-to-good.**
- **Form fidelity** (actual file *names* and per-substudy/per-assay *decomposition*) — **not a design
  goal yet.** A team handed our output sees `AMP-AD_subject.csv`, never `ROSMAP_clinical.csv` +
  `AMP-AD_DiverseCohorts_individual_metadata.csv`.

**Fidelity legend:** ●●● faithful · ●●○ partial · ●○○ shape-only · ✗ absent.
**Name match** = does a synthetic file carry the real deliverable's filename? (Currently ✗ everywhere.)

---

## 2. Fidelity tally, by program

### AMP-AD — 9 real files across **3 sub-studies**; 58 CDEs / 12 instruments
Real data is split by sub-study, each with its own named metadata files:

| Real deliverable file | Our synthetic stand-in | Name | Content | Gap |
|---|---|---|---|---|
| `ROSMAP_clinical.csv` | fields folded into `AMP-AD_subject.csv` (msex, educ, spanish, cogdx, braaksc, ceradsc, apoe, age_death, age_first_ad_dx) | ✗ | ●●○ | not emitted as a ROSMAP-named file |
| `AMP-AD_DiverseCohorts_individual_metadata.csv` | folded into `AMP-AD_subject.csv` (amyThal, amyCerad, Braak, ADoutcome, mayoDx) | ✗ | ●●○ | DiverseCohorts + ROSMAP are **blended into one file** |
| `ROSMAP_biospecimen_metadata.csv` · `AMP-AD_DiverseCohorts_biospecimen_metadata.csv` · `MIT_ROSMAP_Multiomics_biospecimen_metadata.csv` | `AMP-AD_specimen.csv` (one unified file) | ✗ | ●●○ | 3 real files → 1 synthetic; sub-study identity lost |
| `ROSMAP_assay_scrnaSeq_metadata.csv` · `AMP-AD_DiverseCohorts_assay_multiome_metadata.csv` · `MIT_ROSMAP_Multiomics_assay_snRNAseq_metadata.csv` | `AMP-AD_assay.csv` + fastq catalog + pseudobulk `.h5` | ✗ | ●●○ | assay *types* present (scRNA/snRNA/multiome/ATAC); not per-substudy files |
| `AMP-AD_DiverseCohorts_AMP-AD_1.0_WGS_biospecimen_metadata.csv` | — | ✗ | ✗ | **no WGS** generated at all |

### AMP-PD — 4 biospecimen-analysis files + **28 clinical instruments** (415 CDEs — richest program)

| Real deliverable | Our synthetic stand-in | Name | Content | Gap |
|---|---|---|---|---|
| 28 clinical dictionaries (MDS-UPDRS I–IV, MMSE, MOCA, DaTSCAN, Epworth, PDQ-39, UPSIT, Smoking/alcohol, …) | 415 CDEs → observations/measurements | ✗ | ●●● | strongest clinical coverage; not emitted as per-instrument files |
| `Biospecimen_analyses_SomaLogic_plasma.csv` | `AMP-PD_proteomics_matrix.parquet` (thousands-shape) | ✗ | ●●○ | represented as a matrix, not the SomaLogic-named file |
| `Biospecimen_analyses_CSF_abeta_tau_ptau.csv` | — | ✗ | ✗ | **no CSF biomarker** data |
| `Biospecimen_analyses_CSF_beta_glucocerebrosidase.csv` · `_other.csv` | — | ✗ | ✗ | absent |
| *(single-cell brain omics)* | fastq/`.h5` catalog exists but **PD has no harmonized HDF5** | ✗ | ●○○ | PD omics = proteomics only |

### AMP-CMD — ~24 CMDGA (ENCODE-style) model files; 62 CDEs / 9 instruments

| Real deliverable | Our synthetic stand-in | Name | Content | Gap |
|---|---|---|---|---|
| `donor.tsv` · `biosample.tsv` | `AMP-CMD_subject.csv` · `AMP-CMD_specimen.csv` | ✗ | ●●○ | unified, renamed |
| `genomic_experiments.tsv` · `molecular_library.tsv` · `replicates.tsv` · `pipelines.tsv` | `AMP-CMD_assay.csv` | ✗ | ●○○ | assay concept only; not the CMDGA experiment model |
| `fragments.tsv` · `barcodes.tsv` · `features.tsv` · `peak_calls.tsv` · `tagalign_file.tsv` · `pairs_file.tsv` · `genetranscript_quantifications.tsv` | fastq catalog + pseudobulk `.h5` (fnih-hypothalamus shape) | ✗ | ●○○ | **ENCODE processed-file model not represented** |
| `cmd_value_set_schema.json` **disease** value set (DKD, HKD, diabetes) | — (all donors `Normal`) | ✗ | ✗ | **No real CMD disease data** — the value set is schema-only (no participant diagnoses); `adj_primary_dxC` disabled |

### AMP-RA-SLE (ARK) — schema-driven model, ~15 templates + annotation maps; 20 CDEs / 7 instruments

| Real deliverable (ARK templates) | Our synthetic stand-in | Name | Content | Gap |
|---|---|---|---|---|
| `ark.ClinicalMetadataTemplate` · `ark.BiospecimenMetadataTemplate` | `AMP-RA-SLE_subject.csv` · `_specimen.csv` (with `parentBiospecimenID` lineage) | ✗ | ●●○ | diagnosis aligned to ARK source values |
| `ark.{ScRNASeq,SnRNASeq,BulkRNASeq,CyTOF,SpatialImaging,Olink}AssayMetadataTemplate` | `AMP-RA-SLE_assay.csv` + fastq/`.fcs` catalog + proteomics matrix + pseudobulk `.h5` | ✗ | ●●○ | **broadest assay-type coverage** of any program |
| `ark.{SnATACseq,BulkATACSeq,ScVDJSeq}…Template` | — | ✗ | ✗ | no snATAC / bulkATAC / VDJ |
| `annotation_maps/` (diagnosis-DOID, biospecimenType-BRENDA, CL-cellType) | curated_concept sqlite (our own) | ✗ | ●●○ | ARK ships exact concept maps we could adopt |

---

## 3. Scorecard

| Dimension | State | Note |
|---|---|---|
| Clinical field coverage (CDEs) | **557** total — PD 415 · CMD 62 · AD 58 · RA-SLE 20 | 256 approved mappings load a subset into the CDM |
| Assay-type coverage | Good | scRNA/snRNA/bulkRNA/ATAC/multiome/CyTOF/spatial/proteomics all appear |
| Disease/cohort classification | AD ●●● · RA-SLE ●●● · PD ●●○ · **CMD ✗** | CMD has **no real disease data** — kidney value-set is schema-only; hypothalamus omics is a separate normal-reference atlas; `adj_primary_dxC` disabled |
| **File-name fidelity** | **✗ across all 4 programs** | the core gap for the platform hand-off |
| Sub-study decomposition (AD 3, PD analyses, CMD CMDGA, ARK templates) | **collapsed to one uniform set** | real hand-off is many named files |
| Vestigial `parked` flag in `cde_dictionary` | **109 rows still `parked=true`** | non-gating (manual_approval is the only gate; 256/256 mappings approved) but misleading — should be cleaned |

**Bottom line:** we represent *what the data says* reasonably well; we do **not** yet represent *what
the files look like*. Handed to the platform team today, the field content would be recognizable but
every filename and file boundary would differ.

---

## 4. Re-rendering, fidelity testing, and scale

### 4.1 Is the re-render "just re-organizing"? — mostly yes
The row data **and the sub-study routing key already exist.** Proof: `AMP-AD_subject.csv` already carries
a `cohort` column with the real contributing sites — `ROS` + `MAP` = **ROSMAP** (61 participants here),
while `Mayo Clinic / Mt Sinai / Emory / Banner / UPenn / …` = **DiverseCohorts** sites. So splitting AD
into `ROSMAP_clinical.csv` vs `AMP-AD_DiverseCohorts_individual_metadata.csv` is a filter on data we
already generate. (MIT_ROSMAP_Multiomics = the ROSMAP participants carrying multiome assays — also
derivable.)

Beyond the pure re-org, three **bounded** tasks remain — none need new synthetic participants:
1. **Column crosswalk** per target file: our internal column → real header (+ order). Source of truth is
   already in-repo — ARK ships exact `.csv` templates; DiverseCohorts has a parsed dictionary; ROSMAP a
   codebook; CMD a value-set schema.
2. **Value re-encoding** where our stored value differs from the real coded token (bounded by the value set).
3. **Missing columns** — real files will list fields we never synthesized; they surface as blanks and
   become the fidelity **gap list** (an output of the work, not a blocker).

Net: a **declarative per-file map + a small emitter.** The only real thinking is the maps, and the maps
are dictated by files we already hold.

### 4.2 Fidelity criteria — how we prove "high-fidelity representation"
A repeatable scorecard per (real file ↔ emitted file) pair — most of it buildable **now** from the
in-repo schemas; the distributional checks light up when the real data comes back. Proposed
`scripts/15_fidelity_report.py`:

- **Structural (schema truth, available today):** every real file has an emitted counterpart *by name*;
  column-name **set and order** match (report missing/extra); dtype per column matches; required fields
  present where the template marks them required.
- **Semantic (value truth):** **zero out-of-vocabulary values** (every categorical ∈ the real value set —
  ARK `annotation_maps/`, DiverseCohorts value sets, `cmd_value_set_schema.json`); numerics within real
  range; **distributional similarity** (needs real data — categorical proportions within tolerance,
  continuous via quantiles; closes the loop with `inputs/fidelity_distributions.json`, which already
  *drives* generation); referential integrity across participant↔biospecimen↔assay↔file keys.
- **Scale:** participant count within the target band (§4.3); per-datatype coverage ≥ testing floor;
  cardinality bands hold (proteomics **thousands per file**, never one file per patient).

**Bar to declare pass:** 100% filename + column-name match, **zero** out-of-vocab values, numerics in
range, keys 100% resolvable, and (with real data) distributions within tolerance.

### 4.3 Scale — match the real N, and floor the sparse types
The current cohort is a **small sample**, not the platform-scale dataset:

| Program | Now | Real target | Thinnest data type now |
|---|---|---|---|
| AMP-AD | 150 | *(bring from program)* | ~30/type (balanced) |
| AMP-PD | 274 | *(bring — real is ~10k-scale)* | SomaLogic 201; **no single-cell** |
| AMP-CMD | 42 | *(bring)* | bulkRNA 14 / snRNA 12 |
| AMP-RA-SLE | 34 | *(bring)* | every type ~13–17 |

Two knobs, kept **separate and labelled** so downstream isn't misled:
- **Realistic mode** — N and per-type proportions matched to the real dataset (representativeness).
- **Testing/viz mode** — a per-datatype participant **floor** (over-sample sparse assays like RA-SLE VDJ
  or CMD snRNA up to e.g. ≥50) so every modality is populated enough for QA and dashboards, even where
  that over-represents vs. reality.

Generation is deterministic (SHA-256-seeded), so N is a **config knob** — but changing it reshuffles the
whole cohort, so the determinism **golden test must be re-frozen** on any scale change, and each build
should record which mode/N it used.

---

## 5. Roadmap — action items (ordered by impact-to-effort)

1. **Deliverable-emulation rendering layer** *(highest impact for the stated goal).* Add a step that
   renders the existing synthetic cohort out under the **real filenames + column headers**. Start where
   the schema is handed to us for free: **ARK templates** (RA-SLE — exact `.csv` templates in
   `inputs/amp_dictionaries/ark/data_model-main/model_templates/`) and **AD ROSMAP/DiverseCohorts**
   (split `AMP-AD_subject.csv` → `ROSMAP_clinical.csv` + `AMP-AD_DiverseCohorts_individual_metadata.csv`).
   No new synthetic *data* needed — it's a re-projection of what we already generate.
2. **CMD disease — acquire real data (do NOT classify from the value set).** There is no real CMD
   participant diagnosis data: the CMDGA `donor.tsv`/`biosample.tsv` are empty schema templates and
   `cmd_value_set_schema.json` is only a list of allowed values. The one real CMD dataset is the
   fnih-hypothalamus normal-reference atlas (11 donors, all `normal`), which shares no participants
   with any kidney cohort. CMD stays unclassified (`adj_primary_dxC` disabled) until real
   participant-level diagnosis data arrives.
3. **Close named omics gaps** (per program, cheapest first): AD **WGS** biospecimen; PD **CSF
   biomarker** files (abeta/tau/ptau, glucocerebrosidase); RA-SLE **snATAC / bulkATAC / VDJ**; CMD
   **CMDGA processed-file model** (fragments/peak_calls/tagalign/barcodes/features) — the largest lift.
4. **RA-SLE string-only diagnoses.** Map osteoarthritis, cutaneous lupus erythematosus, psoriatic
   arthritis once concept_ids are provided (Open Decision D) — they're real ARK source values.
5. **Remove the vestigial `parked` field** (109 rows) from `cde_dictionary.jsonl`/`.tsv` so the only
   visible gate is `manual_approval`, matching the actual loader behavior.
6. **Re-freeze the determinism golden test** (`tests/`, stale after generation changes) and keep the
   14-story acceptance gate green (`make verify-stories`).

## 6. Open decisions (need your / the team's input)

- **A. Do we emit real-named deliverable files at all?** If yes, this reframes the pipeline from
  "CDM loader" to "CDM loader **+** source-like emitter." (Recommended: yes — it's what makes the
  hand-off low-friction.)
- **B. Model sub-studies separately or keep unified?** AD is really ROSMAP + DiverseCohorts +
  MIT_ROSMAP_Multiomics; today they're one program. Splitting improves fidelity but multiplies files.
- **C. CMD disease:** there is no real CMD participant diagnosis data (kidney value set is schema-only;
  the real omics is a separate normal hypothalamus atlas). Leave CMD unclassified (current, honest), or
  source real CMD participant-level diagnosis data before classifying?
- **D. Three RA-SLE concept_ids** for OA / cutaneous lupus / psoriatic arthritis — provide, or leave
  string-only?
- **E. Omics gap scope:** which of {AD-WGS, PD-CSF, RA-SLE-ATAC/VDJ, CMD-CMDGA-model} are in scope vs.
  explicitly out of scope for the synthetic set?
- **F. What is "the deliverable"?** the OMOP CDM, realistically-named source-like files, or both? This
  decides whether item #1 is the top priority.
- **G. Real target N per program** — source of truth for participant counts (bring from each program, or
  read from the real data when it returns).
- **H. Testing/viz floor** — the minimum participants-per-datatype for over-sampling sparse modalities.
- **I. One build or two?** — ship a single realistic build, or both a realistic and a floor-boosted
  testing/viz build (each clearly labelled with its mode + N).
- **J. Brain-bank / contributing-institution entities.** AD `cohort` mixes study cohorts (ROS, MAP) with
  brain banks (Mt Sinai Brain Bank, NY Brain Bank, Banner, Mayo Clinic, Biggs Institute Brain Bank, …),
  and `dataContributionGroup` names research groups (Columbia, Emory, Mayo, MSSM, Rush). How should these
  be modelled — first-class entities (OMOP `care_site`/`location`, or a governed institution dimension)
  vs. left as source values? Institutions recur across programs (ARK / CMD sites), so a shared
  institution registry — a natural fit for the pre-ETL **harmonization layer** (`harmonization/`) — may
  be warranted for provenance/governance. Also decide whether `cohort` (study group) and
  `dataContributionGroup` (contributing bank) are distinct dimensions.

## 7. Harmonization layer (`harmonization/`)
The pre-ETL flat harmonization layer — normalize every source's representation of a variable to one
layer, then ETL that. Seeded this session with `harmonization/variable_crosswalk.tsv` (the `sex`/`msex`
case, tracked by variable × program × file × column) and `harmonization/README.md`. **Action:** extend
the registry to the other multi-representation variables (`race`, `ethnicity`, `diagnosis`, age units,
brain-bank/institution names — see decision J) and have the ETL read it
as the single source of truth.
