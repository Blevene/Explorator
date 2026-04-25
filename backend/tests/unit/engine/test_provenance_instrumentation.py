"""Tests for provenance event instrumentation in graph nodes."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from explorator.engine.state import ExplorationState


def _make_state(**overrides) -> ExplorationState:
    """Build a minimal ExplorationState with provenance_events initialized."""
    base: ExplorationState = {
        "session_id": "sess_test",
        "prompt": "dreamy chords",
        "genre": "dream_pop",
        "provenance_events": [],
        "round_number": 1,
        "n_candidates": 6,
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


class TestGenerateProvenance:
    """generate node should append a provenance event."""

    @pytest.mark.asyncio
    async def test_generate_appends_provenance_event(self):
        from explorator.engine.nodes.generate import generate

        mock_gemini = MagicMock()
        mock_candidate = MagicMock()
        mock_candidate.model_dump.return_value = {
            "id": "pc_1",
            "chord_symbols": ["C", "Am"],
        }

        with patch("explorator.engine.nodes.generate.HarmonyGenerator") as MockGen:
            instance = MockGen.return_value
            instance.generate = AsyncMock(return_value=[mock_candidate, mock_candidate])

            state = _make_state(
                creative_brief={"key_center": "C", "mode": "major", "phrase_length_bars": 4},
                genre_profile={},
            )
            result = await generate(state, gemini=mock_gemini)

        events = result.get("provenance_events", [])
        assert len(events) == 1
        assert events[0]["action"] == "generate"
        assert events[0]["details"]["candidate_count"] == 2
        assert "timestamp" in events[0]

    @pytest.mark.asyncio
    async def test_generate_preserves_existing_events(self):
        from explorator.engine.nodes.generate import generate

        mock_gemini = MagicMock()
        mock_candidate = MagicMock()
        mock_candidate.model_dump.return_value = {"id": "pc_1", "chord_symbols": ["C"]}

        with patch("explorator.engine.nodes.generate.HarmonyGenerator") as MockGen:
            instance = MockGen.return_value
            instance.generate = AsyncMock(return_value=[mock_candidate])

            existing_event = {"timestamp": "prior", "action": "test", "object_id": "x"}
            state = _make_state(
                creative_brief={"key_center": "C", "mode": "major", "phrase_length_bars": 4},
                genre_profile={},
                provenance_events=[existing_event],
            )
            result = await generate(state, gemini=mock_gemini)

        events = result.get("provenance_events", [])
        assert len(events) == 2
        assert events[0]["action"] == "test"
        assert events[1]["action"] == "generate"


class TestMutateProvenance:
    """mutate node should append a provenance event per mutation."""

    @pytest.mark.asyncio
    async def test_mutate_appends_provenance_events(self):
        from explorator.engine.nodes.mutate import mutate

        mock_gemini = MagicMock()
        mock_response = MagicMock()
        mock_response.mutated_chord_symbols = ["Dm7", "G7", "Cmaj7", "Am7"]
        mock_mutation = MagicMock()
        mock_mutation.operation = "substitute_chord"
        mock_mutation.position = 0
        mock_mutation.original_value = "C"
        mock_mutation.new_value = "Dm7"
        mock_mutation.description = "sub chord"
        mock_mutation.reason = "improve tension"
        mock_mutation.predicted_score_changes = []
        mock_response.mutations = [mock_mutation]

        with patch("explorator.engine.nodes.mutate.HarmonyMutator") as MockMut:
            instance = MockMut.return_value
            instance.mutate_harmonic = AsyncMock(return_value=mock_response)

            state = _make_state(
                progression_candidates=[
                    {
                        "id": "pc_1",
                        "chord_symbols": ["C", "Am", "F", "G"],
                        "metadata": {"scores": {"genre_fit": 7.0}},
                    },
                ],
                scorecards=[
                    {"candidate_id": "arr_1", "weighted_total": 7.5, "scores": {"genre_fit": 7.0}},
                ],
                arrangement_candidates=[
                    {"id": "arr_1", "progression_candidate_id": "pc_1"},
                ],
                search_plan={"mutation_budget_per_round": 2},
                pareto_front={"candidate_ids": ["arr_1"]},
                mutation_records=[],
                all_candidates_history=[],
                genre_profile={"genre": "dream_pop"},
            )
            result = await mutate(state, gemini=mock_gemini)

        events = result.get("provenance_events", [])
        assert len(events) >= 1
        mutate_events = [e for e in events if e["action"] == "mutate"]
        assert len(mutate_events) == 1
        assert "source_candidate_id" in mutate_events[0]["details"]


class TestRankAndSelectProvenance:
    """rank_and_select should append a provenance event."""

    @pytest.mark.asyncio
    async def test_rank_and_select_appends_provenance_event(self):
        from explorator.engine.nodes.rank_and_select import rank_and_select

        state = _make_state(
            arrangement_candidates=[
                {
                    "id": "arr_1",
                    "progression_candidate_id": "pc_1",
                    "status": "pending",
                },
            ],
            arrangement_families=[],
            progression_candidates=[
                {
                    "id": "pc_1",
                    "chord_symbols": ["C", "Am", "F", "G"],
                    "metadata": {"scores": {"genre_fit": 7.0}},
                },
            ],
            evaluations=[
                {
                    "arrangement_candidate_id": "arr_1",
                    "voice_leading": {"overall_score": 8.0},
                    "register_density": {"overall_score": 7.5},
                    "playability": {"overall_score": 8.5},
                },
            ],
            search_plan={"diversity_target": 0.65},
        )
        result = await rank_and_select(state)

        events = result.get("provenance_events", [])
        assert len(events) == 1
        assert events[0]["action"] == "rank_and_select"
        assert "role_assignments" in events[0]["details"]


class TestLoadMemoryProvenance:
    """load_memory should append a provenance event when feedback is loaded."""

    @pytest.mark.asyncio
    async def test_load_memory_appends_event_with_feedback(self):
        from explorator.engine.nodes.load_memory import load_memory

        mock_driver = MagicMock()

        with (
            patch("explorator.engine.nodes.load_memory.FeedbackEventRepo") as MockFB,
            patch("explorator.engine.nodes.load_memory.ObjectiveWeightsRepo") as MockOW,
        ):
            fb_instance = MockFB.return_value
            fb_instance.list_by_session = AsyncMock(
                return_value=[
                    {"id": "fb_1", "text": "more tension", "weight_deltas": {"tension_curve": 0.5}},
                ]
            )

            ow_instance = MockOW.return_value
            ow_instance.get_latest_for_session = AsyncMock(return_value=None)

            state = _make_state()
            result = await load_memory(state, driver=mock_driver)

        events = result.get("provenance_events", [])
        assert len(events) == 1
        assert events[0]["action"] == "feedback"
        assert events[0]["details"]["feedback_count"] == 1

    @pytest.mark.asyncio
    async def test_load_memory_no_event_without_feedback(self):
        from explorator.engine.nodes.load_memory import load_memory

        mock_driver = MagicMock()

        with (
            patch("explorator.engine.nodes.load_memory.FeedbackEventRepo") as MockFB,
            patch("explorator.engine.nodes.load_memory.ObjectiveWeightsRepo") as MockOW,
        ):
            fb_instance = MockFB.return_value
            fb_instance.list_by_session = AsyncMock(return_value=[])

            ow_instance = MockOW.return_value
            ow_instance.get_latest_for_session = AsyncMock(return_value=None)

            state = _make_state()
            result = await load_memory(state, driver=mock_driver)

        events = result.get("provenance_events", [])
        assert len(events) == 0
