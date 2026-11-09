"""Offline tests for the JSON-to-table-rows conversion and display layer used by the demo page."""

import json
from pathlib import Path

from deliverables.table import (
    CATEGORY_LABELS,
    COLUMNS,
    category_label,
    clause_label,
    clause_parts,
    deliverable_rows,
    eval_line,
    format_payments,
    format_term,
    grounded_flags,
    qty_text,
    show_value_column,
    status_text,
    summary_line,
    table_rows,
    type_counts,
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


def test_clause_label_shortens_schedules():
    assert clause_label("Schedule 1, 2(a)") == "Sch. 1 · 2(a)"
    assert clause_label("Schedule 1, 4(c)(ii)-(iii)") == "Sch. 1 · 4(c)(ii)-(iii)"
    assert clause_label("3") == "3"
    assert clause_label("4(a)(ii)") == "4(a)(ii)"  # sub-clause numbering is not a note
    assert clause_label(None) == "–"
    assert clause_label("  ") == "–"


def test_clause_note_is_split_off_and_prefixed():
    assert clause_parts("Schedule 1, 5(c) (Super Bowl)") == ("Sch. 1 · 5(c)", "Super Bowl")
    d = make_deliverable(section="Schedule 1, 5(c) (Super Bowl)", description="Two tickets to the game.")
    assert table_rows({"deliverables": [d]}, "")[0]["whats_owed"] == "Super Bowl: Two tickets to the game."
    d = make_deliverable(section="Schedule 1, 5(c) (Super Bowl)", description="Two SUPER BOWL tickets.")
    assert table_rows({"deliverables": [d]}, "")[0]["whats_owed"] == "Two SUPER BOWL tickets."  # already says it


def test_qty_text():
    assert qty_text(4, "signs") == "4 signs"
    assert qty_text(4.0, None) == "4"
    assert qty_text(2.5, "hours") == "2.5 hours"
    assert qty_text(1200, "tickets") == "1,200 tickets"
    assert qty_text(None, "signs") == ""
    assert qty_text(0, "signs") == "0 signs"


def test_status_text_all_four_cases():
    assert status_text(True, True) == "To be agreed"
    assert status_text(False, False) == "Check quote"
    assert status_text(True, False) == "To be agreed · check quote"
    assert status_text(False, True) == ""


def test_grounded_flags_ignore_line_breaks():
    text = "Sponsor shall receive two\npermanent   signs at the\n\nStadium."
    ds = [make_deliverable(source_quote="two permanent signs at the Stadium"),
          make_deliverable(source_quote="three permanent signs")]
    assert grounded_flags(ds, text) == [True, False]
    assert grounded_flags([], text) == []


def test_table_rows():
    d = make_deliverable(section="Schedule 1, 2(a)", category="scoreboard_led", quantity=4.0, unit="signs",
                         dollar_value=50000, details_to_be_agreed=True, source_quote="not in the text")
    row = table_rows({"deliverables": [d]}, "two permanent signs")[0]
    assert {k: v for k, v in row.items() if k != "deliverable"} == {
        "clause": "Sch. 1 · 2(a)", "type": "Scoreboard / LED", "whats_owed": "Two signs.", "qty": "4 signs",
        "when": "each home game", "status": "To be agreed · check quote", "value": "$50,000", "grounded": False}
    assert row["deliverable"] is d
    blank = table_rows({"deliverables": [make_deliverable(frequency=None)]}, "two permanent signs")[0]
    assert (blank["when"], blank["value"], blank["status"]) == ("", "", "")


def test_show_value_column():
    assert show_value_column({"deliverables": [make_deliverable(), make_deliverable(dollar_value=50000)]})
    assert not show_value_column({"deliverables": [make_deliverable(), make_deliverable()]})
    assert not show_value_column({"deliverables": []})


def test_type_counts_most_common_then_label():
    cats = ["tickets", "signage", "broadcast", "tickets", "signage", "digital", "tickets"]
    result = {"deliverables": [make_deliverable(category=c) for c in cats]}
    assert type_counts(result) == [("Tickets", 3), ("Signage", 2), ("Broadcast", 1), ("Digital", 1)]


def make_contract(**overrides) -> dict:
    c = {"sponsor": "AlphaTrade", "rights_holder": "Mets", "seasons": ["2007", "2008"],
         "term_start": None, "term_end": None, "territory": None, "payments": []}
    c.update(overrides)
    return c


def test_summary_line_null_term_and_redacted_payments():
    redacted = [{"amount": None, "due_date": None, "redacted": True}] * 6
    line = summary_line(make_contract(payments=redacted), {"grounded": 12, "total": 12})
    assert line == "Term not stated in contract · 6 payments, amounts redacted · 12 of 12 quotes found in the PDF"


def test_summary_line_open_ended_and_full_terms():
    paid = [{"amount": 500000, "due_date": None, "redacted": False},
            {"amount": 4000000, "due_date": None, "redacted": False}]
    line = summary_line(make_contract(term_start="2012-06-13", payments=paid), {"grounded": 37, "total": 38})
    assert line == "Term starts June 13, 2012 · 2 payments totaling $4,500,000 · 37 of 38 quotes found in the PDF"
    line = summary_line(make_contract(term_start="2026-01-26", term_end="2029-06-30"), {"grounded": 4, "total": 4})
    assert line.startswith("Term January 26, 2026 to June 30, 2029 · Payments not stated in contract")
    assert summary_line(make_contract(term_end="2029-06-30"), {"grounded": 0, "total": 0}).startswith(
        "Term ends June 30, 2029 · ")


def test_format_term_and_payments():
    assert format_term("2012-06-13", None) == "Starts June 13, 2012; end date not stated in contract"
    assert format_term(None, "2029-06-30") == "Ends June 30, 2029; start date not stated in contract"
    assert format_term("sometime in 2014", None).startswith("Starts sometime in 2014")
    mixed = [{"amount": 1000, "due_date": None, "redacted": False}, {"amount": None, "due_date": None, "redacted": True}]
    assert format_payments(mixed) == "2 payments: $1,000 stated, 1 redacted"


def test_eval_line():
    evaluation = {"deliverables": {"gold": 14, "pred": 12, "matched": 12}}
    assert eval_line(evaluation) == ("Checked against a hand-built answer key: found 12 of 14 deliverables, "
                                     "no false positives.")
    evaluation = {"deliverables": {"gold": 14, "pred": 13, "matched": 11}}
    assert eval_line(evaluation).endswith("found 11 of 14 deliverables, 2 extra items not in the key.")


def test_saved_outputs_display():
    for path in sorted((ROOT / "output").glob("*.json")):
        result = json.loads(path.read_text(encoding="utf-8"))
        rows = table_rows(result, "")
        assert len(rows) == len(result["deliverables"]), path.name
        assert all("_" not in r["type"] and r["clause"] for r in rows), path.name
        assert sum(count for _, count in type_counts(result)) == len(rows), path.name
