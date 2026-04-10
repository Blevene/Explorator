"""mutate node — orchestrate mutation engine and produce new candidates."""

import logging
from typing import Any

from ulid import ULID

from explorator.adapters.gemini import GeminiClient
from explorator.domain.harmony.mutator import HarmonyMutator
from explorator.engine.state import ExplorationState
from explorator.utils import utc_now

logger = logging.getLogger(__name__)


def _select_candidates_to_mutate(
    scorecards: list[dict[str, Any]],
    pareto_ids: list[str],
    budget: int,
    user_targeted: list[str] | None = None,
) -> list[str]:
    """Select candidate IDs to mutate, respecting budget.

    Priority: user-targeted > Pareto front > highest weighted_total.
    """
    selected: list[str] = []
    seen: set[str] = set()

    for cid in (user_targeted or []):
        if cid not in seen and len(selected) < budget:
            selected.append(cid)
            seen.add(cid)

    for cid in pareto_ids:
        if cid not in seen and len(selected) < budget:
            selected.append(cid)
            seen.add(cid)

    sorted_cards = sorted(scorecards, key=lambda s: s.get("weighted_total", 0.0), reverse=True)
    for sc in sorted_cards:
        cid = sc.get("candidate_id", "")
        if cid and cid not in seen and len(selected) < budget:
            selected.append(cid)
            seen.add(cid)

    return selected


async def mutate(state: ExplorationState, *, gemini: GeminiClient) -> dict[str, Any]:
    """Mutate selected candidates and return merged state update."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "mutate"})

    plan = state.get("search_plan", {})
    budget = plan.get("mutation_budget_per_round", 6)
    round_number = state.get("round_number", 1)
    scorecards = state.get("scorecards", [])
    pareto = state.get("pareto_front", {})
    pareto_ids = pareto.get("candidate_ids", [])
    existing_progs = list(state.get("progression_candidates", []))
    existing_records = list(state.get("mutation_records", []))
    existing_history = list(state.get("all_candidates_history", []))
    genre = state.get("genre", state.get("genre_profile", {}).get("genre", ""))

    prog_by_id = {p["id"]: p for p in existing_progs}
    scores_by_id = {sc["candidate_id"]: sc.get("scores", {}) for sc in scorecards}

    to_mutate = _select_candidates_to_mutate(scorecards, pareto_ids, budget)

    mutator = HarmonyMutator(gemini)
    new_progs: list[dict[str, Any]] = []
    new_records: list[dict[str, Any]] = []
    now = utc_now()

    for source_id in to_mutate:
        source = prog_by_id.get(source_id)
        if not source:
            logger.warning("Mutation target %s not found in progressions", source_id)
            continue

        chord_symbols = source.get("chord_symbols", [])
        source_scores = scores_by_id.get(source_id, {})

        try:
            response = await mutator.mutate_harmonic(
                chord_symbols=chord_symbols,
                genre=genre,
                scores=source_scores,
            )
        except Exception:
            logger.exception("Gemini mutation failed for candidate %s — skipping", source_id)
            continue

        new_id = f"pc_{ULID()}"
        new_prog = {
            **source,
            "id": new_id,
            "chord_symbols": response.mutated_chord_symbols,
            "status": "pending",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "metadata": {
                **source.get("metadata", {}),
                "mutated_from": source_id,
                "mutation_round": round_number + 1,
            },
        }
        new_progs.append(new_prog)

        record = {
            "id": f"mr_{ULID()}",
            "type": "mutation_record",
            "status": "completed",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "source_candidate_id": source_id,
            "source_candidate_type": "progression",
            "result_candidate_id": new_id,
            "result_candidate_type": "progression",
            "mutation_scope": "harmonic",
            "changes": [m.model_dump() for m in response.mutations],
            "reason": "; ".join(m.reason for m in response.mutations),
            "predicted_effects": [
                f"{k}: {v:+.1f}" for m in response.mutations
                for k, v in m.predicted_effects.items()
            ],
            "actual_score_delta": {},
        }
        new_records.append(record)

    history_snapshot = [
        {"id": p["id"], "round": round_number, "scores": scores_by_id.get(p["id"], {})}
        for p in existing_progs
    ]

    if callback:
        await callback("mutation_completed", {
            "mutations_count": len(new_records),
            "round": round_number + 1,
        })

    return {
        "progression_candidates": existing_progs + new_progs,
        "mutation_records": existing_records + new_records,
        "all_candidates_history": existing_history + history_snapshot,
        "round_number": round_number + 1,
        "voicing_plans": [],
        "bass_lines": [],
        "arrangement_candidates": [],
        "arrangement_families": [],
        "selected_arrangements": [],
        "evaluations": [],
        "scorecards": [],
    }
