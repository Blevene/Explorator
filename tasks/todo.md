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

Implemented on branch `feat/token-usage-instrumentation` via subagent-driven TDD
(11 tasks, each implemented + spec-reviewed + quality-reviewed). Commits
`ce847c0`..`e11a9b2`.

**What shipped**
- `adapters/usage.py`: `contextvars`-scoped `RoundUsage` accumulator (by-model +
  by-phase), `track_usage()`/`set_phase()`/`record()`/`record_tokens()`,
  estimated-cost from configurable pricing. No-op outside a scope.
- `adapters/gemini.py`: records `usage_metadata` after each `generate_content`
  (2 lines). `gemini_mock.py`: synthetic usage so mock/e2e exercise the UI.
- `engine/graph.py`: `_instrument(name, fn)` wraps every node → per-phase
  attribution + live `token_usage` SSE emit (gated on cumulative growth).
- `api/routes/rounds.py` + `genre_research.py`: open the scope around
  `graph.ainvoke`, emit a terminal `token_usage`.
- Frontend: `token_usage` SSE type + `TokenUsage` interface; candidate store
  `live`/`usages` + `sessionTokenTotals`; `useGenerationFlow` consumes events;
  `TokenUsagePanel` (round headline + per-phase breakdown + session footer)
  rendered in `SessionWorkspace`.

**Verification**
- Backend: 697 passed / 5 skipped; ruff clean on all changed files.
- Frontend: `tsc --noEmit` exit 0; 133 tests passed.
- End-to-end (mock mode, memory): a real-graph round emitted 5 live
  `token_usage` events ticking 1,000 → 10,000 tokens; final split flash 9 calls
  / pro 1 call; by-phase parse_intent/generate(pro)/evaluate_progressions/
  plan_voicings; cost ~$0.0097, `is_estimate: true`.
- Browser smoke: panel renders the headline, the expandable per-phase breakdown,
  and the session footer (screenshot `frontend/token-usage-panel.png`).

**Deviations from plan (all minor, reviewed)**
- `_last_emitted_total` marked `field(init=False)` (hygiene, from quality review).
- Task 9 test used `getAllByText` for two assertions because, with a single
  round, the round headline total equals the session footer total (expected).
- `ruff format` reformatted two `add_conditional_edges` blocks in `graph.py`
  cosmetically (leaves the file formatter-clean).

**Follow-ons (out of scope, as designed):** persist per-round usage to Neo4j for
long-term trends; per-phase UI for the genre-research flow (it emits a total).

## Review pass 2 — critique findings addressed

A self-critique surfaced further findings; all addressed (commits
`9fb329a`..`3ea5132`):

- **Cross-session leak** — store usage now cleared on session switch
  (`clearUsage` wired into `SessionWorkspace`'s id-keyed loader).
- **Failed-round spend was dropped** — tokens are billed even on failure, so the
  round route now emits the terminal `token_usage` in an inner `finally`
  (best-effort, doesn't mask the error / swallow cancellation), and the frontend
  commits live usage in its `finally`. Failed/partial rounds now count.
- **Cached double-count** — `cached_content_token_count` ⊆ `prompt_token_count`,
  so it's no longer added to `total` or priced separately (was inflating both).
- **Silent-zero** — a real round that records zero usage now logs a warning
  (instrumentation-broke signal), instead of failing silently to "0 tokens".
- **Mock numbers looked real** — mock usage is flagged `is_synthetic`; the panel
  shows a "synthetic" badge in mock mode.
- **Genre-research dead event** — replaced the unconsumed `token_usage` channel
  emit with a server-side spend log (measured, not dead-on-wire).
- **Misnomer** — `RoundUsage` → `UsageAccumulator` (accumulates a whole generate
  scope, not one round).
- **UX** — live "· updating…" affordance while a round is in flight; session
  footer relabeled "This session (since load)" with a "resets on reload / not
  persisted" tooltip.
- New regression tests: concurrent-gather attribution, mutation-loop revisit,
  synthetic-in-event, failed-round-emits-token_usage (backend), failed-round
  -commits-spend + clearUsage (frontend).

**Deliberate, documented limitations (not bugs):**
- **No cross-session/all-time aggregate.** "This session" is per-page-load and
  not persisted — a deliberate scope choice. Truly answering "how much to run
  Explorator over time" needs Neo4j persistence (offered as a follow-on).
- **`by_phase.model` is last-writer-wins** — fine while every node is single-tier
  (true today); would need a per-phase model set if a node ever mixes tiers.
- **Flat per-tier pricing** — no modeling of Gemini's tiered long-context rates;
  cost is surfaced as a labeled estimate.
