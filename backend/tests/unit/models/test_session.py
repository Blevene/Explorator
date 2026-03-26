"""Tests for session domain models."""

from explorator.models.session import CreativeBrief, Session, SessionContext


def test_session_creation() -> None:
    session = Session(
        id="sess_01",
        type="session",
        status="active",
        mode="full_exploration",
    )
    assert session.id == "sess_01"
    assert session.mode == "full_exploration"
    assert session.creative_brief_id is None
    assert session.progression_candidate_ids == []


def test_creative_brief_creation() -> None:
    brief = CreativeBrief(
        id="brief_01",
        type="creative_brief",
        status="active",
        genre="dream_pop",
        mood_targets=["wistful", "haunted"],
        key_center="A",
        mode="major",
        phrase_length_bars=8,
        complexity_target="medium",
        novelty_target="moderate",
        generation_mode="balanced",
    )
    assert brief.genre == "dream_pop"
    assert brief.mood_targets == ["wistful", "haunted"]
    assert brief.phrase_length_bars == 8
    assert brief.generation_mode == "balanced"
    assert brief.meter == "4/4"
    assert brief.seed_melody_id is None


def test_session_context_creation() -> None:
    ctx = SessionContext(
        id="ctx_01",
        type="session_context",
        status="active",
        session_id="sess_01",
        active_phase="harmonic_generation",
        current_round=1,
        search_budget_remaining=12,
    )
    assert ctx.current_round == 1
    assert ctx.active_phase == "harmonic_generation"
