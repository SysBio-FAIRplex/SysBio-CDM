"""
Synthetic value generators — BATCH 7: ARK's Cell Ontology pair.

ARK ships annotation_maps/CL-cellType.csv, a Cell Ontology identifier and its label:

    CL:0000084   T cell
    CL:0000091   Kupffer cell

`cellOntologyID` carries ARK's validation rule `regex search ^CL:`, and `cellType` is that
identifier's LABEL. They are two views of ONE fact, so they must come from ONE row of the map.
Drawn independently they disagreed -- a specimen was labelled 'foreskin fibroblast' with no
identifier at all, because cellOntologyID had no value set and was being invented.

Both columns are CONDITIONAL (config/ark_conditional.tsv): ARK declares them only for
'flow-sorted cells', 'cell suspension', 'cell line' and 'primary cell culture'. The generator
blanks them on every other kind of specimen, so a serum sample carries no cell type.

fn(rng, subj) -> value.
"""
import csv
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_P = os.path.join(ROOT, "config", "ark_cell_ontology.tsv")

CL = []
if os.path.exists(_P):
    with open(_P, newline="", encoding="utf-8") as fh:
        CL = [(r["cellOntologyID"], r["cellType"])
              for r in csv.DictReader((l for l in fh if not l.startswith("#")), delimiter="\t")]


def _pair(rng, subj):
    """One row of ARK's CL map, held for THIS specimen.

    An individual has several specimens now (a lineage), so the pair is cached against the
    specimen being written, not the subject -- otherwise every specimen of one individual would
    be the same cell type. Whichever of the two columns is drawn first fixes the pair for both.
    """
    if not CL:
        return None
    sp = subj.get("_specimen") or {}
    key = "_cl_pair_%s" % sp.get("biospecimenID", "")
    if key not in subj:
        subj[key] = CL[rng.randrange(len(CL))]
    return subj[key]


def cellOntologyID(rng, subj):
    p = _pair(rng, subj)
    return p[0] if p else None


def cellType(rng, subj):
    p = _pair(rng, subj)
    return p[1] if p else None


# ── program ──────────────────────────────────────────────────────────── subject-constant
# ARK's `program` value set is {AMP AIM, AMP RA/SLE, Community Contribution}. Drawn from all
# three, 15 of 34 subjects in an AMP cohort came out as 'Community Contribution' -- ARK's category
# for data contributed from OUTSIDE the programme. ARK then correctly withheld visitID from them
# (only AMP AIM and AMP RA/SLE DependOn visitID), so nearly half the specimens had no visit.
# ASSUMED: this is AMP RA/SLE data, so the subject is enrolled under an AMP programme.
def program(rng, subj):
    if "_program" not in subj:
        subj["_program"] = "AMP RA/SLE" if rng.random() < 0.5 else "AMP AIM"
    return subj["_program"]


# The programmes whose tables these functions may touch. WITHOUT this the registry is keyed
# by BARE NAME and is global: ARK's weight() -- which returns ARK's -1 sentinel and reasons
# about inches vs centimetres -- was being run on FUSION's weight column, in kg.
SCOPE = {"AMP-RA-SLE"}




BATCH_07 = {
    "cellOntologyID": cellOntologyID,
    "cellType": cellType,
    "program": program,
}
