# Task 3 — README and a small demo page

## Context
The extraction pipeline (Task 1) and eval (Task 2) are done and committed. This repo is a portfolio piece I'm sending with a job referral for a Forward Deployed Engineer role, so the README is the most important file in it: a reviewer should understand the problem, the approach, and how good it is within 2 minutes. The demo page is secondary: a small Streamlit app that shows the output as a table.

Read first: `CLAUDE.md`, `README.md`, `src/deliverables/` (all files), `output/*.json`, `output/eval/mets-alphatrade-2007.json`, `gold/mets-alphatrade-2007.json`.

IMPORTANT: STAGE all changes (`git add -A`) but DO NOT COMMIT.

## Scope

### 1. README.md (priority — do this first and do it well)
Rewrite it fully. Plain, direct prose with no hype words ("revolutionary", "seamless", "cutting-edge"). Use real numbers read from `output/eval/mets-alphatrade-2007.json`, never invented ones. Sections:

1. **Title and one-sentence pitch.** An AI pipeline that turns sponsorship contracts into a trackable list of deliverables, with an eval measuring how accurate it is.
2. **The problem** (short). Sports partnership teams sell sponsors packages of deliverables (signage, PA reads, tickets, digital, appearances) and have to track and prove each one over a season. That tracking usually starts by reading the contract by hand. Missed deliverables lead to make-goods and renewal risk. Mark this framing as based on my research, not on interviews with teams.
3. **What it does:** the steps from PDF to text to Claude to validated JSON, with a small mermaid flowchart. Then a short excerpt of real output: one deliverable (clause 4, the $50,000 SNY inventory) from `output/mets-alphatrade-2007.json`.
4. **How it works:** structured outputs with a JSON schema via `output_config`; the guards (max_tokens, refusal, unparseable JSON, jsonschema re-validation); and the extraction rules (one deliverable per clause, null instead of guessing, verbatim quotes, skip legal boilerplate).
5. **Evaluation:**
   - Method: a hand-checked gold file; deliverables matched within a clause by quote similarity; strict fields scored; free text listed for human review; quote grounding checked against the PDF.
   - A results table from the eval JSON: recall, precision, field accuracy per field, contract block, grounding.
   - Error patterns found, taken from the gold file and eval mismatches:
     - multi-part clauses merged into one (clause 5: banner ads lost)
     - the per-season preamble missed in `frequency` (clauses 5, 9, 10)
     - an optional right recorded as an obligation (clause 6)
     - a mutual obligation miscategorized (clause 12)
   - An honest note: one contract, single runs. A re-run changed clause 12's category and the frequency wording, so results vary run to run.
6. **Other contracts (no gold file):**
   - 49ers (2012 stadium deal): 39 deliverables at the sub-clause level. It exposed two schema gaps: redacted quantities can't be told apart from unstated ones, and seasons defined relative to the stadium opening don't fit a list of years.
   - Vanderbilt (2026): Exhibit A, the benefits list, is blank in the public filing, and the model didn't invent deliverables to fill it.
   - Check these claims against `output/` before writing them.
7. **Design decisions:**
   - Structured outputs over forced tool use. Forced `tool_choice` returns a 400 on Sonnet 5.5, and structured outputs is the native way to get JSON only.
   - Null over guessing.
   - A verbatim `source_quote` on every deliverable, so a human can verify it in seconds.
   - A small, explainable eval rather than an LLM judge, for v1.
8. **Limitations and next steps:**
   - Fix clause merging and preamble handling in the prompt, and measure the change with the eval.
   - Add a `redacted` flag on deliverables and a `make_good_terms` field.
   - An LLM-as-judge for free-text fields like `frequency`.
   - Multiple runs per contract to measure variance.
   - More gold files.
   - The roadmap the project is building toward: reconcile deliverables against proof-of-performance data, then draft end-of-season partner recaps.
9. **Run it:** setup (venv, `pip install -e ".[dev]"`, `.env`), extract, eval, demo, tests.
10. **Repo layout:** a short tree.

### 2. Demo page: `app.py` (Streamlit)
- A sidebar select box listing the PDFs in `data/contracts/`.
- The main area shows the saved `output/<stem>.json` by default, with no API call. Show the contract block as a few key-value lines, then the deliverables as a table: section, category, description, quantity, unit, frequency, dollar_value, details_to_be_agreed, and obligation and condition counts. Clicking a row (or an expander per deliverable) shows the `source_quote`.
- If `output/eval/<stem>.json` exists, show the headline eval numbers (recall, precision, grounding) above the table.
- A "Re-run extraction" button calls `extract_contract` with the real API, then shows and saves the new output. Show a spinner, and show any `ExtractionError` message cleanly.
- Put the JSON-to-table-rows conversion in a pure function in `src/deliverables/` (e.g. `table.py`), so it can be tested without Streamlit.
- Add `streamlit` as an optional dependency (e.g. a `demo` extra), not a core one.

### 3. Housekeeping
- Remove the iCloud `chflags` workaround from `CLAUDE.md`. The repo now lives in `~/code`, outside iCloud.
- Add the demo command to `CLAUDE.md`.

## Testing
Offline. Add tests for the pure table function: a row for every deliverable, correct obligation and condition counts, nulls handled, and column order stable. Don't test the Streamlit UI. All existing tests stay green.

## Constraints
- No new core dependencies; streamlit is only in the `demo` extra.
- The README numbers must come from the eval JSON. If anything I've described above doesn't match the files, trust the files and tell me what differed.
- Keep `app.py` short, under ~120 lines.

## Acceptance criteria
1. `pytest` passes.
2. `streamlit run app.py` starts. Give me the exact command, and confirm it loads all three contracts from saved output without calling the API.
3. The README renders cleanly on GitHub, including the mermaid diagram.
4. Everything staged, no commits.

## Report back with
- Changed files.
- Confirmation that changes are staged, not committed.
- `pytest` output.
- The full README text.
- Any place where my description in this brief didn't match the files.
- How to install the demo extra and run the app.

STAGE all changes, DO NOT COMMIT.
