"""Provider-neutral LLM client interface.

Every LLM adapter (``GeminiClient``, ``OpenAICompatClient``, ``FakeGeminiClient``)
satisfies ``LLMClient`` structurally; engine, domain and route code depends only
on this module. Provider selection lives in ``api/deps.get_llm_client``.
"""

from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel


class ModelTier(StrEnum):
    """Model tier selection — each provider maps tiers to configured model names."""

    PRO = "pro"
    FLASH = "flash"


class LLMClient(Protocol):
    """The two operations the app needs from any LLM provider."""

    async def generate_structured[T: BaseModel](
        self,
        prompt: str,
        response_model: type[T],
        tier: ModelTier = ModelTier.FLASH,
        system_prompt: str | None = None,
    ) -> T: ...

    async def generate_text(
        self,
        prompt: str,
        tier: ModelTier = ModelTier.FLASH,
        system_prompt: str | None = None,
    ) -> str: ...
