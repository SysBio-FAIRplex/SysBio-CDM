#!/usr/bin/env python3
"""Export SHAREABLE mapping artifacts from mappings/*.json.

Strips the INTERNAL review field (manual_approval) — that is the private review
ledger, not part of the functional mapping. Everything else (variable, cde_id, reads_as, lands,
value_map, links, derived_from, derivation_rule, ...) is kept. Produces BOTH shapes so you can choose:
  * exports/mappings_shareable/<cde>.json  — cleaned PER-CDE (keep as the editable source of truth)
  * exports/mappings_bundle.json           — ONE combined file (the distribution / load artifact)

The working mappings/*.json (with your notes + approvals) are untouched.
"""
import glob, json, os

ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC    = os.path.join(ROOT, "mappings")
OUTDIR = os.path.join(ROOT, "exports", "mappings_shareable")
BUNDLE = os.path.join(ROOT, "exports", "mappings_bundle.json")
STRIP  = ("manual_approval",)


def clean(d):
    return {k: v for k, v in d.items() if k not in STRIP}


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    maps = []
    for fp in sorted(glob.glob(os.path.join(SRC, "*.json"))):
        d = clean(json.load(open(fp)))
        key = str(d.get("variable") or d.get("cde_id") or os.path.basename(fp)[:-5])
        maps.append((key, d))
        json.dump(d, open(os.path.join(OUTDIR, os.path.basename(fp)), "w"), indent=2, ensure_ascii=False)
    maps.sort(key=lambda kv: kv[0])
    bundle = {"schema": "amp-cde-omop-mapping", "schema_version": 1,
              "count": len(maps), "mappings": [d for _, d in maps]}
    json.dump(bundle, open(BUNDLE, "w"), indent=2, ensure_ascii=False)

    leaked = sorted({k for _, d in maps for k in STRIP if k in d})
    print(f"wrote {len(maps)} cleaned per-CDE -> {os.path.relpath(OUTDIR, ROOT)}/")
    print(f"wrote combined bundle           -> {os.path.relpath(BUNDLE, ROOT)}")
    print(f"leaked review fields: {leaked or 'NONE'}")


if __name__ == "__main__":
    main()
