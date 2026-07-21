"""
Synthetic value generators — BATCH 3: elements 21–30.

Mostly the AMP-AD amyloid/tau block, which is a tightly coupled set. The dictionary describes the
same pathology at several granularities, so most of these are COMPUTED, not drawn:

    amyThal  0-5                     the raw Thal phase                       <- drawn
    amyA     grouped Thal phases     "Indicator of Thal Phase, GROUPED"       <- computed
    amyCerad 0/A/B/C                 CERAD neuritic plaque score              <- drawn
    amyAny   True/False              "Presence of ANY amyloid pathology"      <- computed
    Braak    0..VI  (batch 1)        raw NFT stage                            <- drawn
    bScore   binned Braak            "Braak Staging as BINNED Values"         <- computed

Drawing them independently would give a subject Thal Phase 5 with amyA='None', or Braak VI with
bScore='Braak Stage I-II'.

fn(rng, subj) -> value.  ASSUMED marks a decision the dictionary does not make.
"""

from batch_01 import BRAAK_STAGE


# ── 21. alcohol_stop_age ─────────────────────────────────────────────────── visit
# "Age in years when participant/subject stopped ingesting alcoholic beverages"
# value_set: 9 - 85.  AMP: Integer.
# CLAMPED: >= alcohol_start_age (batch 2), and <= the subject's current age.
# Empty for a never-drinker, and for someone still drinking (they have not stopped).
def alcohol_stop_age(rng, subj):
    if not subj.get("alc_ever") or subj.get("alc_current"):
        return None
    if "alc_stop_age" not in subj:
        lo = max(9, subj.get("alc_start_age", 9))
        hi = min(85, subj.get("last_age_at_visit", subj.get("age_at_baseline", 85)))
        if lo > hi:
            return None
        subj["alc_stop_age"] = rng.randint(lo, hi)
    return subj["alc_stop_age"]


# ── 22. alcohol_use_frequency ────────────────────────────────────────────── visit
# "The frequency of consumption of alcohol by the participant"
# AMP declares String; NO value set is given.
# ASSUMED: the categories. Derived from alcohol_drinks_day (batch 2) so the two agree.
def alcohol_use_frequency(rng, subj):
    if not subj.get("alc_ever"):
        return "Never"
    d = subj.get("alc_drinks_day")
    if d is None or d == 0:
        return "Not currently"
    if d <= 1:
        return "Monthly or less"
    if d <= 3:
        return "Weekly"
    return "Daily or almost daily"


# ── 23. amyA ─────────────────────────────────────────────────────────────── subject
# "Indicator of Thal Phase, GROUPED"
# value_set: None | Thal Phase 1 or 2 | Thal Phase 3 | Thal Phase 4 or 5 | missing or unknown
# COMPUTED from amyThal — it IS amyThal, binned. ('missing or unknown' is a missingValue.)
def amyA(rng, subj):
    t = THAL_PHASE.get(subj.get("amyThal"))
    if t is None:
        return "Missing or unknown"
    if t == 0:
        return "None"
    if t in (1, 2):
        return "Thal Phase 1 or 2"
    if t == 3:
        return "Thal Phase 3"
    return "Thal Phase 4 or 5"


# ── 24. amyAny ───────────────────────────────────────────────────────────── subject
# "Presence of ANY amyloid pathology".  value_set: True | False
# COMPUTED: any amyloid = a non-zero Thal phase or a non-zero CERAD score.
# amyAny's AMP value set is CODED:
#   0 = amyCerad = None/No AD/C0
#   1 = amyCerad = Sparse/Possible/C1 or Moderate/Probable/C2 or Frequent/Definite/C3
#   Missing or unknown
# The cell holds 0, 1 or 'Missing or unknown'. It is defined off amyCerad ALONE, not Thal.
def amyAny(rng, subj):
    cerad = subj.get("amyCerad")
    if cerad is None or cerad.startswith("Missing"):
        return "Missing or unknown"
    return 0 if cerad.startswith("None/") else 1


# ── 25. amyCerad ─────────────────────────────────────────────────────────── subject
# "CERAD score, a semi-quantitative measure of neuritic plaque"
# value_set: None/No AD/C0 | Sparse/Possible/C1 | Moderate/Probable/C2 | Frequent/Definite/C3
#            | Missing or unknown
# The cell holds the whole label string. ('Missing or unknown' is a missingValue.)
# ASSUMED: uniform over the 4 grades. The dictionary states no prevalence.
import fidelity  # real-world distributions (draw realistic values within the legal value set)

