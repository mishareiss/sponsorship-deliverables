# Task 6 — Full-row click, drop the summary link, and a public static demo on GitHub Pages

## Context
Two parts.

**Part A** makes two small fixes to the Streamlit app:
- The whole table row should be clickable, not just the clause label.
- The "N of M quotes found in the PDF" link only scrolls a couple of inches, so make it plain text.

**Part B** adds a public demo. The Streamlit app stays as it is, including upload and Re-run, for running locally. The public version needs to:
- run on GitHub Pages, so it's static HTML with no server and no API key anywhere
- show only the pre-extracted sample contracts from `output/`
- have no way to call the Claude API at all

It should look and behave like the redesigned Streamlit results page: same palette, fonts, summary header, pills, six-column table and row dialog.

Read first: `CLAUDE.md`, `app.py`, `src/deliverables/ui.py`, `src/deliverables/table.py`, `src/deliverables/evaluate.py`, `src/deliverables/pdf_text.py`, `.streamlit/config.toml`, `output/*.json`, `output/eval/*.json`, and `docs/prompts/05-ui-redesign.md` for the design reference.

IMPORTANT: STAGE all changes (`git add -A`) but DO NOT COMMIT.

## Part A — Streamlit fixes
1. **Full-row click.** Clicking anywhere on a row opens that row's dialog.
   - Use the stretched-button pattern: give each row container a key (so it gets a `st-key-…` class), make it `position: relative`, and give the clause button's `::after` pseudo-element `position: absolute; inset: 0`, so the button's hit area covers the row. Add a hover background on the row (`#EEF2EF`) and a visible focus ring.
   - Check that no ancestor between the button and the row container is positioned and breaks this. If Streamlit 1.67's DOM makes it impossible, say so, and propose the closest alternative instead of shipping something half-working.
   - Keyboard: Tab still lands on one button per row, and Enter opens the dialog.
2. **Summary link.** Make "N of M quotes found in the PDF" plain text, and remove the anchor `div` that existed only for that link.

## Part B — Static public demo
1. **Build script: `src/deliverables/site.py`.** `python -m deliverables.site` writes `docs/index.html`, so GitHub Pages can serve it from `main` → `/docs`.
   - For every `output/<stem>.json` with a matching `data/contracts/<stem>.pdf`, compute in Python:
     - the summary line
     - the eval line, if `output/eval/<stem>.json` exists
     - the table rows via the existing `table.py` helpers (`table_rows`, `type_counts`, `show_value_column`, `summary_line`, `clause_label`, etc.)
     - per-row grounding, from `extract_text` on the local PDF

     Reuse these; don't reimplement any formatting in JavaScript. The page should show exactly what the Streamlit app shows.
   - Embed the computed data as JSON in a `<script type="application/json" id="data">` tag. **Escape it for that context**: replace `<` with `<` (at minimum `</`), plus U+2028 and U+2029, so contract text can't close the script tag.
   - Copy each source PDF into `docs/contracts/<stem>.pdf`, so the page can link "Open the contract (PDF)". They're public SEC filings.
   - Add an empty `docs/.nojekyll`.
   - The output must be deterministic: same inputs, byte-identical output. No timestamps.
2. **The page.** One self-contained `docs/index.html`, with inline CSS and vanilla JS. No frameworks, no build tools, no external scripts. Google Fonts is the only external request.
   - **Header:** the same title and subtitle as the app. Then one Muted line: "These contracts were extracted ahead of time with Claude. The full app also extracts uploaded contracts; it runs locally from the repo." Link "the repo" to https://github.com/mishareiss/sponsorship-deliverables.
   - **Contract switcher:** a row of buttons acting as tabs, labeled by parties and year, e.g. "Mets × AlphaTrade · 2007", "49ers × Violin Memory · 2012", "Vanderbilt × Learfield · 2026". Build the labels from the data, plus a small hand-written label map in `site.py` if the party names are too long. Default to the Mets contract, since it has the eval line.
   - **Per-contract note** (optional, from a small dict in `site.py`). For Vanderbilt: "The benefits list (Exhibit A) is blank in the public filing, so only general items appear." Show it as a Muted line under the summary.
   - **Summary header:** the parties heading, the summary line, the eval line where it exists, and an "Open the contract (PDF)" link. No Download JSON and no Re-run.
   - **Pills, table and dialog:** same behavior as the app.
     - Pills: All plus the present types, with counts; they filter the table; "Showing N".
     - Table: six columns, plus Value only when the contract has dollar values.
     - Rows: each row is a real `<button>` (or contains one stretched over it), so the whole row is clickable and keyboard accessible.
     - Dialog: use `<dialog>` with `showModal()`. Escape and a Close button both close it, and focus returns to the row.
   - **Security:** build all DOM from data with `textContent` / `createElement`. Never put data into `innerHTML`. Add a test that the built HTML contains no `innerHTML` assignment that uses data (a simple grep-style test is fine).
   - **Responsive:** at 390px wide, rows stack into readable cards and nothing scrolls sideways.
   - **Accessibility:** contrast as in the app, visible focus rings, `aria-pressed` on pills and the contract switcher, and a `lang` attribute.
3. **Pages setup.** Don't enable Pages yourself. In the report, give me the exact steps: either Settings → Pages → Deploy from a branch → `main` / `/docs`, or the equivalent `gh api` command for `mishareiss/sponsorship-deliverables`. Also give me the resulting URL.
4. **Docs.**
   - README: add a "Live demo" link near the top (the Pages URL), and say the live demo shows pre-extracted results only.
   - CLAUDE.md: add the build command and the rule "rebuild `docs/index.html` after changing `output/` or the table helpers".

## Testing
- **Part A:** an AppTest test that the summary line has no link. Keep the existing dialog tests green. If you can check the row-stretch CSS in a test, do; otherwise say how you verified it by hand.
- **Part B:** build into a temp dir in tests, not `docs/`.
  - The build contains all three contracts, with 38 rows for 49ers and the Mets eval line.
  - No API key, `anthropic` import or `.env` content appears in the output. Assert the string `ANTHROPIC` isn't in the built HTML.
  - A deliverable containing `</script><script>alert(1)</script>` is embedded escaped and can't break out.
  - The build is deterministic: build twice and compare bytes.
  - PDFs are copied.
  - **Staleness check:** a test that `docs/index.html` in the repo equals a fresh build. If someone changes `output/` and forgets to rebuild, the tests fail.
- All existing tests stay green and offline. `site.py` must not import `anthropic` or anything that does.

## Constraints
- No new dependencies.
- The public page has no code path that calls an API. It's static files only.
- `docs/prompts/` will also be served by Pages. That's fine, but don't link to it from the page.
- Keep `site.py` readable. The page's HTML/CSS/JS template can live in `src/deliverables/site_template.html` and be read by `site.py`.

## Acceptance criteria
1. `pytest` passes.
2. `python -m deliverables.site` writes `docs/index.html`, `docs/.nojekyll` and `docs/contracts/*.pdf`. Opening `docs/index.html` straight from disk in a browser works: switching contracts, pills, row click, dialog, and Escape to close.
3. In the Streamlit app, clicking anywhere on a row opens the dialog, and the summary line has no link.
4. Everything staged, no commits.

## Report back with
- Changed and new files, and confirmation that changes are staged, not committed.
- `pytest` output.
- The size of `docs/index.html`.
- The GitHub Pages steps and the final URL.
- How full-row click works in Streamlit, and anything that didn't work.
- A click-through for both the app and the static page.

STAGE all changes, DO NOT COMMIT.
