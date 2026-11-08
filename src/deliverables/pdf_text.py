"""Turn a contract PDF into plain text."""

import re
from pathlib import Path

import pdfplumber

# Browser print header, e.g. "10/6/26, 4:48 PM EX-10.1 Shea Stadium Advertising Agreement"
HEADER_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}, \d{1,2}:\d{2} [AP]M\b.*$")
# Browser print footer, e.g. "https://www.sec.gov/Archives/.../ex-10_1.htm 1/7"
FOOTER_RE = re.compile(r"^https?://(www\.)?sec\.gov/\S*\s+\d+/\d+$")
# Below this many non-whitespace characters we treat the PDF as scanned (no text layer).
MIN_TEXT_CHARS = 200


def strip_print_artifacts(text: str) -> str:
    """Remove browser-printout header and footer lines; keep everything else."""
    kept = [
        line
        for line in text.splitlines()
        if not HEADER_RE.match(line.strip()) and not FOOTER_RE.match(line.strip())
    ]
    return "\n".join(kept)


def extract_text(path: str | Path) -> str:
    """Read every page of the PDF and return the text without print artifacts."""
    with pdfplumber.open(path) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    return strip_print_artifacts("\n".join(pages))


def page_count(path: str | Path) -> int:
    """Number of pages in the PDF."""
    with pdfplumber.open(path) as pdf:
        return len(pdf.pages)


def has_text(text: str, min_chars: int = MIN_TEXT_CHARS) -> bool:
    """True if the text has at least min_chars non-whitespace characters.

    A scanned PDF has no text layer, so extract_text returns nothing or a few stray characters.
    """
    return len("".join(text.split())) >= min_chars
