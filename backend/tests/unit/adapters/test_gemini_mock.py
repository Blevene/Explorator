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
