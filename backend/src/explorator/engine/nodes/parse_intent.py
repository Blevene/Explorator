"""Parse intent node — extract constraints from prompt."""

from explorator.adapters.gemini import GeminiClient
from explorator.domain.intent.parser import IntentParser
from explorator.engine.state import ExplorationState


async def parse_intent(state: ExplorationState, *, gemini: GeminiClient) -> dict:
    """Extract structured creative brief from user prompt."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "parse_intent"})

    parser = IntentParser(gemini)
    brief = await parser.parse(state["prompt"], state["session_id"])

    # Update state with parsed intent
    result = {
        "creative_brief": brief.model_dump(mode="json"),
        "genre": brief.genre,
    }

    if callback:
        await callback("node_completed", {"node": "parse_intent", "genre": brief.genre})

    return result
