# Task 1 — Contract extraction pipeline (PDF → validated deliverables JSON)

## Context
This is a new, empty repo. It's a portfolio project: an AI system that helps sports partnership teams track the deliverables they owe sponsors. This task builds step 1: read a sponsorship contract PDF, then use Claude tool use as a structured-output mechanism to extract the contract terms and every deliverable into JSON. Later tasks (not this one): an eval against hand-checked gold files, reconciliation against proof-of-performance data, and drafting partner recaps.

Read these first:
- `/Users/mishareiss/Documents/FDE Prep/flagship/extraction_schema.py`: the tool definition. Use it as-is.
- `/Users/mishareiss/Documents/FDE Prep/flagship/schema.md`: notes on the fields.
- `/Users/mishareiss/Documents/FDE Prep/reading/contracts/`: 3 contract PDFs. `mets-alphatrade-2007.pdf` is the primary test case. It's a 2007 SEC filing; the fee amounts are redacted as `$*`.

The structured-output pattern: the tool is never "run." Claude is forced to call it with `tool_choice`, and the tool's `input` is the extraction result.

IMPORTANT: `git init`, then STAGE all changes (`git add -A`) but DO NOT COMMIT. I review and commit myself.

## Scope
1. **Layout:** `src/deliverables/` package (`schema.py`, `pdf_text.py`, `extract.py`, `cli.py`), `data/contracts/` (copy in the 3 PDFs), `output/`, `tests/`, `pyproject.toml`, `.env.example` (`ANTHROPIC_API_KEY=`, `ANTHROPIC_MODEL=`), and `.gitignore` (ignore `.env`, `.venv`, caches; do NOT ignore `output/`).
2. **`schema.py`:** copy `EXTRACT_TOOL` and `TOOL_NAME` from `extraction_schema.py` without changing any fields. If you think a field is wrong, say so in your report instead of changing it.
3. **`pdf_text.py`:** `extract_text(path) -> str` using pdfplumber. The Mets PDF is a browser printout, so every page has a header line like `10/6/26, 4:48 PM ... EX-10.1 Shea Stadium Advertising Agreement` and a footer line that is a sec.gov URL followed by a page number like `1/7`. Strip those with a separate pure function `strip_print_artifacts(text) -> str` so it can be unit-tested. Keep everything else, including the `$*` redaction markers.
4. **`extract.py`:** `extract_contract(text, client, model) -> dict`.
   - Call `client.messages.create` with `tools=[EXTRACT_TOOL]`, `tool_choice={"type": "tool", "name": TOOL_NAME}`, and `max_tokens=16000`. Put the contract in `<contract>` tags in the user message.
   - System prompt rules:
     - Extract every deliverable the rights holder provides to the sponsor, one per numbered clause unless a clause clearly contains separate items.
     - Use null when the contract doesn't state something; never guess.
     - Mark redacted amounts with `redacted: true` and `amount: null`.
     - `source_quote` must be verbatim contract text.
     - Legal boilerplate (indemnity, subordination, governing law, payment default interest) is not a deliverable.
   - If `stop_reason == "max_tokens"`, raise `ExtractionError`. A truncated tool input is a silent bad result, so fail loudly.
   - Raise `ExtractionError` if there's no `tool_use` block.
   - Validate the tool input against `EXTRACT_TOOL["input_schema"]` with `jsonschema`, and raise `ExtractionError` with the validation message if it fails.
   - Model comes from `ANTHROPIC_MODEL`, default `claude-sonnet-5-5`.
5. **`cli.py`:** `python -m deliverables.cli <pdf>` writes `output/<pdf-stem>.json` (`ensure_ascii=False, indent=2`) and prints a summary: deliverable count, count by category, and how many have `details_to_be_agreed`. `--all` runs every PDF in `data/contracts/`. Load `.env` with python-dotenv. Never print the API key.
6. **`CLAUDE.md`:** project purpose (2–3 lines), layout, commands (install, test, run), and rules: stage don't commit; tests are offline; never call the real API in tests; don't change schema fields without asking.
7. **`README.md`:** a short stub covering the problem, how to run it, and current status. The full README comes in a later task.

## Testing
pytest. Fully offline: mock the Anthropic client with a fake object whose `messages.create` records its kwargs and returns a fake response. Cover these cases:
- Returns the tool input dict on a valid `tool_use` response.
- Passes `tools` and the forced `tool_choice` correctly (assert on the recorded kwargs).
- Raises `ExtractionError` on `stop_reason="max_tokens"`.
- Raises when there's no `tool_use` block.
- Raises when the tool input fails schema validation (e.g. a deliverable missing `source_quote`).
- `strip_print_artifacts` removes header and footer lines and keeps body text and `$*`.
- `extract_text` on the real Mets PDF in `data/contracts/` returns text containing "Pitch Speed LED Scoreboards" and no sec.gov URL lines. This is a local file, so no network is involved.

## Constraints
- Python 3.11+. Dependencies: anthropic, pdfplumber, python-dotenv, jsonschema, and pytest for dev only. Nothing else.
- Use a venv in the repo. Install the package in editable mode so tests import `deliverables`.
- Keep it small and readable. I need to explain every file in an interview, so no clever abstractions.

## Acceptance criteria
1. `pytest` passes.
2. `python -m deliverables.cli data/contracts/mets-alphatrade-2007.pdf` runs against the real API using `.env` in the repo root and writes a schema-valid `output/mets-alphatrade-2007.json`. If `.env` is missing, stop and tell me; don't create a key.
3. `git status` shows everything staged and no commits.

## Report back with
- File tree.
- Confirmation that changes are staged, not committed.
- `pytest` output.
- The CLI summary for the Mets contract.
- The full JSON for the deliverables from clauses 3 and 4 (PA announcement and the $50,000 SNY inventory).
- Any deviations from this brief and why.
- A plain-English walkthrough of `extract.py` in 5–8 sentences that I could say out loud in an interview.

STAGE all changes, DO NOT COMMIT.
