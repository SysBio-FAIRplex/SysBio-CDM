"""
Synthetic value generators — BATCH 6: AMP-RA/SLE (the ARK data model).

ARK's ClinicalMetadataTemplate is visit-grained, so every column repeats per visit. The
subject-level ones are held fixed by config/subject_constant.tsv. These three need more than
"constant" or "monotone":

    age      must track the VISIT CLOCK. Monotonicity alone let a subject gain 16 years in 9
             months (67.3 -> 83.9 between M0 and M9).
    height   ARK states no bounds, so the generic 0-100 window produced 32.7 inches at one visit
             and 86.9 at the next. An adult's height does not change; it is drawn once, in the
             unit the subject reports.
    weight   varies visit to visit, but around that subject's own weight -- not redrawn from
             scratch.

fn(rng, subj) -> value.  ASSUMED marks a decision ARK does not make.
"""

# ARK states no Minimum/Maximum for height or weight. These windows are ASSUMED, chosen to be
# plausible in each unit ARK allows (heightUnits: centimeters|feet|inches|meters;
# weightUnits: g|kg|lb|oz).
HEIGHT_RANGE = {"centimeters": (150, 195), "meters": (1.5, 1.95),
                "inches": (59, 77), "feet": (4.9, 6.4)}
WEIGHT_RANGE = {"kg": (45, 120), "lb": (100, 265), "g": (45000, 120000), "oz": (1600, 4200)}


# ── age ──────────────────────────────────────────────────────────────────── visit
# ARK: "Age at which subject was enrolled in study or age at corresponding visit". number,
#      no Minimum/Maximum. The parked SysBio row gives 0-120 years.
# Tracks the visit clock: an enrolment age, plus the elapsed months.
# ageUnits is subject-constant (years|months), so the value is emitted in that unit.
# ASSUMED: enrolment age 18-85.
def age(rng, subj):
    if "ra_age_enrol" not in subj:
        subj["ra_age_enrol"] = rng.randint(18, 85)
    months = subj.get("visit_month", 0)
    yrs = subj["ra_age_enrol"] + max(0.0, months) / 12.0
    return round(yrs * 12, 1) if subj.get("_const_ageUnits") == "months" else round(yrs, 1)


# ── height ───────────────────────────────────────────────────────────────── visit
# ARK: "Standing height of subject." number, no bounds.
# An adult's height does not change between visits — drawn once, in the subject's own unit.
def height(rng, subj):
    if "ra_height" not in subj:
        unit = subj.get("_const_heightUnits") or "centimeters"
        lo, hi = HEIGHT_RANGE.get(unit, (150, 195))
        subj["ra_height"] = round(rng.uniform(lo, hi), 1)
    return subj["ra_height"]


# ── weight ───────────────────────────────────────────────────────────────── visit
# ARK: "Weight of subject. If value unknown, enter '-1'." number, no bounds.
# Varies between visits, but around THIS subject's own weight — not redrawn from scratch.
# ARK's own -1 sentinel for unknown is honoured: it is a value the real files contain.
# ASSUMED: +/-4% visit-to-visit variation, and a 3% unknown rate.
def weight(rng, subj):
    if rng.random() < 0.03:
        return -1                       # ARK's stated sentinel for an unknown weight
    if "ra_weight" not in subj:
        unit = subj.get("_const_weightUnits") or "kg"
        lo, hi = WEIGHT_RANGE.get(unit, (45, 120))
        subj["ra_weight"] = rng.uniform(lo, hi)
    return round(subj["ra_weight"] * rng.uniform(0.96, 1.04), 1)


# ── ageUnits ─────────────────────────────────────────────────────────────── visit
# ARK: enum months | years.
# ASSUMED: always 'years'. AMP-RA/SLE enrols adults; 'months' is an infant convention, and using it
#        puts age at 780 (= 65 years), outside the 0-120 range the source states for this column.
#        ARK permits months; no adult record would use it.
def ageUnits(rng, subj):
    return "years"


# The programmes whose tables these functions may touch. WITHOUT this the registry is keyed
# by BARE NAME and is global: ARK's weight() -- which returns ARK's -1 sentinel and reasons
# about inches vs centimetres -- was being run on FUSION's weight column, in kg.
SCOPE = {"AMP-RA-SLE"}


BATCH_06 = {
    "age": age,
    "ageUnits": ageUnits,
    "height": height,
    "weight": weight,
}
