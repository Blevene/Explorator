"""Deterministic melody generation from LLM-provided melodic strategy.

Seven-step algorithm:
1. Beat grid setup (density-based or groove-driven)
2. Strong beat targeting (chord tones on downbeats)
3. Weak beat filling (diatonic passing/neighbor tones)
4. Contour shaping (~70/30 bias during pitch selection)
5. Collision avoidance (post-hoc against voicing events)
6. Phrase boundaries (rest_after handling)
7. Resolution rule (final note = chord tone of final chord)
"""

from __future__ import annotations

import contextlib
import logging
import re
from typing import TYPE_CHECKING, Any

from music21 import harmony
from music21 import pitch as m21pitch
from music21 import scale as m21scale
from ulid import ULID

from explorator.adapters.music21_adapter import _normalize_chord_symbol
from explorator.models.melody import (
    MelodicComplement,
    MelodicNoteEvent,
    MelodicStrategyResponse,
    PhraseInstruction,
)
from explorator.utils import pitch_str_to_midi, utc_now

if TYPE_CHECKING:
    from explorator.models.realization import VoicingEvent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Degree label → interval offset from root in semitones
_DEGREE_SEMITONES: dict[str, int] = {
    "root": 0,
    "2nd": 2,
    "3rd": 4,  # major 3rd; minor handled by chord lookup
    "4th": 5,
    "5th": 7,
    "6th": 9,
    "7th": 11,
}

_CONTOUR_BIAS = 0.70  # structural: preferred direction checked first, fallback to others


def _midi_to_pitch(midi: int) -> str:
    """Convert MIDI note number to pitch string (e.g. 60 → 'C5')."""
    p = m21pitch.Pitch()
    p.midi = midi
    return p.nameWithOctave


def _pitch_name(pitch_str: str) -> str:
    """Extract the note name (without octave) from a pitch string."""
    m = re.match(r"^([A-G][#\-b]?)", pitch_str)
    if not m:
        raise ValueError(f"Cannot extract note name from {pitch_str!r}")
    name = m.group(1).replace("b", "-")
    return name


def _chord_tones_midi(chord_symbol: str, octave_range: tuple[int, int]) -> list[int]:
    """Return all MIDI values of chord tones within the given MIDI range."""
    normalized = _normalize_chord_symbol(chord_symbol)
    try:
        chord = harmony.ChordSymbol(normalized)
        pitch_names = [p.name for p in chord.pitches]
    except Exception:
        # Fallback: just use root
        root = normalized[0] if normalized else "C"
        if len(normalized) >= 2 and normalized[1] in ("-", "#"):
            root = normalized[:2]
        pitch_names = [root]

    lo, hi = octave_range
    result: list[int] = []
    for name in pitch_names:
        try:
            base = m21pitch.Pitch(f"{name}0").midi
        except Exception:
            continue
        # Walk octaves to find all instances in range
        for oct in range(-1, 10):
            midi = base + oct * 12
            if midi < 0:
                continue
            if midi > 127:
                break
            if lo <= midi <= hi:
                result.append(midi)
    return sorted(set(result))


def _chord_tone_names(chord_symbol: str) -> set[str]:
    """Return set of pitch class names for a chord symbol."""
    normalized = _normalize_chord_symbol(chord_symbol)
    try:
        chord = harmony.ChordSymbol(normalized)
        return {p.name for p in chord.pitches}
    except Exception:
        root = normalized[0] if normalized else "C"
        if len(normalized) >= 2 and normalized[1] in ("-", "#"):
            root = normalized[:2]
        return {root}


def _build_scale(key_center: str, mode: str) -> list[str]:
    """Return the scale pitch names for the key/mode."""
    key_center_norm = key_center.replace("b", "-")
    sc: Any
    if mode in ("minor", "aeolian"):
        sc = m21scale.MinorScale(key_center_norm)  # type: ignore[no-untyped-call]
    elif mode == "dorian":
        sc = m21scale.DorianScale(key_center_norm)  # type: ignore[no-untyped-call]
    elif mode == "mixolydian":
        sc = m21scale.MixolydianScale(key_center_norm)  # type: ignore[no-untyped-call]
    else:
        sc = m21scale.MajorScale(key_center_norm)  # type: ignore[no-untyped-call]
    return [p.name for p in sc.getPitches(key_center_norm + "1", key_center_norm + "8")]


