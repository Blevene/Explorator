"""Gemini API client with Pro/Flash model routing."""

import json
import logging
from enum import StrEnum
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class ModelTier(StrEnum):
    """Gemini model tier selection."""

    PRO = "pro"
    FLASH = "flash"


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
        self._client = genai.Client(api_key=api_key)

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

        raw_text = response.text
        if raw_text is None:
            msg = f"Gemini returned empty response for model={model_name}"
            raise ValueError(msg)

        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as e:
            logger.error("Gemini returned invalid JSON (model=%s): %s", model_name, raw_text[:500])
            msg = f"Gemini returned malformed JSON for model={model_name}: {e}"
            raise ValueError(msg) from e

        try:
            return response_model.model_validate(parsed)
        except Exception:
            logger.error(
                "Gemini response failed validation (model=%s, schema=%s): %s",
                model_name, response_model.__name__, parsed,
            )
            raise

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

        if response.text is None:
            msg = f"Gemini returned empty response for model={model_name}"
            raise ValueError(msg)

        return response.text
