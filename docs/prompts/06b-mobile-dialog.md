# Task 6b — Static page: lock background scroll while the row dialog is open (mobile)

## Context
On the live GitHub Pages demo on a phone, opening a row's dialog and then swiping scrolls the page behind it while the dialog stays put. `<dialog>` with `showModal()` doesn't stop the page underneath from scrolling, and iOS Safari ignores `overflow: hidden` on the body alone. The dialog should behave like a proper sheet: the page behind it is frozen, and swipes scroll the dialog's own content.

Read first: `src/deliverables/site_template.html`, `src/deliverables/site.py`, `tests/test_site.py`, `CLAUDE.md`.

IMPORTANT: STAGE all changes (`git add -A`) but DO NOT COMMIT.

## Scope
1. **Freeze the page while the dialog is open.**
   - On open: save `window.scrollY`, then set the body to `position: fixed; top: -<scrollY>px; left: 0; right: 0; width: 100%` and `overflow: hidden` on `html`. This is the reliable approach on iOS Safari.
   - On every close path (Close button, Escape, a backdrop tap if supported, and the dialog's `close` event as the single place that restores), undo those styles and `window.scrollTo(0, savedY)`. The page must not jump.
   - Restore exactly once even if several close paths fire.
2. **Make the dialog scroll by itself.**
   - Constrain it to the viewport (`max-height: calc(100dvh - 32px)`, with a `100vh` fallback), and give the content `overflow-y: auto; overscroll-behavior: contain`, so long contract text scrolls inside the dialog and never chains to the page.
   - Keep the header with the Close button visible while the content scrolls (sticky header inside the dialog).
3. **On phones (≤ 640px), show the dialog as a bottom sheet.**
   - Full width, anchored to the bottom, rounded top corners, up to about 90dvh tall.
   - Respect `env(safe-area-inset-bottom)` padding.
   - Desktop stays a centered dialog.
   - Keep it simple: no drag-to-dismiss gesture.
4. **Tapping the backdrop closes the dialog.** A click whose target is the dialog element itself, outside its inner content box, counts as a backdrop tap.
5. **Keep everything else unchanged:** focus returns to the row on close, Escape works, and there's no `innerHTML`. The CSP is still pinned by hash: rebuild with `python -m deliverables.site` so the hash and `docs/index.html` match. The staleness test must pass.

## Testing
- Existing site tests stay green, including the staleness, determinism and no-markup-sink tests.
- Add a simple test that the built HTML contains the scroll-lock code path: e.g. that the close handler restores scroll, and that the dialog has `overscroll-behavior: contain`. A string check is fine.
- **Manual check, which you must report:** in headless Chrome with mobile emulation (390×844, touch enabled):
  - open a dialog, then dispatch a scroll or wheel on the page and confirm `window.scrollY` doesn't change
  - close it and confirm the page is back at the same scroll position
  - confirm a long quote scrolls inside the dialog

## Acceptance criteria
1. `pytest` passes.
2. `docs/index.html` is rebuilt and matches a fresh build.
3. Everything staged, no commits.

## Report back with
Changed files, staged confirmation, `pytest` output, the results of the manual check, and anything that behaves differently on iOS Safari that you couldn't test (say so plainly).

STAGE all changes, DO NOT COMMIT.
