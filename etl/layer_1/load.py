#!/usr/bin/env python3
"""Layer 1 loader, version 0. Writes harmonized values for every cohort from the files the ETL input manifest lists (see dryrun.py).

Everything it does is decided by data: the mapping registry (which column, which value map, which rows), the cohort
declarations and bridges (who is in scope, which column says whose row it is), and the declared row keys and row
filters. No cohort name, column name or value is written in this file. No regex.

    .venv/bin/python load.py [output folder]

Per cohort it writes layer1_values.tsv (long: one row per distinct value with its keys and full lineage) and one wide
table per grain. The grain of an element is MEASURED: the coarsest key at which it has one value per key. Nothing is
written per cell: rows of a per-cell table collapse to distinct values per participant and sample, with a row count.
Calendar dates are not written. A value with no line in its value map is not written; it goes to audit/unmapped_values.tsv.
"""
import collections, csv, datetime, json, os, subprocess, sys
import dryrun as D
HERE_DIR = os.path.dirname(os.path.abspath(__file__))

LEVELS = [("dataset", ()), ("participant", ("participant_id",)), ("participant_visit", ("participant_id", "visit")),
          ("participant_sample", ("participant_id", "sample_id")), ("participant_sample_visit", ("participant_id", "sample_id", "visit")),
          ("participant_sample_visit_detail", ("participant_id", "sample_id", "visit", "other_keys"))]


def harmonizer(b):
    vm, form = b["value_map"], (b["value_form"] or "")
    m, anytok, anyconst = {}, False, None
    for e in vm:
        hv = e.get("harmonized_value")
        for k in ("source_value", "source_encoding"):
            sv = e.get(k)
            if sv in (None, ""):
                continue
            sv = str(sv).strip()
            if sv == "<any>":
                anytok = True
                if hv not in (None, "", "<value>"):
                    anyconst = str(hv)          # an <any> line with a literal harmonized value is a CONSTANT, not a pass-through
            else:
                m.setdefault(sv, None if hv is None else str(hv))
    numeric = form in ("continuous", "interval", "binned") or any("interval" in e for e in vm)

    def f(v):
        if form == "date":
            return None, "calendar dates are not written in version 0"
        if v == "" and b["blank_hv"] is not None:     # a value line whose source value is blank: a blank cell means this
            return b["blank_hv"], "blank-cell line"
        if v in m:
            if m[v] is None:
                return None, "null line: the value map says this source value is not written"
            return (v if m[v] == "<value>" else m[v]), "value map line"
        if anytok:
            return (anyconst, "constant from the <any> line") if anyconst is not None else (v, "pass-through <any>")
        if numeric:
            try:
                x = float(v)
                return (str(int(x)) if x.is_integer() and "e" not in v.lower() else v), "number"
            except ValueError:
                return None, "not a number and no line in the value map"
        if not vm and form in ("text", "identifier"):
            return v, "identifier or text"
        return None, "no line in the value map"
    return f


