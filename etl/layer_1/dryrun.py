#!/usr/bin/env python3
"""Layer 1 dry run: validate the mapping registry against the files a run processes. Reads only. Loads nothing.

THE INPUT is the ETL input manifest (environment ETL_INPUT_MANIFEST; default <declarations>/etl_input_manifest.tsv): one row
per file to process, columns file (path relative to the datamart root, or absolute), optional cohort, sheet and sha256.
Every mapping block that pins a listed file applies to it; nothing else decides what is read. The other declarations are
DATA: declarations/cohorts.tsv (cohorts, their participant bridges; a cohort without a bridge processes whole files with keys
as written), optional reader profiles and key columns. This file holds no cohort name, column name or value. No regex.

    .venv/bin/python dryrun.py [output folder]

For every cohort it reports: the listed files resolved by sha256; the mapping blocks that pin them; for each block
whether its column is found, how its rows resolve to participants, whether every observed value is covered by
the value map, and the grain MEASURED from the source (is the value constant per participant, per sample, or neither).
"""
import collections, csv, datetime, glob, gzip, hashlib, json, os, subprocess, sys

csv.field_size_limit(10 ** 9)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))                       # this repository (the scripts sit in etl/layer_1/)
SYSBIO = os.environ.get("CDM_SYSBIO", os.path.dirname(REPO))         # the project root that holds datamart/ (never inside the repository)
REG = os.environ.get("CDM_REGISTRY", os.path.join(REPO, "registry"))  # the mapping files this run reads: the staged subset by default
DM = os.environ.get("CDM_DATA", os.path.join(SYSBIO, "datamart"))    # real data, outside the repository
DECL = os.path.join(HERE, "declarations")
SCOPE = os.environ.get("CDM_SCOPE", os.path.join(DM, "harmonization_scope"))   # the scope lists: private, they name data files
DECL_PRIVATE = os.environ.get("CDM_DECL", os.path.join(SCOPE, "declarations"))  # declarations that name data files (cohorts, key columns, reader profiles, row filters): private


ETL_INPUT_MANIFEST = os.environ.get("ETL_INPUT_MANIFEST", os.path.join(DECL_PRIVATE, "etl_input_manifest.tsv"))   # THE input: the files this run processes


def manifest_rows(cohort):
    """The ETL input manifest, rows of this cohort. Columns: file (relative to the datamart root, or absolute); optional cohort
    (a row without one belongs to every cohort), sheet (a workbook sheet; blank = every sheet holding a pinned label) and
    sha256 (checked against the file when given). Whole files are processed; nothing else decides what is read."""
    rows = [r for r in read_tsv(ETL_INPUT_MANIFEST) if r.get("file") and (r.get("cohort") or cohort) == cohort]
    for r in rows:
        r["path"] = r["file"] if os.path.isabs(r["file"]) else os.path.join(DM, r["file"])
    return rows


REGISTRY_FOLDERS = [("registry", "*.json"), ("mappings", os.path.join("mappings", "*", "*.json")), ("drafts", os.path.join("drafts", "*", "*.json"))]   # one flat folder of element files; the nested forms are read if present
DISTINCT_CAP = 20000
PRESCAN_ROWS = 20000
HEADER_SEARCH_ROWS = 12
_sha = {}


def log(*a):
    print(*a, flush=True)


def sha256(path):
    if path not in _sha:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        _sha[path] = h.hexdigest()
    return _sha[path]


def read_tsv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def cell_values(cell):
    """A cell is a string or a list of strings (repeating fields). Returns the non-blank values, stripped."""
    if isinstance(cell, list):
        return [v.strip() for v in cell if isinstance(v, str) and v.strip()]
    v = cell.strip() if isinstance(cell, str) else ""
    return [v] if v else []


# ---------------------------------------------------------------- registry
def norm_cond(c):
    return dict(column=c.get("column"), token=c.get("token"), inequality=bool(c.get("inequality")), pos=c.get("token_position"), delims=c.get("delimiters") or [])


def norm_applies(a):
    if not a:
        return None
    if isinstance(a, list):
        return dict(require="all", action="include", conds=[norm_cond(c) for c in a])
    if "conditions" in a:
        return dict(require=a.get("require") or "all", action=a.get("action") or "include", conds=[norm_cond(c) for c in a.get("conditions") or []])
    return dict(require="all", action="include", conds=[norm_cond(a)])


def cond_true(c, text):
    v = text
    if c["delims"] and c["pos"] is not None:
        parts = [v]
        for d in c["delims"]:
            parts = [q for p in parts for q in p.split(d)]
        v = parts[c["pos"]] if 0 <= c["pos"] < len(parts) else ""
    v = v.strip()
    if c["inequality"]:
        bits = str(c["token"]).split()
        if len(bits) != 2:
            return False
        try:
            x, y = float(v), float(bits[1])
        except ValueError:
            return False
        return {">=": x >= y, ">": x > y, "<=": x <= y, "<": x < y, "==": x == y, "!=": x != y}.get(bits[0], False)
    if isinstance(c["token"], list):
        return v in [str(t) for t in c["token"]]
    return v == str(c["token"])


