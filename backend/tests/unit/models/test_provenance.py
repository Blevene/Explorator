"""Tests for ProvenanceEvent and ProvenanceTrace models."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from explorator.models.export import ProvenanceEvent, ProvenanceTrace


class TestProvenanceEvent:
    """Validate ProvenanceEvent structured creation."""

    def test_minimal_event(self):
        ev = ProvenanceEvent(
            timestamp=datetime(2026, 4, 12, tzinfo=timezone.utc),
            action="generate",
            object_id="pc_abc123",
        )
        assert ev.action == "generate"
        assert ev.round_number is None
        assert ev.details == {}

    def test_full_event(self):
        ev = ProvenanceEvent(
            timestamp=datetime(2026, 4, 12, tzinfo=timezone.utc),
            action="mutate",
            object_id="pc_abc123",
            round_number=2,
            details={"mutation_type": "substitute_chord", "source_id": "pc_xyz"},
        )
        assert ev.round_number == 2
        assert ev.details["mutation_type"] == "substitute_chord"

    def test_missing_required_fields_raises(self):
        with pytest.raises(ValidationError):
            ProvenanceEvent(action="generate")  # type: ignore[call-arg]

    def test_serialization_roundtrip(self):
        ev = ProvenanceEvent(
            timestamp=datetime(2026, 4, 12, tzinfo=timezone.utc),
            action="rank_and_select",
            object_id="session_123",
            round_number=1,
            details={"roles": {"a": "best"}},
        )
        data = ev.model_dump(mode="json")
        restored = ProvenanceEvent.model_validate(data)
        assert restored.action == ev.action
        assert restored.details == ev.details


class TestProvenanceTraceModel:
    """Validate ProvenanceTrace has session_id and events list."""

    def test_empty_trace(self):
        trace = ProvenanceTrace(
            id="pt_test",
            type="provenance_trace",
            status="active",
            session_id="sess_abc",
        )
        assert trace.events == []
        assert trace.session_id == "sess_abc"

    def test_trace_with_events(self):
        trace = ProvenanceTrace(
            id="pt_test",
            type="provenance_trace",
            status="active",
            session_id="sess_abc",
            events=[
                {"timestamp": "2026-04-12T00:00:00Z", "action": "generate", "object_id": "pc_1"},
            ],
        )
        assert len(trace.events) == 1


import pytest_asyncio
from neo4j import AsyncDriver

from explorator.graph.provenance_trace_repo import ProvenanceTraceRepo


@pytest.mark.skip(reason="Integration tests — require live Neo4j connection")
class TestProvenanceTraceRepo:
    """Integration tests for ProvenanceTraceRepo (requires Neo4j)."""

    @pytest_asyncio.fixture
    async def repo(self, neo4j_driver: AsyncDriver) -> ProvenanceTraceRepo:
        return ProvenanceTraceRepo(neo4j_driver)

    @pytest.mark.asyncio
    async def test_create_and_get(self, repo: ProvenanceTraceRepo):
        trace = ProvenanceTrace(
            id="pt_test1",
            type="provenance_trace",
            status="active",
            session_id="sess_test1",
            events=[],
        )
        await repo.create(trace)
        result = await repo.get_by_id("pt_test1")
        assert result is not None
        assert result["session_id"] == "sess_test1"

    @pytest.mark.asyncio
    async def test_append_events(self, repo: ProvenanceTraceRepo):
        trace = ProvenanceTrace(
            id="pt_test2",
            type="provenance_trace",
            status="active",
            session_id="sess_test2",
            events=[
                {"timestamp": "2026-04-12T00:00:00Z", "action": "generate", "object_id": "pc_1"},
            ],
        )
        await repo.create(trace)

        new_events = [
            {"timestamp": "2026-04-12T00:01:00Z", "action": "mutate", "object_id": "pc_2"},
            {"timestamp": "2026-04-12T00:02:00Z", "action": "rank_and_select", "object_id": "sess_test2"},
        ]
        await repo.append_events("pt_test2", new_events)

        result = await repo.get_by_id("pt_test2")
        assert result is not None
        assert len(result["events"]) == 3
        assert result["events"][0]["action"] == "generate"
        assert result["events"][2]["action"] == "rank_and_select"

    @pytest.mark.asyncio
    async def test_append_events_not_found(self, repo: ProvenanceTraceRepo):
        """append_events on nonexistent trace should raise."""
        with pytest.raises(ValueError, match="not found"):
            await repo.append_events("pt_nonexistent", [{"action": "test"}])

    @pytest.mark.asyncio
    async def test_get_by_session_id(self, repo: ProvenanceTraceRepo):
        trace = ProvenanceTrace(
            id="pt_test3",
            type="provenance_trace",
            status="active",
            session_id="sess_test3",
            events=[],
        )
        await repo.create(trace)
        result = await repo.get_by_session_id("sess_test3")
        assert result is not None
        assert result["id"] == "pt_test3"
