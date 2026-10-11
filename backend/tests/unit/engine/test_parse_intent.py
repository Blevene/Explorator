"""Unit tests for the parse_intent node's genre precedence.

An explicit genre threaded through `state["genre"]` (the user's picker choice)
must win over whatever the LLM-backed parser infers from the free-text prompt.
When absent, the node falls back to the parser's (brief's) genre.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from explorator.engine.nodes import parse_intent as parse_intent_module
from explorator.engine.nodes.parse_intent import parse_intent
from explorator.models.session import CreativeBrief


def _brief(genre: str) -> CreativeBrief:
    return CreativeBrief(
        id="cb_test",
        type="creative_brief",
        status="active",
        genre=genre,
    )


@pytest.fixture
def patched_parser(monkeypatch):
    """Patch IntentParser so .parse() yields a brief with the parser's genre."""

    def _install(parser_genre: str) -> CreativeBrief:
        brief = _brief(parser_genre)
        instance = MagicMock()
        instance.parse = AsyncMock(return_value=brief)
        monkeypatch.setattr(
            parse_intent_module, "IntentParser", lambda llm: instance
        )
        return brief

    return _install


async def test_explicit_genre_wins(patched_parser) -> None:
    # Parser infers "synthwave", but the user explicitly chose "cinematic".
    brief = patched_parser("synthwave")
    state = {
        "prompt": "something moody",
        "session_id": "S",
        "genre": "cinematic",
    }
    result = await parse_intent(state, llm=MagicMock())
    assert result["genre"] == "cinematic"
    # The stored brief is kept consistent with the resolved genre.
    assert result["creative_brief"]["genre"] == "cinematic"
    assert brief.genre == "cinematic"


async def test_falls_back_to_brief_genre_when_absent(patched_parser) -> None:
    patched_parser("synthwave")
    state = {"prompt": "something moody", "session_id": "S"}
    result = await parse_intent(state, llm=MagicMock())
    assert result["genre"] == "synthwave"
    assert result["creative_brief"]["genre"] == "synthwave"


async def test_empty_state_genre_falls_back(patched_parser) -> None:
    # An empty-string genre is falsy → fall back to the parser's genre.
    patched_parser("dream_pop")
    state = {"prompt": "x", "session_id": "S", "genre": ""}
    result = await parse_intent(state, llm=MagicMock())
    assert result["genre"] == "dream_pop"
