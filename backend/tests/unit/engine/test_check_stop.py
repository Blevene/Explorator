"""Tests for check_stop node."""

from explorator.engine.nodes.check_stop import check_stop


def _make_state(
    round_number: int = 1,
    max_rounds: int = 4,
    target_score: float = 8.5,
    scorecards: list | None = None,
    pareto_front: dict | None = None,
) -> dict:
    return {
        "round_number": round_number,
        "search_plan": {
            "stop_conditions": {
                "target_score": target_score,
                "max_rounds": max_rounds,
            },
        },
        "scorecards": scorecards or [],
        "pareto_front": pareto_front or {"candidate_ids": []},
    }


async def test_stop_on_quality_threshold() -> None:
    state = _make_state(
        scorecards=[{"weighted_total": 9.0, "candidate_id": "a"}],
    )
    result = await check_stop(state)
    assert result["stop_condition_met"] is True
    assert result["stop_reason"] == "quality"


async def test_stop_on_budget_exhausted() -> None:
    state = _make_state(
        round_number=4,
        max_rounds=4,
        scorecards=[{"weighted_total": 6.0, "candidate_id": "a"}],
    )
    result = await check_stop(state)
    assert result["stop_condition_met"] is True
    assert result["stop_reason"] == "budget"


async def test_no_stop_when_conditions_not_met() -> None:
    state = _make_state(
        round_number=1,
        scorecards=[{"weighted_total": 6.0, "candidate_id": "a"}],
    )
    result = await check_stop(state)
    assert result["stop_condition_met"] is False
    assert result["stop_reason"] == ""


async def test_stop_on_diversity() -> None:
    state = _make_state(
        scorecards=[{"weighted_total": 6.0, "candidate_id": "a"}],
        pareto_front={
            "candidate_ids": ["a", "b", "c"],
            "pairwise_diverse": True,
        },
    )
    result = await check_stop(state)
    assert result["stop_condition_met"] is True
    assert result["stop_reason"] == "diversity"


async def test_quality_checked_before_budget() -> None:
    """Quality threshold takes priority over budget."""
    state = _make_state(
        round_number=4,
        max_rounds=4,
        scorecards=[{"weighted_total": 9.0, "candidate_id": "a"}],
    )
    result = await check_stop(state)
    assert result["stop_reason"] == "quality"


async def test_stop_on_user_satisfaction() -> None:
    """Stop when recent feedback indicates positive satisfaction."""
    state = _make_state(
        scorecards=[{"weighted_total": 6.0, "candidate_id": "a"}],
    )
    state["feedback_history"] = [
        {
            "id": "fb_1",
            "candidate_id": "a",
            "interpreted_adjustments": {"satisfaction": "positive"},
        },
    ]
    result = await check_stop(state)
    assert result["stop_condition_met"] is True
    assert result["stop_reason"] == "satisfaction"


async def test_no_stop_on_neutral_feedback() -> None:
    """Neutral feedback does not trigger satisfaction stop."""
    state = _make_state(
        scorecards=[{"weighted_total": 6.0, "candidate_id": "a"}],
    )
    state["feedback_history"] = [
        {
            "id": "fb_1",
            "candidate_id": "a",
            "interpreted_adjustments": {"satisfaction": "neutral"},
        },
    ]
    result = await check_stop(state)
    assert result["stop_condition_met"] is False


async def test_old_positive_overridden_by_new_negative() -> None:
    """Later negative feedback overrides earlier positive satisfaction."""
    state = _make_state(
        scorecards=[{"weighted_total": 6.0, "candidate_id": "a"}],
    )
    state["feedback_history"] = [
        {
            "id": "fb_1",
            "candidate_id": "a",
            "interpreted_adjustments": {"satisfaction": "positive"},
        },
        {
            "id": "fb_2",
            "candidate_id": "a",
            "interpreted_adjustments": {"satisfaction": "negative"},
        },
    ]
    result = await check_stop(state)
    assert result["stop_condition_met"] is False
    assert result["stop_reason"] == ""