def row_applies(a, get):
    """True/False, or None when a filter column is absent from the table."""
    if a is None:
        return True
    res = []
    for c in a["conds"]:
        cell = get(c["column"])
        if cell is None:
            return None
        res.append(cond_true(c, " ".join(cell_values(cell))))
    hit = all(res) if a["require"] == "all" else any(res)
    return (not hit) if a["action"] == "exclude" else hit


def load_blocks():
    blocks = []
    for folder, pattern in REGISTRY_FOLDERS:
        for path in sorted(glob.glob(os.path.join(REG, pattern))):
            j = json.load(open(path, encoding="utf-8"))
            rel = os.path.relpath(path, REG)
            for i, s in enumerate(j.get("sources") or []):
                l1 = s.get("layer_1_etl") or {}
                grain = (s.get("loading_grain") or j.get("loading_grain") or {})
                blocks.append(dict(
                    mapping_file=rel, folder=folder, schema=j.get("schema_version"), label=j.get("registry_label"), block=i, role=j.get("role") or "element",
                    source_label=" | ".join(s["source_label"]) if isinstance(s.get("source_label"), list) else s.get("source_label"),
                    labels=[str(x) for x in s["source_label"]] if isinstance(s.get("source_label"), list) else [s.get("source_label")],
                    program=s.get("program"), status=s.get("status"),
                    value_form=l1.get("value_form"), datatype=l1.get("datatype") or "", value_map=l1.get("value_map") or [], missing={str(m).strip() for m in (l1.get("missing_values") or [])},
                    range=l1.get("range") or {}, pins=l1.get("data_files") or [], excluded={d.get("sha256") for d in (l1.get("excluded_data_files") or [])},
                    sheet=(s.get("layout") or {}).get("sheet"), layout=(s.get("layout") or {}), applies=norm_applies(s.get("applies_to_rows")), precedence=s.get("precedence"),
                    key_columns=l1.get("key_columns"), grain_declared=grain.get("entity") or "", grain_anchor=grain.get("anchor") or "", one_per=j.get("one_per"),
                    separator=l1.get("multi_value_separator") or "",
                    blank_hv=next((str(e.get("harmonized_value")) for e in (l1.get("value_map") or []) if str(e.get("source_value") or "").strip() == "" and e.get("harmonized_value") not in (None, "")), None), null_is_agreement=bool(j.get("null_is_agreement")),
                    unit=l1.get("unit") or j.get("unit") or "", on_conflict=j.get("on_conflict") or "", must_agree=j.get("must_agree"),
                    definition=j.get("definition") or j.get("registry_description") or "", harmonized_values=j.get("harmonized_values") or [],
                    src_definition=(str(s.get("src_definition")).strip() if s.get("src_definition") not in (None, "", "None", "null") else ""),
                    drops={str(x.get("participant_id")) for x in (s.get("participant_value_drops") or []) if isinstance(x, dict)}))
    return blocks


# ---------------------------------------------------------------- readers: each returns (header, rows_factory)
def rd_delim(path, delim, header_row=1):
    op = gzip.open if path.endswith(".gz") else open

    def rows():
        with op(path, "rt", encoding="utf-8-sig", newline="") as f:
            rd = csv.reader(f, delimiter=delim)
            for _ in range(header_row):
                next(rd, None)
            for r in rd:
                yield r
    with op(path, "rt", encoding="utf-8-sig", newline="") as f:
        rd = csv.reader(f, delimiter=delim)
        head = []
        for _ in range(header_row):
            head = next(rd, [])
    return head, rows


_wb = {}


def workbook(path):
    if path not in _wb:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        sheets = collections.OrderedDict()
        for ws in wb.worksheets:
            ws.reset_dimensions()
            sheets[ws.title] = [["" if x is None else (str(int(x)) if isinstance(x, float) and x.is_integer() else str(x)) for x in r] for r in ws.iter_rows(values_only=True)]
        wb.close()
        _wb[path] = sheets
    return _wb[path]


def rd_xlsx(path, sheet, header_row, data_start):
    rows = workbook(path).get(sheet)
    if rows is None:
        return None, None
    head = list(rows[header_row - 1]) if len(rows) >= header_row else []
    start = data_start if data_start else header_row + 1
    data = [r for r in rows[start - 1:] if any(x != "" for x in r)]
    return head, (lambda: iter(data))


def rd_rds(path):
    import pyreadr
    df = next(iter(pyreadr.read_r(path).values()))
    head = [str(c) for c in df.columns]
    data = [["" if x is None else str(x) for x in t] for t in df.itertuples(index=False, name=None)]
    return head, (lambda: iter(data))


