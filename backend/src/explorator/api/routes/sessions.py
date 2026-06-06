"""Session CRUD endpoints."""

import datetime
import os
import shutil
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from neo4j import AsyncDriver
from pydantic import BaseModel
from ulid import ULID

from explorator.api.deps import get_neo4j_driver, get_session_repo
from explorator.config import settings
from explorator.graph.session_repo import SessionRepository
from explorator.models.session import Session
from explorator.persistence.factory import make_provenance_trace_repo
from explorator.utils import parse_json_or_dict

router = APIRouter(tags=["sessions"])


class CreateSessionRequest(BaseModel):
    """Request body for creating a session."""

    mode: str = "full_exploration"
    prompt: str


class SessionResponse(BaseModel):
    """Response for a single session."""

    session_id: str
    status: str
    mode: str
    created_at: str
    prompt: str


class SessionListResponse(BaseModel):
    """Response for listing sessions."""

    items: list[SessionResponse]


@router.post("/sessions", status_code=201)
async def create_session(
    request: CreateSessionRequest,
    repo: SessionRepository = Depends(get_session_repo),  # noqa: B008
) -> SessionResponse:
    """Create a new exploration session."""
    session_id = f"sess_{ULID()}"
    now = datetime.datetime.now(datetime.UTC)

    session = Session(
        id=session_id,
        type="session",
        status="active",
        mode=request.mode,
        created_at=now,
        updated_at=now,
        metadata={"prompt": request.prompt},
    )
    await repo.create(session)

    return SessionResponse(
        session_id=session_id,
        status="active",
        mode=request.mode,
        created_at=now.isoformat(),
        prompt=request.prompt,
    )


@router.get("/sessions")
async def list_sessions(
    repo: SessionRepository = Depends(get_session_repo),  # noqa: B008
) -> SessionListResponse:
    """List all sessions."""
    sessions = await repo.list_sessions()
    items = [
        SessionResponse(
            session_id=s["id"],
            status=s.get("status", "unknown"),
            mode=s.get("mode", "unknown"),
            created_at=s.get("created_at", ""),
            prompt=parse_json_or_dict(s.get("metadata")).get("prompt", ""),
        )
        for s in sessions
    ]
    return SessionListResponse(items=items)


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    repo: SessionRepository = Depends(get_session_repo),  # noqa: B008
) -> SessionResponse:
    """Get a single session by ID."""
    session = await repo.get_by_id(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    metadata = parse_json_or_dict(session.get("metadata"))
    return SessionResponse(
        session_id=session["id"],
        status=session.get("status", "unknown"),
        mode=session.get("mode", "unknown"),
        created_at=session.get("created_at", ""),
        prompt=metadata.get("prompt", ""),
    )


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    repo: SessionRepository = Depends(get_session_repo),  # noqa: B008
    driver: AsyncDriver | None = Depends(get_neo4j_driver),  # noqa: B008
) -> None:
    """Delete a session and all its child nodes from Neo4j."""
    session = await repo.get_by_id(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # Remove exported files for this session from the filesystem
    export_dir = os.path.join(settings.export_dir, session_id)
    if os.path.isdir(export_dir):
        shutil.rmtree(export_dir)

    # Memory mode: filesystem export cleanup above is sufficient. The graph
    # cascade below (child nodes, relationships, library rows) is a Neo4j-only
    # concern; in-memory state is process-lifetime and lost on restart anyway.
    if driver is None:
        return

    # All three deletes share one transaction so a transient failure mid-cascade
    # cannot leave orphaned nodes (e.g. PatternLibraryEntry rows surviving while
    # their source ArrangementCandidate is gone).
    async with driver.session() as neo_session:
        tx = await neo_session.begin_transaction()
        try:
            # Delete PatternLibraryEntry nodes whose source arrangement belongs
            # to this session. These are linked via the denormalised
            # source_candidate_id property (no edge) and must be cleaned up
            # before the ArrangementCandidate sweep below.
            await tx.run(
                "MATCH (a:ArrangementCandidate {session_id: $sid}) "
                "WITH collect(a.id) AS aids "
                "MATCH (p:PatternLibraryEntry) WHERE p.source_candidate_id IN aids "
                "DETACH DELETE p",
                sid=session_id,
            )
            # Delete all nodes that reference this session_id (ArrangementCandidate, etc.)
            await tx.run(
                "MATCH (n) WHERE n.session_id = $sid DETACH DELETE n",
                sid=session_id,
            )
            # Delete the session node itself
            await tx.run(
                "MATCH (n:Session {id: $sid}) DETACH DELETE n",
                sid=session_id,
            )
            await tx.commit()
        except Exception:
            if not tx.closed():
                await tx.rollback()
            raise


class ProvenanceResponse(BaseModel):
    """Response for session provenance trace."""

    session_id: str
    events: list[dict[str, Any]]


@router.get("/sessions/{session_id}/provenance")
async def get_provenance(
    session_id: str,
    driver: AsyncDriver | None = Depends(get_neo4j_driver),  # noqa: B008
) -> ProvenanceResponse:
    """Return the provenance trace for a session.

    Returns an empty events list if no trace exists yet
    (session hasn't been explored). Memory mode always returns empty.
    """
    repo = make_provenance_trace_repo(driver)
    trace = await repo.get_by_session_id(session_id)
    if trace is None:
        return ProvenanceResponse(session_id=session_id, events=[])
    return ProvenanceResponse(
        session_id=session_id,
        events=trace.get("events", []),
    )
