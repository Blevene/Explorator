"""Pattern harvesting — abstracts finalist facets into PatternLibraryEntry rows."""
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


def _loopability_tag(value: float) -> str:
    return f"loopability:{_bucket(value)}"


def _cadence_tag(roman_numerals: list[str]) -> str | None:
    """Classify final two Roman numerals as authentic/plagal/half/deceptive/unknown."""
    if len(roman_numerals) < 2:
        return None
    penult, final = _root_only(roman_numerals[-2]), _root_only(roman_numerals[-1])
    if penult in ("V", "v") and final in ("I", "i"):
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

def harvest_progression_pattern(
    *,
    arrangement: dict[str, Any],
    progression: dict[str, Any],
    scorecard: dict[str, Any],
    genre: str,
    role: str,
) -> PatternLibraryEntry:
    scores = scorecard.get("scores") or {}
    romans = (progression.get("metadata") or {}).get("roman_numerals") or []
    chord_symbols = progression.get("chord_symbols") or []

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
