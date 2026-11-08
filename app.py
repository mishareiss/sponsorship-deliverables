"""Demo page: streamlit run app.py

Two tabs at the top:
- Upload a contract (first): upload any PDF, press "Extract deliverables" to call the Claude API.
  Nothing is written to output/. The upload and its result live in st.session_state, so switching
  tabs or rerunning keeps them.
- Sample contracts: saved extractions from output/. No API call unless you press "Re-run extraction".

Both tabs render on every rerun, so every widget in them has a key with a tab prefix.
"""

import hashlib
import json
import os
import tempfile
from pathlib import Path

import streamlit as st

from deliverables.evaluate import evaluate_grounding
from deliverables.table import deliverable_rows

ROOT = Path(__file__).resolve().parent
CONTRACTS_DIR = ROOT / "data" / "contracts"
OUTPUT_DIR = ROOT / "output"
EVAL_DIR = OUTPUT_DIR / "eval"

UPLOAD_TAB = "Upload a contract"
SAMPLE_TAB = "Sample contracts"

# st.session_state key for the current upload: name, key (sha256), data, text, pages, result.
UPLOAD_STATE = "upload"
UPLOADER_KEY = "upload_file"


def load_json(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0%}"


def run_extraction(text: str) -> dict:
    """Call the real API on contract text and return the result. Raises on any failure."""
    import anthropic

    from deliverables.extract import default_model, extract_contract

    return extract_contract(text, anthropic.Anthropic(), default_model())


def api_key_present() -> bool:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def extract_with_messages(text: str) -> dict | None:
    """Run the extraction in a spinner; show a clean error and return None on failure."""
    from deliverables.extract import ExtractionError

    if not api_key_present():
        st.error("ANTHROPIC_API_KEY is not set. Add it to .env in the repo root (see .env.example).")
        return None
    with st.spinner("Extracting deliverables (this can take a minute)..."):
        try:
            return run_extraction(text)
        except ExtractionError as err:
            st.error(f"Extraction failed: {err}")
        except Exception as err:  # API or network errors; keep the message, not a traceback
            st.error(f"API call failed: {type(err).__name__}: {err}")
    return None


# ---------- rendering (shared by both tabs) ----------

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


def show_grounding(grounding: dict, key_prefix: str) -> None:
    st.subheader("Grounding")
    st.metric("Quotes found verbatim in the PDF", pct(grounding["rate"]),
              f"{grounding['grounded']}/{grounding['total']}", delta_color="off")
    st.caption("No answer key exists for an uploaded contract, so this is the one automatic check: "
               "each source_quote should appear word for word in the PDF text (whitespace ignored).")
    if grounding["ungrounded"]:
        with st.expander(f"Quotes not found in the PDF ({len(grounding['ungrounded'])})",
                         key=f"{key_prefix}_ungrounded"):
            for item in grounding["ungrounded"]:
                st.markdown(f"**Section {item['section'] or '-'}**")
                st.text(item["source_quote"])


def show_deliverables(result: dict, key_prefix: str) -> None:
    deliverables = result["deliverables"]
    st.subheader(f"Deliverables ({len(deliverables)})")
    st.dataframe(deliverable_rows(result), width="stretch", hide_index=True, key=f"{key_prefix}_table")
    st.caption("Expand a deliverable to see the contract text it came from.")
    for i, d in enumerate(deliverables):
        with st.expander(f"[{d['section'] or '-'}] {d['category']}: {d['description'][:90]}",
                         key=f"{key_prefix}_deliverable_{i}"):
            st.markdown("**Source quote**")
            st.text(d["source_quote"])
            for label, items in [("Conditions", d["conditions"]), ("Sponsor obligations", d["sponsor_obligations"])]:
                if items:
                    st.markdown(f"**{label}**\n" + "\n".join(f"- {item}" for item in items))


def show_result(result: dict, key_prefix: str, evaluation: dict | None = None,
                grounding: dict | None = None) -> None:
    """Contract block, then the eval or grounding summary if given, then the deliverables.

    key_prefix keeps widget keys unique, since both tabs render on every rerun.
    """
    show_contract(result["contract"])
    if evaluation:
        show_eval(evaluation)
    if grounding:
        show_grounding(grounding, key_prefix)
    show_deliverables(result, key_prefix)


# ---------- upload tab ----------

@st.cache_data(show_spinner=False)
def read_pdf(data: bytes) -> tuple[str, int]:
    """Text and page count of an uploaded PDF, via a temp file (deleted on return)."""
    from deliverables.pdf_text import extract_text, page_count

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "upload.pdf"
        path.write_bytes(data)
        return extract_text(path), page_count(path)


