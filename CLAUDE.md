# CLAUDE.md

## Purpose
A portfolio project: an AI system that helps sports partnership teams track the deliverables they owe sponsors.
Step 1 (this code) reads a sponsorship contract PDF and uses Claude structured outputs (`output_config.format`
with a JSON schema) to extract the contract terms and every deliverable into schema-valid JSON.

## Layout
- `src/deliverables/schema.py`: `EXTRACTION_SCHEMA`, the JSON schema the output must match (from `flagship/extraction_schema.py`, plus `additionalProperties: false`)
- `src/deliverables/pdf_text.py`: PDF to text with pdfplumber; strips browser print headers/footers
- `src/deliverables/extract.py`: calls Claude with the schema as a structured output, checks the stop reason, parses the JSON, re-validates with jsonschema
- `src/deliverables/cli.py`: `python -m deliverables.cli`, writes `output/<pdf-stem>.json`
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
```
Needs `.env` in the repo root with `ANTHROPIC_API_KEY` (and optionally `ANTHROPIC_MODEL`). See `.env.example`.

## Rules
- Stage changes (`git add -A`), don't commit. The owner reviews and commits.
- Tests are fully offline. Never call the real API in tests; use a fake client.
- Don't change schema fields in `schema.py` without asking.
- Don't switch back to forced `tool_choice`: `claude-sonnet-5-5` rejects it with a 400.
- Never print or log the API key.

## Gotcha: iCloud hides venv files
This repo lives under `~/Documents`, which iCloud syncs. iCloud sets the macOS "hidden" flag on files inside `.venv`,
and Python 3.13 skips hidden `.pth` files, so `import deliverables` fails outside pytest. Tests are covered by
`pythonpath = ["src"]` in `pyproject.toml`. If the CLI says `No module named 'deliverables'`, run:
`chflags nohidden .venv/lib/python3.*/site-packages/*.pth`
