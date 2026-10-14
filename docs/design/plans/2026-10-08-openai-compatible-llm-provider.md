# Configurable LLM Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Explorator run against native Gemini (default, unchanged) or any OpenAI-compatible endpoint (OpenAI, vLLM, Ollama `/v1`, LM Studio, OpenRouter), selected by `LLM_*` configuration.

**Architecture:** A two-method `LLMClient` Protocol (`adapters/llm.py`) is implemented by the existing `GeminiClient` and a new `OpenAICompatClient`; a cached factory in `api/deps.py` picks one from `settings.llm_provider`. Both clients share a provider-neutral parse path (`adapters/_structured.py`) and record usage with an explicit tier. Silent LLM fallbacks are counted and surfaced in the token-usage event/panel.

**Tech Stack:** Python 3.13, FastAPI, pydantic-settings, google-genai, `openai` SDK (new), httpx `MockTransport` for tests, pytest-asyncio, React + vitest.

**Spec:** `docs/superpowers/specs/2026-10-08-openai-compatible-llm-provider-design.md`

## Global Constraints

- Branch: `feat/openai-compatible-llm`. Commit after every task; end every commit message with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- All pytest runs need the test Neo4j on **port 7689**: run `make neo4j-test-up` once from the repo root before the first pytest step. Run pytest from `backend/` with `uv run pytest ...`.
- `LLM_PROVIDER=gemini` must behave exactly as today. An existing `.env` using only `GEMINI_*` names must keep working.
- Do **not** rename `gemini=` kwargs, `FakeGeminiClient`, `GEMINI_MOCK`, or `test_gemini.py` (deferred follow-up PR).
- Usage `by_model` / `by_phase.model` keys stay `"pro"` / `"flash"`.
- No new test dependency: use `httpx.MockTransport`.
- `mypy` is strict on `src/` (`uv run mypy src`); `ruff check src tests` must stay clean.
- Prompts stay in `backend/src/explorator/prompts/` — the schema-instruction suffix in Task 6 is adapter mechanics, not a domain prompt.
- After any subagent work, check for and remove stray `CLAUDE.md` files before committing (`git status`).

## Review Focus

1. **A 400 that is not about `response_format`** (e.g. prompt longer than the server context) must not permanently downgrade the schema mode — the mode only becomes sticky after a downgraded request *succeeds*. Test in Task 6.
2. **Legacy-only `.env`** (`GEMINI_API_KEY`, `GEMINI_PRO_MODEL` …, no `LLM_*`) must resolve to identical Gemini settings; when both names are set, the `LLM_*` name wins. Tests in Task 4.
3. **Base URL without `/v1`** (e.g. `http://localhost:11434`) returns 404 — this must surface as an error, not trigger a schema downgrade or be swallowed. Test in Task 6; README note in Task 10.
4. **Reasoning text containing `{`/`}` before `</think>`** — and the common "chat template pre-fills `<think>`" output that has only a closing `</think>` — must not leak braces into the extracted JSON. Tests in Task 2.
5. **Server omits `usage`** (some Ollama/proxy builds) must not crash; tokens simply aren't recorded. Test in Task 6.

---

### Task 1: Apply the Gemini timeout (latent bug)

`GeminiClient` stores `timeout_seconds` but never passes it to `genai.Client`, so `GEMINI_TIMEOUT_SECONDS` has never had any effect. Isolated commit because it changes runtime behaviour.

**Files:**
- Modify: `backend/src/explorator/adapters/gemini.py:40`
- Test: `backend/tests/unit/adapters/test_gemini.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `GeminiClient(api_key, pro_model, flash_model, timeout_seconds)` — signature unchanged; now honours `timeout_seconds`.

- [ ] **Step 1: Write the failing test** — append to `backend/tests/unit/adapters/test_gemini.py`:

```python
def test_timeout_is_passed_to_genai_client(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _FakeGenaiClient:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    monkeypatch.setattr("explorator.adapters.gemini.genai.Client", _FakeGenaiClient)
    GeminiClient(api_key="k", timeout_seconds=45)

    http_options = captured["http_options"]
    assert http_options.timeout == 45_000  # type: ignore[attr-defined]  # google-genai uses ms
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/unit/adapters/test_gemini.py::test_timeout_is_passed_to_genai_client -v`
Expected: FAIL with `KeyError: 'http_options'`.

- [ ] **Step 3: Implement** — in `gemini.py` replace line 40:

```python
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=timeout_seconds * 1000),
        )
```

- [ ] **Step 4: Run adapter tests**

Run: `uv run pytest tests/unit/adapters/ -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/adapters/gemini.py backend/tests/unit/adapters/test_gemini.py
git commit -m "fix(gemini): actually apply GEMINI_TIMEOUT_SECONDS to the genai client"
```

---

### Task 2: Shared structured-output helpers

**Files:**
- Create: `backend/src/explorator/adapters/_structured.py`
- Modify: `backend/src/explorator/adapters/gemini.py` (remove `_truncate_to_max_length`, delegate parsing)
- Test: `backend/tests/unit/adapters/test_structured.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `strip_reasoning(text: str) -> str`
  - `extract_json(text: str) -> str`
  - `truncate_to_max_length(data: dict[str, Any] | list[Any], model: type[BaseModel]) -> dict[str, Any] | list[Any]`
  - `parse_structured(raw_text: str | None, response_model: type[T], *, provider: str, model_name: str) -> T` — raises `ValueError` on empty/malformed, `pydantic.ValidationError` (a `ValueError` subclass) on schema mismatch.

- [ ] **Step 1: Confirm nothing else uses the private helper or asserts on its messages**

Run: `grep -rn "_truncate_to_max_length\|malformed JSON\|returned empty response" backend/src backend/tests`
Expected: only `backend/src/explorator/adapters/gemini.py`. If tests assert on messages, keep `provider="Gemini"` so text is byte-identical.

- [ ] **Step 2: Write the failing tests** — create `backend/tests/unit/adapters/test_structured.py`:

```python
"""Tests for provider-neutral structured-output helpers."""

import json

import pytest
from pydantic import BaseModel, Field, ValidationError

from explorator.adapters._structured import (
    extract_json,
    parse_structured,
    strip_reasoning,
    truncate_to_max_length,
)


class _Item(BaseModel):
    note: str = Field(max_length=5)


class _Sample(BaseModel):
    name: str = Field(max_length=4)
    value: int
    items: list[_Item] = Field(default_factory=list)


# ── strip_reasoning ──────────────────────────────────────────────────────────

def test_strip_reasoning_removes_think_block() -> None:
    assert strip_reasoning("<think>hmm {x}</think>\nhello").strip() == "hello"


def test_strip_reasoning_handles_prefilled_think_with_only_closing_tag() -> None:
    # Chat templates for qwen3/deepseek-r1 often pre-fill "<think>" in the prompt,
    # so the completion contains reasoning followed by a bare closing tag.
    assert strip_reasoning("reasoning {not json}\n</think>\n{\"a\": 1}").strip() == '{"a": 1}'


def test_strip_reasoning_passthrough() -> None:
    assert strip_reasoning("plain text") == "plain text"


# ── extract_json ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('{"a": 1}', {"a": 1}),
        ('```json\n{"a": 1}\n```', {"a": 1}),
        ('Here you go:\n```json\n{"a": 1}\n```\nEnjoy!', {"a": 1}),
        ('```\n{"a": 1}', {"a": 1}),  # unterminated fence
        ('<think>I think {maybe} this</think>\n{"a": 1}', {"a": 1}),
        ('thinking about {braces}</think>```json\n{"a": 1}\n```', {"a": 1}),
        ('Sure! The answer is {"a": {"b": 2}} as requested.', {"a": {"b": 2}}),
        ('[1, 2, 3]', [1, 2, 3]),
    ],
)
def test_extract_json_variants(raw: str, expected: object) -> None:
    assert json.loads(extract_json(raw)) == expected


