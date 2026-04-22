"""Tests for pattern harvesting abstractions and tag generation.

Fixtures mirror the *actual* source-node shapes produced by the graph pipeline
(see models/{harmony,realization,groove,melody}.py). The earlier revision of
this file used a made-up shape; the extractor was written against it and
silently produced default-filled rows in production. See
docs/manual-test/m5d2-pattern-library.md for the full diagnosis.
"""
from explorator.domain.memory.pattern_harvesting import (
    harvest_bass_pattern,
    harvest_finalist,
    harvest_groove_pattern,
    harvest_melody_pattern,
    harvest_progression_pattern,
    harvest_voicing_pattern,
)


# --- Fixtures ---------------------------------------------------------------


def _arrangement(arr_id: str = "arr_01") -> dict:
    return {"id": arr_id, "progression_candidate_id": "prog_01"}


def _progression(
    *,
    chord_symbols: list[str] | None = None,
    roman_numerals: list[str] | None = None,
    bars: int = 4,
) -> dict:
    """A ProgressionCandidate dict as emitted by the harmony generator.

    Chord symbols are embedded in `chord_events[*].symbol`; Roman numerals
    live in `metadata.roman_numeral_analysis.analysis_events[*].symbol`
    (set by `domain/harmony/generator.py` via `rna.model_dump()`). The flat
    top-level `chord_symbols` / `roman_numerals` fields default to [] in practice.
    """
    symbols = chord_symbols or ["Cmaj7", "Am7", "Dm7", "G7"]
    romans = roman_numerals or ["Imaj7", "vi7", "ii7", "V7"]
    return {
        "id": "prog_01",
        "key_center": "C",
        "mode": "major",
        "phrase_length_bars": bars,
        "chord_symbols": [],          # intentionally empty — real state shape
        "roman_numerals": [],         # intentionally empty — real state shape
        "chord_events": [
            {"bar": i + 1, "symbol": s, "duration_beats": 4.0}
            for i, s in enumerate(symbols)
        ],
        "metadata": {
            "roman_numeral_analysis": {
                "analysis_events": [
                    {"bar": i + 1, "symbol": r}
                    for i, r in enumerate(romans)
                ],
            },
        },
    }


def _bass_line(
    *,
    style_mode: str = "supportive",
    rhythmic_density: str | float = "low",
    contour_type: str = "mostly_stepwise",
    relationship: str = "stabilizing",
    note_events: list[dict] | None = None,
) -> dict:
    """A BassLine dict as persisted by the graph (flat, no `mode` key)."""
    if note_events is None:
        note_events = [
            {"bar": 1, "beat": 1.0, "pitch": "C2", "duration_beats": 2.0},
            {"bar": 1, "beat": 3.0, "pitch": "G2", "duration_beats": 2.0},
        ]
    return {
        "id": "bl_01",
        "progression_candidate_id": "prog_01",
        "style_mode": style_mode,
        "contour_type": contour_type,
        "rhythmic_density": rhythmic_density,
        "relationship_to_harmony": relationship,
        "note_events": note_events,
    }


def _groove(
    *,
    swing_amount: float = 0.4,
    density: float | str = 0.6,
    source_template: str = "house_basic",
    pattern_events: list[dict] | None = None,
) -> dict:
    """A GroovePattern dict. Note: swing_amount (not swing_level);
    source_template (not template_name); NO syncopation_level field."""
    if pattern_events is None:
        pattern_events = [
            {"beat": 1.0, "duration_beats": 0.5, "velocity": 100, "accent": True},
            {"beat": 2.5, "duration_beats": 0.5, "velocity": 70, "accent": False},
        ]
    return {
        "id": "gp_01",
        "genre": "house",
        "time_signature": "4/4",
        "swing_amount": swing_amount,
        "density": density,
        "pattern_events": pattern_events,
        "source_template": source_template,
    }


def _melody(
    *,
    contour_type: str = "arch",
    range_low: str = "C5",
    range_high: str = "C6",
    note_events: list[dict] | None = None,
) -> dict:
    """A MelodicComplement dict. All fields are flat; no `strategy` sub-object."""
    if note_events is None:
        note_events = [
            {"bar": 1, "beat": 1.0, "pitch": "E5", "duration_beats": 1.0},
            {"bar": 1, "beat": 2.0, "pitch": "G5", "duration_beats": 1.0},
            {"bar": 1, "beat": 3.0, "pitch": "A5", "duration_beats": 1.0},
            {"bar": 1, "beat": 4.0, "pitch": "G5", "duration_beats": 1.0},
        ]
    return {
        "id": "mc_01",
        "arrangement_candidate_id": "arr_01",
        "contour_type": contour_type,
        "range_low": range_low,
        "range_high": range_high,
        "note_events": note_events,
        "source_strategy": "",
    }


