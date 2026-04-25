"""Genre profile endpoints."""

import contextlib
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
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


def _parse_json_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Parse JSON string fields back to dicts/lists."""
    result = dict(data)
    for key, value in result.items():
        if isinstance(value, str) and value.startswith(("{", "[")):
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                result[key] = json.loads(value)
    return result


@router.get("/genres/{genre_name}")
async def get_genre_detail(
    genre_name: str,
    repo: StyleRepository = Depends(get_style_repo),  # noqa: B008
) -> dict[str, Any]:
    """Get full genre profile details."""
    profile = await repo.get_genre_profile(genre_name)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Genre '{genre_name}' not found")
    return _parse_json_fields(profile)