def test_extract_json_without_delimiters_returns_text_so_json_loads_raises() -> None:
    out = extract_json("no json here")
    with pytest.raises(json.JSONDecodeError):
        json.loads(out)


# ── truncate_to_max_length (previously untested) ─────────────────────────────

def test_truncate_top_level_field() -> None:
    data = {"name": "toolong", "value": 1}
    assert truncate_to_max_length(data, _Sample)["name"] == "tool"  # type: ignore[index]


def test_truncate_list_of_ref_items() -> None:
    data = {"name": "a", "value": 1, "items": [{"note": "abcdefgh"}, {"note": "ok"}]}
    out = truncate_to_max_length(data, _Sample)
    assert out["items"] == [{"note": "abcde"}, {"note": "ok"}]  # type: ignore[index]


def test_truncate_non_dict_passthrough() -> None:
    assert truncate_to_max_length([1, 2], _Sample) == [1, 2]


# ── parse_structured ─────────────────────────────────────────────────────────

def test_parse_structured_happy_path_with_fence_and_truncation() -> None:
    result = parse_structured(
        '```json\n{"name": "toolong", "value": 3}\n```', _Sample, provider="X", model_name="m"
    )
    assert result == _Sample(name="tool", value=3)


@pytest.mark.parametrize("raw", [None, ""])
def test_parse_structured_empty_raises(raw: str | None) -> None:
    with pytest.raises(ValueError, match="X returned empty response for model=m"):
        parse_structured(raw, _Sample, provider="X", model_name="m")


def test_parse_structured_malformed_raises_value_error() -> None:
    with pytest.raises(ValueError, match="X returned malformed JSON for model=m"):
        parse_structured("{not json", _Sample, provider="X", model_name="m")


def test_parse_structured_schema_mismatch_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        parse_structured('{"name": "a"}', _Sample, provider="X", model_name="m")
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/unit/adapters/test_structured.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'explorator.adapters._structured'`.

- [ ] **Step 4: Implement** — create `backend/src/explorator/adapters/_structured.py`:

```python
"""Provider-neutral helpers that turn raw LLM text into validated Pydantic models.

Shared by every LLM adapter so parsing behaviour (reasoning-block stripping,
markdown-fence unwrapping, maxLength truncation, validation logging) is
identical across providers.
"""

import json
import logging
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_THINK_CLOSE = "</think>"
_FENCE = re.compile(r"```(?:json)?[ \t]*\n?(.*?)```", re.DOTALL | re.IGNORECASE)


def strip_reasoning(text: str) -> str:
    """Remove ``<think>…</think>`` reasoning emitted by reasoning models.

    Also handles chat templates that pre-fill ``<think>`` in the prompt, where
    the completion contains reasoning followed by a bare closing tag: everything
    up to the last ``</think>`` is dropped.
    """
    stripped = _THINK_BLOCK.sub("", text)
    close = stripped.lower().rfind(_THINK_CLOSE)
    if close != -1:
        stripped = stripped[close + len(_THINK_CLOSE) :]
    return stripped


def extract_json(text: str) -> str:
    """Best-effort isolation of a JSON value from raw model output.

    Strips reasoning, unwraps a markdown fence anywhere in the text, then slices
    from the first ``{``/``[`` to the last matching ``}``/``]``. Returns the
    cleaned text unchanged when no delimiters exist, so ``json.loads`` raises a
    normal ``JSONDecodeError``.
    """
    cleaned = strip_reasoning(text)
    fence = _FENCE.search(cleaned)
    if fence:
        cleaned = fence.group(1)
    starts = [i for i in (cleaned.find("{"), cleaned.find("[")) if i != -1]
    if not starts:
        return cleaned.strip()
    start = min(starts)
    end = cleaned.rfind("}" if cleaned[start] == "{" else "]")
    if end < start:
        return cleaned.strip()
    return cleaned[start : end + 1]


def truncate_to_max_length(
    data: dict[str, Any] | list[Any],
    model: type[BaseModel],
) -> dict[str, Any] | list[Any]:
    """Truncate string fields to their maxLength constraint before validation.

    Prevents verbose model output from causing validation rejection. Handles
    top-level string fields and lists of ``$ref`` sub-models (one level deep),
    which is all current response models need.
    """
    if not isinstance(data, dict):
        return data

    schema = model.model_json_schema()
    props = schema.get("properties", {})
    defs = schema.get("$defs", {})

    for field_name, field_schema in props.items():
        value = data.get(field_name)
        if isinstance(value, str):
            max_len = field_schema.get("maxLength")
            if max_len and len(value) > max_len:
                data[field_name] = value[:max_len]

        if isinstance(value, list):
            items_ref = field_schema.get("items", {}).get("$ref", "")
            if not items_ref:
                continue
            sub_props = defs.get(items_ref.split("/")[-1], {}).get("properties", {})
            for item in value:
                if not isinstance(item, dict):
                    continue
                for sf_name, sf_schema in sub_props.items():
                    sub_value = item.get(sf_name)
                    sub_max = sf_schema.get("maxLength")
                    if isinstance(sub_value, str) and sub_max and len(sub_value) > sub_max:
                        item[sf_name] = sub_value[:sub_max]

    return data


def parse_structured(
    raw_text: str | None,
    response_model: type[T],
    *,
    provider: str,
    model_name: str,
) -> T:
    """Parse raw model text into ``response_model``.

    Raises ``ValueError`` for empty or malformed output and
    ``pydantic.ValidationError`` (a ``ValueError`` subclass) for schema mismatch.
    """
    if not raw_text:
        msg = f"{provider} returned empty response for model={model_name}"
        raise ValueError(msg)

    try:
        parsed = json.loads(extract_json(raw_text))
    except json.JSONDecodeError as e:
        logger.error(
            "%s returned invalid JSON (model=%s): %s", provider, model_name, raw_text[:500]
        )
        msg = f"{provider} returned malformed JSON for model={model_name}: {e}"
        raise ValueError(msg) from e

    parsed = truncate_to_max_length(parsed, response_model)

    try:
        return response_model.model_validate(parsed)
    except ValidationError:
        logger.error(
            "%s response failed validation (model=%s, schema=%s): %s",
            provider, model_name, response_model.__name__, parsed,
        )
        raise
