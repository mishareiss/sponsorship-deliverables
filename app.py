"""Demo page: streamlit run app.py

Shows saved extractions from output/ as a table. No API call unless you press "Re-run extraction".
"""

import json
from pathlib import Path

import streamlit as st

from deliverables.table import deliverable_rows

ROOT = Path(__file__).resolve().parent
CONTRACTS_DIR = ROOT / "data" / "contracts"
OUTPUT_DIR = ROOT / "output"
EVAL_DIR = OUTPUT_DIR / "eval"


def load_json(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0%}"


def rerun_extraction(pdf_path: Path) -> dict:
    """Call the real API, save output/<stem>.json and return the result."""
    import anthropic
    from dotenv import load_dotenv

    from deliverables.extract import default_model, extract_contract
    from deliverables.pdf_text import extract_text

    load_dotenv(ROOT / ".env")
    result = extract_contract(extract_text(pdf_path), anthropic.Anthropic(), default_model())
    out_path = OUTPUT_DIR / f"{pdf_path.stem}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def show_contract(contract: dict) -> None:
    st.markdown(f"**Sponsor:** {contract['sponsor']}  \n"
                f"**Rights holder:** {contract['rights_holder']}  \n"
                f"**Seasons:** {', '.join(contract['seasons']) or 'not stated'}  \n"
                f"**Term:** {contract['term_start'] or '?'} to {contract['term_end'] or '?'}  \n"
                f"**Payments:** {len(contract['payments'])} "
                f"({sum(p['redacted'] for p in contract['payments'])} redacted)")


def show_eval(evaluation: dict) -> None:
    d, g = evaluation["deliverables"], evaluation["grounding"]
    st.subheader("Eval against gold")
    cols = st.columns(3)
    cols[0].metric("Recall", pct(d["recall"]), f"{d['matched']}/{d['gold']}", delta_color="off")
    cols[1].metric("Precision", pct(d["precision"]), f"{d['matched']}/{d['pred']}", delta_color="off")
    cols[2].metric("Grounding", pct(g["rate"]), f"{g['grounded']}/{g['total']}", delta_color="off")


def show_deliverables(result: dict) -> None:
    deliverables = result["deliverables"]
    st.subheader(f"Deliverables ({len(deliverables)})")
    st.dataframe(deliverable_rows(result), width="stretch", hide_index=True)
    st.caption("Expand a deliverable to see the contract text it came from.")
    for d in deliverables:
        with st.expander(f"[{d['section'] or '-'}] {d['category']}: {d['description'][:90]}"):
            st.markdown("**Source quote**")
            st.text(d["source_quote"])
            for label, items in [("Conditions", d["conditions"]), ("Sponsor obligations", d["sponsor_obligations"])]:
                if items:
                    st.markdown(f"**{label}**\n" + "\n".join(f"- {item}" for item in items))


def main() -> None:
    st.set_page_config(page_title="Sponsorship deliverables", layout="wide")
    st.title("Sponsorship deliverables")

    pdfs = sorted(CONTRACTS_DIR.glob("*.pdf"))
    if not pdfs:
        st.error(f"No PDFs found in {CONTRACTS_DIR}")
        return
    pdf_path = st.sidebar.selectbox("Contract", pdfs, format_func=lambda p: p.name)
    stem = pdf_path.stem

    if st.sidebar.button("Re-run extraction", help="Calls the Claude API and overwrites the saved output"):
        from deliverables.extract import ExtractionError

        with st.spinner(f"Extracting {pdf_path.name}..."):
            try:
                rerun_extraction(pdf_path)
                st.sidebar.success("Saved new output. Eval numbers are from the last eval run.")
            except ExtractionError as err:
                st.error(f"Extraction failed: {err}")
            except Exception as err:  # API or network errors; keep the message, not a traceback
                st.error(f"API call failed: {type(err).__name__}: {err}")

    result = load_json(OUTPUT_DIR / f"{stem}.json")
    if result is None:
        st.info(f"No saved output for {stem}. Press 'Re-run extraction' to create it.")
        return

    show_contract(result["contract"])
    evaluation = load_json(EVAL_DIR / f"{stem}.json")
    if evaluation:
        show_eval(evaluation)
    show_deliverables(result)


main()