def _voicing_plan(
    *,
    density_level: str = "medium",
    register_profile: str = "mid_high",
    voicing_events: list[dict] | None = None,
) -> dict:
    """A VoicingPlan dict. Flat fields; no `strategy` sub-object;
    voice_count is derived from voicing_events[0].pitches."""
    if voicing_events is None:
        voicing_events = [
            {"bar": 1, "beat": 1.0, "chord_symbol": "Cmaj7",
             "pitches": ["C4", "E4", "G4", "B4"], "duration_beats": 4.0},
        ]
    return {
        "id": "vp_01",
        "progression_candidate_id": "prog_01",
        "instrument": "electric_piano",
        "global_strategy": "",
        "density_level": density_level,
        "register_profile": register_profile,
        "voicing_events": voicing_events,
    }


def _scorecard(weighted: float = 0.8, loopability: float = 0.85, pareto: bool = False) -> dict:
    scores = {"loopability": loopability, "cadence_quality": 0.85, "theoretical_coherence": 0.75}
    return {
        "weighted_total": weighted,
        "scores": scores,
        "pareto_tags": ["pareto_front"] if pareto else [],
    }


# --- Progression tests ------------------------------------------------------


def test_harvest_progression_extracts_symbols_from_chord_events():
    """chord_symbols should be derived from chord_events[*].symbol, not the empty
    top-level field (the real state shape — see fixture docstring)."""
    entry = harvest_progression_pattern(
        arrangement=_arrangement(), progression=_progression(),
        scorecard=_scorecard(), genre="house", role="safest",
    )
    assert entry.abstracted_pattern["chord_symbols"] == ["Cmaj7", "Am7", "Dm7", "G7"]


def test_harvest_progression_extracts_romans_from_analysis_events():
    """Roman numerals come from metadata.roman_numeral_analysis.analysis_events[*].symbol."""
    entry = harvest_progression_pattern(
        arrangement=_arrangement(), progression=_progression(),
        scorecard=_scorecard(), genre="house", role="safest",
    )
    assert entry.abstracted_pattern["roman_numerals"] == ["Imaj7", "vi7", "ii7", "V7"]


def test_harvest_progression_basic_fields():
    entry = harvest_progression_pattern(
        arrangement=_arrangement(), progression=_progression(),
        scorecard=_scorecard(), genre="house", role="safest",
    )
    assert entry.pattern_type == "progression"
    assert entry.genre == "house"
    assert entry.source_candidate_id == "arr_01"
    assert entry.abstracted_pattern["key_center"] == "C"
    assert entry.abstracted_pattern["mode"] == "major"
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
    entry = harvest_progression_pattern(
        arrangement=_arrangement(),
        progression=_progression(roman_numerals=["I", "vi", "IV", "I"]),
        scorecard=_scorecard(), genre="house", role="safest",
    )
    assert "cadence:plagal" in entry.tags


def test_harvest_progression_cadence_tag_half():
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


def test_harvest_progression_supports_legacy_top_level_fields():
    """If a caller passes chord_symbols / metadata.roman_numerals at the legacy
    top-level shape (as older state snapshots did), the extractor still works."""
    prog = {
        "id": "prog_01", "key_center": "G", "mode": "minor",
        "phrase_length_bars": 8,
        "chord_symbols": ["Gm", "Cm", "D", "Gm"],
        "metadata": {"roman_numerals": ["i", "iv", "V", "i"]},
    }
    entry = harvest_progression_pattern(
        arrangement=_arrangement(), progression=prog,
        scorecard=_scorecard(), genre="house", role="safest",
    )
    assert entry.abstracted_pattern["chord_symbols"] == ["Gm", "Cm", "D", "Gm"]
    assert entry.abstracted_pattern["roman_numerals"] == ["i", "iv", "V", "i"]
    assert "cadence:authentic" in entry.tags


# --- Voicing tests ----------------------------------------------------------


