"""Shared utility functions."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(UTC)
