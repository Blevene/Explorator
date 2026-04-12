"""Export API routes — create and download export packages."""

import logging
import os
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from neo4j import AsyncDriver
from pydantic import BaseModel

from explorator.api.deps import get_neo4j_driver
from explorator.config import settings
from explorator.domain.export.json_renderer import JsonRenderContext
from explorator.domain.export.orchestrator import ExportRequest, render_and_write_artifacts
from explorator.graph.bass_line_repo import BassLineRepo
from explorator.graph.export_package_repo import ExportPackageRepo
from explorator.graph.render_artifact_repo import RenderArtifactRepo
from explorator.graph.repository import BaseRepository, ProgressionCandidateRepo
from explorator.graph.session_repo import SessionRepository
from explorator.graph.voicing_plan_repo import VoicingPlanRepo
from explorator.models.export import ExportPackage, RenderArtifact
from explorator.models.realization import ArrangementCandidate, BassLine, VoicingPlan
from explorator.models.session import CreativeBrief, Session

logger = logging.getLogger(__name__)
router = APIRouter(tags=["exports"])


# ---------------------------------------------------------------------------
# Inline repos for nodes without dedicated repo files
# ---------------------------------------------------------------------------


class ArrangementCandidateRepo(BaseRepository):
    label = "ArrangementCandidate"


class CreativeBriefRepo(BaseRepository):
    label = "CreativeBrief"

    async def get_by_session_id(self, session_id: str) -> dict[str, Any] | None:
        results = await self.query_by_property("session_id", session_id)
        return results[0] if results else None


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------


