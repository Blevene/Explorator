"""Session CRUD endpoints."""

import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from ulid import ULID

from explorator.api.deps import get_session_repo
from explorator.graph.session_repo import SessionRepository
from explorator.models.session import Session
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
