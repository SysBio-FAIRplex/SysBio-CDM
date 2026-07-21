#!/usr/bin/env python3
"""
Derive ARK's CONDITIONAL rules for the biospecimen table, and its Cell Ontology value set.

ARK's model carries rows whose `Attribute` is not an attribute at all but a VALUE -- 'synovial
tissue', 'saliva', 'flow-sorted cells' -- and whose `DependsOn` lists the columns that value
brings with it:

    synovial tissue    DependsOn  synovialCollectionProcedure, anatomicalSite, krennInflammatory,
                                  krennLining, krennStroma, krennSynovitisScore
    saliva             DependsOn  salivaCollectionProcedure
    flow-sorted cells  DependsOn  FACSPopulation, cellOntologyID, cellType, userDefinedCellType

That is a conditional requirement: those columns exist for THAT kind of specimen and no other.
Ignoring it is why a serum sample was carrying a Krenn SYNOVITIS score and a saliva collection
procedure.

The trigger column is found by asking which attribute's Valid Values contains that value -- so
'synovial tissue' resolves to biospecimenType, 'flow-sorted cells' to biospecimenSubtype. Nothing
is hand-copied.

Also emits ARK's own CL-cellType map. cellOntologyID's validation rule is `regex search ^CL:`, and
cellType is that identifier's LABEL, so the two must come from the same row of the map.

Reads only. Writes config/ark_conditional.tsv + config/ark_cell_ontology.tsv
"""
import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARK = os.path.join(ROOT, "inputs", "amp_dictionaries", "ark", "data_model-main")
MODEL = os.path.join(ARK, "model_contexts", "biospecimen", "ark.biospecimen_model.csv")
CLMAP = os.path.join(ARK, "annotation_maps", "CL-cellType.csv")


def main():
    rows = list(csv.DictReader(open(MODEL, newline="", encoding="utf-8-sig")))

    # value -> the attribute that declares it (biospecimenType, biospecimenSubtype, ...)
    owner = {}
    for r in rows:
        attr = (r.get("Attribute") or "").strip()
        for v in [x.strip() for x in (r.get("Valid Values") or "").split(",") if x.strip()]:
            owner.setdefault(v, attr)

    out = []
    for r in rows:
        a = (r.get("Attribute") or "").strip()
        dep = [x.strip() for x in (r.get("DependsOn") or "").split(",") if x.strip()]
        if not dep or a not in owner:
            continue                     # not a VALUE -- it is a template or a plain attribute
        out.append([owner[a], a, ",".join(dep)])

    p = os.path.join(ROOT, "config", "ark_conditional.tsv")
    with open(p, "w", newline="", encoding="utf-8") as fh:
        fh.write("#\tARK's conditional requirements, read off the biospecimen model's DependsOn.\n")
        fh.write("#\tA dependent column is emitted ONLY when its trigger column holds the trigger\n")
        fh.write("#\tvalue. A serum sample therefore carries no Krenn synovitis score.\n")
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["trigger_column", "trigger_value", "dependent_columns"])
        w.writerows(sorted(out))

    cl = [(r["cellOntologyID"], r["cellType"])
          for r in csv.DictReader(open(CLMAP, newline="", encoding="utf-8-sig"))]
    q = os.path.join(ROOT, "config", "ark_cell_ontology.tsv")
    with open(q, "w", newline="", encoding="utf-8") as fh:
        fh.write("#\tARK's annotation_maps/CL-cellType.csv -- the Cell Ontology identifier and its\n")
        fh.write("#\tlabel. cellOntologyID must match ^CL: (ARK validation rule); cellType is that\n")
        fh.write("#\tidentifier's label, so the pair is drawn from ONE row of this map.\n")
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["cellOntologyID", "cellType"])
        w.writerows(cl)

    print(f"conditional rules ({len(out)}):\n")
    for t, v, d in sorted(out):
        print(f"  {t:20s} == {v!r}")
        print(f"      -> {d}")
    print(f"\ncell ontology terms: {len(cl)}   e.g. {cl[47] if len(cl) > 47 else cl[0]}")
    print(f"\nwrote config/ark_conditional.tsv, config/ark_cell_ontology.tsv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
