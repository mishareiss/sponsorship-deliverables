"""Demo page: streamlit run app.py

Two tabs at the top:
- Upload a contract (first): upload any PDF, press "Extract deliverables" to call the Claude API.
  Nothing is written to output/. The upload and its result live in st.session_state, so switching
  tabs or rerunning keeps them.
- Try a sample contract: saved extractions from output/. No API call unless you press "Re-run extraction".

Both tabs render on every rerun, so every widget in them has a key with a tab prefix.
Rendering of a result lives in deliverables.ui; theme in .streamlit/config.toml.
"""

import hashlib
import json
import os
import tempfile
from pathlib import Path

import streamlit as st

from deliverables.evaluate import evaluate_grounding
from deliverables.ui import inject_css, show_result

ROOT = Path(__file__).resolve().parent
CONTRACTS_DIR = ROOT / "data" / "contracts"
OUTPUT_DIR = ROOT / "output"
EVAL_DIR = OUTPUT_DIR / "eval"

UPLOAD_TAB = "Upload a contract"
SAMPLE_TAB = "Try a sample contract"
TAGLINE = ("Turn a sponsorship contract into a list of everything the team owes the sponsor, "
           "with the contract text behind each item.")

# st.session_state key for the current upload: name, key (sha256), data, text, pages, result.
UPLOAD_STATE = "upload"
UPLOADER_KEY = "upload_file"


def load_json(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


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
        st.error("ANTHROPIC_API_KEY is not set. Add it to .env in the repo root (see .env.example), "
                 "then press Extract deliverables again.")
        return None
    with st.spinner("Extracting deliverables. This takes about a minute."):
        try:
            return run_extraction(text)
        except ExtractionError as err:
            st.error(f"Extraction failed: {err}. Press Extract deliverables to try again.")
        except Exception as err:  # API or network errors; keep the message, not a traceback
            st.error(f"The Claude API call failed ({type(err).__name__}: {err}). "
                     "Check your network connection and API key, then try again.")
    return None


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

    upload = st.file_uploader("Contract PDF", type="pdf", key=UPLOADER_KEY,
                              on_change=clear_upload_if_removed)
    if upload is not None:
        try:
            store_upload(upload)
        except Exception as err:  # pdfplumber errors on corrupt or non-PDF files
            st.error(f"Could not read this file as a PDF ({type(err).__name__}: {err}). "
                     "Upload a different PDF.")
            return

    # Everything below renders from session state, not from the uploader.
    stored = st.session_state.get(UPLOAD_STATE)
    if stored is None:
        st.info("Upload a sponsorship contract PDF. Extraction uses the Claude API and takes about a minute.")
        return
    text = stored["text"]
    if not has_text(text):
        st.warning("This PDF has no text layer, so it is probably a scan. Scanned PDFs aren't supported yet; "
                   "upload a PDF with selectable text.")
        return

    st.caption(f"{stored['name']} · {stored['pages']} pages · {len(text):,} characters")

    if st.button("Extract deliverables", type="primary", key="upload_extract"):
        result = extract_with_messages(text)
        if result is not None:
            stored["result"] = result

    result = stored["result"]
    if result is None:
        return
    # The file hash is in the prefix so a new upload starts with a fresh filter and selection.
    show_result(result, f"upload_{stored['key'][:12]}",
                grounding=evaluate_grounding(result["deliverables"], text),
                download_name=f"{Path(stored['name']).stem}.json")


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
        st.error(f"No contract PDFs found in {CONTRACTS_DIR}. Add a PDF there and reload the page.")
        return
    pick, rerun = st.columns([4, 1], vertical_alignment="bottom")
    pdf_path = pick.selectbox("Contract", pdfs, format_func=lambda p: p.name, key="sample_contract")
    stem = pdf_path.stem

    if rerun.button("Re-run extraction", help="Calls the Claude API and overwrites the saved output",
                    key="sample_rerun", width="stretch"):
        from deliverables.extract import ExtractionError

        with st.spinner(f"Extracting {pdf_path.name}..."):
            try:
                api_key_present()  # loads .env
                rerun_extraction(pdf_path)
                st.success("Saved new output. The answer-key numbers are from the last eval run; "
                           "run python -m deliverables.eval_cli to refresh them.")
            except ExtractionError as err:
                st.error(f"Extraction failed: {err}. Press Re-run extraction to try again.")
            except Exception as err:  # API or network errors; keep the message, not a traceback
                st.error(f"The Claude API call failed ({type(err).__name__}: {err}). "
                         "Check your network connection and API key, then try again.")

    result = load_json(OUTPUT_DIR / f"{stem}.json")
    if result is None:
        st.info(f"No saved output for {stem} yet. Press Re-run extraction to create it.")
        return
    # The stem is in the prefix so each contract keeps its own filter and selection.
    show_result(result, f"sample_{stem}", evaluation=load_json(EVAL_DIR / f"{stem}.json"))


def main() -> None:
    st.set_page_config(page_title="Sponsorship deliverables", layout="wide")
    inject_css()
    st.title("Sponsorship deliverables")
    st.markdown(TAGLINE)

    upload, sample = st.tabs([UPLOAD_TAB, SAMPLE_TAB])
    with upload:
        upload_tab()
    with sample:
        sample_tab()


main()
