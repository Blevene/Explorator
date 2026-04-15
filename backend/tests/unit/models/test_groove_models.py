"""Tests for groove domain models."""

import json

import pytest
from pydantic import ValidationError

from explorator.models.groove import (
    GrooveEvent,
    GroovePattern,
    GroovePreferences,
)

# ---------------------------------------------------------------------------
# GrooveEvent
# ---------------------------------------------------------------------------


def test_groove_event_defaults() -> None:
    evt = GrooveEvent(beat=1.0, duration_beats=0.5, velocity=80)
    assert evt.beat == 1.0
    assert evt.duration_beats == 0.5
    assert evt.velocity == 80
    assert evt.accent is False


def test_groove_event_with_accent() -> None:
    evt = GrooveEvent(beat=2.5, duration_beats=0.25, velocity=110, accent=True)
    assert evt.beat == 2.5
    assert evt.duration_beats == 0.25
    assert evt.velocity == 110
    assert evt.accent is True


def test_groove_event_requires_beat_duration_velocity() -> None:
    with pytest.raises(ValidationError):
        GrooveEvent(duration_beats=0.5, velocity=80)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        GrooveEvent(beat=1.0, velocity=80)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        GrooveEvent(beat=1.0, duration_beats=0.5)  # type: ignore[call-arg]


def test_groove_event_beat_positions() -> None:
    # Various 1.0-based beat positions
    for beat in [1.0, 1.5, 2.0, 2.5, 3.0, 4.0]:
        evt = GrooveEvent(beat=beat, duration_beats=0.5, velocity=64)
        assert evt.beat == beat


# ---------------------------------------------------------------------------
# GroovePattern
# ---------------------------------------------------------------------------


def _make_groove_pattern(**overrides) -> GroovePattern:
    defaults = dict(
        id="gp_01HXXXXXTEST",
        type="groove_pattern",
        status="active",
        session_id="sess_01",
        genre="jazz",
    )
    defaults.update(overrides)
    return GroovePattern(**defaults)


def test_groove_pattern_creation_minimal() -> None:
    gp = _make_groove_pattern()
    assert gp.id == "gp_01HXXXXXTEST"
    assert gp.type == "groove_pattern"
    assert gp.status == "active"
    assert gp.session_id == "sess_01"
    assert gp.genre == "jazz"
    # Defaults
    assert gp.arrangement_candidate_id is None
    assert gp.time_signature == "4/4"
    assert gp.swing_amount == 0.0
    assert gp.density == 0.5
    assert gp.pattern_events == []
    assert gp.source_template == "straight_eighths"
    assert gp.variation_seed is None


def test_groove_pattern_creation_all_fields() -> None:
    events = [
        GrooveEvent(beat=1.0, duration_beats=0.5, velocity=100, accent=True),
        GrooveEvent(beat=1.5, duration_beats=0.5, velocity=70),
        GrooveEvent(beat=2.0, duration_beats=0.5, velocity=90),
    ]
    gp = _make_groove_pattern(
        arrangement_candidate_id="arr_01",
        time_signature="3/4",
        swing_amount=0.3,
        density=0.7,
        pattern_events=events,
        source_template="swing_eighths",
        variation_seed=42,
    )
    assert gp.arrangement_candidate_id == "arr_01"
    assert gp.time_signature == "3/4"
    assert gp.swing_amount == 0.3
    assert gp.density == 0.7
    assert len(gp.pattern_events) == 3
    assert gp.pattern_events[0].accent is True
    assert gp.source_template == "swing_eighths"
    assert gp.variation_seed == 42


def test_groove_pattern_json_roundtrip() -> None:
    events = [GrooveEvent(beat=1.0, duration_beats=1.0, velocity=80)]
    gp = _make_groove_pattern(
        pattern_events=events,
        swing_amount=0.15,
        density=0.6,
        variation_seed=7,
    )
    serialized = gp.model_dump_json()
    data = json.loads(serialized)

    restored = GroovePattern.model_validate(data)
    assert restored.id == gp.id
    assert restored.genre == gp.genre
    assert restored.swing_amount == gp.swing_amount
    assert restored.density == gp.density
    assert restored.variation_seed == gp.variation_seed
    assert len(restored.pattern_events) == 1
    assert restored.pattern_events[0].beat == 1.0
    assert restored.pattern_events[0].velocity == 80


def test_groove_pattern_inherits_base_entity_fields() -> None:
    gp = _make_groove_pattern()
    # BaseEntity fields
    assert hasattr(gp, "created_at")
    assert hasattr(gp, "updated_at")
    assert gp.version == 1
    assert gp.metadata == {}


def test_groove_pattern_requires_session_genre() -> None:
    with pytest.raises(ValidationError):
        GroovePattern(
            id="gp_x",
            type="groove_pattern",
            status="active",
            genre="jazz",
            # missing session_id
        )
    with pytest.raises(ValidationError):
        GroovePattern(
            id="gp_x",
            type="groove_pattern",
            status="active",
            session_id="sess_01",
            # missing genre
        )


# ---------------------------------------------------------------------------
# GroovePreferences
# ---------------------------------------------------------------------------


def test_groove_preferences_defaults() -> None:
    prefs = GroovePreferences()
    assert prefs.comp_density == "medium"
    assert prefs.articulation_style == "straight"
    assert prefs.syncopation_level == "light"


def test_groove_preferences_from_genre_tendencies_full() -> None:
    tendencies = {
        "comp_density": "sparse",
        "articulation_style": "swung",
        "syncopation_level": "heavy",
    }
    prefs = GroovePreferences.from_genre_tendencies(tendencies)
    assert prefs.comp_density == "sparse"
    assert prefs.articulation_style == "swung"
    assert prefs.syncopation_level == "heavy"


def test_groove_preferences_from_genre_tendencies_partial() -> None:
    # Only some keys provided — defaults fill in the rest
    tendencies = {"comp_density": "dense"}
    prefs = GroovePreferences.from_genre_tendencies(tendencies)
    assert prefs.comp_density == "dense"
    assert prefs.articulation_style == "straight"  # default
    assert prefs.syncopation_level == "light"  # default


def test_groove_preferences_from_genre_tendencies_empty() -> None:
    prefs = GroovePreferences.from_genre_tendencies({})
    assert prefs.comp_density == "medium"
    assert prefs.articulation_style == "straight"
    assert prefs.syncopation_level == "light"


def test_groove_preferences_from_genre_tendencies_ignores_unknown_keys() -> None:
    tendencies = {
        "comp_density": "sparse",
        "unknown_key": "ignored_value",
    }
    prefs = GroovePreferences.from_genre_tendencies(tendencies)
    assert prefs.comp_density == "sparse"
    assert prefs.articulation_style == "straight"
