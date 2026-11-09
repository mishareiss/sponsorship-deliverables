"""Turn an extraction result into flat table rows for display. Pure: no I/O.

deliverable_rows/COLUMNS keep raw field names (tests and the eval rely on them). The display layer
below maps them to the headers, category labels and summary text the demo shows.
"""

from datetime import date

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

# User-facing column headers, in the order the demo table shows them.
DISPLAY_HEADERS = {
    "section": "Clause",
    "category": "Type",
    "description": "What's owed",
    "quantity": "Qty",
    "unit": "Unit",
    "frequency": "When",
    "dollar_value": "Value",
    "details_to_be_agreed": "To be agreed",
    "conditions": "Conditions",
    "sponsor_obligations": "Sponsor must",
}
DISPLAY_COLUMNS = list(DISPLAY_HEADERS.values())

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


def display_rows(result: dict) -> list[dict]:
    """deliverable_rows with user-facing headers (DISPLAY_COLUMNS order) and category labels."""
    rows = []
    for row in deliverable_rows(result):
        display = {header: row[field] for field, header in DISPLAY_HEADERS.items()}
        display["Type"] = category_label(row["category"])
        rows.append(display)
    return rows


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


def contract_summary(contract: dict) -> list[tuple[str, str]]:
    """(label, value) rows for the contract summary. Missing values read 'Not stated in contract'."""
    seasons = ", ".join(contract.get("seasons") or []) or NOT_STATED
    return [
        ("Sponsor ↔ Rights holder", f"{contract['sponsor']} ↔ {contract['rights_holder']}"),
        ("Seasons", seasons),
        ("Term", format_term(contract.get("term_start"), contract.get("term_end"))),
        ("Payments", format_payments(contract.get("payments") or [])),
    ]
