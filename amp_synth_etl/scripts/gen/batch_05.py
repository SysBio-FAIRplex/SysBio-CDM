"""
Synthetic value generators — BATCH 5: elements 41–50.

Two coupled pairs here:

    dcfdx (per VISIT)  and  cogdx (per SUBJECT)
        The ROSMAP codebook: dcfdx is "rendered at every assessment"; cogdx is the
        "consensus diagnosis AT TIME OF DEATH, all available clinical data reviewed".
        cogdx is therefore the END of the dcfdx series, not an independent draw. And cognitive
        diagnosis does not improve -- a subject who reached AD does not return to NCI.

    cigarettes_per_day_current / _past
        The dictionary splits them by WHO answers: "Current smokers: ..." / "Past smokers: ...".
        A current smoker answers one, a past smoker the other. Never both.

fn(rng, subj) -> value.  ASSUMED marks a decision the dictionary does not make.
"""

# dcfdx / cogdx share one 6-point scale. Order matters: it is monotone non-decreasing.
#   1 NCI   2 MCI   3 MCI+   4 AD   5 AD+   6 Other dementia
DX_SCALE = [1, 2, 3, 4, 5, 6]


# ── 41. cigarettes_per_day_current ───────────────────────────────────────── visit
# "Current smokers: average number cigarettes per day?"  value_set: 0 - 250
# Only a CURRENT smoker answers. Empty otherwise.
# ASSUMED: current-smoker rate among ever-smokers (30%). Also: the dictionary's ceiling of 250 is
#        implausible as a daily count; this draws 1-60 and never approaches it.
def cigarettes_per_day_current(rng, subj):
    if not subj.get("tob_ever"):
        return None
    if "tob_current" not in subj:
        subj["tob_current"] = rng.random() < 0.30
    if not subj["tob_current"]:
        return None
    return rng.randint(1, 60)


# ── 42. cigarettes_per_day_past ──────────────────────────────────────────── visit
# "Past smokers: average number of cigarettes smoked daily?"  value_set: 0 - 80.  AMP: Float.
# Only a PAST smoker answers — an ever-smoker who is not a current smoker. Empty otherwise.
def cigarettes_per_day_past(rng, subj):
    if not subj.get("tob_ever"):
        return None
    if "tob_current" not in subj:
        subj["tob_current"] = rng.random() < 0.30
    if subj["tob_current"]:
        return None
    return round(rng.uniform(1.0, 80.0), 1)


# ── 43. cogdx ────────────────────────────────────────────────────────────── subject
# "Final Consensus Cognitive Diagnosis"
# value_set: 1=NCI | 2=MCI (no other cause) | 3=MCI (another cause) | 4=AD (no other cause)
#            | 5=AD (another cause) | 6=Other dementia      -- the cell holds the CODE
# ROSMAP: rendered AT TIME OF DEATH from all available clinical data.
# COMPUTED: it is the subject's FINAL dcfdx, not an independent draw. Drawing it separately would
# let someone be diagnosed AD at every visit and come out NCI at death.
def cogdx(rng, subj):
    return subj.get("dcfdx_last")


# ── 44. cohort ───────────────────────────────────────────────────────────── subject
# "Cohort Identifier".  value_set: 'required'  <- a constraint marker, not a value set.
# The dictionary states NO members. The AMP-AD source lists them (AA, Banner, Emory, Mayo, ROS,
# UFL, ...), but this element's own value set does not.
# ASSUMED ENTIRELY: the membership list below. Replace with real cohort membership when available.
import fidelity  # real-world distributions (draw realistic values within the legal value set)

COHORTS = ["AA", "Banner", "CLINCOR", "Emory", "LATC", "MAP", "MARS",
           "Mayo Clinic", "Mt Sinai Brain Bank", "NY Brain Bank", "ROS", "UFL", "UPenn"]


def cohort(rng, subj):
    return subj.setdefault("cohort", fidelity.categorical("cohort", COHORTS, rng))


# ── 44. cohort ───────────────────────────────────────────────────────────── subject
# "The initial study group population to which the individual belonged"
# value_set: AA | Banner | Biggs Institute Brain Bank | CLINCOR | Emory | LATC | MAP | MARS
#            | Mayo Clinic | Mt Sinai Brain Bank | NY Brain Bank | UPenn | ROS | UFL
# STRUCTURAL, not decorative: DiverseCohorts is the AMP-AD harmonisation layer across these 14
# brain banks, and ROS + MAP together ARE ROSMAP. A subject whose cohort is ROS or MAP also
# appears in the ROSMAP tables, carrying that study's native fields (projid, dcfdx, cogdx,
# braaksc, ceradsc) -- measured from the SAME autopsy, so braaksc must agree with Braak.
# A Mayo Clinic subject has no ROSMAP row at all.
# Decided by the cohort builder (config/cohort.json) because it gates table membership; this
# function only reports it.
def cohort(rng, subj):
    return subj.get("cohort")


