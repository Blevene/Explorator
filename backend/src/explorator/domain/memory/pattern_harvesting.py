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


def harvest_voicing_pattern(
    *, arrangement: dict[str, Any], voicing_plan: dict[str, Any],
    scorecard: dict[str, Any], genre: str, role: str,
) -> PatternLibraryEntry:
    strategy = voicing_plan.get("strategy") or {}
    register = strategy.get("register_profile", "mid")
    density = strategy.get("density", "medium")
    voice_count = strategy.get("voice_count", 4)
    tags = [f"role:{role}", f"register:{register}", f"density:{density}", f"voices:{voice_count}"]
    abstracted = {"register_profile": register, "density": density, "voice_count": voice_count}
    return _build_entry(
        pattern_type="voicing", arrangement=arrangement,
        abstracted=abstracted, tags=tags, scorecard=scorecard, genre=genre,
    )


def harvest_bass_pattern(
    *, arrangement: dict[str, Any], bass_line: dict[str, Any],
    scorecard: dict[str, Any], genre: str, role: str,
) -> PatternLibraryEntry:
    mode = bass_line.get("mode", "root")
    density = float(bass_line.get("rhythmic_density", 0.5))
    tags = [f"role:{role}", f"bass_mode:{mode}", f"rhythmic_density:{_bucket(density)}"]
    abstracted = {"mode": mode, "rhythmic_density": density}
    return _build_entry(
        pattern_type="bass", arrangement=arrangement,
        abstracted=abstracted, tags=tags, scorecard=scorecard, genre=genre,
    )


def harvest_groove_pattern(
    *, arrangement: dict[str, Any], groove: dict[str, Any],
    scorecard: dict[str, Any], genre: str, role: str,
) -> PatternLibraryEntry:
    swing = float(groove.get("swing_level", 0.0))
    sync = float(groove.get("syncopation_level", 0.0))
    density = float(groove.get("density", 0.5))
    template = groove.get("template_name", "")
    tags = [
        f"role:{role}",
        f"swing:{_bucket(swing)}",
        f"syncopation:{_bucket(sync)}",
        f"density:{_bucket(density)}",
    ]
    if template:
        tags.append(f"template:{template}")
    abstracted = {
        "swing_level": swing, "syncopation_level": sync,
        "density": density, "template_name": template,
    }
    return _build_entry(
        pattern_type="groove", arrangement=arrangement,
        abstracted=abstracted, tags=tags, scorecard=scorecard, genre=genre,
    )


def harvest_melody_pattern(
    *, arrangement: dict[str, Any], melody: dict[str, Any],
    scorecard: dict[str, Any], genre: str, role: str,
) -> PatternLibraryEntry:
    strategy = melody.get("strategy") or {}
    contour = strategy.get("contour_type", "")
    rng = int(strategy.get("range_semitones", 12))
    density = float(strategy.get("rhythmic_density", 0.5))
    tags = [
        f"role:{role}",
        f"contour:{contour}",
        _range_tag(rng),
        f"melody_density:{_bucket(density)}",
    ]
    abstracted = {"contour_type": contour, "range_semitones": rng, "rhythmic_density": density}
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
