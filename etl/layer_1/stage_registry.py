#!/usr/bin/env python3
"""Copy the mapping files of the released elements from the private registry into this repository's registry/ folder,
sanitized for a public repository: every file pin redacted to its hash (sha256, id_type and access_groups kept; file name
and provider id replaced by the withholding label); every commentary field blanked (status_note, note, notes,
_open_questions, reviewed_by, reviewed_on, and any key starting with "_" or "why_"); per-record fields removed
(participant_id, sample_id inside a block); definitions and provider definitions kept only up to the first sentence that
carries process text (a person, a session, a ruling, a decision record, a date, a draft or generated marker). Selection:
the elements that pass spec_check. Writes STAGED_ELEMENTS.tsv (private manifest with each copy's hash) in the given manifest directory.

    python stage_registry.py <registry dir> <private manifest dir> [--select | <element label> ...]
"""
import re
import csv, hashlib, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(os.path.dirname(HERE)); OUT = os.path.join(REPO, "registry")
LABEL = "withheld: AMP data file names are not shared under the current agreement"

COMMENTARY_KEYS = {"status_note", "note", "notes", "_open_questions", "reviewed_by", "reviewed_on", "why", "rationale", "comment", "comments", "history", "what_reads_it_instead", "surfaced_by", "classified_on", "ruled_by", "excluded_by", "excluded_on", "enforced_by", "added_by", "added_on", "changed_by", "changed_on", "evidence", "reason"}
DROP_KEYS = {"participant_value_drops", "expected_participants"}          # per-record exceptions and run-derived counts: not specification
RECORD_KEYS = {"participant_id", "sample_id", "specimen_id", "donor_id"}
# Concept names from vocabularies whose licence does not permit redistribution are withheld in the public copies; the
# concept_id, vocabulary_id and concept_code stay so a reader resolves the name from their own licensed vocabulary.
# The vocabulary of each concept comes from a private table (CDM_CONCEPT_VOCAB: concept_id, vocabulary_id, concept_code).
SNOMED_FAMILY = {"SNOMED", "Nebraska Lexicon"}
LICENSED_OTHER = {"CPT4", "HCPCS"}
SNOMED_PLACEHOLDER = "[SNOMED-LABEL-WITHHELD-MUST-HAVE-LICENSE-TO-RESOLVE]"
LICENSED_PLACEHOLDER = "[LABEL-WITHHELD-MUST-HAVE-LICENSE-TO-RESOLVE]"
UNRESOLVED_PLACEHOLDER = "[LABEL-WITHHELD-VOCABULARY-NOT-RESOLVED]"


def concept_vocabulary():
    """The private concept_id -> (vocabulary_id, concept_code) table, or an empty dict when none is given."""
    path = os.environ.get("CDM_CONCEPT_VOCAB", "")
    out = {}
    if path and os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f, delimiter="\t"):
                try:
                    out[int(r["concept_id"])] = (r["vocabulary_id"], r["concept_code"])
                except (KeyError, ValueError):
                    continue
    return out


def withhold_licensed_names(node, vocab, counts=None):
    """Walk a spec; every concept object ({id: int, name: str, ...}) gets vocabulary_id and concept_code, and its name is
    replaced by a placeholder when the vocabulary is SNOMED (or a SNOMED extension), another licensed vocabulary, or unknown.
    concept id 0 (no concept) is left alone. counts, if given, receives one entry per placeholder written."""
    if isinstance(node, dict):
        if isinstance(node.get("id"), int) and isinstance(node.get("name"), str) and node["id"] != 0:
            v = vocab.get(node["id"])
            if v:
                node.setdefault("vocabulary_id", v[0]); node.setdefault("concept_code", v[1])
                ph = SNOMED_PLACEHOLDER if v[0] in SNOMED_FAMILY else (LICENSED_PLACEHOLDER if v[0] in LICENSED_OTHER else None)
            else:
                ph = UNRESOLVED_PLACEHOLDER
            if ph:
                node["name"] = ph
                if counts is not None: counts[ph] = counts.get(ph, 0) + 1
        for v_ in node.values(): withhold_licensed_names(v_, vocab, counts)
    elif isinstance(node, list):
        for v_ in node: withhold_licensed_names(v_, vocab, counts)
    return node