def test_harvest_voicing_reads_flat_density_level():
    """VoicingPlan is flat; reading from `strategy.density` (old shape) yields
    the default 'medium'. The real field is `density_level`."""
    arr = {"id": "arr_01", "voicing_plan_id": "vp_01"}
    entry = harvest_voicing_pattern(
        arrangement=arr, voicing_plan=_voicing_plan(density_level="full"),
        scorecard=_scorecard(), genre="house", role="safest",
    )
    assert entry.abstracted_pattern["density_level"] == "full"
    assert "density:full" in entry.tags


def test_harvest_voicing_reads_flat_register_profile():
    arr = {"id": "arr_01", "voicing_plan_id": "vp_01"}
    entry = harvest_voicing_pattern(
        arrangement=arr, voicing_plan=_voicing_plan(register_profile="high"),
        scorecard=_scorecard(), genre="house", role="safest",
    )
    assert entry.abstracted_pattern["register_profile"] == "high"
    assert "register:high" in entry.tags


def test_harvest_voicing_derives_voice_count_from_events():
    """voice_count isn't a field on VoicingPlan. Derive from first event's pitches len."""
    arr = {"id": "arr_01", "voicing_plan_id": "vp_01"}
    vp = _voicing_plan(voicing_events=[
        {"bar": 1, "beat": 1.0, "chord_symbol": "Cmaj7",
         "pitches": ["C4", "E4", "G4", "B4", "D5"], "duration_beats": 4.0},
    ])
    entry = harvest_voicing_pattern(
        arrangement=arr, voicing_plan=vp,
        scorecard=_scorecard(), genre="house", role="safest",
    )
    assert entry.abstracted_pattern["voice_count"] == 5
    assert "voices:5" in entry.tags


def test_harvest_voicing_abstracted_pattern_is_not_default_filled():
    """Integrity: realistic input must produce an abstract without all-default values."""
    arr = {"id": "arr_01", "voicing_plan_id": "vp_01"}
    entry = harvest_voicing_pattern(
        arrangement=arr, voicing_plan=_voicing_plan(),
        scorecard=_scorecard(), genre="house", role="safest",
    )
    ap = entry.abstracted_pattern
    assert ap["density_level"] == "medium"
    assert ap["register_profile"] == "mid_high"
    assert ap["voice_count"] == 4
    assert ap["instrument"] == "electric_piano"
    assert ap["event_count"] == 1


# --- Bass tests -------------------------------------------------------------


def test_harvest_bass_reads_style_mode_not_mode():
    """BassLine.style_mode is the field; the old extractor read `.mode`,
    always falling through to default 'root'."""
    arr = {"id": "arr_01", "bass_line_id": "bl_01"}
    entry = harvest_bass_pattern(
        arrangement=arr, bass_line=_bass_line(style_mode="walking"),
        scorecard=_scorecard(), genre="house", role="best_loop",
    )
    assert entry.abstracted_pattern["style_mode"] == "walking"
    assert "bass_mode:walking" in entry.tags


def test_harvest_bass_includes_contour_and_relationship():
    arr = {"id": "arr_01", "bass_line_id": "bl_01"}
    entry = harvest_bass_pattern(
        arrangement=arr,
        bass_line=_bass_line(contour_type="arpeggiated", relationship="driving"),
        scorecard=_scorecard(), genre="house", role="safest",
    )
    ap = entry.abstracted_pattern
    assert ap["contour_type"] == "arpeggiated"
    assert ap["relationship_to_harmony"] == "driving"
    assert "contour:arpeggiated" in entry.tags


def test_harvest_bass_includes_note_count_from_events():
    arr = {"id": "arr_01", "bass_line_id": "bl_01"}
    events = [{"bar": 1, "beat": b, "pitch": "C2", "duration_beats": 0.5}
              for b in (1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5)]
    entry = harvest_bass_pattern(
        arrangement=arr, bass_line=_bass_line(note_events=events),
        scorecard=_scorecard(), genre="house", role="safest",
    )
    assert entry.abstracted_pattern["note_count"] == 8


def test_harvest_bass_accepts_string_categorical_density():
    arr = {"id": "arr_01", "bass_line_id": "bl_01"}
    entry = harvest_bass_pattern(
        arrangement=arr, bass_line=_bass_line(rhythmic_density="low"),
        scorecard=_scorecard(), genre="dream_pop", role="safest",
    )
    assert isinstance(entry.abstracted_pattern["rhythmic_density"], float)
    assert "rhythmic_density:low" in entry.tags


