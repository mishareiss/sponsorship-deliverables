"""Command line entry point: python -m deliverables.cli <pdf> | --all"""

import argparse
import json
from collections import Counter
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from deliverables.extract import default_model, extract_contract
from deliverables.pdf_text import extract_text

CONTRACTS_DIR = Path("data/contracts")
OUTPUT_DIR = Path("output")


def print_summary(name: str, result: dict) -> None:
    deliverables = result["deliverables"]
    by_category = Counter(d["category"] for d in deliverables)
    to_be_agreed = sum(1 for d in deliverables if d["details_to_be_agreed"])

    print(f"\n{name}")
    print(f"  deliverables: {len(deliverables)}")
    for category, count in by_category.most_common():
        print(f"    {category}: {count}")
    print(f"  details_to_be_agreed: {to_be_agreed}")


def run_one(pdf_path: Path, client: anthropic.Anthropic, model: str) -> None:
    text = extract_text(pdf_path)
    result = extract_contract(text, client, model)

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / f"{pdf_path.stem}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print_summary(pdf_path.name, result)
    print(f"  wrote {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract sponsorship deliverables from contract PDFs.")
    parser.add_argument("pdf", nargs="?", type=Path, help="Path to a contract PDF")
    parser.add_argument("--all", action="store_true", help=f"Run every PDF in {CONTRACTS_DIR}/")
    args = parser.parse_args()

    if args.all:
        pdfs = sorted(CONTRACTS_DIR.glob("*.pdf"))
    elif args.pdf:
        pdfs = [args.pdf]
    else:
        parser.error("give a PDF path or --all")

    load_dotenv()
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    model = default_model()
    print(f"model: {model}")

    for pdf_path in pdfs:
        run_one(pdf_path, client, model)


if __name__ == "__main__":
    main()
