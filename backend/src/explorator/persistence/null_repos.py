"""No-op / empty repo implementations for memory mode (graceful degradation).

These mirror the public surfaces of the learning/recall Neo4j repos
(``graph/*``) but do nothing on writes and return neutral empties on reads, so
the corresponding endpoints return 200 with empty/neutral data instead of 500
when Neo4j is unavailable.

Method signatures (including keyword-only args) and return *types* match the
real repos exactly so they are drop-in substitutes via the persistence factory.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from datetime import datetime

    from pydantic import BaseModel

    from explorator.models.base import BaseEntity
    from explorator.models.memory import PatternLibraryEntry
    from explorator.services.pattern_library.cursor import Cursor
    from explorator.services.pattern_library.filters import PatternFilters


class NullPatternLibraryRepo:
    """Empty stand-in for :class:`PatternLibraryRepo`.

    Writes are no-ops; reads return empties. Pattern library / harvest /
    curation are disabled in memory mode.
    """

    async def upsert(self, entry: PatternLibraryEntry) -> None:
        return None

    async def get_by_id(self, entry_id: str) -> dict[str, Any] | None:
        return None

    async def delete_by_id(self, entry_id: str) -> None:
        return None

    async def query_for_warm_starts(
        self,
        *,
        genre: str,
        top_k_per_type: int = 5,
        tag_filters: list[str] | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        return {}

    async def list_page(
        self,
        *,
        filters: PatternFilters | None = None,
        cursor: Cursor | None = None,
        limit: int = 50,
    ) -> tuple[list[dict[str, Any]], Cursor | None]:
        return [], None

    async def iter_all(
        self,
        *,
        filters: PatternFilters | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        # True async generator that yields nothing.
        return
        yield  # pragma: no cover

    async def soft_delete(self, entry_id: str) -> bool:
        return False

    async def toggle_curation(
        self,
        *,
        arrangement_id: str,
        is_curated: bool,
        now: datetime,
    ) -> list[str]:
        return []


class NullFeedbackEventRepo:
    """Empty stand-in for :class:`FeedbackEventRepo`."""

    async def create_with_relationships(
        self,
        event: BaseEntity,
        weights_id: str,
        session_id: str,
    ) -> None:
        return None

    async def list_by_session(self, session_id: str) -> list[dict[str, Any]]:
        return []


class NullObjectiveWeightsRepo:
    """Empty stand-in for :class:`ObjectiveWeightsRepo`.

    ``get_latest_for_session`` → ``None``; ``load_memory`` falls back to the
    canonical default weights, so there is no learning in memory mode.
    """

    async def create(self, entity: BaseModel) -> None:
        return None

    async def get_latest_for_session(self, session_id: str) -> dict[str, Any] | None:
        return None


class NullGenreResearchRepo:
    """Empty stand-in for :class:`GenreResearchRepository`."""

    async def create_job(self, job_data: dict[str, Any]) -> None:
        return None

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        return None

    async def update_job(self, job_id: str, updates: dict[str, Any]) -> None:
        return None

    async def list_pending_drafts(self) -> list[dict[str, Any]]:
        return []

    async def job_exists_for_genre(self, genre_name: str) -> bool:
        return False


class NullProvenanceTraceRepo:
    """Empty stand-in for :class:`ProvenanceTraceRepo`."""

    async def append_events(
        self, trace_id: str, new_events: list[dict[str, Any]]
    ) -> None:
        return None

    async def get_by_session_id(self, session_id: str) -> dict[str, Any] | None:
        return None


class _NullCrudRepo:
    """Shared no-op base for the generic :class:`BaseRepository` surface."""

    async def create(self, entity: BaseModel) -> None:
        return None

    async def get_by_id(self, entity_id: str) -> dict[str, Any] | None:
        return None

    async def query_by_property(self, prop: str, value: Any) -> list[dict[str, Any]]:
        return []

    async def update_status(self, entity_id: str, status: str) -> None:
        return None


class NullComparisonViewRepo(_NullCrudRepo):
    """Empty stand-in for :class:`ComparisonViewRepo`."""


class NullCandidateExplanationRepo(_NullCrudRepo):
    """Empty stand-in for :class:`CandidateExplanationRepo`."""

    async def get_by_candidate_id(self, candidate_id: str) -> dict[str, Any] | None:
        return None


class NullExportPackageRepo(_NullCrudRepo):
    """Empty stand-in for :class:`ExportPackageRepo`."""


class NullRenderArtifactRepo(_NullCrudRepo):
    """Empty stand-in for :class:`RenderArtifactRepo`."""