```

- [ ] **Step 5: Delegate from `GeminiClient`** — in `backend/src/explorator/adapters/gemini.py`:
  - Delete the whole `_truncate_to_max_length` static method.
  - Delete the `import json` and `from typing import Any, TypeVar` → keep `TypeVar` only (`from typing import TypeVar`).
  - Add `from explorator.adapters._structured import parse_structured`.
  - Replace everything in `generate_structured` after `usage.record(...)` with:

```python
        return parse_structured(
            response.text, response_model, provider="Gemini", model_name=model_name
        )
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/unit/adapters/ -v && uv run mypy src && uv run ruff check src tests`
Expected: all PASS / clean (including the existing `test_usage.py` GeminiClient-with-AsyncMock test).

- [ ] **Step 7: Commit**

```bash
git add backend/src/explorator/adapters/_structured.py backend/src/explorator/adapters/gemini.py backend/tests/unit/adapters/test_structured.py
git commit -m "refactor(adapters): extract provider-neutral structured-output parsing"
```

---

### Task 3: `LLMClient` Protocol and annotation sweep

**Files:**
- Create: `backend/src/explorator/adapters/llm.py`
- Modify: `backend/src/explorator/adapters/gemini.py` (move `ModelTier` out, re-export)
- Modify (annotations/imports only): every file from `grep -rl GeminiClient backend/src --include='*.py'` except `adapters/gemini.py`, `adapters/gemini_mock.py`, `api/deps.py` — i.e. `engine/graph.py`, `engine/genre_research_graph.py`, `engine/nodes/*.py`, `engine/nodes/genre_research/*.py`, `domain/**`, `prompts/{feedback,mutation,explanation}.py`, `api/routes/{realization_rounds,feedback,mutations,genre_research,rounds,explanations}.py`
- Test: `backend/tests/unit/adapters/test_llm.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `explorator.adapters.llm.ModelTier` (StrEnum `PRO="pro"`, `FLASH="flash"`); `explorator.adapters.gemini.ModelTier` is the same object.
  - `explorator.adapters.llm.LLMClient` Protocol:
    - `async generate_structured(prompt: str, response_model: type[T], tier: ModelTier = ModelTier.FLASH, system_prompt: str | None = None) -> T`
    - `async generate_text(prompt: str, tier: ModelTier = ModelTier.FLASH, system_prompt: str | None = None) -> str`

- [ ] **Step 1: Baseline** — Run: `uv run mypy src && uv run ruff check src tests`. Expected: clean. If not clean on `main`, note pre-existing errors and don't count them against this task.

- [ ] **Step 2: Write the failing test** — create `backend/tests/unit/adapters/test_llm.py`:

```python
"""Tests for the provider-neutral LLM interface."""

from explorator.adapters import gemini, llm
from explorator.adapters.gemini import GeminiClient
from explorator.adapters.gemini_mock import FakeGeminiClient
from explorator.adapters.llm import LLMClient, ModelTier


def test_model_tier_is_reexported_from_gemini() -> None:
    assert gemini.ModelTier is llm.ModelTier
    assert ModelTier.PRO.value == "pro"
    assert ModelTier.FLASH.value == "flash"


def test_clients_satisfy_protocol_statically() -> None:
    # Checked by mypy (`uv run mypy src tests/unit/adapters/test_llm.py`);
    # at runtime this just proves both construct.
    clients: list[LLMClient] = [GeminiClient(api_key="k"), FakeGeminiClient()]
    assert len(clients) == 2
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/unit/adapters/test_llm.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'explorator.adapters.llm'`.

- [ ] **Step 4: Implement** — create `backend/src/explorator/adapters/llm.py`:

```python
"""Provider-neutral LLM client interface.

Every LLM adapter (``GeminiClient``, ``OpenAICompatClient``, ``FakeGeminiClient``)
satisfies ``LLMClient`` structurally; engine, domain and route code depends only
on this module. Provider selection lives in ``api/deps.get_llm_client``.
"""

from enum import StrEnum
from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ModelTier(StrEnum):
    """Model tier selection — each provider maps tiers to configured model names."""

    PRO = "pro"
    FLASH = "flash"


class LLMClient(Protocol):
    """The two operations the app needs from any LLM provider."""

    async def generate_structured(
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
```

In `adapters/gemini.py`: delete the `ModelTier` class and `from enum import StrEnum`; add
`from explorator.adapters.llm import ModelTier  # re-exported; existing imports keep working`
and add `__all__ = ["GeminiClient", "ModelTier"]` below the imports (so ruff F401 doesn't flag the re-export).
In `adapters/gemini_mock.py`: change `from explorator.adapters.gemini import ModelTier` → `from explorator.adapters.llm import ModelTier`.

- [ ] **Step 5: Annotation sweep** (mechanical; from repo root):

```bash
cd backend/src/explorator
FILES=$(grep -rl "GeminiClient" --include='*.py' . | grep -v -e '^./adapters/gemini.py$' -e '^./adapters/gemini_mock.py$' -e '^./api/deps.py$')
sed -i \
  -e 's/from explorator\.adapters\.gemini import GeminiClient, ModelTier/from explorator.adapters.llm import LLMClient, ModelTier/' \
  -e 's/from explorator\.adapters\.gemini import GeminiClient$/from explorator.adapters.llm import LLMClient/' \
  -e 's/\bGeminiClient\b/LLMClient/g' \
  $FILES
grep -rn "adapters.gemini import" $FILES   # remaining ones should import only ModelTier — switch them to adapters.llm too
cd - && cd backend && uv run ruff check --fix src && uv run ruff format --check src || true
```

Then inspect `git diff --stat` — only import/annotation/docstring lines should change. Any remaining `from explorator.adapters.gemini import ModelTier` in swept files: change to `explorator.adapters.llm`.

- [ ] **Step 6: Verify**

Run: `uv run mypy src tests/unit/adapters/test_llm.py && uv run ruff check src tests && uv run pytest tests/unit -q`
Expected: mypy clean (proves both clients satisfy `LLMClient`), ruff clean, unit tests PASS.

- [ ] **Step 7: Commit**

```bash
git add -A backend/src backend/tests/unit/adapters/test_llm.py
git commit -m "refactor: depend on LLMClient protocol instead of GeminiClient"
```

---

### Task 4: Unified `LLM_*` settings with legacy `GEMINI_*` aliases

**Files:**
- Modify: `backend/src/explorator/config.py`
- Modify: `backend/src/explorator/api/deps.py:82-87` (read `llm_*`)
- Modify: `backend/src/explorator/adapters/usage.py:125-137` (`_pricing` reads `llm_price_*`)
- Modify: `backend/src/explorator/api/app.py` lifespan (legacy-name warning)
- Test: `backend/tests/unit/test_config.py`

**Interfaces:**
- Consumes: nothing.
- Produces (after `Settings()` validation, all resolved):
  - `settings.llm_provider: Literal["gemini", "openai"]`
  - `settings.llm_api_key: str`, `settings.llm_base_url: str`
  - `settings.llm_pro_model: str`, `settings.llm_flash_model: str` (non-empty)
  - `settings.llm_timeout_seconds: int` (gemini 120 / openai 300 when unset)
  - `settings.llm_max_retries: int` (default 1)
  - `settings.llm_max_concurrency: int` (openai default 4; gemini 0 = unbounded, unused)
  - `settings.llm_context_tokens: int | None`
  - `settings.llm_price_{pro,flash}_{input,output}: float | None` (gemini defaults 1.25/10.0/0.30/2.50 when unset; openai stays `None`)
  - `settings.legacy_names_used: list[str]` (property; e.g. `["GEMINI_API_KEY"]`)

- [ ] **Step 1: Write the failing tests** — create `backend/tests/unit/test_config.py`:

```python
"""Tests for LLM provider settings resolution."""

import pytest
from pydantic import ValidationError

from explorator.config import Settings


@pytest.fixture(autouse=True)
def _clean_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    for key in list(os.environ):
        if key.startswith(("LLM_", "GEMINI_")) and key != "GEMINI_MOCK":
            monkeypatch.delenv(key)


def _settings(**kwargs: object) -> Settings:
    return Settings(_env_file=None, **kwargs)  # type: ignore[call-arg]


def test_gemini_defaults_match_previous_behaviour() -> None:
    s = _settings()
    assert s.llm_provider == "gemini"
    assert s.llm_pro_model == "gemini-pro-latest"
    assert s.llm_flash_model == "gemini-flash-latest"
    assert s.llm_timeout_seconds == 120
    assert (s.llm_price_pro_input, s.llm_price_pro_output) == (1.25, 10.0)
    assert (s.llm_price_flash_input, s.llm_price_flash_output) == (0.30, 2.50)
    assert s.legacy_names_used == []


def test_legacy_gemini_env_names_are_honoured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "legacy-key")
    monkeypatch.setenv("GEMINI_PRO_MODEL", "gemini-2.5-pro")
    monkeypatch.setenv("GEMINI_TIMEOUT_SECONDS", "90")
    monkeypatch.setenv("GEMINI_PRICE_PRO_INPUT", "2.0")
    s = _settings()
    assert s.llm_api_key == "legacy-key"
    assert s.llm_pro_model == "gemini-2.5-pro"
    assert s.llm_timeout_seconds == 90
    assert s.llm_price_pro_input == 2.0
    assert set(s.legacy_names_used) == {
        "GEMINI_API_KEY", "GEMINI_PRO_MODEL", "GEMINI_TIMEOUT_SECONDS", "GEMINI_PRICE_PRO_INPUT",
    }


def test_new_name_wins_over_legacy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "old")
    monkeypatch.setenv("LLM_API_KEY", "new")
    s = _settings()
    assert s.llm_api_key == "new"
    assert "GEMINI_API_KEY" not in s.legacy_names_used


def test_openai_provider_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("LLM_PRO_MODEL", "qwen3:32b")
    monkeypatch.setenv("LLM_FLASH_MODEL", "qwen3:8b")
    s = _settings()
    assert s.llm_timeout_seconds == 300
    assert s.llm_max_concurrency == 4
    assert s.llm_max_retries == 1
    assert s.llm_price_pro_input is None  # unpriced → "not priced" in the UI
    assert s.llm_context_tokens is None


def test_openai_without_models_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_PRO_MODEL", "qwen3:32b")
    with pytest.raises(ValidationError, match="LLM_FLASH_MODEL"):
        _settings()


def test_unknown_provider_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    with pytest.raises(ValidationError):
        _settings()


def test_openai_ignores_gemini_model_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    # Legacy GEMINI_* model names must not leak into an openai config.
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("GEMINI_PRO_MODEL", "gemini-pro-latest")
    monkeypatch.setenv("LLM_FLASH_MODEL", "qwen3:8b")
    with pytest.raises(ValidationError, match="LLM_PRO_MODEL"):
        _settings()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/test_config.py -v`
Expected: FAIL — `AttributeError: 'Settings' object has no attribute 'llm_provider'`.

- [ ] **Step 3: Implement `config.py`** — replace the `# Gemini` block, the `# Gemini pricing` block and `gemini_timeout_seconds` with the following (keep Neo4j, generation, export and `neo4j_query_timeout_seconds` as they are):

```python
"""Application configuration via environment variables."""

from typing import Literal, Self

from pydantic import PrivateAttr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Gemini-provider defaults (USD per 1M tokens are estimates — the models are
# *-latest aliases, so cost is surfaced as "~ estimate").
_GEMINI_DEFAULTS = {
    "llm_pro_model": "gemini-pro-latest",
    "llm_flash_model": "gemini-flash-latest",
    "llm_price_pro_input": 1.25,
    "llm_price_pro_output": 10.0,
    "llm_price_flash_input": 0.30,
    "llm_price_flash_output": 2.50,
}

# Pre-ADR-012 names still accepted; each fills its LLM_* counterpart when unset.
_LEGACY_SUFFIXES = (
    "api_key",
    "pro_model",
    "flash_model",
    "timeout_seconds",
    "price_pro_input",
    "price_pro_output",
    "price_flash_input",
    "price_flash_output",
)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7688"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "explorator_dev"

    # LLM provider — see docs/decisions/012-configurable-llm-provider.md.
    # Empty string / 0 / None mean "unset"; provider defaults resolve below.
    llm_provider: Literal["gemini", "openai"] = "gemini"
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_pro_model: str = ""
    llm_flash_model: str = ""
    llm_timeout_seconds: int = 0
    llm_max_retries: int = 1
    llm_max_concurrency: int = 0
    llm_context_tokens: int | None = None
    llm_price_pro_input: float | None = None
    llm_price_pro_output: float | None = None
    llm_price_flash_input: float | None = None
    llm_price_flash_output: float | None = None

    # Deprecated aliases — read only to fill unset LLM_* values (logged at startup).
    gemini_api_key: str | None = None
    gemini_pro_model: str | None = None
    gemini_flash_model: str | None = None
    gemini_timeout_seconds: int | None = None
    gemini_price_pro_input: float | None = None
    gemini_price_pro_output: float | None = None
    gemini_price_flash_input: float | None = None
    gemini_price_flash_output: float | None = None

    # Generation defaults
    default_max_rounds: int = 4
    default_target_score: float = 8.5
    default_generation_mode: str = "balanced"

    # Export
    export_dir: str = "exports"

    # Timeouts
    neo4j_query_timeout_seconds: int = 5

    _legacy_names_used: list[str] = PrivateAttr(default_factory=list)

    @property
    def legacy_names_used(self) -> list[str]:
        """Deprecated GEMINI_* env names that supplied a value."""
        return list(self._legacy_names_used)

    @model_validator(mode="after")
    def _resolve_llm(self) -> Self:
        legacy: list[str] = []
        for suffix in _LEGACY_SUFFIXES:
            new, old = f"llm_{suffix}", f"gemini_{suffix}"
            old_value = getattr(self, old)
            if old_value is None or getattr(self, new) not in ("", 0, None):
                continue
            # GEMINI_* model names never apply to a non-Gemini provider.
            if self.llm_provider != "gemini" and suffix.endswith("_model"):
                continue
            setattr(self, new, old_value)
            legacy.append(old.upper())
        self._legacy_names_used = legacy

        if self.llm_provider == "gemini":
            for name, default in _GEMINI_DEFAULTS.items():
                if getattr(self, name) in ("", None):
                    setattr(self, name, default)
            self.llm_timeout_seconds = self.llm_timeout_seconds or 120
        else:
            missing = [
                env
                for env, value in (
                    ("LLM_PRO_MODEL", self.llm_pro_model),
                    ("LLM_FLASH_MODEL", self.llm_flash_model),
                )
                if not value
            ]
            if missing:
                msg = f"LLM_PROVIDER={self.llm_provider} requires {', '.join(missing)}"
                raise ValueError(msg)
            self.llm_timeout_seconds = self.llm_timeout_seconds or 300
            self.llm_max_concurrency = self.llm_max_concurrency or 4
        return self


settings = Settings()
```

- [ ] **Step 4: Point consumers at the new names**
  - `api/deps.py` `GeminiClient(...)` call: `api_key=settings.llm_api_key, pro_model=settings.llm_pro_model, flash_model=settings.llm_flash_model, timeout_seconds=settings.llm_timeout_seconds`.
  - `adapters/usage.py` `_pricing()`: read `settings.llm_price_pro_input` etc. and coerce `None` to `0.0` (`settings.llm_price_pro_input or 0.0`). (Task 5 adds `is_priced`.)
  - `api/app.py` lifespan, right after `logger = logging.getLogger(__name__)`:

```python
    from explorator.config import settings

    for name in settings.legacy_names_used:
        logger.warning(
            "%s is deprecated — rename it to LLM_%s", name, name.removeprefix("GEMINI_")
        )
```

  - Run `grep -rn "settings\.gemini_" backend/src` — expected: no matches.

- [ ] **Step 5: Verify**

Run: `uv run pytest tests/unit/test_config.py tests/unit/adapters -v && uv run mypy src && uv run ruff check src tests`
Expected: PASS / clean. `test_estimated_cost_matches_pricing` still passes (Gemini defaults unchanged).

- [ ] **Step 6: Commit**

```bash
git add backend/src/explorator/config.py backend/src/explorator/api/deps.py backend/src/explorator/adapters/usage.py backend/src/explorator/api/app.py backend/tests/unit/test_config.py
git commit -m "feat(config): unified LLM_* settings with deprecated GEMINI_* aliases"
```

---

### Task 5: Usage — explicit tier, `is_priced`, fallback counter

**Files:**
- Modify: `backend/src/explorator/adapters/usage.py`
- Modify: `backend/src/explorator/adapters/gemini.py` (pass `tier=`)
- Modify: `backend/src/explorator/adapters/gemini_mock.py:219,230` (pass `tier=`)
- Modify: `backend/src/explorator/engine/nodes/plan_voicings.py:157`, `generate_melody.py:185`, `evaluate_progressions.py:47` (call `record_fallback`)
- Test: `backend/tests/unit/adapters/test_usage.py`

**Interfaces:**
- Consumes: `settings.llm_price_*: float | None` (Task 4).
- Produces:
  - `usage.record_tokens(model_name, input_tokens, output_tokens, cached_tokens=0, *, tier: str | None = None) -> None`
  - `usage.record_synthetic_tokens(..., *, tier: str | None = None)` — same shape
  - `usage.record(model_name, usage_metadata, *, tier: str | None = None)`
  - `usage.record_fallback(node: str) -> None` — no-op outside a scope
  - `usage.is_priced() -> bool`
  - `UsageAccumulator.fallbacks: dict[str, int]`; `to_event()` adds `"is_priced": bool`, `"fallbacks": dict[str, int]`

- [ ] **Step 1: Write the failing tests** — append to `backend/tests/unit/adapters/test_usage.py`:

```python
def test_explicit_tier_overrides_name_heuristic() -> None:
    # "qwen3:8b" has no "flash" in it — the heuristic would call it pro.
    with usage.track_usage() as u, usage.set_phase("plan_voicings"):
        usage.record_tokens("qwen3:8b", 100, 10, tier="flash")
    assert set(u.by_model) == {"flash"}
    assert u.by_phase["plan_voicings"].model == "flash"


def test_record_fallback_counts_and_is_noop_outside_scope() -> None:
    usage.record_fallback("plan_voicings")  # no scope → no error
    with usage.track_usage() as u:
        usage.record_fallback("plan_voicings")
        usage.record_fallback("plan_voicings")
        usage.record_fallback("generate_melody")
    assert u.fallbacks == {"plan_voicings": 2, "generate_melody": 1}
    assert u.to_event(1)["fallbacks"] == {"plan_voicings": 2, "generate_melody": 1}


def test_to_event_reports_priced_for_gemini_defaults() -> None:
    with usage.track_usage() as u:
        usage.record_tokens("gemini-pro-latest", 1, 1)
    assert u.to_event(1)["is_priced"] is True
    assert u.to_event(1)["fallbacks"] == {}


def test_unpriced_provider_reports_zero_cost_and_not_priced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from explorator.config import settings

    for name in (
        "llm_price_pro_input", "llm_price_pro_output",
        "llm_price_flash_input", "llm_price_flash_output",
    ):
        monkeypatch.setattr(settings, name, None)
    with usage.track_usage() as u:
        usage.record_tokens("qwen3:32b", 1_000_000, 1_000_000, tier="pro")
    event = u.to_event(1)
    assert event["is_priced"] is False
    assert event["estimated_cost_usd"] == 0
```

Add `import pytest` at the top of the file if absent. Also extend the existing `test_gemini_client_records_usage...` test (the one using `AsyncMock`, around line 83) — add after its asserts:

```python
    assert set(u.by_model) == {"pro"}
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/adapters/test_usage.py -v`
Expected: new tests FAIL (`unexpected keyword argument 'tier'`, no `record_fallback`).

- [ ] **Step 3: Implement in `usage.py`**
  - Module docstring first line: `"""Context-scoped LLM token-usage accumulator.` and "Every Gemini call funnels through ``adapters/gemini.py``" → "Every LLM call funnels through an adapter (``adapters/gemini.py``, ``adapters/openai_compat.py``)".
  - `UsageAccumulator`: add field `fallbacks: dict[str, int] = field(default_factory=dict)` after `by_phase`.
  - `add` signature → `def add(self, model_name: str, input_: int, output: int, cached: int, phase: str, *, tier: str | None = None) -> None:` and first line → `tier = tier or _tier_of(model_name)`.
  - `to_event`: after `"is_estimate": True,` add `"is_priced": is_priced(),` and `"fallbacks": dict(self.fallbacks),`.
  - `_pricing()` (already coerces None → 0.0 from Task 4). Add below it:

```python
def is_priced() -> bool:
    """True when any LLM_PRICE_* is configured (Gemini always has defaults)."""
    return any(
        price is not None
        for price in (
            settings.llm_price_pro_input,
            settings.llm_price_pro_output,
            settings.llm_price_flash_input,
            settings.llm_price_flash_output,
        )
    )
```

  - `record_tokens`, `record_synthetic_tokens`: add `*, tier: str | None = None` and pass `tier=tier` to `accumulator.add(...)`.
  - `record(model_name, usage_metadata, *, tier: str | None = None)`: pass `tier=tier` to `record_tokens`.
  - Add:

```python
def record_fallback(node: str) -> None:
    """Count an LLM call that failed and was replaced by a default. No-op outside a scope."""
    accumulator = _current.get()
    if accumulator is None:
        return
    accumulator.fallbacks[node] = accumulator.fallbacks.get(node, 0) + 1
```

- [ ] **Step 4: Pass tiers from clients**
  - `gemini.py` both methods: `usage.record(model_name, response.usage_metadata, tier=tier.value)`.
  - `gemini_mock.py`: `usage.record_synthetic_tokens(self.get_model_name(tier), 800, 200, tier=tier.value)` and `(..., 1200, 400, tier=tier.value)`.

- [ ] **Step 5: Wire fallback counting** — add `from explorator.adapters import usage` to each node, then:
  - `plan_voicings.py` inside `except Exception:` before `strategy = _default_strategy(...)`: `usage.record_fallback("plan_voicings")`
  - `generate_melody.py` inside `except Exception:` before `strategy = _default_strategy(...)`: `usage.record_fallback("generate_melody")`
  - `evaluate_progressions.py` inside `if isinstance(result, BaseException):` before `failed += 1`: `usage.record_fallback("evaluate_progressions")`

- [ ] **Step 6: Verify**

Run: `uv run pytest tests/unit tests/api -q && uv run mypy src && uv run ruff check src tests`
Expected: PASS / clean (existing `test_token_usage_event.py` still passes; new keys are additive).

- [ ] **Step 7: Commit**

```bash
git add backend/src/explorator/adapters backend/src/explorator/engine/nodes backend/tests/unit/adapters/test_usage.py
git commit -m "feat(usage): explicit tier, is_priced flag and LLM fallback counter"
```

---

### Task 6: `OpenAICompatClient`

**Files:**
- Modify: `backend/pyproject.toml` (+ `uv.lock`)
- Create: `backend/src/explorator/adapters/openai_compat.py`
- Test: `backend/tests/unit/adapters/test_openai_compat.py`

**Interfaces:**
- Consumes: `parse_structured`, `strip_reasoning` (Task 2); `ModelTier` (Task 3); `usage.record_tokens(..., tier=)` (Task 5).
- Produces: `OpenAICompatClient(*, base_url: str, api_key: str, pro_model: str, flash_model: str, timeout_seconds: int = 300, max_retries: int = 1, max_concurrency: int = 4, context_tokens: int | None = None, http_client: httpx.AsyncClient | None = None)` satisfying `LLMClient`; `get_model_name(tier) -> str`.

- [ ] **Step 1: Add the dependency**

Run: `cd backend && uv add openai && uv run python -c "import openai; print(openai.__version__)"`
Expected: prints a version; `pyproject.toml` gains `"openai>=<that version>"`, `uv.lock` updated.

- [ ] **Step 2: Write the failing tests** — create `backend/tests/unit/adapters/test_openai_compat.py`:

```python
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
            return httpx.Response(status, json={"error": {"message": "response_format unsupported"}})
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
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/unit/adapters/test_openai_compat.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'explorator.adapters.openai_compat'`.

- [ ] **Step 4: Implement** — create `backend/src/explorator/adapters/openai_compat.py`:

```python
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
from typing import TYPE_CHECKING, Any, Literal, TypeVar

import openai
from pydantic import BaseModel

from explorator.adapters import usage
from explorator.adapters._structured import parse_structured, strip_reasoning
from explorator.adapters.llm import ModelTier

if TYPE_CHECKING:
    import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

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
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.pro_model = pro_model
        self.flash_model = flash_model
        self.context_tokens = context_tokens
        self._client = openai.AsyncOpenAI(
            base_url=base_url or None,
            api_key=api_key or "not-needed",  # local servers ignore it; the SDK requires one
            timeout=timeout_seconds,
            max_retries=max_retries,
            http_client=http_client,
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

    async def generate_structured(
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
        async with self._semaphore:
            response = await self._client.chat.completions.create(**kwargs)
        self._record_usage(model, tier, response.usage)
        if not response.choices:
            return None
        return response.choices[0].message.content

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
```

> mypy note: if `chat.completions.create(**kwargs)` is flagged (overloads), keep `kwargs: dict[str, Any]` and add a narrow `# type: ignore[call-overload]` on that line only — do not loosen the module.

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/unit/adapters/test_openai_compat.py -v && uv run mypy src && uv run ruff check src tests`
Expected: all PASS / clean.

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/src/explorator/adapters/openai_compat.py backend/tests/unit/adapters/test_openai_compat.py
git commit -m "feat(adapters): OpenAI-compatible LLM client (vLLM, Ollama, OpenAI, ...)"
```

---

### Task 7: Provider factory and route wiring

**Files:**
- Modify: `backend/src/explorator/api/deps.py:76-87`
- Modify: `backend/src/explorator/api/routes/{realization_rounds,feedback,mutations,genre_research,rounds,explanations}.py` (import + `Depends`)
- Test: `backend/tests/api/test_llm_factory.py`

**Interfaces:**
- Consumes: `settings.llm_*` (Task 4), `OpenAICompatClient` (Task 6), `LLMClient` (Task 3).
- Produces: `get_llm_client() -> LLMClient` (lru_cached); `get_gemini_client` is the **same function object**.

- [ ] **Step 1: Write the failing tests** — create `backend/tests/api/test_llm_factory.py`:

```python
"""Provider selection in the LLM client factory."""

from collections.abc import Iterator

import pytest

from explorator.adapters.gemini import GeminiClient
from explorator.adapters.gemini_mock import FakeGeminiClient
from explorator.adapters.openai_compat import OpenAICompatClient
from explorator.api.deps import get_gemini_client, get_llm_client
from explorator.config import settings


@pytest.fixture(autouse=True)
def _fresh_factory(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv("GEMINI_MOCK", raising=False)
    get_llm_client.cache_clear()
    yield
    get_llm_client.cache_clear()


def test_legacy_name_is_same_function() -> None:
    assert get_gemini_client is get_llm_client


def test_mock_env_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_MOCK", "true")
    monkeypatch.setattr(settings, "llm_provider", "openai")
    assert isinstance(get_llm_client(), FakeGeminiClient)


def test_gemini_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    client = get_llm_client()
    assert isinstance(client, GeminiClient)
    assert client.pro_model == settings.llm_pro_model


def test_openai_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "llm_base_url", "http://localhost:11434/v1")
    monkeypatch.setattr(settings, "llm_pro_model", "qwen3:32b")
    monkeypatch.setattr(settings, "llm_flash_model", "qwen3:8b")
    monkeypatch.setattr(settings, "llm_max_concurrency", 3)
    client = get_llm_client()
    assert isinstance(client, OpenAICompatClient)
    assert (client.pro_model, client.flash_model) == ("qwen3:32b", "qwen3:8b")
    assert str(client._client.base_url).startswith("http://localhost:11434/v1")
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/api/test_llm_factory.py -v`
Expected: FAIL — `ImportError: cannot import name 'get_llm_client'`.

- [ ] **Step 3: Implement** — in `api/deps.py` replace the `GeminiClient` import with `from explorator.adapters.gemini import GeminiClient` + `from explorator.adapters.llm import LLMClient` as a **runtime** import (FastAPI may resolve dependency annotations; if ruff TC001 flags it, add `# noqa: TC001  # FastAPI resolves Depends annotations`), and replace `get_gemini_client` with:

```python
@lru_cache
def get_llm_client() -> LLMClient:
    """LLM client singleton for the configured provider.

    Returns FakeGeminiClient when GEMINI_MOCK=true (e2e / memory-mode lanes).
    """
    if os.environ.get("GEMINI_MOCK", "").lower() == "true":
        from explorator.adapters.gemini_mock import FakeGeminiClient
        return FakeGeminiClient()
    if settings.llm_provider == "openai":
        from explorator.adapters.openai_compat import OpenAICompatClient
        return OpenAICompatClient(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            pro_model=settings.llm_pro_model,
            flash_model=settings.llm_flash_model,
            timeout_seconds=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
            max_concurrency=settings.llm_max_concurrency,
            context_tokens=settings.llm_context_tokens,
        )
    return GeminiClient(
        api_key=settings.llm_api_key,
        pro_model=settings.llm_pro_model,
        flash_model=settings.llm_flash_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )


# Legacy name — the same function object, so `get_gemini_client.cache_clear()`
# in tests and FastAPI `Depends` identity keep working.
get_gemini_client = get_llm_client
```

Then in the six route files:

```bash
cd backend/src/explorator/api/routes
sed -i -e 's/\bget_gemini_client\b/get_llm_client/g' realization_rounds.py feedback.py mutations.py genre_research.py rounds.py explanations.py
cd - >/dev/null && cd backend && uv run ruff check --fix src/explorator/api
```

- [ ] **Step 4: Verify**

Run: `uv run pytest tests/api tests/unit -q && uv run mypy src && uv run ruff check src tests`
Expected: PASS / clean — including `test_memory_mode_endpoints.py` and `test_token_usage_event.py`, which call `get_gemini_client.cache_clear()`.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/api backend/tests/api/test_llm_factory.py
git commit -m "feat(api): select LLM client from LLM_PROVIDER"
```

---

### Task 8: Genre-research JSON hardening and provider-neutral provenance label

**Files:**
- Modify: `backend/src/explorator/engine/nodes/genre_research/{draft,critique,refine}.py`
- Modify: `backend/src/explorator/engine/nodes/generate_melody.py:221`
- Test: `backend/tests/unit/engine/nodes/test_genre_research_parsing.py`

**Interfaces:**
- Consumes: `extract_json` (Task 2), `settings.llm_provider` (Task 4).
- Produces: nothing new.

- [ ] **Step 1: Write the failing test** — create `backend/tests/unit/engine/nodes/test_genre_research_parsing.py`:

```python
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
    raw = '<think>Check {cadences} first.</think>\nHere is my review:\n```json\n{"issues": [], "passed": true}\n```'
    state = {"job_id": "job-x", "genre_name": "dream_pop", "draft_yamls": {"profile": {}}}
    result = await critique_draft(state, gemini=_ScriptedClient(raw), driver=neo4j_driver)
    assert result["critique_trail"][-1]["passed"] is True
```

(If `critique_draft` returns the trail entry as a model rather than a dict, adapt the final assertion to `.passed` — read the return statement at the end of `critique.py` first.)

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/engine/nodes/test_genre_research_parsing.py -v`
Expected: FAIL with `json.decoder.JSONDecodeError`.

- [ ] **Step 3: Implement** — in each of `draft.py`, `critique.py`, `refine.py`:
  - Add `from explorator.adapters._structured import extract_json`.
  - Replace the block from `text = raw_text.strip()` (draft: the `# Strip markdown code fences if present` comment too) through `parsed = json.loads(text)` with:

```python
    parsed = json.loads(extract_json(raw_text))
```

  - Update the comments above `generate_text` that say "Gemini additionalProperties" to keep the reason but stay accurate: `# generate_text + manual parsing: nested schemas trip Gemini's "additionalProperties" check.`

  In `generate_melody.py:221` replace `complement.source_strategy = f"gemini_flash_{genre}"` with
  `complement.source_strategy = f"{settings.llm_provider}_flash_{genre}"` and import `from explorator.config import settings` (Gemini output stays `gemini_flash_<genre>`).

- [ ] **Step 4: Verify**

Run: `uv run pytest tests/unit/engine tests/integration -q && uv run mypy src && uv run ruff check src tests`
Expected: PASS / clean.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/engine/nodes backend/tests/unit/engine/nodes/test_genre_research_parsing.py
git commit -m "fix(genre-research): tolerate reasoning/prose around JSON; neutral provenance label"
```

---

### Task 9: Token panel — "not priced" and fallbacks

**Files:**
- Modify: `frontend/src/services/sse.ts:20-30` (`TokenUsage`)
- Modify: `frontend/src/components/TokenUsagePanel.tsx`
- Test: `frontend/src/components/__tests__/TokenUsagePanel.test.tsx`

**Interfaces:**
- Consumes: usage event keys `is_priced: boolean`, `fallbacks: Record<string, number>` (Task 5).
- Produces: UI only.

- [ ] **Step 1: Write the failing tests** — append inside the `describe` in `TokenUsagePanel.test.tsx`:

```tsx
  it('shows "not priced" instead of a dollar estimate for unpriced providers', () => {
    useCandidateStore.getState().setLiveUsage({ ...sample, is_priced: false, estimated_cost_usd: 0 });
    render(<TokenUsagePanel />);
    expect(screen.getAllByText(/not priced/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/est\./)).toBeNull();
  });

  it('flags LLM fallbacks with a per-node tooltip', () => {
    useCandidateStore.getState().setLiveUsage({
      ...sample,
      fallbacks: { plan_voicings: 2, generate_melody: 1 },
    });
    render(<TokenUsagePanel />);
    const badge = screen.getByTestId('token-usage-fallbacks');
    expect(badge).toHaveTextContent('3 fallbacks');
    expect(badge.getAttribute('title')).toContain('plan_voicings ×2');
  });

  it('shows no fallback badge when there were none', () => {
    useCandidateStore.getState().setLiveUsage({ ...sample, fallbacks: {} });
    render(<TokenUsagePanel />);
    expect(screen.queryByTestId('token-usage-fallbacks')).toBeNull();
  });
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/components/__tests__/TokenUsagePanel.test.tsx`
Expected: FAIL (type errors on unknown keys / missing text).

- [ ] **Step 3: Implement**
  - `sse.ts` `TokenUsage`: add, after `is_synthetic: boolean;`

```ts
  /** False when no LLM_PRICE_* is configured (e.g. local models). Absent on pre-012 events. */
  is_priced?: boolean;
  /** LLM calls per node that failed and were replaced by defaults. */
  fallbacks?: Record<string, number>;
