"""Runtime capability reporting for the frontend (limited-mode UI)."""
from fastapi import APIRouter, Request

router = APIRouter()

# Features that exist ONLY with a durable graph backend. In memory mode each is
# reported false so the UI can hide/disable the corresponding surface.
_NEO4J_ONLY = (
    "durable_persistence",
    "pattern_library",
    "feedback_learning",
    # "session_history" gates the in-session PROVENANCE timeline drawer
    # (frontend SessionHistory → getProvenance), which is empty in memory mode
    # via NullProvenanceTraceRepo — NOT the session LIST (GET /v1/sessions),
    # which is ungated and works in memory mode. Correctly false here.
    "session_history",
    "lineage",
    "genre_research",
    "curation",
)


@router.get("/capabilities")
async def get_capabilities(request: Request) -> dict[str, object]:
    mode = getattr(request.app.state, "persistence_mode", "memory")
    enabled = mode == "neo4j"
    return {
        "persistence_mode": mode,
        "features": {name: enabled for name in _NEO4J_ONLY},
    }
