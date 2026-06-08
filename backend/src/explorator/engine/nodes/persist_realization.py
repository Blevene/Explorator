"""Persist realization node — write voicing plans, bass lines, and arrangements to Neo4j."""

import logging
from typing import Any

from neo4j import AsyncDriver
from neo4j.exceptions import Neo4jError

from explorator.engine.state import ExplorationState
from explorator.models.evaluation import AggregateScorecard
from explorator.models.groove import GroovePattern
from explorator.models.melody import MelodicComplement
from explorator.models.realization import (
    ArrangementCandidate,
    ArrangementFamily,
    BassLine,
    VoicingPlan,
)
from explorator.persistence.factory import (
    make_arrangement_candidate_repo,
    make_arrangement_family_repo,
    make_bass_line_repo,
    make_groove_pattern_repo,
    make_melodic_complement_repo,
    make_scorecard_repo,
    make_session_repo,
    make_voicing_plan_repo,
)

logger = logging.getLogger(__name__)


async def _create_relationship(
    driver: AsyncDriver,
    from_label: str,
    from_id: str,
    rel_type: str,
    to_label: str,
    to_id: str,
) -> None:
    """Create a directed relationship between two nodes by ID."""
    query = (
        f"MATCH (a:{from_label} {{id: $from_id}}) "
        f"MATCH (b:{to_label} {{id: $to_id}}) "
        f"CREATE (a)-[:{rel_type}]->(b)"
    )
    async with driver.session() as session:
        await session.run(query, from_id=from_id, to_id=to_id)