```

  - `TokenUsagePanel.tsx`: after `if (!current) return null;` add

```tsx
  const priced = current.is_priced !== false;
  const cost = (n: number) => (priced ? usd(n) : 'not priced');
  const fallbackEntries = Object.entries(current.fallbacks ?? {});
  const fallbackCount = fallbackEntries.reduce((sum, [, n]) => sum + n, 0);
```

  - Replace both `{usd(current.estimated_cost_usd)}` and `{usd(session.cost)}` with `{cost(current.estimated_cost_usd)}` / `{cost(session.cost)}`.
  - Next to the `synthetic` badge (inside the same header `<span>`), add:

```tsx
          {fallbackCount > 0 && (
            <span
              data-testid="token-usage-fallbacks"
              className="normal-case tracking-normal rounded px-1.5 py-0.5"
              style={{ background: 'var(--surface-3, var(--surface-1))', color: 'var(--accent-warning, var(--text-muted))', border: '1px solid var(--border-subtle)' }}
              title={`LLM calls that failed and were replaced by defaults: ${fallbackEntries.map(([node, n]) => `${node} ×${n}`).join(', ')}`}
            >
              {fallbackCount} fallback{fallbackCount === 1 ? '' : 's'}
            </span>
          )}
```

  (Check `frontend/src/index.css` for the warning token name; use the existing one if `--accent-warning` doesn't exist.)

- [ ] **Step 4: Verify**

Run: `cd frontend && npm run test:unit && npx tsc --noEmit && npm run build`
Then: `grep -rn "token-usage" e2e/` from the repo root — confirm no existing selector changed (only additions).
Expected: all PASS; build clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/sse.ts frontend/src/components/TokenUsagePanel.tsx frontend/src/components/__tests__/TokenUsagePanel.test.tsx
git commit -m "feat(ui): token panel shows 'not priced' and LLM fallback count"
```

