"""Tests for provider-neutral structured-output helpers."""

import json
import logging

import pytest
from pydantic import BaseModel, Field, ValidationError

from explorator.adapters._structured import (
    extract_json,
    loads_lenient,
    parse_structured,
    repair_truncated_json,
    strip_reasoning,
    truncate_to_max_length,
)
from explorator.models.realization import VoicingStrategyResponse


class _Item(BaseModel):
    note: str = Field(max_length=5)


class _Sample(BaseModel):
    name: str = Field(max_length=4)
    value: int
    items: list[_Item] = Field(default_factory=list)


# ── strip_reasoning ──────────────────────────────────────────────────────────

def test_strip_reasoning_removes_think_block() -> None:
    assert strip_reasoning("<think>hmm {x}</think>\nhello").strip() == "hello"


def test_strip_reasoning_handles_prefilled_think_with_only_closing_tag() -> None:
    # Chat templates for qwen3/deepseek-r1 often pre-fill "<think>" in the prompt,
    # so the completion contains reasoning followed by a bare closing tag.
    assert strip_reasoning("reasoning {not json}\n</think>\n{\"a\": 1}").strip() == '{"a": 1}'


def test_strip_reasoning_passthrough() -> None:
    assert strip_reasoning("plain text") == "plain text"


# ── extract_json ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('{"a": 1}', {"a": 1}),
        ('```json\n{"a": 1}\n```', {"a": 1}),
        ('Here you go:\n```json\n{"a": 1}\n```\nEnjoy!', {"a": 1}),
        ('```\n{"a": 1}', {"a": 1}),  # unterminated fence
        ('<think>I think {maybe} this</think>\n{"a": 1}', {"a": 1}),
        ('thinking about {braces}</think>```json\n{"a": 1}\n```', {"a": 1}),
        ('Sure! The answer is {"a": {"b": 2}} as requested.', {"a": {"b": 2}}),
        ('[1, 2, 3]', [1, 2, 3]),
    ],
)
def test_extract_json_variants(raw: str, expected: object) -> None:
    assert json.loads(extract_json(raw)) == expected


def test_extract_json_without_delimiters_returns_text_so_json_loads_raises() -> None:
    out = extract_json("no json here")
    with pytest.raises(json.JSONDecodeError):
        json.loads(out)


# ── truncate_to_max_length (previously untested) ─────────────────────────────

def test_truncate_top_level_field() -> None:
    data = {"name": "toolong", "value": 1}
    assert truncate_to_max_length(data, _Sample)["name"] == "tool"  # type: ignore[index]


def test_truncate_list_of_ref_items() -> None:
    data = {"name": "a", "value": 1, "items": [{"note": "abcdefgh"}, {"note": "ok"}]}
    out = truncate_to_max_length(data, _Sample)
    assert out["items"] == [{"note": "abcde"}, {"note": "ok"}]  # type: ignore[index]


def test_truncate_non_dict_passthrough() -> None:
    assert truncate_to_max_length([1, 2], _Sample) == [1, 2]


# ── parse_structured ─────────────────────────────────────────────────────────

def test_parse_structured_happy_path_with_fence_and_truncation() -> None:
    result = parse_structured(
        '```json\n{"name": "toolong", "value": 3}\n```', _Sample, provider="X", model_name="m"
    )
    assert result == _Sample(name="tool", value=3)


@pytest.mark.parametrize("raw", [None, ""])
def test_parse_structured_empty_raises(raw: str | None) -> None:
    with pytest.raises(ValueError, match="X returned empty response for model=m"):
        parse_structured(raw, _Sample, provider="X", model_name="m")


def test_parse_structured_malformed_raises_value_error() -> None:
    with pytest.raises(ValueError, match="X returned malformed JSON for model=m"):
        parse_structured("{not json", _Sample, provider="X", model_name="m")


def test_parse_structured_schema_mismatch_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        parse_structured('{"name": "a"}', _Sample, provider="X", model_name="m")


# ── loads_lenient ────────────────────────────────────────────────────────────

