"""Genre profile endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from explorator.api.deps import get_style_repo
from explorator.graph.style_repo import StyleRepository

router = APIRouter(tags=["genres"])


class GenreSummary(BaseModel):
    """Summary of a genre profile."""

    genre: str
    display_name: str


class GenreListResponse(BaseModel):
    """Response for listing genres."""

    items: list[GenreSummary]


@router.get("/genres")
async def list_genres(
    repo: StyleRepository = Depends(get_style_repo),  # noqa: B008
) -> GenreListResponse:
    """List available genre profiles."""
    profiles = await repo.list_genre_profiles()
    items = [
        GenreSummary(
            genre=p.get("genre", "unknown"),
            display_name=p.get("display_name", p.get("genre", "unknown")),
        )
        for p in profiles
    ]
    return GenreListResponse(items=items)
