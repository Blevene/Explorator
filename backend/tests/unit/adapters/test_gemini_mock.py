"""Tests for FakeGeminiClient."""

import pytest

from explorator.adapters.gemini_mock import FakeGeminiClient
from explorator.domain.harmony.generator import GeneratedProgressionSet
from explorator.domain.harmony.mutator import MutationResponse
from explorator.domain.evaluation.theory import GeminiScores
from explorator.domain.intent.feedback import FeedbackInterpretation
from explorator.domain.intent.parser import SoftPreferences
from explorator.models.realization import VoicingStrategyResponse


@pytest.mark.asyncio
async def test_fake_returns_soft_preferences() -> None:
    client = FakeGeminiClient()
    result = await client.generate_structured("test", response_model=SoftPreferences)
    assert isinstance(result, SoftPreferences)
    assert len(result.mood_targets) > 0


@pytest.mark.asyncio
async def test_fake_returns_progression_set() -> None:
    client = FakeGeminiClient()
    result = await client.generate_structured("test", response_model=GeneratedProgressionSet)
    assert isinstance(result, GeneratedProgressionSet)
    assert len(result.progressions) == 4


@pytest.mark.asyncio
async def test_fake_returns_gemini_scores() -> None:
    client = FakeGeminiClient()
    result = await client.generate_structured("test", response_model=GeminiScores)
    assert isinstance(result, GeminiScores)
    assert 0 <= result.genre_fit <= 10


@pytest.mark.asyncio
async def test_fake_returns_voicing_strategy() -> None:
    client = FakeGeminiClient()
    result = await client.generate_structured("test", response_model=VoicingStrategyResponse)
    assert isinstance(result, VoicingStrategyResponse)
    assert result.voice_count == 4
    assert len(result.per_chord) == 4


@pytest.mark.asyncio
async def test_fake_returns_mutation_response() -> None:
    client = FakeGeminiClient()
    result = await client.generate_structured("test", response_model=MutationResponse)
    assert isinstance(result, MutationResponse)
    assert len(result.mutated_chord_symbols) > 0


@pytest.mark.asyncio
async def test_fake_returns_feedback_interpretation() -> None:
    client = FakeGeminiClient()
    result = await client.generate_structured("test", response_model=FeedbackInterpretation)
    assert isinstance(result, FeedbackInterpretation)
    assert result.satisfaction == "neutral"


@pytest.mark.asyncio
async def test_fake_tracks_call_counts() -> None:
    client = FakeGeminiClient()
    await client.generate_structured("a", response_model=GeminiScores)
    await client.generate_structured("b", response_model=GeminiScores)
    assert client.call_counts["GeminiScores"] == 2


@pytest.mark.asyncio
async def test_fake_rejects_unknown_model() -> None:
    from pydantic import BaseModel

    class UnknownModel(BaseModel):
        x: int

    client = FakeGeminiClient()
    with pytest.raises(ValueError, match="Unsupported"):
        await client.generate_structured("test", response_model=UnknownModel)


# ── generate_text dispatch on <!-- stage: ... --> tag ────────────────────────


@pytest.mark.asyncio
async def test_generate_text_research_stage_returns_log() -> None:
    client = FakeGeminiClient()
    prompt = "<!-- stage: research -->\n# Genre Research: ambient_jazz\n\nresearch the genre."
    result = await client.generate_text(prompt)
    assert "ambient_jazz" in result
    assert "harmonic vocabulary" in result.lower()


@pytest.mark.asyncio
async def test_generate_text_draft_stage_returns_valid_json() -> None:
    import json
    client = FakeGeminiClient()
    prompt = "<!-- stage: draft -->\n# Genre Draft: shoegaze\n\ndraft the YAMLs."
    result = await client.generate_text(prompt)
    payload = json.loads(result)
    assert payload["profile"]["genre"] == "shoegaze"
    assert "rules" in payload
    assert "grammar" in payload


@pytest.mark.asyncio
async def test_generate_text_critique_stage_passes() -> None:
    import json
    client = FakeGeminiClient()
    prompt = "<!-- stage: critique -->\n# Genre Critique: anything\n\nreview please."
    result = await client.generate_text(prompt)
    payload = json.loads(result)
    assert payload["passed"] is True
    assert payload["issues"] == []


@pytest.mark.asyncio
async def test_generate_text_refine_stage_returns_draft_json() -> None:
    import json
    client = FakeGeminiClient()
    prompt = "<!-- stage: refine -->\n# Genre Refinement: jazz\n\nrefine."
    result = await client.generate_text(prompt)
    payload = json.loads(result)
    assert payload["profile"]["genre"] == "jazz"


@pytest.mark.asyncio
async def test_generate_text_no_tag_returns_default() -> None:
    """Prompts without a stage tag fall through to the generic mock string."""
    client = FakeGeminiClient()
    result = await client.generate_text("# Some Other Prompt: foo\n\nplain text request.")
    assert result == "Mock text response"


@pytest.mark.asyncio
async def test_generate_text_unknown_tag_returns_default() -> None:
    """A tag we don't have a handler for falls through cleanly."""
    client = FakeGeminiClient()
    result = await client.generate_text("<!-- stage: imaginary -->\n# Genre Anything: x")
    assert result == "Mock text response"


@pytest.mark.asyncio
async def test_generate_text_tag_anywhere_in_prompt() -> None:
    """The tag isn't required to be on the first line — anywhere works."""
    import json
    client = FakeGeminiClient()
    prompt = "# Genre Draft: techno\n\nSome preamble.\n\n<!-- stage: draft -->\n\nMore content."
    result = await client.generate_text(prompt)
    payload = json.loads(result)
    assert payload["profile"]["genre"] == "techno"
