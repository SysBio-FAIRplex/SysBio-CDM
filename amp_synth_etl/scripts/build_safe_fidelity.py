#!/usr/bin/env python3
"""
build_safe_fidelity.py — regenerate inputs/fidelity_distributions.json from the MASKED
v3 spec package instead of raw controlled data.

    python3 scripts/build_safe_fidelity.py /path/to/synth_spec_variables.tsv \
            [--profile /path/to/datamart_profile.json]

Why this exists: fidelity inputs must be derivable from the MASKED spec package
alone — never from raw or normalization data — so the file is safe BY CONSTRUCTION.
The masked spec has already passed two disclosure reviews; this builder adds the
following invariants on top:

  RULES (never relax these):
  1. Identifier-shaped variables are EXCLUDED entirely — no entry, ever.
  2. A value_set containing a mask sentinel ('<...MASKED...>') is EXCLUDED.
  3. Categorical entries use the spec's masked frequency counts, emitted as
     PROPORTIONS rounded to 4dp (never raw counts, never raw value lists).
  4. High-cardinality categoricals (n_unique > 40) are EXCLUDED.
  5. Numeric entries are 101-point quantile curves from a TRUNCATED-NORMAL
     APPROXIMATION of the spec's (mean, sd, min, max) — a smooth shape, never an
     enumeration of observed values; rounded to 2dp.
  6. Integer-coded categoricals without a value_set (e.g. apoe_genotype) get a
     MAXIMUM-ENTROPY fit over their legal codes matched to the spec's mean/sd.
  7. The output must pass preflight_scan.py before it is committed.
  8. Missingness markers (NA, N/A, NaN, None, empty) are EXCLUDED from categorical
     weights — they are absence, not values, and QC enums reject them.

PER-PROGRAM KEYING. The spec is per-dataset; pooling every dataset into one entry
per variable produces cross-program nonsense (a CMD single-cell tissue distribution
counted at CELL grain swamps the AD specimen-grain tissue tokens — the source of the
brain/Kidney specimen bug). So alongside the pooled entry "var" (kept for unscoped
callers), the builder emits "PROGRAM::var" entries merged WITHIN each program only.
scripts/fidelity.py resolves scoped lookups to "PROGRAM::var" first and falls back
to the pooled entry; scripts/gen/omics.py passes its programme as the scope.

--profile takes the local datamart column profile (identifier-masked at profile
time) and uses it as a CROSS-CHECK ONLY: per-program value-token sets derived from
the spec are compared against the profile's per-file marginals and disagreements
are reported. Nothing from the profile is written to the output — the masked spec
stays the sole source, so the safety argument stays by-construction.

Output shape matches scripts/fidelity.py: {"var": {"values": {...}}} or
{"var": {"quantiles": [101 floats]}}; scoped keys are "PROGRAM::var".
"""
import csv, json, math, os, re, sys
from collections import defaultdict

ID_RE = re.compile(r'(?:^|_)(id|ids|uid|guid)$|projid|library|barcode|accession|specimen_?id'
                   r'|individual|participant|sample_?id|filename|file_name|path', re.I)
MASK_RE = re.compile(r'<[^>]*MASKED', re.I)
VS_RE = re.compile(r'^(.*)\((\d+)\)$')

# integer-coded categorical value sets for rule 6 (variable -> legal codes)
CODED = {"apoe_genotype": [22, 23, 24, 33, 34, 44], "apoeGenotype": [22, 23, 24, 33, 34, 44]}


def maxent(codes, mean, sd):
    """Weights ∝ exp(a*x + b*x^2) fitted to (mean, sd) by coarse-to-fine grid search."""
    best, target = None, (mean, sd * sd + mean * mean)
    span = max(codes) - min(codes)
    for a in [x / 50 for x in range(-200, 201)]:
        for b in [x / 500 for x in range(-100, 101)]:
            w = [math.exp(a * c + b * c * c - (a * codes[0] + b * codes[0] ** 2)) for c in codes]
            s = sum(w)
            m1 = sum(wi * c for wi, c in zip(w, codes)) / s
            m2 = sum(wi * c * c for wi, c in zip(w, codes)) / s
            err = ((m1 - target[0]) / span) ** 2 + ((m2 - target[1]) / span ** 2) ** 2
            if best is None or err < best[0]:
                best = (err, w, s)
    _, w, s = best
    return {str(c): round(wi / s, 4) for c, wi in zip(codes, w)}


