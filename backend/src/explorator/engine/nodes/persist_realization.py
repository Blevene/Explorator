"""Persist realization node — write voicing plans, bass lines, and arrangements to Neo4j."""

import logging
from typing import Any

from neo4j import AsyncDriver
from neo4j.exceptions import Neo4jError

from explorator.engine.realization_state import RealizationState
from explorator.graph.arrangement_candidate_repo import ArrangementCandidateRepo
from explorator.graph.arrangement_family_repo import ArrangementFamilyRepo
from explorator.graph.bass_line_repo import BassLineRepo
from explorator.graph.voicing_plan_repo import VoicingPlanRepo
from explorator.models.realization import (
    ArrangementCandidate,
    ArrangementFamily,
    BassLine,
    VoicingPlan,
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


async def persist_realization(state: RealizationState, *, driver: AsyncDriver) -> dict[str, Any]:
    """Persist all realization artifacts to Neo4j in dependency order."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "persist_realization"})

    voicing_plan_repo = VoicingPlanRepo(driver)
    bass_line_repo = BassLineRepo(driver)
    arrangement_candidate_repo = ArrangementCandidateRepo(driver)
    arrangement_family_repo = ArrangementFamilyRepo(driver)

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

    # 3. Persist ArrangementCandidates + relationships
    arrangement_candidate_ids: list[str] = []
    for arr_data in state.get("arrangement_candidates", []):
        arr = ArrangementCandidate.model_validate(arr_data)
        try:
            await arrangement_candidate_repo.create(arr)
            arrangement_candidate_ids.append(arr.id)

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

        except Neo4jError as e:
            logger.error("Failed to persist ArrangementCandidate %s: %s", arr.id, e)
        except Exception:
            logger.exception("Unexpected error persisting ArrangementCandidate %s", arr.id)

    # 4. Persist ArrangementFamilies + relationships
    for fam_data in state.get("arrangement_families", []):
        fam = ArrangementFamily.model_validate(fam_data)
        try:
            await arrangement_family_repo.create(fam)

            # (ArrangementFamily)-[:CONTAINS]->(ArrangementCandidate)
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

    if callback:
        await callback(
            "realization_completed",
            {"arrangement_candidate_ids": arrangement_candidate_ids},
        )

    return {}
