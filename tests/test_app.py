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
    assert [t.label for t in at.tabs] == ["Upload a contract", "Sample contracts"]
    assert not at.sidebar.selectbox and not at.sidebar.button and not at.sidebar.radio
    assert "Upload a contract PDF" in at.tabs[0].info[0].value


def test_sample_tab_shows_saved_output_without_api():
    at = run_app()
    box = at.selectbox(key="sample_contract")
    box.set_value(CONTRACTS / f"{METS.stem}.pdf")
    at.run()
    assert not at.exception, at.exception
    sample = at.tabs[1]
    mets = json.loads(METS.read_text(encoding="utf-8"))
    assert mets["contract"]["sponsor"] in all_text(sample)
    assert sample.dataframe  # deliverables table
    assert "Eval against gold" in [s.value for s in sample.subheader]


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
        assert "my-contract.pdf: 3 pages" in upload.caption[0].value
        assert result["contract"]["sponsor"] in all_text(upload)
        assert "Grounding" in [s.value for s in upload.subheader]
        assert at.session_state["upload"]["result"] == result
        at.run()
        assert not at.exception, at.exception


def test_upload_tab_stored_file_without_result_shows_extract_button():
    stored = {"name": "x.pdf", "key": "abc", "data": b"", "text": "some contract text " * 20,
              "pages": 1, "result": None}
    at = run_app({"upload": stored})
    assert at.button(key="upload_extract").label == "Extract deliverables"
    assert not at.tabs[0].dataframe
