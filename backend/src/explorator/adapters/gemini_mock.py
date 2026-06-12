"""Fake Gemini client for E2E testing — returns deterministic structured responses."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections import defaultdict
from typing import TYPE_CHECKING, Any, TypeVar, cast

if TYPE_CHECKING:
    from collections.abc import Callable

from pydantic import BaseModel

from explorator.adapters import usage
from explorator.adapters.gemini import ModelTier

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


# ── genre-research text fixtures ──────────────────────────────────────────────
# The genre-research pipeline calls generate_text() (not generate_structured()).
# Each prompt template starts with a recognizable header — we dispatch on it
# to return appropriate JSON/text. Without these, json.loads() crashes the
# pipeline at the draft stage.

def _genre_research_log(genre_name: str) -> str:
    return (
        f"Research log for {genre_name}: harmonic vocabulary spans 7th chords "
        "with extended tones, modal interchange, and chromatic mediants. "
        "Voicings favor open spread with mid-range bass. Groove leans towards "
        "spacious eighth-note patterns with light syncopation. Common devices "
        "include sus chords, plagal cadences, and pedal points."
    )


def _genre_draft_json(genre_name: str) -> str:
    """JSON satisfying GenreDraftResponse (profile/rules/grammar)."""
    payload = {
        "profile": {
            "genre": genre_name,
            "display_name": genre_name.replace("_", " ").title(),
            "version": 1,
            "harmonic_vocabulary": ["maj7", "m7", "sus4", "9"],
            "common_devices": ["plagal cadence", "pedal point"],
        },
        "rules": {
            "rules": [
                {
                    "name": "soft_cadence",
                    "type": "harmonic",
                    "weight": 0.6,
                    "description": "Prefer plagal/deceptive cadences over V-I.",
                    "applicability": {"scope": ["global"]},
                },
            ],
            "anti_patterns": [
                {
                    "name": "harsh_dominant",
                    "scope": "global",
                    "severity": 0.7,
                    "description": "Avoid bare V7-I in tonic-dark passages.",
                },
            ],
        },
        "grammar": {
            "genre_profile_id": f"genre_{genre_name}_01",
            "preferred_chord_qualities": ["maj7", "m7"],
            "cadence_archetypes": ["plagal"],
        },
    }
    return json.dumps(payload)


def _genre_critique_pass_json() -> str:
    """Critique that passes on the first try, so refine loop is skipped."""
    return json.dumps({"issues": [], "passed": True})


_STAGE_TAG_RE = re.compile(r"<!--\s*stage:\s*(\w+)\s*-->")
_GENRE_HEADER_RE = re.compile(r"^#\s+Genre\s+\w+:\s+(.+?)\s*$", re.MULTILINE)

_STAGE_HANDLERS: dict[str, Callable[[str], str]] = {
    "research": lambda g: _genre_research_log(g),
    "draft": lambda g: _genre_draft_json(g),
    "refine": lambda g: _genre_draft_json(g),
    "critique": lambda _g: _genre_critique_pass_json(),
}


def _genre_research_text(prompt: str) -> str | None:
    """Return a stage-appropriate string if `prompt` is a genre-research prompt.

    Each genre-research template carries a stable machine-readable tag near the
    top, e.g. `<!-- stage: research -->`. Matching on that (rather than on the
    human-readable header) means the mock survives template renames or
    reformatting — only the tag is load-bearing.

    Stages: research -> free-text log; draft / refine -> draft JSON;
    critique -> {issues, passed} JSON.
    """
    tag = _STAGE_TAG_RE.search(prompt)
    if tag is None:
        return None
    handler = _STAGE_HANDLERS.get(tag.group(1))
    if handler is None:
        return None
    header = _GENRE_HEADER_RE.search(prompt)
    genre = header.group(1) if header else "unknown_genre"
    return handler(genre)

# Lazy-initialized fixture map (avoids circular imports at module level)
_BUILDERS: dict[str, object] = {}


def _get_builders() -> dict[str, Any]:
    """Build fixture map on first call."""
    if _BUILDERS:
        return _BUILDERS

    from explorator.domain.evaluation.theory import GeminiScores
    from explorator.domain.harmony.generator import GeneratedProgression, GeneratedProgressionSet
    from explorator.domain.harmony.mutator import MutationResponse, MutationResponseItem
    from explorator.domain.intent.feedback import FeedbackInterpretation
    from explorator.domain.intent.parser import SoftPreferences
    from explorator.models.realization import ChordVoicingInstruction, VoicingStrategyResponse

    _progs = [
        GeneratedProgression(
            chord_symbols=["Amaj7", "F#m7", "Dmaj7", "E7"],
            rationale="Classic dream pop I-vi-IV-V with 7th extensions",
            intent_tags=["wistful", "ethereal"],
        ),
        GeneratedProgression(
            chord_symbols=["Amaj7", "C#m7", "F#m7", "Dmaj7"],
            rationale="Descending through relative minor",
            intent_tags=["melancholic", "flowing"],
        ),
        GeneratedProgression(
            chord_symbols=["Dmaj7", "Amaj7", "E7", "F#m7"],
            rationale="Subdominant-start for floating quality",
            intent_tags=["dreamy", "open"],
        ),
        GeneratedProgression(
            chord_symbols=["F#m7", "Dmaj7", "Amaj7", "E7"],
            rationale="Minor-start for darker mood",
            intent_tags=["haunted", "atmospheric"],
        ),
    ]

    _BUILDERS.update({
        "SoftPreferences": lambda: SoftPreferences(
            mood_targets=["wistful", "ethereal"],
            energy_level="low",
            complexity_target="medium",
            novelty_target="moderate",
        ),
        "GeneratedProgressionSet": lambda: GeneratedProgressionSet(progressions=_progs),
        "GeminiScores": lambda: GeminiScores(genre_fit=7.5, emotional_fit=7.0, novelty=6.5),
        "VoicingStrategyResponse": lambda: VoicingStrategyResponse(
            global_strategy="Open voicings with 7th extensions",
            density_level="medium",
            voice_count=4,
            register_profile="mid_high",
            rationale="Ethereal spread voicings",
            per_chord=[
                ChordVoicingInstruction(
                    chord_symbol=sym, voicing_type="open",
                    target_register="mid_high", extensions_to_include=["7"],
                )
                for sym in ["Amaj7", "F#m7", "Dmaj7", "E7"]
            ],
        ),
        "MutationResponse": lambda: MutationResponse(
            mutated_chord_symbols=["Amaj7", "F#m9", "Dmaj7", "Esus4"],
            mutations=[MutationResponseItem(
                operation="substitute_chord", position=1,
                original_value="F#m7", new_value="F#m9",
                description="Added 9th for color", reason="Increases novelty",
                predicted_score_changes=["novelty: +0.5"],
            )],
        ),
        "FeedbackInterpretation": lambda: FeedbackInterpretation(
            interpreted_adjustments={"increase_novelty": True, "reduce_predictability": True},
            weight_deltas={"novelty": 0.03, "genre_fit": -0.02, "loopability": -0.01},
            satisfaction="neutral",
        ),
    })
    return _BUILDERS


class FakeGeminiClient:
    """Drop-in replacement for GeminiClient returning deterministic fixtures."""

    def __init__(self) -> None:
        self.call_counts: dict[str, int] = defaultdict(int)

    def get_model_name(self, tier: ModelTier) -> str:
        return f"fake-{tier.value}"

    async def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        tier: ModelTier = ModelTier.FLASH,
        system_prompt: str | None = None,
    ) -> T:
        """Return a deterministic fixture based on response_model type."""
        name = response_model.__name__
        builders = _get_builders()
        if name not in builders:
            msg = f"Unsupported response_model for FakeGeminiClient: {name}"
            raise ValueError(msg)
        self.call_counts[name] += 1
        usage.record_synthetic_tokens(self.get_model_name(tier), 800, 200)
        logger.info("FakeGemini: %s (call #%d)", name, self.call_counts[name])
        return cast("T", builders[name]())

    async def generate_text(
        self,
        prompt: str,
        tier: ModelTier = ModelTier.FLASH,
        system_prompt: str | None = None,
    ) -> str:
        self.call_counts["generate_text"] += 1
        usage.record_synthetic_tokens(self.get_model_name(tier), 1200, 400)
        fixture = _genre_research_text(prompt)
        if fixture is not None:
            # Small artificial delay so the UI has time to render each stage's
            # progress indicator. Real LLM calls take seconds; without a delay
            # the pipeline finishes in single-digit milliseconds and the
            # in-progress view flashes by before E2E tests can observe it.
            await asyncio.sleep(0.15)
            logger.info("FakeGemini.generate_text: genre-research stage matched")
            return fixture
        return "Mock text response"
