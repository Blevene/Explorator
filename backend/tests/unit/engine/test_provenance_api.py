"""Tests for the provenance GET endpoint."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from explorator.api.routes.sessions import router


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/v1")
    return app


class TestProvenanceEndpoint:
    """Tests for GET /sessions/{id}/provenance."""

    def test_provenance_returns_trace(self):
        app = _make_app()

        trace = {
            "id": "pt_1",
            "session_id": "sess_1",
            "events": [
                {"timestamp": "2026-04-12T00:00:00Z", "action": "generate", "object_id": "pc_1", "round_number": 1, "details": {}},
                {"timestamp": "2026-04-12T00:01:00Z", "action": "mutate", "object_id": "pc_2", "round_number": 2, "details": {}},
            ],
        }

        with patch(
            "explorator.api.routes.sessions.get_neo4j_driver",
            new=AsyncMock(return_value=MagicMock()),
        ), patch(
            "explorator.api.routes.sessions.ProvenanceTraceRepo"
        ) as MockRepo:
            MockRepo.return_value.get_by_session_id = AsyncMock(return_value=trace)

            client = TestClient(app)
            resp = client.get("/v1/sessions/sess_1/provenance")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["events"]) == 2
            assert data["events"][0]["action"] == "generate"

    def test_provenance_empty_when_no_trace(self):
        app = _make_app()

        with patch(
            "explorator.api.routes.sessions.get_neo4j_driver",
            new=AsyncMock(return_value=MagicMock()),
        ), patch(
            "explorator.api.routes.sessions.ProvenanceTraceRepo"
        ) as MockRepo:
            MockRepo.return_value.get_by_session_id = AsyncMock(return_value=None)

            client = TestClient(app)
            resp = client.get("/v1/sessions/sess_1/provenance")
            assert resp.status_code == 200
            data = resp.json()
            assert data["events"] == []