---

### Task 10: Documentation

**Files:**
- Modify: `backend/.env.example`
- Modify: `README.md` (Quick start env line ~97; add "LLM providers" section after setup; neutral wording at lines ~11, 13, 24, 67, 69, 234, 272-277 where they describe runtime behaviour — keep historical/ADR references to Gemini)
- Create: `docs/decisions/012-configurable-llm-provider.md`
- Modify: `docs/decisions/011-token-usage-instrumentation.md` (addendum), `docs/decisions/README.md` (index row, if it lists ADRs)

**Interfaces:** none.

- [ ] **Step 1: `.env.example`** — replace the `# Gemini` block with:

```bash
# ── LLM provider ────────────────────────────────────────────────────────────
# gemini (default) | openai  (any OpenAI-compatible endpoint: OpenAI, vLLM,
# Ollama, LM Studio, OpenRouter). Legacy GEMINI_* names still work but are
# deprecated — a warning is logged at startup.
LLM_PROVIDER=gemini
LLM_API_KEY=your-api-key-here
# LLM_PRO_MODEL=gemini-pro-latest
# LLM_FLASH_MODEL=gemini-flash-latest

# Ollama (note the /v1 suffix; set OLLAMA_CONTEXT_LENGTH on the server):
# LLM_PROVIDER=openai
# LLM_BASE_URL=http://localhost:11434/v1
# LLM_PRO_MODEL=qwen3:32b
# LLM_FLASH_MODEL=qwen3:8b
# LLM_CONTEXT_TOKENS=16384

# vLLM:
# LLM_PROVIDER=openai
# LLM_BASE_URL=http://gpu-box:8000/v1
# LLM_PRO_MODEL=Qwen/Qwen3-32B
# LLM_FLASH_MODEL=Qwen/Qwen3-32B

# Optional tuning (defaults shown for openai):
# LLM_TIMEOUT_SECONDS=300
# LLM_MAX_CONCURRENCY=4
# LLM_MAX_RETRIES=1
# LLM_PRICE_PRO_INPUT=   LLM_PRICE_PRO_OUTPUT=   (USD per 1M tokens; unset = "not priced")
# LLM_PRICE_FLASH_INPUT= LLM_PRICE_FLASH_OUTPUT=
```

