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
NINERS = ROOT / "output" / "49ers-violin-memory-2012.json"
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


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def clause_buttons(at: AppTest, prefix: str) -> list:
    return [b for b in at.button if b.key and b.key.startswith(f"{prefix}_row_")]


def header_cells(container) -> list[str]:
    return [m.value for m in container.markdown if 'class="deliv-th"' in m.value]


def test_renders_two_tabs_upload_first():
    at = run_app()
    assert [t.label for t in at.tabs] == ["Upload a contract", "Try a sample contract"]
    assert not at.sidebar.selectbox and not at.sidebar.button and not at.sidebar.radio
    upload = at.tabs[0]
    assert not upload.info  # no empty-state box
    assert upload.caption[0].value == "Extraction uses the Claude API and takes about a minute."
    assert at.title[0].value == "Sponsorship deliverables"
    assert "everything the team owes the sponsor" in all_text(at)


def open_sample(stem: str) -> AppTest:
    at = run_app()
    at.selectbox(key="sample_contract").set_value(CONTRACTS / f"{stem}.pdf")
    at.run()
    assert not at.exception, at.exception
    return at


def test_mets_sample_has_value_column_and_eval_line():
    at = open_sample(METS.stem)
    sample = at.tabs[1]
    mets = load(METS)
    text = all_text(sample)
    assert sample.header[0].value.startswith("AlphaTrade.com and Sterling Mets")
    assert "Term not stated in contract · 6 payments, amounts redacted · " in text
    assert "12 of 12 quotes found in the PDF" in text
    assert ("Checked against a hand-built answer key: found 12 of 14 deliverables, no false positives."
            in text)
    assert any(">Value<" in cell for cell in header_cells(sample))
    assert '<div class="deliv-cell">&#36;50,000</div>' in text
    assert len(clause_buttons(at, f"sample_{METS.stem}")) == len(mets["deliverables"])
    assert at.button(key="sample_rerun").proto.type == "secondary"
    assert sample.get("download_button")
    assert not sample.expander and not sample.dataframe and not sample.metric
    assert NO_SELECTION in [c.value for c in sample.caption]


def test_49ers_sample_has_no_value_column_and_a_button_per_row():
    at = open_sample(NINERS.stem)
    sample = at.tabs[1]
    niners = load(NINERS)
    headers = header_cells(sample)
    assert [h.split(">")[1].split("<")[0] for h in headers] == [
        "Clause", "Type", "What's owed", "Qty", "When", "Status"]
    buttons = clause_buttons(at, f"sample_{NINERS.stem}")
    assert len(buttons) == len(niners["deliverables"]) == 38
    assert all(b.proto.type == "tertiary" for b in buttons)
    assert buttons[3].label == "Sch. 1 · 2(a)"
    super_bowl = next(i for i, d in enumerate(niners["deliverables"]) if d["section"].endswith("(Super Bowl)"))
    assert buttons[super_bowl].label == "Sch. 1 · 5(c)"  # the note is dropped from the clause label


def test_type_pills_filter_rows():
    at = open_sample(NINERS.stem)
    prefix = f"sample_{NINERS.stem}"
    pills = at.pills(key=f"{prefix}_types")
    assert pills.value == "__all__"
    assert pills.format_func("__all__") == "All 38" and pills.format_func("Activation") == "Activation 10"
    assert "Showing" not in all_text(at.tabs[1])
    pills.set_value("Tickets")
    at.run()
    assert not at.exception, at.exception
    assert len(clause_buttons(at, prefix)) == 4
    assert "38 deliverables" in all_text(at.tabs[1]) and "Showing 4" in all_text(at.tabs[1])


def test_clause_button_opens_dialog_once():
    at = open_sample(METS.stem)
    from deliverables.ui import esc

    quote = load(METS)["deliverables"][3]["source_quote"]
    at.button(key=f"sample_{METS.stem}_row_3").click()
    at.run()
    assert not at.exception, at.exception
    text = all_text(at)
    assert "deliv-dialog-title" in text and "Contract text" in text
    assert esc(quote[:60]) in text
    at.run()  # any other rerun must not reopen it
    assert "deliv-dialog-title" not in all_text(at)


def test_sample_tab_switching_contracts_does_not_call_api():
    at = run_app()
    for pdf in sorted(CONTRACTS.glob("*.pdf")):
        at.selectbox(key="sample_contract").set_value(pdf)
        at.run()
        assert not at.exception, at.exception
        assert clause_buttons(at, f"sample_{pdf.stem}") or at.tabs[1].info


def upload_state(result: dict, text: str) -> dict:
    return {"upload": {"name": "my-contract.pdf", "key": "abc", "data": b"%PDF-fake", "text": text,
                       "pages": 3, "result": result}}


def test_upload_tab_renders_stored_result_across_reruns():
    result = load(METS)
    text = "\n".join(d["source_quote"] for d in result["deliverables"])
    at = run_app(upload_state(result, text))

    for _ in range(2):  # first render, then a rerun with no file in the uploader
        upload = at.tabs[0]
        assert not upload.info
        assert "my-contract.pdf · 3 pages" in upload.caption[1].value
        assert result["contract"]["sponsor"] in upload.header[0].value
        assert "12 of 12 quotes found in the PDF" in all_text(upload)
        assert upload.get("download_button")
        assert len(clause_buttons(at, "upload_abc")) == 12
        assert at.session_state["upload"]["result"] == result
        at.run()
        assert not at.exception, at.exception


def test_upload_flags_the_quote_not_in_the_pdf():
    """The saved 49ers output is fully grounded, so drop one quote from the text to get a flag."""
    result = load(NINERS)
    text = "\n".join(d["source_quote"] for d in result["deliverables"][1:])
    at = run_app(upload_state(result, text))
    upload_text = all_text(at.tabs[0])
    assert "37 of 38 quotes found in the PDF" in upload_text
    assert upload_text.count('<span class="deliv-check">Check quote</span>') == 1
    assert not any(">Value<" in cell for cell in header_cells(at.tabs[0]))


def test_upload_tab_stored_file_without_result_shows_extract_button():
    stored = {"name": "x.pdf", "key": "abc", "data": b"", "text": "some contract text " * 20,
              "pages": 1, "result": None}
    at = run_app({"upload": stored})
    assert at.button(key="upload_extract").label == "Extract deliverables"
    assert at.button(key="upload_extract").proto.type == "primary"
    assert not clause_buttons(at, "upload_abc")
