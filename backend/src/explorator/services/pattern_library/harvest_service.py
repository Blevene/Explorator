"""Transport-free pattern harvest orchestration.

Extracted from the LangGraph `harvest_patterns` node so the same logic can be
reused by the POST /v1/sessions/{id}/finalists/harvest API endpoint.
"""

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from neo4j.exceptions import Neo4jError

from explorator.domain.memory.pattern_harvesting import harvest_finalist
from explorator.graph.pattern_library_repo import PatternLibraryRepo

logger = logging.getLogger(__name__)


class SkipReason(StrEnum):
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
            session_id=session_id,
            upserted_count=0,
            skipped_count=0,
        )

    if not genre:
        logger.warning(
            "harvest_session_finalists: no genre in state for session %s; skipping",
            session_id or "?",
        )
        skipped_missing_genre: list[SkipEntry] = [
            SkipEntry(candidate_id=cid, pattern_type="*", reason=SkipReason.MISSING_GENRE)
            for cid in selected_ids
        ]
        return HarvestReport(
            session_id=session_id,
            upserted_count=0,
            skipped_count=len(skipped_missing_genre),
            skipped_reasons=skipped_missing_genre,
        )

    roles: dict[str, str] = final_selection.get("selection_roles") or {}
    arrangements = _index_by_id(state.get("arrangement_candidates") or [])
    progressions = _index_by_id(state.get("progression_candidates") or [])
    voicing_plans = _index_by_id(state.get("voicing_plans") or [])
    bass_lines = _index_by_id(state.get("bass_lines") or [])
    grooves = _index_by_id(state.get("groove_patterns") or [])
    melodies = _index_by_id(state.get("melodic_complements") or [])
    scorecards_by_cand = {
        s["candidate_id"]: s for s in (state.get("scorecards") or []) if s.get("candidate_id")
    }

    upserted_ids: list[str] = []
    skipped: list[SkipEntry] = []

    for arr_id in selected_ids:
        arrangement = arrangements.get(arr_id)
        if arrangement is None:
            skipped.append(
                SkipEntry(
                    candidate_id=arr_id,
                    pattern_type="*",
                    reason=SkipReason.MISSING_ARRANGEMENT,
                )
            )
            continue
        progression = progressions.get(arrangement.get("progression_candidate_id") or "")
        if progression is None:
            skipped.append(
                SkipEntry(
                    candidate_id=arr_id,
                    pattern_type="*",
                    reason=SkipReason.MISSING_PROGRESSION,
                )
            )
            continue
        scorecard = scorecards_by_cand.get(arr_id) or {
            "weighted_total": 0.0,
            "scores": {},
            "pareto_tags": [],
        }
        role = roles.get(arr_id, "unknown")

        entries = harvest_finalist(
            arrangement=arrangement,
            progression=progression,
            voicing_plan=voicing_plans.get(arrangement.get("voicing_plan_id") or ""),
            bass_line=bass_lines.get(arrangement.get("bass_line_id") or ""),
            groove=grooves.get(arrangement.get("groove_pattern_id") or ""),
            melody=melodies.get(arrangement.get("melodic_complement_id") or ""),
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
                    entry.id,
                    entry.pattern_type,
                    entry.source_candidate_id,
                    exc,
                )
                skipped.append(
                    SkipEntry(
                        candidate_id=entry.source_candidate_id,
                        pattern_type=entry.pattern_type,
                        reason=SkipReason.UPSERT_FAILED,
                    )
                )

    return HarvestReport(
        session_id=session_id,
        upserted_count=len(upserted_ids),
        skipped_count=len(skipped),
        skipped_reasons=skipped,
        upserted_pattern_ids=upserted_ids,
    )


# NOTE: HarvestRepos is a composition bundle constructed in deps.py (composition
# root) and passed to harvest_session_finalists. The helper reads finalists from
# these repos via session_id — used by the POST /v1/sessions/{id}/finalists/harvest
# endpoint. The LangGraph node uses harvest_session_finalists_from_state instead
# (reads from in-memory state to avoid a DB round-trip at realization time).