- [ ] **Step 2: README "LLM providers" section** — add:

```markdown
## LLM providers

Explorator talks to an LLM through one of two adapters, chosen by `LLM_PROVIDER`
in `backend/.env` (see `backend/.env.example` for full recipes):

| Provider | `LLM_PROVIDER` | Required | Notes |
|---|---|---|---|
| Google Gemini (default) | `gemini` | `LLM_API_KEY` | Native SDK; models default to `gemini-pro-latest` / `gemini-flash-latest` |
| OpenAI | `openai` | `LLM_API_KEY`, `LLM_PRO_MODEL`, `LLM_FLASH_MODEL` | Leave `LLM_BASE_URL` empty |
| Ollama | `openai` | `LLM_BASE_URL=http://localhost:11434/v1`, both models | No key needed |
| vLLM / LM Studio / OpenRouter | `openai` | `LLM_BASE_URL=…/v1`, both models | |

The **pro** model handles harmony generation, mutation and explanations; the
**flash** model handles intent parsing, evaluation, voicing/melody planning and
genre research. Using one model for both is fine.

**Base URL must end in `/v1`.** A 404 at startup of a round usually means it doesn't.

**Context length (Ollama).** Ollama's default context window (2–4k tokens) silently
truncates Explorator's longer prompts, and the `/v1` API can't change it per request.
Start the server with `OLLAMA_CONTEXT_LENGTH=16384` (or set `num_ctx` in a Modelfile),
and set `LLM_CONTEXT_TOKENS` to the same value so Explorator warns when a prompt nears it.

