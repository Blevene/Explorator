# Token Usage Instrumentation

Goal: measure how many tokens each generation round consumes and surface it in the UI so users can see and understand token usage (and an estimated cost).

## Design: single choke point + context-scoped accumulator

Every Gemini call funnels through two methods in `adapters/gemini.py`
(`generate_structured`, `generate_text`), both calling
`self._client.aio.models.generate_content(...)`. The response carries
`response.usage_metadata` (prompt_token_count / candidates_token_count /
cached_content_token_count) which is currently discarded.

Rather than thread token counts through 8 node call sites + domain services
(invasive, return-type churn), use a **`contextvars`-scoped accumulator**:
- The adapter records usage into "the current accumulator" after each call.
- The round handler opens an accumulator scope around `graph.ainvoke(...)`.
- contextvars propagate into asyncio child tasks (incl. `asyncio.gather` in
  `evaluate_progressions`), and the copied ContextVar references the *same*
  mutable accumulator object — so parallel calls aggregate correctly.
- Zero changes to nodes / domain services. Two one-line hooks total.

## Backend

- [ ] **New `adapters/usage.py`**
  - `RoundUsage` accumulator: per-model `{prompt, completion, cached, calls}`,
    plus `totals()` and `estimated_cost_usd()`.
  - `ContextVar[RoundUsage | None] _current`.
  - `record(model_name, usage_metadata)` — no-op if no active scope (so calls
    outside a round, or mock mode, are safe).
  - `track_usage()` contextmanager → sets a fresh `RoundUsage`, yields it.
  - Pricing map (USD per 1M tokens) keyed by "pro"/"flash" with documented
    default rates; cost is clearly labeled an **estimate** and rates are
    overridable via config. Model aliases make exact pricing uncertain, so
    tokens are the primary metric, cost secondary.
- [ ] **`adapters/gemini.py`**: after each `generate_content`, call
  `usage.record(model_name, response.usage_metadata)`. One line in each method.
- [ ] **`config.py`**: optional `gemini_price_pro_*` / `gemini_price_flash_*`
  settings feeding the pricing map (sane defaults).
- [ ] **`api/routes/rounds.py`**: wrap `graph.ainvoke` in `with track_usage()
  as usage:` inside `run_and_close`; after it completes emit a new
  `token_usage` SSE event with `{by_model, total_input, total_output,
  total_tokens, estimated_cost_usd}`.
- [ ] **Genre research route** (same one-liner wrap) so that flow reports too.
- [ ] **Mock client**: record a small synthetic usage so mock/e2e exercises the
  UI path instead of always showing 0.

## Frontend

- [ ] `services/sse.ts`: add `token_usage` to the event-type union.
- [ ] `hooks/useGenerationFlow.ts`: handle `token_usage` → store per-round
  totals; expose `tokenUsage` from the hook.
- [ ] Small **`TokenUsagePanel`/badge** component: shows input/output/total
  tokens + estimated cost for the latest round, with a per-model breakdown on
  hover/expand. Rendered in `SessionWorkspace` near the prompt/progress area.
- [ ] Session-cumulative running total (sum rounds in the store) so users see
  total spend for the session, not just the last round.

## Verification

- [ ] Backend unit test: `RoundUsage` aggregation + cost math; `record()` no-op
  outside scope; contextvar isolation across concurrent scopes.
- [ ] Backend test: a round (mock Gemini) emits a `token_usage` event with
  non-zero counts.
- [ ] Frontend test: hook stores token usage on event; panel renders totals.
- [ ] Manual: run a real round, confirm the panel shows plausible token counts
  and the breakdown matches per-model calls.

## Out of scope (note as follow-ons)
- Persisting per-round usage to Neo4j for long-term history/trends.
- Org-wide / cross-session dashboards.

## Review
(to be filled in after implementation)
