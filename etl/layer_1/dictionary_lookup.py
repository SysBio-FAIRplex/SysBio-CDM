#!/usr/bin/env python3
"""The dictionary lookup table: one row per source dictionary the mapping files cite, with the provider, the file,
the blocks citing it, and where it came from. Origin is taken from the private registry's dictionary folder layout
(source/<program>/..., external/ for public downloads) and is stated as recorded there, never assumed.

    python dictionary_lookup.py <private registry root> <out.tsv>
"""
import csv, glob, json, os, sys, collections


def main():
    reg, out = sys.argv[1], sys.argv[2]
    cites = collections.defaultdict(set)
    for f in glob.glob(os.path.join(reg, "mappings", "**", "*.json"), recursive=True) + glob.glob(os.path.join(reg, "drafts", "*", "*.json")):
        try: j = json.load(open(f, encoding="utf-8"))
        except Exception: continue
        if not isinstance(j, dict): continue
        for s in j.get("sources") or []:
            for d in (s.get("src_dictionary") or []) if isinstance(s.get("src_dictionary"), list) else ([s.get("src_dictionary")] if s.get("src_dictionary") else []):
                name = d if isinstance(d, str) else json.dumps(d, ensure_ascii=False)[:160]
                cites[name].add(j.get("registry_label") or os.path.basename(f))
    rows = []
    for p in sorted(glob.glob(os.path.join(reg, "dictionaries", "**", "*"), recursive=True)):
        if not os.path.isfile(p): continue
        rel = os.path.relpath(p, reg); parts = rel.split(os.sep)
        base = os.path.basename(p).lower()
        if "/unattributed/" in rel or "/provenance/" in rel or base.endswith(".md") or base.startswith(("read_first", "readme")) or any(m in base for m in ("manifest", "collection_meta", "identifying", "_meta.csv", "_meta.xlsx")): continue   # internal notes and data tables are not dictionaries
        provider = parts[2] if len(parts) > 2 and parts[1] in ("source", "input_formatted_dds") else (parts[1] if len(parts) > 1 else "")
        origin = "public download (external/)" if "/external/" in rel else ("derived here from a provider file (input_formatted_dds/)" if parts[1:2] == ["input_formatted_dds"] else "provider file as obtained; origin not recorded in the registry")
        citing = sorted({el for name, els in cites.items() if os.path.basename(p) in name or rel in name for el in els})
        rows.append([rel, provider, origin, os.path.getsize(p), ", ".join(citing)[:300]])
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n"); w.writerow(["dictionary_file", "provider", "origin", "bytes", "elements citing it"]); w.writerows(rows)
    print("dictionaries:", len(rows), "| cited by at least one element:", sum(1 for r in rows if r[4]))


if __name__ == "__main__":
    main()
