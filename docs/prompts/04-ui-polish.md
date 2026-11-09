# Task 4 — Demo UI polish: clean, professional, on-subject

## Context
`app.py` (Streamlit 1.67 in `.venv`) works but looks like default Streamlit: a stock theme, raw field names as column headers (`scoreboard_led`, `details_to_be_agreed`), a wall of expanders under the table, and "Term: ? to ?" when the contract doesn't state dates. This task is visual and copy polish only. The behavior from Task 3c must not change: tabs, the session-state upload logic, and no API calls in the sample tab except Re-run.

**Who looks at this:** a sports partnership or activation manager, and the engineers interviewing me for a Forward Deployed Engineer role. **What it's for:** show at a glance that a contract became a trackable list of what the team owes the sponsor, and make every row easy to check against the contract text.

Read first: `app.py`, `src/deliverables/table.py`, `tests/test_app.py`, `tests/test_table.py`, `CLAUDE.md`.

IMPORTANT: STAGE all changes (`git add -A`) but DO NOT COMMIT.

## Design direction
The idea is a stadium operations sheet: calm, precise, and easy to scan, with the type borrowing from stadium wayfinding signage. Spend the boldness in one place, the deliverables table. Keep everything else quiet.

- **Type:** one family, Barlow (Google Fonts). Barlow Semi Condensed for the title and section headings, regular Barlow for body text and the table. Numbers in the table should line up (tabular figures, if Barlow supports them in this setup).
- **Palette:**

  | Name | Hex | Use |
  |---|---|---|
  | Paper | `#F6F7F5` | background |
  | Panel | `#E9EEEA` | secondary background |
  | Ink | `#1C2B2A` | text |
  | Field | `#1F6B47` | primary buttons, active tab, links |
  | Signal | `#A8661A` | **only** to flag items still to be agreed |
  | Rule | `#CFD8D2` | borders |

  Don't add gradients or extra accent colors.
- **Avoid these generic looks:** all-caps eyebrow labels, cards with soft shadows around everything, emoji, a monospace font for labels, "→" on buttons, and decorative dividers.
- **Theme first.** Set the theme in `.streamlit/config.toml` (colors, fonts via Streamlit's font config, `baseRadius` small, `toolbarMode = "minimal"`). Use injected CSS only where config can't reach, keep it in one small block in one place, and comment each rule.

## Scope
1. **`.streamlit/config.toml`:** the theme above. Check Streamlit 1.67's theming options (including custom fonts) in the installed version or its docs rather than guessing key names.
2. **Header:** keep the title "Sponsorship deliverables" and add one plain line under it: "Turn a sponsorship contract into a list of everything the team owes the sponsor, with the contract text behind each item." Constrain the main content to a comfortable max width on wide screens.
3. **Contract summary:** replace the markdown block with a compact two-column summary (labels on the left, values on the right). Show "Sponsor ↔ Rights holder," seasons, term, and payments. Null terms show "Not stated in contract," not "?". Long `seasons` strings (like the 49ers one) must wrap cleanly.
4. **Eval and grounding:** keep `st.metric`, but give each a plain-English caption, e.g. "Found 12 of 14 deliverables in the hand-checked answer key." Shorten the grounding explanation to one sentence.
5. **Deliverables table (the main element):**
   - **Readable columns.** Add a pure display layer in `table.py` (keep `deliverable_rows` and `COLUMNS` as they are, since the tests and the eval depend on them). Map field names to user-facing headers: Clause, Type, What's owed, Qty, Unit, When, Value, To be agreed, Conditions, Sponsor must. Map category codes to labels, e.g. `scoreboard_led` → "Scoreboard / LED", `pa_announcement` → "PA announcement", `marks_designation` → "Marks & designation".
   - **Column formatting.** Use `st.column_config`: Value as dollars with no cents, To be agreed as a read-only checkbox, sensible widths, and "What's owed" as the widest column.
   - **Type filter.** Add `st.pills`, or a multiselect if pills don't fit, above the table so the 38-row 49ers contract can be narrowed.
   - **Row detail.** Replace the wall of expanders with row selection (`on_select="rerun"`, `selection_mode="single-row"`). Selecting a row shows a detail panel under the table: the source quote in a quiet indented block, then Conditions and Sponsor obligations as short lists, and the To be agreed status in Signal color when it's true. When nothing is selected, show one line: "Select a row to see the contract text behind it."
   - Widget keys must keep their `upload_` and `sample_` prefixes.
6. **Upload tab copy:**
   - Empty state: "Upload a sponsorship contract PDF. Extraction uses the Claude API and takes about a minute."
   - After upload: a quiet file line (name · pages · characters is fine here), then the primary button "Extract deliverables."
   - Keep all error messages. Make them say what happened and what to do, with no apologies.
7. **Sample tab:** rename the tab to "Try a sample contract." Make Re-run a secondary button with its warning ("Calls the Claude API and overwrites the saved output") as help text or a caption, not a prominent element.
8. **Download JSON:** a secondary button, placed next to the result header rather than above everything.

## Testing
- Add pure tests for the new display layer in `table.py`: header mapping, category labels (including an unknown category falling back to a readable label), and column order.
- Update `tests/test_app.py` for the renamed tab, the selection-based detail panel, and anything else that moved. The existing guarantees stay: both tabs render, sample mode makes no API call, and the stored upload result survives a rerun.
- All tests stay green and offline.

## Constraints
- No new dependencies. Fonts load through Streamlit's theme config or a Google Fonts link.
- No behavior changes beyond what's listed above.
- Keep `app.py` readable. If rendering grows, move it into a small `ui.py` helper module.
- Accessible: text contrast at least WCAG AA on Paper and Panel. Don't rely on Signal color alone (pair it with the words "To be agreed").

## Acceptance criteria
1. `pytest` passes.
2. `streamlit run app.py` shows the new theme. Check in both light and dark system settings that nothing becomes unreadable; if the theme forces light mode, that's fine, but say so.
3. Everything staged, no commits.

## Report back with
- Changed files and confirmation that changes are staged, not committed.
- `pytest` output.
- The final `config.toml`, and every injected CSS rule with its reason.
- Anything in this brief that Streamlit 1.67 can't do, and what you did instead.
- A short click-through for me to check visually.

STAGE all changes, DO NOT COMMIT.