class ExportRequestBody(BaseModel):
    arrangement_candidate_ids: list[str]
    formats: list[str] = ["midi_combined", "json"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_beats_per_bar(meter: str) -> int:
    """Parse '4/4' → 4. Falls back to 4 on any error."""
    try:
        return int(meter.split("/")[0])
    except (IndexError, ValueError):
        return 4


def _short_id(entity_id: str) -> str:
    """Return the last 8 characters of an ID for use in filenames."""
    return entity_id[-8:]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/sessions/{session_id}/export")
async def create_export(
    session_id: str,
    body: ExportRequestBody,
    driver: AsyncDriver = Depends(get_neo4j_driver),  # noqa: B008
) -> dict[str, Any]:
    """Create an export package for the given arrangement candidates."""
    # Validate session exists
    session_repo = SessionRepository(driver)
    session_data = await session_repo.get_by_id(session_id)
    if session_data is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if not body.arrangement_candidate_ids:
        raise HTTPException(
            status_code=422, detail="At least one arrangement_candidate_id required"
        )

    # Load repos
    ac_repo = ArrangementCandidateRepo(driver)
    vp_repo = VoicingPlanRepo(driver)
    bl_repo = BassLineRepo(driver)
    prog_repo = ProgressionCandidateRepo(driver)
    cb_repo = CreativeBriefRepo(driver)
    artifact_repo = RenderArtifactRepo(driver)
    package_repo = ExportPackageRepo(driver)

    # Load creative brief for BPM and meter
    brief_data = await cb_repo.get_by_session_id(session_id)
    bpm: float = 120.0
    beats_per_bar: int = 4
    if brief_data:
        bpm = float(brief_data.get("tempo_hint_bpm") or 120)
        beats_per_bar = _parse_beats_per_bar(brief_data.get("meter", "4/4"))

    # Generate a package ID up-front (needed for output directory)
    package_id = f"pkg_{uuid4().hex[:12]}"
    output_dir = os.path.join(settings.export_dir, session_id, package_id)

    all_artifact_ids: list[str] = []
    all_artifact_meta: list[dict[str, Any]] = []

    for ac_id in body.arrangement_candidate_ids:
        # Load arrangement candidate
        ac_data = await ac_repo.get_by_id(ac_id)
        if ac_data is None:
            raise HTTPException(status_code=404, detail=f"ArrangementCandidate not found: {ac_id}")

        voicing_plan_id = ac_data.get("voicing_plan_id")
        bass_line_id = ac_data.get("bass_line_id")

        if not voicing_plan_id:
            raise HTTPException(
                status_code=422,
                detail=f"ArrangementCandidate {ac_id} has no voicing_plan_id",
            )
        if not bass_line_id:
            raise HTTPException(
                status_code=422,
                detail=f"ArrangementCandidate {ac_id} has no bass_line_id",
            )

        # Load VoicingPlan and BassLine dicts from Neo4j
        vp_data = await vp_repo.get_by_id(voicing_plan_id)
        bl_data = await bl_repo.get_by_id(bass_line_id)
        if vp_data is None:
            raise HTTPException(status_code=404, detail=f"VoicingPlan not found: {voicing_plan_id}")
        if bl_data is None:
            raise HTTPException(status_code=404, detail=f"BassLine not found: {bass_line_id}")

        # Reconstruct domain models
        voicing_plan = VoicingPlan.model_validate(vp_data)
        bass_line = BassLine.model_validate(bl_data)

        # Determine label for filenames
        ac_meta = ac_data.get("metadata") or {}
        if isinstance(ac_meta, str):
            import json as _json
            try:
                ac_meta = _json.loads(ac_meta)
            except Exception:
                ac_meta = {}
        label = str(ac_meta.get("label", "arr"))
        short_id = _short_id(ac_id)

        # Build optional JSON context
        json_context: JsonRenderContext | None = None
        if "json" in body.formats:
            prog_candidate_id = ac_data.get("progression_candidate_id")
            prog_data = await prog_repo.get_by_id(prog_candidate_id) if prog_candidate_id else None

            # Build Session and CreativeBrief models for JSON renderer
            session_obj = Session.model_validate({
                **session_data,
                "type": session_data.get("type", "session"),
                "status": session_data.get("status", "active"),
            })
            if brief_data:
                brief_obj = CreativeBrief.model_validate({
                    **brief_data,
                    "type": brief_data.get("type", "creative_brief"),
                    "status": brief_data.get("status", "active"),
                })
            else:
                # Minimal fallback brief
                brief_obj = CreativeBrief(
                    id="brief_fallback",
                    type="creative_brief",
                    status="active",
                    genre="unknown",
                )

            if prog_data:
                from explorator.models.harmony import ProgressionCandidate
                prog_obj = ProgressionCandidate.model_validate({
                    **prog_data,
                    "type": prog_data.get("type", "progression_candidate"),
                    "status": prog_data.get("status", "active"),
                    "rationale": prog_data.get("rationale", ""),
                    "key_center": prog_data.get("key_center", "C"),
                })
                arrangement_obj = ArrangementCandidate.model_validate({
                    **ac_data,
                    "type": ac_data.get("type", "arrangement_candidate"),
                    "status": ac_data.get("status", "active"),
                    "rationale": ac_data.get("rationale", ""),
                    "progression_candidate_id": prog_candidate_id or "",
                })
                json_context = JsonRenderContext(
                    session=session_obj,
                    creative_brief=brief_obj,
                    candidate=prog_obj,
                    arrangement=arrangement_obj,
                    voicing_plan=voicing_plan,
                    bass_line=bass_line,
                    scores={},
                    mutation_summaries=[],
                )

        # Render artifacts
        req = ExportRequest(
            label=label,
            short_id=short_id,
            voicing_plan=voicing_plan,
            bass_line=bass_line,
            bpm=bpm,
            beats_per_bar=beats_per_bar,
            formats=body.formats,
            output_dir=output_dir,
            json_context=json_context,
        )
        artifact_metas = render_and_write_artifacts(req)

        # Persist RenderArtifact nodes
        for meta in artifact_metas:
            artifact_id = f"art_{uuid4().hex[:12]}"
            artifact = RenderArtifact(
                id=artifact_id,
                type="render_artifact",
                status="ready",
                session_id=session_id,
                candidate_id=ac_id,
                artifact_type=meta["artifact_type"],
                path=meta["path"],
                render_metadata={"filename": meta["filename"]},
            )
            await artifact_repo.create(artifact)

            # Create Neo4j relationship: (RenderArtifact)-[:RENDERS]->(ArrangementCandidate)
            async with driver.session() as neo_session:
                await neo_session.run(
                    """
                    MATCH (a:RenderArtifact {id: $art_id})
                    MATCH (ac:ArrangementCandidate {id: $ac_id})
                    MERGE (a)-[:RENDERS]->(ac)
                    """,
                    art_id=artifact_id,
                    ac_id=ac_id,
                )

            all_artifact_ids.append(artifact_id)
            all_artifact_meta.append({
                "artifact_id": artifact_id,
                "arrangement_candidate_id": ac_id,
                "artifact_type": meta["artifact_type"],
                "filename": meta["filename"],
                "path": meta["path"],
            })

    # Create ExportPackage node
    package = ExportPackage(
        id=package_id,
        type="export_package",
        status="ready",
        session_id=session_id,
        included_candidate_ids=body.arrangement_candidate_ids,
        included_artifact_ids=all_artifact_ids,
        formats=body.formats,
    )
    await package_repo.create(package)

    # Create Neo4j relationships for the package
    async with driver.session() as neo_session:
        # (Session)-[:HAS_EXPORT]->(ExportPackage)
        await neo_session.run(
            """
            MATCH (s:Session {id: $sid})
            MATCH (p:ExportPackage {id: $pkg_id})
            MERGE (s)-[:HAS_EXPORT]->(p)
            """,
            sid=session_id,
            pkg_id=package_id,
        )
        # (ExportPackage)-[:INCLUDES]->(RenderArtifact)  and
        # (ExportPackage)-[:INCLUDES_CANDIDATE]->(ArrangementCandidate)
        for art_id in all_artifact_ids:
            await neo_session.run(
                """
                MATCH (p:ExportPackage {id: $pkg_id})
                MATCH (a:RenderArtifact {id: $art_id})
                MERGE (p)-[:INCLUDES]->(a)
                """,
                pkg_id=package_id,
                art_id=art_id,
            )
        for ac_id in body.arrangement_candidate_ids:
            await neo_session.run(
                """
                MATCH (p:ExportPackage {id: $pkg_id})
                MATCH (ac:ArrangementCandidate {id: $ac_id})
                MERGE (p)-[:INCLUDES_CANDIDATE]->(ac)
                """,
                pkg_id=package_id,
                ac_id=ac_id,
            )

    return {
        "package_id": package_id,
        "session_id": session_id,
        "formats": body.formats,
        "artifact_count": len(all_artifact_ids),
        "artifacts": all_artifact_meta,
    }


@router.get("/sessions/{session_id}/exports")
async def list_exports(
    session_id: str,
    driver: AsyncDriver = Depends(get_neo4j_driver),  # noqa: B008
) -> list[dict[str, Any]]:
    """List all export packages for a session."""
    session_repo = SessionRepository(driver)
    session_data = await session_repo.get_by_id(session_id)
    if session_data is None:
        raise HTTPException(status_code=404, detail="Session not found")

    package_repo = ExportPackageRepo(driver)
    packages = await package_repo.query_by_property("session_id", session_id)
    return packages


@router.get("/exports/{package_id}/artifacts/{artifact_id}/download")
async def download_artifact(
    package_id: str,
    artifact_id: str,
    driver: AsyncDriver = Depends(get_neo4j_driver),  # noqa: B008
) -> FileResponse:
    """Download a single render artifact file."""
    artifact_repo = RenderArtifactRepo(driver)
    artifact = await artifact_repo.get_by_id(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")

    file_path = artifact.get("path", "")
    if not file_path or not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Artifact file not found on disk")

    render_meta = artifact.get("render_metadata") or {}
    filename = render_meta.get("filename") or os.path.basename(file_path)
    artifact_type = artifact.get("artifact_type", "")

    if artifact_type in ("midi_combined", "midi_separate_chords", "midi_separate_bass"):
        media_type = "audio/midi"
    elif artifact_type == "json":
        media_type = "application/json"
    else:
        media_type = "application/octet-stream"

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename,
    )
