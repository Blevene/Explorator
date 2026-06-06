"""Persist round node — save results to Neo4j."""

import logging
from typing import Any

from neo4j import AsyncDriver
from neo4j.exceptions import Neo4jError
from ulid import ULID

from explorator.engine.state import ExplorationState
from explorator.models.export import ProvenanceTrace
from explorator.models.search import MutationRecord, SearchRound
from explorator.persistence.factory import (
    make_candidate_repo,
    make_mutation_record_repo,
    make_search_round_repo,
)
from explorator.utils import utc_now

logger = logging.getLogger(__name__)




async def persist_round(
    state: ExplorationState, *, driver: AsyncDriver | None
) -> dict[str, Any]:
    """Save all candidates and evaluations to Neo4j (or the in-memory store)."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "persist_round"})

    from explorator.models.harmony import ProgressionCandidate

    repo = make_candidate_repo(driver)

    # Persist genre on Session so M2 realization can load the correct genre profile.
    # Graph-only concern (the genre read path uses GenreProfile nodes); in memory
    # mode genre flows through state, so this direct-Cypher write is skipped.
    session_id = state.get("session_id", "")
    genre = state.get("genre", "")
    if driver is not None and session_id and genre:
        try:
            async with driver.session() as neo_session:
                await neo_session.run(
                    "MATCH (s:Session {id: $id}) SET s.genre = $genre",
                    id=session_id,
                    genre=genre,
                )
        except Exception:
            logger.exception("Failed to persist genre on Session %s", session_id)

    # Build a lookup of candidate_id → scorecard
    # Note: state["scorecards"] may contain M2 arrangement scorecards (arr_*) by this point.
    # M1 progression scores should already be on candidate metadata from select_top_progressions.
    scorecard_lookup: dict[str, dict[str, Any]] = {}
    for sc in state.get("scorecards", []):
        cid = sc.get("candidate_id", "")
        if cid:
            scorecard_lookup[cid] = sc

    saved = 0
    failed = 0
    for candidate_data in state.get("top_progressions", []):
        candidate = ProgressionCandidate.model_validate(candidate_data)

        # Attach scorecard — prefer existing metadata scores (set by select_top_progressions),
        # fall back to scorecard lookup
        if not candidate.metadata.get("scores"):
            sc = scorecard_lookup.get(candidate.id, {})
            candidate.metadata["weighted_total"] = sc.get("weighted_total", 0.0)
            candidate.metadata["scores"] = sc.get("scores", {})

        try:
            await repo.create(candidate)
            saved += 1
        except Neo4jError as e:
            logger.error("Failed to persist candidate %s: %s", candidate.id, e)
            failed += 1
        except Exception:
            logger.exception("Unexpected error persisting candidate %s", candidate.id)
            failed += 1

    if failed > 0:
        logger.warning("Persisted %d/%d candidates (%d failed)", saved, saved + failed, failed)

    # --- M3a: Persist SearchRound ---
    round_number = state.get("round_number", 1)
    search_round = SearchRound(
        id=f"sr_{ULID()}",
        type="search_round",
        status="completed",
        created_at=utc_now(),
        updated_at=utc_now(),
        session_id=session_id,
        round_number=round_number,
        selected_candidate_ids=[p.get("id", "") for p in state.get("top_progressions", [])],
    )
    try:
        sr_repo = make_search_round_repo(driver)
        await sr_repo.create(search_round)
    except Exception:
        logger.exception("Failed to persist SearchRound")

    # --- M3a: Persist MutationRecords ---
    mr_repo = make_mutation_record_repo(driver)
    for mr_data in state.get("mutation_records", []):
        try:
            mr = MutationRecord.model_validate(mr_data)
            await mr_repo.create(mr)
        except Exception:
            logger.exception("Failed to persist MutationRecord %s", mr_data.get("id"))

    # --- M4b: Persist provenance events ---
    # Provenance is a learning/lineage concern that degrades in memory mode
    # (empty timeline), so the trace write only runs with a real driver.
    provenance_events = state.get("provenance_events", [])
    if driver is not None and provenance_events:
        from explorator.graph.provenance_trace_repo import ProvenanceTraceRepo
        try:
            prov_repo = ProvenanceTraceRepo(driver)
            existing_trace = await prov_repo.get_by_session_id(session_id)
            if existing_trace:
                await prov_repo.append_events(existing_trace["id"], provenance_events)
            else:
                new_trace = ProvenanceTrace(
                    id=f"pt_{ULID()}",
                    type="provenance_trace",
                    status="active",
                    session_id=session_id,
                    events=provenance_events,
                )
                await prov_repo.create(new_trace)
        except Exception:
            logger.exception("Failed to persist provenance events")

    if callback:
        top_score = max(
            (s.get("weighted_total", 0.0) for s in state.get("scorecards", [])),
            default=0.0,
        )

        await callback(
            "round_completed",
            {
                "round": state.get("round_number", 1),
                "candidates_count": saved,
                "top_score": round(top_score, 2),
                "stop_met": True,  # M1 is single-round
                "persist_failures": failed,
            },
        )

    return {}
