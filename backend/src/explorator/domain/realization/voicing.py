"""Deterministic voicing realization from Gemini strategies."""

from ulid import ULID

from explorator.adapters.music21_adapter import (
    _REGISTER_BOUNDS,
    _clamp_to_register,
    check_voice_leading,
    realize_voicing,
)
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
        prev_pitches: list[str] | None = None

        for bar_idx, chord_symbol in enumerate(chord_symbols):
            instruction = self._get_instruction(strategy, bar_idx, chord_symbol, prefs)

            # Variant voicing_type overrides the per-chord instruction
            effective_voicing_type = voicing_type or instruction.voicing_type
            register = instruction.target_register or prefs.default_register

            base_pitches = realize_voicing(
                symbol=chord_symbol,
                voicing_type=effective_voicing_type,
                register=register,
                voice_count=strategy.voice_count,
                extensions=instruction.extensions_to_include,
            )

            # Apply inversion sweep to minimize voice movement (skip first chord)
            if prev_pitches is not None:
                pitches = self._optimize_voice_leading(
                    base_pitches, prev_pitches, register
                )
            else:
                pitches = base_pitches

            events.append(
                VoicingEvent(
                    bar=bar_idx,
                    chord_symbol=chord_symbol,
                    pitches=pitches,
                )
            )
            prev_pitches = pitches

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
            metadata={"voicing_type": voicing_type},
        )

    def _optimize_voice_leading(
        self,
        current_pitches: list[str],
        prev_pitches: list[str],
        register: str,
    ) -> list[str]:
        """Pick the inversion of current_pitches that minimizes voice-leading cost.

        Generates up to 4 inversion candidates by rotating bottom notes up one
        octave, clamps each to the target register, then scores against the
        previous chord using check_voice_leading().

        Cost formula:
            total_semitone_distance - (common_tones * 4)
            + 100 if has_parallel_fifths
            + 100 if has_parallel_octaves
        """
        from music21 import pitch as m21pitch

        bounds = _REGISTER_BOUNDS.get(register, _REGISTER_BOUNDS["mid"])
        midi_low, midi_high, _ = bounds

        def to_midi(pitches: list[str]) -> list[int]:
            return sorted(m21pitch.Pitch(p).midi for p in pitches)

        def to_named(midi_list: list[int]) -> list[str]:
            result = []
            for m in sorted(midi_list):
                p = m21pitch.Pitch()
                p.midi = m
                result.append(p.nameWithOctave)
            return result

        def shift_to_register(midi: list[int]) -> list[int]:
            """Shift entire voicing by octaves until centroid is within register."""
            if not midi:
                return midi
            centroid = sum(midi) / len(midi)
            target = (midi_low + midi_high) / 2
            shift = round((target - centroid) / 12) * 12
            return sorted(m + shift for m in midi)

        base_midi = to_midi(current_pitches)
        n = len(base_midi)

        # Generate inversion candidates by rotating bottom notes up an octave,
        # then shift the whole voicing to fit the register (preserving intervals).
        candidates: list[list[int]] = []
        for k in range(min(n, 4)):
            midi = list(base_midi)
            for i in range(k):
                midi[i] += 12
            midi = shift_to_register(midi)
            candidates.append(midi)

        # Also try shifting the original voicing up/down one octave for more options
        candidates.append(shift_to_register([m + 12 for m in base_midi]))
        candidates.append(shift_to_register([m - 12 for m in base_midi]))

        # Score each candidate against previous chord
        best_pitches = current_pitches
        best_cost = float("inf")

        for candidate_midi in candidates:
            candidate_named = to_named(candidate_midi)
            vl = check_voice_leading(prev_pitches, candidate_named)
            cost = (
                vl.total_semitone_distance
                - (vl.common_tones * 4)
                + (100 if vl.has_parallel_fifths else 0)
                + (100 if vl.has_parallel_octaves else 0)
            )
            if cost < best_cost:
                best_cost = cost
                best_pitches = candidate_named

        return best_pitches

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
