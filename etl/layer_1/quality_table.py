#!/usr/bin/env python3
"""Quality table of the registry's elements, from the mapping files alone: is the element well defined, used (a real
source pinned), fully mapped (every block has value lines or a declared form), and landed (an OMOP concept). Optional:
source values a run left unmapped (from a run's stage1 audit). Writes one TSV row per element file.

    python quality_table.py <registry root> <out.tsv> [<stage1 folder of a run>]
"""
import csv, glob, json, os, sys, collections


def read_tsv(p):
    with open(p, encoding="utf-8", newline="") as f: return list(csv.DictReader(f, delimiter="\t"))


def main():
    reg, out = sys.argv[1], sys.argv[2]; stage1 = sys.argv[3] if len(sys.argv) > 3 else None
    unmapped = collections.Counter()
    if stage1:
        for p in glob.glob(os.path.join(stage1, "*", "audit", "unmapped_values.tsv")):
            for r in read_tsv(p):
                if "date" not in r.get("why_not_written", "").lower(): unmapped[r["element"]] += int(r.get("source_rows") or 1)
    rows = []
    files = sorted(glob.glob(os.path.join(reg, "mappings", "**", "*.json"), recursive=True) + glob.glob(os.path.join(reg, "drafts", "*", "*.json")))
    for f in files:
        rel = os.path.relpath(f, reg)
        if "/superseded/" in rel or "/_backups/" in rel or rel.endswith("TEMPLATE.json"): continue
        try: j = json.load(open(f, encoding="utf-8"))
        except Exception as e: rows.append([rel, "", "unreadable: %s" % type(e).__name__] + [""] * 9); continue
        if not isinstance(j, dict) or "sources" not in j: continue
        label = j.get("registry_label") or os.path.splitext(os.path.basename(f))[0]
        d = str(j.get("definition") or "").strip()
        defined = "yes" if d and not d.startswith(("DRAFT - to be authored", "GENERATED", "RETIRED")) else ("retired" if d.startswith("RETIRED") else "no")
        land = [x for x in (j.get("sysbio_etl") or []) if isinstance(x, dict) and (x.get("defining_concept_id") or {}).get("id")]
        landed = "yes" if land else "no"; landing = "; ".join("%s %s (%s)" % ((x.get("defining_concept_id") or {}).get("id"), (x.get("defining_concept_id") or {}).get("name"), x.get("table")) for x in land)
        blocks = [s for s in (j.get("sources") or []) if str(s.get("status") or "") not in ("excluded", "withdrawn", "superseded")]
        pinned = [s for s in blocks if any(d_.get("sha256") or d_.get("source_id") for d_ in (s.get("layer_1_etl") or {}).get("data_files") or [])]
        gaps = []
        for i, s in enumerate(blocks):
            l1 = s.get("layer_1_etl") or {}; form = str(l1.get("value_form") or ""); vm = l1.get("value_map") or []
            if not form and not vm: gaps.append("block %d: no value form and no value lines" % i)
            elif form in ("nominal", "ordinal", "boolean", "code") and not vm: gaps.append("block %d: %s with no value lines" % (i, form))
        covered = "yes" if blocks and not gaps else ("no blocks" if not blocks else "no")
        programs = sorted({str(s.get("program")) for s in blocks})
        quality = "yes" if defined == "yes" and landed == "yes" and pinned and covered == "yes" else "no"
        rows.append([rel, label, quality, defined, landed, "yes" if pinned else "no", covered, str(len(blocks)), str(len(pinned)), ", ".join(programs), landing, "; ".join(gaps)[:300], str(unmapped.get(label, 0)), d[:200]])
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n"); w.writerow(["file", "element", "meets all four", "defined", "landed (OMOP)", "source pinned", "every block covered", "blocks", "pinned blocks", "programs", "landing", "coverage gaps", "unmapped source rows in the run", "definition"]); w.writerows(rows)
    c = collections.Counter(r[2] for r in rows); print("elements:", len(rows), "| meet all four:", c.get("yes", 0), "| do not:", c.get("no", 0))
    print("  defined:", collections.Counter(r[3] for r in rows), "| landed:", collections.Counter(r[4] for r in rows), "| pinned:", collections.Counter(r[5] for r in rows), "| covered:", collections.Counter(r[6] for r in rows))


if __name__ == "__main__":
    main()
