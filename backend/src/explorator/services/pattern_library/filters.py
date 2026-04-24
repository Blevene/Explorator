"""Typed filter object for PatternLibraryRepo.list_page / iter_all.

Prevents raw kwargs leaking storage concerns back into the router. Add new
filter fields here, not as positional args on repo methods.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class PatternFilters:
    genre: str | None = None
    pattern_type: str | None = None
    curated_only: bool = False
