"""Pattern harvesting — abstracts finalist facets into PatternLibraryEntry rows.

Field paths mirror the actual persisted source-node shapes (see
models/{harmony,realization,groove,melody}.py):

- ProgressionCandidate: chord_events[*].symbol (top-level chord_symbols default [])
  + metadata.roman_numeral_analysis.analysis_events[*].symbol (set by the harmony
  generator at creation time; flat roman_numerals default []).
- BassLine: style_mode, contour_type, relationship_to_harmony, note_events
  (no `mode` field).
- MelodicComplement: flat contour_type, range_low/range_high pitch strings,
  note_events (no nested `strategy`).
- GroovePattern: swing_amount, density, source_template, pattern_events
  (no swing_level, no syncopation_level, no template_name).
- VoicingPlan: density_level, register_profile, voicing_events[0].pitches
  (no nested `strategy`, no voice_count field).

Each extractor accepts the legacy/test-only flat shape as a fallback so older
state snapshots (and callers that already use the simpler shape) keep working.
"""
from typing import Any

from ulid import ULID

from explorator.models.memory import PatternLibraryEntry
from explorator.utils import utc_now

# --- Tag helpers -----------------------------------------------------------------

def _bucket(value: float, low: float = 0.4, high: float = 0.7) -> str:
    if value >= high:
        return "high"
    if value >= low:
        return "mid"
    return "low"


_DENSITY_WORD_TO_FLOAT = {
    "sparse": 0.2, "low": 0.25, "medium": 0.5, "mid": 0.5,
    "moderate": 0.5, "high": 0.75, "dense": 0.8,
}


