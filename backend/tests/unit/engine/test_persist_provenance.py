"""Tests for provenance persistence in persist_round node."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from explorator.engine.state import ExplorationState


def _make_state(**overrides) -> ExplorationState:
    base: ExplorationState = {
        "session_id": "sess_test",
        "prompt": "test",
        "genre": "dream_pop",
        "round_number": 1,
        "provenance_events": [],
        "top_progressions": [],
        "scorecards": [],
        "mutation_records": [],
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


class TestPersistRoundProvenance:
    """persist_round should write accumulated provenance events to ProvenanceTrace."""

    @pytest.mark.asyncio
    async def test_persist_round_creates_trace_on_first_run(self):
        from explorator.engine.nodes.persist_round import persist_round

        mock_driver = MagicMock()
        mock_neo_session = AsyncMock()
        mock_driver.session.return_value.__aenter__ = AsyncMock(return_value=mock_neo_session)
        mock_driver.session.return_value.__aexit__ = AsyncMock(return_value=False)

        events = [
            {"timestamp": "2026-04-12T00:00:00Z", "action": "generate", "object_id": "pc_1"},
        ]

        with patch(
            "explorator.graph.provenance_trace_repo.ProvenanceTraceRepo"
        ) as MockRepo, patch(
            "explorator.engine.nodes.persist_round.make_candidate_repo"
        ), patch(
            "explorator.engine.nodes.persist_round.make_search_round_repo"
        ) as MockSR, patch(
            "explorator.engine.nodes.persist_round.make_mutation_record_repo"
        ) as MockMR:
            repo_instance = MockRepo.return_value
            repo_instance.get_by_session_id = AsyncMock(return_value=None)
            repo_instance.create = AsyncMock()
            repo_instance.append_events = AsyncMock()

            MockSR.return_value.create = AsyncMock()
            MockMR.return_value.create = AsyncMock()

            state = _make_state(provenance_events=events)
            await persist_round(state, driver=mock_driver)

            # Should create a new trace (not append)
            repo_instance.create.assert_called_once()
            created_trace = repo_instance.create.call_args[0][0]
            assert created_trace.session_id == "sess_test"
            assert len(created_trace.events) == 1

    @pytest.mark.asyncio
    async def test_persist_round_appends_to_existing_trace(self):
        from explorator.engine.nodes.persist_round import persist_round

        mock_driver = MagicMock()
        mock_neo_session = AsyncMock()
        mock_driver.session.return_value.__aenter__ = AsyncMock(return_value=mock_neo_session)
        mock_driver.session.return_value.__aexit__ = AsyncMock(return_value=False)

        events = [
            {"timestamp": "2026-04-12T00:01:00Z", "action": "mutate", "object_id": "pc_2"},
        ]

        with patch(
            "explorator.graph.provenance_trace_repo.ProvenanceTraceRepo"
        ) as MockRepo, patch(
            "explorator.engine.nodes.persist_round.make_candidate_repo"
        ), patch(
            "explorator.engine.nodes.persist_round.make_search_round_repo"
        ) as MockSR, patch(
            "explorator.engine.nodes.persist_round.make_mutation_record_repo"
        ) as MockMR:
            repo_instance = MockRepo.return_value
            repo_instance.get_by_session_id = AsyncMock(return_value={
                "id": "pt_existing",
                "session_id": "sess_test",
                "events": [{"action": "generate"}],
            })
            repo_instance.append_events = AsyncMock()
            repo_instance.create = AsyncMock()

            MockSR.return_value.create = AsyncMock()
            MockMR.return_value.create = AsyncMock()

            state = _make_state(provenance_events=events)
            await persist_round(state, driver=mock_driver)

            # Should append, not create
            repo_instance.append_events.assert_called_once_with("pt_existing", events)
            repo_instance.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_persist_round_no_events_skips_provenance(self):
        from explorator.engine.nodes.persist_round import persist_round

        mock_driver = MagicMock()
        mock_neo_session = AsyncMock()
        mock_driver.session.return_value.__aenter__ = AsyncMock(return_value=mock_neo_session)
        mock_driver.session.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "explorator.graph.provenance_trace_repo.ProvenanceTraceRepo"
        ) as MockRepo, patch(
            "explorator.engine.nodes.persist_round.make_candidate_repo"
        ), patch(
            "explorator.engine.nodes.persist_round.make_search_round_repo"
        ) as MockSR, patch(
            "explorator.engine.nodes.persist_round.make_mutation_record_repo"
        ) as MockMR:
            repo_instance = MockRepo.return_value
            repo_instance.get_by_session_id = AsyncMock()
            repo_instance.create = AsyncMock()
            repo_instance.append_events = AsyncMock()

            MockSR.return_value.create = AsyncMock()
            MockMR.return_value.create = AsyncMock()

            state = _make_state(provenance_events=[])
            await persist_round(state, driver=mock_driver)

            # No provenance events — skip entirely
            repo_instance.get_by_session_id.assert_not_called()
            repo_instance.create.assert_not_called()
            repo_instance.append_events.assert_not_called()