**Concurrency.** Rounds fan out several LLM calls at once. `LLM_MAX_CONCURRENCY`
(default 4) caps in-flight requests; for Ollama, keep it ≤ `OLLAMA_NUM_PARALLEL`.

**Structured output.** The adapter asks for `json_schema` output, falls back to JSON
mode and then to schema-in-prompt if the server rejects it, and strips `<think>`
blocks from reasoning models. If a model still can't produce valid JSON, the round
completes with default strategies and the token panel shows an "N fallbacks" badge —
try a larger model.

**Cost.** Gemini shows estimated cost. Other providers show "not priced" unless you
set `LLM_PRICE_*` (USD per 1M tokens).
```

Update the Quick start line `# Edit backend/.env and set GEMINI_API_KEY.` → `# Edit backend/.env and set LLM_API_KEY (or configure another provider — see "LLM providers").`

- [ ] **Step 3: ADR 012** — create `docs/decisions/012-configurable-llm-provider.md` following the format of `011-token-usage-instrumentation.md` (read it first for headings). Content:
  - **Context:** single hard-wired Gemini adapter; desire to run local models (vLLM, Ollama) and other hosted APIs.
  - **Decision:** `LLMClient` Protocol; keep native `GeminiClient`; add `OpenAICompatClient`; `LLM_PROVIDER` selects; one `LLM_*` settings namespace with deprecated `GEMINI_*` aliases; structured-output mode ladder sticky-on-success; shared `_structured.py`; fallback counter surfaced in usage.
  - **Rejected:** routing Gemini through its OpenAI-compat endpoint (loses native `response_schema` behaviour, different usage fields); per-tier provider mixing (YAGNI); LiteLLM / instructor (dependency weight vs ~150 lines).
  - **Consequences:** `gemini=` kwarg names, `FakeGeminiClient`, `GEMINI_MOCK` intentionally unchanged pending a mechanical rename PR; Ollama context length is an operator concern (documented).