def trunc_normal_quantiles(mean, sd, lo, hi):
    """101 quantiles of N(mean, sd) truncated to [lo, hi] (inverse-CDF via bisection)."""
    def phi(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))
    a, b = (lo - mean) / sd, (hi - mean) / sd
    pa, pb = phi(a), phi(b)
    out = []
    for i in range(101):
        p = pa + (pb - pa) * (i / 100)
        x0, x1 = a, b
        for _ in range(60):
            xm = (x0 + x1) / 2
            if phi(xm) < p: x0 = xm
            else: x1 = xm
        out.append(round(mean + sd * (x0 + x1) / 2, 2))
    return out


def accumulate(rows, cats, nums, keyfn):
    """Apply rules 1/2/4/8 row by row; merge categorical counts and numeric moments per keyfn(row)."""
    for r in rows:
        var = r["variable"]
        if ID_RE.search(var):
            continue                               # rule 1
        key = keyfn(r)
        if key is None:
            continue
        vs = (r.get("value_set") or "").strip()
        if vs and not MASK_RE.search(vs):
            parts = [p.strip() for p in vs.split("|")]
            parsed = [VS_RE.match(p) for p in parts]
            if all(parsed) and len(parts) <= 40:   # rule 4
                for m in parsed:
                    tok = m.group(1).strip()
                    if tok.upper() in ("NA", "N/A", "NAN", "NONE", ""):
                        continue                   # rule 8
                    cats[key][tok] += int(m.group(2))
                continue
        if MASK_RE.search(vs):
            continue                               # rule 2
        try:
            mean, sd = float(r["mean"]), float(r["sd"])
            lo, hi = float(r["min"]), float(r["max"])
            n = int(float(r["n_records"] or 0))
        except (TypeError, ValueError):
            continue
        if sd <= 0 or hi <= lo or int(float(r["n_unique"] or 0)) <= 1:
            continue
        nums[key].append((n, mean, sd, lo, hi))


def emit(cats, nums, dist, coded_var=lambda k: k):
    """Rules 3/5/6 — proportions, quantile curves, max-ent coded fits."""
    for key, counts in sorted(cats.items()):
        total = sum(counts.values())
        if total <= 0 or len(counts) > 40:         # rule 4 (post-merge cardinality)
            continue
        dist[key] = {"values": {k: round(v / total, 4) for k, v in counts.items()}}
    for key, entries in sorted(nums.items()):
        if key in dist:
            continue
        var = coded_var(key)
        if var in CODED:                            # rule 6
            n, mean, sd, lo, hi = max(entries)
            dist[key] = {"values": maxent(CODED[var], mean, sd)}
            continue
        ntot = sum(e[0] for e in entries) or len(entries)
        mean = sum(e[0] * e[1] for e in entries) / ntot
        sd = sum(e[0] * e[2] for e in entries) / ntot
        lo, hi = min(e[3] for e in entries), max(e[4] for e in entries)
        if sd <= 0:
            continue
        dist[key] = {"quantiles": trunc_normal_quantiles(mean, sd, lo, hi)}


