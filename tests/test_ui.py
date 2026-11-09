"""The demo's HTML builders (deliverables.ui): contract text is untrusted, so it must come out escaped."""

import pytest

pytest.importorskip("streamlit")

from deliverables.table import table_rows  # noqa: E402
from deliverables.ui import (  # noqa: E402
    NOT_FOUND,
    cell_html,
    dialog_body_html,
    dialog_facts,
    dialog_head_html,
    md_label,
    status_html,
    summary_html,
)

EVIL = '<script>alert("x")</script> and <b>bold</b>'


def evil_row(**overrides) -> dict:
    d = {"section": "Schedule 1, 2(a) (<b>VIP</b>)", "category": "signage", "description": EVIL,
         "quantity": 2, "unit": "<b>signs</b>", "frequency": "<i>weekly</i>", "dollar_value": None,
         "details_to_be_agreed": False, "conditions": [EVIL], "sponsor_obligations": [EVIL],
         "proof_of_performance": None, "source_quote": EVIL}
    d.update(overrides)
    return table_rows({"deliverables": [d]}, "contract text without the quote")[0]


def assert_escaped(html_text: str) -> None:
    assert "<script>" not in html_text and "<b>" not in html_text and "<i>" not in html_text
    assert "&lt;script&gt;" in html_text or "&lt;b&gt;" in html_text or "&lt;i&gt;" in html_text


def test_table_cells_escape_contract_text():
    row = evil_row()
    assert "&lt;b&gt;VIP&lt;/b&gt;: " in cell_html(row["whats_owed"])  # the clause note moves here
    for field in ("whats_owed", "qty", "when"):
        assert_escaped(cell_html(row[field]))


def test_dialog_escapes_description_quote_and_lists():
    row = evil_row()
    assert_escaped(dialog_head_html(row))
    body = dialog_body_html(row)
    assert_escaped(body)
    assert body.count("&lt;script&gt;") == 3  # quote, condition, obligation
    for _, value in dialog_facts(row, with_value=True):
        assert "<b>" not in value and "<i>" not in value


def test_summary_escapes_free_text_dates():
    contract = {"term_start": "<script>soon</script>", "term_end": None, "payments": []}
    html_text = summary_html(contract, {"grounded": 1, "total": 2}, "sample-x-deliverables")
    assert "<script>" not in html_text and "&lt;script&gt;" in html_text
    assert '<a href="#sample-x-deliverables" target="_self">1 of 2 quotes found in the PDF</a>' in html_text


def test_dollar_signs_do_not_become_latex():
    assert "$" not in cell_html("$50,000 to $75,000")
    assert md_label("$5 [link](http://x)") == r"\$5 \[link\](http://x)"


def test_dialog_flags_ungrounded_quote_and_skips_empty_lists():
    row = evil_row(conditions=[], sponsor_obligations=[])
    body = dialog_body_html(row)
    assert NOT_FOUND in body and "Conditions" not in body and "Sponsor must" not in body
    grounded = table_rows({"deliverables": [{**row["deliverable"], "source_quote": "contract text"}]},
                          "contract text")[0]
    assert NOT_FOUND not in dialog_body_html(grounded)


def test_dialog_facts_blanks_and_value():
    row = evil_row(quantity=None, frequency=None, dollar_value=50000)
    facts = dict(dialog_facts(row, with_value=True))
    assert facts["Qty"] == "Not stated" and facts["When"] == "Not stated"
    assert facts["Value"] == "&#36;50,000"
    assert "deliv-check" in facts["Status"]
    assert "Value" not in dict(dialog_facts(row, with_value=False))


def test_status_html():
    assert status_html("") == ""
    assert status_html("To be agreed") == '<span class="deliv-tba">To be agreed</span>'
    assert status_html("Check quote") == '<span class="deliv-check">Check quote</span>'
    assert status_html("To be agreed · check quote") == (
        '<span class="deliv-tba">To be agreed</span> · <span class="deliv-check">check quote</span>')