def cohort_tables(crow, coh, blocks, by_sha, profiles, problems, keys):
    """Yield (table, blocks pinned to its file, sha256) for every file the ETL input manifest lists for this cohort."""
    groups = collections.OrderedDict()
    for r in D.manifest_rows(coh.name):
        if not os.path.exists(r["path"]):
            problems.append((coh.name, r["file"], "file missing")); continue
        sha = D.sha256(r["path"])
        if r.get("sha256") and r["sha256"] != sha:
            problems.append((coh.name, r["file"], "sha256 differs from the manifest")); continue
        rel = os.path.relpath(r["path"], D.DM)
        g = groups.setdefault(sha, dict(path=r["path"], file=rel, entries=[], source_ids={str(d["source_id"]) for _, d in by_sha.get(sha, []) if d.get("source_id")}))
        g["entries"].append((r.get("sheet") or None, profiles.get((coh.name, rel, r.get("sheet") or ""))))
    for sha, g in groups.items():
        bl = [b for b, d in by_sha.get(sha, [])]
        if not bl:
            continue
        tables = []
        for sheet, prof in g["entries"]:
            if not prof:      # no reader profile: the blocks that pin this file and sheet declare its layout and, through their grain, whether it is dataset-level
                lay = {}
                for b_, d_ in by_sha.get(sha, []):
                    kinds_ = {D.kind_of(x.get("file", "")) for x in b_["pins"] if x.get("file")}
                    if len(kinds_) > 1: continue                      # a block over files of several kinds declares no layout for any of them
                    if (b_["sheet"] or "") in (sheet or "", ""):
                        for k_ in ("file_type", "header_row", "data_start"):
                            if b_["layout"].get(k_) not in (None, ""): lay.setdefault(k_, b_["layout"][k_])
                        if b_["grain_declared"] == "dataset": lay["dataset_level"] = True
                if lay: prof = {"kind": lay.get("file_type", ""), "header_row": str(lay.get("header_row", "") or ""), "data_start": str(lay.get("data_start", "") or ""), "sample_column": "", "other_keys": "dataset_level" if lay.get("dataset_level") else ""}
            kind = (prof or {}).get("kind") or D.kind_of(g["path"])
            if kind == "xlsx" and sheet in (None, ""):
                labels = {lab for b in bl for lab in b["labels"]}
                for sname, rows in D.workbook(g["path"]).items():
                    hr = next((i for i, r in enumerate(rows[:D.HEADER_SEARCH_ROWS]) if any(c.strip() in labels for c in r)), None)
                    if hr is None:
                        continue
                    data = [r for r in rows[hr + 1:] if any(x != "" for x in r)]
                    tables.append(dict(file=g["file"], sheet=sname, header=list(rows[hr]), rows=(lambda d=data: iter(d)), kind=kind, dataset_level=False, sample_column="", layout="measured"))
                continue
            hr = int(prof["header_row"]) if prof and prof["header_row"] else None
            ds = int(prof["data_start"]) if prof and prof["data_start"] else None
            head, rows = D.open_table(g["path"], kind, sheet, hr, ds)
            if head is None:
                problems.append((coh.name, g["file"], "no reader for this file type"))
                continue
            tables.append(dict(file=g["file"], sheet=sheet or "", header=head, rows=rows, kind=kind, layout="declared" if prof else "by type",
                               dataset_level=(kind == "sidecar" or "dataset_level" in (prof or {}).get("other_keys", "")), sample_column=(prof or {}).get("sample_column", "")))
        if not tables:
            continue
        fpart = next((coh.file_participant[s] for s in g["source_ids"] if s in coh.file_participant), None)
        for t in tables:
            declared = keys.get((coh.name, t["file"], t["sheet"])) or keys.get((coh.name, t["file"], "")) or keys.get(("__sha__", sha, t["sheet"])) or keys.get(("__sha__", sha, ""), ("", ""))
            spec_keys = keys.get(("__sha__", sha, t["sheet"])) or keys.get(("__sha__", sha, ""), ("", "", ""))
            t["id_column"] = coh.declared_id.get((os.path.basename(t["file"]), t["sheet"]), "") or declared[0]
            t["sample_column"] = declared[1] or t["sample_column"]
            t["visit_column"] = spec_keys[2] if len(spec_keys) > 2 else ""
            t["file_participant"] = fpart
        placed = D.attach(bl, tables)
        for ti, t in enumerate(tables):
            if placed.get(ti):
                yield t, placed[ti], sha


COLUMN_GAPS = []        # (cohort, file, sheet, column, columns in the file): header columns no block reads

