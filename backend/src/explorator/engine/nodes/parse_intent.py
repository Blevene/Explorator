"""Parse intent node — extract constraints from prompt."""

from typing import Any

from explorator.adapters.llm import LLMClient
from explorator.domain.intent.parser import IntentParser
from explorator.engine.state import ExplorationState


async def parse_intent(state: ExplorationState, *, gemini: LLMClient) -> dict[str, Any]:
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

    # Explicit key + musical mode (threaded via state, like genre) win over the
    # brittle regex-parsed brief values. Without this the regex KEY_PATTERN
    # rarely fires and key_center stays None → generator defaults to C major.
    state_key = state.get("key_center")
    if state_key:
        brief.key_center = str(state_key)
    state_mode = state.get("mode")
    if state_mode:
        brief.mode = str(state_mode)

    # Update state with parsed intent
    result = {
        "creative_brief": brief.model_dump(mode="json"),
        "genre": genre,
    }

    if callback:
        await callback("node_completed", {"node": "parse_intent", "genre": genre})

    return result