async def persist_realization(
    state: ExplorationState, *, driver: AsyncDriver | None
) -> dict[str, Any]:
    """Persist all realization artifacts to Neo4j (or the in-memory store).

    Node writes (voicing plans, bass lines, grooves, melodies, arrangements,
    families, scorecards) go through the repo factory so they land in either
    backend. Relationship/lineage/provenance writes are graph-only and are
    skipped when ``driver is None`` (memory mode degrades gracefully).
    """
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "persist_realization"})

    voicing_plan_repo = make_voicing_plan_repo(driver)
    bass_line_repo = make_bass_line_repo(driver)
    groove_pattern_repo = make_groove_pattern_repo(driver)
    melodic_complement_repo = make_melodic_complement_repo(driver)
    arrangement_candidate_repo = make_arrangement_candidate_repo(driver)
    arrangement_family_repo = make_arrangement_family_repo(driver)

    # 1. Persist VoicingPlans
    for vp_data in state.get("voicing_plans", []):
        vp = VoicingPlan.model_validate(vp_data)
        try:
            await voicing_plan_repo.create(vp)
        except Neo4jError as e:
            logger.error("Failed to persist VoicingPlan %s: %s", vp.id, e)
        except Exception:
            logger.exception("Unexpected error persisting VoicingPlan %s", vp.id)

    # 2. Persist BassLines
    for bl_data in state.get("bass_lines", []):
        bl = BassLine.model_validate(bl_data)
        try:
            await bass_line_repo.create(bl)
        except Neo4jError as e:
            logger.error("Failed to persist BassLine %s: %s", bl.id, e)
        except Exception:
            logger.exception("Unexpected error persisting BassLine %s", bl.id)

    # 2b. Persist GroovePatterns
    for gp_data in state.get("groove_patterns", []):
        gp = GroovePattern.model_validate(gp_data)
        try:
            await groove_pattern_repo.create(gp)
        except Neo4jError as e:
            logger.error("Failed to persist GroovePattern %s: %s", gp.id, e)
        except Exception:
            logger.exception("Unexpected error persisting GroovePattern %s", gp.id)

    # 2c. Persist MelodicComplements
    for mc_data in state.get("melodic_complements", []):
        mc = MelodicComplement.model_validate(mc_data)
        try:
            await melodic_complement_repo.create(mc)
        except Neo4jError as e:
            logger.error("Failed to persist MelodicComplement %s: %s", mc.id, e)
        except Exception:
            logger.exception("Unexpected error persisting MelodicComplement %s", mc.id)

    # Stamp selection roles into arrangement metadata before persisting
    final_selection = state.get("final_selection") or {}
    selection_roles: dict[str, str] = {}
    if isinstance(final_selection, dict):
        selection_roles = final_selection.get("selection_roles", {})

    # 3. Persist ArrangementCandidates + relationships
    arrangement_candidate_ids: list[str] = []
    for arr_data in state.get("arrangement_candidates", []):
        # Stamp role into metadata if this arrangement has a role
        role = selection_roles.get(arr_data.get("id", ""), "")
        if role:
            meta = arr_data.get("metadata", {})
            if isinstance(meta, str):
                import json as _json
                try:
                    meta = _json.loads(meta)
                except Exception:
                    meta = {}
            meta["role"] = role
            arr_data["metadata"] = meta

        arr = ArrangementCandidate.model_validate(arr_data)
        try:
            await arrangement_candidate_repo.create(arr)
            arrangement_candidate_ids.append(arr.id)

            # Relationships are graph-only (lineage); skipped in memory mode.
            if driver is not None:
                # (ProgressionCandidate)-[:REALIZED_AS]->(ArrangementCandidate)
                await _create_relationship(
                    driver,
                    "ProgressionCandidate",
                    arr.progression_candidate_id,
                    "REALIZED_AS",
                    "ArrangementCandidate",
                    arr.id,
                )

                # (ArrangementCandidate)-[:USES_VOICING_PLAN]->(VoicingPlan)
                if arr.voicing_plan_id:
                    await _create_relationship(
                        driver,
                        "ArrangementCandidate",
                        arr.id,
                        "USES_VOICING_PLAN",
                        "VoicingPlan",
                        arr.voicing_plan_id,
                    )

                # (ArrangementCandidate)-[:USES_BASS_LINE]->(BassLine)
                if arr.bass_line_id:
                    await _create_relationship(
                        driver,
                        "ArrangementCandidate",
                        arr.id,
                        "USES_BASS_LINE",
                        "BassLine",
                        arr.bass_line_id,
                    )

                # (ArrangementCandidate)-[:USES_GROOVE_PATTERN]->(GroovePattern)
                if arr.groove_pattern_id:
                    await _create_relationship(
                        driver,
                        "ArrangementCandidate",
                        arr.id,
                        "USES_GROOVE_PATTERN",
                        "GroovePattern",
                        arr.groove_pattern_id,
                    )

                # (ArrangementCandidate)-[:USES_MELODIC_COMPLEMENT]->(MelodicComplement)
                if arr.melodic_complement_id:
                    await _create_relationship(
                        driver,
                        "ArrangementCandidate",
                        arr.id,
                        "USES_MELODIC_COMPLEMENT",
                        "MelodicComplement",
                        arr.melodic_complement_id,
                    )

        except Neo4jError as e:
            logger.error("Failed to persist ArrangementCandidate %s: %s", arr.id, e)
        except Exception:
            logger.exception("Unexpected error persisting ArrangementCandidate %s", arr.id)

    # 4. Persist ArrangementFamilies + relationships
    for fam_data in state.get("arrangement_families", []):
        fam = ArrangementFamily.model_validate(fam_data)
        try:
            await arrangement_family_repo.create(fam)

            # (ArrangementFamily)-[:CONTAINS]->(ArrangementCandidate) — graph-only.
            if driver is not None:
                for member_id in fam.member_arrangement_candidate_ids:
                    await _create_relationship(
                        driver,
                        "ArrangementFamily",
                        fam.id,
                        "CONTAINS",
                        "ArrangementCandidate",
                        member_id,
                    )

        except Neo4jError as e:
            logger.error("Failed to persist ArrangementFamily %s: %s", fam.id, e)
        except Exception:
            logger.exception("Unexpected error persisting ArrangementFamily %s", fam.id)

    # 5. Persist evaluation entities (direct-Cypher, graph-only — skip in memory mode)
    if driver is not None:
        from explorator.graph.repository import _neo4j_safe
        for ev_data in state.get("evaluations", []):
            arrangement_id = ev_data.get("arrangement_candidate_id", "")
            for eval_type in ("voice_leading", "register_density", "playability"):
                eval_entry = ev_data.get(eval_type, {})
                eval_node = eval_entry.get("evaluation")
                if not eval_node:
                    continue
                eval_id = eval_node.get("id", "")
                if not eval_id:
                    continue
                label = {
                    "voice_leading": "VoiceLeadingEvaluation",
                    "register_density": "RegisterDensityEvaluation",
                    "playability": "PlayabilityEvaluation",
                }[eval_type]
                query = (
                    f"MERGE (e:{label} {{id: $id}}) "
                    "SET e += $props"
                )
                props = _neo4j_safe({k: v for k, v in eval_node.items() if k != "id"})
                try:
                    async with driver.session() as session:
                        await session.run(query, id=eval_id, props=props)
                    # Link arrangement → evaluation
                    await _create_relationship(
                        driver,
                        "ArrangementCandidate",
                        arrangement_id,
                        "HAS_EVALUATION",
                        label,
                        eval_id,
                    )
                except Neo4jError as e:
                    logger.error("Failed to persist %s %s: %s", label, eval_id, e)
                except Exception:
                    logger.exception("Unexpected error persisting %s %s", label, eval_id)

    # 6. Persist AggregateScorecard nodes + relationships.
    # CRITICAL: the scorecard write goes through the factory repo so it lands in
    # both backends. realization_rounds.list_arrangements reads scorecards back via
    # query_by_property("candidate_id", ...) to populate weighted_total /
    # rank_within_round; in memory mode that read only works if the write did too.
    scorecard_repo = make_scorecard_repo(driver)
    for sc_data in state.get("scorecards", []):
        sc = AggregateScorecard.model_validate(sc_data)
        try:
            await scorecard_repo.create(sc)
            # HAS_SCORECARD relationship is graph-only (lineage).
            if driver is not None:
                await _create_relationship(
                    driver,
                    "ArrangementCandidate",
                    sc.candidate_id,
                    "HAS_SCORECARD",
                    "AggregateScorecard",
                    sc.id,
                )
        except Neo4jError as e:
            logger.error("Failed to persist AggregateScorecard %s: %s", sc.id, e)
        except Exception:
            logger.exception("Unexpected error persisting AggregateScorecard %s", sc.id)

    # 6b. Persist final_selection to Session node for re-fetch on page load.
    # Routed through the session repo so it works in both backends.
    if selection_roles:
        session_id = state.get("session_id", "")
        if session_id:
            try:
                session_repo = make_session_repo(driver)
                await session_repo.set_final_selection(session_id, final_selection)
            except Exception:
                logger.exception("Failed to persist final_selection on Session %s", session_id)

    # 7. Update ArrangementCandidate statuses (selected / rejected).
    # Direct-Cypher status flip is graph-only; the memory store keeps the status
    # carried on the arrangement at create time.
    if driver is not None:
        for arr_data in state.get("arrangement_candidates", []):
            arr_id = arr_data.get("id", "")
            new_status = arr_data.get("status", "")
            if arr_id and new_status in ("selected", "rejected"):
                update_query = (
                    "MATCH (a:ArrangementCandidate {id: $id}) "
                    "SET a.status = $status"
                )
                try:
                    async with driver.session() as session:
                        await session.run(update_query, id=arr_id, status=new_status)
                except Neo4jError as e:
                    logger.error(
                        "Failed to update status for ArrangementCandidate %s: %s",
                        arr_id, e,
                    )
                except Exception:
                    logger.exception("Unexpected error updating status for %s", arr_id)

    if callback:
        await callback(
            "realization_completed",
            {"arrangement_candidate_ids": arrangement_candidate_ids},
        )

    return {}
