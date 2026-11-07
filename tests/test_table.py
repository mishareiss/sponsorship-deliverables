"""Offline tests for the JSON-to-table-rows conversion used by the demo page."""

import json
from pathlib import Path

from deliverables.table import COLUMNS, deliverable_rows

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
