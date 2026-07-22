"""
Omics extension generation for the SysBio-CDM (specimen / assay / file + lineage edges).
Scope: AMP-AD + AMP-RA-SLE.

Mirrors gen/lineage.py: deterministic integer surrogate ids, parents-before-children. AMP-AD
specimen + assay/file fields draw from the REAL AMP-AD (DiverseCohorts/ROSMAP) distributions in
inputs/fidelity_distributions.json via fidelity.categorical (legal set = the distribution's own
values). AMP-RA-SLE assay/file frequencies are ASSUMED (no real RA/SLE omics data exists in-repo).
These rows are emitted as extra output CSVs OUTSIDE 03_generate's model-driven grain loop; the CDM
render (scripts/11_render_extensions.py) maps them to cdm.specimen/assay/files/junctions.

IDs are deterministic and used directly as CDM surrogate PKs (no DB sequence needed):
    specimen_id : AMP-AD  = pid*100 + seq ;  AMP-RA-SLE = the ARK biospecimenID (already pid*100+seq)
    assay_id    = pid*10000  + aseq
    file_id     = pid*1000   + fseq
  All three are INTEGER (int4) surrogate PKs and their bands stay DISJOINT so fact_relationship can
  reference them unambiguously: specimen < 1.01e7  <  file < 1.01e8  <  assay < 1.01e9  <  int4 max.
"""
import fidelity

# ---- helpers: draw from the real distribution's own value set, else a ASSUMED fallback ----
def _legal(var, fallback):
    fd = fidelity.DIST.get(var)
    return list(fd["values"].keys()) if fd and fd.get("values") else list(fallback)

def _cat(var, fallback, rng):
    return fidelity.categorical(var, _legal(var, fallback), rng)

# ASSUMED assay technologies per program (grounded in the ARK assay families + real AMP-AD metadata).
AD_ASSAYS    = ["snRNAseq", "scRNAseq", "snATACseq", "bulkRNAseq", "10x Multiome"]
RASLE_ASSAYS = ["scRNAseq", "snRNAseq", "bulkRNAseq", "CyTOF", "Olink Explore HT", "Visium"]

# technology -> (dataType[assay_type], analyte_type, suspension_type). Grounded in ARK assay-dataType.csv.
ASSAY_META = {
    "snRNAseq":       ("transcriptomics", "RNA",     "single-nucleus"),
    "scRNAseq":       ("transcriptomics", "RNA",     "single-cell"),
    "snATACseq":      ("epigenomics",     "DNA",     "single-nucleus"),
    "bulkRNAseq":     ("transcriptomics", "RNA",     "bulk"),
    "10x Multiome":   ("multimodal",      "RNA+DNA", "single-nucleus"),
    "CyTOF":          ("cytometry",       "protein", "single-cell"),
    "Olink Explore HT": ("proteomics",    "protein", "bulk"),
    "Visium":         ("transcriptomics", "RNA",     "spatial"),
}

# ---- curated pseudobulk cell types (small + high-fidelity). AMP-AD labels are the REAL AMP-AD data-model
# vocabulary: inputs/amp_dictionaries/ad/data_models/BiospecimenMetadataTemplate.json `cellType` enum.
# AMP-RA-SLE from the ARK cell ontology. Single-cell/nucleus RNA & ATAC -> ONE pseudobulk matrix PER cell type.
PSEUDOBULK_CELLTYPES = {
    "AMP-AD":     ["microglia", "astrocytes", "oligodendrocyte", "GLUtamatergic neurons", "GABAergic neurons"],
    "AMP-RA-SLE": ["synovial fibroblast", "T cell", "B cell", "monocyte"],
}
HARMONIZED_TISSUE = {"AMP-AD": "postmortem brain", "AMP-RA-SLE": "synovial tissue"}  # biosample_type on harmonized files
SINGLE_CELL_TECH  = {"snRNAseq", "scRNAseq", "snATACseq", "10x Multiome"}            # RNA/ATAC pseudobulked per cell type
_BLOOD_CT = ["monocyte", "T cell", "B cell", "NK cell", "peripheral blood mononuclear cell"]  # clean immune set

def _analysis_types(tech):
    if tech == "10x Multiome": return ["RNA", "ATAC"]        # cookbook: one assay -> RNA + ATAC files
    if "ATAC" in tech:         return ["ATAC"]
    if "RNA" in tech:          return ["RNA"]
    if tech == "CyTOF":        return ["cytometry"]
    if tech.startswith("Olink"): return ["proteomics"]
    if tech == "Visium":       return ["spatial"]
    return ["other"]

# file format by role/modality (ASSUMED; from the ARK fileFormat enum + cookbook usage).
def _out_format(atype):
    return "HDF5" if atype in ("RNA", "ATAC", "spatial") else ("fcs" if atype == "cytometry" else "parquet")

