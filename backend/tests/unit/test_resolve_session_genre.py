"""Unit tests for resolve_session_genre — the single source of truth for genre.

Genre lives only in ``metadata.genre``; the Session model has no top-level
``genre`` field. These cover: metadata genre present, absent, and non-dict
metadata (e.g. a JSON string from Neo4j, or garbage).
"""

from explorator.utils import resolve_session_genre


def test_metadata_genre_present() -> None:
    session = {"metadata": {"genre": "synthwave", "prompt": "moody"}}
    assert resolve_session_genre(session) == "synthwave"


def test_metadata_genre_absent_falls_back() -> None:
    session = {"metadata": {"prompt": "moody"}}
    assert resolve_session_genre(session) == "dream_pop"


def test_no_metadata_falls_back() -> None:
    assert resolve_session_genre({}) == "dream_pop"


def test_empty_string_genre_falls_back() -> None:
    # An empty-string genre is falsy and must degrade to the default, not "".
    session = {"metadata": {"genre": ""}}
    assert resolve_session_genre(session) == "dream_pop"


def test_metadata_as_json_string() -> None:
    # Neo4j may store metadata as a JSON string; parse_json_or_dict handles it.
    session = {"metadata": '{"genre": "ambient"}'}
    assert resolve_session_genre(session) == "ambient"


def test_non_dict_metadata_falls_back() -> None:
    # Non-dict / unparseable metadata parses to {} → default.
    assert resolve_session_genre({"metadata": "not-json"}) == "dream_pop"
    assert resolve_session_genre({"metadata": 42}) == "dream_pop"
