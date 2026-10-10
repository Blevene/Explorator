"""In-memory generation-path repos — the Neo4j stand-in for memory mode.

Each repo stores `entity.model_dump(mode="json")` dicts in the process-singleton
`MemoryStore`, so reads return the SAME deserialized shape (nested dicts/lists,
ISO datetime strings) the Neo4j repos yield. Behaviour for the generation path
(M1 → M2 → M3) is real; learning/recall lives in `null_repos`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from explorator.persistence.memory_store import MemoryStore, get_memory_store
from explorator.utils import utc_now

if TYPE_CHECKING:
    from pydantic import BaseModel


class _MemoryCrud:
    """Generic in-memory node CRUD. Subclasses set `label`."""

    label: str = "Node"

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    async def create(self, entity: BaseModel) -> None:
        self._store.create(self.label, entity.model_dump(mode="json"))

    async def get_by_id(self, entity_id: str) -> dict[str, Any] | None:
        return self._store.get(self.label, entity_id)

    async def query_by_property(self, prop: str, value: Any) -> list[dict[str, Any]]:
        return self._store.query(self.label, prop, value)

    async def update_status(self, entity_id: str, status: str) -> None:
        self._store.update(
            self.label,
            entity_id,
            status=status,
            updated_at=utc_now().isoformat(),
        )


class MemoryCandidateRepo(_MemoryCrud):
    label = "ProgressionCandidate"


class MemoryVoicingPlanRepo(_MemoryCrud):
    label = "VoicingPlan"


class MemoryBassLineRepo(_MemoryCrud):
    label = "BassLine"


class MemoryGroovePatternRepo(_MemoryCrud):
    label = "GroovePattern"


class MemoryMelodicComplementRepo(_MemoryCrud):
    label = "MelodicComplement"


class MemoryScorecardRepo(_MemoryCrud):
    label = "AggregateScorecard"


class MemorySearchRoundRepo(_MemoryCrud):
    label = "SearchRound"


class MemoryArrangementFamilyRepo(_MemoryCrud):
    label = "ArrangementFamily"


class MemoryMutationRecordRepo(_MemoryCrud):
    label = "MutationRecord"


class MemorySessionRepo(_MemoryCrud):
    label = "Session"

    async def list_sessions(self) -> list[dict[str, Any]]:
        """All sessions ordered by created_at descending."""
        rows = self._store.all("Session")
        return sorted(rows, key=lambda r: r.get("created_at") or "", reverse=True)

    async def update_metadata(
        self, session_id: str, metadata: dict[str, Any]
    ) -> None:
        """Overwrite the Session record's metadata (native dict, no-op if absent)."""
        self._store.update("Session", session_id, metadata=metadata)

    async def delete(self, session_id: str) -> bool:
        """Remove the Session record from the store. Returns True if it existed.

        Child nodes are not cascaded (memory state is process-lifetime and lost
        on restart); this just makes a subsequent `get_by_id` return None.
        """
        return self._store.delete("Session", session_id)

    async def set_final_selection(
        self, session_id: str, payload: dict[str, Any]
    ) -> None:
        """Store the round's final selection on the Session record.

        No-op if the session isn't in the store. Stored as the native dict (the
        memory store keeps deserialized shapes), unlike the JSON string the Neo4j
        repo writes — final selection is optional UI sugar in either mode.
        """
        self._store.update("Session", session_id, final_selection=payload)


class MemoryArrangementCandidateRepo(_MemoryCrud):
    label = "ArrangementCandidate"

    async def list_finalists_for_session(
        self, session_id: str
    ) -> list[dict[str, Any]]:
        """Arrangements for a session whose metadata carries a finalist role.

        `persist_realization` stamps `metadata.role`; rows without it are excluded.
        Sorted by `weighted_total` descending (None last).
        """
        rows = self._store.query("ArrangementCandidate", "session_id", session_id)
        finalists = [
            r
            for r in rows
            if isinstance(r.get("metadata"), dict) and "role" in r["metadata"]
        ]

        def _total(r: dict[str, Any]) -> float:
            value = r.get("weighted_total")
            if value is None:
                value = r.get("metadata", {}).get("weighted_total")
            return float(value) if isinstance(value, (int, float)) else float("-inf")

        return sorted(finalists, key=_total, reverse=True)

    async def get_progression_candidate(
        self, pc_id: str
    ) -> dict[str, Any] | None:
        """Fetch a progression candidate by id (harvest reconstruction)."""
        return self._store.get("ProgressionCandidate", pc_id)

    async def fetch_curation_state(
        self, arrangement_ids: list[str]
    ) -> dict[str, tuple[bool | None, str | None]]:
        """No curation in memory mode → `(None, None)` per id."""
        return {aid: (None, None) for aid in arrangement_ids}


class MemoryCreativeBriefRepo(_MemoryCrud):
    label = "CreativeBrief"

    async def get_by_session_id(self, session_id: str) -> dict[str, Any] | None:
        rows = self._store.query("CreativeBrief", "session_id", session_id)
        return rows[0] if rows else None


class MemoryStyleRepo:
    """Serves genre profiles from YAML, matching `StyleRepository`'s shape.

    The YAML catalog is loaded once and cached for the process. Takes an optional
    store for constructor symmetry with the other repos (unused).
    """

    _cache: list[dict[str, Any]] | None = None

    def __init__(self, store: MemoryStore | None = None) -> None:
        self._store = store or get_memory_store()

    @classmethod
    def _profiles(cls) -> list[dict[str, Any]]:
        if cls._cache is None:
            from explorator.domain.style.service import load_genre_profiles_from_yaml

            cls._cache = load_genre_profiles_from_yaml()
        return cls._cache

    async def get_genre_profile(self, genre: str) -> dict[str, Any] | None:
        for profile in self._profiles():
            if profile.get("genre") == genre:
                return dict(profile)
        return None

    async def list_genre_profiles(self) -> list[dict[str, Any]]:
        return [dict(p) for p in self._profiles()]


# NOTE: MemoryStyleRepo returns native Python dicts (nested dicts/lists intact),
# whereas StyleRepository.get_genre_profile returns dicts whose nested values are
# JSON *strings* (Neo4j can't store nested structures). This shape divergence is
# benign: both forms are normalized downstream via `parse_json_field`, which is a
# no-op on already-decoded dicts/lists and decodes the Neo4j JSON strings.


class MemoryExportPackageRepo(_MemoryCrud):
    """In-memory store for ExportPackage nodes.

    Plain CRUD: `list_exports` queries by `session_id` via `query_by_property`,
    so export create→list works in memory mode just as in Neo4j mode (only the
    lineage relationships are Neo4j-only). Lost on restart.
    """

    label = "ExportPackage"


class MemoryRenderArtifactRepo(_MemoryCrud):
    """In-memory store for RenderArtifact nodes.

    Plain CRUD: `download_artifact` fetches by id via `get_by_id`, so the file
    written to disk during export is downloadable in memory mode. Lost on
    restart (the artifact node, not the file on disk).
    """

    label = "RenderArtifact"


class MemoryCandidateExplanationRepo(_MemoryCrud):
    """In-memory cache for candidate explanations.

    Backed by the process-singleton store so a `POST /explain` result is cached
    within the process and subsequent calls skip the (expensive) pro-tier LLM
    invocation — matching the Neo4j repo's caching behaviour. Lost on restart.
    """

    label = "CandidateExplanation"

    async def get_by_candidate_id(self, candidate_id: str) -> dict[str, Any] | None:
        rows = self._store.query(self.label, "candidate_id", candidate_id)
        return rows[0] if rows else None
