"""Tests for pattern harvesting abstractions and tag generation."""
from explorator.domain.memory.pattern_harvesting import harvest_progression_pattern


def _arrangement(arr_id: str = "arr_01") -> dict:
    return {"id": arr_id, "progression_candidate_id": "prog_01"}


def _progression(
    chord_symbols: list[str] | None = None,
    roman_numerals: list[str] | None = None,
    bars: int = 4,
) -> dict:
    return {
        "id": "prog_01",
        "key_center": "C",
        "mode": "major",
        "chord_symbols": chord_symbols or ["Cmaj7", "Am7", "Dm7", "G7"],
        "phrase_length_bars": bars,
        "metadata": {"roman_numerals": roman_numerals or ["Imaj7", "vi7", "ii7", "V7"]},
    }


def _scorecard(weighted: float = 0.8, loopability: float = 0.85, pareto: bool = False) -> dict:
    scores = {"loopability": loopability, "cadence_quality": 0.85, "theoretical_coherence": 0.75}
    return {
        "weighted_total": weighted,
        "scores": scores,
        "pareto_tags": ["pareto_front"] if pareto else [],
    }


def test_harvest_progression_basic_fields():
    entry = harvest_progression_pattern(
        arrangement=_arrangement(), progression=_progression(),
        scorecard=_scorecard(), genre="house", role="safest",
    )
    assert entry.pattern_type == "progression"
    assert entry.genre == "house"
    assert entry.source_candidate_id == "arr_01"
    assert entry.abstracted_pattern["chord_symbols"] == ["Cmaj7", "Am7", "Dm7", "G7"]
    assert entry.abstracted_pattern["roman_numerals"] == ["Imaj7", "vi7", "ii7", "V7"]
    assert entry.success_metrics["weighted_total"] == 0.8


def test_harvest_progression_role_and_loopability_tags():
    entry = harvest_progression_pattern(
        arrangement=_arrangement(), progression=_progression(),
        scorecard=_scorecard(loopability=0.2), genre="house", role="best_loop",
    )
    assert "role:best_loop" in entry.tags
    assert "loopability:low" in entry.tags


def test_harvest_progression_cadence_tag_authentic():
    """V → I (or V7 → Imaj7) final two chords → cadence:authentic."""
    entry = harvest_progression_pattern(
        arrangement=_arrangement(),
        progression=_progression(roman_numerals=["Imaj7", "vi7", "V7", "Imaj7"]),
        scorecard=_scorecard(), genre="house", role="safest",
    )
    assert "cadence:authentic" in entry.tags


def test_harvest_progression_cadence_tag_plagal():
    """IV → I final two → cadence:plagal."""
    entry = harvest_progression_pattern(
        arrangement=_arrangement(),
        progression=_progression(roman_numerals=["I", "vi", "IV", "I"]),
        scorecard=_scorecard(), genre="house", role="safest",
    )
    assert "cadence:plagal" in entry.tags


def test_harvest_progression_cadence_tag_half():
    """X → V final two → cadence:half."""
    entry = harvest_progression_pattern(
        arrangement=_arrangement(),
        progression=_progression(roman_numerals=["I", "vi", "ii", "V"]),
        scorecard=_scorecard(), genre="house", role="safest",
    )
    assert "cadence:half" in entry.tags


def test_harvest_progression_complexity_tag_buckets():
    """Complexity is bucketed by distinct-chord count: <=3 low, 4-5 mid, >=6 high."""
    low = harvest_progression_pattern(
        arrangement=_arrangement(),
        progression=_progression(
            chord_symbols=["C", "F", "C", "F"],
            roman_numerals=["I", "IV", "I", "IV"],
        ),
        scorecard=_scorecard(), genre="house", role="safest",
    )
    high = harvest_progression_pattern(
        arrangement=_arrangement(),
        progression=_progression(
            chord_symbols=["C", "Am", "F", "G", "Em", "Dm", "G7"],
            roman_numerals=["I", "vi", "IV", "V", "iii", "ii", "V7"],
        ),
        scorecard=_scorecard(), genre="house", role="safest",
    )
    assert "complexity:low" in low.tags
    assert "complexity:high" in high.tags


def test_harvest_progression_pareto_tag_propagates():
    entry = harvest_progression_pattern(
        arrangement=_arrangement(), progression=_progression(),
        scorecard=_scorecard(pareto=True), genre="house", role="safest",
    )
    assert "pareto_front" in entry.tags