def flatten_keys(obj, out, path=()):
    """Every scalar is a value of its own key and of every key that encloses it, so a field wrapped in an object
    (the KPMP Atlas index writes {"sex": {"raw": ["Female"]}}) is still addressed by its name."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            flatten_keys(v, out, path + (k,))
    elif isinstance(obj, list):
        for x in obj:
            flatten_keys(x, out, path)
    else:
        v = "" if obj is None else str(obj)
        for k in dict.fromkeys(path):
            out[k].append(v)


def rd_json_objects(objs):
    recs = []
    keys = []
    seen = set()
    for o in objs:
        d = collections.defaultdict(list)
        flatten_keys(o, d)
        recs.append(d)
        for k in d:
            if k not in seen:
                seen.add(k)
                keys.append(k)
    data = [[r.get(k, []) for k in keys] for r in recs]
    return keys, (lambda: iter(data))


def rd_json(path):
    return rd_json_objects([json.load(open(path, encoding="utf-8"))])


def rd_jsonl(path):
    objs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                objs.append(json.loads(line))
    return rd_json_objects(objs)


def rd_soft(path):
    """One row per sample; every sample attribute is a list because the format lets a field repeat."""
    samples = []
    cur = None
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("^SAMPLE"):
                cur = collections.OrderedDict()
                samples.append(cur)
            elif line.startswith("^"):
                cur = None
            elif cur is not None and line.startswith("!"):
                k, _, v = line.partition("=")
                cur.setdefault(k.strip(), []).append(v.strip())
    keys = []
    for s in samples:
        for k in s:
            if k not in keys:
                keys.append(k)
    data = [[s.get(k, []) for k in keys] for s in samples]
    return keys, (lambda: iter(data))


def rd_fields(path):
    """Portal per-cell labels: metadata_labels[key] is the label list, metadata[key] the per-cell index into it."""
    j = json.load(open(path, encoding="utf-8"))
    labels, md = j.get("metadata_labels") or {}, j.get("metadata") or {}
    keys = [k for k in labels if k in md]
    n = max((len(md[k]) for k in keys), default=0)

    def rows():
        cols = [(labels[k], md[k]) for k in keys]
        for i in range(n):
            out = []
            for lab, idx in cols:
                x = idx[i] if i < len(idx) else ""
                out.append(str(lab[x]) if isinstance(x, int) and not isinstance(x, bool) and 0 <= x < len(lab) else ("" if x is None else str(x)))
            yield out
    return keys, rows


def kind_of(path):
    p = path.lower()
    for ext, k in ((".tsv.gz", "tsv"), (".tsv", "tsv"), (".csv", "csv"), (".xlsx", "xlsx"), (".jsonl", "jsonl"), (".soft.gz", "soft"), (".rds", "rds"), (".json", "json")):
        if p.endswith(ext):
            return k
    return ""


def open_table(path, kind, sheet, header_row, data_start):
    if kind == "csv":
        return rd_delim(path, ",", header_row or 1)
    if kind == "tsv":
        return rd_delim(path, "\t", header_row or 1)
    if kind == "xlsx":
        return rd_xlsx(path, sheet, header_row or 1, data_start)
    if kind == "rds":
        return rd_rds(path)
    if kind == "soft":
        return rd_soft(path)
    if kind == "fields":
        return rd_fields(path)
    if kind == "jsonl":
        return rd_jsonl(path)
    if kind in ("json", "sidecar"):
        return rd_json(path)
    return None, None


# ---------------------------------------------------------------- cohort context
class Cohort:
    def __init__(self, row):
        self.name = row["cohort"]
        self.expected = int(row["expected_participants"] or 0)
        self.open = not row.get("participant_bridge")     # no participant list: whole files, every key value is a participant as written
        self.row = row
        sep = row["list_separator"]
        split = (lambda v: [x for x in v.split(sep) if x]) if sep else (lambda v: [v] if v else [])
        bridge = read_tsv(os.path.join(DM, row["participant_bridge"])) if not self.open else []
        pc = row["participant_column"]
        assert self.open or (bridge and pc in bridge[0]), "participant column %r not in %s" % (pc, row["participant_bridge"])
        self.participants = [r[pc] for r in bridge if r[pc]]
        self.P = set(self.participants)
        self.spell = {p: p for p in self.P}
        self.collisions = 0
        for col in ([c for c in row["participant_alias_columns"].split(";") if c] if not self.open else []):
            assert col in bridge[0], "alias column %r not in participant bridge" % col
            for r in bridge:
                for v in split(r[col]):
                    self.add_spelling(v, r[pc])
        self.file_spell = collections.defaultdict(dict)      # (basename, sheet) -> as written -> participant
        self.declared_id = {}                                # (basename, sheet) -> id column
        if row["file_participants"]:
            for r in read_tsv(os.path.join(DM, row["file_participants"])):
                key = (os.path.basename(r["file"]), r["sheet"])
                if r["id_column"]:
                    self.declared_id[key] = r["id_column"]
                if r["participant_id"] in self.P and r["id_as_written"]:
                    self.file_spell[key][r["id_as_written"]] = r["participant_id"]
        self.sample = collections.defaultdict(set)           # sample id -> participants
        self.sample_col = {}                                 # sample id -> bridge column it came from
        self.file_participant = {}                           # file source id -> participant
        if row["sample_bridge"]:
            sb = read_tsv(os.path.join(DM, row["sample_bridge"]))
            spc = row["sample_participant_column"]
            assert sb and spc in sb[0], "sample participant column %r not in sample bridge" % spc
            for col in [c for c in row["sample_columns"].split(";") if c]:
                assert col in sb[0], "sample column %r not in sample bridge" % col
                for r in sb:
                    p = self.resolve(r[spc])
                    for v in split(r[col]):
                        if p:
                            self.sample[v].add(p)
                            self.sample_col.setdefault(v, col)
            for col in [c for c in row["file_id_columns"].split(";") if c]:
                assert col in sb[0], "file id column %r not in sample bridge" % col
                for r in sb:
                    p = self.resolve(r[spc])
                    for v in split(r[col]):
                        if p:
                            self.file_participant[v] = p

    def resolve(self, v):
        """The participant a key value names: through the bridge spellings, or the value itself when the cohort has no participant list."""
        return self.spell.get(v) or (v if self.open and v else None)

    def known(self, p):
        return p in self.P or (self.open and bool(p))

    def add_spelling(self, written, participant):
        if not written:
            return
        if written in self.spell and self.spell[written] != participant:
            self.collisions += 1
            return
        self.spell[written] = participant

    def sample_participant(self, v):
        s = self.sample.get(v)
        return next(iter(s)) if s and len(s) == 1 else None


# ---------------------------------------------------------------- measuring one table
def coverage(b, distinct):
    vm = b["value_map"]
    known = set()
    for e in vm:
        for k in ("source_value", "source_encoding"):
            if e.get(k) not in (None, ""):
                known.add(str(e[k]).strip())
    interval = any("interval" in e for e in vm)
    if any(str(e.get("source_value")) == "<any>" for e in vm):
        return [], 0, 0, 0, "", True
    form = b["value_form"] or ""
    unmapped, nonnum, out_of_range, note = [], 0, 0, ""
    lo, hi = b["range"].get("min"), b["range"].get("max")
    numeric_form = form in ("continuous", "interval", "binned") or interval
    for v, n in distinct.items():
        if v in known:
            continue
        if numeric_form:
            try:
                x = float(v)
            except ValueError:
                nonnum += n
                unmapped.append((v, n))
                continue
            if (lo is not None and x < lo) or (hi is not None and x > hi):
                out_of_range += n
        elif vm:
            unmapped.append((v, n))
        elif form in ("nominal", "ordinal"):
            unmapped.append((v, n))
            note = "no value map for a categorical element"
    low = {k.lower() for k in known}
    near = sum(1 for v, _ in unmapped if v.lower() in low)
    return unmapped, nonnum, out_of_range, near, note, False


def measure(coh, t, attached):
    """t: dict(file, sheet, header, rows, id_column, sample_column, file_participant). attached: list of (block, col index, pre-reasons)."""
    head = t["header"]
    pos = collections.defaultdict(list)
    for i, h in enumerate(head):
        pos[h].append(i)
    key = (os.path.basename(t["file"]), t["sheet"])
    fspell = coh.file_spell.get(key, {})

    def to_participant(v):
        return fspell.get(v) or coh.resolve(v)
    # prescan: where are the participant and sample ids
    pm, sm = collections.Counter(), collections.Counter()
    seen_p, seen_s = collections.defaultdict(set), collections.defaultdict(set)
    for n, r in enumerate(t["rows"]()):
        if n >= PRESCAN_ROWS:
            break
        for i, cell in enumerate(r):
            for v in cell_values(cell):
                if not coh.open and to_participant(v) in coh.P:     # the key column is measured only against a participant list
                    seen_p[i].add(v)
                if v in coh.sample:
                    seen_s[i].add(v)
    for i, s in seen_p.items():
        pm[i] = len(s)
    for i, s in seen_s.items():
        sm[i] = len(s)
    id_i, id_src = None, ""
    if t["id_column"] and len(pos.get(t["id_column"], [])) >= 1:
        id_i, id_src = pos[t["id_column"]][0], "declared in the file-participant manifest"
    elif pm:
        id_i, id_src = max(sorted(pm), key=lambda i: pm[i]), "measured: column whose values match the participant bridge"
    s_i, s_src = None, ""
    if t["sample_column"] and len(pos.get(t["sample_column"], [])) >= 1:
        s_i, s_src = pos[t["sample_column"]][0], "declared in the reader profile"
    elif sm:
        s_i, s_src = max(sorted(sm), key=lambda i: sm[i]), "measured: column whose values match the sample bridge"
    rowkey = id_i is not None or s_i is not None
    keyed = rowkey or bool(t["file_participant"])
    assess = keyed or t.get("dataset_level")
    cover_ok = rowkey or t.get("dataset_level") or not t["layout"].startswith("measured")
    acc = []
    for b, ci, pre in attached:
        dups = [int(x) for p in pre if p.startswith("DUP:") for x in p[4:].split(",")]
        acc.append(dict(n=0, parts=set(), distinct=collections.Counter(), overflow=False, pv={}, sv={}, missing=0, nofilter=False, dups=dups, dupdiff=0))
    n_rows = n_scope = 0
    found = set()

    def getter(r):
        return lambda col: (r[pos[col][0]] if len(pos.get(col, [])) == 1 and pos[col][0] < len(r) else None)
    for r in (t["rows"]() if assess else ()):
        n_rows += 1
        p = None
        key_text = False
        if id_i is not None and id_i < len(r):
            for v in cell_values(r[id_i]):
                key_text = True
                p = to_participant(v) or p
        s = None
        if s_i is not None and s_i < len(r):
            vals = cell_values(r[s_i])
            s = vals[0] if vals else None
            key_text = key_text or bool(vals)
            if p is None and s is not None:
                p = coh.sample_participant(s)
        if p is None and t["file_participant"] and not key_text:      # a row whose own key cell is filled but unresolved is not this file's participant
            p = t["file_participant"]
        if keyed and not coh.known(p):
            continue
        n_scope += 1
        if p:
            found.add(p)
        get = getter(r)
        for (b, ci, pre), a in zip(attached, acc):
            if ci is None or ci >= len(r):
                continue
            if a["dups"] and len({r[x] if x < len(r) else "" for x in a["dups"]}) > 1:
                a["dupdiff"] += 1
            ok = row_applies(b["applies"], get)
            if ok is None:
                a["nofilter"] = True
                continue
            if not ok:
                continue
            vals = [v for v in cell_values(r[ci])]
            kept = []
            for v in vals:
                if v in b["missing"]:
                    a["missing"] += 1
                else:
                    kept.append(v)
            if not kept:
                continue
            a["n"] += 1
            if p:
                a["parts"].add(p)
            for v in kept:
                if v in a["distinct"] or len(a["distinct"]) < DISTINCT_CAP:
                    a["distinct"][v] += 1
                else:
                    a["overflow"] = True
            sig = "\x1f".join(kept)
            if p:
                st = a["pv"].setdefault(p, set())
                if len(st) < 3:
                    st.add(sig)
            if s:
                st = a["sv"].setdefault(s, set())
                if len(st) < 3:
                    st.add(sig)
    info = dict(rows=n_rows, rows_in_scope=n_scope, participants_found=len(found), keyed=keyed,
                id_column=(head[id_i] if id_i is not None else ""), id_source=id_src,
                sample_column=(head[s_i] if s_i is not None else ""), sample_source=s_src,
                id_candidates="; ".join("%s=%d" % (head[i], pm[i]) for i in sorted(pm, key=lambda i: -pm[i])[:4]),
                sample_candidates="; ".join("%s=%d" % (head[i], sm[i]) for i in sorted(sm, key=lambda i: -sm[i])[:4]))
    results = []
    for (b, ci, pre), a in zip(attached, acc):
        reasons = [p for p in pre if not p.startswith("DUP:")]
        header_note = ""
        if a["dups"]:
            if a["dupdiff"] or not assess:
                reasons.append("label repeated in the header and the columns differ")
            else:
                header_note = "label is in the header %d times; the columns are identical on every row read, first one used" % len(a["dups"])
        unmapped, nonnum, oor, near, note, anytoken = coverage(b, a["distinct"]) if ci is not None else ([], 0, 0, 0, "", False)
        soft = []
        if ci is not None and not assess:
            soft.append("no participant or sample key resolves this table's rows")
        elif ci is not None and keyed and not found:
            soft.append("an id column is present but no value resolves to a scoped participant through the declared bridges")
        elif ci is not None and not cover_ok:
            soft.append("first data row undeclared for this sheet")
            unmapped, note = [], ""
        if a["nofilter"]:
            reasons.append("row filter column not found in the table")
        empty = ci is not None and not reasons and not soft and a["n"] == 0
        if note:
            reasons.append(note)
        elif unmapped:
            reasons.append("%d observed value(s) not in the value map" % len(unmapped))
        if not a["pv"] and not a["sv"]:
            grain = "dataset" if a["n"] else ""
        elif a["pv"] and max(len(x) for x in a["pv"].values()) <= 1:
            grain = "participant"
        elif a["sv"] and max(len(x) for x in a["sv"].values()) <= 1:
            grain = "sample"
        else:
            grain = "row"
        results.append(dict(block=b, reasons=reasons, soft=soft, empty=empty, anytoken=anytoken, header_note=header_note, rows_with_value=a["n"], participants_with_value=len(a["parts"]), n_distinct=len(a["distinct"]),
                            overflow=a["overflow"], unmapped=unmapped, nonnumeric=nonnum, out_of_range=oor, near_miss=near, missing_dropped=a["missing"], grain_measured=grain))
    return info, results


def clean_header(tables):
    """Header cells are compared without surrounding whitespace (KPMP workbooks end some with a non-breaking space)."""
    for t in tables:
        t["header"] = [h.strip() if isinstance(h, str) else h for h in t["header"]]


def attach(blocks_for_sha, tables):
    clean_header(tables)
    """Decide which table (sheet) each block reads. Returns {table index: [(block, col index, reasons)]}, plus unplaced."""
    out = collections.defaultdict(list)
    for b in blocks_for_sha:
        cands = [i for i, t in enumerate(tables) if (b["sheet"] is None or t["sheet"] == b["sheet"])]
        if b["sheet"] is not None and not cands:
            out[0].append((b, None, ["declared sheet %r is not among this file's scoped sheets" % b["sheet"]]))
            continue
        hits = []
        for i in cands:
            head = tables[i]["header"]
            first = next((lab.strip() for lab in b["labels"] if isinstance(lab, str) and lab.strip() in head), None)      # a list is label then code twin, or alternate spellings
            if first is not None:
                hits.append((i, [j for j, h in enumerate(head) if h == first]))
        if not hits:
            out[cands[0]].append((b, None, ["column not found"]))
        elif len(hits) > 1:
            out[hits[0][0]].append((b, None, ["sheet undeclared and the label is in several sheets (%s)" % ", ".join(tables[i]["sheet"] for i, _ in hits)]))
        elif len(hits[0][1]) > 1:
            out[hits[0][0]].append((b, hits[0][1][0], ["DUP:" + ",".join(str(x) for x in hits[0][1])]))
        else:
            out[hits[0][0]].append((b, hits[0][1][0], []))
    return out


# ---------------------------------------------------------------- the run
def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.environ["CDM_OUT"], "dryrun")
    os.makedirs(out, exist_ok=True)
    commit = subprocess.run(["git", "-C", REG, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    blocks = load_blocks()
    by_sha = collections.defaultdict(list)
    excluded_by_sha = collections.defaultdict(set)
    for b in blocks:
        for d in b["pins"]:
            if d.get("sha256") and d["sha256"] not in b["excluded"]:
                if b["status"] == "excluded":
                    excluded_by_sha[d["sha256"]].add((b["mapping_file"], b["block"]))
                elif not any(x is b for x, _ in by_sha[d["sha256"]]):
                    by_sha[d["sha256"]].append((b, d))
    profiles = {(r["cohort"], r["file"], r["sheet"]): r for name in ("reader_profiles.tsv", "reader_profiles_declared.tsv") for r in read_tsv(os.path.join(DECL_PRIVATE, name))}
    F, B, U, K, SUM = [], [], [], [], []
    for crow in read_tsv(os.path.join(DECL_PRIVATE, "cohorts.tsv")):
        coh = Cohort(crow)
        log("cohort", coh.name, "expected", coh.expected, "| bridge participants", len(coh.P), "| spellings", len(coh.spell), "| samples", len(coh.sample))
        groups = collections.OrderedDict()                       # sha -> dict(path, file, entries=[(sheet, profile)], source_ids)
        unresolved = []
        for r in manifest_rows(coh.name):
            if not os.path.exists(r["path"]):
                unresolved.append((r["file"], r.get("sha256") or "", "file missing")); continue
            sha = sha256(r["path"])
            if r.get("sha256") and r["sha256"] != sha:
                unresolved.append((r["file"], r["sha256"], "sha256 differs from the manifest")); continue
            rel = os.path.relpath(r["path"], DM)
            g = groups.setdefault(sha, dict(path=r["path"], file=rel, entries=[], source_ids={str(d["source_id"]) for _, d in by_sha.get(sha, []) if d.get("source_id")}, status="listed"))
            g["entries"].append((r.get("sheet") or None, profiles.get((coh.name, rel, r.get("sheet") or ""))))
        pair_verdicts = collections.defaultdict(set)
        block_reasons = collections.defaultdict(set)
        block_grain = {}
        for sha, g in groups.items():
            kind_default = kind_of(g["path"])
            bl = [b for b, d in by_sha.get(sha, [])]
            tables = []
            for sheet, prof in g["entries"]:
                kind = (prof or {}).get("kind") or kind_default
                if kind == "xlsx" and sheet in (None, ""):
                    labels = {lab for b in bl for lab in b["labels"]}
                    for sname, rows in workbook(g["path"]).items():
                        hr = next((i for i, r in enumerate(rows[:HEADER_SEARCH_ROWS]) if any(c in labels for c in r)), None)
                        if hr is None:
                            continue
                        data = [r for r in rows[hr + 1:] if any(x != "" for x in r)]
                        tables.append(dict(file=g["file"], sheet=sname, header=list(rows[hr]), rows=(lambda d=data: iter(d)), kind=kind,
                                           layout="measured: header found on row %d; first data row undeclared" % (hr + 1), sample_column="", scope_note=""))
                    continue
                hr = int(prof["header_row"]) if prof and prof["header_row"] else None
                ds = int(prof["data_start"]) if prof and prof["data_start"] else None
                head, rows = open_table(g["path"], kind, sheet, hr, ds)
                if head is None:
                    F.append(dict(cohort=coh.name, file=g["file"], sheet=sheet or "", sha256=sha, kind=kind, read="NO READER for this file type", rows="", rows_in_scope="", participants_found="", expected=coh.expected))
                    continue
                tables.append(dict(file=g["file"], sheet=sheet or "", header=head, rows=rows, kind=kind,
                                   dataset_level=(kind == "sidecar" or "dataset_level" in (prof or {}).get("other_keys", "")),
                                   layout=("declared in reader_profiles.tsv" if prof else "by file type; header on row 1"),
                                   sample_column=(prof or {}).get("sample_column", ""), scope_note=(prof or {}).get("scope_note", "") + ("" if (prof or {}).get("row_filter") else "")))
            if not tables:
                if not any(f["file"] == g["file"] for f in F):
                    F.append(dict(cohort=coh.name, file=g["file"], sheet="", sha256=sha, kind=kind_default, read="no sheet holds any pinned label", rows="", rows_in_scope="", participants_found="", expected=coh.expected))
                continue
            fpart = next((coh.file_participant[s] for s in g["source_ids"] if s in coh.file_participant), None)
            for t in tables:
                t["id_column"] = coh.declared_id.get((os.path.basename(t["file"]), t["sheet"]), "")
                t["file_participant"] = fpart
            placed = attach(bl, tables)
            for ti, t in enumerate(tables):
                if t["kind"] == "fields" and not placed.get(ti):
                    info = dict(rows="not iterated (no block pins it)", rows_in_scope="", participants_found="", keyed="", id_column=t["id_column"], id_source="declared in the file-participant manifest" if t["id_column"] else "", sample_column="", sample_source="", id_candidates="", sample_candidates="")
                    res = []
                else:
                    info, res = measure(coh, t, placed.get(ti, []))
                F.append(dict(cohort=coh.name, file=t["file"], sheet=t["sheet"], sha256=sha, kind=t["kind"], read="ok", layout=t["layout"], rows=info["rows"], rows_in_scope=info["rows_in_scope"],
                              participants_found=info["participants_found"], expected=coh.expected, id_column=info["id_column"], id_source=info["id_source"], id_candidates=info["id_candidates"],
                              sample_column=info["sample_column"], sample_source=info["sample_source"], sample_candidates=info["sample_candidates"], file_level_participant=fpart or "",
                              blocks=len(res), scope_note=t["scope_note"], list_status=g["status"], keyed=("yes" if info["keyed"] else ("declared dataset-level" if t.get("dataset_level") else "no")) if info["keyed"] != "" else ""))
                for r in res:
                    b = r["block"]
                    rs = list(r["reasons"])
                    structural = [x for x in rs if "not in the value map" not in x]
                    verdict = "BLOCKED" if structural else ("NOT ASSESSED" if r["soft"] else ("EMPTY" if r["empty"] else ("LOADABLE, VALUES TO MAP" if rs else "LOADABLE")))
                    rs = rs + r["soft"] + (["no value for any scoped participant"] if r["empty"] else [])
                    bkey = (b["mapping_file"], b["block"])
                    pair_verdicts[bkey].add(verdict)
                    for x in rs:
                        x = x.split(" (")[0]
                        block_reasons[bkey].add("observed values not in the value map" if "not in the value map" in x else ("declared sheet not in this file" if x.startswith("declared sheet") else x))
                    declared = b["grain_declared"] or ("one_per=" + json.dumps(b["one_per"]) if b["one_per"] else "")
                    if verdict.startswith("LOADABLE"):
                        rank = {"participant": 1, "sample": 2, "row": 3}.get(r["grain_measured"], 0)
                        if rank >= block_grain.get(bkey, (0, "", ""))[0]:
                            block_grain[bkey] = (rank, declared or "(none declared)", r["grain_measured"])
                    B.append(dict(cohort=coh.name, mapping_file=b["mapping_file"], schema=b["schema"], registry_label=b["label"], block=b["block"], source_label=b["source_label"], status=b["status"],
                                  program=b["program"], value_form=b["value_form"], file=t["file"], sheet=t["sheet"], verdict=verdict, reasons=" | ".join(rs), rows_with_value=r["rows_with_value"],
                                  participants_with_value=r["participants_with_value"], expected=coh.expected, n_distinct=r["n_distinct"], n_unmapped=len(r["unmapped"]), unmapped_examples="; ".join(v for v, _ in r["unmapped"][:5]),
                                  near_miss_case_only=r["near_miss"], nonnumeric=r["nonnumeric"], out_of_range=r["out_of_range"], missing_dropped=r["missing_dropped"], grain_declared=declared, grain_measured=r["grain_measured"],
                                  precedence="" if b["precedence"] is None else b["precedence"], row_filter="yes" if b["applies"] else "", distinct_overflow="yes" if r["overflow"] else "",
                                  label_is_list="yes" if len(b["labels"]) > 1 else "", any_token_passthrough="yes" if r["anytoken"] else "", header_note=r["header_note"]))
                    for v, n in r["unmapped"]:
                        U.append(dict(cohort=coh.name, mapping_file=b["mapping_file"], block=b["block"], source_label=b["source_label"], file=os.path.basename(t["file"]), sheet=t["sheet"], value=v, rows=n))
        for f, s, why in unresolved:
            K.append(dict(cohort=coh.name, file=f, sha256=s, problem=why))
        roll = collections.Counter()
        for bkey, vs in pair_verdicts.items():
            ok = {v for v in vs if v.startswith("LOADABLE")}
            roll["loadable, every value mapped" if vs == {"LOADABLE"} else ("loadable, some observed values still to map" if ok and ok == vs else ("loadable on some of its pinned files" if ok else ("blocked by structure" if "BLOCKED" in vs else ("not assessed: key or layout undeclared" if "NOT ASSESSED" in vs else "empty for the scoped participants"))))] += 1
        reasons_n = collections.Counter(x for bkey, xs in block_reasons.items() if pair_verdicts[bkey] != {"LOADABLE"} for x in xs)
        grain_cmp = collections.Counter((d, m) for _, d, m in block_grain.values())
        verdicts = roll
        excl = len({k for sha in groups for k in excluded_by_sha.get(sha, ())})
        nokey = sum(1 for f in F if f["cohort"] == coh.name and f.get("read") == "ok" and f.get("keyed") == "no")
        mine = [f for f in F if f["cohort"] == coh.name]
        best = max([f["participants_found"] for f in mine if isinstance(f.get("participants_found"), int)] or [0])
        SUM.append(dict(cohort=coh.name, expected=coh.expected, bridge=len(coh.P), files=len(groups), tables=len(mine), unresolved=len(unresolved), best_participants=best,
                        verdicts=dict(verdicts), reasons=dict(reasons_n), grain=dict(grain_cmp), collisions=coh.collisions, nokey=nokey, blocks=len(pair_verdicts), excluded=excl,
                        elements=len({b["registry_label"] for b in B if b["cohort"] == coh.name and b["verdict"].startswith("LOADABLE")}),
                        unmapped_values=sum(1 for u in U if u["cohort"] == coh.name), unmapped_blocks=len({(u["mapping_file"], u["block"]) for u in U if u["cohort"] == coh.name})))
        log("  files", len(groups), "tables", len(mine), "unresolved", len(unresolved), "| blocks", dict(verdicts))

    def write(name, rows):
        if not rows:
            open(os.path.join(out, name), "w").write("")
            return
        cols = []
        for r in rows:
            for k in r:
                if k not in cols:
                    cols.append(k)
        with open(os.path.join(out, name), "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols, delimiter="\t", restval="")
            w.writeheader()
            w.writerows(rows)
    write("files.tsv", F)
    write("blocks.tsv", B)
    write("unmapped_values.tsv", U)
    write("unresolved_files.tsv", K)
    lines = ["# Layer 1 dry run", "", "Run %s. Registry commit `%s` plus its working copy. Reads only; nothing was loaded." % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), commit), "",
             "Tables behind every number: `files.tsv` (one row per file or sheet read), `blocks.tsv` (one row per mapping block and file), `unmapped_values.tsv`, `unresolved_files.tsv`.", ""]
    for s in SUM:
        lines += ["## %s" % s["cohort"], "",
                  "- Participants: expected %d; bridge holds %d; the best-covered file resolves %d." % (s["expected"], s["bridge"], s["best_participants"]),
                  "- Files: %d resolved by sha256, read as %d tables; %d not resolved." % (s["files"], s["tables"], s["unresolved"]),
                  "- Tables in which no participant or sample key was found: %d." % s["nokey"],
                  "- Blocks marked excluded in the registry and skipped: %d." % s["excluded"],
                  "- Mapping blocks pinned to those files: %d. " % s["blocks"] + ("; ".join("%s %d" % kv for kv in sorted(s["verdicts"].items(), key=lambda kv: -kv[1])) or "none") + ". Distinct elements loadable on at least one file: %d." % s["elements"]]
        if s["unmapped_values"]:
            lines += ["- Observed values with no line in a value map: %d rows in `unmapped_values.tsv`, across %d blocks." % (s["unmapped_values"], s["unmapped_blocks"])]
        if s["reasons"]:
            lines += ["- Reasons, counted once per block:"] + ["  - %s: %d" % kv for kv in sorted(s["reasons"].items(), key=lambda kv: -kv[1])]
        if s["grain"]:
            lines += ["- Grain of loadable blocks, declared against measured. Measured means: constant within participant, else constant within sample, else varies by row. A participant-level reading cannot rule out a finer grain where each participant has one sample."] + ["  - declared %s, measured %s: %d" % (k[0], k[1] or "(no rows)", v) for k, v in sorted(s["grain"].items(), key=lambda kv: -kv[1])]
        if s["collisions"]:
            lines += ["- Identifier spellings claimed by two participants in the bridge: %d (first kept)." % s["collisions"]]
        lines += [""]
    open(os.path.join(out, "summary.md"), "w", encoding="utf-8").write("\n".join(lines))
    log("wrote", out)


if __name__ == "__main__":
    main()
