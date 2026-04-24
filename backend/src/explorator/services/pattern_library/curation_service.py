"""Orchestrates arrangement-level pattern curation (M5d-3).

Writes an append-only UserFeedbackEvent and updates the denormalized
is_curated/curated_at fields on every non-deleted PatternLibraryEntry row
for the arrangement — both inside a single Neo4j transaction.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from neo4j import AsyncDriver
from ulid import ULID

from explorator.graph.pattern_library_repo import CURATION_FANOUT_CYPHER
from explorator.graph.repository import _neo4j_safe
from explorator.models.memory import UserFeedbackEvent
from explorator.utils import utc_now

logger = logging.getLogger(__name__)


class ArrangementNotFound(Exception):
    """Raised when the arrangement_id doesn't exist. Maps to HTTP 404."""


class PatternsNotHarvested(Exception):
    """Raised when an arrangement exists but has no non-deleted library rows.

    Maps to HTTP 409. Frontend should prevent this via the disabled-star UX.
    """


@dataclass(frozen=True)
class CurationResult:
    arrangement_id: str
    is_curated: bool
    curated_at: datetime | None
    affected_pattern_ids: list[str]


async def curate_arrangement(
    *,
    driver: AsyncDriver,
    arrangement_id: str,
    is_curated: bool,
) -> CurationResult:
    """Toggle curation on an arrangement. Atomic: event + fan-out in one tx.

    Raises:
        ArrangementNotFound: no ArrangementCandidate with that id.
        PatternsNotHarvested: arrangement exists but no non-deleted
            PatternLibraryEntry rows match (no event is written).
    """
    now = utc_now()
    content = "curated" if is_curated else "uncurated"

    # One session, one transaction. The probe runs inside the tx so concurrent
    # soft-deletes between probe and write cannot leak partial state: if no
    # non-deleted pattern rows exist at probe time, we roll back without
    # writing the event. affected_pattern_ids is read from the fan-out's
    # RETURN, so it reflects actual writes, not a pre-probe snapshot.
    async with driver.session() as neo_session:
        tx = await neo_session.begin_transaction()
        try:
            probe = await tx.run(
                "MATCH (a:ArrangementCandidate {id: $aid}) "
                "OPTIONAL MATCH (p:PatternLibraryEntry) "
                "  WHERE p.source_candidate_id = a.id AND p.deleted_at IS NULL "
                "RETURN a.session_id AS session_id, collect(p.id) AS pattern_ids",
                aid=arrangement_id,
            )
            record = await probe.single()
            if record is None:
                await tx.rollback()
                raise ArrangementNotFound(arrangement_id)
            session_id = record["session_id"]
            probe_pattern_ids = [
                pid for pid in record["pattern_ids"] if pid is not None
            ]
            if not probe_pattern_ids:
                await tx.rollback()
                logger.warning(
                    "curation attempted with no harvested patterns "
                    "(arrangement_id=%s session_id=%s)",
                    arrangement_id, session_id,
                )
                raise PatternsNotHarvested(arrangement_id)

            event = UserFeedbackEvent(
                id=f"fb_{ULID()}",
                type="user_feedback_event",
                status="active",
                session_id=session_id,
                candidate_id=arrangement_id,
                feedback_type="pattern_curation",
                content=content,
            )
            event_props = _neo4j_safe(event.model_dump(mode="json"))

            await tx.run(
                "CREATE (e:UserFeedbackEvent $props)",
                props=event_props,
            )
            await tx.run(
                "MATCH (s:Session {id: $sid}), (e:UserFeedbackEvent {id: $eid}) "
                "CREATE (s)-[:HAS_FEEDBACK]->(e)",
                sid=session_id, eid=event.id,
            )
            await tx.run(
                "MATCH (e:UserFeedbackEvent {id: $eid}), "
                "(a:ArrangementCandidate {id: $aid}) "
                "CREATE (e)-[:ABOUT]->(a)",
                eid=event.id, aid=arrangement_id,
            )
            fanout = await tx.run(
                CURATION_FANOUT_CYPHER,
                aid=arrangement_id, is_curated=is_curated, now=now.isoformat(),
            )
            affected_pattern_ids = [r["id"] async for r in fanout]
            await tx.commit()
        except Exception:
            if not tx.closed():
                await tx.rollback()
            raise

    return CurationResult(
        arrangement_id=arrangement_id,
        is_curated=is_curated,
        curated_at=now if is_curated else None,
        affected_pattern_ids=affected_pattern_ids,
    )
