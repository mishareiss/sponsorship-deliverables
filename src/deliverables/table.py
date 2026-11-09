"""Turn an extraction result into flat table rows for display. Pure: no I/O.

deliverable_rows/COLUMNS keep raw field names (tests and the eval rely on them). The display layer
below turns a result into the text the demo shows: clause labels, quantities, status, the summary line.
No HTML here; deliverables.ui escapes and styles it.
"""

import re
from datetime import date

from deliverables.evaluate import normalize_ws

COLUMNS = [
    "section",
    "category",
    "description",
    "quantity",
    "unit",
    "frequency",
    "dollar_value",
    "details_to_be_agreed",
    "sponsor_obligations",
    "conditions",
]

# List fields are shown as counts; everything else is copied as is (None stays None).
COUNT_FIELDS = {"sponsor_obligations", "conditions"}


def deliverable_rows(result: dict) -> list[dict]:
    """One dict per deliverable, keys in COLUMNS order."""
    rows = []
    for d in result.get("deliverables", []):
        row = {}
        for col in COLUMNS:
            value = d.get(col)
            row[col] = len(value or []) if col in COUNT_FIELDS else value
        rows.append(row)
    return rows


# ---------- display layer for the demo (pure; COLUMNS and deliverable_rows stay as they are) ----------

CATEGORY_LABELS = {
    "signage": "Signage",
    "scoreboard_led": "Scoreboard / LED",
    "pa_announcement": "PA announcement",
    "broadcast": "Broadcast",
    "digital": "Digital",
    "print": "Print",
    "tickets": "Tickets",
    "hospitality": "Hospitality",
    "activation": "Activation",
    "marks_designation": "Marks & designation",
    "exclusivity": "Exclusivity",
    "other": "Other",
}

NOT_STATED = "Not stated in contract"


def category_label(code: str | None) -> str:
    """Readable label for a category code; unknown codes become 'Some code' from 'some_code'."""
    if not code:
        return CATEGORY_LABELS["other"]
    return CATEGORY_LABELS.get(code) or code.replace("_", " ").strip().capitalize()


def format_date(value: str | None) -> str | None:
    """'2012-06-13' -> 'June 13, 2012'. Non-ISO strings come back unchanged."""
    if not value:
        return None
    try:
        d = date.fromisoformat(value)
    except ValueError:
        return value
    return f"{d:%B} {d.day}, {d.year}"


def format_term(start: str | None, end: str | None) -> str:
    start, end = format_date(start), format_date(end)
    if start and end:
        return f"{start} to {end}"
    if start:
        return f"Starts {start}; end date not stated in contract"
    if end:
        return f"Ends {end}; start date not stated in contract"
    return NOT_STATED


def format_payments(payments: list[dict]) -> str:
    if not payments:
        return NOT_STATED
    count = f"{len(payments)} payment{'s' if len(payments) != 1 else ''}"
    redacted = sum(1 for p in payments if p.get("redacted"))
    amounts = [p["amount"] for p in payments if p.get("amount") is not None]
    if not amounts:
        return f"{count}, amounts redacted" if redacted == len(payments) else f"{count}, amounts not stated"
    total = f"${sum(amounts):,.0f}"
    if len(amounts) == len(payments):
        return f"{count} totaling {total}"
    missing = f"{redacted} redacted" if redacted else f"{len(payments) - len(amounts)} not stated"
    return f"{count}: {total} stated, {missing}"


# Trailing parenthetical on a section, e.g. "Schedule 1, 5(c) (Super Bowl)" -> "Super Bowl".
# It must follow a space, so "4(a)(ii)" keeps its sub-clause numbering.
NOTE_RE = re.compile(r"^(?P<section>.*\S)\s+\((?P<note>[^()]*)\)$")
# "Schedule 1, 2(a)" -> ("1", "2(a)")
SCHEDULE_RE = re.compile(r"^Schedule\s+(?P<schedule>\S+?),?\s+(?P<clause>.+)$", re.IGNORECASE)

