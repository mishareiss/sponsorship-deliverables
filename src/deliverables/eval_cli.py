"""Command line entry point: python -m deliverables.eval_cli <stem> | --all

Loads output/<stem>.json (prediction), gold/<stem>.json and the text of
data/contracts/<stem>.pdf, prints a report and writes output/eval/<stem>.json.
"""

import argparse
import json
from pathlib import Path

from deliverables.evaluate import evaluate
from deliverables.pdf_text import extract_text

CONTRACTS_DIR = Path("data/contracts")
GOLD_DIR = Path("gold")
OUTPUT_DIR = Path("output")
EVAL_DIR = OUTPUT_DIR / "eval"
MAX_VALUE_WIDTH = 70  # printed values are truncated; the JSON file keeps them in full


def pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0%}"


def short(value: object) -> str:
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= MAX_VALUE_WIDTH else text[: MAX_VALUE_WIDTH - 3] + "..."


def print_mismatches(title: str, rows: list[dict]) -> None:
    print(f"\n{title} ({len(rows)})")
    if not rows:
        print("  none")
    for row in rows:
        print(f"  [{row['section']}] {row['field']}: {short(row['pred'])} -> {short(row['gold'])}")


def print_report(stem: str, result: dict) -> None:
    d = result["deliverables"]
    print(f"\n=== {stem} ===")
    print("\nDeliverables")
    print(f"  gold {d['gold']}, pred {d['pred']}, matched {d['matched']}")
    print(f"  recall    {d['matched']}/{d['gold']} = {pct(d['recall'])}")
    print(f"  precision {d['matched']}/{d['pred']} = {pct(d['precision'])}")
    for item in d["missed"]:
        print(f"  missed [{item['section']}] {item['category']}: {short(item['description'])}")
    for item in d["extra"]:
        print(f"  extra  [{item['section']}] {item['category']}: {short(item['description'])}")

    print("\nField accuracy (matched pairs)")
    for field, acc in result["field_accuracy"].items():
        print(f"  {field:<24} {acc['correct']:>3}/{acc['total']:<3} {pct(acc['accuracy']):>5}")

    c = result["contract"]
    print(f"\nContract block: {c['passed']}/{c['total']} checks pass")
    for m in c["mismatches"]:
        print(f"  {m['field']}: {short(m['pred'])} -> {short(m['gold'])}")

    g = result["grounding"]
    print(f"\nGrounding: {g['grounded']}/{g['total']} quotes found verbatim = {pct(g['rate'])}")
    for item in g["ungrounded"]:
        print(f"  not found [{item['section']}]: {short(item['source_quote'])}")

    print_mismatches("Mismatches, scored (pred -> gold)", result["mismatches"])
    print_mismatches("Differences, unscored free text, for human review", result["unscored_differences"])


def run_one(stem: str) -> None:
    pred = json.loads((OUTPUT_DIR / f"{stem}.json").read_text(encoding="utf-8"))
    gold = json.loads((GOLD_DIR / f"{stem}.json").read_text(encoding="utf-8"))
    contract_text = extract_text(CONTRACTS_DIR / f"{stem}.pdf")

    result = evaluate(pred, gold, contract_text)
    print_report(stem, result)

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    out_path = EVAL_DIR / f"{stem}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Score extraction output against hand-checked gold files.")
    parser.add_argument("stem", nargs="?", help="Contract name without extension, e.g. mets-alphatrade-2007")
    parser.add_argument("--all", action="store_true", help=f"Run every stem that has a file in {GOLD_DIR}/")
    args = parser.parse_args()

    if args.all:
        stems = sorted(p.stem for p in GOLD_DIR.glob("*.json"))
    elif args.stem:
        stems = [args.stem]
    else:
        parser.error("give a stem or --all")

    for stem in stems:
        run_one(stem)


if __name__ == "__main__":
    main()