def cross_check(profile_path, dist, programs):
    """Compare per-program spec-derived token sets against the datamart column profile.
    READ-ONLY: prints agreement/disagreement; never writes profile content to the output."""
    try:
        prof = json.load(open(profile_path, encoding="utf-8"))
    except Exception as ex:
        print(f"cross-check SKIPPED: cannot read profile ({type(ex).__name__})")
        return
    files, cols = prof.get("files", {}), prof.get("columns", {})

    def amp_of_key(key):
        rel = key.split("::")[0]
        e = files.get(rel.replace("/*.json", ""))
        if e:
            return (e.get("amp") or "").strip()
        for fe in files.values():
            if fe.get("pooled_key_prefix") == rel:
                return (fe.get("amp") or "").strip()
        low = rel.lower()
        for tag, prog in (("amp-ad", "AMP-AD"), ("amp-pd", "AMP-PD"),
                          ("amp-cmd", "AMP-CMD"), ("amp-ra-sle", "AMP-RA-SLE"),
                          ("amp_ad", "AMP-AD"), ("ra-sle", "AMP-RA-SLE"), ("ark", "AMP-RA-SLE")):
            if tag in low:
                return prog
        return ""

    checked = 0
    for var in ("tissue", "organ"):
        by_prog = defaultdict(set)
        for k, p in cols.items():
            leaf = k.split("::")[-1]
            if leaf != var or p.get("masked") or p.get("kind") != "categorical":
                continue
            amp = amp_of_key(k)
            if amp:
                by_prog[amp].update(t for t in p.get("values", {})
                                    if str(t).strip().upper() not in ("NA", "N/A", "NAN", "NONE", ""))
        for prog in programs:
            spec_e = dist.get(f"{prog}::{var}")
            if not spec_e or prog not in by_prog:
                continue
            spec_toks = {t.strip().lower() for t in spec_e["values"]}
            prof_toks = {str(t).strip().lower() for t in by_prog[prog]}
            checked += 1
            only_spec = sorted(spec_toks - prof_toks)
            only_prof = sorted(prof_toks - spec_toks)
            tag = "AGREE" if not only_spec and not only_prof else "DIVERGE"
            print(f"cross-check {prog}::{var}: {tag} "
                  f"(spec {len(spec_toks)} tokens, profile {len(prof_toks)})")
            if only_spec:
                print(f"    spec-only   : {only_spec}")
            if only_prof:
                print(f"    profile-only: {only_prof}")
    if not checked:
        print("cross-check: no comparable columns found in profile")


def main():
    args = [a for a in sys.argv[1:]]
    profile = None
    if "--profile" in args:
        i = args.index("--profile")
        profile = args[i + 1]
        del args[i:i + 2]
    spec = args[0]
    rows = list(csv.DictReader(open(spec, encoding="utf-8"), delimiter="\t"))

    dist = {}
    # pooled entries (unscoped callers; unchanged semantics)
    cats, nums = defaultdict(lambda: defaultdict(float)), defaultdict(list)
    accumulate(rows, cats, nums, lambda r: r["variable"])
    emit(cats, nums, dist)

    # per-program entries "PROGRAM::var" — merged WITHIN each program only
    programs = sorted({(r.get("program") or "").strip() for r in rows} - {""})
    cats, nums = defaultdict(lambda: defaultdict(float)), defaultdict(list)
    accumulate(rows, cats, nums,
               lambda r: f'{(r.get("program") or "").strip()}::{r["variable"]}'
               if (r.get("program") or "").strip() else None)
    emit(cats, nums, dist, coded_var=lambda k: k.split("::", 1)[1])

    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "inputs", "fidelity_distributions.json")
    json.dump(dist, open(out, "w"), indent=1, sort_keys=True)
    pooled = sum(1 for k in dist if "::" not in k)
    scoped = len(dist) - pooled
    print(f"{out}: {len(dist)} entries ({pooled} pooled, {scoped} program-scoped; "
          f"{sum(1 for v in dist.values() if 'values' in v)} categorical, "
          f"{sum(1 for v in dist.values() if 'quantiles' in v)} numeric)")
    print("apoe_genotype:", dist.get("apoe_genotype"))
    for prog in programs:
        e = dist.get(f"{prog}::tissue")
        if e:
            top = sorted(e["values"].items(), key=lambda kv: -kv[1])[:4]
            print(f"{prog}::tissue -> {top}")

    if profile:
        cross_check(profile, dist, programs)


main()