# ── 45. dat ──────────────────────────────────────────────────────────────── visit
# "Dopamine transporter scan result".  value_set: Positive | Negative | NA
# 'NA' is a missingValue.
# A scan result is a fact about the brain: once positive it does not turn negative.
# ASSUMED: 55% positive (this element sits in the PD/LBD cohorts).
def dat(rng, subj):
    if "dat_pos" not in subj:
        subj["dat_pos"] = rng.random() < 0.55
    if rng.random() < 0.04:
        return "NA"
    return "Positive" if subj["dat_pos"] else "Negative"


# ── 46. datscan_visual_interpretation ────────────────────────────────────── visit
# "DaTSCAN SPECT Visual Interpretation Assessment Report".  value_set: Positive | Negative
# The visual read of the same DaTSCAN as `dat`. Agrees with it — one scan, one brain.
# No 'NA' member in this value set, so none is emitted.
def datscan_visual_interpretation(rng, subj):
    if "dat_pos" not in subj:
        subj["dat_pos"] = rng.random() < 0.55
    return "Positive" if subj["dat_pos"] else "Negative"


# ── 47. dcfdx ────────────────────────────────────────────────────────────── visit
# "Clinical Cognitive Diagnosis Summary"
# value_set: 1=NCI | 2=MCI | 3=MCI+ | 4=AD | 5=AD+ | 6=Other dementia   -- cell holds the CODE
# ROSMAP: "rendered at every assessment" -> per VISIT.
# MONOTONE NON-DECREASING: cognitive diagnosis does not improve. A subject who reaches AD does not
# return to NCI at the next visit. Enforced at draw time.
# ASSUMED: the progression rate (25% chance of worsening one step per visit).
def dcfdx(rng, subj):
    cur = subj.get("dcfdx_last", 1)
    if rng.random() < 0.25 and cur < 6:
        cur += 1
    subj["dcfdx_last"] = cur
    return cur


# ── 48. diagnosis ────────────────────────────────────────────────────────── visit
# "opinion on a participant's diagnosis"
# value_set: At-Risk RA | CLE | LN | OA | PsA | PsO | RA | SLE | SjD | control | dermatomyositis
#            | scleroderma | vitiligo
# A subject's diagnosis is a fact about them: it does not change randomly between visits.
# (change_in_diagnosis, batch 4, is the element that records when it DOES change.)
# The element exists in TWO dictionaries with different value sets -- the SysBio dictionary
# (At-Risk RA | CLE | LN | ...) and ARK (At-Risk RA | Not Applicable | OA | ... 16 values).
# So the list is NOT hardcoded: it is taken from whichever spec governs the table this row is in.
def diagnosis(rng, subj):
    if "diagnosis" not in subj:
        spec = subj.get("_spec") or {}
        enum = (spec.get("constraints") or {}).get("enum")
        subj["diagnosis"] = rng.choice(enum) if enum else None
    return subj["diagnosis"]


# ── 49. diagnosis_type ───────────────────────────────────────────────────── visit
# "How was diagnosis made?".  value_set: Clinical | Pathological | Unknown
# ASSUMED: 80% clinical. 'Unknown' is a missingValue.
def diagnosis_type(rng, subj):
    if rng.random() < 0.04:
        return "Unknown"
    return subj.setdefault("diagnosis_type",
                           "Clinical" if rng.random() < 0.80 else "Pathological")


# The programmes whose tables these functions may touch. WITHOUT this the registry is keyed
# by BARE NAME and is global: ARK's weight() -- which returns ARK's -1 sentinel and reasons
# about inches vs centimetres -- was being run on FUSION's weight column, in kg.
SCOPE = {"AMP-PD", "AMP-AD"}


BATCH_05 = {
    "cigarettes_per_day_current": cigarettes_per_day_current,
    "cohort": cohort,
    "cigarettes_per_day_past": cigarettes_per_day_past,
    "cogdx": cogdx,
    "cohort": cohort,
    "dat": dat,
    "datscan_visual_interpretation": datscan_visual_interpretation,
    "dcfdx": dcfdx,
    "diagnosis": diagnosis,
    "diagnosis_type": diagnosis_type,
}
