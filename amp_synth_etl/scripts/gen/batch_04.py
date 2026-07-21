"""
Synthetic value generators — BATCH 4: elements 31–40.

Two of these are the SAME pathology as batch 3, recorded under ROSMAP's names:

    Braak (DiverseCohorts)  and  braaksc (ROSMAP)   -- both "Braak stage", both 0..VI
    amyCerad (DiverseCohorts) and ceradsc (ROSMAP)  -- both the CERAD neuritic-plaque score

The AMP value set proves the CERAD equivalence itself: amyCerad's members are written
"Frequent/Definite/C3", "Moderate/Probable/C2", "Sparse/Possible/C1", "None/No AD/C0" -- the middle
term of each IS ceradsc's label (Definite / Probable / Possible / No AD). So ceradsc is amyCerad on
the same scale, and is COMPUTED from it. Note the scale runs BACKWARDS: ceradsc 1 = Definite AD
(worst), 4 = No AD (best).

fn(rng, subj) -> value.  ASSUMED marks a decision the dictionary does not make.
"""

from batch_01 import BRAAK_STAGE

P_UNKNOWN = 0.04


def _yn(rng, val):
    return "Unknown" if rng.random() < P_UNKNOWN else ("Yes" if val else "No")


# ── 31-32. biological_father_with_pd / biological_mother_with_pd ─────────── visit
# "Father/Mother Has Or Had Parkinson's Disease".  value_set: No | Yes | Unknown
# A family history is a FACT ABOUT THE PARENT — it cannot change between the subject's visits.
# Decided once per subject.
# ASSUMED: 12% per parent. The dictionary states no rate.
def biological_father_with_pd(rng, subj):
    if "father_pd" not in subj:
        subj["father_pd"] = rng.random() < 0.12
    return _yn(rng, subj["father_pd"])


def biological_mother_with_pd(rng, subj):
    if "mother_pd" not in subj:
        subj["mother_pd"] = rng.random() < 0.12
    return _yn(rng, subj["mother_pd"])


# ── 33. braaksc ──────────────────────────────────────────────────────────── subject
# "Braak Stage Values"
# value_set: {"0":"0","1":"I","2":"II","3":"III","4":"IV","5":"V","6":"VI"}   (ROSMAP codebook)
# CODED: the cell holds the INTEGER 0-6; the Roman numeral is its label.
# The same measurement as `Braak` (batch 1) under ROSMAP's name, so it is COMPUTED from it —
# a subject cannot be Braak VI in one table and Braak I in another.
def braaksc(rng, subj):
    return BRAAK_STAGE.get(subj.get("Braak"))


# ── 34-35. caff_drinks_current_use / caff_drinks_ever_used_regularly ─────── visit
# "Current regular caffeinated drinks use indicator" / "...ever used caffeinated drinks"
# value_set: Yes | No | Unknown
# Same gate as alcohol: 'current' cannot be Yes if 'ever' is No.
# ASSUMED: 85% ever, 75% of those currently. The dictionary states no rate.
def _caff_ever(rng, subj):
    if "caff_ever" not in subj:
        subj["caff_ever"] = rng.random() < 0.85
    return subj["caff_ever"]


def caff_drinks_ever_used_regularly(rng, subj):
    return _yn(rng, _caff_ever(rng, subj))


def caff_drinks_current_use(rng, subj):
    if not _caff_ever(rng, subj):
        return "No"
    return _yn(rng, rng.random() < 0.75)


# ── 36. ceradsc ──────────────────────────────────────────────────────────── subject
# "CERAD Score".  value_set: 1=Definite AD | 2=Probable AD | 3=Possible AD | 4=No AD
# The cell holds the CODE (1-4).
# COMPUTED from amyCerad — the same score. amyCerad's own labels carry the mapping:
#     Frequent/Definite/C3 -> 1 (Definite AD)      Sparse/Possible/C1 -> 3 (Possible AD)
#     Moderate/Probable/C2 -> 2 (Probable AD)      None/No AD/C0      -> 4 (No AD)
# The scale is INVERTED (1 = worst). Drawing it independently could give a subject
# amyCerad=Frequent and ceradsc=4 (No AD) at the same autopsy.
CERAD_TO_CERADSC = {
    "Frequent/Definite/C3": 1,
    "Moderate/Probable/C2": 2,
    "Sparse/Possible/C1": 3,
    "None/No AD/C0": 4,
}   # 'Missing or unknown' maps to nothing -> ceradsc is empty for that subject


