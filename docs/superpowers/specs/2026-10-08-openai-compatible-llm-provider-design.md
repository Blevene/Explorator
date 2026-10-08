# Configurable LLM Provider (Gemini + OpenAI-compatible) — Design

**Date:** 2026-10-08
**Status:** Draft — awaiting review
**Branch:** `feat/openai-compatible-llm`

## 1. Goal

Make the LLM backend configurable so Explorator can run against native Google
Gemini (today's behaviour) **or** any OpenAI-compatible endpoint — OpenAI,
vLLM, Ollama (`/v1`), LM Studio, OpenRouter — selected by configuration, with
no call-site changes and no regression of the Gemini path.

### Success criteria

- `LLM_PROVIDER=openai` + `LLM_BASE_URL` + two model names runs a full
  exploration round and a genre-research run against a local Ollama/vLLM model.
- `LLM_PROVIDER=gemini` (default) behaves exactly as today; an existing `.env`
  using `GEMINI_*` names keeps working unchanged.
- Local-model failures are visible (logged + counted), not silently masked.
- Token usage is attributed to the correct tier; cost shows "not priced" when
  no prices are configured.
- Full backend suite, frontend suite and e2e (mock) lane stay green.

### Decisions already made

- **Option A:** keep the native Gemini client; add one OpenAI-compatible client.
  (Rejected: B — route Gemini through its OpenAI-compat endpoint; C — per-tier
  provider mixing.)
- **One settings namespace (`LLM_*`)**, with legacy `GEMINI_*` names accepted as
  deprecated aliases.
- Hand-rolled JSON extraction (~30 lines) rather than adding `instructor`/`litellm`.

### Out of scope

- Per-tier provider mixing, UI provider/model picker, streaming.
- Renaming `gemini` → `llm` across the 35 `gemini=` kwargs, `FakeGeminiClient`,
  `GEMINI_MOCK`, `test_gemini.py`. Deferred to a follow-up mechanical PR (it
  touches `e2e/`). This PR keeps those names.

## 2. Architecture

```
api/deps.py ── get_llm_client() ──┬── GEMINI_MOCK=true → FakeGeminiClient
   (alias get_gemini_client)      ├── provider=gemini   → GeminiClient
                                  └── provider=openai   → OpenAICompatClient
                                            │
             both clients ──► adapters/_structured.py (extract_json, parse_structured,
                                                       truncate_to_max_length)
             both clients ──► adapters/usage.py (record_tokens(..., tier=))
```

### 2.1 `adapters/llm.py` (new)

- `ModelTier` (`PRO`, `FLASH`) moves here; `adapters/gemini.py` re-exports it so
  the ~80 existing imports keep working.
- `LLMClient(Protocol)` with exactly the two methods consumers use:
  - `generate_structured(prompt, response_model, tier=FLASH, system_prompt=None) -> T`
  - `generate_text(prompt, tier=FLASH, system_prompt=None) -> str`
- All type annotations in `engine/`, `domain/`, `api/routes/` change
  `GeminiClient` → `LLMClient`. Parameter names (`gemini=`) are unchanged.
- The `# type: ignore[return-value]` in `deps.py` for `FakeGeminiClient` goes away.

### 2.2 `adapters/_structured.py` (new, shared)

- `extract_json(text: str) -> str` — strips `<think>…</think>` blocks (and an
  unterminated leading `<think>`), unwraps a markdown fence anywhere in the
  text, then slices from the first `{`/`[` to the matching last `}`/`]`.
  Returns the input unchanged when no JSON delimiters are found (so
  `json.loads` raises a normal error).
- `truncate_to_max_length(data, model)` — moved verbatim from
  `GeminiClient._truncate_to_max_length` (typed `type[BaseModel]`, no
  `hasattr` duck-typing). Not generalised beyond today's one-level/list-of-`$ref`
  support (YAGNI — current models only need that).
- `parse_structured(raw_text, response_model, *, provider, model_name) -> T` —
  empty check → `extract_json` → `json.loads` → truncate → `model_validate`.
  Error messages and logs name the provider (no hardcoded "Gemini"). Catches
  `pydantic.ValidationError` (not bare `Exception`) for the log-and-reraise.

### 2.3 `GeminiClient` (modified, behaviour-preserving)

- `generate_structured` delegates post-processing to `parse_structured`.
- **Timeout fix:** pass `http_options=types.HttpOptions(timeout=timeout_seconds * 1000)`
  to `genai.Client`. Today the setting is stored but never applied
  (`gemini.py:39-40`). Landed as its own commit.
- Records usage with explicit `tier=`.
- Keeps `self._client.aio...` structure (tests patch it).

### 2.4 `adapters/openai_compat.py` (new)

`OpenAICompatClient(base_url, api_key, pro_model, flash_model, timeout_seconds,
max_retries, max_concurrency, http_client=None)`

- Uses `openai.AsyncOpenAI(base_url=..., api_key=api_key or "not-needed",
  timeout=..., max_retries=..., http_client=...)`.
- **Concurrency:** an `asyncio.Semaphore(max_concurrency)` wraps every request,
  so the unbounded `asyncio.gather` fan-outs in `plan_voicings`,
  `generate_melody` and `evaluate_progressions` don't overrun single-GPU
  servers (Ollama queues; queued requests would time out).
- **`generate_text`:** `chat.completions.create(messages=[system?, user])`,
  returns `message.content`. Any `reasoning_content` field is ignored. Empty
  content → `ValueError`.
- **`generate_structured` — schema mode ladder**, remembered per instance
  (`self._schema_mode`) so a rejected mode is paid for once, not every call:
  1. `json_schema`: `response_format={"type":"json_schema","json_schema":{"name": Model.__name__, "schema": Model.model_json_schema(), "strict": False}}`
  2. `json_object`: `response_format={"type":"json_object"}` + schema appended to the system prompt
  3. `prompt`: no `response_format`; schema + "respond with only JSON" in the system prompt
  - A `BadRequestError` or `UnprocessableEntityError` (400/422) on a mode
    downgrades to the next mode and retries immediately.
  - A **parse or validation failure** (server ignored the schema) triggers one
    retry at the same mode; a second failure raises.
- Usage: `response.usage.prompt_tokens`, `completion_tokens`,
  `prompt_tokens_details.cached_tokens` (all None-safe) → `usage.record_tokens(..., tier=tier.value)`.
- Context warning: when `LLM_CONTEXT_TOKENS` is set and a response reports
  `prompt_tokens >= 0.9 * LLM_CONTEXT_TOKENS`, log a warning (once per process)
  that the prompt is near/over the server context window and may be silently
  truncated; message points at the README context-length section. Unset → no
  check (servers don't expose their window over `/v1`, so we don't guess).

### 2.5 Factory — `api/deps.py`

```python
@lru_cache
def get_llm_client() -> LLMClient:
    if os.environ.get("GEMINI_MOCK", "").lower() == "true":
        return FakeGeminiClient()
    if settings.llm_provider == "openai":
        return OpenAICompatClient(...)
    return GeminiClient(...)

get_gemini_client = get_llm_client   # same object → cache_clear() + Depends identity preserved
```

Routes switch to `Depends(get_llm_client)`; tests that call
`get_gemini_client.cache_clear()` keep working via the alias.

## 3. Configuration (`config.py`)

One namespace. Legacy names accepted via `validation_alias=AliasChoices(...)`;
a startup log line warns when a legacy name was used.

| Setting | Legacy alias | Default | Notes |
|---|---|---|---|
| `LLM_PROVIDER` | — | `gemini` | `gemini` \| `openai`; unknown value → startup error |
| `LLM_API_KEY` | `GEMINI_API_KEY` | `""` | Optional for local servers |
| `LLM_BASE_URL` | — | `""` | openai only; empty = `api.openai.com` |
| `LLM_PRO_MODEL` | `GEMINI_PRO_MODEL` | gemini: `gemini-pro-latest`; openai: required | |
| `LLM_FLASH_MODEL` | `GEMINI_FLASH_MODEL` | gemini: `gemini-flash-latest`; openai: required | |
| `LLM_TIMEOUT_SECONDS` | `GEMINI_TIMEOUT_SECONDS` | gemini 120 / openai 300 | Local inference is slow |
| `LLM_MAX_RETRIES` | — | 1 | SDK transport retries (openai) |
| `LLM_MAX_CONCURRENCY` | — | gemini: unbounded / openai 4 | Semaphore in openai client |
| `LLM_CONTEXT_TOKENS` | — | unset | openai only; enables the near-context-limit warning |
| `LLM_PRICE_{PRO,FLASH}_{INPUT,OUTPUT}` | `GEMINI_PRICE_*` | gemini: today's estimates; openai: unset | Unset → "not priced" |

Provider-dependent defaults resolve in a `model_validator(mode="after")`.
**Fail fast** (raise at settings load, surfaced at startup) when
`LLM_PROVIDER=openai` and either model name is empty.

`.env.example` is rewritten with a Gemini block (default) and commented
Ollama / vLLM / OpenAI examples.

## 4. Usage & cost (`adapters/usage.py`, frontend)

- `record_tokens`, `record_synthetic_tokens`, `record`, `UsageAccumulator.add`
  gain keyword-only `tier: str | None = None`. When `None`, fall back to the
  existing `_tier_of(model_name)` heuristic — **zero churn** for the ~20 test
  call sites; `by_model` keys stay `"pro"`/`"flash"`.
- `GeminiClient`, `OpenAICompatClient`, `FakeGeminiClient` all pass `tier=`.
- `record(model, usage_metadata)` stays google-genai-specific (used only by
  `GeminiClient`); the openai client calls `record_tokens` directly.
- `_pricing()` reads the single `LLM_PRICE_*` set. When prices are unset,
  `to_dict()` emits `"is_priced": false` and `estimated_cost_usd: 0`.
- **Fallback counter:** new `usage.record_fallback(node: str)` increments
  `UsageAccumulator.fallbacks[node]`; emitted in `to_dict()` as
  `"fallbacks": {...}`. Called from the silent-fallback sites:
  `plan_voicings.py:157`, `generate_melody` strategy fallback, and
  `evaluate_progressions` exceptions from `gather(return_exceptions=True)`.
  Existing warning logs stay.
- Frontend `TokenUsagePanel.tsx`: when `is_priced === false`, show
  "not priced" instead of `~$0.0000 est.`; show a small "N fallbacks" note
  when `fallbacks` is non-empty. Type in the frontend usage model updated.
- Usage docstring: "Every Gemini call" → "Every LLM call".

## 5. Call-site fixes

- **Genre research** (`draft.py:94-102`, `critique.py`, `refine.py`): replace the
  inline fence-stripping with `extract_json(raw_text)` before `json.loads`.
- `generate_melody.py:221`: `source_strategy = f"{settings.llm_provider}_flash_{genre}"`
  — gemini output is byte-identical to today (`gemini_flash_<genre>`).

## 6. Dependencies

- Add `openai` (current 1.x/2.x major) to `backend/pyproject.toml`; update `uv.lock`.
- No new test dependency: tests use `httpx.MockTransport` (httpx already a dep).

## 7. Documentation

- `README.md`: provider-neutral wording where it describes runtime behaviour;
  new "LLM providers" section with Gemini / Ollama / vLLM / OpenAI recipes,
  and an **Ollama context length** note (`OLLAMA_CONTEXT_LENGTH` or a Modelfile
  `num_ctx`, since `/v1` can't set it per request) and concurrency note
  (`OLLAMA_NUM_PARALLEL` vs `LLM_MAX_CONCURRENCY`).
- New ADR `docs/decisions/012-configurable-llm-provider.md` (the decisions in §1).
- Addendum to ADR 011: tier is now explicit; `is_priced`; `fallbacks`.

## 8. Testing

Unit (backend, no network):

- `_structured`: `extract_json` — plain JSON, fenced, fenced mid-text, `<think>`
  prefix, unterminated `<think>`, preamble text, arrays, no-JSON passthrough.
  `truncate_to_max_length` — top-level, list-of-`$ref`, non-dict passthrough
  (currently untested). `parse_structured` — empty, malformed, validation error.
- `OpenAICompatClient` via `AsyncOpenAI(http_client=httpx.AsyncClient(transport=httpx.MockTransport(...)), max_retries=0)`:
  - json_schema request body shape + success
  - 400 → json_object; 422 → json_object; json_object 400 → prompt mode
  - downgrade is sticky across calls (second call sends json_object directly)
  - ignored schema (prose + fenced JSON) still parses; garbage twice → raises
  - `<think>` + JSON from a reasoning model parses
  - usage recorded under the passed tier with a non-"flash" model name
  - semaphore caps concurrency (max in-flight observed == `max_concurrency`)
  - api key defaults to `"not-needed"`; base_url honoured
  - context warning fires once at ≥90% of `LLM_CONTEXT_TOKENS`, never when unset
- `GeminiClient`: constructor passes `http_options.timeout`; existing tests green.
- `usage`: `tier=` overrides heuristic; `is_priced`; `fallbacks` in `to_dict`.
- `config`: provider defaults; legacy alias mapping; openai without models → error;
  unknown provider → error.
- Factory: mock / gemini / openai selection (with `cache_clear()`).
- Genre-research nodes: `<think>`-prefixed draft output parses.

Frontend: `TokenUsagePanel` renders "not priced" and fallbacks note.

Regression: full backend suite, frontend suite, e2e mock lane.

Manual smoke (if a local server is available): one exploration round + one
genre-research run with `LLM_PROVIDER=openai` against Ollama or vLLM; assert in
the usage event that `fallbacks` is empty (or report which nodes fell back) —
"it ran" is not sufficient.

## 9. Commit sequence (for the plan)

1. Gemini timeout fix (isolated behaviour change).
2. `_structured.py` extraction + tests; GeminiClient uses it.
3. `llm.py` Protocol + annotation sweep.
4. Usage: `tier=`, `is_priced`, `fallbacks` + call-site wiring.
5. Config unification + validation.
6. `OpenAICompatClient` + tests; `openai` dep.
7. Factory + route `Depends` swap.
8. Genre-research `extract_json`; `source_strategy`.
9. Frontend panel.
10. Docs: README, `.env.example`, ADR 012, ADR 011 addendum.