TO_BE_AGREED = "To be agreed"
CHECK_QUOTE = "Check quote"


def clause_parts(section: str | None) -> tuple[str, str | None]:
    """(short clause label, trailing note or None).

    "Schedule 1, 2(a)" -> ("Sch. 1 · 2(a)", None); "Schedule 1, 5(c) (Super Bowl)" -> ("Sch. 1 · 5(c)",
    "Super Bowl"); "3" -> ("3", None); None -> ("–", None).
    """
    if not section or not section.strip():
        return "–", None
    section, note = section.strip(), None
    m = NOTE_RE.match(section)
    if m and any(ch.isdigit() for ch in m["section"]):
        section, note = m["section"], m["note"].strip() or None
    m = SCHEDULE_RE.match(section)
    if m:
        section = f"Sch. {m['schedule']} · {m['clause']}"
    return section, note


def clause_label(section: str | None) -> str:
    """Short clause label for the Clause column; see clause_parts."""
    return clause_parts(section)[0]


def whats_owed(description: str, note: str | None) -> str:
    """The description, prefixed with the clause note ("Super Bowl: ...") unless it already mentions it."""
    if not note or note.casefold() in description.casefold():
        return description
    return f"{note}: {description}"


def format_number(value: float | int) -> str:
    """4 -> "4", 4.0 -> "4", 2.5 -> "2.5", 1200 -> "1,200"."""
    return f"{value:,.0f}" if float(value).is_integer() else f"{value:,}"


def qty_text(quantity: float | int | None, unit: str | None) -> str:
    """4, "signs" -> "4 signs"; quantity None -> "" (a unit alone isn't shown)."""
    if quantity is None:
        return ""
    return f"{format_number(quantity)} {unit}".strip() if unit else format_number(quantity)


def money(value: float | int | None) -> str:
    """50000 -> "$50,000" (no cents); None -> ""."""
    return "" if value is None else f"${value:,.0f}"


def grounded_flags(deliverables: list[dict], contract_text: str) -> list[bool]:
    """Per deliverable: is its source_quote in the contract text? Same rule as evaluate_grounding."""
    text = normalize_ws(contract_text)
    return [normalize_ws(d["source_quote"]) in text for d in deliverables]


def status_pieces(status: str) -> list[tuple[str, str]]:
    """Split a status into (style, text) pieces, shown joined by " · ".

    "To be agreed · check quote" -> [("tba", "To be agreed"), ("check", "check quote")]; any other
    non-empty text is one plain piece ("", text); "" -> [].
    """
    if not status:
        return []
    pieces = []
    if status.startswith(TO_BE_AGREED):
        pieces.append(("tba", TO_BE_AGREED))
    if status.lower().endswith(CHECK_QUOTE.lower()):
        pieces.append(("check", CHECK_QUOTE.lower() if pieces else CHECK_QUOTE))
    return pieces or [("", status)]


def status_text(details_to_be_agreed: bool, grounded: bool) -> str:
    if details_to_be_agreed and not grounded:
        return f"{TO_BE_AGREED} · {CHECK_QUOTE.lower()}"
    if details_to_be_agreed:
        return TO_BE_AGREED
    return "" if grounded else CHECK_QUOTE


def table_rows(result: dict, contract_text: str) -> list[dict]:
    """One display row per deliverable, in order. "deliverable" holds the raw item for the dialog."""
    deliverables = result.get("deliverables", [])
    rows = []
    for d, grounded in zip(deliverables, grounded_flags(deliverables, contract_text)):
        clause, note = clause_parts(d.get("section"))
        rows.append({
            "clause": clause,
            "type": category_label(d.get("category")),
            "whats_owed": whats_owed(d.get("description") or "", note),
            "qty": qty_text(d.get("quantity"), d.get("unit")),
            "when": d.get("frequency") or "",
            "status": status_text(bool(d.get("details_to_be_agreed")), grounded),
            "value": money(d.get("dollar_value")),
            "grounded": grounded,
            "deliverable": d,
        })
    return rows


