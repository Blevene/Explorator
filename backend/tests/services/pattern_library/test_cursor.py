"""Unit tests for pattern_library.cursor."""
import pytest

from explorator.services.pattern_library.cursor import (
    Cursor,
    InvalidCursor,
    parse_cursor,
)


def test_parse_none_none_returns_none() -> None:
    assert parse_cursor(None, None) is None


def test_parse_both_set_returns_cursor() -> None:
    result = parse_cursor(0.87, "01J_abc")
    assert result == Cursor(after_score=0.87, after_id="01J_abc")


def test_parse_only_score_raises() -> None:
    with pytest.raises(InvalidCursor):
        parse_cursor(0.5, None)


def test_parse_only_id_raises() -> None:
    with pytest.raises(InvalidCursor):
        parse_cursor(None, "01J_abc")
