"""
Specimen lineage for AMP-RA/SLE (ARK's BiospecimenMetadataTemplate).

ARK carries lineage in the source file itself:

    biospecimenID        the specimen
    parentBiospecimenID  "The biospecimenID associated with the originating biospecimen for
                          derived or child biospecimens."   -> empty for a COLLECTED specimen
    primaryCellSource    "the biological source material from which a primary cell culture was
                          derived."  Required when biospecimenType == 'primary cell culture'.

So a derived specimen points at the specimen it came from, and a cultured one also names the
MATERIAL it came from. Those two must agree: primaryCellSource is the parent's biospecimenType.
Before this, every specimen was drawn independently -- one biospecimen per individual, no parents,
and a `serum` specimen recorded as having been cultured from `kidney`.

ARK also separates the MATERIAL from its FORM:
    biospecimenType     what was collected      (synovial tissue, whole blood, ...)   20 values
    biospecimenSubtype  its form before assay   (fresh tissue, cell suspension, ...)   9 values
A cell suspension OF synovial tissue is still synovial tissue; only the FORM changed. So a
preparation keeps its parent's biospecimenType and changes the subtype.

ASSUMED marks a decision ARK does not make. ARK declares the columns, the value sets and the
derivation rule; it does not say which specimens get collected, how many, or what is prepared
from what.
"""

# ARK's 20 biospecimenType values, split by whether the material is COLLECTED from the
# participant or PRODUCED in the lab. ASSUMED -- ARK lists the values but does not classify them.
# 'primary cell culture' and 'cell line' are the two ARK itself treats as derived: both DependOn
# cellType/cellOntologyID, and primary cell culture additionally requires primaryCellSource,
# "the biological source material from which [it] was derived".
COLLECTED = ["kidney biopsy", "saliva", "salivary gland", "skin biopsy", "skin swab", "stool",
             "suction blister cells", "suction blister fluid", "synovial fluid",
             "synovial tissue", "urine", "uvea", "whole blood"]
CULTURED = ["primary cell culture", "cell line"]

# ASSUMED. Blood fractions are not collected -- they are separated from a whole blood draw. ARK
# lists them as biospecimenTypes but says nothing about where they come from. This is the one
# place a child's biospecimenType DIFFERS from its parent's.
FROM_BLOOD = ["PBMCs", "plasma", "serum", "total leukocytes"]

# ARK's 9 biospecimenSubtype values, split by whether the form is a PRESERVATION of the material
# as collected, or a PREPARATION made from it. ASSUMED -- ARK lists them, it does not classify them.
PRESERVED = ["fresh tissue", "frozen tissue/fluid", "FFPE tissue", "PFA-fixed tissue"]
PREPARED = ["cell suspension", "nuclei suspension", "cell or tissue lysate", "supernatant"]

# ASSUMED. ARK constrains neither of these, and drawing them uniformly produced nonsense: whole
# blood recorded as 'PFA-fixed tissue', and a SERUM specimen with a cell suspension and
# flow-sorted cells hanging off it.
#
#   FLUID      is not fixed or embedded as tissue. ARK's own subtype 'frozen tissue/fluid' is the
#              one that names fluid, so a fluid takes that.
#   ACELLULAR  has no cells to suspend, sort or culture. Serum and plasma are what is LEFT once
#              the cells are removed. Note urine is NOT here: ARK lists it in primaryCellSource,
#              so ARK itself says cells are grown from urine.
FLUID = {"whole blood", "serum", "plasma", "urine", "saliva", "synovial fluid",
         "suction blister fluid"}
ACELLULAR = {"serum", "plasma", "suction blister fluid"}

# ARK's primaryCellSource value set. A primary cell culture can only be derived from one of these,
# so it is only grown from a parent whose biospecimenType appears here.
CELL_SOURCE = ["PBMCs", "kidney", "pannus-derived dermis", "pannus-derived epidermis",
               "salivary gland", "synovial tissue", "total leukocytes", "urine", "uvea",
               "whole blood"]


def _sp(sid, seq, typ, sub, visit, parent=None, source=None):
    return {"biospecimenID": int(f"{sid}{seq:02d}"),
            "parentBiospecimenID": parent,
            "biospecimenType": typ,
            "biospecimenSubtype": sub,
            "primaryCellSource": source,
            "visitID": visit,
            "_seq": seq}


def plan(rng, sid, visits):
    """Every specimen for one individual, PARENTS BEFORE CHILDREN.

    ASSUMED: 2-3 collection events, each yielding one collected specimen; then what is prepared
    from each. ARK sets no number. Enough specimens are drawn that ARK's declared types all
    appear across the cohort -- otherwise a column like krennSynovitisScore exists or vanishes
    depending on whether a uniform draw happened to land on 'synovial tissue'.
    """
    out, seq = [], 0
    vs = [v for v, _ in visits] or ["M0"]

    def preserved(typ, rng):
        return "frozen tissue/fluid" if typ in FLUID else PRESERVED[rng.randrange(len(PRESERVED))]

    for _ in range(rng.randint(2, 3)):
        visit = vs[rng.randrange(len(vs))]
        seq += 1
        typ = COLLECTED[rng.randrange(len(COLLECTED))]
        root = _sp(sid, seq, typ, preserved(typ, rng), visit)
        out.append(root)

        # A whole blood draw is separated into its fractions. Each is a child of the draw.
        stock = [root]
        if typ == "whole blood":
            for frac in FROM_BLOOD:
                if rng.random() < 0.5:
                    seq += 1
                    out.append(_sp(sid, seq, frac, "frozen tissue/fluid", visit,
                                   parent=root["biospecimenID"]))
                    stock.append(out[-1])

        for p in list(stock):
            mat = p["biospecimenType"]

            # Something is prepared from the material: a cell/nuclei suspension, a lysate.
            # Not from serum or plasma -- there are no cells left in them to prepare.
            if mat not in ACELLULAR and rng.random() < 0.6:
                seq += 1
                prep = _sp(sid, seq, mat, PREPARED[rng.randrange(len(PREPARED))], visit,
                           parent=p["biospecimenID"])
                out.append(prep)

                # Cells are sorted OUT of a suspension -- a third generation.
                if prep["biospecimenSubtype"] in ("cell suspension", "nuclei suspension") \
                        and rng.random() < 0.5:
                    seq += 1
                    out.append(_sp(sid, seq, mat, "flow-sorted cells", visit,
                                   parent=prep["biospecimenID"]))

            # A culture is grown from the material. ARK REQUIRES primaryCellSource for a culture,
            # and it IS the material it came from -- so a culture is only grown from a parent
            # whose biospecimenType is one ARK actually lists as a cell source.
            if mat in CELL_SOURCE and rng.random() < 0.25:
                seq += 1
                out.append(_sp(sid, seq, CULTURED[rng.randrange(len(CULTURED))],
                               "cell suspension", visit,
                               parent=p["biospecimenID"], source=mat))
    return out
