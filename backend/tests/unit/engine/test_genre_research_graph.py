"""Tests for genre research graph routing logic."""

from explorator.engine.genre_research_graph import route_after_critique, route_after_validate


class TestRouteAfterCritique:
    def test_needs_refine_first_iteration(self):
        state = {"needs_refine": True, "refine_iteration": 0}
        assert route_after_critique(state) == "refine"

    def test_needs_refine_second_iteration(self):
        state = {"needs_refine": True, "refine_iteration": 1}
        assert route_after_critique(state) == "refine"

    def test_needs_refine_at_max_goes_to_validate(self):
        state = {"needs_refine": True, "refine_iteration": 2}
        assert route_after_critique(state) == "validate"

    def test_no_refine_needed(self):
        state = {"needs_refine": False, "refine_iteration": 0}
        assert route_after_critique(state) == "validate"

    def test_missing_keys_defaults_to_validate(self):
        state = {}
        assert route_after_critique(state) == "validate"


class TestRouteAfterValidate:
    def test_always_routes_to_output(self):
        assert route_after_validate({}) == "output"
        assert route_after_validate({"validation_errors": ["some error"]}) == "output"
