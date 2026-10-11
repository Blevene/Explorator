"""OpenAI-compatible chat-completions client.

Works with OpenAI, vLLM, Ollama (``/v1``), LM Studio and OpenRouter. Structured
output degrades through three modes — ``json_schema`` → ``json_object`` →
schema-in-prompt — and a mode becomes the default for this client only after a
request in that mode succeeds, so a 400 unrelated to ``response_format`` (e.g.
an over-long prompt) never sticks.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any, Literal

import openai
from pydantic import BaseModel

from explorator.adapters import usage
from explorator.adapters._structured import parse_structured, strip_reasoning
from explorator.adapters.llm import ModelTier

if TYPE_CHECKING:
    import httpx

logger = logging.getLogger(__name__)

SchemaMode = Literal["json_schema", "json_object", "prompt"]
_NEXT_MODE: dict[SchemaMode, SchemaMode] = {"json_schema": "json_object", "json_object": "prompt"}
_PROVIDER = "OpenAI-compatible endpoint"
_SCHEMA_INSTRUCTION = (
    "Respond with only a single JSON object that conforms to this JSON Schema. "
    "No prose, no markdown.\n"
)


class OpenAICompatClient:
    """LLM client for any OpenAI-compatible ``/chat/completions`` endpoint."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        pro_model: str,
        flash_model: str,
        timeout_seconds: int = 300,
        max_retries: int = 1,
        max_concurrency: int = 4,
        context_tokens: int | None = None,
        extra_body: dict[str, Any] | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.pro_model = pro_model
        self.flash_model = flash_model
        self.context_tokens = context_tokens
        self.extra_body = extra_body or {}
        self._client = openai.AsyncOpenAI(
            base_url=base_url or None,
            # Real OpenAI: None lets the SDK read OPENAI_API_KEY. Custom servers
            # usually ignore the key, but the SDK requires one.
            api_key=api_key or (None if not base_url else "not-needed"),
            timeout=timeout_seconds,
            max_retries=max_retries,
            # openai>=3 types this as httpx2 but still accepts legacy httpx clients at runtime
            http_client=http_client,  # type: ignore[arg-type]
        )
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._schema_mode: SchemaMode = "json_schema"
        self._context_warned = False

    def get_model_name(self, tier: ModelTier) -> str:
        """Get the model name for a given tier."""
        return self.pro_model if tier == ModelTier.PRO else self.flash_model

    async def generate_text(
        self,
        prompt: str,
        tier: ModelTier = ModelTier.FLASH,
        system_prompt: str | None = None,
    ) -> str:
        """Generate a plain text response (reasoning blocks removed)."""
        model = self.get_model_name(tier)
        content = await self._complete(model, tier, _messages(system_prompt, prompt))
        text = strip_reasoning(content or "").strip()
        if not text:
            msg = f"{_PROVIDER} returned empty response for model={model}"
            raise ValueError(msg)
        return text

    async def generate_structured[T: BaseModel](
        self,
        prompt: str,
        response_model: type[T],
        tier: ModelTier = ModelTier.FLASH,
        system_prompt: str | None = None,
    ) -> T:
        """Generate a response validated against ``response_model``."""
        model = self.get_model_name(tier)
        schema = response_model.model_json_schema()
        mode = self._schema_mode
        parse_attempts = 2  # one retry when the server ignored the schema

        while True:
            try:
                raw = await self._complete(
                    model,
                    tier,
                    _messages(_system_for(mode, system_prompt, schema), prompt),
                    _response_format(mode, response_model.__name__, schema),
                )
            except (openai.BadRequestError, openai.UnprocessableEntityError) as e:
                next_mode = _NEXT_MODE.get(mode)
                if next_mode is None:
                    raise
                logger.warning(
                    "%s rejected structured mode %s (model=%s, status=%s); trying %s",
                    _PROVIDER, mode, model, e.status_code, next_mode,
                )
                mode = next_mode
                continue

            try:
                result = parse_structured(
                    raw, response_model, provider=_PROVIDER, model_name=model
                )
            except ValueError:  # includes pydantic.ValidationError
                parse_attempts -= 1
                if parse_attempts == 0:
                    raise
                logger.warning(
                    "%s output did not match %s (model=%s, mode=%s); retrying once",
                    _PROVIDER, response_model.__name__, model, mode,
                )
                continue

            self._schema_mode = mode  # sticky only once a request in this mode succeeded
            return result

    async def _complete(
        self,
        model: str,
        tier: ModelTier,
        messages: list[dict[str, str]],
        response_format: dict[str, Any] | None = None,
    ) -> str | None:
        kwargs: dict[str, Any] = {"model": model, "messages": messages}
        if response_format is not None:
            kwargs["response_format"] = response_format
        if self.extra_body:
            kwargs["extra_body"] = self.extra_body
        async with self._semaphore:
            response = await self._client.chat.completions.create(**kwargs)
        self._record_usage(model, tier, response.usage)
        if not response.choices:
            return None
        content: str | None = response.choices[0].message.content
        return content

    def _record_usage(self, model: str, tier: ModelTier, counts: Any) -> None:
        if counts is None:
            return
        prompt_tokens = counts.prompt_tokens or 0
        details = getattr(counts, "prompt_tokens_details", None)
        usage.record_tokens(
            model,
            prompt_tokens,
            counts.completion_tokens or 0,
            getattr(details, "cached_tokens", 0) or 0,
            tier=tier.value,
        )
        if (
            self.context_tokens
            and not self._context_warned
            and prompt_tokens >= 0.9 * self.context_tokens
        ):
            self._context_warned = True
            logger.warning(
                "Prompt used %d of LLM_CONTEXT_TOKENS=%d (model=%s) — the server may be "
                "silently truncating context. See README 'LLM providers → Context length'.",
                prompt_tokens, self.context_tokens, model,
            )


def _messages(system_prompt: str | None, prompt: str) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": system_prompt}] if system_prompt else []
    return [*messages, {"role": "user", "content": prompt}]


def _system_for(mode: SchemaMode, system_prompt: str | None, schema: dict[str, Any]) -> str | None:
    if mode == "json_schema":
        return system_prompt
    instruction = _SCHEMA_INSTRUCTION + json.dumps(schema)
    return f"{system_prompt}\n\n{instruction}" if system_prompt else instruction


def _response_format(
    mode: SchemaMode, name: str, schema: dict[str, Any]
) -> dict[str, Any] | None:
    if mode == "json_schema":
        return {
            "type": "json_schema",
            # strict=False: Pydantic schemas use maxLength/$defs that OpenAI strict mode rejects.
            "json_schema": {"name": name, "schema": schema, "strict": False},
        }
    if mode == "json_object":
        return {"type": "json_object"}
    return None