VOCAB = concept_vocabulary()
PIN_KEYS = {"file", "source_id", "id_type", "sha256", "access_groups", "sheet", "item_as_source_id", "item_as_source_ids"}      # a pin is identity only; no notes ride on it
FREE_TEXT_WORDS = 4          # a source value of this many words or more is a per-record text, not a category
DEFINITION_MAX = 160         # a first sentence longer than this is rationale, not a definition
DATA_FILE_MARKS = ("datamart/", "metadata.tsv", ".jsonl", ".tsv", ".csv", "_file_inventory", "manifest")
FREE_TEXT_LINE = 60          # a value-map source value longer than this is a per-record text, not a category
FREE_TEXT_BLOCK = 40         # a block with this many value lines of text is a free-text column mapped line by line
PROCESS_MARKERS = tuple(m.strip() for m in open(os.environ["CDM_SANITIZE_MARKERS"], encoding="utf-8") if m.strip()) if os.environ.get("CDM_SANITIZE_MARKERS") else ("session", "ruling", "Ruled", "ruled", "DECISIONS", "decision", "TODO", "DRAFT", "GENERATED", "RETIRED", "ADDED", "PATCHED", "Harmonized 20", "2025-", "2026-", "I-0", "D-0", "N-0", "F-0", "known issue")
# CDM_SANITIZE_MARKERS: optional path to a private text file, one marker per line, that extends the list above


IS_IDENTIFIER = [False]


def blank_commentary(node, in_block=False, label=""):
    """Blank or remove every commentary field, per-record field, run-derived count and observed extreme, at any depth."""
    if isinstance(node, dict):
        for k in list(node.keys()):
            v = node[k]
            if k in DROP_KEYS or k.startswith("_") or k.endswith("_by") or k.endswith("_on") or k.startswith("why_"): del node[k]; continue
            if k in COMMENTARY_KEYS:
                node[k] = [] if isinstance(v, list) else {} if isinstance(v, dict) else None if v is None else ""; continue
            if k in RECORD_KEYS and in_block: del node[k]; continue
            if k in ("data_files", "excluded_data_files") and isinstance(v, list):
                node[k] = [{kk: vv for kk, vv in d.items() if kk in PIN_KEYS} if isinstance(d, dict) else d for d in v]; continue
            if k == "src_dictionary" and isinstance(v, list):
                node[k] = [d for d in v if not (isinstance(d, str) and any(m in d for m in DATA_FILE_MARKS))]; continue
            if k == "range" and isinstance(v, dict):
                if IS_IDENTIFIER[0]: del node[k]; continue
                import math
                for b, fn in (("min", math.floor), ("max", math.ceil)):
                    if isinstance(v.get(b), float): v[b] = float(fn(v[b]))
            if k == "value_map" and isinstance(v, list):
                def free_text(e): sv = e.get("source_value") if isinstance(e, dict) else None; return isinstance(sv, str) and (len(sv) > FREE_TEXT_LINE or len(sv.split()) >= FREE_TEXT_WORDS)
                lines = v if len(v) <= 15 else [e for e in v if not free_text(e)]      # a small enumeration is never free text, however long its options read
                if len(v) >= FREE_TEXT_BLOCK and sum(len(str(e.get("source_value", ""))) for e in v if isinstance(e, dict)) / max(1, len(v)) > 25: lines = []
                if v and len(lines) * 2 < len(v): lines = []                       # more than half the lines were per-record text: the column is free text
                numeric = [e for e in v if isinstance(e, dict) and str(e.get("source_value", "")).replace(".", "", 1).replace("-", "", 1).isdigit()]
                if v and len(numeric) == len(v) and all(str(e.get("harmonized_value")) == str(e.get("source_value")) for e in numeric):
                    node[k] = []; node["value_form"] = "continuous"; continue      # observed numbers mapped to themselves: a continuous column, not an enumeration
                if len(lines) != len(v):
                    node[k] = lines
                    if not lines: node["_block_dropped_as_free_text"] = True; continue
            blank_commentary(node[k], in_block or k == "sources", label)
    elif isinstance(node, list):
        for x in node: blank_commentary(x, in_block, label)