def load_table(coh, t, attached, sha, rowkeys, filters, noemit, agg, unm, rep, forced):
    head = t["header"]
    pos = collections.defaultdict(list)
    for i, h in enumerate(head):
        pos[h].append(i)
    key = (os.path.basename(t["file"]), t["sheet"])
    fspell = coh.file_spell.get(key, {})
    to_p = lambda v: fspell.get(v) or coh.resolve(v)
    # Keys come from the registry's identity elements (and, where present, the declaration files that override them).
    # No column is ever chosen by its contents.
    id_i = pos[t["id_column"]][0] if t["id_column"] and pos.get(t["id_column"]) else None
    s_i = pos[t["sample_column"]][0] if t["sample_column"] and pos.get(t["sample_column"]) else None
    rowkey = id_i is not None or s_i is not None
    # coverage: every header column of this table that no block reads and that is not a key (the gap report)
    v_i = pos[t.get("visit_column")][0] if t.get("visit_column") and pos.get(t.get("visit_column")) else None
    covered = {ci for b, ci, pre in attached if ci is not None} | {i for i in (id_i, s_i, v_i) if i is not None}
    covered |= {i for i, h in enumerate(head) if any(h in (b.get("labels") or ()) for b, ci, pre in attached)}   # every column of a paired or multi-column block
    for i, h in enumerate(head):
        if i not in covered and str(h).strip(): COLUMN_GAPS.append((coh.name, t["file"], t["sheet"], str(h), len(head)))
    keyed = rowkey or bool(t["file_participant"])
    base = os.path.basename(t["file"])

    def skip(b, why):
        rep[(coh.name, b["mapping_file"], b["block"], b["label"], base, t["sheet"])]["skipped"] = why
    if not keyed and not t["dataset_level"]:
        for b, ci, pre in attached:
            skip(b, "no declared participant or sample key column for this table (file-participant manifest, key_columns.tsv, reader profile)")
        return
    if t["layout"] == "measured" and not rowkey:
        for b, ci, pre in attached:
            skip(b, "first data row undeclared for this sheet and no row key")
        return
    filt = filters.get((coh.name, t["file"], t["sheet"]))
    if filt and not pos.get(filt[0]):
        for b, ci, pre in attached:
            skip(b, "declared row filter column %r is not in the table" % filt[0])
        return
    visit_i = pos[t["visit_column"]][0] if t.get("visit_column") and pos.get(t["visit_column"]) else next((pos[c][0] for c in rowkeys.get("visit", []) if pos.get(c)), None)
    samp_i = next((pos[c][0] for c in rowkeys.get("sample", []) if pos.get(c)), None)
    usable = []
    for b, ci, pre in attached:
        structural = [p for p in pre if not p.startswith("DUP:")]
        if b["label"] in noemit:
            skip(b, "element is declared never written: " + noemit[b["label"]])
        elif b["role"] == "lineage_blueprint":
            skip(b, "lineage blueprint: declares derivation, never written as a column")
        elif ci is None or structural:
            skip(b, "; ".join(structural) or "column not found")
        else:
            extra = b["key_columns"] if isinstance(b["key_columns"], dict) else {}
            eidx = [(k, pos[c][0]) for k, c in extra.items() if pos.get(c)] if all(pos.get(c) for c in extra.values()) else []
            usable.append((b, ci, harmonizer(b), eidx))
            if samp_i is not None:
                forced.add((b["label"], b["mapping_file"], b["block"], t["file"], t["sheet"]))
            rep[(coh.name, b["mapping_file"], b["block"], b["label"], base, t["sheet"])]["readings"] += 0
    if not usable:
        return
    first = lambda cell: (D.cell_values(cell) or [""])[0]
    pooled = [0]
    for b, ci, h, eidx in usable:
        rr = rep[(coh.name, b["mapping_file"], b["block"], b["label"], base, t["sheet"])]
        rr.update(source_column_read=head[ci], source_file_sha256=sha, source_file=t["file"], row_filter=(json.dumps(b["applies"]["conds"]) if b["applies"] else (" ".join(filt) if filt else "")),
                  participant_key_column=(head[id_i] if id_i is not None else ("file-level: " + t["file_participant"] if t["file_participant"] else "")),
                  sample_key_column=(head[samp_i] if samp_i is not None else (head[s_i] if s_i is not None else "")), visit_key_column=(head[visit_i] if visit_i is not None else ""))
    rows_in_scope = 0
    for r in t["rows"]():
        p, key_text = None, False
        if id_i is not None and id_i < len(r):
            named = set()
            for v in D.cell_values(r[id_i]):
                key_text = True
                q = to_p(v)
                if coh.known(q):
                    named.add(q)
                p = q or p
            if len(named) > 1:
                pooled[0] += 1
                continue
        s = None
        if s_i is not None and s_i < len(r):
            vals = D.cell_values(r[s_i])
            s = vals[0] if vals else None
            key_text = key_text or bool(vals)
            if p is None and s is not None:
                p = coh.sample_participant(s)
        if p is None and t["file_participant"] and not key_text:
            p = t["file_participant"]
        if keyed and not coh.known(p):
            continue
        if filt:
            cell = first(r[pos[filt[0]][0]]) if pos[filt[0]][0] < len(r) else ""
            if not (cell == filt[2] if filt[1] == "equals" else cell.startswith(filt[2])):
                continue
        rows_in_scope += 1
        if samp_i is not None:          # a declared sample id column is the row's sample key
            s = (first(r[samp_i]) if samp_i < len(r) else "") or None
        vis = first(r[visit_i]) if visit_i is not None and visit_i < len(r) else ""
        get = lambda col: (r[pos[col][0]] if len(pos.get(col, [])) >= 1 and pos[col][0] < len(r) else None)
        for b, ci, h, eidx in usable:
            if ci >= len(r) or (p and p in b["drops"]):
                continue
            if b["applies"] is not None and not D.row_applies(b["applies"], get):
                continue
            ek = ";".join("%s=%s" % (k, first(r[i]) if i < len(r) else "") for k, i in eidx)
            cell_vals = D.cell_values(r[ci])
            if not cell_vals and b["blank_hv"] is not None:
                cell_vals = [""]          # the block declares what a blank cell means; let it through to the value map
            if b["separator"]:            # the block declares that one cell may list several values
                cell_vals = [x.strip() for v in cell_vals for x in v.split(b["separator"]) if x.strip()]
            for val in cell_vals:
                if val in b["missing"]:
                    continue
                hv, why = h(val)
                if hv is None:
                    unm[(coh.name, b["mapping_file"], b["block"], b["label"], base, t["sheet"], head[ci], val, why)] += 1
                    continue
                agg[(b["label"], p or "", s or "", vis, ek, hv, val, b["unit"], b["mapping_file"], b["block"], "" if b["precedence"] is None else b["precedence"], t["file"], t["sheet"], head[ci], sha, why)] += 1
                rr = rep[(coh.name, b["mapping_file"], b["block"], b["label"], base, t["sheet"])]
                rr["readings"] += 1
                rr["participants"].add(p or "")
    for b, ci, h, eidx in usable:
        rep[(coh.name, b["mapping_file"], b["block"], b["label"], base, t["sheet"])]["rows_in_scope"] = rows_in_scope
    if pooled[0]:
        for b, ci, h, eidx in usable:
            rep[(coh.name, b["mapping_file"], b["block"], b["label"], base, t["sheet"])]["skipped"] = "%d rows name more than one participant (pooled) and were not credited to any one of them" % pooled[0]