def _coerce_density(value: Any, default: float = 0.5) -> float:
    """Accept either a float or a string categorical ('low', 'sparse', 'medium', ...)."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return _DENSITY_WORD_TO_FLOAT.get(value.strip().lower(), default)
    return default


def _loopability_tag(value: float) -> str:
    return f"loopability:{_bucket(value)}"


def _cadence_tag(roman_numerals: list[str]) -> str | None:
    """Classify final two Roman numerals as authentic/plagal/half/deceptive/other."""
    if len(roman_numerals) < 2:
        return None
    penult, final = _root_only(roman_numerals[-2]), _root_only(roman_numerals[-1])
    # V → I and vii° → I both function as authentic (leading-tone substitute).
    if penult in ("V", "v", "vii", "VII") and final in ("I", "i"):
        return "cadence:authentic"
    if penult in ("IV", "iv") and final in ("I", "i"):
        return "cadence:plagal"
    if final in ("V", "v"):
        return "cadence:half"
    if penult in ("V", "v"):  # V → not-I (deceptive, e.g. V→vi)
        return "cadence:deceptive"
    return "cadence:other"


def _root_only(roman: str) -> str:
    """Strip qualities/extensions ('Imaj7' → 'I', 'V7' → 'V', 'vi7' → 'vi').

    Roman numerals use only I/V (or i/v) as degree letters. Anything else
    (m, maj, o, ø, +, digits) is a quality/extension and stops the scan.
    A leading b/# accidental is preserved.
    """
    result: list[str] = []
    first_alpha: str | None = None
    for ch in roman:
        if ch in ("b", "#") and not result:
            result.append(ch)
            continue
        if ch in ("I", "V", "i", "v"):
            # Enforce single case (uppercase = major, lowercase = minor).
            if first_alpha is None:
                first_alpha = ch
            elif ch.isupper() != first_alpha.isupper():
                break
            result.append(ch)
            continue
        break
    return "".join(result)


def _complexity_tag(distinct_chords: int) -> str:
    if distinct_chords >= 6:
        return "complexity:high"
    if distinct_chords >= 4:
        return "complexity:mid"
    return "complexity:low"


def _range_tag(semitones: int) -> str:
    if semitones >= 19:
        return "range:wide"
    if semitones >= 12:
        return "range:medium"
    return "range:narrow"


# --- Pitch helpers ---------------------------------------------------------------

_SEMITONES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def _pitch_to_midi(pitch: str) -> int | None:
    """Parse 'C5' / 'F#5' / 'Bb4' / 'B-4' into a MIDI note number.

    Accepts both 'b' and '-' as the flat accidental so the helper works for
    whatever form the LLM or music21 round-trip produces (see feedback memory
    on music21 using 'B-' internally).
    """
    if not isinstance(pitch, str) or not pitch:
        return None
    letter = pitch[0].upper()
    if letter not in _SEMITONES:
        return None
    base = _SEMITONES[letter]
    idx = 1
    accidental = 0
    while idx < len(pitch) and pitch[idx] in ("#", "b", "-"):
        accidental += 1 if pitch[idx] == "#" else -1
        idx += 1
    try:
        octave = int(pitch[idx:])
    except ValueError:
        return None
    return (octave + 1) * 12 + base + accidental


def _pitch_span(low: str, high: str) -> int:
    lo = _pitch_to_midi(low)
    hi = _pitch_to_midi(high)
    if lo is None or hi is None:
        return 0
    return max(0, hi - lo)


# --- Entity builder --------------------------------------------------------------

def _new_id() -> str:
    return f"pl_{ULID()}"


def _build_entry(
    *,
    pattern_type: str,
    arrangement: dict[str, Any],
    abstracted: dict[str, Any],
    tags: list[str],
    scorecard: dict[str, Any],
    genre: str,
) -> PatternLibraryEntry:
    """Shared constructor for all 5 per-type harvesters."""
    scores = scorecard.get("scores") or {}
    wt = scorecard.get("weighted_total")
    success_metrics: dict[str, float] = {
        "weighted_total": float(wt) if isinstance(wt, (int, float)) else 0.0,
        **{k: float(v) for k, v in scores.items() if isinstance(v, (int, float))},
    }
    now = utc_now()
    return PatternLibraryEntry(
        id=_new_id(),
        type="pattern_library_entry",
        created_at=now, updated_at=now,
        status="active", metadata={},
        pattern_type=pattern_type,
        genre=genre,
        tags=tags,
        source_candidate_id=arrangement["id"],
        abstracted_pattern=abstracted,
        success_metrics=success_metrics,
    )


# --- Per-type harvesters ---------------------------------------------------------

def _extract_chord_symbols(progression: dict[str, Any]) -> list[str]:
    """Prefer chord_events[*].symbol (real persisted shape); fall back to
    top-level chord_symbols for legacy snapshots."""
    events = progression.get("chord_events") or []
    from_events: list[str] = [
        sym for e in events if isinstance(sym := e.get("symbol"), str) and sym
    ]
    if from_events:
        return from_events
    return list(progression.get("chord_symbols") or [])


def _extract_roman_numerals(progression: dict[str, Any]) -> list[str]:
    """Prefer metadata.roman_numeral_analysis.analysis_events[*].symbol (real
    persisted shape, set by domain/harmony/generator.py); fall back to
    metadata.roman_numerals, then top-level roman_numerals."""
    meta = progression.get("metadata") or {}
    analysis = meta.get("roman_numeral_analysis") or {}
    events = analysis.get("analysis_events") or []
    from_events: list[str] = [
        sym for e in events
        if isinstance(e, dict) and isinstance(sym := e.get("symbol"), str) and sym
    ]
    if from_events:
        return from_events
    legacy_meta = meta.get("roman_numerals") or []
    if legacy_meta:
        return list(legacy_meta)
    return list(progression.get("roman_numerals") or [])


def harvest_progression_pattern(
    *,
    arrangement: dict[str, Any],
    progression: dict[str, Any],
    scorecard: dict[str, Any],
    genre: str,
    role: str,
) -> PatternLibraryEntry:
    scores = scorecard.get("scores") or {}
    chord_symbols = _extract_chord_symbols(progression)
    romans = _extract_roman_numerals(progression)

    tags: list[str] = [
        f"role:{role}",
        _loopability_tag(scores.get("loopability", 0.0)),
        _complexity_tag(len(set(chord_symbols))),
    ]
    if (cad := _cadence_tag(romans)) is not None:
        tags.append(cad)
    if "pareto_front" in (scorecard.get("pareto_tags") or []):
        tags.append("pareto_front")

    abstracted = {
        "key_center": progression.get("key_center"),
        "mode": progression.get("mode"),
        "chord_symbols": chord_symbols,
        "roman_numerals": romans,
        "phrase_length_bars": progression.get("phrase_length_bars"),
    }
    return _build_entry(
        pattern_type="progression", arrangement=arrangement,
        abstracted=abstracted, tags=tags, scorecard=scorecard, genre=genre,
    )


def harvest_voicing_pattern(
    *, arrangement: dict[str, Any], voicing_plan: dict[str, Any],
    scorecard: dict[str, Any], genre: str, role: str,
) -> PatternLibraryEntry:
    # Prefer flat fields (real persisted shape); fall back to nested `strategy`
    # for legacy test/state dicts.
    strategy = voicing_plan.get("strategy") or {}
    density = (
        voicing_plan.get("density_level")
        or strategy.get("density")
        or "medium"
    )
    register = (
        voicing_plan.get("register_profile")
        or strategy.get("register_profile")
        or "mid"
    )
    events = voicing_plan.get("voicing_events") or []
    voice_count = (
        len(events[0].get("pitches") or []) if events and isinstance(events[0], dict) else 0
    ) or strategy.get("voice_count") or 0

    tags = [
        f"role:{role}",
        f"register:{register}",
        f"density:{density}",
        f"voices:{voice_count}",
    ]
    abstracted = {
        "register_profile": register,
        "density_level": density,
        "voice_count": voice_count,
        "instrument": voicing_plan.get("instrument", ""),
        "event_count": len(events),
    }
    return _build_entry(
        pattern_type="voicing", arrangement=arrangement,
        abstracted=abstracted, tags=tags, scorecard=scorecard, genre=genre,
    )


def harvest_bass_pattern(
    *, arrangement: dict[str, Any], bass_line: dict[str, Any],
    scorecard: dict[str, Any], genre: str, role: str,
) -> PatternLibraryEntry:
    # BassLine.style_mode is the real field; older code / test fixtures used `mode`.
    style_mode = bass_line.get("style_mode") or bass_line.get("mode") or "supportive"
    contour = bass_line.get("contour_type", "")
    relationship = bass_line.get("relationship_to_harmony", "")
    density = _coerce_density(bass_line.get("rhythmic_density", 0.5))
    note_events = bass_line.get("note_events") or []

    tags = [
        f"role:{role}",
        f"bass_mode:{style_mode}",
        f"rhythmic_density:{_bucket(density)}",
    ]
    if contour:
        tags.append(f"contour:{contour}")
    if relationship:
        tags.append(f"relationship:{relationship}")

    abstracted = {
        "style_mode": style_mode,
        "contour_type": contour,
        "rhythmic_density": density,
        "relationship_to_harmony": relationship,
        "note_count": len(note_events),
    }
    return _build_entry(
        pattern_type="bass", arrangement=arrangement,
        abstracted=abstracted, tags=tags, scorecard=scorecard, genre=genre,
    )


def harvest_groove_pattern(
    *, arrangement: dict[str, Any], groove: dict[str, Any],
    scorecard: dict[str, Any], genre: str, role: str,
) -> PatternLibraryEntry:
    # GroovePattern uses swing_amount and source_template; drop the fake
    # syncopation_level that never existed on the node.
    swing = float(
        groove.get("swing_amount", groove.get("swing_level", 0.0)) or 0.0
    )
    density = _coerce_density(groove.get("density", 0.5))
    template = groove.get("source_template") or groove.get("template_name") or ""
    pattern_events = groove.get("pattern_events") or []

    tags = [
        f"role:{role}",
        f"swing:{_bucket(swing)}",
        f"density:{_bucket(density)}",
    ]
    if template:
        tags.append(f"template:{template}")
    abstracted = {
        "swing_amount": swing,
        "density": density,
        "source_template": template,
        "time_signature": groove.get("time_signature", "4/4"),
        "event_count": len(pattern_events),
    }
    return _build_entry(
        pattern_type="groove", arrangement=arrangement,
        abstracted=abstracted, tags=tags, scorecard=scorecard, genre=genre,
    )


def harvest_melody_pattern(
    *, arrangement: dict[str, Any], melody: dict[str, Any],
    scorecard: dict[str, Any], genre: str, role: str,
) -> PatternLibraryEntry:
    # MelodicComplement exposes flat fields; older code read a nested `strategy`.
    strategy = melody.get("strategy") or {}
    contour = melody.get("contour_type") or strategy.get("contour_type") or ""
    range_low = melody.get("range_low", "") or ""
    range_high = melody.get("range_high", "") or ""
    note_events = melody.get("note_events") or []

    range_semitones = _pitch_span(range_low, range_high)
    # Fall back to strategy.range_semitones only if we failed to compute it.
    if range_semitones == 0 and strategy.get("range_semitones"):
        range_semitones = int(strategy.get("range_semitones", 0))

    # Density: prefer strategy.rhythmic_density if supplied (legacy); else derive
    # from note_events (notes per beat, capped at 1.0). Default 0.0 for empty.
    if strategy.get("rhythmic_density") is not None:
        density = _coerce_density(strategy.get("rhythmic_density"))
    elif note_events:
        max_bar = max(
            (int(e.get("bar", 0)) for e in note_events if isinstance(e, dict)),
            default=1,
        )
        beats = max(1, max_bar * 4)
        density = min(1.0, len(note_events) / beats)
    else:
        density = 0.0

    tags = [
        f"role:{role}",
        _range_tag(range_semitones),
        f"melody_density:{_bucket(density)}",
    ]
    if contour:
        tags.append(f"contour:{contour}")

    abstracted = {
        "contour_type": contour,
        "range_low": range_low,
        "range_high": range_high,
        "range_semitones": range_semitones,
        "rhythmic_density": density,
        "note_count": len(note_events),
    }
    return _build_entry(
        pattern_type="melody", arrangement=arrangement,
        abstracted=abstracted, tags=tags, scorecard=scorecard, genre=genre,
    )


# --- Orchestrator ----------------------------------------------------------------

def harvest_finalist(
    *, arrangement: dict[str, Any], progression: dict[str, Any],
    voicing_plan: dict[str, Any] | None, bass_line: dict[str, Any] | None,
    groove: dict[str, Any] | None, melody: dict[str, Any] | None,
    scorecard: dict[str, Any], genre: str, role: str,
) -> list[PatternLibraryEntry]:
    entries: list[PatternLibraryEntry] = [
        harvest_progression_pattern(
            arrangement=arrangement, progression=progression,
            scorecard=scorecard, genre=genre, role=role,
        )
    ]
    if voicing_plan is not None:
        entries.append(harvest_voicing_pattern(
            arrangement=arrangement, voicing_plan=voicing_plan,
            scorecard=scorecard, genre=genre, role=role,
        ))
    if bass_line is not None:
        entries.append(harvest_bass_pattern(
            arrangement=arrangement, bass_line=bass_line,
            scorecard=scorecard, genre=genre, role=role,
        ))
    if groove is not None:
        entries.append(harvest_groove_pattern(
            arrangement=arrangement, groove=groove,
            scorecard=scorecard, genre=genre, role=role,
        ))
    if melody is not None:
        entries.append(harvest_melody_pattern(
            arrangement=arrangement, melody=melody,
            scorecard=scorecard, genre=genre, role=role,
        ))
    return entries
