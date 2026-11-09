"""Streamlit demo (app.py) through Streamlit's test harness. Fully offline: any API call fails the test."""

import json
from pathlib import Path

import pytest

st_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = st_testing.AppTest

ROOT = Path(__file__).resolve().parent.parent
APP = str(ROOT / "app.py")
CONTRACTS = ROOT / "data" / "contracts"
METS = ROOT / "output" / "mets-alphatrade-2007.json"
NO_SELECTION = "Select a row to see the contract text behind it."


@pytest.fixture(autouse=True)
def no_api(monkeypatch):
    """Make any attempt to build an API client or extract fail loudly."""
    import anthropic

    import deliverables.extract

    def boom(*args, **kwargs):
        raise AssertionError("the app called the API")

    monkeypatch.setattr(anthropic, "Anthropic", boom)
    monkeypatch.setattr(deliverables.extract, "extract_contract", boom)


def run_app(session: dict | None = None) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=30)
    for key, value in (session or {}).items():
        at.session_state[key] = value
    at.run()
    assert not at.exception, at.exception
    return at


def all_text(container) -> str:
    return "\n".join(m.value for m in container.markdown)


def test_renders_two_tabs_upload_first():
    at = run_app()
    assert [t.label for t in at.tabs] == ["Upload a contract", "Try a sample contract"]
    assert not at.sidebar.selectbox and not at.sidebar.button and not at.sidebar.radio
    assert "Upload a sponsorship contract PDF" in at.tabs[0].info[0].value
    assert at.title[0].value == "Sponsorship deliverables"
    assert "everything the team owes the sponsor" in all_text(at)


def open_mets() -> AppTest:
    at = run_app()
    at.selectbox(key="sample_contract").set_value(CONTRACTS / f"{METS.stem}.pdf")
    at.run()
    assert not at.exception, at.exception
    return at


def test_sample_tab_shows_saved_output_without_api():
    at = open_mets()
    sample = at.tabs[1]
    mets = json.loads(METS.read_text(encoding="utf-8"))
    assert mets["contract"]["sponsor"] in all_text(sample)
    assert "Not stated in contract" in all_text(sample)  # Mets has no term dates
    table = sample.dataframe[0].value
    assert list(table.columns)[:3] == ["Clause", "Type", "What's owed"]
    assert len(table) == len(mets["deliverables"])
    assert "Checked against the answer key" in [s.value for s in sample.subheader]
    assert any("hand-checked answer key" in c.value for c in sample.caption)
    assert at.button(key="sample_rerun").proto.type == "secondary"
    assert not sample.expander  # no wall of expanders
    assert NO_SELECTION in [c.value for c in sample.caption]


def test_sample_tab_selected_row_shows_detail_panel():
    at = open_mets()
    mets = json.loads(METS.read_text(encoding="utf-8"))
    at.session_state[f"sample_{METS.stem}_table"] = {"selection": {"rows": [0], "columns": [], "cells": []}}
    at.run()
    assert not at.exception, at.exception
    sample = at.tabs[1]
    first = mets["deliverables"][0]
    detail = all_text(sample)
    assert "Contract text" in detail and "Sponsor obligations" in detail
    assert first["source_quote"][:40].replace("'", "&#x27;") in detail
    assert NO_SELECTION not in [c.value for c in sample.caption]


def test_sample_tab_to_be_agreed_flag():
    at = open_mets()
    mets = json.loads(METS.read_text(encoding="utf-8"))
    index = next(i for i, d in enumerate(mets["deliverables"]) if d["details_to_be_agreed"])
    at.session_state[f"sample_{METS.stem}_table"] = {"selection": {"rows": [index], "columns": [], "cells": []}}
    at.run()
    assert not at.exception, at.exception
    assert '<p class="deliv-tba">To be agreed</p>' in all_text(at.tabs[1])


def test_sample_tab_type_filter_narrows_table():
    at = open_mets()
    pills = at.pills(key=f"sample_{METS.stem}_types")
    assert "Scoreboard / LED" in pills.options
    pills.set_value(["Signage"])
    at.run()
    assert not at.exception, at.exception
    table = at.tabs[1].dataframe[0].value
    assert set(table["Type"]) == {"Signage"}


def test_sample_tab_switching_contracts_does_not_call_api():
    at = run_app()
    for pdf in sorted(CONTRACTS.glob("*.pdf")):
        at.selectbox(key="sample_contract").set_value(pdf)
        at.run()
        assert not at.exception, at.exception
        assert at.tabs[1].dataframe or at.tabs[1].info


def test_upload_tab_renders_stored_result_across_reruns():
    result = json.loads(METS.read_text(encoding="utf-8"))
    text = "\n".join(d["source_quote"] for d in result["deliverables"])
    stored = {"name": "my-contract.pdf", "key": "abc", "data": b"%PDF-fake", "text": text,
              "pages": 3, "result": result}
    at = run_app({"upload": stored})

    for _ in range(2):  # first render, then a rerun with no file in the uploader
        upload = at.tabs[0]
        assert not upload.info  # not the empty "upload a PDF" prompt
        assert "my-contract.pdf · 3 pages" in upload.caption[0].value
        assert result["contract"]["sponsor"] in all_text(upload)
        assert "Grounding" in [s.value for s in upload.subheader]
        assert upload.get("download_button")  # JSON download next to the result header
        assert at.session_state["upload"]["result"] == result
        at.run()
        assert not at.exception, at.exception


def test_upload_tab_stored_file_without_result_shows_extract_button():
    stored = {"name": "x.pdf", "key": "abc", "data": b"", "text": "some contract text " * 20,
              "pages": 1, "result": None}
    at = run_app({"upload": stored})
    assert at.button(key="upload_extract").label == "Extract deliverables"
    assert at.button(key="upload_extract").proto.type == "primary"
    assert not at.tabs[0].dataframe
