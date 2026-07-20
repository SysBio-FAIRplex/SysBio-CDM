"""
Synthetic value generators — BATCH 1: elements 1–10 (distinct).

fn(rng, subj) -> value        rng = deterministic Random; subj = the subject's accumulated state
Return None for an empty cell.

Each function shows the dictionary's own value_set. Where a decision is ASSUMED and not the
dictionary's, it is marked ASSUMED.
"""
import fidelity  # real-world distributions (draw realistic values within the legal value set)

# The AMP file's own values, verbatim (DiverseCohorts_DataDictionary.pdf).
# 'Stave VI' is a typo in the AMP source; it is reproduced, not corrected -- the synthetic data
# must contain what the real data contains.
BRAAK_VALUES = ["None", "Stage I", "Stage II", "Stage III", "Stage IV", "Stage V", "Stave VI",
                "Missing or unknown"]
BRAAK_STAGE = {"None": 0, "Stage I": 1, "Stage II": 2, "Stage III": 3,
               "Stage IV": 4, "Stage V": 5, "Stave VI": 6}


# ── 1. ADoutcome ─────────────────────────────────────────────────────────── subject
# "AD clinical outcome post-mortem. Classify participants into control / AD / Other."
# The data cell holds the CLASS. The three classes are derived from Braak + CERAD:
#     AD      : Braak >= 4  and CERAD in {Frequent, Moderate}
#     Control : Braak <= 3  and CERAD in {Sparse, None}
#     Other   : everything else
# amyCerad's value set is the AMP source's own text:
#     None/No AD/C0 | Sparse/Possible/C1 | Moderate/Probable/C2 | Frequent/Definite/C3
# so Frequent-or-Moderate is C3/C2, and Sparse-or-None is C1/C0.
# COMPUTED from this subject's own Braak and CERAD — never drawn, or a Braak-VI subject
# could come out "Control".
def ADoutcome(rng, subj):
    stage = BRAAK_STAGE.get(subj.get("Braak"))
    cerad = subj.get("amyCerad")
    if stage is None or cerad is None:
        return None
    if stage >= 4 and cerad.startswith(("Frequent/", "Moderate/")):
        return "AD"
    if stage <= 3 and cerad.startswith(("Sparse/", "None/")):
        return "Control"
    return "Other"


# ── 2. Braak ─────────────────────────────────────────────────────────────── subject
# "Braak stage for neurofibrillary tangle pathology"
# value_set: None | Stage I | Stage II | Stage III | Stage IV | Stage V | Stave VI
#            | Missing or unknown            (8 values -- the AMP file's own text)
# ASSUMED: the distribution. The AMP file states the legal values, not their frequency.
#        Uniform. A real brain bank skews high; weighting can be added if required.
def Braak(rng, subj):
    return subj.setdefault("Braak", fidelity.categorical("Braak", BRAAK_VALUES, rng))


# ── 3. BrodmannArea ──────────────────────────────────────────────────────── subject
# "Brodmann area designation for brain tissue sample or region of interest"
# value_set: BA1 | BA2 | BA3 | BA4 | BA5 | BA6 | BA7 | BA8 | BA9 | BA10 | BA11 |
#            BA17 | BA18 | BA19 | BA20 | BA21
# ASSUMED: uniform over the 16 listed areas.
def BrodmannArea(rng, subj):
    return fidelity.categorical("BrodmannArea",
                                ["BA1", "BA2", "BA3", "BA4", "BA5", "BA6", "BA7", "BA8", "BA9",
                                 "BA10", "BA11", "BA17", "BA18", "BA19", "BA20", "BA21"], rng)


# ── 4. GUID ──────────────────────────────────────────────────────────────── key
# "Global Unique ID (USUBJID)".  value_set: none.
# A KEY — it IS the subject. Assigned once by the cohort builder, identical on every row of
# every table for that person. Never drawn.
# ASSUMED: numeric by specification (the AMP dictionary declares it String).
def GUID(rng, subj):
    return subj["guid"]


# ── 5. age_at_baseline ───────────────────────────────────────────────────── subject
# "Age At Baseline".  value_set: 19 - 100   (a real range)
# Whole number. Every later age builds on this one.
def age_at_baseline(rng, subj):
    return subj.setdefault("age_at_baseline", fidelity.numeric("age_at_baseline", 19, 100, rng))


