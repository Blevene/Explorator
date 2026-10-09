# ADR 011 — Token usage instrumented via a context-scoped accumulator

**Status:** Accepted

## Context

Every generation round fans out ~20 Gemini calls across many nodes and domain
services (`parse_intent`, `generate`, `evaluate_progressions` ×N, `plan_voicings`,
`generate_melody`, `mutate`, plus genre research and feedback). The `google-genai`
response carries `usage_metadata` (prompt / candidate / cached token counts), but
we discarded it. The result: no measurement of what a round consumes, and nothing
surfaced to the operator — who is paying the Gemini bill and had no sense of cost.

We wanted per-round, per-phase, and per-session visibility, live during a round,
without rewriting every call site. Three shapes considered:

1. **Thread token counts through return types** — every domain method returns
   `(result, usage)`. Pro: explicit. Con: invasive churn across ~8 call sites and
   the domain layer, and it leaks an infrastructure concern (token accounting)
   into pure music-theory code.
2. **Accumulate on the Gemini client singleton** — the client is an `lru_cache`
   singleton, so its counters would mix concurrent rounds/sessions. Per-round
   reporting becomes impossible without locking and request correlation.
3. **A `contextvars`-scoped accumulator** — the adapter records into "the current
   scope"; the round handler opens a scope around `graph.ainvoke`. contextvars
   copy *by reference* into asyncio child tasks, so even the parallel
   `asyncio.gather` fan-out in `evaluate_progressions` aggregates into the one
   accumulator. Per-round isolation is automatic; call sites are untouched.

## Decision

**Capture at the single adapter choke point into a `contextvars`-scoped
accumulator; attribute by phase with a graph node wrapper; surface live over SSE.**

- `adapters/usage.py` holds a `UsageAccumulator` (by-model and by-phase breakdowns
  + estimated cost) behind a `ContextVar`. `track_usage()` opens a scope;
  `record()` is a no-op when no scope is active.
- `adapters/gemini.py` records `usage_metadata` after each `generate_content`
  (two lines). No domain or node code changes.
- `engine/graph.py` wraps every node with `_instrument(name, fn)`, which tags the
  active phase (`set_phase`) and emits a live `token_usage` SSE event when the
  round's cumulative tokens grow — gated so deterministic nodes don't spam.
- `api/routes/rounds.py` opens the scope around `graph.ainvoke` and emits a
  **terminal** `token_usage` in an inner `finally` — so spend is reported even
  when a round fails (the tokens were billed regardless). A round that records
  zero usage logs a warning (fail-loud, not silent-zero).
- The frontend stores live + committed usage and renders a `TokenUsagePanel`
  (round headline, per-phase breakdown, session footer). Cost is computed from
  configurable per-tier rates (`gemini_price_*` settings) and always labeled an
  estimate. Mock-mode usage is flagged `is_synthetic` and badged in the UI.

**Scope is session-only, frontend-side.** The per-session running total lives in
the browser store and resets on page reload. We deliberately did **not** persist
per-round usage to Neo4j. Cumulative-across-time spend is a separate, larger
feature (a repo + aggregation + degradation handling) and was not needed for the
first cut, whose goal is "let the operator see what a round costs."

## Consequences

**Positive:**
- Near-zero invasiveness — two lines in the adapter, a wrapper in the graph, a
  scope in the route. The domain layer stays pure (consistent with ADR 002).
- Async-safe per-round isolation for free: the contextvar copies its *reference*
  into gather children, so concurrent evaluation calls aggregate correctly, and
  separate requests get separate accumulators.
- Per-phase attribution makes cost *legible* — see ARCHITECTURE.md for a measured
  round where `plan_voicings` is ~64% of spend, an actionable optimization target.
- Spend is counted even on failed/partial rounds, and a zero-usage round warns
  rather than silently reporting "0 tokens".

**Negative:**
- "Magic at a distance" — a node author doesn't see that their calls are being
  attributed to a phase a wrapper set. Correctness depends on asyncio context
  semantics: a future refactor that spawns work via `create_task` *outside* the
  phase window would mis-attribute silently. Not enforced by types; guarded only
  by tests (concurrency + revisit cases in `tests/unit/adapters/test_usage.py`).
- `record()` is a silent no-op outside a scope. Convenient, but if instrumentation
  regresses (a route stops opening the scope) usage drops to zero — mitigated by
  the route's warn-on-zero, not eliminated.
- Cost is an **estimate**: flat per-tier rates, no modeling of Gemini's tiered
  long-context pricing; cached tokens are treated as part of input (a subset of
  `prompt_token_count`, not priced separately). Surfaced as "~est." accordingly.
- `by_phase.model` is last-writer-wins — fine while each node uses a single tier
  (true today), wrong if a node ever mixes tiers.
- No cross-session / all-time aggregate. "This session" is per-page-load.

## Revisit if

- We need durable, cross-session, or per-user spend trends → persist per-round
  usage to Neo4j (a `TokenUsage` node off `Round`/`Session`) with the usual
  memory-mode degradation, and add an all-time rollup.
- We need accurate billing rather than an estimate → model tiered/long-context
  pricing, a cached-token discount rate, and reconcile against the provider's
  reported usage.
- A node starts mixing model tiers → make `by_phase` track a set of models.

## See also

- [`docs/ARCHITECTURE.md#token-usage-instrumentation`](../ARCHITECTURE.md#token-usage-instrumentation)
- `backend/src/explorator/adapters/usage.py` — the accumulator + scope
- [`docs/design/specs/2026-06-11-token-usage-instrumentation-design.md`](../design/specs/2026-06-11-token-usage-instrumentation-design.md) — design spec
- ADR 002 (LangGraph orchestration; pure domain) — why instrumentation lives in the glue layer, not the domain

## Addendum (2026-10-08, ADR 012)

- Adapters now pass the tier explicitly (`record_tokens(..., tier=)`); the
  model-name heuristic remains only as a fallback for callers that don't.
- Usage events carry `is_priced` (false when no `LLM_PRICE_*` is configured —
  the UI shows "not priced") and `fallbacks` (per-node count of LLM calls that
  failed and were replaced by defaults).
- Pricing settings are now `LLM_PRICE_*`; `GEMINI_PRICE_*` remain as deprecated
  aliases, honoured only when `LLM_PROVIDER=gemini`. An explicit `LLM_PRICE_*=0`
  beats a legacy `GEMINI_PRICE_*` value.
