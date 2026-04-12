"""Tests for CandidateExplanation repo and API route."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from explorator.graph.candidate_explanation_repo import CandidateExplanationRepo
from explorator.models.export import CandidateExplanation


def _make_driver_with_records(records: list[dict]) -> MagicMock:
    """Build a mock AsyncDriver whose session().run() returns the given records."""
    driver = MagicMock()
    result_mock = AsyncMock()
    result_mock.single = AsyncMock(
        return_value=(
            {"props": records[0]} if records else None
        )
    )
    result_mock.data = AsyncMock(
        return_value=[{"props": r} for r in records]
    )
    neo_session = AsyncMock()
    neo_session.run = AsyncMock(return_value=result_mock)
    driver.session.return_value.__aenter__ = AsyncMock(return_value=neo_session)
    driver.session.return_value.__aexit__ = AsyncMock(return_value=False)
    return driver


class TestCandidateExplanationRepo:
    """Unit tests for CandidateExplanationRepo."""

    @pytest.mark.asyncio
    async def test_create_and_get(self):
        record = {
            "id": "ce_test1",
            "type": "candidate_explanation",
            "status": "active",
            "session_id": "sess_test",
            "candidate_id": "arr_test1",
            "summary": "A dreamy progression with modal interchange.",
            "why_it_works": ["Uses borrowed chords for color"],
            "what_is_experimental": ["Tritone sub in bar 3"],
            "recommended_use_cases": ["Intro section", "Bridge"],
        }
        driver = _make_driver_with_records([record])
        repo = CandidateExplanationRepo(driver)

        explanation = CandidateExplanation(
            id="ce_test1",
            type="candidate_explanation",
            status="active",
            session_id="sess_test",
            candidate_id="arr_test1",
            summary="A dreamy progression with modal interchange.",
            why_it_works=["Uses borrowed chords for color"],
            what_is_experimental=["Tritone sub in bar 3"],
            recommended_use_cases=["Intro section", "Bridge"],
        )
        await repo.create(explanation)
        result = await repo.get_by_id("ce_test1")
        assert result is not None
        assert result["summary"] == "A dreamy progression with modal interchange."

    @pytest.mark.asyncio
    async def test_get_by_candidate_id(self):
        record = {
            "id": "ce_test2",
            "type": "candidate_explanation",
            "status": "active",
            "session_id": "sess_test",
            "candidate_id": "arr_test2",
            "summary": "Smooth voice leading.",
        }
        driver = _make_driver_with_records([record])
        repo = CandidateExplanationRepo(driver)

        explanation = CandidateExplanation(
            id="ce_test2",
            type="candidate_explanation",
            status="active",
            session_id="sess_test",
            candidate_id="arr_test2",
            summary="Smooth voice leading.",
        )
        await repo.create(explanation)
        result = await repo.get_by_candidate_id("arr_test2")
        assert result is not None
        assert result["id"] == "ce_test2"

    @pytest.mark.asyncio
    async def test_get_by_candidate_id_not_found(self):
        driver = _make_driver_with_records([])
        repo = CandidateExplanationRepo(driver)

        result = await repo.get_by_candidate_id("nonexistent")
        assert result is None


from fastapi import FastAPI
from fastapi.testclient import TestClient

from explorator.api.routes.explanations import router


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/v1")
    return app


class TestExplanationRoute:
    """Unit tests for explanation endpoints using mocked dependencies."""

    def test_get_cached_explanation_404(self):
        """GET returns 404 when no explanation exists."""
        app = _make_app()

        with patch(
            "explorator.api.routes.explanations.get_neo4j_driver",
            new=AsyncMock(return_value=MagicMock()),
        ):
            with patch(
                "explorator.api.routes.explanations.CandidateExplanationRepo"
            ) as MockRepo:
                MockRepo.return_value.get_by_candidate_id = AsyncMock(return_value=None)

                client = TestClient(app)
                resp = client.get("/v1/candidates/arr_x/explanation")
                assert resp.status_code == 404

    def test_get_cached_explanation_200(self):
        """GET returns cached explanation."""
        app = _make_app()

        cached = {
            "id": "ce_1",
            "candidate_id": "arr_x",
            "session_id": "sess_1",
            "summary": "Dreamy",
            "why_it_works": ["Modal interchange"],
            "what_is_experimental": [],
            "recommended_use_cases": ["Intro"],
        }

        with patch(
            "explorator.api.routes.explanations.get_neo4j_driver",
            new=AsyncMock(return_value=MagicMock()),
        ):
            with patch(
                "explorator.api.routes.explanations.CandidateExplanationRepo"
            ) as MockRepo:
                MockRepo.return_value.get_by_candidate_id = AsyncMock(return_value=cached)

                client = TestClient(app)
                resp = client.get("/v1/candidates/arr_x/explanation")
                assert resp.status_code == 200
                data = resp.json()
                assert data["summary"] == "Dreamy"