def show_value_column(result: dict) -> bool:
    """True only if some deliverable states a dollar value."""
    return any(d.get("dollar_value") is not None for d in result.get("deliverables", []))


def type_counts(result: dict) -> list[tuple[str, int]]:
    """(type label, count) for the types present, most common first, then by label."""
    counts: dict[str, int] = {}
    for d in result.get("deliverables", []):
        label = category_label(d.get("category"))
        counts[label] = counts.get(label, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def term_text(contract: dict) -> str:
    """"Term June 13, 2012 to ...", "Term starts June 13, 2012", or "Term not stated in contract"."""
    term = format_term(contract.get("term_start"), contract.get("term_end"))
    if term == NOT_STATED:
        return "Term not stated in contract"
    if term.startswith(("Starts", "Ends")):  # drop "; end date not stated in contract"
        first = term.split(";")[0]
        return f"Term {first[0].lower()}{first[1:]}"
    return f"Term {term}"


def payments_text(contract: dict) -> str:
    payments = format_payments(contract.get("payments") or [])
    return "Payments not stated in contract" if payments == NOT_STATED else payments


def grounding_text(grounding: dict) -> str:
    return f"{grounding['grounded']} of {grounding['total']} quotes found in the PDF"


def summary_parts(contract: dict, grounding: dict) -> list[str]:
    """Term, payments, grounding: the pieces of summary_line."""
    return [term_text(contract), payments_text(contract), grounding_text(grounding)]


def summary_line(contract: dict, grounding: dict) -> str:
    """One line under the contract heading, e.g.
    "Term starts June 13, 2012 · 3 payments totaling $4,500,000 · 37 of 38 quotes found in the PDF"."""
    return " · ".join(summary_parts(contract, grounding))


# ---------- page and dialog text shared by the Streamlit app and the static site ----------

PAGE_TITLE = "Sponsorship deliverables"
TAGLINE = ("Turn a sponsorship contract into a list of everything the team owes the sponsor, "
           "with the contract text behind each item.")
NO_SELECTION = "Select a row to see the contract text behind it."
NOT_FOUND = "This text was not found word for word in the PDF. Check it against the contract."
FACT_NOT_STATED = "Not stated"
STATUS_BLANK = "Set in the contract"


def table_columns(with_value: bool) -> list[tuple[str, float]]:
    """(header, width ratio) for the row table; What's owed gets most of the room. Value only if asked."""
    columns = [("Clause", 1.25), ("Type", 1.25), ("What's owed", 4.5), ("Qty", 1.3), ("When", 1.6)]
    return columns + ([("Value", 0.9)] if with_value else []) + [("Status", 1.3)]


def dialog_kicker(row: dict) -> str:
    """The Muted line above a dialog's title: "Sch. 1 · 2(a) · Signage"."""
    return f"{row['clause']} · {row['type']}"


def dialog_facts(row: dict, with_value: bool) -> list[tuple[str, str]]:
    """(label, text) facts for a row's dialog: Qty, When, Status, plus Value when the row has one."""
    facts = [("Qty", row["qty"] or FACT_NOT_STATED), ("When", row["when"] or FACT_NOT_STATED),
             ("Status", row["status"] or STATUS_BLANK)]
    if with_value and row["value"]:
        facts.insert(2, ("Value", row["value"]))
    return facts


def parties_heading(contract: dict) -> str:
    return f"{contract.get('sponsor') or 'Sponsor not stated'} and {contract.get('rights_holder') or 'rights holder not stated'}"


def eval_line(evaluation: dict) -> str:
    """One line from output/eval/<stem>.json, e.g. "Checked against a hand-built answer key:
    found 12 of 14 deliverables, no false positives." """
    d = evaluation["deliverables"]
    extra = d["pred"] - d["matched"]
    extras = "no false positives" if extra == 0 else f"{extra} extra item{'s' if extra != 1 else ''} not in the key"
    return f"Checked against a hand-built answer key: found {d['matched']} of {d['gold']} deliverables, {extras}."
