"""Tests for the OpenAI-compatible adapter, using a mocked HTTP transport."""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import openai
import pytest
from pydantic import BaseModel, Field

from explorator.adapters import usage
from explorator.adapters.llm import LLMClient, ModelTier
from explorator.adapters.openai_compat import OpenAICompatClient

Handler = Callable[[httpx.Request], httpx.Response | Awaitable[httpx.Response]]


class _Sample(BaseModel):
    name: str = Field(max_length=10)
    value: int


def _completion(
    content: str | None, *, prompt_tokens: int = 10, completion_tokens: int = 5,
    cached: int | None = None, include_usage: bool = True,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": "c1", "object": "chat.completion", "created": 0, "model": "m",
        "choices": [{"index": 0, "finish_reason": "stop",
                     "message": {"role": "assistant", "content": content}}],
    }
    if include_usage:
        body["usage"] = {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                         "total_tokens": prompt_tokens + completion_tokens}
        if cached is not None:
            body["usage"]["prompt_tokens_details"] = {"cached_tokens": cached}
    return body


def _client(handler: Handler, **kwargs: Any) -> OpenAICompatClient:
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return OpenAICompatClient(
        base_url="http://local/v1", api_key="", pro_model="big-model",
        flash_model="small-model", max_retries=0, http_client=http, **kwargs,
    )


def _body(request: httpx.Request) -> dict[str, Any]:
    return json.loads(request.content)


def test_satisfies_protocol() -> None:
    client: LLMClient = _client(lambda r: httpx.Response(200, json=_completion("x")))
    assert client is not None


async def test_generate_text_routes_tier_and_sends_placeholder_key() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=_completion("hello"))

    client = _client(handler)
    assert await client.generate_text("p", tier=ModelTier.PRO, system_prompt="sys") == "hello"
    req = seen[0]
    assert str(req.url) == "http://local/v1/chat/completions"
    assert req.headers["authorization"] == "Bearer not-needed"
    body = _body(req)
    assert body["model"] == "big-model"
    assert body["messages"] == [
        {"role": "system", "content": "sys"}, {"role": "user", "content": "p"},
    ]


async def test_generate_text_strips_reasoning() -> None:
    client = _client(lambda r: httpx.Response(200, json=_completion("<think>x</think>\nlog text")))
    assert (await client.generate_text("p")).strip() == "log text"


async def test_generate_text_empty_raises() -> None:
    client = _client(lambda r: httpx.Response(200, json=_completion(None)))
    with pytest.raises(ValueError, match="empty response"):
        await client.generate_text("p")


async def test_structured_sends_json_schema_and_parses() -> None:
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(_body(request))
        return httpx.Response(200, json=_completion('{"name": "a", "value": 1}'))

    result = await _client(handler).generate_structured("p", _Sample)
    assert result == _Sample(name="a", value=1)
    rf = seen[0]["response_format"]
    assert rf["type"] == "json_schema"
    assert rf["json_schema"]["name"] == "_Sample"
    assert rf["json_schema"]["strict"] is False
    assert rf["json_schema"]["schema"]["properties"]["value"]["type"] == "integer"
    assert seen[0]["model"] == "small-model"


@pytest.mark.parametrize("status", [400, 422])
async def test_rejected_schema_downgrades_to_json_object_and_sticks(status: int) -> None:
    modes: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        rf = _body(request).get("response_format")
        modes.append(rf["type"] if rf else None)
        if rf and rf["type"] == "json_schema":
            error = {"error": {"message": "response_format unsupported"}}
            return httpx.Response(status, json=error)
        return httpx.Response(200, json=_completion('{"name": "a", "value": 1}'))

    client = _client(handler)
    await client.generate_structured("p", _Sample)
    await client.generate_structured("p", _Sample)
    assert modes == ["json_schema", "json_object", "json_object"]


async def test_json_object_rejected_falls_back_to_prompt_mode() -> None:
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = _body(request)
        seen.append(body)
        if "response_format" in body:
            return httpx.Response(400, json={"error": {"message": "nope"}})
        return httpx.Response(200, json=_completion('{"name": "a", "value": 1}'))

    assert await _client(handler).generate_structured("p", _Sample, system_prompt="sys")
    assert [b.get("response_format", {}).get("type") for b in seen] == [
        "json_schema", "json_object", None,
    ]
    system = seen[-1]["messages"][0]["content"]
    assert system.startswith("sys") and '"value"' in system  # schema embedded in prompt


async def test_400_unrelated_to_schema_does_not_stick() -> None:
    # Review Focus 1: e.g. prompt longer than server context — every mode 400s.
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls <= 3:
            return httpx.Response(400, json={"error": {"message": "context length exceeded"}})
        return httpx.Response(200, json=_completion('{"name": "a", "value": 1}'))

    client = _client(handler)
    with pytest.raises(openai.BadRequestError):
        await client.generate_structured("huge", _Sample)
    seen_modes: list[str | None] = []

    def recording(request: httpx.Request) -> httpx.Response:
        rf = _body(request).get("response_format")
        seen_modes.append(rf["type"] if rf else None)
        return httpx.Response(200, json=_completion('{"name": "a", "value": 1}'))

    client._client = _client(recording)._client  # swap transport, keep schema-mode state
    await client.generate_structured("small", _Sample)
    assert seen_modes == ["json_schema"]


