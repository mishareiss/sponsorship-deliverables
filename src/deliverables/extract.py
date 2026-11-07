"""Extract contract terms and deliverables with Claude, using structured outputs."""

import json
import os

import anthropic
import jsonschema

from deliverables.schema import EXTRACTION_SCHEMA

DEFAULT_MODEL = "claude-sonnet-5-5"
MAX_TOKENS = 16000

SYSTEM_PROMPT = """You extract structured data from sports sponsorship contracts.

Rules:
- Extract every deliverable the rights holder provides to the sponsor. Use one deliverable per numbered clause, unless a clause clearly contains separate items.
- Use null when the contract doesn't state something. Never guess.
- If a payment amount is redacted (for example shown as "$*"), set "redacted": true and "amount": null.
- "source_quote" must be verbatim text copied from the contract.
- Legal boilerplate is not a deliverable: indemnity, subordination, governing law, payment default interest, and similar terms.

Respond with the contract terms and the full list of deliverables as JSON matching the provided schema."""


class ExtractionError(Exception):
    """The model did not return a complete, schema-valid extraction."""


def default_model() -> str:
    return os.environ.get("ANTHROPIC_MODEL") or DEFAULT_MODEL


def extract_contract(text: str, client: anthropic.Anthropic, model: str) -> dict:
    """Send the contract text to Claude and return the parsed, validated JSON."""
    response = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        output_config={"format": {"type": "json_schema", "schema": EXTRACTION_SCHEMA}},
        messages=[
            {
                "role": "user",
                "content": f"<contract>\n{text}\n</contract>\n\nExtract the contract terms and all deliverables.",
            }
        ],
    )

    # The schema is only guaranteed on a normal finish. A cut-off or refused
    # response can still look like JSON, so fail loudly on both.
    if response.stop_reason == "max_tokens":
        raise ExtractionError("Response hit max_tokens; the extraction is likely truncated.")
    if response.stop_reason == "refusal":
        raise ExtractionError("Model refused the request; output may not match the schema.")

    text_blocks = [block.text for block in response.content if block.type == "text"]
    if not text_blocks:
        raise ExtractionError("Response contained no text block with JSON.")
    try:
        result = json.loads(text_blocks[0])
    except json.JSONDecodeError as err:
        raise ExtractionError(f"Response text is not valid JSON: {err}") from err

    # Structured outputs should guarantee this; checking again is cheap.
    try:
        jsonschema.validate(result, EXTRACTION_SCHEMA)
    except jsonschema.ValidationError as err:
        raise ExtractionError(f"JSON failed schema validation: {err.message}") from err

    return result
