"""Tests for PDF text extraction. Uses a local PDF only; no network."""

from pathlib import Path

from deliverables.pdf_text import MIN_TEXT_CHARS, extract_text, has_text, page_count, strip_print_artifacts

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


def test_page_count_on_mets_pdf():
    assert page_count(METS_PDF) == 7


def test_has_text_true_for_real_contract():
    assert has_text(extract_text(METS_PDF))


def test_has_text_false_for_empty_or_whitespace():
    assert not has_text("")
    assert not has_text("  \n\n \t ")


def test_has_text_ignores_whitespace_when_counting():
    # A scanned PDF can yield a few stray characters spread over many blank lines.
    assert not has_text("a \n" * (MIN_TEXT_CHARS - 1))
    assert has_text("a \n" * MIN_TEXT_CHARS)


def test_has_text_custom_threshold():
    assert has_text("abc", min_chars=3)
    assert not has_text("ab", min_chars=3)
