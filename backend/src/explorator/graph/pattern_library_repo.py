"""Neo4j repository for PatternLibraryEntry (M5d)."""
from collections.abc import AsyncIterator
from typing import Any

from neo4j import AsyncDriver

from explorator.graph.repository import _neo4j_safe, _neo4j_deserialize
from explorator.models.memory import PatternLibraryEntry
from explorator.services.pattern_library.cursor import Cursor
from explorator.services.pattern_library.filters import PatternFilters
from explorator.utils import utc_now


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
        immutable_on_match = ("id", "source_candidate_id", "pattern_type", "created_at")
        props = _neo4j_safe({k: v for k, v in payload.items() if k not in immutable_on_match})
        props["weighted_total"] = weighted_total  # denormalized scalar for indexed ORDER BY

        # ON CREATE: `p = $props` runs first, then the subsequent assignments
        # override the natural-key/create-only fields. Cypher applies the SET
        # sub-clauses left-to-right, so the id/scid/pt/created_at overrides win.
        query = """
        MERGE (p:PatternLibraryEntry {source_candidate_id: $scid, pattern_type: $pt})
        ON CREATE SET p = $props,
                      p.id = $id,
                      p.source_candidate_id = $scid,
                      p.pattern_type = $pt,
                      p.created_at = $created_at
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

    async def list_all(
        self,
        *,
        genre: str | None = None,
        pattern_type: str | None = None,
        tags: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        # TODO(scale): this pulls every matching row into Python and filters tags
        # client-side. Acceptable at current cardinality (hundreds per genre). When
        # PatternLibraryEntry row count exceeds ~1k per genre, push tag filtering
        # into Cypher (tags is stored as a native string array in Neo4j; use
        # `ALL(t IN $tags WHERE t IN p.tags)`) and add LIMIT pagination here.
        clauses: list[str] = []
        params: dict[str, Any] = {}
        if genre is not None:
            clauses.append("p.genre = $genre")
            params["genre"] = genre
        if pattern_type is not None:
            clauses.append("p.pattern_type = $pattern_type")
            params["pattern_type"] = pattern_type
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        query = f"""
        MATCH (p:PatternLibraryEntry)
        {where}
        RETURN p
        ORDER BY p.weighted_total DESC
        """
        async with self._driver.session() as neo_session:
            result = await neo_session.run(query, **params)
            records = [r async for r in result]
        entries = [_neo4j_deserialize(dict(rec["p"])) for rec in records]

        if tags:
            entries = [e for e in entries if all(t in (e.get("tags") or []) for t in tags)]
        return entries

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
        """Return top-K patterns per pattern_type for a genre, ordered by weighted_total DESC."""
        all_for_genre = await self.list_all(genre=genre, tags=tag_filters)
        grouped: dict[str, list[dict[str, Any]]] = {}
        for entry in all_for_genre:
            grouped.setdefault(entry["pattern_type"], []).append(entry)
        # list_all already orders by weighted_total DESC — just truncate per bucket.
        for ptype, bucket in grouped.items():
            grouped[ptype] = bucket[:top_k_per_type]
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
            "after_score": cursor.after_score if cursor else None,
            "after_id": cursor.after_id if cursor else None,
            "limit": limit + 1,
        }
        query = """
        MATCH (p:PatternLibraryEntry)
        WHERE p.deleted_at IS NULL
          AND ($genre IS NULL OR p.genre = $genre)
          AND ($ptype IS NULL OR p.pattern_type = $ptype)
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
        params: dict[str, Any] = {"genre": filters.genre, "ptype": filters.pattern_type}
        query = """
        MATCH (p:PatternLibraryEntry)
        WHERE p.deleted_at IS NULL
          AND ($genre IS NULL OR p.genre = $genre)
          AND ($ptype IS NULL OR p.pattern_type = $ptype)
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
