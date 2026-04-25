"""Neo4j repository for PatternLibraryEntry (M5d)."""
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from neo4j import AsyncDriver

from explorator.graph.repository import _neo4j_deserialize, _neo4j_safe
from explorator.models.memory import PatternLibraryEntry
from explorator.services.pattern_library.cursor import Cursor
from explorator.services.pattern_library.filters import PatternFilters
from explorator.utils import utc_now

# Shared by PatternLibraryRepo.toggle_curation (owns its own session) and
# curation_service.curate_arrangement (runs it inside a multi-statement
# transaction). Both sites must use this exact query — keep it in sync by
# referencing the constant, not by copy-pasting the Cypher.
CURATION_FANOUT_CYPHER = """
MATCH (p:PatternLibraryEntry {source_candidate_id: $aid})
WHERE p.deleted_at IS NULL
SET p.is_curated = $is_curated,
    p.curated_at = CASE WHEN $is_curated THEN $now ELSE NULL END
RETURN p.id AS id
"""


class PatternLibraryRepo:
    """CRUD and query access for pattern library entries.

    Idempotence is enforced at the DB layer via a uniqueness constraint on
    (source_candidate_id, pattern_type); upsert uses MERGE on that natural key.
    """

    def __init__(self, driver: AsyncDriver) -> None:
        self._driver = driver

    async def upsert(self, entry: PatternLibraryEntry) -> None:
        """Create or update by (source_candidate_id, pattern_type).

        ULID `id` and `created_at` are set only on first create; subsequent
        upserts refresh mutable props in place. `updated_at` flows passively
        through `$props` (the entry's fresh `utc_now()` stamp from harvesting,
        which runs milliseconds before upsert). This preserves the audit trail
        of "when was this pattern first harvested" while keeping mutation
        timestamps current.
        """
        payload = entry.model_dump(mode="json")
        weighted_total = float((payload.get("success_metrics") or {}).get("weighted_total") or 0.0)
        # Exclude natural-key and creation-time fields from the merge-props payload:
        # id + created_at are CREATE-only; source_candidate_id + pattern_type live in the MERGE key.
        # On re-harvest, these fields must survive untouched:
        #   id/scid/pt/created_at — natural key + creation audit
        #   is_curated/curated_at — explicit user intent (M5d-3), would otherwise
        #                           be wiped by the Pydantic default (False/None).
        immutable_on_match = (
            "id", "source_candidate_id", "pattern_type", "created_at",
            "is_curated", "curated_at",
        )
        props = _neo4j_safe({k: v for k, v in payload.items() if k not in immutable_on_match})
        props["weighted_total"] = weighted_total  # denormalized scalar for indexed ORDER BY

        # ON CREATE: `p = $props` runs first, then the subsequent assignments
        # override the natural-key/create-only fields. Cypher applies the SET
        # sub-clauses left-to-right, so the id/scid/pt/created_at overrides win.
        # is_curated/curated_at are excluded from $props (immutable_on_match), so
        # we set their Pydantic defaults explicitly on CREATE only.
        query = """
        MERGE (p:PatternLibraryEntry {source_candidate_id: $scid, pattern_type: $pt})
        ON CREATE SET p = $props,
                      p.id = $id,
                      p.source_candidate_id = $scid,
                      p.pattern_type = $pt,
                      p.created_at = $created_at,
                      p.is_curated = false,
                      p.curated_at = null
        ON MATCH  SET p += $props,
                      p.deleted_at = NULL
        """
        async with self._driver.session() as neo_session:
            await neo_session.run(
                query,
                scid=entry.source_candidate_id, pt=entry.pattern_type,
                id=entry.id, props=props,
                created_at=entry.created_at.isoformat(),
            )

    async def get_by_id(self, entry_id: str) -> dict[str, Any] | None:
        query = """
        MATCH (p:PatternLibraryEntry {id: $id})
        WHERE p.deleted_at IS NULL
        RETURN p
        """
        async with self._driver.session() as neo_session:
            result = await neo_session.run(query, id=entry_id)
            record = await result.single()
            if record is None:
                return None
            return _neo4j_deserialize(dict(record["p"]))

    async def delete_by_id(self, entry_id: str) -> None:
        query = "MATCH (p:PatternLibraryEntry {id: $id}) DETACH DELETE p"
        async with self._driver.session() as neo_session:
            await neo_session.run(query, id=entry_id)

    async def query_for_warm_starts(
        self,
        *,
        genre: str,
        top_k_per_type: int = 5,
        tag_filters: list[str] | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Return top-K patterns per pattern_type for a genre, ordered by weighted_total DESC.

        Streams via iter_all to avoid pulling the full genre slice into memory at once.
        Tag filtering is client-side (acceptable at current cardinality; see M5d-3 note
        on pushing into Cypher when cardinality warrants).
        """
        filters = PatternFilters(genre=genre)
        grouped: dict[str, list[dict[str, Any]]] = {}
        async for entry in self.iter_all(filters=filters):
            if tag_filters and not all(t in (entry.get("tags") or []) for t in tag_filters):
                continue
            bucket = grouped.setdefault(entry["pattern_type"], [])
            if len(bucket) < top_k_per_type:
                bucket.append(entry)
        return grouped

    async def list_page(
        self,
        *,
        filters: PatternFilters | None = None,
        cursor: Cursor | None = None,
        limit: int = 50,
    ) -> tuple[list[dict[str, Any]], Cursor | None]:
        """Bounded keyset-paginated list of non-deleted patterns.

        Order: weighted_total DESC, id ASC (compound tiebreaker). Emits a
        Cursor over the last returned row's (weighted_total, id) pair; None
        when the page is terminal. Caller-supplied `limit` must be bounded —
        no unbounded sentinel is accepted (use `iter_all` for unbounded reads).
        """
        filters = filters or PatternFilters()
        params: dict[str, Any] = {
            "genre": filters.genre,
            "ptype": filters.pattern_type,
            "curated_only": filters.curated_only,
            "after_score": cursor.after_score if cursor else None,
            "after_id": cursor.after_id if cursor else None,
            "limit": limit + 1,
        }
        query = """
        MATCH (p:PatternLibraryEntry)
        WHERE p.deleted_at IS NULL
          AND ($genre IS NULL OR p.genre = $genre)
          AND ($ptype IS NULL OR p.pattern_type = $ptype)
          AND (NOT $curated_only OR p.is_curated = true)
          AND ($after_score IS NULL
               OR p.weighted_total < $after_score
               OR (p.weighted_total = $after_score AND p.id > $after_id))
        RETURN p
        ORDER BY p.weighted_total DESC, p.id ASC
        LIMIT $limit
        """
        async with self._driver.session() as neo_session:
            result = await neo_session.run(query, **params)
            records = [r async for r in result]

        entries = [_neo4j_deserialize(dict(rec["p"])) for rec in records]
        next_cursor: Cursor | None = None
        if len(entries) > limit:
            overflow = entries[limit - 1]  # the last in-window row becomes the cursor
            next_cursor = Cursor(
                after_score=float(overflow["success_metrics"].get("weighted_total") or 0.0),
                after_id=str(overflow["id"]),
            )
            entries = entries[:limit]
        return entries, next_cursor

    async def iter_all(
        self,
        *,
        filters: PatternFilters | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Unbounded internal generator over non-deleted patterns.

        Not exposed via the HTTP API. Used by internal consumers that need to
        stream the full library (e.g. query_for_warm_starts). Order is the same
        as list_page (weighted_total DESC, id ASC) for consumer consistency.
        """
        filters = filters or PatternFilters()
        params: dict[str, Any] = {
            "genre": filters.genre,
            "ptype": filters.pattern_type,
            "curated_only": filters.curated_only,
        }
        query = """
        MATCH (p:PatternLibraryEntry)
        WHERE p.deleted_at IS NULL
          AND ($genre IS NULL OR p.genre = $genre)
          AND ($ptype IS NULL OR p.pattern_type = $ptype)
          AND (NOT $curated_only OR p.is_curated = true)
        RETURN p
        ORDER BY p.weighted_total DESC, p.id ASC
        """
        async with self._driver.session() as neo_session:
            result = await neo_session.run(query, **params)
            async for record in result:
                yield _neo4j_deserialize(dict(record["p"]))

    async def soft_delete(self, entry_id: str) -> bool:
        """Mark a pattern as deleted by setting deleted_at. Returns False if the
        row is missing or already deleted — callers translate to HTTP 404.
        """
        query = """
        MATCH (p:PatternLibraryEntry {id: $id})
        WHERE p.deleted_at IS NULL
        SET p.deleted_at = $now
        RETURN p.id AS id
        """
        async with self._driver.session() as neo_session:
            result = await neo_session.run(
                query, id=entry_id, now=utc_now().isoformat()
            )
            record = await result.single()
            return record is not None

    async def toggle_curation(
        self,
        *,
        arrangement_id: str,
        is_curated: bool,
        now: datetime,
    ) -> list[str]:
        """Flip is_curated on every non-deleted facet row for an arrangement.

        Fan-out semantics: one arrangement -> 1-5 facet rows. Returns the IDs
        of the rows that were updated. Empty list means no matching non-deleted
        rows exist (caller translates to HTTP 409).

        When is_curated=False, curated_at is cleared to NULL.

        Opens its own session — NOT usable inside an external transaction.
        The curation service uses the shared CURATION_FANOUT_CYPHER directly
        within its multi-statement transaction; see curation_service.py.
        """
        async with self._driver.session() as neo_session:
            result = await neo_session.run(
                CURATION_FANOUT_CYPHER,
                aid=arrangement_id,
                is_curated=is_curated,
                now=now.isoformat(),
            )
            records = [r async for r in result]
        return [r["id"] for r in records]
