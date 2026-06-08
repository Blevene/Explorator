"""Parse intent node — extract constraints from prompt."""

from typing import Any

from explorator.adapters.gemini import GeminiClient
from explorator.domain.intent.parser import IntentParser
from explorator.engine.state import ExplorationState


async def parse_intent(state: ExplorationState, *, gemini: GeminiClient) -> dict[str, Any]:
    """Extract structured creative brief from user prompt."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "parse_intent"})

    parser = IntentParser(gemini)
    brief = await parser.parse(state["prompt"], state["session_id"])

    # An explicit genre (chosen by the user, threaded via state) wins over the
    # genre the parser inferred from the free-text prompt. Keep the stored brief
    # consistent with the resolved genre.
    genre = state.get("genre") or brief.genre
    brief.genre = genre

    # Update state with parsed intent
    result = {
        "creative_brief": brief.model_dump(mode="json"),
        "genre": genre,
    }

    if callback:
        await callback("node_completed", {"node": "parse_intent", "genre": genre})

    return result
