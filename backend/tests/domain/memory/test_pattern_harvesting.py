"""Tests for pattern harvesting abstractions and tag generation."""
from explorator.domain.memory.pattern_harvesting import (
    harvest_bass_pattern,
    harvest_finalist,
    harvest_groove_pattern,
    harvest_melody_pattern,
    harvest_progression_pattern,
    harvest_voicing_pattern,
)


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


def test_harvest_voicing_tags_and_abstracted():
    arr = {"id": "arr_01", "voicing_plan_id": "vp_01"}
    vp = {"id": "vp_01", "strategy": {"register_profile": "mid", "density": "medium", "voice_count": 4}}
    entry = harvest_voicing_pattern(
        arrangement=arr, voicing_plan=vp, scorecard=_scorecard(), genre="house", role="safest",
    )
    assert entry.pattern_type == "voicing"
    assert entry.abstracted_pattern == {"register_profile": "mid", "density": "medium", "voice_count": 4}
    assert {"role:safest", "register:mid", "density:medium", "voices:4"} <= set(entry.tags)


def test_harvest_bass_tags_and_abstracted():
    arr = {"id": "arr_01", "bass_line_id": "bl_01"}
    bl = {"id": "bl_01", "mode": "walking", "rhythmic_density": 0.65}
    entry = harvest_bass_pattern(
        arrangement=arr, bass_line=bl, scorecard=_scorecard(), genre="house", role="best_loop",
    )
    assert entry.pattern_type == "bass"
    assert entry.abstracted_pattern == {"mode": "walking", "rhythmic_density": 0.65}
    assert {"role:best_loop", "bass_mode:walking", "rhythmic_density:mid"} <= set(entry.tags)


def test_harvest_groove_tags_and_abstracted():
    arr = {"id": "arr_01", "groove_pattern_id": "gp_01"}
    g = {"id": "gp_01", "swing_level": 0.4, "syncopation_level": 0.6, "density": 0.7, "template_name": "house_basic"}
    entry = harvest_groove_pattern(
        arrangement=arr, groove=g, scorecard=_scorecard(), genre="house", role="safest",
    )
    assert entry.pattern_type == "groove"
    assert entry.abstracted_pattern == {"swing_level": 0.4, "syncopation_level": 0.6, "density": 0.7, "template_name": "house_basic"}
    assert {"swing:mid", "syncopation:mid", "density:high", "template:house_basic"} <= set(entry.tags)


def test_harvest_melody_tags_and_abstracted():
    arr = {"id": "arr_01", "melodic_complement_id": "mc_01"}
    m = {"id": "mc_01", "strategy": {"contour_type": "arch", "range_semitones": 14, "rhythmic_density": 0.5}}
    entry = harvest_melody_pattern(
        arrangement=arr, melody=m, scorecard=_scorecard(), genre="house", role="most_experimental",
    )
    assert entry.pattern_type == "melody"
    assert entry.abstracted_pattern == {"contour_type": "arch", "range_semitones": 14, "rhythmic_density": 0.5}
    assert {"role:most_experimental", "contour:arch", "range:medium", "melody_density:mid"} <= set(entry.tags)


def test_harvest_finalist_produces_one_entry_per_present_facet():
    arr = {
        "id": "arr_01", "progression_candidate_id": "prog_01",
        "voicing_plan_id": "vp_01", "bass_line_id": "bl_01",
        "groove_pattern_id": "gp_01", "melodic_complement_id": "mc_01",
    }
    entries = harvest_finalist(
        arrangement=arr,
        progression=_progression(),
        voicing_plan={"id": "vp_01", "strategy": {"register_profile": "mid", "density": "medium", "voice_count": 4}},
        bass_line={"id": "bl_01", "mode": "walking", "rhythmic_density": 0.6},
        groove={"id": "gp_01", "swing_level": 0.4, "syncopation_level": 0.5, "density": 0.7, "template_name": "house_basic"},
        melody={"id": "mc_01", "strategy": {"contour_type": "arch", "range_semitones": 14, "rhythmic_density": 0.5}},
        scorecard=_scorecard(), genre="house", role="safest",
    )
    assert sorted(e.pattern_type for e in entries) == ["bass", "groove", "melody", "progression", "voicing"]


def test_harvest_finalist_skips_missing_facets():
    arr = {"id": "arr_01", "progression_candidate_id": "prog_01"}
    entries = harvest_finalist(
        arrangement=arr, progression=_progression(),
        voicing_plan=None, bass_line=None, groove=None, melody=None,
        scorecard=_scorecard(), genre="house", role="safest",
    )
    assert [e.pattern_type for e in entries] == ["progression"]
