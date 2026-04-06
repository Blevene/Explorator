"""Deterministic voicing realization from Gemini strategies."""

from ulid import ULID

from explorator.adapters.music21_adapter import check_voice_leading, realize_voicing
from explorator.models.realization import (
    ChordVoicingInstruction,
    VariantConfig,
    VoicingEvent,
    VoicingPlan,
    VoicingPreferences,
    VoicingStrategyResponse,
)
from explorator.utils import utc_now


class VoicingGenerator:
    """Realizes voicing strategies into concrete pitched VoicingPlans."""

    def realize(
        self,
        strategy: VoicingStrategyResponse,
        chord_symbols: list[str],
        prefs: VoicingPreferences,
        variant: VariantConfig,
    ) -> VoicingPlan:
        """Realize a voicing strategy into a VoicingPlan for one variant."""
        voicing_type = variant.voicing_type or prefs.default_voicing_type

        events: list[VoicingEvent] = []
        for bar_idx, chord_symbol in enumerate(chord_symbols):
            instruction = self._get_instruction(strategy, bar_idx, chord_symbol, prefs)

            # Variant voicing_type overrides the per-chord instruction
            effective_voicing_type = voicing_type or instruction.voicing_type
            register = instruction.target_register or prefs.default_register

            pitches = realize_voicing(
                symbol=chord_symbol,
                voicing_type=effective_voicing_type,
                register=register,
                voice_count=strategy.voice_count,
                extensions=instruction.extensions_to_include,
            )

            events.append(
                VoicingEvent(
                    bar=bar_idx,
                    chord_symbol=chord_symbol,
                    pitches=pitches,
                )
            )

        now = utc_now()
        return VoicingPlan(
            id=f"vp_{ULID()}",
            type="voicing_plan",
            status="draft",
            created_at=now,
            updated_at=now,
            global_strategy=strategy.global_strategy,
            density_level=strategy.density_level,
            voicing_events=events,
        )

    def generate_variants(
        self,
        strategy: VoicingStrategyResponse,
        chord_symbols: list[str],
        prefs: VoicingPreferences,
    ) -> list[VoicingPlan]:
        """Generate multiple voicing plan variants by sweeping voicing types."""
        return [
            self.realize(strategy, chord_symbols, prefs, VariantConfig(voicing_type=vt))
            for vt in prefs.variant_voicing_types
        ]

    def _get_instruction(
        self,
        strategy: VoicingStrategyResponse,
        bar_idx: int,
        chord_symbol: str,
        prefs: VoicingPreferences,
    ) -> ChordVoicingInstruction:
        """Get per-chord instruction, falling back to genre defaults."""
        if bar_idx < len(strategy.per_chord):
            return strategy.per_chord[bar_idx]
        return ChordVoicingInstruction(
            chord_symbol=chord_symbol,
            voicing_type=prefs.default_voicing_type,
            target_register=prefs.default_register,
            extensions_to_include=[],
        )
