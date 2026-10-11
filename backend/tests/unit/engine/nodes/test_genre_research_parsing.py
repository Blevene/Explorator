"""Genre-research nodes must tolerate reasoning-model output around their JSON."""

from typing import Any

from neo4j import AsyncDriver
from pydantic import BaseModel

from explorator.adapters.llm import ModelTier
from explorator.engine.nodes.genre_research.critique import critique_draft


class _ScriptedClient:
    def __init__(self, text: str) -> None:
        self.text = text

    async def generate_structured(
        self, prompt: str, response_model: type[BaseModel],
        tier: ModelTier = ModelTier.FLASH, system_prompt: str | None = None,
    ) -> Any:
        raise AssertionError("critique uses generate_text")

    async def generate_text(
        self, prompt: str, tier: ModelTier = ModelTier.FLASH, system_prompt: str | None = None,
    ) -> str:
        return self.text


async def test_critique_parses_think_prefixed_fenced_json(neo4j_driver: AsyncDriver) -> None:
    raw = (
        "<think>Check {cadences} first.</think>\nHere is my review:\n"
        '```json\n{"issues": [], "passed": true}\n```'
    )
    state = {"job_id": "job-x", "genre_name": "dream_pop", "draft_yamls": {"profile": {}}}
    result = await critique_draft(state, gemini=_ScriptedClient(raw), driver=neo4j_driver)
    assert result["critique_trail"][-1]["passed"] is True
