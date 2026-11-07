# Task 2 — Eval: score extraction output against a hand-checked gold file

## Context
Task 1 built `extract_contract` (structured outputs → JSON) and the CLI that writes `output/<stem>.json`. I've now hand-checked the Mets extraction and saved the corrected version as `gold/mets-alphatrade-2007.json`: 14 deliverables against the model's 12, because clause 5 was split into three. This task builds an eval that scores a prediction file against its gold file, so extraction quality is a number instead of a feeling.

Read first: `CLAUDE.md`, `src/deliverables/schema.py`, `src/deliverables/pdf_text.py`, `output/mets-alphatrade-2007.json`, `gold/mets-alphatrade-2007.json`.

Known model errors in the gold set, for context:
- Clause 5: three independent deliverables (sweepstakes, banners, email) were merged into one.
- Clauses 5, 9 and 10: the "during each of the 2007 and 2008 seasons" preamble was missed in `frequency`.
- Clause 6: an optional right was listed as a sponsor obligation.
- Clause 12: wrong category (`digital` → `other`), and the sponsor's half of a mutual obligation was missed.

IMPORTANT: STAGE all changes (`git add -A`) but DO NOT COMMIT.

## Scope
1. **`src/deliverables/evaluate.py`** with `evaluate(pred: dict, gold: dict, contract_text: str) -> dict`. It's pure and makes no API calls.
2. **Deliverable matching:**
   - Only pair deliverables that share the same `section`.
   - Within a section, score each (pred, gold) pair by `source_quote` similarity after whitespace normalization (collapse all whitespace, strip). Use `difflib.SequenceMatcher` ratio, and give a full score when one quote contains the other.
   - Pair greedily, highest score first, one-to-one.
   - Unmatched gold = missed. Unmatched pred = extra.
   - Keep this simple and explainable.
3. **Metrics:**
   - **Deliverables:** gold count, pred count, matched, recall (matched/gold), precision (matched/pred).
   - **Field accuracy** over matched pairs, for these strict fields:
     - `category`
     - `quantity`
     - `dollar_value`
     - `details_to_be_agreed`
     - `has_sponsor_obligations`: whether the list is non-empty
     - `has_conditions`: whether the list is non-empty

     Compare numbers numerically and treat null as its own value. Report each field's accuracy as correct/total plus a percentage.
   - **Not scored yet (free text):** `description`, `unit`, `frequency`, the text of the conditions and obligations, `proof_of_performance`. Include them in the mismatch list for human review, labeled "unscored." Note: frequency is where the per-season errors live, so it's a known blind spot in v1.
   - **Contract block:**
     - `sponsor` and `rights_holder`: case- and whitespace-insensitive equality
     - `seasons`: set equality
     - `term_start` / `term_end`: equality
     - `payments`: count match, and per-payment (in order) `due_date` and `redacted` match
   - **Grounding:** the share of predicted `source_quote`s that appear verbatim in `contract_text` after whitespace normalization on both sides.
4. **`src/deliverables/eval_cli.py`:** `python -m deliverables.eval_cli <stem>` loads `output/<stem>.json`, `gold/<stem>.json` and the text of `data/contracts/<stem>.pdf` (reuse `extract_text`; don't reimplement it). `--all` runs every stem that has a gold file. It prints a readable report: the deliverables summary, the field accuracy table, contract-block results, grounding, then a mismatch list (section, field, predicted → gold) with unscored fields shown separately. It also writes the full result as JSON to `output/eval/<stem>.json`.
5. **Docs:** update `CLAUDE.md` (eval command, what's scored vs not) and the README stub (one line on how quality is measured).

## Testing
Offline and deterministic. Use small hand-built pred/gold dicts in the tests, not the real files. Cases:
- Identical pred and gold give 100% recall, precision and field accuracy.
- Split case: gold has 3 deliverables in section "5" and pred has 1 whose quote contains all three gold quotes. The result is 1 matched, 2 missed, recall < 1.
- An extra pred deliverable lowers precision.
- A wrong `category` on a matched pair shows up in the mismatch list and lowers category accuracy.
- `quantity` null vs 4 counts as a mismatch, and 4 vs 4.0 counts as a match.
- `has_sponsor_obligations` treats `[]` vs a non-empty list as a mismatch.
- Grounding: a quote whose only difference from the contract text is line breaks counts as grounded, and an invented quote doesn't.
- Deliverables in different sections never get paired, even if their quotes are similar.
- Contract block: a payment with a different `redacted` flag is reported.

## Constraints
- Standard library plus existing dependencies only. No new packages, and no API calls in the eval.
- Small, readable functions. I'll explain the matching logic in an interview.

## Acceptance criteria
1. `pytest` passes, with the old tests still green.
2. `python -m deliverables.eval_cli mets-alphatrade-2007` runs and writes `output/eval/mets-alphatrade-2007.json`.
3. Sanity check against what I expect: gold 14, pred 12, precision 100%, recall about 12/14, and mismatches including clause 12's `category` and `has_sponsor_obligations` for clauses 6 and 12. If the numbers differ, explain why rather than tuning the matcher until they match.
4. Everything staged, no commits.

## Report back with
- New and changed files.
- Confirmation that changes are staged, not committed.
- `pytest` output.
- The full printed eval report for Mets.
- Which gold deliverable the model's single clause-5 item was matched to, and why.
- Any deviations from this brief.
- A 4–6 sentence plain-English explanation of how the matching and scoring work, for an interview.

STAGE all changes, DO NOT COMMIT.