def write(path, cols, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(cols)
        w.writerows(rows)




def place(coh, agg, outdir, placement, conflicts, forced, setvalued, nullagree, identity=None):
    """Pivot the readings to wide tables. Grain is measured per SOURCE (one block reading one file): the coarsest key at
    which that source has one value per key. Sources of one element that land on the same key are then reconciled:
    equal values agree; where every competing reading declares a precedence the lowest number wins; otherwise the
    cell is left blank and every reading is logged in conflicts.tsv."""
    def keyof(k, fields):
        d = dict(participant_id=k[1], sample_id=k[2], visit=k[3], other_keys=k[4])
        return tuple(d[f] for f in fields)
    by_src = collections.defaultdict(list)
    for k in agg:
        by_src[(k[0], k[8], k[9], k[11], k[12])].append(k)
    cells = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(list)))
    stats = collections.defaultdict(lambda: collections.Counter())
    for src, ks in sorted(by_src.items()):
        label = src[0]
        if all(k[1] == "" for k in ks):
            li = 0
        else:
            li = None
            for i in range(3 if src in forced else 1, len(LEVELS)):     # a row with a declared sample id is never coarser than the sample
                seen = collections.defaultdict(set)
                for k in ks:
                    seen[keyof(k, LEVELS[i][1])].add("<set>" if (k[8], k[9]) in setvalued else k[5])   # a set-valued block holds several values per key by design
                if all(len(v) == 1 for v in seen.values()):
                    li = i
                    break
        if li is None:
            stats[(label, "long table only")]["sources"] += 1
            stats[(label, "long table only")]["readings"] += len(ks)
            continue
        stats[(label, LEVELS[li][0])]["sources"] += 1
        stats[(label, LEVELS[li][0])]["readings"] += len(ks)
        for k in ks:
            cells[LEVELS[li][0]][keyof(k, LEVELS[li][1])][label].append(k)
    tables = collections.defaultdict(dict)
    for name, fields in LEVELS:
        for kk, per_label in cells[name].items():
            row = tables[name].setdefault(kk, {})
            for label, ks in per_label.items():
                kf = label if label in fields else (identity or {}).get(label)   # an identity element declares which key it carries (participant_id, sample_id, visit)
                if kf in fields:        # an identity element that is also this table's key: the key column already carries it, so no second column
                    keyval = kk[fields.index(kf)]
                    row[label + "_source_value"] = " | ".join(sorted({k[6] for k in ks}))
                    if any(k[5] != keyval for k in ks):
                        row[label + "_alias"] = " | ".join(sorted({k[5] for k in ks if k[5] != keyval}))   # the element carries another id for the same sample
                    continue
                if len({k[5] for k in ks}) > 1:
                    # several values at one key. Set-valued by design when the block declares a separator, or when the registry
                    # maps several columns of ONE file into this element (each column is a member of the set).
                    if all((k[8], k[9]) in setvalued for k in ks) or (len({k[11] for k in ks}) == 1 and len({k[13] for k in ks}) > 1):
                        stats[(label, name)]["keys holding a set of values"] += 1
                        row[label] = " | ".join(sorted({k[5] for k in ks}))
                        row[label + "_source_value"] = " | ".join(sorted({k[6] for k in ks}))
                        if any(k[7] for k in ks):
                            row[label + "_unit"] = next(k[7] for k in ks if k[7])
                        continue
                    # registry precedence: a block without a precedence number is primary; numbered blocks are fallbacks (1 before 2 before 3)
                    primary = [k for k in ks if k[10] == ""]
                    if primary and len({k[5] for k in primary}) == 1:
                        ks = primary
                        stats[(label, name)]["keys settled by precedence"] += 1
                    elif not primary:
                        best = min(float(k[10]) for k in ks)
                        ks = [k for k in ks if float(k[10]) == best]
                        stats[(label, name)]["keys settled by precedence"] += 1
                    if len({k[5] for k in ks}) > 1:
                        stats[(label, name)]["keys left blank: sources disagree"] += 1
                        for k in ks:
                            conflicts.append((coh.name, label) + (k[1], k[2], k[3], k[4]) + (k[5], k[6], k[11], k[12], k[13], k[8], k[9], k[10]))
                        continue
                row[label] = ks[0][5]
                row[label + "_source_value"] = " | ".join(sorted({k[6] for k in ks}))
                if any(k[7] for k in ks):
                    row[label + "_unit"] = next(k[7] for k in ks if k[7])
    for (label, table), c in sorted(stats.items()):
        placement.append((coh.name, label, table, c["sources"], c["readings"], c["keys settled by precedence"], c["keys left blank: sources disagree"]))
    for p in coh.participants:
        tables["participant"].setdefault((p,), {})
    written = {}
    for name, fields in LEVELS:
        if name not in tables:
            continue
        cols = sorted({c for row in tables[name].values() for c in row})
        write(os.path.join(outdir, name + ".tsv"), list(fields) + cols, [list(kk) + [row.get(c, "") for c in cols] for kk, row in sorted(tables[name].items())])
        written[name] = (len(tables[name]), len([c for c in cols if not c.endswith(("_source_value", "_unit"))]))
    return written


REGISTRY = collections.defaultdict(list)
_msha = {}


def mapping_sha(mf, commit):
    if mf not in _msha:
        p = os.path.join(D.REG, mf)
        dirty = subprocess.run(["git", "-C", D.REG, "status", "--porcelain", "--", mf], capture_output=True, text=True).stdout.strip()
        _msha[mf] = (D.sha256(p), commit + (" + working copy" if dirty else ""))
    return _msha[mf]