# ASSUMED size bands per format (bytes) — realistic order of magnitude, deterministic per file.
_SIZE = {"fastq": (2_000_000_000, 90_000_000_000), "HDF5": (200_000_000, 3_000_000_000),
         "fcs": (50_000_000, 400_000_000), "parquet": (10_000_000, 500_000_000)}
def _size(fmt, rng):
    lo, hi = _SIZE.get(fmt, (1_000_000, 100_000_000))
    return rng.randint(lo, hi)


def specimens_ad(rng, pid, visits):
    """AMP-AD specimens: autopsy brain (+ sometimes blood), drawn from the real distributions.
    ASSUMED: 1-3 specimens per subject (AD is largely single-timepoint / autopsy)."""
    vis = visits[0][0] if visits else "M0"
    out, seq = [], 0
    for _ in range(rng.randint(1, 3)):
        seq += 1
        organ  = _cat("organ", ["brain", "blood"], rng)
        # organ-coherent tissue + cell type: the marginal fidelity dists pool across organs, so a
        # bare draw yields nonsense like a 'blood' organ with a brain tissue -- condition on organ. ASSUMED.
        t_legal = _legal("tissue", [organ])
        if organ == "blood":
            tissue = "blood"
            ct = _BLOOD_CT[rng.randrange(len(_BLOOD_CT))]   # clean immune set (nonsense CL terms dropped)
        else:
            brain = [t for t in t_legal if t.strip().lower() != "blood"] or [organ]
            tissue = fidelity.categorical("tissue", brain, rng)
            ct = "microglia" if rng.random() < 0.25 else ""   # most AD brain is bulk (no cell type)
        site   = _cat("BrodmannArea", ["NA"], rng) if organ == "brain" else tissue
        out.append({
            "participant_id": pid, "specimen_id": pid * 100 + seq,
            "visit_name": vis, "organ": organ,
            "specimen_source_value": tissue, "anatomic_site_source_value": site,
            "cell_type": ct,
            "nucleic_acid_source": _cat("nucleicAcidSource", ["bulk cell"], rng),
            "sample_status": _cat("sampleStatus", ["frozen"], rng),
            "is_post_mortem": _cat("isPostMortem", ["TRUE"], rng)})
    return out


def _raw_files(tech):
    """The PER-SAMPLE raw files a wet-lab assay yields (realistic count + format). Olink proteomics is
    PLATE-level (one file spans a whole plate) so it yields NO per-sample file -- see cohort_files()."""
    if tech.startswith("Olink"):   return []                                  # plate-level -> cohort_files
    if tech == "CyTOF":            return [("", "fcs")]                        # one FCS per sample
    if tech == "Visium":           return [("R1", "fastq"), ("R2", "fastq")]  # spatial seq, paired
    if tech == "bulkRNAseq":       return [("R1", "fastq")]                    # bulk, single file
    return [("R1", "fastq"), ("R2", "fastq")]                                 # single-cell/nucleus, paired


def assays_and_files(rng, pid, prog, specimens):
    """Per person: specimens -> assay(s) + their PER-SAMPLE RAW files + wet-lab usage edges.

    Only per-SAMPLE files are minted here (raw fastq per sequencing library, one FCS per cytometry
    sample) -- these are legitimately one-per-sample. The AGGREGATE / plate-level files (Olink NPX
    plates, harmonized matrices) are NOT one-per-assay; they span the whole cohort and are minted once
    by cohort_files(). `specimens` = list of {specimen_id, specimen_source_value, cell_type, organ,...}.
    Returns (assays, files, assay_to_specimen). ASSUMED which specimens get assayed."""
    assays, files, a2s = [], [], []
    if not specimens:
        return assays, files, a2s
    pool = AD_ASSAYS if prog == "AMP-AD" else RASLE_ASSAYS
    aseq = fseq = 0
    for sp in specimens:
        if rng.random() > 0.6:                      # ASSUMED: ~60% of specimens are assayed
            continue
        aseq += 1
        tech = pool[rng.randrange(len(pool))]
        dtype, analyte, suspension = ASSAY_META.get(tech, ("other", "", ""))
        platform = _cat("platform", ["Illumina NovaSeq 6000"], rng)
        assay_id = pid * 10000 + aseq
        assays.append({
            "participant_id": pid, "assay_id": assay_id,
            "assay_source_value": tech, "assay_type": dtype, "platform": platform,
            "suspension_type": suspension, "analyte_type": analyte,
            "analysis_pipeline": f"{tech}:{platform}"})
        a2s.append({"assay_id": assay_id, "specimen_id": sp["specimen_id"]})   # wet-lab usage edge
        tissue = sp.get("specimen_source_value") or ""
        tclean = tech.replace(" ", "")
        for suffix, fmt in _raw_files(tech):        # per-SAMPLE raw file(s); files.assay_id = producing assay
            fseq += 1
            fid = pid * 1000 + fseq
            tag = f"_{suffix}" if suffix else ""
            ext = f"{fmt}.gz" if fmt == "fastq" else fmt
            files.append({"participant_id": pid, "file_id": fid, "assay_id": assay_id,
                          "file_name": f"{prog}_{tclean}_{sp['specimen_id']}{tag}.{ext}",
                          "file_role": "source_input", "analysis_type": "raw", "file_format": fmt,
                          "biosample_type": sp.get("organ") or tissue, "tissue": tissue,
                          "cell_type": sp.get("cell_type") or "", "species": "Homo sapiens",
                          "study": prog, "grant": prog,
                          "file_size_bytes": _size(fmt, rng), "drs_id": f"drs://sysbio/{fid}"})
    return assays, files, a2s