def ceradsc(rng, subj):
    return CERAD_TO_CERADSC.get(subj.get("amyCerad"))


# ── 37. change_in_diagnosis ──────────────────────────────────────────────── visit
# "Change In Diagnosis Indicator".  value_set: No | Yes
# No 'Unknown' member here, so none is emitted.
# ASSUMED: 15%. Once it has happened it stays Yes at later visits — a change cannot un-happen.
def change_in_diagnosis(rng, subj):
    if subj.get("dx_changed"):
        return "Yes"
    changed = rng.random() < 0.15
    if changed:
        subj["dx_changed"] = True
        subj["dx_change_month"] = subj.get("visit_month", 0)
    return "Yes" if changed else "No"


# ── 38. change_in_diagnosis_months_after_baseline ────────────────────────── visit
# "Number of months after baseline visit at which Change in Diagnosis occurred; negative values
#  [indicate before baseline]".  AMP: Float. No value set.
# Empty unless the diagnosis actually changed. Reports the visit_month at which it changed, so
# the two fields agree and the offset can never point at a visit that never happened.
# The description permits negative values (a change before baseline), so those are legal.
def change_in_diagnosis_months_after_baseline(rng, subj):
    if not subj.get("dx_changed"):
        return None
    return float(subj.get("dx_change_month", 0))


# ── 39. cigarettes_packs_per_day ─────────────────────────────────────────── visit
# "Average number packs of cigarettes smoked daily"
# value_set: Unknown | 0.5 pack or less | 1 pack | 0.5 pack | 2 or more packs | 1.5 pack
# ('Unknown' is listed as a member here, so it is drawn like any other.)
# Empty for a never-smoker. The smoking gate itself (tobacco_ever_used) lands in a later batch;
# it is set here on first use so the whole tobacco block stays consistent.
# ASSUMED: 40% ever-smokers.
PACKS = ["0.5 pack or less", "0.5 pack", "1 pack", "1.5 pack", "2 or more packs"]
PACKS_TO_CIGS = {"0.5 pack or less": 7, "0.5 pack": 10, "1 pack": 20,
                 "1.5 pack": 30, "2 or more packs": 40}


def _smokes(rng, subj):
    if "tob_ever" not in subj:
        subj["tob_ever"] = rng.random() < 0.40
    return subj["tob_ever"]


def cigarettes_packs_per_day(rng, subj):
    if not _smokes(rng, subj):
        return None
    if rng.random() < P_UNKNOWN:
        return "Unknown"
    p = rng.choice(PACKS)
    subj["cig_packs"] = p
    return p


# ── 40. cigarettes_per_day ───────────────────────────────────────────────── visit
# "Average number cigarettes smoked daily".  AMP declares String; NO value set.
# COMPUTED from cigarettes_packs_per_day at 20 cigarettes to the pack, so a subject cannot report
# "2 or more packs" and 3 cigarettes a day.
# ASSUMED: the 20-per-pack conversion, and the count for each band.
def cigarettes_per_day(rng, subj):
    p = subj.get("cig_packs")
    if p is None:
        return None
    return str(PACKS_TO_CIGS[p])


# The programmes whose tables these functions may touch. WITHOUT this the registry is keyed
# by BARE NAME and is global: ARK's weight() -- which returns ARK's -1 sentinel and reasons
# about inches vs centimetres -- was being run on FUSION's weight column, in kg.
SCOPE = {"AMP-PD", "AMP-AD"}


BATCH_04 = {
    "biological_father_with_pd": biological_father_with_pd,
    "biological_mother_with_pd": biological_mother_with_pd,
    "braaksc": braaksc,
    "caff_drinks_current_use": caff_drinks_current_use,
    "caff_drinks_ever_used_regularly": caff_drinks_ever_used_regularly,
    "ceradsc": ceradsc,
    "change_in_diagnosis": change_in_diagnosis,
    "change_in_diagnosis_months_after_baseline": change_in_diagnosis_months_after_baseline,
    "cigarettes_packs_per_day": cigarettes_packs_per_day,
    "cigarettes_per_day": cigarettes_per_day,
}