async def test_404_wrong_base_url_surfaces_without_downgrade() -> None:
    # Review Focus 3: base URL missing /v1.
    modes: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        rf = _body(request).get("response_format")
        modes.append(rf["type"] if rf else None)
        return httpx.Response(404, json={"error": {"message": "not found"}})

    with pytest.raises(openai.NotFoundError):
        await _client(handler).generate_structured("p", _Sample)
    assert modes == ["json_schema"]


async def test_ignored_schema_with_prose_and_think_still_parses() -> None:
    content = '<think>{"draft": true}</think>Sure!\n```json\n{"name": "a", "value": 2}\n```'
    client = _client(lambda r: httpx.Response(200, json=_completion(content)))
    assert await client.generate_structured("p", _Sample) == _Sample(name="a", value=2)


async def test_unparseable_output_retries_once_then_raises() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=_completion("I cannot do that."))

    with pytest.raises(ValueError, match="malformed JSON"):
        await _client(handler).generate_structured("p", _Sample)
    assert calls == 2


async def test_validation_failure_retry_can_succeed() -> None:
    replies = iter(['{"name": "a"}', '{"name": "a", "value": 3}'])
    client = _client(lambda r: httpx.Response(200, json=_completion(next(replies))))
    assert await client.generate_structured("p", _Sample) == _Sample(name="a", value=3)


async def test_usage_recorded_under_passed_tier() -> None:
    client = _client(
        lambda r: httpx.Response(200, json=_completion("hi", prompt_tokens=120,
                                                       completion_tokens=30, cached=20))
    )
    with usage.track_usage() as u, usage.set_phase("parse_intent"):
        await client.generate_text("p", tier=ModelTier.FLASH)  # "small-model": no "flash" in name
    assert u.totals() == {"input": 120, "output": 30, "cached": 20, "total": 150}
    assert set(u.by_model) == {"flash"}


async def test_missing_usage_does_not_crash() -> None:
    # Review Focus 5.
    client = _client(lambda r: httpx.Response(200, json=_completion("hi", include_usage=False)))
    with usage.track_usage() as u:
        assert await client.generate_text("p") == "hi"
    assert u.totals()["total"] == 0


async def test_semaphore_caps_in_flight_requests() -> None:
    in_flight = 0
    peak = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.01)
        in_flight -= 1
        return httpx.Response(200, json=_completion("hi"))

    client = _client(handler, max_concurrency=2)
    await asyncio.gather(*(client.generate_text("p") for _ in range(6)))
    assert peak == 2


async def test_context_warning_once_at_threshold(caplog: pytest.LogCaptureFixture) -> None:
    client = _client(
        lambda r: httpx.Response(200, json=_completion("hi", prompt_tokens=3700)),
        context_tokens=4096,
    )
    with caplog.at_level(logging.WARNING, logger="explorator.adapters.openai_compat"):
        await client.generate_text("p")
        await client.generate_text("p")
    assert sum("context" in r.getMessage() for r in caplog.records) == 1


async def test_no_context_warning_when_unset(caplog: pytest.LogCaptureFixture) -> None:
    client = _client(lambda r: httpx.Response(200, json=_completion("hi", prompt_tokens=10**6)))
    with caplog.at_level(logging.WARNING, logger="explorator.adapters.openai_compat"):
        await client.generate_text("p")
    assert not [r for r in caplog.records if "context" in r.getMessage()]


async def test_real_openai_uses_env_key_when_none_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        return httpx.Response(200, json=_completion("hi"))

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OpenAICompatClient(
        base_url="", api_key="", pro_model="p", flash_model="f",
        max_retries=0, http_client=http,
    )
    await client.generate_text("x")
    assert seen["auth"] == "Bearer sk-test"


async def test_extra_body_is_merged_into_every_request() -> None:
    bodies: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(_body(request))
        return httpx.Response(200, json=_completion('{"name": "a", "value": 1}'))

    client = _client(handler, extra_body={"chat_template_kwargs": {"thinking": False}})
    await client.generate_text("p")
    await client.generate_structured("p", _Sample)
    assert all(b["chat_template_kwargs"] == {"thinking": False} for b in bodies)
    assert len(bodies) == 2


async def test_no_extra_fields_by_default() -> None:
    bodies: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(_body(request))
        return httpx.Response(200, json=_completion("hi"))

    await _client(handler).generate_text("p")
    assert set(bodies[0]) == {"model", "messages"}


async def test_max_tokens_sent_when_given_alongside_extra_body() -> None:
    bodies: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(_body(request))
        return httpx.Response(200, json=_completion('{"name": "a", "value": 1}'))

    client = _client(handler, extra_body={"chat_template_kwargs": {"thinking": False}})
    await client.generate_structured("p", _Sample, max_output_tokens=4096)
    assert bodies[0]["max_tokens"] == 4096
    assert bodies[0]["chat_template_kwargs"] == {"thinking": False}
    assert "response_format" in bodies[0]


async def test_max_tokens_survives_mode_downgrade() -> None:
    bodies: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(_body(request))
        if len(bodies) == 1:
            return httpx.Response(400, json={"error": {"message": "no schema"}})
        return httpx.Response(200, json=_completion('{"name": "a", "value": 1}'))

    await _client(handler).generate_structured("p", _Sample, max_output_tokens=512)
    assert [b["max_tokens"] for b in bodies] == [512, 512]


async def test_max_tokens_absent_by_default() -> None:
    bodies: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(_body(request))
        return httpx.Response(200, json=_completion('{"name": "a", "value": 1}'))

    await _client(handler).generate_structured("p", _Sample)
    assert "max_tokens" not in bodies[0]
