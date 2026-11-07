"""Turn an extraction result into flat table rows for display. Pure: no I/O."""

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
