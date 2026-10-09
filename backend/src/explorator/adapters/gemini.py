"""Gemini API client with Pro/Flash model routing."""

import logging
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from explorator.adapters import usage
from explorator.adapters._structured import parse_structured
from explorator.adapters.llm import ModelTier  # re-exported; existing imports keep working

__all__ = ["GeminiClient", "ModelTier"]

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class GeminiClient:
    """Client for Google Gemini API with tiered model routing."""

    def __init__(
        self,
        api_key: str,
        pro_model: str = "gemini-pro-latest",
        flash_model: str = "gemini-flash-latest",
        timeout_seconds: int = 30,
    ) -> None:
        self.api_key = api_key
        self.pro_model = pro_model
        self.flash_model = flash_model
        self.timeout_seconds = timeout_seconds
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=timeout_seconds * 1000),
        )

    def get_model_name(self, tier: ModelTier) -> str:
        """Get the model name for a given tier."""
        if tier == ModelTier.PRO:
            return self.pro_model
        return self.flash_model

    async def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        tier: ModelTier = ModelTier.FLASH,
        system_prompt: str | None = None,
    ) -> T:
        """Generate a structured response validated against a Pydantic model."""
        model_name = self.get_model_name(tier)
        contents = prompt
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_model,
            system_instruction=system_prompt,
        )

        response = await self._client.aio.models.generate_content(
            model=model_name,
            contents=contents,
            config=config,
        )
        usage.record(model_name, response.usage_metadata, tier=tier.value)

        return parse_structured(
            response.text, response_model, provider="Gemini", model_name=model_name
        )

    async def generate_text(
        self,
        prompt: str,
        tier: ModelTier = ModelTier.FLASH,
        system_prompt: str | None = None,
    ) -> str:
        """Generate a plain text response."""
        model_name = self.get_model_name(tier)
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
        )

        response = await self._client.aio.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config,
        )
        usage.record(model_name, response.usage_metadata, tier=tier.value)

        if response.text is None:
            msg = f"Gemini returned empty response for model={model_name}"
            raise ValueError(msg)

        return response.text
