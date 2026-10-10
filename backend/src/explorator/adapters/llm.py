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


# Output-token cap for the per-candidate structured fan-out calls. Normal calls use
# ~50-100 answer tokens plus ~400-500 thinking tokens (Gemini counts thinking toward
# the cap), so 4096 leaves ample headroom while cutting off a runaway generation
# (e.g. a rationale string filling with junk) in seconds instead of minutes.
FANOUT_MAX_OUTPUT_TOKENS = 4096


class LLMClient(Protocol):
    """The two operations the app needs from any LLM provider."""

    async def generate_structured[T: BaseModel](
        self,
        prompt: str,
        response_model: type[T],
        tier: ModelTier = ModelTier.FLASH,
        system_prompt: str | None = None,
        max_output_tokens: int | None = None,
    ) -> T: ...

    async def generate_text(
        self,
        prompt: str,
        tier: ModelTier = ModelTier.FLASH,
        system_prompt: str | None = None,
    ) -> str: ...
