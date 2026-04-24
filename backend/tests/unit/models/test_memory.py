"""Tests for memory, feedback, and user preference models."""

import pytest
from pydantic import ValidationError

from explorator.models.memory import (
    PatternLibraryEntry,
    UserFeedbackEvent,
    UserPreferenceProfile,
)

# ---------------------------------------------------------------------------
# UserPreferenceProfile
# ---------------------------------------------------------------------------


def test_user_preference_profile_defaults() -> None:
    profile = UserPreferenceProfile(
        id="up_01",
        type="user_preference_profile",
        status="active",
    )
    assert profile.preferred_complexity_band == "medium"
    assert profile.preferred_novelty_band == "moderate"
    assert profile.voicing_preferences == {}
    assert profile.bass_preferences == {}
    assert profile.melodic_preferences == {}
    assert profile.genre_biases == {}
    assert profile.disliked_patterns == []


def test_user_preference_profile_with_data() -> None:
    profile = UserPreferenceProfile(
        id="up_02",
        type="user_preference_profile",
        status="active",
        preferred_complexity_band="high",
        preferred_novelty_band="adventurous",
        voicing_preferences={"open_voicings": True, "close_voicings": False},
        genre_biases={"dream_pop": 0.9, "jazz": 0.6},
        disliked_patterns=["tritone_substitution", "hard_bop_chains"],
    )
    assert profile.preferred_complexity_band == "high"
    assert profile.voicing_preferences["open_voicings"] is True
    assert profile.genre_biases["dream_pop"] == 0.9
    assert len(profile.disliked_patterns) == 2


def test_user_preference_profile_requires_id() -> None:
    with pytest.raises(ValidationError):
        UserPreferenceProfile(  # type: ignore[call-arg]
            type="user_preference_profile",
            status="active",
        )


# ---------------------------------------------------------------------------
# UserFeedbackEvent
# ---------------------------------------------------------------------------


def test_user_feedback_event_minimal() -> None:
    ev = UserFeedbackEvent(
        id="ufe_01",
        type="user_feedback_event",
        status="recorded",
        session_id="sess_01",
        candidate_id="arr_01",
    )
    assert ev.session_id == "sess_01"
    assert ev.candidate_id == "arr_01"
    assert ev.feedback_type == "text_reaction"
    assert ev.content == ""
    assert ev.interpreted_adjustments == {}


def test_user_feedback_event_with_content() -> None:
    ev = UserFeedbackEvent(
        id="ufe_02",
        type="user_feedback_event",
        status="recorded",
        session_id="sess_01",
        candidate_id="arr_01",
        feedback_type="rating",
        content="Love the open voicings but bass feels too busy",
        interpreted_adjustments={"bass_density": "reduce", "voicing_openness": "maintain"},
    )
    assert ev.feedback_type == "rating"
    assert "bass" in ev.content
    assert ev.interpreted_adjustments["bass_density"] == "reduce"


def test_user_feedback_event_requires_session_id() -> None:
    with pytest.raises(ValidationError):
        UserFeedbackEvent(
            id="ufe_03",
            type="user_feedback_event",
            status="recorded",
            candidate_id="arr_01",
        )  # type: ignore[call-arg]


def test_user_feedback_event_requires_candidate_id() -> None:
    with pytest.raises(ValidationError):
        UserFeedbackEvent(
            id="ufe_04",
            type="user_feedback_event",
            status="recorded",
            session_id="sess_01",
        )  # type: ignore[call-arg]


def test_user_feedback_event_has_weight_deltas() -> None:
    fb = UserFeedbackEvent(
        id="fb_1",
        type="user_feedback_event",
        status="active",
        session_id="sess_1",
        candidate_id="arr_1",
        content="bass is too busy",
        interpreted_adjustments={"reduce_bass_motion": True},
        weight_deltas={"playability": 0.04, "voice_leading": -0.02, "novelty": -0.02},
    )
    assert fb.weight_deltas["playability"] == 0.04
    assert fb.feedback_type == "text_reaction"


