"""
Synthetic value generators — BATCH 8: the Krenn Synovitis Score.

ARK's own descriptions say what this is:

    krennLining        "...the degree of hyperplasia/enlargement of the synovial lining layer.
                        This is ONE OF THREE MEASURES USED TO DERIVE the Krenn Synovitis Score"
    krennStroma        "...stromal cell density. This is one of three measures used to derive..."
    krennInflammatory  "...the degree of inflammatory infiltrate. This is one of three..."
    krennSynovitisScore "The Krenn Synovitis Score (KSS)..."

So the total is DERIVED, not drawn. It is the sum of the three components, each scored 0-3, giving
0-9 (Krenn 2006). ARK states no Minimum or Maximum for any of them, so before this they were drawn
independently from the generic 0-100 window -- a synovitis score of 55.1, with components that did
not add up to it.

ARK also states the unknown sentinel: "If value unknown, use '-1'." That is a value the real files
carry, so it is emitted. A score cannot be summed from an unknown component, so the KSS is -1
whenever any component is.

All four are CONDITIONAL on biospecimenType == 'synovial tissue' (config/ark_conditional.tsv) --
the generator blanks them on every other kind of specimen.

fn(rng, subj) -> value.  ASSUMED marks a decision neither ARK nor the instrument makes.
"""

P_UNKNOWN = 0.05          # ASSUMED. ARK defines the -1 sentinel but not how often it is used.


def _krenn(rng, subj):
    """The three components for THIS specimen, held so the total agrees with them.

    Whichever of the four columns is drawn first fixes the triple; the other three read it back.
    Keyed on the specimen, not the subject -- an individual has several specimens.
    """
    sp = subj.get("_specimen") or {}
    key = "_krenn_%s" % sp.get("biospecimenID", "")
    if key not in subj:
        if rng.random() < P_UNKNOWN:
            subj[key] = (-1, -1, -1)                  # ARK's stated sentinel for unknown
        else:
            subj[key] = (rng.randint(0, 3), rng.randint(0, 3), rng.randint(0, 3))
    return subj[key]


def krennLining(rng, subj):
    return _krenn(rng, subj)[0]


def krennStroma(rng, subj):
    return _krenn(rng, subj)[1]


def krennInflammatory(rng, subj):
    return _krenn(rng, subj)[2]


def krennSynovitisScore(rng, subj):
    c = _krenn(rng, subj)
    return -1 if any(x < 0 for x in c) else sum(c)     # the KSS IS the sum of its components


# The programmes whose tables these functions may touch. WITHOUT this the registry is keyed
# by BARE NAME and is global: ARK's weight() -- which returns ARK's -1 sentinel and reasons
# about inches vs centimetres -- was being run on FUSION's weight column, in kg.
SCOPE = {"AMP-RA-SLE"}


BATCH_08 = {
    "krennLining": krennLining,
    "krennStroma": krennStroma,
    "krennInflammatory": krennInflammatory,
    "krennSynovitisScore": krennSynovitisScore,
}