def test_harvest_bass_supports_legacy_mode_field():
    """If a caller passes the legacy `mode` key, it should still work."""
    arr = {"id": "arr_01", "bass_line_id": "bl_01"}
    bl = {"id": "bl_01", "mode": "walking", "rhythmic_density": 0.65}
    entry = harvest_bass_pattern(
        arrangement=arr, bass_line=bl, scorecard=_scorecard(),
        genre="house", role="best_loop",
    )
    assert entry.abstracted_pattern["style_mode"] == "walking"
    assert "bass_mode:walking" in entry.tags


# --- Groove tests -----------------------------------------------------------


def test_harvest_groove_reads_swing_amount_not_swing_level():
    """GroovePattern.swing_amount is the field; old extractor read swing_level."""
    arr = {"id": "arr_01", "groove_pattern_id": "gp_01"}
    entry = harvest_groove_pattern(
        arrangement=arr, groove=_groove(swing_amount=0.75),
        scorecard=_scorecard(), genre="house", role="safest",
    )
    assert entry.abstracted_pattern["swing_amount"] == 0.75
    assert "swing:high" in entry.tags


def test_harvest_groove_reads_source_template_not_template_name():
    arr = {"id": "arr_01", "groove_pattern_id": "gp_01"}
    entry = harvest_groove_pattern(
        arrangement=arr, groove=_groove(source_template="amen_break"),
        scorecard=_scorecard(), genre="house", role="safest",
    )
    assert entry.abstracted_pattern["source_template"] == "amen_break"
    assert "template:amen_break" in entry.tags


def test_harvest_groove_omits_syncopation_level():
    """GroovePattern has no syncopation_level field. The extractor must not invent
    a fake 0.0 reading — drop the field from abstract + tags entirely."""
    arr = {"id": "arr_01", "groove_pattern_id": "gp_01"}
    entry = harvest_groove_pattern(
        arrangement=arr, groove=_groove(),
        scorecard=_scorecard(), genre="house", role="safest",
    )
    assert "syncopation_level" not in entry.abstracted_pattern
    assert not any(t.startswith("syncopation:") for t in entry.tags)


def test_harvest_groove_accepts_string_density():
    arr = {"id": "arr_01", "groove_pattern_id": "gp_01"}
    entry = harvest_groove_pattern(
        arrangement=arr, groove=_groove(density="medium"),
        scorecard=_scorecard(), genre="dream_pop", role="safest",
    )
    assert isinstance(entry.abstracted_pattern["density"], float)
    assert "density:mid" in entry.tags


def test_harvest_groove_includes_event_count():
    arr = {"id": "arr_01", "groove_pattern_id": "gp_01"}
    events = [{"beat": b, "duration_beats": 0.5, "velocity": 80, "accent": False}
              for b in (1.0, 1.5, 2.0, 2.5)]
    entry = harvest_groove_pattern(
        arrangement=arr, groove=_groove(pattern_events=events),
        scorecard=_scorecard(), genre="house", role="safest",
    )
    assert entry.abstracted_pattern["event_count"] == 4


def test_harvest_groove_supports_legacy_template_name_field():
    """If a caller passes the legacy template_name + swing_level keys, it should still work."""
    arr = {"id": "arr_01", "groove_pattern_id": "gp_01"}
    g = {
        "id": "gp_01", "swing_level": 0.3, "density": 0.7,
        "template_name": "house_basic",
    }
    entry = harvest_groove_pattern(
        arrangement=arr, groove=g, scorecard=_scorecard(),
        genre="house", role="safest",
    )
    assert entry.abstracted_pattern["swing_amount"] == 0.3
    assert entry.abstracted_pattern["source_template"] == "house_basic"
    assert "template:house_basic" in entry.tags


# --- Melody tests -----------------------------------------------------------


def test_harvest_melody_reads_flat_contour_type():
    """MelodicComplement.contour_type is flat; old extractor read strategy.contour_type."""
    arr = {"id": "arr_01", "melodic_complement_id": "mc_01"}
    entry = harvest_melody_pattern(
        arrangement=arr, melody=_melody(contour_type="Descending wave"),
        scorecard=_scorecard(), genre="dream_pop", role="safest",
    )
    assert entry.abstracted_pattern["contour_type"] == "Descending wave"
    assert "contour:Descending wave" in entry.tags