# Cohort/plate-level file-id band -- disjoint from specimen (<1.01e7), per-person file (<1.01e8) and
# assay (<1.01e9). Each program gets a 2e6-wide slot; cohort files per program are few (< a few hundred).
_COHORT_FILE_BASE = {"AMP-PD": 150_000_000, "AMP-AD": 152_000_000,
                     "AMP-CMD": 154_000_000, "AMP-RA-SLE": 156_000_000}
_OLINK_PLATE = 88   # ASSUMED samples per Olink plate -- one NPX file spans the whole plate (many participants)


def cohort_files(rng, prog, assays):
    """Files that span MANY assays -- NOT one per assay -- shaped to match what each output IS in reality:
      * proteomics (Olink)         -> plate-level NPX file(s) (~88 samples/plate; one file, many participants)
      * single-cell/nucleus RNA/ATAC -> one harmonized PSEUDOBULK HDF5 matrix PER cell type (multi-specimen),
        over a curated tissue-specific cell-type set. This is the real shape of harmonized single-cell
        deliverables (SEA-AD / AMP-AD pseudobulk are organized by cell type), and it is what the cohort-
        builder user stories query (e.g. 'pseudobulked microglia HDF5').
      * bulk RNAseq / spatial      -> one aggregated matrix per modality (no cell type)
    Every contributing assay -> the shared file via assay_input_file (M:N). The shared file has
    assay_id = NULL (no single producing assay); it is governed by files.study. Deterministic: file ids
    increment within the program's cohort-file band; cell types are a fixed curated list."""
    files, aif = [], []
    fid = _COHORT_FILE_BASE.get(prog, 158_000_000)
    tissue    = HARMONIZED_TISSUE.get(prog, "pooled")
    celltypes = PSEUDOBULK_CELLTYPES.get(prog, [])

    # bucket each assay's modalities: single-cell RNA/ATAC (split by cell type) vs bulk/spatial vs proteomics
    sc_by_mod, bulk_by_mod, proteomics = {}, {}, []
    for a in assays:
        tech = a["assay_source_value"]
        for atype in _analysis_types(tech):
            if atype == "proteomics":
                proteomics.append(a["assay_id"])
            elif tech in SINGLE_CELL_TECH and atype in ("RNA", "ATAC"):
                sc_by_mod.setdefault(atype, []).append(a["assay_id"])
            else:
                bulk_by_mod.setdefault(atype, []).append(a["assay_id"])

    def _emit(name, role, atype, fmt, biosample, cell_type, aids):
        nonlocal fid
        fid += 1
        files.append({"participant_id": "", "file_id": fid, "assay_id": "", "file_name": name,
                      "file_role": role, "analysis_type": atype, "file_format": fmt,
                      "biosample_type": biosample, "tissue": biosample, "cell_type": cell_type,
                      "species": "Homo sapiens", "study": prog, "grant": prog,
                      "file_size_bytes": _size(fmt, rng), "drs_id": f"drs://sysbio/{fid}"})
        for aid in aids:
            aif.append({"assay_id": aid, "file_id": fid})

    # proteomics -> plate-level NPX (one file spans many participants)
    if proteomics:
        plates = [proteomics[i:i + _OLINK_PLATE] for i in range(0, len(proteomics), _OLINK_PLATE)]
        for pno, chunk in enumerate(plates, 1):
            _emit(f"{prog}_OlinkExploreHT_plate{pno}_NPX.parquet", "assay_matrix", "proteomics",
                  "parquet", "plasma", "", chunk)

    # single-cell / nucleus RNA & ATAC -> one pseudobulk HDF5 PER cell type (multi-specimen)
    for atype in sorted(sc_by_mod):
        aids = sc_by_mod[atype]
        for ct in celltypes:
            _emit(f"{prog}_{atype}_pseudobulk_{ct.replace(' ', '_')}.h5", "harmonized_output", atype,
                  "HDF5", tissue, ct, aids)

    # bulk RNAseq / spatial -> one aggregated matrix per modality (no cell type)
    for atype in sorted(bulk_by_mod):
        fmt = _out_format(atype)
        _emit(f"{prog}_{atype}_matrix.{fmt.lower()}", "harmonized_output", atype, fmt, tissue, "",
              bulk_by_mod[atype])

    return files, aif
