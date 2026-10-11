"""Tests for HarmonyMutator domain service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from explorator.domain.harmony.mutator import (
    HarmonyMutator,
    MutationResponse,
    MutationResponseItem,
)


def _make_llm(response: MutationResponse) -> MagicMock:
    mock = MagicMock()
    mock.generate_structured = AsyncMock(return_value=response)
    return mock


@pytest.fixture
def sample_response() -> MutationResponse:
    return MutationResponse(
        mutated_chord_symbols=["Cmaj7", "Em7", "Fmaj7", "G7"],
        mutations=[
            MutationResponseItem(
                operation="substitute_chord",
                position=1,
                original_value="Am7",
                new_value="Em7",
                reason="Em7 adds more tension before the IV chord",
                predicted_score_changes=["novelty: +1.0", "genre_fit: -0.5"],
            ),
        ],
    )


async def test_mutate_harmonic_returns_progression(sample_response: MutationResponse) -> None:
    llm = _make_llm(sample_response)
    mutator = HarmonyMutator(llm)

    result = await mutator.mutate_harmonic(
        chord_symbols=["Cmaj7", "Am7", "Fmaj7", "G7"],
        genre="dream_pop",
        scores={"genre_fit": 7.0, "novelty": 5.0},
        guidance=None,
    )

    assert result.mutated_chord_symbols == ["Cmaj7", "Em7", "Fmaj7", "G7"]
    assert len(result.mutations) == 1
    assert result.mutations[0].operation == "substitute_chord"
    llm.generate_structured.assert_called_once()


async def test_mutate_harmonic_with_guidance(sample_response: MutationResponse) -> None:
    llm = _make_llm(sample_response)
    mutator = HarmonyMutator(llm)

    await mutator.mutate_harmonic(
        chord_symbols=["Cmaj7", "Am7"],
        genre="synthwave",
        scores={"genre_fit": 6.0},
        guidance="make it darker",
    )

    call_args = llm.generate_structured.call_args
    prompt = call_args.kwargs.get("prompt") or call_args.args[0]
    assert "make it darker" in prompt


async def test_mutate_harmonic_limits_experimental() -> None:
    """At most 1 experimental mutation per call."""
    response = MutationResponse(
        mutated_chord_symbols=["Dm7", "G7", "Cmaj7", "Am7"],
        mutations=[
            MutationResponseItem(
                operation="experimental",
                description="replaced everything",
                reason="creative freedom",
            ),
            MutationResponseItem(
                operation="experimental",
                description="more changes",
                reason="more freedom",
            ),
        ],
    )
    llm = _make_llm(response)
    mutator = HarmonyMutator(llm)

    result = await mutator.mutate_harmonic(
        chord_symbols=["Cmaj7", "Am7", "Fmaj7", "G7"],
        genre="dream_pop",
        scores={},
    )

    experimental_count = sum(1 for m in result.mutations if m.operation == "experimental")
    assert experimental_count <= 1
