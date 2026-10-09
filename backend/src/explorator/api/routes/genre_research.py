"""Genre research API endpoints."""

import asyncio
import contextlib
import logging
import re
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
from ulid import ULID

from explorator.adapters.llm import LLMClient
from explorator.adapters.usage import track_usage
from explorator.api.deps import get_gemini_client, get_genre_research_repo, get_neo4j_driver
from explorator.api.sse import SSEChannel
from explorator.domain.style.loader import discover_genres
from explorator.domain.style.service import STYLE_DIR
from explorator.engine.genre_research_graph import build_genre_research_graph
from explorator.graph.genre_research_repo import GenreResearchRepository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["genre_research"])

# In-memory SSE channels keyed by job_id
_channels: dict[str, SSEChannel] = {}

_GENRE_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,48}$")


# --- Request/Response models ---


class StartResearchRequest(BaseModel):
    genre_name: str
    reference_artists: list[str] = Field(default_factory=list)


class StartResearchResponse(BaseModel):
    job_id: str


class DraftSummary(BaseModel):
    job_id: str
    genre_name: str
    created_at: str


class DraftListResponse(BaseModel):
    items: list[DraftSummary]


class RejectRequest(BaseModel):
    reason: str = ""


# --- Endpoints ---


@router.post("/genres/research")
async def start_research(
    request: StartResearchRequest,
    gemini: LLMClient = Depends(get_gemini_client),  # noqa: B008
    repo: GenreResearchRepository = Depends(get_genre_research_repo),  # noqa: B008
    driver: Any = Depends(get_neo4j_driver),  # noqa: B008
) -> StartResearchResponse:
    """Kick off a genre research job.

    Requires a durable backend: genre research persists drafts and syncs to the
    graph. In memory mode it is disabled (409), matching the limited-mode UI.
    """
    if driver is None:
        raise HTTPException(
            status_code=409,
            detail="Genre research requires the database (unavailable in limited mode)",
        )

    genre_name = request.genre_name.lower().strip()

    if not _GENRE_NAME_RE.match(genre_name):
        raise HTTPException(
            status_code=400,
            detail="Genre name must be lowercase alphanumeric with underscores, 2-49 chars",
        )

    existing = discover_genres(STYLE_DIR)
    if genre_name in existing:
        raise HTTPException(status_code=409, detail=f"Genre '{genre_name}' already exists")

    if await repo.job_exists_for_genre(genre_name):
        raise HTTPException(
            status_code=409, detail=f"Research job already in progress for '{genre_name}'"
        )

    job_id = f"grj_{ULID()}"
    now = datetime.now(tz=UTC)
    job_data = {
        "id": job_id,
        "genre_name": genre_name,
        "reference_artists": request.reference_artists,
        "status": "researching",
        "research_log": "",
        "critique_trail": [],
        "draft_yamls": {},
        "created_at": now,
        "updated_at": now,
    }
    await repo.create_job(job_data)

    channel = SSEChannel()
    _channels[job_id] = channel

    graph = build_genre_research_graph(gemini, driver)
    initial_state = {
        "job_id": job_id,
        "genre_name": genre_name,
        "reference_artists": request.reference_artists,
        "on_progress": channel.send,
        "refine_iteration": 0,
    }

    async def run_and_close() -> None:
        try:
            with track_usage() as job_usage:
                try:
                    await graph.ainvoke(initial_state, {"recursion_limit": 20})
                finally:
                    t = job_usage.totals()
                    logger.info(
                        "Genre research job %s token usage: %d total (in=%d out=%d, ~$%.4f est.)",
                        job_id, t["total"], t["input"], t["output"], job_usage.estimated_cost_usd(),
                    )
        except Exception as e:
            logger.exception("Genre research failed for job %s", job_id)
            await repo.update_job(job_id, {"status": "failed", "error_message": str(e)})
            await channel.send("genre_research", {"status": "failed", "detail": str(e)})
        finally:
            await channel.close()
            _channels.pop(job_id, None)

    asyncio.create_task(run_and_close())

    return StartResearchResponse(job_id=job_id)


