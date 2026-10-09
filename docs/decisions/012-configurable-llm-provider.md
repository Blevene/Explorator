# ADR 012 — Configurable LLM provider: native Gemini or any OpenAI-compatible endpoint

**Status:** Accepted

## Context

Explorator had a single hard-wired LLM adapter (`GeminiClient`, `google-genai`).
Operators want to run local models (vLLM, Ollama, LM Studio) and other hosted
APIs (OpenAI, OpenRouter) without forking the adapter layer. Callers already
depend on a narrow surface (`generate_text`, `generate_structured`), so the
question was where to put the seam and how to configure it.

## Decision

**Keep the native Gemini adapter, add a second adapter for the OpenAI chat
completions protocol, and select between them with `LLM_PROVIDER`.**

- An `LLMClient` Protocol describes the surface callers use; `GeminiClient` and
  the new `OpenAICompatClient` both satisfy it. `LLM_PROVIDER` (`gemini` default,
  or `openai`) picks one at startup; unknown values fail at startup.
- One `LLM_*` settings namespace (`LLM_API_KEY`, `LLM_BASE_URL`, `LLM_PRO_MODEL`,
  `LLM_FLASH_MODEL`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES`,
  `LLM_MAX_CONCURRENCY`, `LLM_CONTEXT_TOKENS`, `LLM_PRICE_*`). Provider defaults
  resolve in `config.py`: Gemini gets `gemini-*-latest` models, Gemini prices and a
  120 s timeout; `openai` gets a 300 s timeout and concurrency 4, and **requires**
  `LLM_PRO_MODEL` and `LLM_FLASH_MODEL` (startup fails otherwise).
- Legacy `GEMINI_*` names remain as deprecated aliases (logged at startup) but are
  honoured **only** when `LLM_PROVIDER=gemini`. Under `openai` they are ignored
  entirely, so a Google API key is never sent as a bearer token to a third-party
  endpoint and Gemini prices never apply to local models. An explicit
  `LLM_PRICE_*=0` beats a legacy `GEMINI_PRICE_*` value.
- Structured output uses a mode ladder: `json_schema`, then JSON mode, then
  schema-in-prompt. A fallback mode becomes **sticky for the process only after a
  request in that mode succeeds**, so one transient failure cannot permanently
  downgrade the client. Shared parsing/repair (including stripping `<think>`
  blocks) lives in `adapters/_structured.py`.
- When a call still yields no valid JSON, the node falls back to defaults and a
  fallback counter is surfaced in usage events; the token panel shows an
  "N fallback(s)" badge. Providers without configured prices report
  `is_priced=false` and the UI shows "not priced" (see ADR 011 addendum).
- The `openai` SDK (3.x) was added as a dependency; it brings its own HTTP stack
  (httpx2).

## Rejected alternatives

- **Route Gemini through its own OpenAI-compatible endpoint** — one adapter, but
  loses native `response_schema` behaviour and the usage fields differ.
- **Per-tier provider mixing** (e.g. pro on Gemini, flash on Ollama) — YAGNI; one
  provider per process keeps config and pricing simple.
- **LiteLLM / instructor** — dependency weight is not justified against a few
  hundred lines of adapter plus the shared structured-output helper.

## Consequences

**Positive:**
- Local and alternative hosted models work with only env changes.
- Gemini models, prices and other defaults are unchanged for existing deployments.
- Secrets and prices cannot leak across providers via the legacy aliases.

**Negative:**
- The Gemini timeout (`LLM_TIMEOUT_SECONDS`, default 120 s, formerly
  `GEMINI_TIMEOUT_SECONDS`) is now actually enforced; before this change it was
  silently ignored. google-genai applies it as both a client timeout and the server
  deadline (`X-Server-Timeout`), so slow requests fail with 504 DEADLINE_EXCEEDED
  after that time. Raise `LLM_TIMEOUT_SECONDS` if needed.
- `gemini=` kwarg names, `FakeGeminiClient` and `GEMINI_MOCK` are intentionally
  unchanged pending a mechanical rename PR, so naming is temporarily misleading.
- Ollama's context window is an operator concern: its default (2-4k tokens)
  silently truncates long prompts and the `/v1` API cannot change it per request.
  Documented in the README; `LLM_CONTEXT_TOKENS` enables a near-limit warning.
- Small local models may not produce valid JSON; rounds degrade to default
  strategies (visible via the fallback badge) rather than failing.

## Revisit if

- A genuine need for per-tier provider mixing appears.
- A third protocol (e.g. native Anthropic) is wanted, which would justify a
  registry rather than an `if` on `LLM_PROVIDER`.

## See also

- [`docs/superpowers/specs/2026-10-08-openai-compatible-llm-provider-design.md`](../superpowers/specs/2026-10-08-openai-compatible-llm-provider-design.md) — design spec
- ADR 011 (token usage instrumentation) — addendum covers tier, `is_priced` and fallbacks
- `backend/src/explorator/config.py` — settings resolution
