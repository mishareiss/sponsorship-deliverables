"""Build the static public demo: python -m deliverables.site

Writes docs/index.html (GitHub Pages serves main -> /docs), docs/.nojekyll and docs/contracts/<stem>.pdf
for every output/<stem>.json that has a matching data/contracts/<stem>.pdf.

All display text is computed here with the same table.py helpers the Streamlit app uses, then embedded
as JSON; the page's JavaScript only lays it out. The page has no server and no API access, and this
module must not import anthropic (or anything that does). Output is deterministic: no timestamps.

Rebuild after changing output/ or the table helpers; a test fails if docs/index.html is stale.
"""

import base64
import hashlib
import html
import json
import re
import shutil
from pathlib import Path

from deliverables.pdf_text import extract_text
from deliverables.table import (
    NO_SELECTION,
    NOT_FOUND,
    PAGE_TITLE,
    TAGLINE,
    dialog_facts,
    dialog_kicker,
    eval_line,
    grounded_flags,
    parties_heading,
    show_value_column,
    status_pieces,
    summary_line,
    table_columns,
    table_rows,
    type_counts,
)

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = Path(__file__).with_name("site_template.html")
REPO_URL = "https://github.com/mishareiss/sponsorship-deliverables"

# Shown first and selected on load: it is the contract with an eval line.
DEFAULT_STEM = "mets-alphatrade-2007"

# Switcher labels where the party names are too long. Other stems get "<rights holder> × <sponsor> · <year>".
LABELS = {
    "mets-alphatrade-2007": "Mets × AlphaTrade · 2007",
    "49ers-violin-memory-2012": "49ers × Violin Memory · 2012",
    "learfield-vanderbilt-2026": "Vanderbilt × Learfield · 2026",
}

# Optional Muted line under a contract's summary.
NOTES = {
    "learfield-vanderbilt-2026": "The benefits list (Exhibit A) is blank in the public filing, "
                                 "so only general items appear.",
}


def contract_label(stem: str, contract: dict) -> str:
    if stem in LABELS:
        return LABELS[stem]
    year = re.search(r"(\d{4})$", stem)
    label = f"{contract.get('rights_holder') or 'Rights holder'} × {contract.get('sponsor') or 'Sponsor'}"
    return f"{label} · {year[1]}" if year else label


def row_data(row: dict, with_value: bool) -> dict:
    """One table row as display text only. Status-like values are (style, text) pieces."""
    d = row["deliverable"]
    return {
        "clause": row["clause"],
        "kicker": dialog_kicker(row),
        "type": row["type"],
        "whats_owed": row["whats_owed"],
        "qty": row["qty"],
        "when": row["when"],
        "value": row["value"],
        "status": status_pieces(row["status"]),
        "grounded": row["grounded"],
        "quote": d.get("source_quote") or "",
        "conditions": list(d.get("conditions") or []),
        "obligations": list(d.get("sponsor_obligations") or []),
        "facts": [[label, status_pieces(text) if label == "Status" else [["", text]]]
                  for label, text in dialog_facts(row, with_value)],
    }


def contract_data(stem: str, result: dict, contract_text: str, evaluation: dict | None) -> dict:
    """Everything the page shows for one contract, computed with the app's helpers."""
    flags = grounded_flags(result["deliverables"], contract_text)
    grounding = {"grounded": sum(flags), "total": len(flags)}
    with_value = show_value_column(result)
    return {
        "stem": stem,
        "label": contract_label(stem, result["contract"]),
        "heading": parties_heading(result["contract"]),
        "summary": summary_line(result["contract"], grounding),
        "eval": eval_line(evaluation) if evaluation else None,
        "note": NOTES.get(stem),
        "pdf": f"contracts/{stem}.pdf",
        "columns": [name for name, _ in table_columns(with_value)],
        "widths": [ratio for _, ratio in table_columns(with_value)],
        "with_value": with_value,
        "types": [[label, count] for label, count in type_counts(result)],
        "rows": [row_data(row, with_value) for row in table_rows(result, contract_text)],
    }


def sources(root: Path) -> list[tuple[str, Path, Path]]:
    """(stem, output json, contract pdf) for each output with a PDF; the default contract first."""
    found = [(p.stem, p, root / "data" / "contracts" / f"{p.stem}.pdf")
             for p in sorted((root / "output").glob("*.json"))]
    found = [item for item in found if item[2].exists()]
    return sorted(found, key=lambda item: (item[0] != DEFAULT_STEM, item[0]))


def load_json(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def script_json(data: object) -> str:
    """JSON safe inside a script element: no "<" (so no closing tag or comment), no "&", no line separators."""
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    for char, escaped in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026"),
                          (" ", "\\u2028"), (" ", "\\u2029")):
        text = text.replace(char, escaped)
    return text


# The page's one inline script. Its hash goes into the Content-Security-Policy, which also sets
# connect-src 'none': the browser itself blocks any network request from the page's code.
APP_SCRIPT_RE = re.compile(r'<script id="app">(.*?)</script>', re.DOTALL)


def script_hash(page_html: str) -> str:
    script = APP_SCRIPT_RE.search(page_html)[1]
    return "sha256-" + base64.b64encode(hashlib.sha256(script.encode("utf-8")).digest()).decode("ascii")


def render(contracts: list[dict]) -> str:
    page = {"contracts": contracts, "no_selection": NO_SELECTION, "not_found": NOT_FOUND}
    template = TEMPLATE.read_text(encoding="utf-8")
    replacements = {
        "__SCRIPT_HASH__": script_hash(template),
        "__TITLE__": html.escape(PAGE_TITLE),
        "__TAGLINE__": html.escape(TAGLINE),
        "__REPO_URL__": html.escape(REPO_URL),
        "__DATA__": script_json(page),  # last, so contract text is never scanned for placeholders
    }
    out = template
    for placeholder, value in replacements.items():
        assert placeholder in out, placeholder
        out = out.replace(placeholder, value)
    return out


def build(root: Path = ROOT, out_dir: Path | None = None) -> Path:
    """Write index.html, .nojekyll and contracts/*.pdf into out_dir (default root/docs). Returns index.html."""
    out_dir = out_dir or root / "docs"
    pdf_dir = out_dir / "contracts"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    contracts = []
    for stem, json_path, pdf_path in sources(root):
        evaluation = load_json(root / "output" / "eval" / f"{stem}.json")
        contracts.append(contract_data(stem, load_json(json_path), extract_text(pdf_path), evaluation))
        shutil.copyfile(pdf_path, pdf_dir / f"{stem}.pdf")
    # Drop PDFs of contracts that are no longer in the build.
    for old in pdf_dir.glob("*.pdf"):
        if old.stem not in {c["stem"] for c in contracts}:
            old.unlink()
    (out_dir / ".nojekyll").write_bytes(b"")
    index = out_dir / "index.html"
    index.write_bytes(render(contracts).encode("utf-8"))
    return index


def main() -> None:
    index = build()
    print(f"Wrote {index.relative_to(ROOT)} ({index.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