def test_harvest_melody_computes_range_semitones_from_pitches():
    """range_semitones is derived from range_low/range_high pitch strings (C5..C6 = 12)."""
    arr = {"id": "arr_01", "melodic_complement_id": "mc_01"}
    entry = harvest_melody_pattern(
        arrangement=arr, melody=_melody(range_low="C5", range_high="C6"),
        scorecard=_scorecard(), genre="dream_pop", role="safest",
    )
    assert entry.abstracted_pattern["range_semitones"] == 12
    assert "range:medium" in entry.tags


def test_harvest_melody_range_semitones_handles_accidentals():
    """Pitch parser must handle sharp/flat: F#4 -> G5 spans 13 semitones."""
    arr = {"id": "arr_01", "melodic_complement_id": "mc_01"}
    entry = harvest_melody_pattern(
        arrangement=arr, melody=_melody(range_low="F#4", range_high="G5"),
        scorecard=_scorecard(), genre="dream_pop", role="safest",
    )
    assert entry.abstracted_pattern["range_semitones"] == 13
    assert "range:medium" in entry.tags


def test_harvest_melody_includes_range_pitches_and_note_count():
    arr = {"id": "arr_01", "melodic_complement_id": "mc_01"}
    entry = harvest_melody_pattern(
        arrangement=arr, melody=_melody(),
        scorecard=_scorecard(), genre="dream_pop", role="safest",
    )
    ap = entry.abstracted_pattern
    assert ap["range_low"] == "C5"
    assert ap["range_high"] == "C6"
    assert ap["note_count"] == 4


def test_harvest_melody_range_semitones_zero_when_range_missing():
    """If range_low/range_high are empty strings (default), semitones = 0 and
    the range tag falls into 'narrow' bucket without crashing."""
    arr = {"id": "arr_01", "melodic_complement_id": "mc_01"}
    entry = harvest_melody_pattern(
        arrangement=arr, melody=_melody(range_low="", range_high=""),
        scorecard=_scorecard(), genre="dream_pop", role="safest",
    )
    assert entry.abstracted_pattern["range_semitones"] == 0
    assert "range:narrow" in entry.tags


# --- Finalist orchestrator --------------------------------------------------


def test_harvest_finalist_produces_one_entry_per_present_facet():
    arr = {
        "id": "arr_01", "progression_candidate_id": "prog_01",
        "voicing_plan_id": "vp_01", "bass_line_id": "bl_01",
        "groove_pattern_id": "gp_01", "melodic_complement_id": "mc_01",
    }
    entries = harvest_finalist(
        arrangement=arr,
        progression=_progression(),
        voicing_plan=_voicing_plan(),
        bass_line=_bass_line(),
        groove=_groove(),
        melody=_melody(),
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


def test_harvest_finalist_no_entry_has_only_default_abstract():
    """Integrity: the 5 finalist entries for a realistic input must all have
    at least one field in their abstract that isn't the model's default value.
    This is the regression guard for the 2026-04-20 data-quality bug."""
    arr = {
        "id": "arr_01", "progression_candidate_id": "prog_01",
        "voicing_plan_id": "vp_01", "bass_line_id": "bl_01",
        "groove_pattern_id": "gp_01", "melodic_complement_id": "mc_01",
    }
    entries = harvest_finalist(
        arrangement=arr,
        progression=_progression(),
        voicing_plan=_voicing_plan(density_level="full", register_profile="high"),
        bass_line=_bass_line(style_mode="walking", rhythmic_density="high"),
        groove=_groove(swing_amount=0.7, source_template="breakbeat"),
        melody=_melody(contour_type="arch", range_low="C5", range_high="E6"),
        scorecard=_scorecard(), genre="house", role="safest",
    )
    by_type = {e.pattern_type: e for e in entries}
    assert by_type["progression"].abstracted_pattern["chord_symbols"]
    assert by_type["progression"].abstracted_pattern["roman_numerals"]
    assert by_type["voicing"].abstracted_pattern["density_level"] == "full"
    assert by_type["bass"].abstracted_pattern["style_mode"] == "walking"
    assert by_type["groove"].abstracted_pattern["source_template"] == "breakbeat"
    assert by_type["melody"].abstracted_pattern["contour_type"] == "arch"
