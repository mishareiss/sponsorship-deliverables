"""Offline tests for the JSON-to-table-rows conversion and display layer used by the demo page."""

import json
from pathlib import Path

from deliverables.table import (
    CATEGORY_LABELS,
    COLUMNS,
    DISPLAY_COLUMNS,
    NOT_STATED,
    category_label,
    contract_summary,
    deliverable_rows,
    display_rows,
    format_payments,
    format_term,
)

ROOT = Path(__file__).resolve().parent.parent


def make_deliverable(**overrides) -> dict:
    d = {
        "section": "1",
        "category": "signage",
        "description": "Two signs.",
        "quantity": 2,
        "unit": "signs",
        "frequency": "each home game",
        "dollar_value": None,
        "details_to_be_agreed": False,
        "conditions": [],
        "sponsor_obligations": [],
        "proof_of_performance": None,
        "source_quote": "two permanent signs",
    }
    d.update(overrides)
    return d


def test_one_row_per_deliverable():
    result = {"deliverables": [make_deliverable(section=str(i)) for i in range(5)]}
    rows = deliverable_rows(result)
    assert len(rows) == 5
    assert [r["section"] for r in rows] == ["0", "1", "2", "3", "4"]


def test_obligation_and_condition_counts():
    d = make_deliverable(sponsor_obligations=["pay for fabrication"], conditions=["MLBAM approval", "term only"])
    row = deliverable_rows({"deliverables": [d]})[0]
    assert row["sponsor_obligations"] == 1
    assert row["conditions"] == 2


def test_nulls_kept_as_none():
    d = make_deliverable(section=None, quantity=None, unit=None, frequency=None, dollar_value=None)
    row = deliverable_rows({"deliverables": [d]})[0]
    assert row["section"] is None
    assert row["quantity"] is None
    assert row["unit"] is None
    assert row["frequency"] is None
    assert row["dollar_value"] is None


def test_column_order_is_stable():
    rows = deliverable_rows({"deliverables": [make_deliverable(), make_deliverable(section="2")]})
    for row in rows:
        assert list(row) == COLUMNS


def test_empty_result():
    assert deliverable_rows({"deliverables": []}) == []


def test_saved_outputs_convert():
    for path in sorted((ROOT / "output").glob("*.json")):
        result = json.loads(path.read_text(encoding="utf-8"))
        rows = deliverable_rows(result)
        assert len(rows) == len(result["deliverables"]), path.name


# ---------- display layer ----------

def test_display_headers_in_order():
    rows = display_rows({"deliverables": [make_deliverable()]})
    assert DISPLAY_COLUMNS == ["Clause", "Type", "What's owed", "Qty", "Unit", "When", "Value",
                               "To be agreed", "Conditions", "Sponsor must"]
    assert list(rows[0]) == DISPLAY_COLUMNS


def test_display_row_values_follow_raw_rows():
    d = make_deliverable(category="scoreboard_led", dollar_value=25000, details_to_be_agreed=True,
                         conditions=["MLBAM approval"], sponsor_obligations=["supply art", "pay fees"])
    row = display_rows({"deliverables": [d]})[0]
    assert row == {"Clause": "1", "Type": "Scoreboard / LED", "What's owed": "Two signs.", "Qty": 2,
                   "Unit": "signs", "When": "each home game", "Value": 25000, "To be agreed": True,
                   "Conditions": 1, "Sponsor must": 2}


def test_every_schema_category_has_a_label():
    from deliverables.schema import EXTRACTION_SCHEMA

    item = EXTRACTION_SCHEMA["properties"]["deliverables"]["items"]
    assert set(item["properties"]["category"]["enum"]) == set(CATEGORY_LABELS)


def test_category_labels():
    assert category_label("scoreboard_led") == "Scoreboard / LED"
    assert category_label("pa_announcement") == "PA announcement"
    assert category_label("marks_designation") == "Marks & designation"
    assert category_label("naming_rights_package") == "Naming rights package"  # unknown code
    assert category_label(None) == "Other"


def make_contract(**overrides) -> dict:
    c = {"sponsor": "AlphaTrade", "rights_holder": "Mets", "seasons": ["2007", "2008"],
         "term_start": None, "term_end": None, "territory": None, "payments": []}
    c.update(overrides)
    return c


def test_contract_summary_nulls_say_not_stated():
    summary = dict(contract_summary(make_contract(seasons=[])))
    assert summary == {"Sponsor ↔ Rights holder": "AlphaTrade ↔ Mets", "Seasons": NOT_STATED,
                       "Term": NOT_STATED, "Payments": NOT_STATED}
    assert "?" not in "".join(summary.values())


def test_contract_summary_term_and_payments():
    paid = [{"amount": 500000, "due_date": None, "redacted": False},
            {"amount": 2000000, "due_date": None, "redacted": False}]
    summary = dict(contract_summary(make_contract(term_start="2026-01-26", term_end="2029-06-30", payments=paid)))
    assert summary["Term"] == "January 26, 2026 to June 30, 2029"
    assert summary["Payments"] == "2 payments totaling $2,500,000"
    assert summary["Seasons"] == "2007, 2008"


def test_partial_term_and_redacted_payments():
    assert format_term("2012-06-13", None) == "Starts June 13, 2012; end date not stated in contract"
    assert format_term(None, "2029-06-30") == "Ends June 30, 2029; start date not stated in contract"
    assert format_term("sometime in 2014", None).startswith("Starts sometime in 2014")
    redacted = [{"amount": None, "due_date": None, "redacted": True}] * 6
    assert format_payments(redacted) == "6 payments, amounts redacted"
    mixed = [{"amount": 1000, "due_date": None, "redacted": False}, {"amount": None, "due_date": None, "redacted": True}]
    assert format_payments(mixed) == "2 payments: $1,000 stated, 1 redacted"


def test_saved_outputs_display():
    for path in sorted((ROOT / "output").glob("*.json")):
        result = json.loads(path.read_text(encoding="utf-8"))
        rows = display_rows(result)
        assert all(list(r) == DISPLAY_COLUMNS for r in rows), path.name
        assert all("_" not in r["Type"] for r in rows), path.name
        assert len(contract_summary(result["contract"])) == 4