- [ ] **Step 4: ADR 011 addendum** — append:

```markdown
## Addendum (2026-10-08, ADR 012)

- Adapters now pass the tier explicitly (`record_tokens(..., tier=)`); the
  model-name heuristic remains only as a fallback for callers that don't.
- Usage events carry `is_priced` (false when no `LLM_PRICE_*` is configured —
  the UI shows "not priced") and `fallbacks` (per-node count of LLM calls that
  failed and were replaced by defaults).
- Pricing settings are now `LLM_PRICE_*`; `GEMINI_PRICE_*` remain as deprecated aliases.
```

- [ ] **Step 5: Commit**

```bash
git add backend/.env.example README.md docs/decisions
git commit -m "docs: LLM provider configuration, ADR 012, ADR 011 addendum"
```

---

### Task 11: Full verification

**Files:** none (fixes only if something fails — fix in the owning task's files and commit separately).

- [ ] **Step 1: Backend** — from `backend/`: `uv run pytest tests/ -q && uv run mypy src && uv run ruff check src tests`
Expected: all PASS / clean.

- [ ] **Step 2: Frontend** — from `frontend/`: `npm run test:unit && npx tsc --noEmit && npm run build`
Expected: PASS / clean.

- [ ] **Step 3: E2E mock lane** — from repo root, run the Playwright lane exactly as CI does (see `.github/workflows/ci.yml` e2e job; it runs under `GEMINI_MOCK=true`).
Expected: PASS (known flake `ux-coherence:11 navigation-flow` passes in isolation).

- [ ] **Step 4: Gemini regression smoke (real key)** — with the user's existing `backend/.env` (only `GEMINI_*` names), start the backend (`make backend`, binds 0.0.0.0) and run one exploration round from the UI or via `curl`. Expected: round completes, a startup warning lists the deprecated `GEMINI_*` names, token panel shows `~$… est.` and no fallback badge.

- [ ] **Step 5: Local-model smoke (if available)** — ask the user whether an Ollama or vLLM server is reachable. If yes, set `LLM_PROVIDER=openai`, `LLM_BASE_URL`, both models (and `LLM_CONTEXT_TOKENS` for Ollama), restart, run one exploration round **and** one genre-research run. Record from the usage SSE event: `by_model` tiers, `is_priced` (false), and `fallbacks`. "It ran" is not a pass — report any non-empty `fallbacks` with node names. If no server is available, say so explicitly in the final report.

- [ ] **Step 6: Final review** — `git log --oneline main..HEAD`, `git status` (no stray `CLAUDE.md` files), and summarise results (including skipped steps) for the user.