CERAD_VALUES = ["None/No AD/C0", "Sparse/Possible/C1", "Moderate/Probable/C2",
                "Frequent/Definite/C3", "Missing or unknown"]


def amyCerad(rng, subj):
    return subj.setdefault("amyCerad", fidelity.categorical("amyCerad", CERAD_VALUES, rng))


# ── 26. amyThal ──────────────────────────────────────────────────────────── subject
# "Thal Phase (a measure of amyloid deposition)"
# value_set: None | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Phase 5 | missing or unknown
#            (7 values -- the AMP file's own text. 'missing or unknown' IS a value that appears
#             in the data; it is not a null marker.)
# ASSUMED: uniform over the 7.
AMYTHAL_VALUES = ["None", "Phase 1", "Phase 2", "Phase 3", "Phase 4", "Phase 5",
                  "missing or unknown"]
THAL_PHASE = {"None": 0, "Phase 1": 1, "Phase 2": 2, "Phase 3": 3, "Phase 4": 4, "Phase 5": 5}


def amyThal(rng, subj):
    return subj.setdefault("amyThal", fidelity.categorical("amyThal", AMYTHAL_VALUES, rng))


# ── 27. anosmia ──────────────────────────────────────────────────────────── visit
# "Anosmia (per history or smell test)".  value_set: Yes | No | NA
# 'NA' is a missingValue.
# ASSUMED: 35% prevalence. Anosmia is common in the PD/LBD cohorts this element belongs to,
#        but the dictionary states no rate.
def anosmia(rng, subj):
    if rng.random() < 0.04:
        return "NA"
    return "Yes" if rng.random() < 0.35 else "No"


# ── 28. apoe_genotype ────────────────────────────────────────────────────── subject
# "APOE Genotype"
# value_set: {"22":"E2E2", "23":"E2E3", "24":"E2E4", "33":"E3E3", "34":"E3E4", "44":"E4E4"}
# A CODED map: the cell holds the CODE (22, 23, ...), not the label (E2E2).
# Germline — fixed for life, one per subject.
# ASSUMED: uniform over the 6 genotypes. Real APOE frequencies are nothing like uniform
#        (E3E3 is ~60%); the dictionary states none. Weighting can be added if required.
def apoe_genotype(rng, subj):
    return subj.setdefault("apoe_genotype",
                           fidelity.categorical("apoe_genotype", [22, 23, 24, 33, 34, 44], rng))


# ── 29. auton_dys ────────────────────────────────────────────────────────── visit
# "Severe dysautonomia (e.g. constipation requiring medications, urinary incontinence,
#  orthostatic hypotension)".  value_set: Yes | No | NA
# ASSUMED: 20% prevalence.
def auton_dys(rng, subj):
    if rng.random() < 0.04:
        return "NA"
    return "Yes" if rng.random() < 0.20 else "No"


# ── 30. bScore ───────────────────────────────────────────────────────────── subject
# "Braak Staging as BINNED Values"
# value_set: Braak Stage I-II | Braak Stage III-IV | Braak Stage V-VI
# COMPUTED from Braak (batch 1) — it IS Braak, binned.
# NOTE: the value set has no bin for Braak 0. A stage-0 subject has no valid bin, so the cell is
#       empty. That is a gap in the dictionary, not a choice of mine.
# bScore's AMP value set HAS a None bin (the SysBio one did not):
#   None | Braak Stage I-II | Braak Stage III-IV | Braak Stage V-VI | Missing or unknown
def bScore(rng, subj):
    stage = BRAAK_STAGE.get(subj.get("Braak"))
    if stage is None:
        return "Missing or unknown"
    if stage == 0:
        return "None"
    if stage <= 2:
        return "Braak Stage I-II"
    if stage <= 4:
        return "Braak Stage III-IV"
    return "Braak Stage V-VI"


# The programmes whose tables these functions may touch. WITHOUT this the registry is keyed
# by BARE NAME and is global: ARK's weight() -- which returns ARK's -1 sentinel and reasons
# about inches vs centimetres -- was being run on FUSION's weight column, in kg.
SCOPE = {"AMP-PD", "AMP-AD"}


BATCH_03 = {
    "alcohol_stop_age": alcohol_stop_age,
    "alcohol_use_frequency": alcohol_use_frequency,
    "amyA": amyA,
    "amyAny": amyAny,
    "amyCerad": amyCerad,
    "amyThal": amyThal,
    "anosmia": anosmia,
    "apoe_genotype": apoe_genotype,
    "auton_dys": auton_dys,
    "bScore": bScore,
}
