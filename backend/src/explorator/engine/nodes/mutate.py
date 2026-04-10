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
    arrangements = state.get("arrangement_candidates", [])

    # Map arrangement IDs → parent progression IDs (scorecards reference arr_* IDs)
    arr_to_prog: dict[str, str] = {
        a["id"]: a.get("progression_candidate_id", "") for a in arrangements
    }
    scores_by_id = {sc["candidate_id"]: sc.get("scores", {}) for sc in scorecards}

    # Select arrangement candidates, then resolve to unique parent progressions
    selected_arr_ids = _select_candidates_to_mutate(scorecards, pareto_ids, budget)
    seen_prog_ids: set[str] = set()
    to_mutate: list[str] = []
    for arr_id in selected_arr_ids:
        prog_id = arr_to_prog.get(arr_id, arr_id)  # fallback to arr_id if no mapping
        if prog_id in prog_by_id and prog_id not in seen_prog_ids:
            to_mutate.append(prog_id)
            seen_prog_ids.add(prog_id)
        if len(to_mutate) >= budget:
            break

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
        # Use arrangement scores if available, else progression scores
        source_scores = scores_by_id.get(source_id, source.get("metadata", {}).get("scores", {}))

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
            "changes": [
                {
                    "field": f"chord_symbols[{m.position}]" if m.position >= 0 else "progression",
                    "operation": m.operation,
                    "description": m.description or f"{m.original_value} → {m.new_value}" if m.original_value else m.reason,
                }
                for m in response.mutations
            ],
            "reason": "; ".join(m.reason for m in response.mutations),
            "predicted_effects": [s for m in response.mutations for s in m.predicted_score_changes],
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