@dataclass(frozen=True)
class HarvestRepos:
    """Bundle of repos needed by the session-id-driven harvest path.

    Progression candidates live only on arrangements via progression_candidate_id —
    ProgressionCandidateRepo is not a separate persistent repo; progression data
    is reconstructed from state or from the ArrangementCandidateRepo's metadata.
    """

    pattern_library: PatternLibraryRepo
    arrangement_candidate: Any  # ArrangementCandidateRepo (imported at call site)
    bass_line: Any  # BassLineRepo
    voicing_plan: Any  # VoicingPlanRepo
    groove_pattern: Any  # GroovePatternRepo
    melodic_complement: Any  # MelodicComplementRepo


async def harvest_session_finalists(
    session_id: str,
    *,
    repos: HarvestRepos,
) -> HarvestReport:
    """Read finalists from repos, harvest patterns, upsert. Idempotent.

    Use from API endpoints (where finalists are already persisted); the
    LangGraph node uses harvest_session_finalists_from_state.
    """
    # Build a state-shaped dict from repo reads, then delegate.
    state = await _reconstruct_state_from_repos(session_id, repos=repos)
    return await harvest_session_finalists_from_state(
        state,
        pattern_library_repo=repos.pattern_library,
    )


async def _reconstruct_state_from_repos(
    session_id: str,
    *,
    repos: HarvestRepos,
) -> dict[str, Any]:
    """Pull finalists + facets from repos into a state-shaped dict.

    This function is the boundary between the repo-indexed world (used by
    the API endpoint) and the state-indexed world (used by the LangGraph
    node and the core harvest loop). It queries the arrangement repo for
    session-scoped arrangements whose metadata carries a finalist role.
    """
    # Arrangements with metadata.role stamped by persist_realization are finalists.
    arrangements = await repos.arrangement_candidate.list_finalists_for_session(session_id)

    selected_ids = [a["id"] for a in arrangements]
    roles = {a["id"]: a.get("metadata", {}).get("role", "unknown") for a in arrangements}

    # Facet fan-out. Each arrangement has *_id pointers; fetch each facet once.
    voicing_ids = {a.get("voicing_plan_id") for a in arrangements if a.get("voicing_plan_id")}
    bass_ids = {a.get("bass_line_id") for a in arrangements if a.get("bass_line_id")}
    groove_ids = {a.get("groove_pattern_id") for a in arrangements if a.get("groove_pattern_id")}
    melody_ids = {
        a.get("melodic_complement_id") for a in arrangements if a.get("melodic_complement_id")
    }
    prog_ids = {
        a.get("progression_candidate_id") for a in arrangements if a.get("progression_candidate_id")
    }

    voicings = [await repos.voicing_plan.get_by_id(i) for i in voicing_ids]
    basses = [await repos.bass_line.get_by_id(i) for i in bass_ids]
    grooves = [await repos.groove_pattern.get_by_id(i) for i in groove_ids]
    melodies = [await repos.melodic_complement.get_by_id(i) for i in melody_ids]
    progressions = [
        await repos.arrangement_candidate.get_progression_candidate(i) for i in prog_ids
    ]

    # Scorecards: pulled via arrangement_candidate repo if it exposes them;
    # otherwise the weighted_total on arrangement metadata is the single source.
    scorecards = [
        {
            "candidate_id": a["id"],
            "weighted_total": a.get("weighted_total", 0.0),
            "scores": a.get("metadata", {}).get("scores", {}),
            "pareto_tags": a.get("metadata", {}).get("pareto_tags", []),
        }
        for a in arrangements
    ]

    # Genre: arrangements inherit session genre via metadata or top-level field.
    genre = None
    if arrangements:
        first = arrangements[0]
        genre = first.get("genre") or first.get("metadata", {}).get("genre")

    return {
        "session_id": session_id,
        "genre": genre,
        "final_selection": {
            "selected_candidate_ids": selected_ids,
            "selection_roles": roles,
        },
        "arrangement_candidates": arrangements,
        "progression_candidates": [p for p in progressions if p],
        "voicing_plans": [v for v in voicings if v],
        "bass_lines": [b for b in basses if b],
        "groove_patterns": [g for g in grooves if g],
        "melodic_complements": [m for m in melodies if m],
        "scorecards": scorecards,
    }