def _scale_midi_in_range(scale_names: list[str], lo: int, hi: int) -> list[int]:
    """All MIDI notes from scale_names within [lo, hi]."""
    result: list[int] = []
    for name in set(scale_names):
        try:
            base = m21pitch.Pitch(f"{name}0").midi
        except Exception:
            continue
        for oct in range(-1, 10):
            midi = base + oct * 12
            if midi < 0:
                continue
            if midi > 127:
                break
            if lo <= midi <= hi:
                result.append(midi)
    return sorted(set(result))


def _nearest_chord_tone(
    target_midi: int, chord_midis: list[int]
) -> int:
    """Find the chord tone nearest to target_midi."""
    if not chord_midis:
        return target_midi
    return min(chord_midis, key=lambda m: abs(m - target_midi))


def _is_downbeat(beat: float) -> bool:
    return beat in (1.0, 3.0)


def _contour_direction(
    contour: str, position_frac: float, beat_index: int
) -> int:
    """Return desired direction: +1 (up), -1 (down), 0 (no preference).

    position_frac: 0.0 to 1.0 within the phrase.
    """
    if contour == "ascending":
        return 1
    elif contour == "descending":
        return -1
    elif contour == "arch":
        return 1 if position_frac < 0.5 else -1
    elif contour == "wave":
        # Alternate every 2 beats
        return 1 if (beat_index // 2) % 2 == 0 else -1
    else:  # static or unknown
        return 0


def _pick_with_contour_bias(
    candidates: list[int],
    prev_midi: int,
    direction: int,
) -> int:
    """Pick from candidates biased toward the contour direction.

    Uses ~70/30 split: prefer candidates in the contour direction,
    but allow others.
    """
    if not candidates:
        return prev_midi
    if direction == 0 or prev_midi is None:
        # No bias: pick closest to prev
        return min(candidates, key=lambda m: abs(m - prev_midi) if prev_midi else 0)

    # Split into preferred (matching direction) and other
    if direction > 0:
        preferred = [m for m in candidates if m > prev_midi]
        [m for m in candidates if m <= prev_midi]
    else:
        preferred = [m for m in candidates if m < prev_midi]
        [m for m in candidates if m >= prev_midi]

    if preferred:
        # Pick the closest in the preferred direction
        return min(preferred, key=lambda m: abs(m - prev_midi))
    # Fall back to closest overall
    return min(candidates, key=lambda m: abs(m - prev_midi))


def _filter_by_motion(
    candidates: list[int], prev_midi: int | None, motion: str
) -> list[int]:
    """Filter candidates based on motion preference (interval limits)."""
    if prev_midi is None:
        return candidates
    if motion == "stepwise":
        max_interval = 4  # up to major 3rd (generous for stepwise to allow 2nds easily)
    elif motion == "leaping":
        max_interval = 9  # up to major 6th
    else:  # mixed
        max_interval = 7  # up to perfect 5th

    filtered = [m for m in candidates if abs(m - prev_midi) <= max_interval]
    # If filtering leaves nothing, relax constraint
    return filtered if filtered else candidates


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


class MelodyGenerator:
    """Deterministic melody realization engine.

    Takes a Gemini-generated MelodicStrategyResponse and produces
    concrete MelodicNoteEvent objects through a 7-step algorithm.
    """

    def realize(
        self,
        strategy: MelodicStrategyResponse,
        chord_symbols: list[str],
        key_center: str,
        mode: str,
        voicing_events: list[VoicingEvent],
        beat_grid: list[dict[str, Any]] | None,
        motion_preference: str,
    ) -> MelodicComplement:
        """Generate a melodic complement from strategy and harmonic context."""
        if not chord_symbols:
            return self._empty_complement(strategy)

        range_lo = pitch_str_to_midi(strategy.range_low)
        range_hi = pitch_str_to_midi(strategy.range_high)
        scale_names = _build_scale(key_center, mode)
        scale_midis = _scale_midi_in_range(scale_names, range_lo, range_hi)

        # Index voicings by bar for collision checks
        voicing_by_bar: dict[int, list[int]] = {}
        for v in voicing_events:
            midis = []
            for p in v.pitches:
                with contextlib.suppress(ValueError):
                    midis.append(pitch_str_to_midi(p))
            voicing_by_bar.setdefault(v.bar, []).extend(midis)

        all_events: list[MelodicNoteEvent] = []
        prev_midi: int | None = None

        for phrase in strategy.phrase_instructions:
            phrase_events, prev_midi = self._realize_phrase(
                phrase=phrase,
                chord_symbols=chord_symbols,
                range_lo=range_lo,
                range_hi=range_hi,
                scale_midis=scale_midis,
                scale_names=scale_names,
                voicing_by_bar=voicing_by_bar,
                beat_grid=beat_grid,
                motion_preference=motion_preference,
                prev_midi=prev_midi,
            )
            all_events.extend(phrase_events)

        # Step 7: Resolution rule — final note must be chord tone of final chord
        if all_events:
            all_events = self._apply_resolution(
                all_events, chord_symbols[-1], range_lo, range_hi, voicing_by_bar, scale_midis
            )

        now = utc_now()
        return MelodicComplement(
            id=f"mc_{ULID()}",
            type="melodic_complement",
            status="draft",
            created_at=now,
            updated_at=now,
            arrangement_candidate_id="",
            note_events=all_events,
            range_low=strategy.range_low,
            range_high=strategy.range_high,
            contour_type=strategy.overall_contour,
        )

    # ------------------------------------------------------------------
    # Phrase realization
    # ------------------------------------------------------------------

    def _realize_phrase(
        self,
        phrase: PhraseInstruction,
        chord_symbols: list[str],
        range_lo: int,
        range_hi: int,
        scale_midis: list[int],
        scale_names: list[str],
        voicing_by_bar: dict[int, list[int]],
        beat_grid: list[dict[str, Any]] | None,
        motion_preference: str,
        prev_midi: int | None,
    ) -> tuple[list[MelodicNoteEvent], int | None]:
        """Realize a single phrase, returning events and last MIDI pitch."""
        start_bar = phrase.start_bar
        end_bar = min(phrase.end_bar, len(chord_symbols) - 1)

        # Step 1: Build beat positions for each bar
        bar_beats: list[tuple[int, float]] = []  # (bar_idx, beat)
        for bar_idx in range(start_bar, end_bar + 1):
            if bar_idx >= len(chord_symbols):
                break
            beats = self._beats_for_bar(
                bar_idx, phrase.density, beat_grid
            )
            for b in beats:
                bar_beats.append((bar_idx, b))

        # Step 6: Phrase boundaries — skip last beat if rest_after
        if phrase.rest_after and bar_beats:
            bar_beats = bar_beats[:-1]

        if not bar_beats:
            return [], prev_midi

        total_positions = len(bar_beats)
        events: list[MelodicNoteEvent] = []

        for idx, (bar_idx, beat) in enumerate(bar_beats):
            chord_sym = chord_symbols[bar_idx]
            chord_midis = _chord_tones_midi(chord_sym, (range_lo, range_hi))
            position_frac = idx / max(total_positions - 1, 1)

            # Steps 2-4 integrated: pick pitch
            if _is_downbeat(beat):
                # Step 2: Strong beat — chord tone targeting
                midi = self._pick_strong_beat(
                    phrase, chord_sym, chord_midis, prev_midi,
                    range_lo, range_hi, position_frac, idx, motion_preference,
                )
            else:
                # Step 3: Weak beat — diatonic passing/neighbor tones
                midi = self._pick_weak_beat(
                    scale_midis, prev_midi, motion_preference,
                    phrase.contour, position_frac, idx,
                )

            if midi is None:
                continue

            # Step 5: Collision avoidance (post-hoc per note)
            midi = self._avoid_collision(
                midi, bar_idx, voicing_by_bar, scale_midis, range_lo, range_hi
            )
            if midi is None:
                continue  # omit note (rest)

            pitch_str = _midi_to_pitch(midi)
            events.append(
                MelodicNoteEvent(
                    bar=bar_idx,
                    beat=beat,
                    duration_beats=self._duration_for_density(phrase.density, beat),
                    pitch=pitch_str,
                    velocity=80,
                )
            )
            prev_midi = midi

        return events, prev_midi

    # ------------------------------------------------------------------
    # Step 1: Beat grid
    # ------------------------------------------------------------------

    def _beats_for_bar(
        self,
        bar_idx: int,
        density: str,
        beat_grid: list[dict[str, Any]] | None,
    ) -> list[float]:
        """Return beat positions for a bar, from groove grid or synthesized."""
        if beat_grid:
            return self._beats_from_groove(bar_idx, density, beat_grid)
        return self._synthesize_beats(density)

    def _synthesize_beats(self, density: str) -> list[float]:
        if density == "sparse":
            return [1.0, 3.0]
        elif density == "active":
            return [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5]
        else:  # moderate
            return [1.0, 2.0, 3.0, 4.0]

    def _beats_from_groove(
        self, bar_idx: int, density: str, beat_grid: list[dict[str, Any]]
    ) -> list[float]:
        """Convert absolute groove beats to per-bar, then filter by density."""
        bar_start = bar_idx * 4.0 + 1.0
        bar_end = bar_start + 4.0

        per_bar: list[float] = []
        for ev in beat_grid:
            abs_beat = ev.get("beat", 0.0)
            if bar_start <= abs_beat < bar_end:
                per_bar_beat = abs_beat - (bar_idx * 4.0)
                per_bar.append(per_bar_beat)

        # Apply density filtering
        allowed = set(self._synthesize_beats(density))
        # For groove: keep groove positions that pass density filter
        filtered = [b for b in per_bar if b in allowed]
        return sorted(filtered) if filtered else sorted(per_bar)

    # ------------------------------------------------------------------
    # Step 2: Strong beat
    # ------------------------------------------------------------------

    def _pick_strong_beat(
        self,
        phrase: PhraseInstruction,
        chord_sym: str,
        chord_midis: list[int],
        prev_midi: int | None,
        range_lo: int,
        range_hi: int,
        position_frac: float,
        beat_index: int,
        motion_preference: str,
    ) -> int | None:
        if not chord_midis:
            return None

        # Try to match strong_beat_targets
        target_midis = self._target_degree_midis(
            phrase.strong_beat_targets, chord_sym, range_lo, range_hi
        )
        candidates = target_midis if target_midis else chord_midis

        # Apply motion filter
        candidates = _filter_by_motion(candidates, prev_midi, motion_preference)

        # First note defaults to upper third of range
        if prev_midi is None:
            upper_third = range_lo + (range_hi - range_lo) * 2 // 3
            return _nearest_chord_tone(upper_third, candidates)

        # Apply contour bias
        direction = _contour_direction(phrase.contour, position_frac, beat_index)
        return _pick_with_contour_bias(candidates, prev_midi, direction)

    def _target_degree_midis(
        self,
        targets: list[str],
        chord_sym: str,
        range_lo: int,
        range_hi: int,
    ) -> list[int]:
        """Get MIDI pitches for the target degrees within range."""
        _chord_tone_names(chord_sym)
        normalized = _normalize_chord_symbol(chord_sym)

        try:
            chord = harmony.ChordSymbol(normalized)
            root_midi = chord.root().midi  # single octave reference
        except Exception:
            return []

        result: list[int] = []
        for target in targets:
            semitone_offset = _DEGREE_SEMITONES.get(target)
            if semitone_offset is None:
                continue
            target_pc = (root_midi + semitone_offset) % 12
            # Find all instances in range
            for midi in range(range_lo, range_hi + 1):
                if midi % 12 == target_pc:
                    result.append(midi)
            # If target degree not in chord tones, it's still valid as a target
            # (the spec says fall back to nearest chord tone)
            if not any(midi % 12 == target_pc for midi in range(range_lo, range_hi + 1)):
                # Use nearest chord tone instead
                all_chord = _chord_tones_midi(chord_sym, (range_lo, range_hi))
                result.extend(all_chord)

        return sorted(set(result)) if result else []

    # ------------------------------------------------------------------
    # Step 3: Weak beat
    # ------------------------------------------------------------------

    def _pick_weak_beat(
        self,
        scale_midis: list[int],
        prev_midi: int | None,
        motion_preference: str,
        contour: str,
        position_frac: float,
        beat_index: int,
    ) -> int | None:
        if not scale_midis:
            return None
        if prev_midi is None:
            # Default to middle of range
            return scale_midis[len(scale_midis) // 2]

        candidates = _filter_by_motion(scale_midis, prev_midi, motion_preference)
        direction = _contour_direction(contour, position_frac, beat_index)
        return _pick_with_contour_bias(candidates, prev_midi, direction)

    # ------------------------------------------------------------------
    # Step 5: Collision avoidance
    # ------------------------------------------------------------------

    def _avoid_collision(
        self,
        midi: int,
        bar: int,
        voicing_by_bar: dict[int, list[int]],
        scale_midis: list[int],
        range_lo: int,
        range_hi: int,
    ) -> int | None:
        """Check for unison/minor-2nd collision; shift diatonically if needed."""
        v_midis = voicing_by_bar.get(bar, [])
        if not v_midis:
            return midi

        def _collides(m: int) -> bool:
            return any(abs(m - vm) <= 1 for vm in v_midis)

        if not _collides(midi):
            return midi

        # Try shifting up diatonically
        upper = [s for s in scale_midis if s > midi and s <= range_hi]
        for candidate in upper:
            if not _collides(candidate):
                return candidate

        # Try shifting down
        lower = [s for s in reversed(scale_midis) if s < midi and s >= range_lo]
        for candidate in lower:
            if not _collides(candidate):
                return candidate

        # Both failed: omit note
        return None

    # ------------------------------------------------------------------
    # Step 7: Resolution
    # ------------------------------------------------------------------

    def _apply_resolution(
        self,
        events: list[MelodicNoteEvent],
        final_chord: str,
        range_lo: int,
        range_hi: int,
        voicing_by_bar: dict[int, list[int]],
        scale_midis: list[int],
    ) -> list[MelodicNoteEvent]:
        """Ensure final note is a chord tone of the final chord, preferring root/5th."""
        last = events[-1]
        last_midi = pitch_str_to_midi(last.pitch)
        chord_names = _chord_tone_names(final_chord)
        last_name = _pitch_name(last.pitch)

        if last_name in chord_names:
            return events  # already good

        # Prefer root or 5th
        normalized = _normalize_chord_symbol(final_chord)
        try:
            chord = harmony.ChordSymbol(normalized)
            root_name = chord.root().name
        except Exception:
            root_name = normalized[0] if normalized else "C"

        # Get root and 5th MIDI in range, nearest to current last note
        preferred: list[int] = []
        for offset in (0, 7):  # root, 5th
            try:
                base_midi = m21pitch.Pitch(f"{root_name}0").midi + offset
            except Exception:
                continue
            for oct in range(-1, 10):
                m = base_midi + oct * 12
                if range_lo <= m <= range_hi:
                    preferred.append(m)

        # Fall back to any chord tone
        all_chord = _chord_tones_midi(final_chord, (range_lo, range_hi))

        candidates = preferred if preferred else all_chord
        if not candidates:
            return events

        best = _nearest_chord_tone(last_midi, candidates)

        # Check collision
        bar = last.bar
        v_midis = voicing_by_bar.get(bar, [])

        def _collides(m: int) -> bool:
            return any(abs(m - vm) <= 1 for vm in v_midis)

        if _collides(best):
            # Try other candidates
            non_colliding = [c for c in all_chord if not _collides(c)]
            if non_colliding:
                best = _nearest_chord_tone(last_midi, non_colliding)
            else:
                return events  # can't resolve without collision, keep as is

        events[-1] = MelodicNoteEvent(
            bar=last.bar,
            beat=last.beat,
            duration_beats=last.duration_beats,
            pitch=_midi_to_pitch(best),
            velocity=last.velocity,
        )
        return events

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------

    def _duration_for_density(self, density: str, beat: float) -> float:
        """Assign duration based on density."""
        if density == "sparse":
            return 2.0
        elif density == "active":
            return 0.5
        else:
            return 1.0

    def _empty_complement(self, strategy: MelodicStrategyResponse) -> MelodicComplement:
        now = utc_now()
        return MelodicComplement(
            id=f"mc_{ULID()}",
            type="melodic_complement",
            status="draft",
            created_at=now,
            updated_at=now,
            arrangement_candidate_id="",
            note_events=[],
            range_low=strategy.range_low,
            range_high=strategy.range_high,
            contour_type=strategy.overall_contour,
        )
