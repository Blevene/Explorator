"""Each fan-out LLM call site must cap output tokens (runaway-generation guard)."""

from typing import Any

from explorator.adapters.llm import FANOUT_MAX_OUTPUT_TOKENS, ModelTier
from explorator.domain.evaluation.theory import TheoryEvaluator
from explorator.engine.nodes.generate_melody import generate_melody
from explorator.engine.nodes.plan_voicings import plan_voicings


class _CapturingClient:
    """Records generate_structured kwargs, then fails so callers take their fallback."""

    def __init__(self) -> None:
        self.kwargs: list[dict[str, Any]] = []

    def get_model_name(self, tier: ModelTier) -> str:
        return "capture"

    async def generate_structured(self, prompt: str, response_model: type, **kwargs: Any) -> Any:
        self.kwargs.append(kwargs)
        raise RuntimeError("stop")

    async def generate_text(self, prompt: str, **kwargs: Any) -> str:
        raise RuntimeError("stop")


def _state() -> dict[str, Any]:
    return {
        "creative_brief": {"genre": "dream_pop", "key_center": "C", "mode": "major"},
        "genre_profile": {"genre": "dream_pop"},
        "progression_candidates": [
            {
                "id": "p1",
                "session_id": "s",
                "type": "progression_candidate",
                "status": "draft",
                "rationale": "r",
                "key_center": "C",
                "chord_events": [
                    {"bar": 0, "symbol": "Cmaj7"},
                    {"bar": 1, "symbol": "Am7"},
                ],
            }
        ],
    }


def test_cap_constant_value() -> None:
    assert FANOUT_MAX_OUTPUT_TOKENS == 4096


async def test_plan_voicings_passes_cap() -> None:
    client = _CapturingClient()
    await plan_voicings(_state(), gemini=client)  # type: ignore[arg-type]
    assert client.kwargs
    assert client.kwargs[0]["max_output_tokens"] == FANOUT_MAX_OUTPUT_TOKENS


async def test_generate_melody_passes_cap() -> None:
    client = _CapturingClient()
    await generate_melody(_state(), gemini=client)  # type: ignore[arg-type]
    assert client.kwargs
    assert client.kwargs[0]["max_output_tokens"] == FANOUT_MAX_OUTPUT_TOKENS


async def test_theory_evaluator_passes_cap() -> None:
    client = _CapturingClient()
    await TheoryEvaluator(client)._gemini_evaluate(  # type: ignore[arg-type]
        ["Cmaj7", "Am7"], "dream_pop", ["wistful"], "C", "major"
    )
    assert client.kwargs
    assert client.kwargs[0]["max_output_tokens"] == FANOUT_MAX_OUTPUT_TOKENS
