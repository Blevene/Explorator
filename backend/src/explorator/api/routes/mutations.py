"""API routes for user-initiated mutations."""

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from neo4j import AsyncDriver
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from ulid import ULID

from explorator.adapters.gemini import GeminiClient
from explorator.api.deps import get_gemini_client, get_neo4j_driver
from explorator.api.sse import SSEChannel
from explorator.domain.harmony.mutator import HarmonyMutator
from explorator.engine.graph import build_realization_subgraph
from explorator.models.harmony import ProgressionCandidate
from explorator.persistence.factory import make_candidate_repo, make_session_repo
from explorator.utils import parse_json_or_dict, utc_now

logger = logging.getLogger(__name__)
router = APIRouter(tags=["mutations"])

# Simple in-memory concurrency guard: tracks sessions with in-flight mutations
_busy_sessions: set[str] = set()


class TriggerMutationRequest(BaseModel):
    candidate_ids: list[str]
    guidance: str | None = None
    operations: list[str] | None = None


@router.post("/sessions/{session_id}/mutate")
async def trigger_mutation(
    session_id: str,
    request: TriggerMutationRequest,
    gemini: GeminiClient = Depends(get_gemini_client),  # noqa: B008
    driver: AsyncDriver | None = Depends(get_neo4j_driver),  # noqa: B008
) -> EventSourceResponse:
    """Trigger user-initiated mutations on specific candidates.

    Returns 409 if a round is already in-flight for this session.
    """
    repo = make_session_repo(driver)
    session = await repo.get_by_id(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if not request.candidate_ids:
        raise HTTPException(status_code=422, detail="At least one candidate_id required")

    if session_id in _busy_sessions:
        raise HTTPException(
            status_code=409, detail="A mutation or round is already in-flight for this session"
        )
    _busy_sessions.add(session_id)

    channel = SSEChannel()

    async def run_mutation() -> None:
        try:
            mutator = HarmonyMutator(gemini)
            prog_repo = make_candidate_repo(driver)
            results: list[dict[str, Any]] = []

            for cid in request.candidate_ids:
                candidate = await prog_repo.get_by_id(cid)
                if candidate is None:
                    await channel.send("mutation_error", {"error": f"Candidate {cid} not found"})
                    continue

                # chord_symbols on the Neo4j node is always empty —
                # the actual symbols live inside chord_events[].symbol
                raw_events = candidate.get("chord_events", [])
                if isinstance(raw_events, str):
                    import json as _json

                    try:
                        raw_events = _json.loads(raw_events)
                    except (ValueError, TypeError):
                        raw_events = []
                chord_symbols = [
                    e.get("symbol", "") for e in raw_events if isinstance(e, dict)
                ] or candidate.get("chord_symbols", [])
                scores = parse_json_or_dict(candidate.get("metadata", {})).get("scores", {})

                response = await mutator.mutate_harmonic(
                    chord_symbols=chord_symbols,
                    genre=session.get("genre", ""),
                    scores=scores,
                    guidance=request.guidance,
                )

                # Persist the new mutated candidate to Neo4j
                now = utc_now()
                new_id = f"prog_{ULID()}"
                source_metadata = parse_json_or_dict(candidate.get("metadata"))
                new_candidate_data = {
                    **candidate,
                    "id": new_id,
                    "chord_symbols": response.mutated_chord_symbols,
                    "status": "candidate",
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                    "metadata": {
                        **source_metadata,
                        "mutated_from": cid,
                        "mutation_round": source_metadata.get("mutation_round", 0) + 1,
                        "parent_chord_symbols": chord_symbols,
                        "mutation_ops": [
                            {
                                "operation": m.operation,
                                "original": m.original_value,
                                "new": m.new_value,
                                "description": m.description,
                            }
                            for m in response.mutations
                        ],
                    },
                }

                # Re-serialize chord_events from mutated symbols
                import json

                original_events = candidate.get("chord_events", [])
                if isinstance(original_events, str):
                    try:
                        original_events = json.loads(original_events)
                    except (json.JSONDecodeError, TypeError):
                        original_events = []
                new_events = []
                for i, sym in enumerate(response.mutated_chord_symbols):
                    if i < len(original_events) and isinstance(original_events[i], dict):
                        new_events.append({**original_events[i], "symbol": sym})
                    else:
                        new_events.append(
                            {
                                "bar": i + 1,
                                "beat": 1.0,
                                "duration_beats": 4.0,
                                "symbol": sym,
                                "function_label": "",
                            }
                        )
                new_candidate_data["chord_events"] = new_events

                # Persist the mutated candidate. Neo4j mode keeps the original
                # raw-CREATE path (tolerant of JSON-string fields the node carries);
                # memory mode validates into the model and uses the repo.
                if driver is not None:
                    from explorator.graph.repository import _neo4j_safe

                    safe_data = _neo4j_safe(new_candidate_data)
                    async with driver.session() as neo_session:
                        await neo_session.run(
                            "CREATE (n:ProgressionCandidate $props) SET n.id = $props.id",
                            props=safe_data,
                        )
                else:
                    new_candidate = ProgressionCandidate.model_validate(new_candidate_data)
                    await prog_repo.create(new_candidate)

                results.append(
                    {
                        "source_id": cid,
                        "new_candidate_id": new_id,
                        "mutated_chord_symbols": response.mutated_chord_symbols,
                        "mutations": [m.model_dump() for m in response.mutations],
                    }
                )

            await channel.send("mutation_completed", {"results": results})

            # Run realization for each mutated candidate so they have arrangements
            new_ids = [r["new_candidate_id"] for r in results]
            if new_ids:
                try:
                    realization_graph = build_realization_subgraph(gemini, driver)
                    await realization_graph.ainvoke(
                        {
                            "session_id": session_id,
                            "progression_candidate_ids": new_ids,
                            "on_progress": channel.send,
                        },
                        {"recursion_limit": 100},
                    )
                except Exception as real_err:
                    logger.exception("Realization failed for mutated candidates %s", new_ids)
                    await channel.send("realization_error", {"error": str(real_err)})

        except Exception as e:
            logger.exception("Mutation failed for session %s", session_id)
            await channel.send("mutation_error", {"error": str(e)})
        finally:
            _busy_sessions.discard(session_id)
            await channel.close()

    asyncio.create_task(run_mutation())
    return EventSourceResponse(channel.stream())