def test_parse_structured_keeps_valid_json_containing_fence_and_think_tag() -> None:
    payload = {"name": "ab", "value": 1, "note": "see ```x``` and </think> ok"}
    text = json.dumps(payload)

    class _Wide(BaseModel):
        name: str
        value: int
        note: str

    result = parse_structured(text, _Wide, provider="p", model_name="m")
    assert result.note == payload["note"]


def test_loads_lenient_falls_back_to_extraction() -> None:
    assert loads_lenient('Sure! ```json\n{"a": 1}\n``` done') == {"a": 1}


def test_loads_lenient_raises_on_malformed() -> None:
    with pytest.raises(json.JSONDecodeError):
        loads_lenient("no json here")


# ── repair_truncated_json / truncated parse_structured ───────────────────────

_TRUNCATED_VOICING = (
    '{"global_strategy":"Maintain lush open pad voicings","density_level":"medium",'
    '"voice_count":4,"register_profile":"mid","rationale":"Adding diatonic seventh '
    + "float. " * 40
)


def _parse_voicing(text: str) -> VoicingStrategyResponse:
    return parse_structured(text, VoicingStrategyResponse, provider="X", model_name="m")


def test_parse_structured_repairs_compact_truncation(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        result = _parse_voicing(_TRUNCATED_VOICING)
    assert result.density_level == "medium"
    assert result.voice_count == 4
    assert result.register_profile == "mid"
    assert result.global_strategy.startswith("Maintain lush")
    assert result.rationale.startswith("Adding diatonic seventh")
    assert len(result.rationale) <= 200
    assert "output was truncated; repaired JSON (model=m)" in caplog.text


def test_parse_structured_repairs_pretty_printed_truncation() -> None:
    pretty = json.dumps(json.loads(
        '{"global_strategy":"Maintain lush open pad voicings","density_level":"medium",'
        '"voice_count":4,"register_profile":"mid","rationale":"x"}'
    ), indent=2)
    cut = pretty[: pretty.index('"x"')] + '"Adding diatonic seventh ' + "float.\n" * 60
    result = _parse_voicing(cut)
    assert result.voice_count == 4
    assert len(result.rationale) <= 200


def test_repair_cut_inside_nested_list() -> None:
    out = repair_truncated_json('{"a": 1, "items": [{"x": "y"}, {"x": "z')
    assert out == {"a": 1, "items": [{"x": "y"}, {"x": "z"}]}


@pytest.mark.parametrize("text", ['{"a": 1, "b":', '{"a": 1, "b', '{"a": 1,', '{"a": 1, "b": 12e'])
def test_repair_cut_after_key_colon_comma(text: str) -> None:
    assert repair_truncated_json(text) == {"a": 1}


def test_repair_handles_escaped_quote_in_truncated_string() -> None:
    assert repair_truncated_json('{"a": "say \\"hi') == {"a": 'say "hi'}


def test_repair_cut_mid_literal_in_list() -> None:
    assert repair_truncated_json('{"a": [1, 2, tr') == {"a": [1, 2]}


def test_repair_skips_fence_and_reasoning() -> None:
    assert repair_truncated_json('<think>x {</think>```json\n{"a": "b') == {"a": "b"}


def test_repair_garbage_raises() -> None:
    with pytest.raises(json.JSONDecodeError):
        repair_truncated_json("no json at all")


def test_parse_structured_truncation_missing_required_field_raises_validation_error() -> None:
    text = '{"global_strategy":"Maintain lush","density_l'
    with pytest.raises(ValidationError):
        _parse_voicing(text)


def test_parse_structured_garbage_still_malformed() -> None:
    with pytest.raises(ValueError, match="X returned malformed JSON for model=m"):
        _parse_voicing("no json at all")


def test_parse_structured_valid_json_does_not_invoke_repair(
    caplog: pytest.LogCaptureFixture,
) -> None:
    text = (
        '{"global_strategy":"g","density_level":"medium","voice_count":4,'
        '"register_profile":"mid","rationale":"r"}'
    )
    with caplog.at_level(logging.WARNING):
        result = _parse_voicing(text)
    assert result.rationale == "r"
    assert "repaired" not in caplog.text
