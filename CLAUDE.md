# CLAUDE.md

## Purpose
A portfolio project: an AI system that helps sports partnership teams track the deliverables they owe sponsors.
Step 1 (this code) reads a sponsorship contract PDF and uses Claude structured outputs (`output_config.format`
with a JSON schema) to extract the contract terms and every deliverable into schema-valid JSON.

## Layout
- `src/deliverables/schema.py`: `EXTRACTION_SCHEMA`, the JSON schema the output must match (from `flagship/extraction_schema.py`, plus `additionalProperties: false`)
- `src/deliverables/pdf_text.py`: PDF to text with pdfplumber; strips browser print headers/footers; `page_count`, `has_text` (scanned-PDF check)
- `src/deliverables/extract.py`: calls Claude with the schema as a structured output, checks the stop reason, parses the JSON, re-validates with jsonschema
- `src/deliverables/cli.py`: `python -m deliverables.cli`, writes `output/<pdf-stem>.json`
- `src/deliverables/evaluate.py`: `evaluate(pred, gold, contract_text)`, pure scoring of a prediction against gold
- `src/deliverables/table.py`: `deliverable_rows(result)`, pure JSON-to-table-rows conversion (eval and tests rely on `COLUMNS`); plus a pure display layer for the demo (`table_rows`, `clause_label`, `qty_text`, `status_text`, `grounded_flags` (reuses `normalize_ws`), `summary_line`, `type_counts`, `show_value_column`, `eval_line`). Plain text, no HTML
- `src/deliverables/ui.py`: Streamlit rendering for the demo. The one injected CSS block (each rule commented; no tag-like text inside it, or `st.html` drops the whole block); summary header (parties h2, Download JSON, summary line, eval line on samples); type pills; a row table built from `st.container` + `st.columns` (Clause is a tertiary button that opens an `@st.dialog`, only from the click branch). Contract text in HTML always goes through `esc()`; Markdown-rendered text (button labels, `st.header`) through `md_label()`. The `*_html` builders are pure and tested in `tests/test_ui.py`. Widget keys start with `upload_` or `sample_`; clause buttons are `<prefix>_row_<i>`, row containers `<prefix>_deliv_row_<i>` (the CSS finds them by that class)
- `.streamlit/config.toml`: demo theme (forces light mode; Barlow via Google Fonts)
- `app.py`: Streamlit demo, two tabs: **Upload a contract** (first; extracts any uploaded PDF via the API, never writes to `output/`; the upload and result live in `st.session_state` so they survive tab switches) and **Try a sample contract** (saved results in `output/`; the bundled PDF's text is read locally and cached with `st.cache_data` so rows can be checked for grounding). `app.py` holds only tabs, session state and API calls
- `src/deliverables/eval_cli.py`: `python -m deliverables.eval_cli`, prints a report, writes `output/eval/<stem>.json`
- `gold/`: hand-checked extractions, one per contract stem
- `data/contracts/`: input contract PDFs
- `output/`: extraction results (committed, not ignored)
- `tests/`: offline pytest suite

## Commands
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"                                   # install
pytest                                                    # test
python -m deliverables.cli data/contracts/mets-alphatrade-2007.pdf   # run one
python -m deliverables.cli --all                          # run every PDF in data/contracts/
python -m deliverables.eval_cli mets-alphatrade-2007      # score output/ against gold/ for one stem
python -m deliverables.eval_cli --all                     # score every stem that has a gold file
pip install -e ".[demo]" && streamlit run app.py          # demo: upload tab calls the API on "Extract deliverables"; sample tab reads output/ (API only on "Re-run")
```
Needs `.env` in the repo root with `ANTHROPIC_API_KEY` (and optionally `ANTHROPIC_MODEL`). See `.env.example`.

## Eval: what is scored
- **Matching:** deliverables pair only within the same `section`, scored by `source_quote` similarity
  (whitespace-normalized; 1.0 if one quote contains the other, else `difflib` ratio; ties go to the higher ratio).
  Greedy, best first, one-to-one. Unmatched gold = missed (recall), unmatched pred = extra (precision).
- **Scored fields** on matched pairs: `category`, `quantity`, `dollar_value`, `details_to_be_agreed`,
  `has_sponsor_obligations` and `has_conditions` (list non-empty). Numbers compare numerically; null is its own value.
- **Contract block:** `sponsor`/`rights_holder` (case/whitespace-insensitive), `seasons` (as a set),
  `term_start`/`term_end`, payment count, and per-payment `due_date` and `redacted`.
- **Grounding:** share of predicted `source_quote`s found verbatim in the PDF text (whitespace-normalized).
- **Not scored (listed for human review):** `description`, `unit`, `frequency`, condition and obligation text,
  `proof_of_performance`, `territory`, payment `amount`. Frequency is where the per-season errors live, so it is a
  known blind spot in v1. There is no minimum match score: two unrelated items in the same section will still pair.

## Rules
- Stage changes (`git add -A`), don't commit. The owner reviews and commits.
- Tests are fully offline. Never call the real API in tests; use a fake client.
- Don't change schema fields in `schema.py` without asking.
- Don't switch back to forced `tool_choice`: `claude-sonnet-5-5` rejects it with a 400.
- Never print or log the API key.