# ── 6. age_at_visit ──────────────────────────────────────────────────────── visit
# "Age of participant at time of clinical visit".  value_set: Continuous; Range: 0-120; years
# Advances with the visit clock: baseline age + elapsed years.
# CLAMPED AT DRAW TIME, so a violation cannot occur (rather than being caught later):
#     >= the previous visit's age      — nobody gets younger
#     <= age_death                     — nobody attends a clinic after dying
def age_at_visit(rng, subj):
    base = subj.setdefault("age_at_baseline", fidelity.numeric("age_at_baseline", 19, 100, rng))
    age = base + int(subj["visit_month"] // 12)
    age = max(subj.get("last_age_at_visit", base), age)
    age = min(age, subj.get("age_death", 120), 120)
    subj["last_age_at_visit"] = age
    return age


# ── 7. age_death ─────────────────────────────────────────────────────────── subject
# "Age at Death".  units: years.  value_set: empty — ROSMAP states only "Continuous".
# ONE per person. Cannot appear on a visit row.
# CLAMPED: >= age_at_baseline, and >= the subject's last visit age.
# ASSUMED: the upper bound (105). ROSMAP is an aging cohort; an unbounded window produced
#        impossible deaths (age 2, age 11).
def age_death(rng, subj):
    if "age_death" in subj:
        return subj["age_death"]
    floor = max(subj.get("age_at_baseline", 65), subj.get("last_age_at_visit", 0))
    subj["age_death"] = rng.randint(max(floor, 65), 105) if floor <= 105 else floor
    return subj["age_death"]


# ── 8. age_first_ad_dx ───────────────────────────────────────────────────── subject
# "Age at First Alzheimer's Dementia Diagnosis".  value_set: Continuous.  units: years
# ONE per person: the age at the first visit where an AD diagnosis was rendered.
# CLAMPED: 50 <= age_first_ad_dx <= age_death, and >= age_at_baseline.
# MIN_AD_DX = 50 by specification. Returns None for a subject never diagnosed.
MIN_AD_DX = 50


def age_first_ad_dx(rng, subj):
    lo = max(MIN_AD_DX, subj.get("age_at_baseline", MIN_AD_DX))
    hi = subj.get("age_death", 120)
    if lo > hi:
        return None
    return subj.setdefault("age_first_ad_dx", rng.randint(lo, hi))


# ── 9. alcohol_consumed_years ────────────────────────────────────────────── visit
# "How many years consumed alcohol heavily in the past?"   value_set: 1 - 51
# AMP dictionary declares Float, so a fractional year count is legal.
# CLAMPED: cannot exceed the subject's age — you cannot have drunk for 51 years at 30.
def alcohol_consumed_years(rng, subj):
    hi = min(51.0, float(subj.get("last_age_at_visit", subj.get("age_at_baseline", 51))))
    return round(rng.uniform(1.0, max(1.0, hi)), 1)


# ── 10. alcohol_consumption_change ───────────────────────────────────────── visit
# "Has your alcohol consumption changed over the past 10 years?"
# value_set: Yes | No | Unknown
# 'Unknown' is a missingValue — the reader nulls it; it is not a third category.
def alcohol_consumption_change(rng, subj):
    return rng.choice(["Yes", "No"]) if rng.random() > 0.04 else "Unknown"


# The programmes whose tables these functions may touch. WITHOUT this the registry is keyed
# by BARE NAME and is global: ARK's weight() -- which returns ARK's -1 sentinel and reasons
# about inches vs centimetres -- was being run on FUSION's weight column, in kg.
SCOPE = {"AMP-PD", "AMP-AD"}


BATCH_01 = {
    "ADoutcome": ADoutcome,
    "Braak": Braak,
    "BrodmannArea": BrodmannArea,
    "GUID": GUID,
    "age_at_baseline": age_at_baseline,
    "age_at_visit": age_at_visit,
    "age_death": age_death,
    "age_first_ad_dx": age_first_ad_dx,
    "alcohol_consumed_years": alcohol_consumed_years,
    "alcohol_consumption_change": alcohol_consumption_change,
}
