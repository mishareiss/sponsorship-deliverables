# Task 5 — Results page redesign: summary header, readable table, row dialog

## Context
Task 4 themed the demo, but the results page still reads like a Streamlit default. I've approved a mockup; this task builds it. The changes in short:
- Above the table, a compact summary header replaces the "Contract" and "Grounding" sections and the big 97% metric.
- Instead of `st.dataframe`, a custom row table with six readable columns. Text wraps instead of truncating.
- Clicking a row opens a dialog with the contract text.
- Quote grounding is flagged on the row it belongs to.

Behavior from Task 3c must not change: tabs, the session-state upload logic, and no API call in the sample tab except Re-run.

Read first: `app.py`, `src/deliverables/ui.py`, `src/deliverables/table.py`, `src/deliverables/evaluate.py` (`normalize_ws`, `evaluate_grounding`), `src/deliverables/pdf_text.py`, `.streamlit/config.toml`, `tests/test_app.py`, `tests/test_table.py`, `CLAUDE.md`.

IMPORTANT: STAGE all changes (`git add -A`) but DO NOT COMMIT. Add `Claude outputs/` to `.gitignore` first so it isn't staged.

## Design reference (match this)
Palette (unchanged from Task 4, except Signal):

| Name | Hex | Use |
|---|---|---|
| Paper | `#F6F7F5` | background |
| Panel | `#E9EEEA` | table header row |
| White | `#FFFFFF` | table body, dialog |
| Ink | `#1C2B2A` | text |
| Muted | `#4A5A56` | secondary text |
| Field | `#1F6B47` | primary buttons, active tab, links, selected pill |
| Signal | `#8F5512` | "To be agreed" only. Darker than before, so it passes AA at any size; update `config.toml`/CSS wherever `#A8661A` appears |
| Rule | `#CFD8D2` | borders, row dividers |

Fonts: Barlow body, Barlow Semi Condensed headings (as now). Tabular figures on numbers where CSS can reach.

Page, top to bottom:
```
Sponsorship deliverables                                  (title, ~40px, no anchor link)
Turn a sponsorship contract into a list of everything...  (subtitle, max-width ~62ch)
[Upload a contract]  [Try a sample contract]
49ers-violin-memory-2012.pdf · 22 pages · 53,438 characters
───────────────────────────────────────────────────────────────────────────────
Violin Memory, Inc. and Forty Niners SC Stadium Company LLC         [Download JSON]
Term starts June 13, 2012 · 3 payments totaling $4,500,000 · 37 of 38 quotes found in the PDF

38 deliverables   (Showing 12 when filtered)
(All 38) (Activation 12) (Broadcast 5) (Tickets 5) ...        pills with counts, only types present
┌ Clause ──────┬ Type ──────────┬ What's owed (wide, wraps) ─────┬ Qty ─────────┬ When ─────────┬ Status ──────┐
│ Sch. 1 · 2(a)│ Signage        │ Exclusive branding at Suite... │ 4 branded areas│ Each contract year│ To be agreed │
Select a row to see the contract text behind it.
```

