"""Gemini API client with Pro/Flash model routing."""

from enum import StrEnum
from typing import TypeVar

from pydantic import BaseModel


class ModelTier(StrEnum):
    """Gemini model tier selection."""

    PRO = "pro"
    FLASH = "flash"


T = TypeVar("T", bound=BaseModel)


class GeminiClient:
    """Client for Google Gemini API with tiered model routing.

    Uses Pro for creative/nuanced tasks, Flash for structured extraction
    and high-volume scoring.
    """

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
        """Generate a structured response using Gemini.

        This is a placeholder that will be fully implemented in M1
        when we need actual LLM calls. For M0, this establishes
        the interface contract.
        """
        raise NotImplementedError(
            "Gemini structured generation will be implemented in M1. "
            f"Would use model: {self.get_model_name(tier)}"
        )

    async def generate_text(
        self,
        prompt: str,
        tier: ModelTier = ModelTier.FLASH,
        system_prompt: str | None = None,
    ) -> str:
        """Generate a text response using Gemini.

        Placeholder for M1 implementation.
        """
        raise NotImplementedError(
            "Gemini text generation will be implemented in M1. "
            f"Would use model: {self.get_model_name(tier)}"
        )
