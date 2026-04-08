"""Rank and select node — score, filter, and select top arrangement candidates."""

import logging
from typing import Any

from ulid import ULID

from explorator.engine.realization_state import RealizationState
from explorator.models.evaluation import AggregateScorecard
from explorator.utils import utc_now

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS: dict[str, float] = {
    "voice_leading": 0.15,
    "register_density": 0.12,
    "playability": 0.12,
    "genre_fit": 0.10,
    "emotional_fit": 0.10,
    "theoretical_coherence": 0.10,
    "cadence_quality": 0.10,
    "novelty": 0.10,
    "loopability": 0.11,
}

# Dimensions whose absence triggers a 5.0 fallback (M1 scores)
_M1_DIMENSIONS = {"genre_fit", "emotional_fit", "theoretical_coherence", "cadence_quality", "novelty", "loopability"}

# M2b dimensions that must pass threshold
_M2B_GATE_DIMENSIONS = {"voice_leading", "register_density", "playability"}


def _compute_weighted_total(
    scores: dict[str, float],
    weights: dict[str, float],
) -> float:
    """Compute weighted sum across all weight dimensions.

    Missing dimensions use 5.0 as a fallback (neutral mid-range score).
    """
    total = 0.0
    for dim, weight in weights.items():
        score = scores.get(dim, 5.0)
        total += score * weight
    return round(total, 4)


def _rank_family(
    candidates: list[dict[str, Any]],
    weights: dict[str, float],
    min_threshold: float = 3.0,
    top_n: int = 2,
) -> list[dict[str, Any]]:
    """Filter, rank, and return top_n candidates within a single progression family.

    Candidates failing any of voice_leading/register_density/playability < min_threshold
    are rejected. Remaining candidates are ranked by weighted total descending.
    If fewer than top_n survive filtering, all survivors are returned.
    """
    passed: list[dict[str, Any]] = []
    for cand in candidates:
        scores = cand.get("merged_scores", {})
        gate_fail = any(
            scores.get(dim, 5.0) < min_threshold for dim in _M2B_GATE_DIMENSIONS
        )
        if not gate_fail:
            passed.append(cand)

    # Rank passed by weighted total descending
    passed.sort(
        key=lambda c: _compute_weighted_total(c.get("merged_scores", {}), weights),
        reverse=True,
    )

    return passed[:top_n]


async def rank_and_select(state: RealizationState) -> dict[str, Any]:
    """Merge M1+M2b scores, rank per progression family, select top arrangements."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "rank_and_select"})

    arrangement_candidates_raw = state.get("arrangement_candidates", [])
    arrangement_families_raw = state.get("arrangement_families", [])
    progression_candidates_raw = state.get("progression_candidates", [])
    evaluations_raw = state.get("evaluations", [])

    # Build eval lookup: arrangement_id → {voice_leading, register_density, playability}
    eval_lookup: dict[str, dict[str, float]] = {}
    for ev in evaluations_raw:
        arr_id = ev["arrangement_candidate_id"]
        eval_lookup[arr_id] = {
            "voice_leading": ev["voice_leading"]["overall_score"],
            "register_density": ev["register_density"]["overall_score"],
            "playability": ev["playability"]["overall_score"],
        }

    # Build M1 scores lookup: progression_candidate_id → scores dict
    m1_scores_lookup: dict[str, dict[str, float]] = {}
    for pc_data in progression_candidates_raw:
        pc_id = pc_data.get("id", "")
        raw_scores = pc_data.get("metadata", {}).get("scores", {})
        if isinstance(raw_scores, dict):
            m1_scores_lookup[pc_id] = raw_scores

    # Group arrangement_candidate_ids by progression_candidate_id
    by_prog: dict[str, list[str]] = {}
    for arr_data in arrangement_candidates_raw:
        arr_id = arr_data["id"]
        prog_id = arr_data.get("progression_candidate_id", "")
        by_prog.setdefault(prog_id, []).append(arr_id)

    now = utc_now()
    selected_ids: set[str] = set()
    scorecards: list[dict[str, Any]] = []
    updated_arrangements = list(arrangement_candidates_raw)  # will be mutated by id below

    # Build a mutable map for status updates
    arr_status: dict[str, str] = {}

    for prog_id, arr_ids in by_prog.items():
        m1_scores = m1_scores_lookup.get(prog_id, {})

        # Build per-candidate merged scores
        family_candidates: list[dict[str, Any]] = []
        for arr_id in arr_ids:
            m2b_scores = eval_lookup.get(arr_id, {})
            merged: dict[str, float] = {}
            # M1 scores (fallback to 5.0 if absent)
            for dim in _M1_DIMENSIONS:
                merged[dim] = float(m1_scores.get(dim, 5.0))
            # M2b scores
            merged.update(m2b_scores)
            family_candidates.append({"id": arr_id, "merged_scores": merged})

        selected_in_family = _rank_family(family_candidates, DEFAULT_WEIGHTS)
        selected_family_ids = {c["id"] for c in selected_in_family}
        selected_ids |= selected_family_ids

        # Build scorecards for each arrangement in this family
        for cand in family_candidates:
            arr_id = cand["id"]
            merged = cand["merged_scores"]
            weighted_total = _compute_weighted_total(merged, DEFAULT_WEIGHTS)
            rank = next(
                (i + 1 for i, c in enumerate(selected_in_family) if c["id"] == arr_id),
                len(selected_in_family) + 1,
            )
            sc = AggregateScorecard(
                id=f"sc_{ULID()}",
                type="aggregate_scorecard",
                status="completed",
                created_at=now,
                updated_at=now,
                candidate_id=arr_id,
                scores=merged,
                weighted_total=weighted_total,
                rank_within_round=rank,
            )
            scorecards.append(sc.model_dump(mode="json"))

            arr_status[arr_id] = "selected" if arr_id in selected_family_ids else "rejected"

    # Apply status updates to arrangement_candidates
    updated_arrangements = []
    for arr_data in arrangement_candidates_raw:
        arr_id = arr_data["id"]
        new_status = arr_status.get(arr_id, arr_data.get("status", "pending"))
        updated_arrangements.append({**arr_data, "status": new_status})

    # Build selected_arrangements list (full dicts for selected ones)
    arr_by_id_updated = {a["id"]: a for a in updated_arrangements}
    selected_arrangements = [arr_by_id_updated[aid] for aid in selected_ids if aid in arr_by_id_updated]

    # Update arrangement_families with selected_member info
    updated_families = []
    for fam_data in arrangement_families_raw:
        member_ids = fam_data.get("member_arrangement_candidate_ids", [])
        selected_members = [mid for mid in member_ids if mid in selected_ids]
        updated_families.append({**fam_data, "selected_member_ids": selected_members})

    return {
        "arrangement_candidates": updated_arrangements,
        "scorecards": scorecards,
        "selected_arrangements": selected_arrangements,
        "arrangement_families": updated_families,
    }
