"""Structural contracts shared by the Neo4j and in-memory repo implementations.

Only the methods actually called by engine nodes / routes are declared — these
are the surfaces that must behave identically across backends. mypy uses these
to verify make_*() factory return types.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pydantic import BaseModel


@runtime_checkable
class CrudRepo(Protocol):
    async def create(self, entity: BaseModel) -> None: ...
    async def get_by_id(self, entity_id: str) -> dict[str, Any] | None: ...
    async def query_by_property(self, prop: str, value: Any) -> list[dict[str, Any]]: ...
    async def update_status(self, entity_id: str, status: str) -> None: ...


@runtime_checkable
class SessionRepoProto(CrudRepo, Protocol):
    async def list_sessions(self) -> list[dict[str, Any]]: ...


@runtime_checkable
class StyleRepoProto(Protocol):
    async def get_genre_profile(self, genre: str) -> dict[str, Any] | None: ...
    async def list_genre_profiles(self) -> list[dict[str, Any]]: ...
