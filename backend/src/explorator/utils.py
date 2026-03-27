"""Shared utility functions."""

import json
from datetime import UTC, datetime
from typing import Any


def utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(UTC)


def parse_json_or_dict(value: Any) -> dict[str, Any]:
    """Parse a value that may be a JSON string, dict, or None into a dict.

    Used for Neo4j properties that store dicts as JSON strings.
    """
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            result = json.loads(value)
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, TypeError):
            pass
    return {}
