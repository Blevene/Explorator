"""Generate melody node — LLM-guided melodic complement generation per progression candidate."""

import asyncio
import logging
from typing import Any

from explorator.adapters.gemini import GeminiClient, ModelTier
from explorator.domain.realization.melody import MelodyGenerator
from explorator.engine.state import ExplorationState
from explorator.models.harmony import ProgressionCandidate
from explorator.models.melody import MelodicPreferences, MelodicStrategyResponse
from explorator.models.realization import BassLine, VoicingPlan
from explorator.prompts.melody import melody_strategy_prompt
from explorator.utils import parse_json_or_dict, pitch_str_to_midi

logger = logging.getLogger(__name__)


def _default_strategy(n_bars: int) -> MelodicStrategyResponse:
    """Build a fallback melodic strategy when Gemini fails."""
    from explorator.models.melody import PhraseInstruction

    phrases = []
    bar = 0
    while bar < n_bars:
        end = min(bar + 3, n_bars - 1)
        phrases.append(PhraseInstruction(
            start_bar=bar,
            end_bar=end,
            contour="arch",
            density="moderate",
            strong_beat_targets=["root", "5th"],
            rest_after=(end < n_bars - 1),
        ))
        bar = end + 1

    return MelodicStrategyResponse(
        range_low="C5",
        range_high="C6",
        overall_contour="arch",
        phrase_instructions=phrases,
        rationale="Default strategy: arch contour with chord-tone targeting.",
    )


def _extract_ceiling_notes(vp: VoicingPlan) -> list[str]:
    """Extract the highest pitched note per bar from voicing events."""
    bar_maxes: dict[int, tuple[int, str]] = {}
    for ve in vp.voicing_events:
        if not ve.pitches:
            continue
        best_midi = -1
        best_pitch = ""
        for p in ve.pitches:
            try:
                m = pitch_str_to_midi(p)
                if m > best_midi:
                    best_midi = m
                    best_pitch = p
            except ValueError:
                pass
        if best_midi >= 0:
            prev = bar_maxes.get(ve.bar, (-1, ""))
            if best_midi > prev[0]:
                bar_maxes[ve.bar] = (best_midi, best_pitch)

    if not bar_maxes:
        return []
    max_bar = max(bar_maxes.keys())
    return [bar_maxes.get(b, (0, "C4"))[1] for b in range(max_bar + 1)]


def _extract_floor_notes(bl: BassLine) -> list[str]:
    """Extract the lowest pitched note per bar from bass line events."""
    bar_mins: dict[int, tuple[int, str]] = {}
    for ne in bl.note_events:
        try:
            m = pitch_str_to_midi(ne.pitch)
        except ValueError:
            continue
        prev = bar_mins.get(ne.bar, (999, ""))
        if m < prev[0]:
            bar_mins[ne.bar] = (m, ne.pitch)

    if not bar_mins:
        return []
    max_bar = max(bar_mins.keys())
    return [bar_mins.get(b, (60, "C3"))[1] for b in range(max_bar + 1)]


def _groove_summary(groove_patterns_raw: list[dict[str, Any]]) -> str:
    """Build a textual groove summary from the first available groove pattern."""
    if not groove_patterns_raw:
        return "straight eighths"
    gp = groove_patterns_raw[0]
    style = str(gp.get("style", ""))
    density = str(gp.get("density_label", ""))
    if style and density:
        return f"{style} ({density})"
    if style:
        return style
    return "rhythmic groove pattern"