def sanitize_definition(text):
    """Keep the first sentence only, and not even that if it carries process text, a path, an identifier-like token or a number with decimals."""
    first = text.replace("\n", " ").split(". ")[0].strip()
    if not first: return ""
    if any(m in first for m in PROCESS_MARKERS) or "/" in first and ("datamart" in first or ".tsv" in first or ".csv" in first or ".xlsx" in first or ".json" in first): return ""
    toks = "".join(ch if ch.isalnum() or ch in "-_." else " " for ch in first).split()
    if any(len(t) > 7 and any(c.isdigit() for c in t) and any(c.isalpha() for c in t) and ("-" in t or "_" in t) for t in toks): return ""
    if any(t.count(".") == 1 and t.replace(".", "").isdigit() and len(t.split(".")[1]) >= 2 for t in toks): return ""
    if len(first) > DEFINITION_MAX: return ""
    if "real coding" in first or any(len(t) >= 7 and t.isupper() and t.isalpha() for t in toks): return ""   # authoring voice (corrections, emphasis in capitals)
    return first if first.endswith((".", "]", ")")) else first + "."


PIN_NAMES = set()

def main():
    """stage_registry.py <registry dir> <private manifest dir> (--select | <label> ...)

    --select copies every element that passes spec_check (every rule, vocabulary checks when CDM_VOCAB_DSN is set); labels copy
    those elements whether or not they pass. A public copy that differs from what this script last wrote is never overwritten:
    it is reported and left alone. The manifest (private, outside the repository) records each copy's hash."""
    import spec_check
    src, mdir = sys.argv[1], sys.argv[2]; args = sys.argv[3:]
    manifest = os.path.join(mdir, "STAGED_ELEMENTS.tsv"); os.makedirs(mdir, exist_ok=True); os.makedirs(OUT, exist_ok=True)
    recorded = {}
    if os.path.exists(manifest):
        for r in csv.DictReader(open(manifest, encoding="utf-8", newline=""), delimiter="\t"): recorded[r["element"]] = r
    paths = sorted(os.path.join(src, f) for f in os.listdir(src) if f.endswith(".json"))
    for p_ in paths:                                  # every pinned data file name, so that none survives in any public string
        try: j_ = json.load(open(p_, encoding="utf-8"))
        except Exception: continue
        for s_ in j_.get("sources") or []:
            for d_ in ((s_.get("layer_1_etl") or {}).get("data_files") or []) if isinstance(s_, dict) else []:
                if d_.get("file"): PIN_NAMES.add(str(d_["file"]))
    if args and args[0] == "--select":
        vocab_rows = spec_check.vocabulary(paths)
        wanted = [p for p in paths if not spec_check.check(p, vocab_rows)[1]]
        # a public element must have a block the registry loads, and an element riding a parent's row needs that parent published too
        NOT_LOADED_ = {"excluded", "withdrawn", "superseded", "retired", "deleted"}
        def loadable(p_):
            j_ = json.load(open(p_, encoding="utf-8"))
            return any(str(s_.get("status") or "").lower() not in NOT_LOADED_ for s_ in (j_.get("sources") or []) if isinstance(s_, dict))
        wanted = [p for p in wanted if loadable(p)]
        # a private exclusion list (one registry label per line, CDM_PUBLIC_EXCLUDE) holds named elements out of the public copies
        if os.environ.get("CDM_PUBLIC_EXCLUDE"):
            excl_ = {l.strip() for l in open(os.environ["CDM_PUBLIC_EXCLUDE"], encoding="utf-8") if l.strip()}
            wanted = [p for p in wanted if os.path.splitext(os.path.basename(p))[0] not in excl_]
        while True:
            names = {os.path.splitext(os.path.basename(p))[0] for p in wanted}
            keep_ = []
            for p in wanted:
                j_ = json.load(open(p, encoding="utf-8"))
                parents = {str(r.get("parent_label")) for r in (j_.get("sysbio_etl") or []) if isinstance(r, dict) and r.get("table") == "parent"}
                if parents <= names: keep_.append(p)
                else: print("not selected, its parent is not public:", os.path.basename(p), sorted(parents - names))
            if len(keep_) == len(wanted): break
            wanted = keep_
    else:
        wanted = [os.path.join(src, a + ".json") for a in args if os.path.exists(os.path.join(src, a + ".json"))]
    kept = []
    for p in wanted:
        j = json.load(open(p, encoding="utf-8")); redacted = 0
        label = str(j.get("registry_label") or os.path.splitext(os.path.basename(p))[0]); dest = os.path.join(OUT, label + ".json")
        if os.path.exists(dest):
            have = hashlib.sha256(open(dest, "rb").read()).hexdigest(); rec = recorded.get(label)
            if not rec or rec.get("public_sha256") != have:
                kept.append(label); continue                                       # changed by hand, or unknown to this script: never overwritten
        for s in j.get("sources") or []:
            l1 = s.get("layer_1_etl") or {}
            for d in (l1.get("data_files") or []) + (l1.get("excluded_data_files") or []):
                if d.get("file"): d["file"] = LABEL; redacted += 1
        land = " ".join(str((x.get("defining_concept_id") or {}).get("name") or "") for x in (j.get("sysbio_etl") or []) if isinstance(x, dict))
        IS_IDENTIFIER[0] = "identifier" in " ".join(str(v) for v in (j.get("harmonized_values") or [])).lower() or "identifier" in land.lower() or "identifier" in str(j.get("definition") or "").lower()
        blank_commentary(j, label=label)
        j["sources"] = [s_ for s_ in (j.get("sources") or []) if not (s_.get("layer_1_etl") or {}).pop("_block_dropped_as_free_text", False)]
        for s in j.get("sources") or []:
            if s.get("src_definition"): s["src_definition"] = sanitize_definition(str(s["src_definition"]))
        stems = [n.rsplit(".", 1)[0] for n in PIN_NAMES if len(n.rsplit(".", 1)[0]) > 12]
        def redact_files(o):                 # no provider data file is named anywhere in a public copy
            if isinstance(o, dict): return {k: redact_files(v) for k, v in o.items()}
            if isinstance(o, list): return [redact_files(v) for v in o]
            if isinstance(o, str):
                if re.search(r"\S+\.(?:xlsx|csv|tsv|jsonl|rds|soft\.gz|h5ad)\b", o, re.I): o = re.sub(r"\S+\.(?:xlsx|csv|tsv|jsonl|rds|soft\.gz|h5ad)\b", "[data file name withheld]", o, flags=re.I)
                for st in stems:
                    if st in o: o = o.replace(st, "[data file name withheld]")
            return o
        for k in list(j.keys()):
            if k != "sources": j[k] = redact_files(j[k])
        for s in j.get("sources") or []:
            for k in list(s.keys()):
                if k not in ("layer_1_etl",): s[k] = redact_files(s[k])
        NOT_LOADED = {"excluded", "withdrawn", "superseded", "retired", "deleted"}     # a block the registry does not load is dropped; every other block is approved
        j["sources"] = [s_ for s_ in (j.get("sources") or []) if str(s_.get("status") or "").lower() not in NOT_LOADED]
        for s_ in j["sources"]: s_["status"] = "approved"
        if "status" in j: j["status"] = "approved"
        withhold_licensed_names(j, VOCAB)
        open(dest, "w", encoding="utf-8").write(json.dumps(j, indent=2, ensure_ascii=False) + "\n")
        recorded[label] = {"element": label, "private_registry_file": os.path.basename(p), "sha256_of_private_original": hashlib.sha256(open(p, "rb").read()).hexdigest(), "pins_redacted": str(redacted), "public_sha256": hashlib.sha256(open(dest, "rb").read()).hexdigest()}
    with open(manifest, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["element", "private_registry_file", "sha256_of_private_original", "pins_redacted", "public_sha256"], delimiter="\t", lineterminator="\n", extrasaction="ignore")
        w.writeheader(); [w.writerow({**{k: "" for k in w.fieldnames}, **recorded[k]}) for k in sorted(recorded)]
    print("copied", len(wanted) - len(kept), "elements into", OUT, "| left alone because changed by hand or unknown:", len(kept), kept[:10])


if __name__ == "__main__":
    main()