## Scope
1. **Pure display helpers in `table.py`.** Keep `COLUMNS` and `deliverable_rows` unchanged. Replace `display_rows`/`DISPLAY_HEADERS` (and the old `clause_label` in `ui.py`) with these:
   - `clause_label(section)`: `"Schedule 1, 2(a)"` → `"Sch. 1 · 2(a)"`. A trailing parenthetical like `"Schedule 1, 5(c) (Super Bowl)"` becomes `"Sch. 1 · 5(c)"`, and the parenthetical is returned separately so it can be prefixed to What's owed (`"Super Bowl: …"`), unless the description already contains it (case-insensitive). Plain `"3"` stays `"3"`, since the column header already says Clause. `None` → `"–"`.
   - `qty_text(quantity, unit)`: `4, "signs"` → `"4 signs"`; `4.0` → `"4"`; quantity `None` → `""` (a unit alone isn't shown).
   - `grounded_flags(deliverables, contract_text) -> list[bool]`: per-deliverable, reusing `normalize_ws` from `evaluate.py`. Don't reimplement the normalization.
   - `status_text(details_to_be_agreed, grounded)`: `"To be agreed"`, `"Check quote"`, `"To be agreed · check quote"`, or `""`.
   - `table_rows(result, contract_text) -> list[dict]`: one dict per deliverable with `clause`, `type` (the readable category label), `whats_owed`, `qty`, `when` (frequency, or `""`), `status`, and `value` (dollars formatted with no cents, or `""`), plus the raw deliverable for the dialog.
   - `show_value_column(result) -> bool`: true only if any deliverable has a `dollar_value`. So Mets shows a Value column and the 49ers contract doesn't.
   - `summary_line(contract, grounding) -> str`: the one-line summary: term, then payments (reuse `format_term`/`format_payments`), then "N of M quotes found in the PDF", joined with " · ".
   - `type_counts(result) -> list[tuple[label, count]]`: types sorted by count descending, then by label.
2. **The table in `ui.py`.** Replace `st.dataframe` with a row layout:
   - A header row on Panel, then one row per deliverable on White with Rule dividers.
   - Build it with `st.container` + `st.columns` per row, using fixed width ratios that give What's owed most of the room. Tighten the default column and row gaps with CSS so it reads as one table, not a stack of widgets.
   - Text wraps naturally; no truncation.
   - The Clause cell is a `st.button(type="tertiary")` with the clause label; clicking it opens the dialog. Each button's key is `<prefix>_<stem-or-hash>_row_<i>`.
   - Status is styled text: "To be agreed" in Signal, semibold; "Check quote" in Ink, semibold, with a dotted underline.
   - **SECURITY: every piece of contract-derived text that goes into HTML (descriptions, quotes, conditions, file names) must go through `html.escape`.** Uploaded PDFs are untrusted. Prefer plain `st.markdown`/`st.write` without `unsafe_allow_html` where you don't need styling. Where you do (status, quote block), escape first. Add a test for this.
   - Below the table: the caption "Select a row to see the contract text behind it."
   - If a row-per-widget table is clearly too slow on 38 rows, say so in the report with timings, and fall back to the closest thing that still has wrapping text and per-row buttons. Don't silently go back to `st.dataframe`.
3. **Filter.** Use `st.pills` with "All N" plus one option per present type, labeled with counts. Single selection, defaulting to All. Selecting a type filters the rows and shows "Showing N" next to the heading.
4. **Row dialog: `@st.dialog`, width "large".** Contents:
   - Clause · type line (Muted), then What's owed as a heading.
   - A three-column facts row: Qty, When, Status. Use "Not stated" for blanks.
   - If there's a Value, add it to the facts.
   - "Contract text" in a quiet quote block: Paper background, small radius, full opacity.
   - If the quote isn't grounded, one Signal line: "This text was not found word for word in the PDF. Check it against the contract."
   - "Conditions" and "Sponsor must" lists, each shown only if non-empty.
   - Open it only from the button-click branch, so other reruns never reopen it.
5. **Summary header.** Replace the Contract/Grounding sections and the metrics:
   - An h2 with "<Sponsor> and <Rights holder>".
   - Under it, the `summary_line`, where "N of M quotes found in the PDF" links to the table section anchor.
   - Download JSON as a secondary button, right-aligned on the same row as the h2 (`st.columns`).
   - Delete the "Quotes not found" expander; the row flag replaces it.
   - **Sample tab with an eval file:** add a second Muted line, e.g. "Checked against a hand-built answer key: found 12 of 14 deliverables, no false positives." Build it from `output/eval/<stem>.json`, not hard-coded numbers.
6. **Sample tab grounding.** `grounded_flags` needs the contract text. In the sample tab, read the bundled PDF with `extract_text` (local, offline) and cache it with `st.cache_data`, keyed by path.
7. **Page chrome:**
   - Cut the top padding above the title to about 2.5rem.
   - `anchor=False` on every title and heading.
   - Subtitle max-width about 62ch.
   - Find out why the primary button ("Extract deliverables") renders near-black instead of Field green, and fix it. Report the cause.
8. **Upload tab:**
   - Remove the `st.info` empty-state box. Uploader label: "Contract PDF". Under it, the caption "Extraction uses the Claude API and takes about a minute."
   - After upload, keep the file line (name · pages · characters) and the Extract button.
   - Keep all error messages.
9. **Docs:** update `CLAUDE.md` (UI layout notes) and the README demo line if it mentions the old layout.

## Testing
- **Pure tests** for every new `table.py` function:
  - clause shortening, including the parenthetical case, plain numbers and `None`
  - `qty_text` with ints, floats and `None`
  - `status_text` for all four cases
  - `grounded_flags` with line-break-only differences counting as grounded
  - `show_value_column` true and false
  - `summary_line` with a null term and with redacted payments
  - `type_counts` ordering
- **Escaping:** a deliverable whose description or quote contains `<script>` or `<b>` renders escaped. Test whichever helper builds the HTML.
- **App tests (AppTest), updated:**
  - both tabs render
  - sample mode makes no API call (keep the fail-if-called fixture)
  - the stored upload result survives a rerun
  - the 49ers sample shows a "Check quote" status and has no Value column
  - the Mets sample has a Value column and shows the eval line
  - the pills filter the row count
  - every row has its clause button
  - If AppTest can't render `st.dialog` contents, test the dialog's content builder as a pure function instead, and say so.
- Remove tests for the old dataframe and metrics; don't leave dead ones. All tests stay offline.

## Constraints
- No new dependencies. Streamlit 1.67 as installed: check `st.pills`, `st.dialog`, `st.button(type="tertiary")` and `anchor=` against the installed version, not memory.
- Keep injected CSS in the one block in `ui.py`, each rule commented.
- `app.py` keeps only tabs, session state and API calls. Rendering lives in `ui.py`, pure logic in `table.py`.
- Phone width: rows may stack. That's acceptable, but nothing should overflow the page horizontally.

## Acceptance criteria
1. `pytest` passes.
2. `streamlit run app.py`: the sample tab loads all three contracts with no API call; 49ers shows 38 rows, one "Check quote", and no Value column; Mets shows a Value column with $50,000 and the eval line.
3. Clicking a row's clause opens the dialog with that row's quote, and closing it doesn't reopen it on the next interaction.
4. Everything staged, no commits. `Claude outputs/` is not staged.

## Report back with
- Changed files and confirmation that changes are staged, not committed.
- `pytest` output.
- How long the 49ers table takes to render.
- What made the primary button dark, and the fix.
- Anything Streamlit 1.67 couldn't do from this brief, and what you did instead.
- A click-through for me to check visually.

STAGE all changes, DO NOT COMMIT.