def polluted(text):
    """Text that records the mapping process rather than the provider's meaning does not belong in a release."""
    t = text or ""
    words = set("".join(c if c.isalnum() else " " for c in t).split())
    return bool(words & {"DRAFT", "TODO", "session", "ruling", "Ruled", "ruled"}) or "2026-" in t


def registry_tables(coh, crow, agg, rep, placement, blocks, cdir, commit, out):
    """The provenance tables that travel with the release: element, value_map, link, identifiers."""
    bidx = {(b["mapping_file"], b["block"]): b for b in blocks}
    rdir = os.path.join(cdir, "registry")
    os.makedirs(rdir, exist_ok=True)
    # element: one row per element written for this cohort
    by_el = collections.defaultdict(list)
    for k, n in agg.items():
        by_el[k[0]].append((k, n))
    tables = collections.defaultdict(set)
    for p in placement:
        tables[p[1]].add(p[2])
    el_rows = []
    for label, items in sorted(by_el.items()):
        bl = [bidx[(k[8], k[9])] for k, _ in items if (k[8], k[9]) in bidx]
        uniq = lambda xs: " | ".join(sorted({str(x) for x in xs if x not in (None, "", [])}))
        vals = sorted({k[5] for k, _ in items})
        mfs = sorted({k[8] for k, _ in items})
        hv = sorted({json.dumps(b["harmonized_values"], ensure_ascii=False) for b in bl})
        el_rows.append([coh.name, label, uniq(b["src_definition"] for b in bl if not polluted(b["src_definition"])), " | ".join(sorted(tables.get(label, {"layer1_values only"}))),
                        len(vals), "; ".join(vals[:30]) + (" ..." if len(vals) > 30 else ""), len({k[1] for k, _ in items if k[1]}), sum(n for _, n in items),
                        uniq(b["unit"] for b in bl), uniq(b["value_form"] for b in bl), uniq(b["datatype"] for b in bl), " | ".join(hv),
                        uniq((b["grain_declared"] or ("one_per=" + json.dumps(b["one_per"]) if b["one_per"] else "")) for b in bl),
                        uniq(b["program"] for b in bl), uniq(b["status"] for b in bl),
                        "; ".join("%s@%s" % (mf, mapping_sha(mf, commit)[0]) for mf in mfs), uniq(mapping_sha(mf, commit)[1] for mf in mfs)])
    EL = ["cohort", "element", "provider_wording", "table", "n_values_written", "values_written", "participants_with_value", "rows_in_layer1_values", "unit", "value_form", "datatype",
          "harmonized_values_declared", "grain_declared", "programs", "block_status", "mapping_files", "registry_commit"]
    # value_map: one row per element, program, source file, sheet, column, source value, harmonized value
    vm = collections.defaultdict(lambda: [0, set()])
    for k, n in agg.items():
        b = bidx.get((k[8], k[9]))
        key = (coh.name, k[0], b["program"] if b else "", os.path.basename(k[11]), k[12], k[13], k[6], k[5], k[7], k[15], k[8], k[9], mapping_sha(k[8], commit)[0])
        vm[key][0] += n
        vm[key][1].add(k[1])
    VM = ["cohort", "element", "program", "source_file", "sheet", "source_column", "source_value", "harmonized_value", "unit", "how", "rows", "participants", "mapping_file", "block", "mapping_file_sha256"]
    vm_rows = [list(key[:10]) + [v[0], len({p for p in v[1] if p})] + list(key[10:]) for key, v in sorted(vm.items())]
    # link: one row per element, block, source file, sheet that was pinned
    LK = ["cohort", "element", "mapping_file", "block", "block_status", "mapping_file_sha256", "program", "source_label", "source_definition", "source_column_read", "source_file", "sheet", "source_file_sha256",
          "pin_source_id", "rows_in_scope", "source_rows_read", "participants", "row_filter", "missing_values_declared", "skipped_because"]
    lk_rows = []
    for (cname, mf, bi, label, base, sheet), v in sorted(rep.items()):
        b = bidx.get((mf, bi))
        pin = next((d for d in (b["pins"] if b else []) if os.path.basename(d.get("file") or "") == base), {})
        lk_rows.append([cname, label, mf, bi, b["status"] if b else "", mapping_sha(mf, commit)[0], b["program"] if b else "", b["source_label"] if b else "", (b["src_definition"] if b and not polluted(b["src_definition"]) else ""), v["source_column_read"],
                        v["source_file"] or base, sheet, v["source_file_sha256"] or pin.get("sha256", ""), pin.get("source_id") or "", v["rows_in_scope"], v["readings"],
                        len({p for p in v["participants"] if p}), v["row_filter"], "; ".join(sorted(b["missing"])) if b else "", v["skipped"]])
    # identifiers: every spelling the sources use for a scoped entity
    ID = ["cohort", "id_kind", "as_written", "release_id", "participant_id", "source_file", "sheet", "source_column", "match", "bridge"]
    id_rows = []
    for w, p in sorted(coh.spell.items()):
        id_rows.append([coh.name, "participant", w, p, p, "", "", "", "identity" if w == p else "alias column of the participant bridge", crow["participant_bridge"]])
    if crow["file_participants"]:
        for r in D.read_tsv(os.path.join(D.DM, crow["file_participants"])):
            if r["participant_id"] in coh.P and r["id_as_written"]:
                id_rows.append([coh.name, "participant", r["id_as_written"], r["participant_id"], r["participant_id"], os.path.basename(r["file"]), r["sheet"], r["id_column"], r["match"], crow["file_participants"]])
    for sid, ps in sorted(coh.sample.items()):
        if len(ps) == 1:
            id_rows.append([coh.name, "sample", sid, sid, next(iter(ps)), "", "", "", "bridge column " + coh.sample_col.get(sid, ""), crow["sample_bridge"]])
    for fid, p in sorted(coh.file_participant.items()):
        id_rows.append([coh.name, "file", fid, fid, p, "", "", "", "bridge column " + (crow["file_id_columns"] or ""), crow["sample_bridge"]])
    for name, cols, rows in (("element", EL, el_rows), ("value_map", VM, vm_rows), ("link", LK, lk_rows), ("identifiers", ID, id_rows)):
        write(os.path.join(rdir, name + ".tsv"), cols, rows)
        out[name].append((cols, rows))
    D.log("   registry tables:", "element", len(el_rows), "| value_map", len(vm_rows), "| link", len(lk_rows), "| identifiers", len(id_rows))


