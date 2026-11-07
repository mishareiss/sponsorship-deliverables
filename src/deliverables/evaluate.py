"""Score an extraction (pred) against a hand-checked gold file. Pure: no I/O, no API calls.

Matching: deliverables are only paired within the same `section`. Each candidate pair is
scored by how similar their `source_quote`s are (1.0 if one contains the other, otherwise
the difflib ratio). Pairs are taken greedily, best score first, each deliverable used once.
Unmatched gold deliverables are "missed"; unmatched predictions are "extra".
"""

from difflib import SequenceMatcher
from typing import Any

# Fields compared exactly on matched pairs. has_* fields are derived from list fields below.
STRICT_FIELDS = [
    "category",
    "quantity",
    "dollar_value",
    "details_to_be_agreed",
    "has_sponsor_obligations",
    "has_conditions",
]
# Free-text fields: differences are listed for human review but not scored (v1).
UNSCORED_FIELDS = [
    "description",
    "unit",
    "frequency",
    "conditions",
    "sponsor_obligations",
    "proof_of_performance",
]


def normalize_ws(text: str) -> str:
    """Collapse every run of whitespace (spaces, line breaks, tabs) to one space and strip."""
    return " ".join(text.split())


def ratio(numerator: int, denominator: int) -> float | None:
    """numerator / denominator, or None when there is nothing to divide by."""
    return numerator / denominator if denominator else None


# ---------- matching ----------

def quote_scores(pred_quote: str, gold_quote: str) -> tuple[float, float]:
    """Return (score, raw_ratio) for two quotes.

    score is 1.0 when one normalized quote contains the other, else the raw ratio.
    raw_ratio is kept as a tie-breaker: when several gold quotes are all contained in one
    long predicted quote, the one closest to it in length wins.
    """
    p, g = normalize_ws(pred_quote), normalize_ws(gold_quote)
    raw = SequenceMatcher(None, p, g).ratio()
    contained = bool(p) and bool(g) and (p in g or g in p)
    return (1.0 if contained else raw), raw


def match_deliverables(pred: list[dict], gold: list[dict]) -> list[dict]:
    """Greedy one-to-one pairing within each section, highest score first."""
    candidates = []
    for pi, p in enumerate(pred):
        for gi, g in enumerate(gold):
            if p["section"] == g["section"]:
                score, raw = quote_scores(p["source_quote"], g["source_quote"])
                candidates.append((score, raw, pi, gi))

    # Best score first; ties broken by raw ratio, then by list position (deterministic).
    candidates.sort(key=lambda c: (-c[0], -c[1], c[2], c[3]))

    used_pred, used_gold, pairs = set(), set(), []
    for score, raw, pi, gi in candidates:
        if pi in used_pred or gi in used_gold:
            continue
        used_pred.add(pi)
        used_gold.add(gi)
        pairs.append({"section": pred[pi]["section"], "pred_index": pi, "gold_index": gi,
                      "score": round(score, 4), "raw_ratio": round(raw, 4)})
    pairs.sort(key=lambda m: m["gold_index"])
    return pairs


# ---------- field comparison ----------

def field_value(deliverable: dict, field: str) -> Any:
    """Read a field; has_* fields are derived from whether the list is non-empty."""
    if field == "has_sponsor_obligations":
        return bool(deliverable["sponsor_obligations"])
    if field == "has_conditions":
        return bool(deliverable["conditions"])
    return deliverable[field]


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def values_equal(a: Any, b: Any) -> bool:
    """Exact equality, except numbers compare numerically (4 == 4.0) and null is its own value."""
    if a is None or b is None:
        return a is None and b is None
    if is_number(a) and is_number(b):
        return float(a) == float(b)
    return a == b


def text_equal(a: Any, b: Any) -> bool:
    """Whitespace-insensitive equality for free text and lists of free text."""
    if isinstance(a, list) and isinstance(b, list):
        return [normalize_ws(x) for x in a] == [normalize_ws(x) for x in b]
    if isinstance(a, str) and isinstance(b, str):
        return normalize_ws(a) == normalize_ws(b)
    return a == b