async def generate_melody(state: ExplorationState, *, gemini: GeminiClient) -> dict[str, Any]:
    """Generate melodic complements via Gemini strategy + deterministic realization."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "generate_melody"})

    genre_profile = parse_json_or_dict(state.get("genre_profile", {}))
    creative_brief = parse_json_or_dict(state.get("creative_brief", {}))
    # Use top_progressions if available, otherwise progression_candidates
    candidates_raw = state.get("top_progressions", []) or state.get("progression_candidates", [])

    genre = genre_profile.get("genre", creative_brief.get("genre", "dream_pop"))
    key_center = creative_brief.get("key_center") or "C"
    mode = creative_brief.get("mode") or "major"

    # Extract melodic tendencies and preferences
    melodic_tendencies = parse_json_or_dict(genre_profile.get("melodic_tendencies", {}))
    mel_prefs = MelodicPreferences.from_genre_tendencies(melodic_tendencies)

    # Build lookups
    vp_by_prog: dict[str, VoicingPlan] = {}
    for vp_data in state.get("voicing_plans", []):
        vp = VoicingPlan.model_validate(vp_data)
        pid = vp.progression_candidate_id or ""
        # Keep the first voicing plan per progression
        if pid not in vp_by_prog:
            vp_by_prog[pid] = vp

    bl_by_prog: dict[str, BassLine] = {}
    for bl_data in state.get("bass_lines", []):
        bl = BassLine.model_validate(bl_data)
        pid = bl.progression_candidate_id or ""
        if pid not in bl_by_prog:
            bl_by_prog[pid] = bl

    groove_patterns_raw = state.get("groove_patterns", [])
    groove_summary_text = _groove_summary(groove_patterns_raw)

    # Build beat_grid from first groove pattern
    beat_grid: list[dict[str, Any]] | None = None
    if groove_patterns_raw:
        gp0 = groove_patterns_raw[0]
        events = gp0.get("events", [])
        if events:
            beat_grid = events

    generator = MelodyGenerator()

    async def _process_candidate(candidate_data: dict[str, Any]) -> list[dict[str, Any]]:
        candidate = ProgressionCandidate.model_validate(candidate_data)
        chord_symbols = [e.symbol for e in candidate.chord_events]
        if not chord_symbols:
            return []

        vp = vp_by_prog.get(candidate.id)
        bl = bl_by_prog.get(candidate.id)

        voicing_ceiling = _extract_ceiling_notes(vp) if vp else []
        bass_floor = _extract_floor_notes(bl) if bl else []

        # Build Gemini prompt
        user_prompt, system = melody_strategy_prompt(
            chord_symbols=chord_symbols,
            key_center=key_center,
            mode=mode,
            genre=genre,
            melodic_tendencies=melodic_tendencies,
            voicing_ceiling_notes=voicing_ceiling or ["C5"] * len(chord_symbols),
            bass_floor_notes=bass_floor or ["C3"] * len(chord_symbols),
            groove_summary=groove_summary_text,
        )

        strategy: MelodicStrategyResponse
        try:
            strategy = await gemini.generate_structured(
                user_prompt,
                response_model=MelodicStrategyResponse,
                tier=ModelTier.FLASH,
                system_prompt=system,
            )
        except Exception:
            logger.warning(
                "Melody strategy LLM call failed for candidate %s — using default",
                candidate.id,
            )
            strategy = _default_strategy(len(chord_symbols))

        # Validate: ensure at least one phrase instruction
        if not strategy.phrase_instructions:
            strategy = _default_strategy(len(chord_symbols))

        # Safety: normalize phrase bars to 0-based. The prompt asks for 0-indexed
        # but Gemini may return 1-indexed anyway. Detect by checking if first
        # phrase starts at 1 when we expect 0.
        if (
            strategy.phrase_instructions
            and strategy.phrase_instructions[0].start_bar == 1
            and len(chord_symbols) > 1
        ):
            for pi in strategy.phrase_instructions:
                pi.start_bar = max(0, pi.start_bar - 1)
                pi.end_bar = max(0, pi.end_bar - 1)

        # Get voicing events for collision avoidance
        voicing_events = vp.voicing_events if vp else []

        complement = generator.realize(
            strategy=strategy,
            chord_symbols=chord_symbols,
            key_center=key_center,
            mode=mode,
            voicing_events=voicing_events,
            beat_grid=beat_grid,
            motion_preference=mel_prefs.motion_preference,
        )
        complement.arrangement_candidate_id = ""  # will be linked in assemble
        complement.source_strategy = f"gemini_flash_{genre}"

        return [complement.model_dump(mode="json")]

    results = await asyncio.gather(
        *[_process_candidate(cd) for cd in candidates_raw],
        return_exceptions=True,
    )

    all_complements: list[dict[str, Any]] = []
    for r in results:
        if isinstance(r, BaseException):
            logger.warning("Melody generation failed for a candidate: %s", r)
            continue
        assert isinstance(r, list)
        all_complements.extend(r)

    logger.info(
        "generate_melody: produced %d complements for %d candidates",
        len(all_complements),
        len(candidates_raw),
    )

    return {"melodic_complements": all_complements}
