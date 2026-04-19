"""Transport-free pattern harvest orchestration.

Extracted from the LangGraph `harvest_patterns` node so the same logic can be
reused by the POST /v1/sessions/{id}/finalists/harvest API endpoint.
"""
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from neo4j.exceptions import Neo4jError

from explorator.domain.memory.pattern_harvesting import harvest_finalist
from explorator.graph.pattern_library_repo import PatternLibraryRepo

logger = logging.getLogger(__name__)


class SkipReason(str, Enum):
    """Why a candidate facet was not upserted to the library."""
    MISSING_ARRANGEMENT = "missing_arrangement"
    MISSING_PROGRESSION = "missing_progression"
    MISSING_GENRE = "missing_genre"
    NO_FINALISTS = "no_finalists"
    UPSERT_FAILED = "upsert_failed"


@dataclass(frozen=True)
class SkipEntry:
    """A single skipped-pattern record for the HarvestReport."""
    candidate_id: str
    pattern_type: str
    reason: SkipReason


@dataclass(frozen=True)
class HarvestReport:
    """Return value of the harvest helper; mirrored to frontend as SSE payload.

    Field names chosen to reflect write-action semantics, not library-size delta:
    `upserted_count` counts MERGE operations (new + idempotent rewrite alike).
    Consumers must treat `upserted_pattern_ids` as an unordered set.
    """
    session_id: str
    upserted_count: int
    skipped_count: int
    skipped_reasons: list[SkipEntry] = field(default_factory=list)
    upserted_pattern_ids: list[str] = field(default_factory=list)


def _index_by_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in items if "id" in item}


async def harvest_session_finalists_from_state(
    state: dict[str, Any],
    *,
    pattern_library_repo: PatternLibraryRepo,
) -> HarvestReport:
    """Harvest patterns from a LangGraph state dict.

    Transport-free: does not emit SSE, does not touch LangGraph state mechanics.
    Reads finalist facets directly from the in-memory state dict (the shape used
    by the `harvest_patterns` node). The public `harvest_session_finalists`
    entry point (added in Commit B) reads the same facets from repos via
    session_id and delegates to this function.
    """
    session_id = state.get("session_id", "")
    final_selection = state.get("final_selection") or {}
    selected_ids: list[str] = final_selection.get("selected_candidate_ids") or []
    genre = state.get("genre")

    if not selected_ids:
        return HarvestReport(
            session_id=session_id, upserted_count=0, skipped_count=0,
        )

    if not genre:
        logger.warning(
            "harvest_session_finalists: no genre in state for session %s; skipping",
            session_id or "?",
        )
        skipped = [
            SkipEntry(candidate_id=cid, pattern_type="*", reason=SkipReason.MISSING_GENRE)
            for cid in selected_ids
        ]
        return HarvestReport(
            session_id=session_id, upserted_count=0,
            skipped_count=len(skipped), skipped_reasons=skipped,
        )

    roles: dict[str, str] = final_selection.get("selection_roles") or {}
    arrangements = _index_by_id(state.get("arrangement_candidates") or [])
    progressions = _index_by_id(state.get("progression_candidates") or [])
    voicing_plans = _index_by_id(state.get("voicing_plans") or [])
    bass_lines = _index_by_id(state.get("bass_lines") or [])
    grooves = _index_by_id(state.get("groove_patterns") or [])
    melodies = _index_by_id(state.get("melodic_complements") or [])
    scorecards_by_cand = {
        s["candidate_id"]: s
        for s in (state.get("scorecards") or [])
        if s.get("candidate_id")
    }

    upserted_ids: list[str] = []
    skipped: list[SkipEntry] = []

    for arr_id in selected_ids:
        arrangement = arrangements.get(arr_id)
        if arrangement is None:
            skipped.append(SkipEntry(
                candidate_id=arr_id, pattern_type="*",
                reason=SkipReason.MISSING_ARRANGEMENT,
            ))
            continue
        progression = progressions.get(arrangement.get("progression_candidate_id"))
        if progression is None:
            skipped.append(SkipEntry(
                candidate_id=arr_id, pattern_type="*",
                reason=SkipReason.MISSING_PROGRESSION,
            ))
            continue
        scorecard = scorecards_by_cand.get(arr_id) or {
            "weighted_total": 0.0, "scores": {}, "pareto_tags": [],
        }
        role = roles.get(arr_id, "unknown")

        entries = harvest_finalist(
            arrangement=arrangement,
            progression=progression,
            voicing_plan=voicing_plans.get(arrangement.get("voicing_plan_id")),
            bass_line=bass_lines.get(arrangement.get("bass_line_id")),
            groove=grooves.get(arrangement.get("groove_pattern_id")),
            melody=melodies.get(arrangement.get("melodic_complement_id")),
            scorecard=scorecard,
            genre=genre,
            role=role,
        )
        # Per-entry try/except: one Neo4j failure doesn't block siblings. The catch
        # is narrowed to Neo4jError so programming errors (KeyError, AttributeError)
        # surface loudly instead of hiding.
        for entry in entries:
            try:
                await pattern_library_repo.upsert(entry)
                upserted_ids.append(entry.id)
            except Neo4jError as exc:
                logger.error(
                    "harvest_session_finalists: failed to upsert entry %s (%s/%s): %s",
                    entry.id, entry.pattern_type, entry.source_candidate_id, exc,
                )
                skipped.append(SkipEntry(
                    candidate_id=entry.source_candidate_id,
                    pattern_type=entry.pattern_type,
                    reason=SkipReason.UPSERT_FAILED,
                ))

    return HarvestReport(
        session_id=session_id,
        upserted_count=len(upserted_ids),
        skipped_count=len(skipped),
        skipped_reasons=skipped,
        upserted_pattern_ids=upserted_ids,
    )