def compare_pairs(pred: list[dict], gold: list[dict], pairs: list[dict]) -> tuple[dict, list, list]:
    """Field accuracy over matched pairs, plus scored mismatches and unscored differences."""
    correct = {field: 0 for field in STRICT_FIELDS}
    mismatches, unscored = [], []

    for pair in pairs:
        p, g = pred[pair["pred_index"]], gold[pair["gold_index"]]
        for field in STRICT_FIELDS:
            pv, gv = field_value(p, field), field_value(g, field)
            if values_equal(pv, gv):
                correct[field] += 1
            else:
                mismatches.append({"section": pair["section"], "field": field, "pred": pv, "gold": gv})
        for field in UNSCORED_FIELDS:
            if not text_equal(p[field], g[field]):
                unscored.append({"section": pair["section"], "field": field,
                                 "pred": p[field], "gold": g[field], "scored": False})

    total = len(pairs)
    accuracy = {field: {"correct": correct[field], "total": total, "accuracy": ratio(correct[field], total)}
                for field in STRICT_FIELDS}
    return accuracy, mismatches, unscored


# ---------- contract block ----------

def same_name(a: str, b: str) -> bool:
    return normalize_ws(a).casefold() == normalize_ws(b).casefold()


def evaluate_contract(pred: dict, gold: dict) -> dict:
    """Check the contract-level fields. Each check is True/False; failures are listed."""
    checks = {
        "sponsor": same_name(pred["sponsor"], gold["sponsor"]),
        "rights_holder": same_name(pred["rights_holder"], gold["rights_holder"]),
        "seasons": set(pred["seasons"]) == set(gold["seasons"]),
        "term_start": pred["term_start"] == gold["term_start"],
        "term_end": pred["term_end"] == gold["term_end"],
        "payments_count": len(pred["payments"]) == len(gold["payments"]),
    }
    mismatches = [{"field": name, "pred": pred[name], "gold": gold[name]}
                  for name in ["sponsor", "rights_holder", "seasons", "term_start", "term_end"]
                  if not checks[name]]
    if not checks["payments_count"]:
        mismatches.append({"field": "payments_count",
                           "pred": len(pred["payments"]), "gold": len(gold["payments"])})

    # Per-payment checks, in order, over the payments both sides have.
    for i, (pp, gp) in enumerate(zip(pred["payments"], gold["payments"])):
        for field in ["due_date", "redacted"]:
            name = f"payments[{i}].{field}"
            checks[name] = pp[field] == gp[field]
            if not checks[name]:
                mismatches.append({"field": name, "pred": pp[field], "gold": gp[field]})

    return {"passed": sum(checks.values()), "total": len(checks), "checks": checks, "mismatches": mismatches}


# ---------- grounding ----------

def evaluate_grounding(pred: list[dict], contract_text: str) -> dict:
    """Share of predicted source_quotes found verbatim in the contract (whitespace-normalized)."""
    text = normalize_ws(contract_text)
    ungrounded = [{"section": d["section"], "source_quote": d["source_quote"]}
                  for d in pred if normalize_ws(d["source_quote"]) not in text]
    grounded = len(pred) - len(ungrounded)
    return {"grounded": grounded, "total": len(pred), "rate": ratio(grounded, len(pred)),
            "ungrounded": ungrounded}


# ---------- top level ----------

def summarize(deliverable: dict) -> dict:
    return {"section": deliverable["section"], "category": deliverable["category"],
            "description": deliverable["description"], "source_quote": deliverable["source_quote"]}


def evaluate(pred: dict, gold: dict, contract_text: str) -> dict:
    """Score a prediction against gold. Returns a JSON-serializable result."""
    pred_d, gold_d = pred["deliverables"], gold["deliverables"]
    pairs = match_deliverables(pred_d, gold_d)
    matched_pred = {m["pred_index"] for m in pairs}
    matched_gold = {m["gold_index"] for m in pairs}
    accuracy, mismatches, unscored = compare_pairs(pred_d, gold_d, pairs)

    return {
        "deliverables": {
            "gold": len(gold_d),
            "pred": len(pred_d),
            "matched": len(pairs),
            "recall": ratio(len(pairs), len(gold_d)),
            "precision": ratio(len(pairs), len(pred_d)),
            "missed": [summarize(d) for i, d in enumerate(gold_d) if i not in matched_gold],
            "extra": [summarize(d) for i, d in enumerate(pred_d) if i not in matched_pred],
        },
        "matches": pairs,
        "field_accuracy": accuracy,
        "contract": evaluate_contract(pred["contract"], gold["contract"]),
        "grounding": evaluate_grounding(pred_d, contract_text),
        "mismatches": mismatches,
        "unscored_differences": unscored,
    }