# ---------------------------------------------------------------------------
# PatternLibraryEntry
# ---------------------------------------------------------------------------


def test_pattern_library_entry_minimal() -> None:
    entry = PatternLibraryEntry(
        id="ple_01",
        type="pattern_library_entry",
        status="active",
        pattern_type="chord_color",
        genre="dream_pop",
        source_candidate_id="prog_01",
    )
    assert entry.pattern_type == "chord_color"
    assert entry.genre == "dream_pop"
    assert entry.tags == []
    assert entry.source_candidate_id == "prog_01"
    assert entry.abstracted_pattern == {}
    assert entry.success_metrics == {}
    assert entry.notes == ""


def test_pattern_library_entry_with_data() -> None:
    entry = PatternLibraryEntry(
        id="ple_02",
        type="pattern_library_entry",
        status="active",
        pattern_type="cadence",
        genre="shoegaze",
        tags=["plagal", "soft", "loop-friendly"],
        source_candidate_id="prog_07",
        abstracted_pattern={"motion": "IV-I", "quality": "major"},
        success_metrics={"genre_fit": 0.92, "loopability": 0.88},
        notes="Works well in 8-bar loops with open voicings",
    )
    assert len(entry.tags) == 3
    assert entry.source_candidate_id == "prog_07"
    assert entry.success_metrics["genre_fit"] == 0.92
    assert "8-bar" in entry.notes


def test_pattern_library_entry_requires_pattern_type() -> None:
    with pytest.raises(ValidationError):
        PatternLibraryEntry(
            id="ple_03",
            type="pattern_library_entry",
            status="active",
            genre="dream_pop",
        )  # type: ignore[call-arg]


def test_pattern_library_entry_requires_genre() -> None:
    with pytest.raises(ValidationError):
        PatternLibraryEntry(
            id="ple_04",
            type="pattern_library_entry",
            status="active",
            pattern_type="voicing",
        )  # type: ignore[call-arg]


def test_pattern_library_entry_requires_source_candidate_id() -> None:
    with pytest.raises(ValidationError):
        PatternLibraryEntry(
            id="pl_01",
            type="pattern_library_entry",
            status="active",
            pattern_type="progression",
            genre="house",
        )  # type: ignore[call-arg]


def test_pattern_library_entry_embedding_defaults_to_none() -> None:
    entry = PatternLibraryEntry(
        id="pl_01",
        type="pattern_library_entry",
        status="active",
        pattern_type="progression",
        genre="house",
        source_candidate_id="arr_01",
    )
    assert entry.embedding is None


def test_pattern_library_entry_accepts_embedding_list() -> None:
    entry = PatternLibraryEntry(
        id="pl_01",
        type="pattern_library_entry",
        status="active",
        pattern_type="progression",
        genre="house",
        source_candidate_id="arr_01",
        embedding=[0.1, 0.2, 0.3],
    )
    assert entry.embedding == [0.1, 0.2, 0.3]


def test_pattern_library_entry_curation_defaults() -> None:
    entry = PatternLibraryEntry(
        id="ple_05",
        type="pattern_library_entry",
        status="active",
        pattern_type="progression",
        genre="jazz",
        source_candidate_id="cand_x",
    )
    assert entry.is_curated is False
    assert entry.curated_at is None


def test_pattern_library_entry_curation_roundtrip() -> None:
    from datetime import datetime, timezone

    now = datetime(2026, 4, 24, 12, 0, tzinfo=timezone.utc)
    entry = PatternLibraryEntry(
        id="ple_06",
        type="pattern_library_entry",
        status="active",
        pattern_type="progression",
        genre="jazz",
        source_candidate_id="cand_x",
        is_curated=True,
        curated_at=now,
    )
    payload = entry.model_dump(mode="json")
    assert payload["is_curated"] is True
    # Pydantic serializes UTC as Z notation
    assert payload["curated_at"] == "2026-04-24T12:00:00Z"
