"""
Synthetic value generators — BATCH 2: elements 11–20 (the alcohol block).

These are NOT independent. The dictionary's own wording defines a gate and a hierarchy:
a subject who never drank has no start age, no drinks per day, no hospitalisation. Sampling each
cell on its own would produce a lifelong abstainer who drinks 8 a day and started at 12.

  alcohol_ever_used = No  ->  every other alcohol field is empty
  alcohol_prior_use       ->  "prior to the past 12 months"
  alcohol_recent_use      ->  "past 12 months"
  alcohol_current_use     ->  now.  current => recent => ever.
  alcohol_inc_dec         ->  only meaningful if consumption CHANGED (batch 1's
                              alcohol_consumption_change == 'Yes')

fn(rng, subj) -> value.  ASSUMED marks a decision the dictionary does not make.
"""

P_UNKNOWN = 0.04          # rate at which a Yes/No question comes back 'Unknown' (a missingValue)


def _yn(rng, val):
    """Yes/No with an occasional 'Unknown' — 'Unknown' is a null marker, not a third category."""
    return "Unknown" if rng.random() < P_UNKNOWN else ("Yes" if val else "No")


def _ever(rng, subj):
    """The gate. Decided once per subject; every other alcohol field defers to it.
    ASSUMED: 70% of the cohort has ever drunk. The dictionary states no prevalence."""
    if "alc_ever" not in subj:
        subj["alc_ever"] = rng.random() < 0.70
    return subj["alc_ever"]


# ── 11. alcohol_current_use ──────────────────────────────────────────────── visit
# "Currentl alcohol use indicator" [sic].  value_set: Yes | No | Unknown
# Implies recent use, which implies ever. Cannot be Yes if the subject never drank.
def alcohol_current_use(rng, subj):
    if not _ever(rng, subj):
        return "No"
    cur = rng.random() < 0.55
    subj["alc_current"] = cur
    return _yn(rng, cur)


# ── 12. alcohol_drinks_daily_range ───────────────────────────────────────── visit
# "Alcohol drinking day average drinks consumed range"
# AMP declares String; NO value set is given — the source lists no bins.
# ASSUMED: the bins. Derived from alcohol_drinks_day so the two agree; a subject reporting 8
#        drinks/day cannot also report the "1-2" band. Empty for a never-drinker.
def alcohol_drinks_daily_range(rng, subj):
    d = subj.get("alc_drinks_day")
    if d is None:
        return None
    if d < 1:
        return "less than 1"
    if d <= 2:
        return "1-2"
    if d <= 4:
        return "3-4"
    if d <= 6:
        return "5-6"
    return "7 or more"


# ── 13. alcohol_drinks_day ───────────────────────────────────────────────── visit
# "How many drinks do you have on an average day?"  value_set: 0 - 10.  AMP: Float.
# Empty for a never-drinker. 0 for someone who drank in the past but not now.
def alcohol_drinks_day(rng, subj):
    if not _ever(rng, subj):
        return None
    d = round(rng.uniform(0.5, 10.0), 1) if subj.get("alc_current") else 0.0
    subj["alc_drinks_day"] = d
    return d


# ── 14. alcohol_ever_used ────────────────────────────────────────────────── visit
# "Indicator of whether subject has ever used alcohol".  value_set: Yes | No | Unknown
# THE GATE. A subject-level fact: 'ever' cannot flip from Yes to No between visits.
def alcohol_ever_used(rng, subj):
    return _yn(rng, _ever(rng, subj))


# ── 15. alcohol_inc_dec ──────────────────────────────────────────────────── visit
# "Has there been a general increase or decrease in your consumption over a 10-year period."
# value_set: Decrease | Increase   (no 'no change' option — so it only applies when it changed)
# Empty unless the subject drinks AND reported a change (batch 1: alcohol_consumption_change).
def alcohol_inc_dec(rng, subj):
    if not _ever(rng, subj) or subj.get("alc_changed") is not True:
        return None
    return rng.choice(["Decrease", "Increase"])


# ── 16. alcohol_prior_use ────────────────────────────────────────────────── visit
# "alcohol consumption prior to the past 12 months".  value_set: Yes | No | Unknown
def alcohol_prior_use(rng, subj):
    if not _ever(rng, subj):
        return "No"
    return _yn(rng, rng.random() < 0.80)


# ── 17. alcohol_recent_use ───────────────────────────────────────────────── visit
# "alcohol consumption past 12 months".  value_set: Yes | No | Unknown
# Current use implies recent use.
def alcohol_recent_use(rng, subj):
    if not _ever(rng, subj):
        return "No"
    return _yn(rng, subj.get("alc_current", False) or rng.random() < 0.30)


# ── 18. alcohol_related_hospitalization ──────────────────────────────────── visit
# "hospitalized for an alcohol-related..."  value_set: Yes | No | Unknown
# Cannot be Yes for a never-drinker.
# ASSUMED: 8% among drinkers. The dictionary states no rate.
def alcohol_related_hospitalization(rng, subj):
    if not _ever(rng, subj):
        return "No"
    return _yn(rng, rng.random() < 0.08)


# ── 19. alcohol_six_more_drinks_frequency ────────────────────────────────── visit
# "Alcohol consume six or more drinks frequency"
# value_set: Never | Less than monthly | Unknown | Monthly | Daily or almost daily | Weekly
# 'Unknown' is listed among the values here, so it is drawn like any other member.
# Never-drinker -> 'Never'.
def alcohol_six_more_drinks_frequency(rng, subj):
    if not _ever(rng, subj):
        return "Never"
    return rng.choice(["Never", "Less than monthly", "Unknown", "Monthly",
                       "Daily or almost daily", "Weekly"])


# ── 20. alcohol_start_age ────────────────────────────────────────────────── visit
# "Age in years when participant/subject started ingesting alcoholic beverages"
# value_set: 1 - 75.  AMP: Integer.
# CLAMPED: <= the subject's current age (you cannot have started at 60 when you are 40).
# Stored on the subject so alcohol_stop_age (a later batch) can be held >= it.
def alcohol_start_age(rng, subj):
    if not _ever(rng, subj):
        return None
    if "alc_start_age" not in subj:
        hi = min(75, subj.get("last_age_at_visit", subj.get("age_at_baseline", 75)))
        subj["alc_start_age"] = rng.randint(1, max(1, hi))
    return subj["alc_start_age"]


# The programmes whose tables these functions may touch. WITHOUT this the registry is keyed
# by BARE NAME and is global: ARK's weight() -- which returns ARK's -1 sentinel and reasons
# about inches vs centimetres -- was being run on FUSION's weight column, in kg.
SCOPE = {"AMP-PD", "AMP-AD"}


BATCH_02 = {
    "alcohol_current_use": alcohol_current_use,
    "alcohol_drinks_daily_range": alcohol_drinks_daily_range,
    "alcohol_drinks_day": alcohol_drinks_day,
    "alcohol_ever_used": alcohol_ever_used,
    "alcohol_inc_dec": alcohol_inc_dec,
    "alcohol_prior_use": alcohol_prior_use,
    "alcohol_recent_use": alcohol_recent_use,
    "alcohol_related_hospitalization": alcohol_related_hospitalization,
    "alcohol_six_more_drinks_frequency": alcohol_six_more_drinks_frequency,
    "alcohol_start_age": alcohol_start_age,
}
