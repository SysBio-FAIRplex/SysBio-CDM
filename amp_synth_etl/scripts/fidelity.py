#!/usr/bin/env python3
"""
Real-world fidelity. Draw values from the empirical distributions in
inputs/fidelity_distributions.json (built from normalization data that is not tracked here)
instead of uniformly -- so the synthetic cohort is epidemiologically plausible.

Shared by 03_generate.draw() (generic draws) and the hand generators in scripts/gen/batch_*.py.
Every draw stays WITHIN the caller's legal value set / range, so legality (and QC) is preserved.
Absent a distribution for a variable, falls back to uniform. Deterministic given the caller's rng.
"""
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PATH = os.path.join(ROOT, "inputs", "fidelity_distributions.json")
DIST = json.load(open(_PATH, encoding="utf-8")) if os.path.exists(_PATH) else {}


def has(var):
    return var in DIST


def _pick(rng, items, weights):
    total = sum(weights)
    if total <= 0:
        return items[rng.randrange(len(items))]
    x = rng.random() * total
    acc = 0.0
    for it, w in zip(items, weights):
        acc += w
        if x <= acc:
            return it
    return items[-1]


def _sample_numeric(fd, rng):
    if fd.get("values"):
        keys = list(fd["values"].keys())
        k = _pick(rng, keys, [fd["values"][x] for x in keys])
        try:
            return float(k)
        except (ValueError, TypeError):
            return None
    q = fd.get("quantiles")
    if q:
        u = rng.random() * 100
        i = int(u)
        j = min(i + 1, len(q) - 1)
        return q[i] * (1 - (u - i)) + q[j] * (u - i)
    return None


def categorical(var, legal, rng, labels=None):
    """Pick from `legal` weighted by var's real frequency; uniform if no distribution. `labels`
    (parallel to legal) lets a coded value also match the real data's label form."""
    fd = DIST.get(var)
    if fd and fd.get("values"):
        vals = fd["values"]
        lower = {k.lower(): v for k, v in vals.items()}

        def look(k):
            k = str(k)
            return vals[k] if k in vals else lower.get(k.lower(), 0.0)  # exact, then case-insensitive

        if labels is not None:
            w = [max(look(v), look(lab)) for v, lab in zip(legal, labels)]
        else:
            w = [look(v) for v in legal]
        if sum(w) > 0:
            return _pick(rng, legal, w)
    return legal[rng.randrange(len(legal))]


def numeric(var, lo, hi, rng, integer=True):
    """Draw a number from var's real distribution, clamped to [lo, hi]; uniform if none. Honours
    integer vs float (a float field must not collapse to int)."""
    fd = DIST.get(var)
    if fd:
        v = _sample_numeric(fd, rng)
        if v is not None:
            v = min(hi, max(lo, v))
            return int(round(v)) if integer else round(v, 4)
    if integer:
        a, b = math.ceil(lo), math.floor(hi)
        return rng.randint(a, b) if a <= b else int(round(lo))
    return round(rng.uniform(lo, hi), 4)
