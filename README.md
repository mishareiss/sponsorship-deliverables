# Sponsorship Deliverables Tracker

## Problem
Sports partnership teams sign contracts that promise sponsors a long list of deliverables: signs, LED messages,
PA announcements, tickets, suites, broadcast inventory. Those promises live in PDFs, so tracking whether each one
was delivered is manual and error-prone. This project turns a contract into structured, checkable data: the PDF text goes to Claude with a JSON schema
(structured outputs), and the result is a list of deliverables, each with a verbatim quote from the contract.

## How to run
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # then fill in ANTHROPIC_API_KEY
pytest
python -m deliverables.cli data/contracts/mets-alphatrade-2007.pdf
```
Output goes to `output/<pdf-stem>.json`.

## Status
- [x] Step 1: extract contract terms and deliverables from a PDF into schema-valid JSON
- [ ] Eval against hand-checked gold files
- [ ] Reconcile against proof-of-performance data
- [ ] Draft partner recaps