def coverage_table(out, element_parts):
    """One row per element across the release: definition, type, and participants with a value per cohort and per AMP."""
    cohorts = D.read_tsv(os.path.join(D.DECL_PRIVATE, "cohorts.tsv"))
    expected = {r["cohort"]: int(r["expected_participants"]) for r in cohorts}
    program = {r["cohort"]: r["program"] for r in cohorts}
    programs = sorted(set(program.values()))
    order = [r["cohort"] for r in cohorts]
    rows = [dict(zip(cols, r)) for cols, rs in element_parts for r in rs]
    by_el = collections.defaultdict(dict)
    for r in rows:
        by_el[r["element"]][r["cohort"]] = r
    out_rows = []
    for el, per in by_el.items():
        anyrow = next(iter(per.values()))
        defs = sorted({d for r in per.values() for d in r["provider_wording"].split(" | ") if d})
        forms = sorted({r["value_form"] for r in per.values() if r["value_form"]})
        units = sorted({r["unit"] for r in per.values() if r["unit"]})
        vals = set()
        for r in per.values():
            vals |= {v.strip() for v in r["values_written"].split(";") if v.strip() and v.strip() != "..."}
        n_vals = max(int(r["n_values_written"]) for r in per.values())
        categorical = all(f in ("nominal", "ordinal", "binned", "interval") for f in forms) if forms else False
        values_summary = ("; ".join(sorted(vals)) if (categorical and n_vals <= 12) else ("numeric, %d distinct values" % n_vals if not categorical else "%d distinct values" % n_vals))
        cells = []
        for c in order:
            if c in per:
                n = int(per[c]["participants_with_value"])
                cells.append("%d/%d (%d%%)" % (n, expected[c], round(100.0 * n / expected[c])))
            else:
                cells.append("")
        prog_cells = []
        for pgm in programs:
            cs = [c for c in order if program[c] == pgm]
            n = sum(int(per[c]["participants_with_value"]) for c in cs if c in per)
            e = sum(expected[c] for c in cs)
            prog_cells.append("%d/%d (%d%%)" % (n, e, round(100.0 * n / e)) if any(c in per for c in cs) else "")
        n_prog = len({program[c] for c in per})
        out_rows.append([el, " | ".join(defs), " | ".join(forms), " | ".join(units), n_prog, len(per)] + prog_cells + cells + [values_summary, " | ".join(sorted({t for r in per.values() for t in r["table"].split(" | ")}))])
    out_rows.sort(key=lambda r: (-r[4], -r[5], r[0]))
    cols = ["element", "provider_wording", "value_form", "unit", "n_amps", "n_cohorts"] + programs + order + ["values", "table"]
    write(os.path.join(out, "registry", "element_coverage.tsv"), cols, out_rows)
    D.log("coverage table:", len(out_rows), "elements")


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.environ["CDM_OUT"], "stage1")
    os.makedirs(out, exist_ok=True)
    commit = subprocess.run(["git", "-C", D.REG, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    blocks = D.load_blocks()
    by_sha = collections.defaultdict(list)
    for b in blocks:
        if b["status"] == "excluded":
            continue
        for d in b["pins"]:
            if d.get("sha256") and d["sha256"] not in b["excluded"] and not any(x is b for x, _ in by_sha[d["sha256"]]):
                by_sha[d["sha256"]].append((b, d))
    def opt_tsv(path):      # a declaration file is optional: what it declared now comes from the registry's identity elements
        return D.read_tsv(path) if os.path.exists(path) else []
    profiles = {(r["cohort"], r["file"], r["sheet"]): r for name in ("reader_profiles.tsv", "reader_profiles_declared.tsv") for r in opt_tsv(os.path.join(D.DECL_PRIVATE, name))}
    rowkeys = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in opt_tsv(os.path.join(D.DECL, "row_keys.tsv")):
        rowkeys[r["cohort"]][r["key"]].append(r["column"])
    filters = {(r["cohort"], r["file"], r["sheet"]): (r["column"], r["match"], r["value"]) for r in opt_tsv(os.path.join(D.DECL_PRIVATE, "row_filters.tsv"))}
    noemit = {r["registry_label"]: r["reason"] for r in opt_tsv(os.path.join(D.DECL, "not_emitted.tsv"))}
    keys = {(r["cohort"], r["file"], r["sheet"]): (r["participant_column"], r["sample_column"]) for r in opt_tsv(os.path.join(D.DECL_PRIVATE, "key_columns.tsv"))}
    # KEYS FROM THE SPECS. An identity element (value_form identifier) names its node in loading_grain: a participant-node block gives the
    # participant key column of every file it pins, a specimen- or library-node block the sample key column, a participant_visit-node block the
    # visit key column. The declaration files above override; a file they do not name takes its keys from the pins.
    derived = collections.defaultdict(dict)
    IDENTITY = {"participant_id", "specimen_id", "library_id", "visit_name"}   # the identity elements: the only blocks that declare a key column. Other identifier-form elements (run names, accessions, file ids) are attributes
    for b in blocks:
        if b["label"] not in IDENTITY or b["value_form"] != "identifier" or b["status"] == "excluded": continue
        kind = {"participant": "participant", "participant_visit": "visit", "specimen": "specimen", "library": "library"}.get(b["grain_declared"])
        if not kind: continue
        for d in b["pins"]:
            if d.get("sha256"): derived[(d["sha256"], d.get("sheet") or b["sheet"] or "")].setdefault(kind, b["source_label"])
    for (sha_, sheet_), kinds in derived.items():      # per file and sheet, never per program: a column is a key only where an identity element pins it
        # a file that carries both a library and a specimen identifier is keyed by the finer one, the library; the specimen is then a column (its parent)
        keys.setdefault(("__sha__", sha_, sheet_), (kinds.get("participant", ""), kinds.get("library") or kinds.get("specimen", ""), kinds.get("visit", "")))
    summary, problems = [], []
    for crow in D.read_tsv(os.path.join(D.DECL_PRIVATE, "cohorts.tsv")):
        coh = D.Cohort(crow)
        cdir = os.path.join(out, coh.name)
        os.makedirs(os.path.join(cdir, "audit"), exist_ok=True)
        agg, unm = collections.Counter(), collections.Counter()
        rep = collections.defaultdict(lambda: dict(readings=0, skipped="", participants=set(), source_column_read="", source_file_sha256="", source_file="", row_filter="", rows_in_scope="", participant_key_column="", sample_key_column="", visit_key_column=""))
        files, forced = {}, set()
        nprob = len(problems)
        for t, attached, sha in cohort_tables(crow, coh, blocks, by_sha, profiles, problems, keys):
            files[t["file"]] = sha
            load_table(coh, t, attached, sha, rowkeys[coh.name], filters, noemit, agg, unm, rep, forced)
        write(os.path.join(cdir, "layer1_values.tsv"),
              ["cohort", "element", "participant_id", "sample_id", "visit", "other_keys", "value", "source_value", "unit", "mapping_file", "block", "precedence", "source_file", "sheet", "source_column", "source_file_sha256", "how", "source_rows"],
              [[coh.name] + list(k) + [n] for k, n in sorted(agg.items())])
        placement, conflicts = [], []
        identity = {b["label"]: {"participant": "participant_id", "participant_visit": "visit", "specimen": "sample_id", "library": "sample_id"}[b["grain_declared"]] for b in blocks if b["label"] in ("participant_id", "specimen_id", "library_id", "visit_name") and b["value_form"] == "identifier" and b["grain_declared"] in ("participant", "participant_visit", "specimen", "library")}
        written = place(coh, agg, cdir, placement, conflicts, forced, {(b["mapping_file"], b["block"]) for b in blocks if b["separator"]}, {b["label"] for b in blocks if b["null_is_agreement"]}, identity)
        write(os.path.join(cdir, "audit", "element_placement.tsv"), ["cohort", "element", "table", "sources", "readings", "keys_settled_by_precedence", "keys_left_blank_sources_disagree"], placement)
        write(os.path.join(cdir, "audit", "conflicts.tsv"), ["cohort", "element", "participant_id", "sample_id", "visit", "other_keys", "value", "source_value", "source_file", "sheet", "source_column", "mapping_file", "block", "precedence"], conflicts)
        write(os.path.join(cdir, "audit", "unmapped_values.tsv"), ["cohort", "mapping_file", "block", "element", "source_file", "sheet", "source_column", "source_value", "why_not_written", "source_rows"], [list(k) + [n] for k, n in sorted(unm.items())])
        write(os.path.join(cdir, "audit", "load_report.tsv"), ["cohort", "mapping_file", "block", "element", "source_file", "sheet", "readings", "skipped_because", "participant_key_column", "sample_key_column", "visit_key_column"],
              [list(k) + [v["readings"], v["skipped"], v["participant_key_column"], v["sample_key_column"], v["visit_key_column"]] for k, v in sorted(rep.items())])
        # every file the ETL input manifest lists for this cohort that it did not load, and why: no block pins it, or the file is missing or altered
        unloaded = [(coh.name, r["file"], r.get("sheet") or "", "listed", "no mapping block pins this file") for r in D.manifest_rows(coh.name)
                    if os.path.exists(r["path"]) and D.sha256(r["path"]) not in by_sha]
        unloaded += [(c, f, "", "listed", why) for c, f, why in problems[nprob:]]
        write(os.path.join(cdir, "audit", "unloaded_files.tsv"), ["cohort", "file", "sheet", "scope_status", "why_not_loaded"], unloaded)
        write(os.path.join(cdir, "audit", "columns_not_read.tsv"), ["cohort", "file", "sheet", "column", "columns_in_file"], [list(g) for g in COLUMN_GAPS if g[0] == coh.name])
        registry_tables(coh, crow, agg, rep, placement, blocks, cdir, commit, REGISTRY)
        write(os.path.join(cdir, "audit", "source_files.tsv"), ["source_file", "sha256"], sorted(files.items()))
        people = {k[1] for k in agg if k[1]}
        nrow = written.get("participant", (0, 0))[0]
        checks = [("participant table has one row per expected participant", coh.open or nrow == coh.expected, "%d rows, %d expected" % (nrow, coh.expected)),
                  ("every participant with a value is in the bridge", coh.open or people <= coh.P, "%d participants carry values" % len(people)),
                  ("every reading names its source file checksum", all(k[14] for k in agg), "%d readings" % len(agg)),
                  ("no element declared never-written was written", not any(k[0] in noemit for k in agg), "")]
        write(os.path.join(cdir, "audit", "verification.tsv"), ["check", "result", "detail"], [[c, "PASS" if ok else "FAIL", d] for c, ok, d in checks])
        summary.append((coh.name, coh.expected, len(people), len(agg), written, len({p[1] for p in placement}), len({p[1] for p in placement if p[2] == "long table only"} - {p[1] for p in placement if p[2] != "long table only"}), len(conflicts), len(unm), all(ok for _, ok, _ in checks)))
        D.log(coh.name, "| participants with values", len(people), "of", coh.expected, "| readings", len(agg), "| tables", {k: v for k, v in written.items()}, "| conflicts", len(conflicts), "| unmapped", len(unm), "| checks", "PASS" if all(ok for _, ok, _ in checks) else "FAIL")
    lines = ["# Layer 1, version 0", "", "Written %s by `load.py`. Registry commit `%s` plus its working copy. Pinned provider files only, plus the declared bridges." % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), commit), "",
             "`registry/` holds the provenance tables of this run.", "",
             "One folder per cohort. `layer1_values.tsv` is the long table: one row per distinct value with its keys and lineage. The wide tables hold each element at its measured grain.",
             "`audit/` holds element_placement, conflicts, unmapped_values, load_report, source_files and verification.", ""]
    for name, exp, people, n, written, els, longonly, conf, unmapped, ok in summary:
        lines += ["## %s" % name, "", "- Participants with at least one value: %d of %d. Checks: %s." % (people, exp, "all pass" if ok else "FAILED, see audit/verification.tsv"),
                  "- Elements written: %d (%d of them in the long table only). Readings: %d." % (els, longonly, n),
                  "- Wide tables: " + "; ".join("%s (%d rows, %d elements)" % (k, v[0], v[1]) for k, v in written.items()) + ".",
                  "- Disagreeing readings logged: %d. Source values not written for lack of a value line: %d." % (conf, unmapped), ""]
    if problems:
        lines += ["## Files that could not be read", ""] + ["- %s: %s (%s)" % p for p in problems]
    rroot = os.path.join(out, "registry")
    os.makedirs(rroot, exist_ok=True)
    for name, parts in REGISTRY.items():
        write(os.path.join(rroot, name + ".tsv"), parts[0][0], [r for cols, rows in parts for r in rows])
    coverage_table(out, REGISTRY["element"])
    seen = set()
    todo = []
    for b in blocks:
        if b["label"] in {r[1] for cols, rows in REGISTRY["element"] for r in rows} and b["mapping_file"] not in seen and polluted(b["definition"]):
            seen.add(b["mapping_file"])
            todo.append([b["mapping_file"], b["label"], b["definition"]])
    write(os.path.join(out, "registry", "registry_definitions_to_clean.tsv"), ["mapping_file", "element", "registry_definition"], sorted(todo))
    lines += ["## Provenance tables", "", "`registry/` at the root and in each cohort folder: `element_coverage.tsv` (one row per element: participants with a value per cohort and per AMP), `element.tsv` (per cohort: where it landed, how many participants carry it, which mapping file produced it),",
              "The CDE definition is not in these tables; the registry file carries it.",
              "`value_map.tsv` (every source value that became a harmonized value, with the rule and row count), `link.tsv` (every pinned source file and column that fed an element, with checksums),",
              "`identifiers.tsv` (every id spelling the sources use, next to the id written here).", ""]
    open(os.path.join(out, "README.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    D.log("wrote", out)


if __name__ == "__main__":
    main()
