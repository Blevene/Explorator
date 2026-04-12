"""Tests for ComparisonView repo and API route."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from explorator.graph.comparison_view_repo import ComparisonViewRepo
from explorator.models.export import ComparisonView


def _make_driver_with_records(records: list[dict]) -> MagicMock:
    """Build a mock AsyncDriver whose session().run() returns the given records."""
    driver = MagicMock()
    result_mock = AsyncMock()
    result_mock.single = AsyncMock(
        return_value=({"props": records[0]} if records else None)
    )
    result_mock.data = AsyncMock(
        return_value=[{"props": r} for r in records]
    )
    neo_session = AsyncMock()
    neo_session.run = AsyncMock(return_value=result_mock)
    driver.session.return_value.__aenter__ = AsyncMock(return_value=neo_session)
    driver.session.return_value.__aexit__ = AsyncMock(return_value=False)
    return driver


class TestComparisonViewRepo:
    """Unit tests for ComparisonViewRepo."""

    @pytest.mark.asyncio
    async def test_create_and_get(self):
        record = {
            "id": "cv_test1",
            "type": "comparison_view",
            "status": "active",
            "session_id": "sess_test",
            "candidate_ids": ["arr_1", "arr_2"],
            "comparison_axes": ["voice_leading", "tension_curve"],
            "labels": '{"arr_1": "A", "arr_2": "B"}',
        }
        driver = _make_driver_with_records([record])
        repo = ComparisonViewRepo(driver)

        view = ComparisonView(
            id="cv_test1",
            type="comparison_view",
            status="active",
            session_id="sess_test",
            candidate_ids=["arr_1", "arr_2"],
            comparison_axes=["voice_leading", "tension_curve"],
            labels={"arr_1": "A", "arr_2": "B"},
        )
        await repo.create(view)
        result = await repo.get_by_id("cv_test1")
        assert result is not None
        assert result["session_id"] == "sess_test"
        assert len(result["candidate_ids"]) == 2

    @pytest.mark.asyncio
    async def test_query_by_session(self):
        record = {
            "id": "cv_test2",
            "type": "comparison_view",
            "status": "active",
            "session_id": "sess_test2",
            "candidate_ids": ["arr_3"],
            "comparison_axes": ["playability"],
            "labels": '{"arr_3": "C"}',
        }
        driver = _make_driver_with_records([record])
        repo = ComparisonViewRepo(driver)

        view = ComparisonView(
            id="cv_test2",
            type="comparison_view",
            status="active",
            session_id="sess_test2",
            candidate_ids=["arr_3"],
            comparison_axes=["playability"],
            labels={"arr_3": "C"},
        )
        await repo.create(view)
        results = await repo.query_by_property("session_id", "sess_test2")
        assert len(results) >= 1


from fastapi import FastAPI
from fastapi.testclient import TestClient

from explorator.api.routes.comparisons import router


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/v1")
    return app


class TestComparisonRoute:
    """Unit tests for comparison POST endpoint."""

    def test_post_comparison_returns_201(self):
        """POST creates a comparison and returns 201 with id."""
        app = _make_app()

        with patch(
            "explorator.api.routes.comparisons.get_neo4j_driver",
            new=AsyncMock(return_value=MagicMock()),
        ):
            mock_driver = MagicMock()
            mock_neo_session = AsyncMock()
            mock_driver.session.return_value.__aenter__ = AsyncMock(return_value=mock_neo_session)
            mock_driver.session.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch(
                "explorator.api.routes.comparisons.ComparisonViewRepo"
            ) as MockRepo:
                MockRepo.return_value.create = AsyncMock()

                client = TestClient(app)
                resp = client.post(
                    "/v1/sessions/sess_1/comparisons",
                    json={
                        "candidate_ids": ["arr_1", "arr_2"],
                        "comparison_axes": ["voice_leading", "tension_curve"],
                        "labels": {"arr_1": "A", "arr_2": "B"},
                    },
                )
                assert resp.status_code == 201
                data = resp.json()
                assert "comparison_id" in data

    def test_post_comparison_requires_two_candidates(self):
        """POST with < 2 candidates returns 422."""
        app = _make_app()

        with patch(
            "explorator.api.routes.comparisons.get_neo4j_driver",
            new=AsyncMock(return_value=MagicMock()),
        ):
            client = TestClient(app)
            resp = client.post(
                "/v1/sessions/sess_1/comparisons",
                json={
                    "candidate_ids": ["arr_1"],
                    "comparison_axes": [],
                    "labels": {},
                },
            )
            assert resp.status_code == 422
