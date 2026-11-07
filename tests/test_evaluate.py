"""Offline tests for evaluate(). Small hand-built pred/gold dicts only."""

import copy

from deliverables.evaluate import evaluate

CONTRACT_TEXT = """1. Two permanent signs on the press level facade.
2. Four field level tickets to each home game.
5. Sponsorship of a sweepstakes on the Website. The Sweepstakes shall be promoted in rotating
banner advertisements, and in one promotional email."""


def make_deliverable(section: str, quote: str, **overrides) -> dict:
    deliverable = {
        "section": section,
        "category": "signage",
        "description": "desc",
        "quantity": 2,
        "unit": "signs",
        "frequency": "each home game",
        "dollar_value": None,
        "details_to_be_agreed": False,
        "conditions": [],
        "sponsor_obligations": [],
        "proof_of_performance": None,
        "source_quote": quote,
    }
    deliverable.update(overrides)
    return deliverable


def make_doc(deliverables: list[dict]) -> dict:
    return {
        "contract": {
            "sponsor": "AlphaTrade.com",
            "rights_holder": "Sterling Mets, L.P.",
            "seasons": ["2007", "2008"],
            "term_start": None,
            "term_end": None,
            "territory": None,
            "payments": [
                {"amount": None, "due_date": "2007-04-01", "redacted": True},
                {"amount": None, "due_date": "2008-04-01", "redacted": True},
            ],
        },
        "deliverables": deliverables,
    }


GOLD = make_doc([
    make_deliverable("1", "Two permanent signs on the press level facade."),
    make_deliverable("2", "Four field level tickets to each home game.", category="tickets", quantity=4),
])


def test_identical_pred_and_gold_score_perfectly():
    result = evaluate(copy.deepcopy(GOLD), GOLD, CONTRACT_TEXT)
    d = result["deliverables"]
    assert (d["matched"], d["recall"], d["precision"]) == (2, 1.0, 1.0)
    assert all(acc["accuracy"] == 1.0 for acc in result["field_accuracy"].values())
    assert result["mismatches"] == []
    assert result["unscored_differences"] == []
    assert result["contract"]["passed"] == result["contract"]["total"]


def test_merged_clause_matches_one_gold_and_misses_the_rest():
    gold = make_doc([
        make_deliverable("5", "Sponsorship of a sweepstakes on the Website."),
        make_deliverable("5", "The Sweepstakes shall be promoted in rotating banner advertisements,"),
        make_deliverable("5", "and in one promotional email."),
    ])
    merged = ("Sponsorship of a sweepstakes on the Website. The Sweepstakes shall be promoted in rotating "
              "banner advertisements, and in one promotional email.")
    pred = make_doc([make_deliverable("5", merged)])

    result = evaluate(pred, gold, CONTRACT_TEXT)
    d = result["deliverables"]
    assert d["matched"] == 1
    assert len(d["missed"]) == 2
    assert d["recall"] < 1
    # All three gold quotes are contained; the tie goes to the closest one by raw ratio.
    assert result["matches"][0]["gold_index"] == 1


def test_extra_pred_lowers_precision():
    pred = copy.deepcopy(GOLD)
    pred["deliverables"].append(make_deliverable("9", "An invented deliverable."))
    d = evaluate(pred, GOLD, CONTRACT_TEXT)["deliverables"]
    assert d["precision"] == 2 / 3
    assert d["recall"] == 1.0
    assert [x["section"] for x in d["extra"]] == ["9"]


def test_wrong_category_is_listed_and_lowers_accuracy():
    pred = copy.deepcopy(GOLD)
    pred["deliverables"][0]["category"] = "digital"
    result = evaluate(pred, GOLD, CONTRACT_TEXT)
    assert result["field_accuracy"]["category"]["correct"] == 1
    assert result["field_accuracy"]["category"]["accuracy"] == 0.5
    assert {"section": "1", "field": "category", "pred": "digital", "gold": "signage"} in result["mismatches"]


def test_quantity_null_vs_number_mismatches_and_int_vs_float_matches():
    pred = copy.deepcopy(GOLD)
    pred["deliverables"][0]["quantity"] = None  # gold is 2
    pred["deliverables"][1]["quantity"] = 4.0  # gold is 4
    result = evaluate(pred, GOLD, CONTRACT_TEXT)
    assert result["field_accuracy"]["quantity"]["correct"] == 1
    quantity_rows = [m for m in result["mismatches"] if m["field"] == "quantity"]
    assert quantity_rows == [{"section": "1", "field": "quantity", "pred": None, "gold": 2}]


def test_empty_vs_nonempty_sponsor_obligations_mismatches():
    pred = copy.deepcopy(GOLD)
    pred["deliverables"][0]["sponsor_obligations"] = ["Pay for fabrication"]
    result = evaluate(pred, GOLD, CONTRACT_TEXT)
    assert result["field_accuracy"]["has_sponsor_obligations"]["correct"] == 1
    assert {"section": "1", "field": "has_sponsor_obligations", "pred": True, "gold": False} in result["mismatches"]
    # The list text itself shows up only as an unscored difference.
    assert any(u["field"] == "sponsor_obligations" for u in result["unscored_differences"])


def test_grounding_ignores_line_breaks_but_catches_invented_quotes():
    pred = make_doc([
        # Differs from the contract only by where the line break falls.
        make_deliverable("5", "promoted in\nrotating banner\n  advertisements"),
        make_deliverable("7", "A suite for every home game."),
    ])
    grounding = evaluate(pred, GOLD, CONTRACT_TEXT)["grounding"]
    assert (grounding["grounded"], grounding["total"], grounding["rate"]) == (1, 2, 0.5)
    assert [u["section"] for u in grounding["ungrounded"]] == ["7"]


def test_deliverables_in_different_sections_never_pair():
    quote = "Two permanent signs on the press level facade."
    pred = make_doc([make_deliverable("3", quote)])
    gold = make_doc([make_deliverable("1", quote)])
    d = evaluate(pred, gold, CONTRACT_TEXT)["deliverables"]
    assert d["matched"] == 0
    assert len(d["missed"]) == 1 and len(d["extra"]) == 1


def test_contract_payment_redacted_flag_mismatch_is_reported():
    pred = copy.deepcopy(GOLD)
    pred["contract"]["payments"][1]["redacted"] = False
    contract = evaluate(pred, GOLD, CONTRACT_TEXT)["contract"]
    assert contract["checks"]["payments[1].redacted"] is False
    assert {"field": "payments[1].redacted", "pred": False, "gold": True} in contract["mismatches"]
    assert contract["passed"] == contract["total"] - 1


def test_contract_names_ignore_case_and_whitespace_and_seasons_ignore_order():
    pred = copy.deepcopy(GOLD)
    pred["contract"]["sponsor"] = "  alphatrade.COM "
    pred["contract"]["rights_holder"] = "Sterling   Mets, L.P."
    pred["contract"]["seasons"] = ["2008", "2007"]
    contract = evaluate(pred, GOLD, CONTRACT_TEXT)["contract"]
    assert contract["mismatches"] == []
