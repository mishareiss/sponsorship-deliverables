"""The static public demo (deliverables.site). Builds into temp dirs; offline; never touches docs/."""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from deliverables.site import build, script_hash

ROOT = Path(__file__).resolve().parent.parent
EVIL = "</script><script>alert(1)</script>"
DATA_RE = re.compile(r'<script type="application/json" id="data">(.*?)</script>', re.DOTALL)


def page_data(page_html: str) -> dict:
    return json.loads(DATA_RE.search(page_html)[1])


@pytest.fixture(scope="module")
def built(tmp_path_factory) -> Path:
    return build(ROOT, tmp_path_factory.mktemp("site"))


def test_build_has_all_three_contracts(built):
    data = page_data(built.read_text(encoding="utf-8"))
    contracts = {c["stem"]: c for c in data["contracts"]}
    assert [c["label"] for c in data["contracts"]] == [
        "Mets × AlphaTrade · 2007", "49ers × Violin Memory · 2012", "Vanderbilt × Learfield · 2026"]
    assert len(contracts["49ers-violin-memory-2012"]["rows"]) == 38
    assert "Value" not in contracts["49ers-violin-memory-2012"]["columns"]
    mets = contracts["mets-alphatrade-2007"]
    assert mets["eval"] == ("Checked against a hand-built answer key: found 12 of 14 deliverables, "
                            "no false positives.")
    assert mets["summary"].endswith("12 of 12 quotes found in the PDF")
    assert mets["columns"] == ["Clause", "Type", "What's owed", "Qty", "When", "Value", "Status"]
    assert contracts["learfield-vanderbilt-2026"]["note"].startswith("The benefits list (Exhibit A)")
    assert contracts["49ers-violin-memory-2012"]["eval"] is None


def test_pdfs_and_nojekyll_are_written(built):
    out = built.parent
    assert (out / ".nojekyll").read_bytes() == b""
    for pdf in (ROOT / "data" / "contracts").glob("*.pdf"):
        assert (out / "contracts" / pdf.name).read_bytes() == pdf.read_bytes()


def test_no_api_key_or_anthropic_in_output(built):
    page = built.read_text(encoding="utf-8")
    assert "ANTHROPIC" not in page
    assert "sk-ant" not in page
    assert "import anthropic" not in page
    env = ROOT / ".env"
    if env.exists():  # no .env value may leak into the page (compared, never printed)
        values = [line.split("=", 1)[1].strip().strip("\"'") for line in env.read_text().splitlines()
                  if "=" in line and not line.lstrip().startswith("#")]
        assert not any(len(v) > 8 and v in page for v in values), "a .env value appears in the page"


def test_site_module_does_not_import_anthropic():
    code = "import sys, deliverables.site; print('anthropic' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"


def test_page_never_builds_dom_from_markup(built):
    page = built.read_text(encoding="utf-8")
    for sink in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
        assert sink not in page, sink
    assert "fetch(" not in page and "XMLHttpRequest" not in page and "WebSocket" not in page


def test_csp_blocks_network_and_pins_the_script(built):
    page = built.read_text(encoding="utf-8")
    assert "connect-src 'none'" in page and "default-src 'none'" in page
    assert f"script-src '{script_hash(page)}'" in page


def test_contract_text_cannot_close_the_script_tag(tmp_path):
    root = tmp_path / "repo"
    (root / "output").mkdir(parents=True)
    (root / "data" / "contracts").mkdir(parents=True)
    shutil.copyfile(ROOT / "data" / "contracts" / "mets-alphatrade-2007.pdf",
                    root / "data" / "contracts" / "evil-2020.pdf")
    deliverable = {"section": "1", "category": "signage", "description": EVIL, "quantity": None, "unit": None,
                   "frequency": "<!--    ", "dollar_value": None, "details_to_be_agreed": False,
                   "conditions": [EVIL], "sponsor_obligations": [], "proof_of_performance": None,
                   "source_quote": EVIL}
    result = {"contract": {"sponsor": EVIL, "rights_holder": "Team", "term_start": None, "term_end": None,
                           "payments": []}, "deliverables": [deliverable]}
    (root / "output" / "evil-2020.json").write_text(json.dumps(result), encoding="utf-8")

    page = build(root, tmp_path / "site").read_text(encoding="utf-8")
    assert "alert(1)" in page  # the text is there...
    assert "<script>alert" not in page and "</script><script>" not in page  # ...but escaped
    assert page.count("</script>") == 2  # the data block and the app script, nothing else
    assert "<!--" not in DATA_RE.search(page)[1] and " " not in page and " " not in page
    row = page_data(page)["contracts"][0]["rows"][0]
    assert row["whats_owed"] == EVIL and row["quote"] == EVIL and row["conditions"] == [EVIL]
    assert row["when"] == "<!--    "


def test_build_is_deterministic(tmp_path, built):
    again = build(ROOT, tmp_path / "again")
    assert again.read_bytes() == built.read_bytes()
    assert sorted(p.name for p in (tmp_path / "again" / "contracts").iterdir()) == sorted(
        p.name for p in (built.parent / "contracts").iterdir())


def test_committed_docs_match_a_fresh_build(built):
    """If this fails, output/ or the table helpers changed: run python -m deliverables.site."""
    docs = ROOT / "docs"
    assert (docs / "index.html").read_bytes() == built.read_bytes(), "docs/index.html is stale"
    for pdf in (built.parent / "contracts").glob("*.pdf"):
        assert (docs / "contracts" / pdf.name).read_bytes() == pdf.read_bytes()
    assert (docs / ".nojekyll").exists()
