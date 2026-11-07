"""Offline tests for extract_contract. The Anthropic client is always faked."""

import copy
import json
from types import SimpleNamespace

import pytest

from deliverables.extract import ExtractionError, extract_contract
from deliverables.schema import EXTRACTION_SCHEMA

VALID_INPUT = {
    "contract": {
        "sponsor": "AlphaTrade.com",
        "rights_holder": "Sterling Mets, L.P.",
        "seasons": ["2007", "2008"],
        "term_start": None,
        "term_end": None,
        "territory": None,
        "payments": [{"amount": None, "due_date": None, "redacted": True}],
    },
    "deliverables": [
        {
            "section": "3",
            "category": "pa_announcement",
            "description": "One 15-second PA announcement each home game.",
            "quantity": 1,
            "unit": "announcements",
            "frequency": "each Mets home game",
            "dollar_value": None,
            "details_to_be_agreed": False,
            "conditions": [],
            "sponsor_obligations": [],
            "proof_of_performance": None,
            "source_quote": "One 15-second announcement on the Stadium public address system",
        }
    ],
}


class FakeMessages:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class FakeClient:
    def __init__(self, response):
        self.messages = FakeMessages(response)


def fake_response(content, stop_reason="end_turn"):
    return SimpleNamespace(content=content, stop_reason=stop_reason)


def text_block(text):
    return SimpleNamespace(type="text", text=text)


def json_block(data):
    return text_block(json.dumps(data))


def test_returns_parsed_json_on_valid_response():
    client = FakeClient(fake_response([json_block(VALID_INPUT)]))
    assert extract_contract("contract text", client, "test-model") == VALID_INPUT


def test_ignores_thinking_block_before_json():
    thinking = SimpleNamespace(type="thinking", thinking="")
    client = FakeClient(fake_response([thinking, json_block(VALID_INPUT)]))
    assert extract_contract("contract text", client, "test-model") == VALID_INPUT


def test_sends_output_config_and_no_tools():
    client = FakeClient(fake_response([json_block(VALID_INPUT)]))
    extract_contract("contract text", client, "test-model")

    kwargs = client.messages.calls[0]
    assert kwargs["output_config"] == {"format": {"type": "json_schema", "schema": EXTRACTION_SCHEMA}}
    assert "tools" not in kwargs
    assert "tool_choice" not in kwargs
    assert kwargs["max_tokens"] == 16000
    assert kwargs["model"] == "test-model"
    assert "<contract>\ncontract text\n</contract>" in kwargs["messages"][0]["content"]


def test_raises_on_max_tokens():
    client = FakeClient(fake_response([json_block(VALID_INPUT)], stop_reason="max_tokens"))
    with pytest.raises(ExtractionError, match="max_tokens"):
        extract_contract("contract text", client, "test-model")


def test_raises_on_refusal():
    client = FakeClient(fake_response([text_block("I can't help with that.")], stop_reason="refusal"))
    with pytest.raises(ExtractionError, match="refused"):
        extract_contract("contract text", client, "test-model")


def test_raises_on_unparseable_json():
    client = FakeClient(fake_response([text_block('{"contract": {"sponsor": "Alpha')]))
    with pytest.raises(ExtractionError, match="not valid JSON"):
        extract_contract("contract text", client, "test-model")


def test_raises_without_text_block():
    client = FakeClient(fake_response([]))
    with pytest.raises(ExtractionError, match="no text block"):
        extract_contract("contract text", client, "test-model")


def test_raises_on_schema_violation():
    bad_input = copy.deepcopy(VALID_INPUT)
    del bad_input["deliverables"][0]["source_quote"]
    client = FakeClient(fake_response([json_block(bad_input)]))
    with pytest.raises(ExtractionError, match="source_quote"):
        extract_contract("contract text", client, "test-model")
