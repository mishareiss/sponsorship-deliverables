"""JSON schema for sponsorship contract extraction.

Sent to Claude as a structured output (output_config.format), so the response text
is JSON matching this schema. Started as the input_schema of the tool in
flagship/extraction_schema.py; the only change is "additionalProperties": False on
every object, which structured outputs requires. Every field is required; fields that
may be missing in a contract are nullable so Claude must answer either way.
Do not change fields without asking.
"""

NULLABLE_STR = {"type": ["string", "null"]}

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "contract": {
            "type": "object",
            "properties": {
                "sponsor": {"type": "string"},
                "rights_holder": {"type": "string", "description": "Team or entity granting the rights"},
                "seasons": {"type": "array", "items": {"type": "string"}, "description": "e.g. ['2007', '2008']"},
                "term_start": {**NULLABLE_STR, "description": "ISO date if stated"},
                "term_end": {**NULLABLE_STR, "description": "ISO date if stated"},
                "territory": {**NULLABLE_STR, "description": "Geographic limits on the rights, if any"},
                "payments": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "amount": {"type": ["number", "null"], "description": "null if redacted or not stated"},
                            "due_date": NULLABLE_STR,
                            "redacted": {"type": "boolean"},
                        },
                        "required": ["amount", "due_date", "redacted"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["sponsor", "rights_holder", "seasons", "term_start", "term_end", "territory", "payments"],
            "additionalProperties": False,
        },
        "deliverables": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "section": {**NULLABLE_STR, "description": "Clause number, e.g. '3'"},
                    "category": {
                        "type": "string",
                        "enum": [
                            "signage", "scoreboard_led", "pa_announcement", "broadcast", "digital",
                            "print", "tickets", "hospitality", "activation", "marks_designation",
                            "exclusivity", "other",
                        ],
                    },
                    "description": {"type": "string", "description": "Plain-English summary of what is delivered"},
                    "quantity": {"type": ["number", "null"], "description": "Count per frequency period; null if not countable"},
                    "unit": {**NULLABLE_STR, "description": "e.g. signs, tickets, announcements"},
                    "frequency": {**NULLABLE_STR, "description": "e.g. 'each home game', 'once per season'"},
                    "dollar_value": {"type": ["number", "null"], "description": "Only when the deliverable is defined by value"},
                    "details_to_be_agreed": {"type": "boolean", "description": "True if dates/specifics are 'mutually agreed'"},
                    "conditions": {
                        "type": "array", "items": {"type": "string"},
                        "description": "Approvals or limits, e.g. 'subject to MLBAM approval'",
                    },
                    "sponsor_obligations": {
                        "type": "array", "items": {"type": "string"},
                        "description": "What the sponsor must do or pay for",
                    },
                    "proof_of_performance": {**NULLABLE_STR, "description": "Only if the contract states it"},
                    "source_quote": {"type": "string", "description": "Exact contract text this deliverable comes from"},
                },
                "required": [
                    "section", "category", "description", "quantity", "unit", "frequency",
                    "dollar_value", "details_to_be_agreed", "conditions",
                    "sponsor_obligations", "proof_of_performance", "source_quote",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["contract", "deliverables"],
    "additionalProperties": False,
}
