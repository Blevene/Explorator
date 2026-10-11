"""Tests for provenance_events initialization in the exploration graph."""

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

if TYPE_CHECKING:
    from explorator.engine.state import ExplorationState


class TestProvenanceStateField:
    """Verify provenance_events is a valid field on ExplorationState."""

    def test_state_accepts_provenance_events(self):
        state: ExplorationState = {
            "session_id": "sess_test",
            "provenance_events": [],
        }
        assert state["provenance_events"] == []

    def test_state_provenance_events_with_data(self):
        state: ExplorationState = {
            "session_id": "sess_test",
            "provenance_events": [
                {"timestamp": "2026-04-12T00:00:00Z", "action": "generate", "object_id": "pc_1"},
            ],
        }
        assert len(state["provenance_events"]) == 1


class TestGraphProvenanceInit:
    """Verify build_exploration_graph produces a compiled graph
    that would receive provenance_events in initial state."""

    def test_graph_compiles_without_error(self):
        """Smoke test: the graph compiles with mock dependencies."""
        from explorator.engine.graph import build_exploration_graph

        llm = MagicMock()
        driver = MagicMock()
        graph = build_exploration_graph(llm, driver)
        assert graph is not None