@router.get("/genres/research/{job_id}")
async def get_research_status(
    job_id: str,
    repo: GenreResearchRepository = Depends(get_genre_research_repo),  # noqa: B008
) -> dict[str, Any]:
    """Poll job status."""
    job = await repo.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/genres/research/{job_id}/stream")
async def stream_research_progress(job_id: str) -> EventSourceResponse:
    """SSE progress stream for a research job."""
    channel = _channels.get(job_id)
    if channel is None:
        raise HTTPException(status_code=404, detail="No active stream for this job")
    return EventSourceResponse(channel.stream())


@router.get("/genres/drafts")
async def list_pending_drafts(
    repo: GenreResearchRepository = Depends(get_genre_research_repo),  # noqa: B008
) -> DraftListResponse:
    """List all pending drafts."""
    drafts = await repo.list_pending_drafts()
    items = [
        DraftSummary(
            job_id=d["id"],
            genre_name=d.get("genre_name", ""),
            created_at=d.get("created_at", ""),
        )
        for d in drafts
    ]
    return DraftListResponse(items=items)


@router.get("/genres/drafts/{job_id}")
async def get_draft_detail(
    job_id: str,
    repo: GenreResearchRepository = Depends(get_genre_research_repo),  # noqa: B008
) -> dict[str, Any]:
    """Get full draft detail for review."""
    job = await repo.get_job(job_id)
    if job is None or job.get("status") != "pending_review":
        raise HTTPException(status_code=404, detail="Draft not found or not pending review")
    return job


@router.post("/genres/drafts/{job_id}/approve")
async def approve_draft(
    job_id: str,
    repo: GenreResearchRepository = Depends(get_genre_research_repo),  # noqa: B008
    driver: Any = Depends(get_neo4j_driver),  # noqa: B008
) -> dict[str, str]:
    """Approve a draft — writes YAML files and syncs to Neo4j."""
    import yaml

    from explorator.domain.style.service import StyleService

    job = await repo.get_job(job_id)
    if job is None or job.get("status") != "pending_review":
        raise HTTPException(status_code=404, detail="Draft not found or not pending review")

    genre_name = job["genre_name"]
    draft_yamls = job.get("draft_yamls", {})

    files_written: list[str] = []
    try:
        profile_path = STYLE_DIR / "genres" / f"{genre_name}.yaml"
        rules_path = STYLE_DIR / "rules" / f"{genre_name}_rules.yaml"
        grammar_path = STYLE_DIR / "grammars" / f"{genre_name}_grammar.yaml"

        profile_path.write_text(
            yaml.dump(draft_yamls.get("profile", {}), default_flow_style=False, sort_keys=False)
        )
        files_written.append(str(profile_path))

        rules_path.write_text(
            yaml.dump(draft_yamls.get("rules", {}), default_flow_style=False, sort_keys=False)
        )
        files_written.append(str(rules_path))

        grammar_path.write_text(
            yaml.dump(draft_yamls.get("grammar", {}), default_flow_style=False, sort_keys=False)
        )
        files_written.append(str(grammar_path))

        style_service = StyleService(driver)
        await style_service.sync_genres_to_neo4j()

    except Exception as err:
        import os

        for f in files_written:
            with contextlib.suppress(OSError):
                os.remove(f)
        logger.exception("Failed to approve genre %s", genre_name)
        raise HTTPException(status_code=500, detail="Failed to write genre files") from err

    await repo.update_job(job_id, {"status": "approved"})
    return {"status": "approved", "genre_name": genre_name}


@router.post("/genres/drafts/{job_id}/reject")
async def reject_draft(
    job_id: str,
    request: RejectRequest,
    repo: GenreResearchRepository = Depends(get_genre_research_repo),  # noqa: B008
) -> dict[str, str]:
    """Reject a draft with optional reason."""
    job = await repo.get_job(job_id)
    if job is None or job.get("status") != "pending_review":
        raise HTTPException(status_code=404, detail="Draft not found or not pending review")

    await repo.update_job(
        job_id,
        {
            "status": "rejected",
            "rejection_reason": request.reason,
        },
    )
    return {"status": "rejected"}
