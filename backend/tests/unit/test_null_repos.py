"""Unit tests for the null learning/recall repos (memory-mode graceful degradation).

Every read returns the documented empty/None; every write is an awaitable no-op
that never raises. asyncio_mode is "auto" — no marker needed.
"""

from datetime import datetime

from explorator.persistence.null_repos import (
    NullCandidateExplanationRepo,
    NullComparisonViewRepo,
    NullExportPackageRepo,
    NullFeedbackEventRepo,
    NullGenreResearchRepo,
    NullObjectiveWeightsRepo,
    NullPatternLibraryRepo,
    NullProvenanceTraceRepo,
    NullRenderArtifactRepo,
)
from explorator.utils import utc_now


class _Dummy:
    """Minimal stand-in for a Pydantic entity / model passed to writes."""

    id = "dummy-id"

    def model_dump(self, mode: str = "json") -> dict[str, object]:
        return {"id": self.id}


# --- NullPatternLibraryRepo ---------------------------------------------------


async def test_pattern_library_writes_are_noops() -> None:
    repo = NullPatternLibraryRepo()
    assert await repo.upsert(_Dummy()) is None  # type: ignore[arg-type]
    assert await repo.delete_by_id("x") is None


async def test_pattern_library_reads_return_empties() -> None:
    repo = NullPatternLibraryRepo()
    assert await repo.get_by_id("x") is None
    assert await repo.query_for_warm_starts(genre="jazz") == {}
    assert await repo.list_page() == ([], None)
    assert await repo.soft_delete("x") is False
    assert await repo.toggle_curation(
        arrangement_id="a", is_curated=True, now=utc_now()
    ) == []


async def test_pattern_library_iter_all_is_empty_async_generator() -> None:
    repo = NullPatternLibraryRepo()
    assert [x async for x in repo.iter_all()] == []


# --- NullFeedbackEventRepo ----------------------------------------------------


async def test_feedback_event_create_is_noop() -> None:
    repo = NullFeedbackEventRepo()
    assert await repo.create_with_relationships(_Dummy(), "w", "s") is None  # type: ignore[arg-type]


async def test_feedback_event_list_by_session_empty() -> None:
    repo = NullFeedbackEventRepo()
    assert await repo.list_by_session("s") == []


# --- NullObjectiveWeightsRepo -------------------------------------------------


async def test_objective_weights_latest_is_none() -> None:
    repo = NullObjectiveWeightsRepo()
    assert await repo.get_latest_for_session("s") is None


# --- NullGenreResearchRepo ----------------------------------------------------


async def test_genre_research_writes_are_noops() -> None:
    repo = NullGenreResearchRepo()
    assert await repo.create_job({"id": "j"}) is None
    assert await repo.update_job("j", {"status": "done"}) is None


async def test_genre_research_reads_return_empties() -> None:
    repo = NullGenreResearchRepo()
    assert await repo.get_job("j") is None
    assert await repo.list_pending_drafts() == []
    assert await repo.job_exists_for_genre("jazz") is False


# --- NullProvenanceTraceRepo --------------------------------------------------


async def test_provenance_trace_append_is_noop() -> None:
    repo = NullProvenanceTraceRepo()
    assert await repo.append_events("t", [{"event": "x"}]) is None


async def test_provenance_trace_get_by_session_is_none() -> None:
    repo = NullProvenanceTraceRepo()
    assert await repo.get_by_session_id("s") is None


# --- Generic CRUD null repos --------------------------------------------------


async def test_comparison_view_crud_noops_and_empties() -> None:
    repo = NullComparisonViewRepo()
    assert await repo.create(_Dummy()) is None  # type: ignore[arg-type]
    assert await repo.get_by_id("x") is None
    assert await repo.query_by_property("p", "v") == []
    assert await repo.update_status("x", "done") is None


async def test_candidate_explanation_get_by_candidate_is_none() -> None:
    repo = NullCandidateExplanationRepo()
    assert await repo.create(_Dummy()) is None  # type: ignore[arg-type]
    assert await repo.get_by_id("x") is None
    assert await repo.query_by_property("p", "v") == []
    assert await repo.update_status("x", "done") is None
    assert await repo.get_by_candidate_id("c") is None


async def test_export_package_crud_noops_and_empties() -> None:
    repo = NullExportPackageRepo()
    assert await repo.create(_Dummy()) is None  # type: ignore[arg-type]
    assert await repo.get_by_id("x") is None
    assert await repo.query_by_property("p", "v") == []
    assert await repo.update_status("x", "done") is None


async def test_render_artifact_crud_noops_and_empties() -> None:
    repo = NullRenderArtifactRepo()
    assert await repo.create(_Dummy()) is None  # type: ignore[arg-type]
    assert await repo.get_by_id("x") is None
    assert await repo.query_by_property("p", "v") == []
    assert await repo.update_status("x", "done") is None


def test_now_helper_type() -> None:
    """Sanity: utc_now returns a datetime usable as the toggle_curation arg."""
    assert isinstance(utc_now(), datetime)
