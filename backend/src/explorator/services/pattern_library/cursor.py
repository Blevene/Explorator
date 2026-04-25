"""Plaintext keyset cursor for PatternLibraryRepo.list_page.

Chosen over opaque base64 encoding: library browser is internal tooling, so
DevTools-legibility beats API-contract opacity. Router emits `after_score` /
`after_id` as separate query params and response fields.
"""
from dataclasses import dataclass


class InvalidCursor(Exception):  # noqa: N818 — semantic name, not all exceptions are errors
    """Raised when exactly one of (after_score, after_id) is set."""


@dataclass(frozen=True)
class Cursor:
    after_score: float
    after_id: str


def parse_cursor(
    after_score: float | None,
    after_id: str | None,
) -> Cursor | None:
    """None if both are None; Cursor if both are set; raises InvalidCursor otherwise."""
    if after_score is None and after_id is None:
        return None
    if after_score is None or after_id is None:
        raise InvalidCursor(
            "after_score and after_id must be set together (either both or neither)"
        )
    return Cursor(after_score=after_score, after_id=after_id)
