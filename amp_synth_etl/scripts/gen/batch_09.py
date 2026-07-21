"""
Synthetic value generators — BATCH 9: KPMP's two durations, and the age they depend on.

The workbook DEFINES both of them, in its own description column:

    diabetes_durationC   "Diabetes duration = np_age - mh_diabetes_age"
    ht_durationC         "Hypertension duration = np_age - mh_ht_age"

But mh_diabetes_age and mh_ht_age are NOT IN THE WORKBOOK -- the operand each formula needs is
never published. So the duration cannot be computed, and it is drawn. Two things still follow from
the formula and hold by construction:

    duration <= np_age      the onset age cannot be negative, so a duration cannot exceed the age.
                            Drawn independently, a 22-year-old had had diabetes for 61 years.
    duration only exists    mh_diabetes_yn / mh_ht_yn say whether the participant HAS the
    for someone who has     condition (1=Yes, 0=No, 99=Don't know). A non-diabetic has no diabetes
    the condition           duration, and 'Don't know' cannot yield one either.

np_age and the two yes/no flags are therefore held on the participant, so the durations can read
them back. The workbook's column order puts np_age (position 2) and each flag ahead of its
duration, so they are already drawn when the duration is; QC asserts both relationships rather than
trusting that order to hold.

fn(rng, subj) -> value.  ASSUMED marks a decision the workbook does not make.
"""


# ── np_age ───────────────────────────────────────────────────── KPMP, one per participant
# "Participant age (released as range in open file)" -- the workbook says it is bounded but does
# not give the bound. Range in config/instrument_ranges.tsv. Whole years, per the project rule.
def np_age(rng, subj):
    if "_np_age" not in subj:
        subj["_np_age"] = rng.randint(18, 90)
    return subj["_np_age"]


# ── the two condition flags ──────────────────────────────── 1=Yes, 0=No, 99=Don't know
# Held so the durations can see them. ASSUMED: drawn uniformly over the workbook's three codes --
# the workbook states no prevalence, and this project does not invent distributions.
def mh_diabetes_yn(rng, subj):
    if "_dm" not in subj:
        subj["_dm"] = rng.choice([1, 0, 99])
    return subj["_dm"]


def mh_ht_yn(rng, subj):
    if "_ht" not in subj:
        subj["_ht"] = rng.choice([1, 0, 99])
    return subj["_ht"]


def _duration(rng, subj, has):
    if has != 1:
        return None                       # no condition (or unknown) -> no duration
    age = subj.get("_np_age")
    if age is None:
        return None
    return rng.randint(0, min(70, int(age)))   # duration = age - onset, and onset >= 0


def diabetes_durationC(rng, subj):
    return _duration(rng, subj, subj.get("_dm"))


def ht_durationC(rng, subj):
    return _duration(rng, subj, subj.get("_ht"))


# The programmes whose tables these functions may touch. WITHOUT this the registry is keyed
# by BARE NAME and is global: ARK's weight() -- which returns ARK's -1 sentinel and reasons
# about inches vs centimetres -- was being run on FUSION's weight column, in kg.
SCOPE = {"AMP-CMD"}


BATCH_09 = {
    "np_age": np_age,
    "mh_diabetes_yn": mh_diabetes_yn,
    "mh_ht_yn": mh_ht_yn,
    "diabetes_durationC": diabetes_durationC,
    "ht_durationC": ht_durationC,
}