def clear_upload_if_removed() -> None:
    """Uploader on_change: the user pressed ✕, so drop the stored upload.

    Runs only on a user action, never when Streamlit drops the file by itself, so the stored
    result survives anything that is not a deliberate removal.
    """
    if st.session_state.get(UPLOADER_KEY) is None:
        st.session_state.pop(UPLOAD_STATE, None)


def store_upload(upload) -> None:
    """Save a newly uploaded file to session state, replacing any earlier upload and its result."""
    data = upload.getvalue()
    file_key = hashlib.sha256(data).hexdigest()
    stored = st.session_state.get(UPLOAD_STATE)
    if stored and stored["key"] == file_key:
        return  # same file as before: keep its result
    st.session_state.pop(UPLOAD_STATE, None)
    text, pages = read_pdf(data)  # raises on unreadable files; nothing is stored then
    st.session_state[UPLOAD_STATE] = {"name": upload.name, "key": file_key, "data": data,
                                      "text": text, "pages": pages, "result": None}


def upload_tab() -> None:
    from deliverables.pdf_text import has_text

    upload = st.file_uploader("Upload a sponsorship contract (PDF)", type="pdf", key=UPLOADER_KEY,
                              on_change=clear_upload_if_removed)
    if upload is not None:
        try:
            store_upload(upload)
        except Exception as err:  # pdfplumber errors on corrupt or non-PDF files
            st.error(f"Could not read this PDF: {type(err).__name__}: {err}")
            return

    # Everything below renders from session state, not from the uploader.
    stored = st.session_state.get(UPLOAD_STATE)
    if stored is None:
        st.info("Upload a contract PDF to extract its deliverables. Extraction calls the Claude API.")
        return
    text = stored["text"]
    if not has_text(text):
        st.warning("No text found — scanned PDFs aren't supported yet.")
        return

    st.caption(f"{stored['name']}: {stored['pages']} pages, {len(text):,} characters of text")

    if st.button("Extract deliverables", type="primary", key="upload_extract"):
        result = extract_with_messages(text)
        if result is not None:
            stored["result"] = result

    result = stored["result"]
    if result is None:
        return
    st.download_button("Download JSON", json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                       file_name=f"{Path(stored['name']).stem}.json", mime="application/json",
                       key="upload_download")
    show_result(result, "upload", grounding=evaluate_grounding(result["deliverables"], text))


# ---------- sample tab ----------

def rerun_extraction(pdf_path: Path) -> dict:
    """Call the real API, save output/<stem>.json and return the result."""
    from deliverables.pdf_text import extract_text

    result = run_extraction(extract_text(pdf_path))
    out_path = OUTPUT_DIR / f"{pdf_path.stem}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def sample_tab() -> None:
    """Saved output only. The Re-run button is the one place this tab calls the API."""
    pdfs = sorted(CONTRACTS_DIR.glob("*.pdf"))
    if not pdfs:
        st.error(f"No PDFs found in {CONTRACTS_DIR}")
        return
    pdf_path = st.selectbox("Contract", pdfs, format_func=lambda p: p.name, key="sample_contract")
    stem = pdf_path.stem

    if st.button("Re-run extraction", help="Calls the Claude API and overwrites the saved output",
                 key="sample_rerun"):
        from deliverables.extract import ExtractionError

        with st.spinner(f"Extracting {pdf_path.name}..."):
            try:
                api_key_present()  # loads .env
                rerun_extraction(pdf_path)
                st.success("Saved new output. Eval numbers are from the last eval run.")
            except ExtractionError as err:
                st.error(f"Extraction failed: {err}")
            except Exception as err:  # API or network errors; keep the message, not a traceback
                st.error(f"API call failed: {type(err).__name__}: {err}")

    result = load_json(OUTPUT_DIR / f"{stem}.json")
    if result is None:
        st.info(f"No saved output for {stem}. Press 'Re-run extraction' to create it.")
        return
    show_result(result, "sample", evaluation=load_json(EVAL_DIR / f"{stem}.json"))


def main() -> None:
    st.set_page_config(page_title="Sponsorship deliverables", layout="wide")
    st.title("Sponsorship deliverables")

    upload, sample = st.tabs([UPLOAD_TAB, SAMPLE_TAB])
    with upload:
        upload_tab()
    with sample:
        sample_tab()


main()
