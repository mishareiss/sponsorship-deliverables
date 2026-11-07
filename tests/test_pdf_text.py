"""Tests for PDF text extraction. Uses a local PDF only; no network."""

from pathlib import Path

from deliverables.pdf_text import extract_text, strip_print_artifacts

METS_PDF = Path(__file__).parent.parent / "data" / "contracts" / "mets-alphatrade-2007.pdf"


def test_strip_print_artifacts_removes_header_and_footer():
    text = (
        "10/6/26, 4:48 PM EX-10.1 Shea Stadium Advertising Agreement\n"
        "4. Advertising inventory with a value of $50,000, based on the applicable rate card,\n"
        "AlphaTrade shall pay Sterling $* on or before April 1, 2007.\n"
        "https://www.sec.gov/Archives/edgar/data/1076462/000101738607000024/ex-10_1.htm 1/7\n"
        "10/6/26, 4:48 PM EX-10.1 Shea Stadium Advertising Agreement\n"
        "the prior approval of MLBAM."
    )
    result = strip_print_artifacts(text)

    assert "PM EX-10.1" not in result
    assert "sec.gov" not in result
    assert "4. Advertising inventory with a value of $50,000" in result
    assert "$*" in result
    assert result.endswith("the prior approval of MLBAM.")


def test_extract_text_on_mets_pdf():
    text = extract_text(METS_PDF)

    assert "Pitch Speed LED Scoreboards" in text
    assert not any("sec.gov" in line for line in text.splitlines())
    assert "$*" in text
