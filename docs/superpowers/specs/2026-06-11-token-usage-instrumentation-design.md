# Token Usage Instrumentation — Design

**Date:** 2026-06-11
**Status:** Approved (design); pending implementation plan

## Problem

Explorator makes many Gemini calls per generation round (parse_intent, generate,
evaluate_progressions, plan_voicings, generate_melody, mutate, plus genre
research and feedback), but the response's `usage_metadata` is discarded. There
is no measurement of token consumption and nothing surfaced to users. Users
cannot see what a round costs, understand where tokens go, or track spend over a
session.

## Goals

1. **Per-round cost awareness** — show input/output/total tokens and an estimated
   USD cost for each generation round.
2. **Understand the distribution** — break usage down by phase/step so users see
   which steps (generate vs evaluate vs mutate vs melody) are expensive.
3. **Session-cumulative total** — a running total across rounds within a session.
4. **Live during a round** — counts tick up per phase as the round progresses.

### Non-goals (explicit)

- Persisting token usage to Neo4j for long-term history/trends. Cumulative is
  **frontend-only, per-session** (resets on reload / new session).
- App-level all-time rollups or cross-session dashboards.
- A dedicated per-phase UI for the genre-research flow (it surfaces a total only
  in v1; its results live in a different view).

## Approach

Every Gemini call funnels through two methods in `adapters/gemini.py`
(`generate_structured`, `generate_text`), both calling
`self._client.aio.models.generate_content(...)`. Rather than thread token counts
back through ~8 LangGraph node call sites and domain services (invasive,
return-type churn), use a **`contextvars`-scoped accumulator**:

- The adapter records each call's usage into "the current accumulator".
- The round handler opens an accumulator scope around `graph.ainvoke(...)`.
- A central node wrapper in `graph.py` tags the active phase and emits live
  updates — no per-node edits.

contextvars copy **by reference** into asyncio child tasks, so the
`asyncio.gather` fan-out in `evaluate_progressions` aggregates correctly into the
single accumulator. Net backend churn: one new module, one line × 2 in the
adapter, a wrapper applied at node registration, and a scope wrap in the route.

## Components

### A. Measurement core — `adapters/usage.py` (new)

- **`RoundUsage`** accumulator holding two breakdowns:
  - `by_model`: `{"pro"|"flash"} → {input, output, cached, calls}`
  - `by_phase`: `{phase_name} → {input, output, calls, model}`
  - `totals()` → `{total_input, total_output, total_cached, total_tokens}`
  - `estimated_cost_usd(pricing)` derived from `by_model`.
  - `to_event(round_number)` → the SSE payload dict (see SSE contract).
- **`_current: ContextVar[RoundUsage | None]`** (default `None`).
- **`_current_phase: ContextVar[str]`** (default `"unknown"`).
- **`record(model_name, usage_metadata)`** — resolves the model to a "pro"/"flash"
  tier label, reads `prompt_token_count` / `candidates_token_count` /
  `cached_content_token_count` (guarding `None`), and adds to the active
  accumulator under `_current_phase`. **No-op when there is no active scope**, so
  calls outside a round (or in mock mode without a scope) are safe.
- **`track_usage()`** — context manager (sync `contextmanager`) that `set()`s a
  fresh `RoundUsage` on `_current`, yields it, and resets the token on exit.
- **`set_phase(name)`** — small context manager used by the graph wrapper to set
  and reset `_current_phase`.

Model→tier resolution: substring match on `"flash"` → flash, else pro (the
configured model names are `gemini-pro-latest` / `gemini-flash-latest`). Keyed by
tier label so the breakdown is stable regardless of alias.

### B. Capture + attribution + live emit

- **`adapters/gemini.py`** — after each `generate_content` call in both
  `generate_structured` and `generate_text`:
  ```python
  usage.record(model_name, response.usage_metadata)
  ```
  This single hook covers every call site (generate, evaluate, plan_voicings,
  melody, mutate, parse_intent, feedback, genre research).

- **`engine/graph.py`** — an `instrument(name, fn)` wrapper applied at each
  `graph.add_node(name, fn)` registration:
  ```python
  def instrument(name, fn):
      async def wrapped(state):
          with set_phase(name):
              result = await fn(state)
          # emit live token_usage if cumulative changed since last emit
          await _maybe_emit_usage(state)
          return result
      return wrapped
  ```
  - Sets `_current_phase` for the node's duration → per-phase attribution.
  - After the node runs, emits a live `token_usage` event via
    `state["on_progress"]`, **only when the cumulative total changed** since the
    last emit (so deterministic nodes don't spam duplicates). Change-tracking
    uses a small per-round marker (e.g. last-emitted total stored on the
    accumulator).
  - Applied uniformly in both `build_exploration_graph` and
    `build_realization_subgraph`.

### C. SSE contract — new `token_usage` event

```json
{
  "round": 1,
  "total_input": 8421,
  "total_output": 3120,
  "total_cached": 0,
  "total_tokens": 11541,
  "by_model": {
    "pro":   { "input": 6000, "output": 2400, "cached": 0, "calls": 2 },
    "flash": { "input": 2421, "output": 720,  "cached": 0, "calls": 4 }
  },
  "by_phase": {
    "generate":               { "input": 6000, "output": 2400, "calls": 1, "model": "pro" },
    "evaluate_progressions":  { "input": 1800, "output": 480,  "calls": 3, "model": "flash" }
  },
  "estimated_cost_usd": 0.0142,
  "is_estimate": true
}
```

The route wraps `graph.ainvoke` in `with track_usage()` and additionally sends a
final `token_usage` on completion (covers the last node and guarantees a terminal
value even if no live event fired). The same `track_usage()` wrap is added to the
genre-research route to emit its total.

### D. Frontend

- **`services/sse.ts`** — add `token_usage` to the event-type union.
- **`hooks/useGenerationFlow.ts`** — on `token_usage`: set `tokenUsage` (latest
  round snapshot) and append/replace into a per-session `roundUsages` array in the
  candidate store. Expose `tokenUsage` from the hook.
- **`stores/candidateStore.ts`** — hold `roundUsages` for the session (cleared on
  session change), and a derived session cumulative.
- **`TokenUsagePanel`** (new component) rendered in `SessionWorkspace` near the
  progress indicator:
  - **Headline:** total tokens for the current/last round + `~$0.014 est.`
  - **Live:** ticks up per phase as events arrive during a round.
  - **Expandable:** by-phase breakdown (which step cost what) and by-model split.
  - **Session footer:** cumulative tokens + estimated cost across all rounds this
    session (frontend sum of `roundUsages`).
  - Degrades cleanly to zeros / hidden detail when no usage is present.

### E. Config, mock, pricing

- **`config.py`** — pricing settings (USD per 1M tokens), with documented
  defaults, feeding a pricing map:
  - `gemini_price_pro_input`, `gemini_price_pro_output`
  - `gemini_price_flash_input`, `gemini_price_flash_output`
  - Cached tokens priced at the input rate by default (slight overestimate;
    acceptable for an estimate).
  Cost is always rendered with a clear "~ estimate" label, since the models are
  `*-latest` aliases and exact pricing is not guaranteed.
- **Mock client (`adapters/gemini_mock.py`)** — record small synthetic usage via
  the same `usage.record(...)` path so mock mode and e2e exercise the panel
  instead of always showing zeros.

## Data flow

```
POST /sessions/{id}/rounds
  └─ run_and_close():
       with track_usage() as usage:           # opens accumulator scope
         await graph.ainvoke(state)            # nodes run under the scope
           └─ instrument(name, fn):
                set_phase(name)                # attribution
                fn(state) → gemini.*           # adapter calls usage.record(...)
                _maybe_emit_usage(state)       # live token_usage SSE (on change)
       channel.send("token_usage", usage.to_event(round))   # terminal value
```

## Error handling & edge cases

- `usage_metadata` or any sub-count being `None` → treated as 0; never raises.
- `record()` outside a scope → no-op (covers non-round LLM calls and any stray
  call paths).
- Mock mode → synthetic usage, panel still populated.
- Neo4j off → unaffected (no persistence dependency).
- Client disconnect mid-round → existing cancel path applies; a partial
  `token_usage` may have been emitted live, which is fine (it reflects real
  partial spend).
- Concurrent rounds (different requests) → separate `track_usage()` scopes via
  contextvars; no cross-contamination.

## Testing

**Backend**
- `RoundUsage` aggregation across multiple `record()` calls (by_model + by_phase).
- `estimated_cost_usd` math against known token counts + rates.
- `record()` is a no-op with no active scope.
- contextvar isolation: two concurrent `track_usage()` scopes accumulate
  independently; a `gather` fan-out attributes to one accumulator.
- A mock-Gemini round emits a `token_usage` event with non-zero counts and a
  populated `by_phase`.

**Frontend**
- `useGenerationFlow` stores token usage on a `token_usage` event.
- `TokenUsagePanel` renders round totals, by-phase breakdown, and session
  cumulative.

**Manual**
- Run a real round; confirm the panel shows plausible counts, the by-phase split
  matches which nodes called which model tier, and the session total accumulates
  across rounds.

## Files touched

- New: `backend/src/explorator/adapters/usage.py`
- Edit: `backend/src/explorator/adapters/gemini.py` (2 lines)
- Edit: `backend/src/explorator/adapters/gemini_mock.py` (synthetic record)
- Edit: `backend/src/explorator/engine/graph.py` (instrument wrapper)
- Edit: `backend/src/explorator/api/routes/rounds.py` (track_usage + terminal event)
- Edit: genre-research route (track_usage + terminal event)
- Edit: `backend/src/explorator/config.py` (pricing settings)
- New: `frontend/src/components/TokenUsagePanel.tsx`
- Edit: `frontend/src/services/sse.ts` (event union)
- Edit: `frontend/src/hooks/useGenerationFlow.ts` (handle event)
- Edit: `frontend/src/stores/candidateStore.ts` (roundUsages + cumulative)
- Edit: `frontend/src/views/SessionWorkspace.tsx` (render panel)
- Tests: backend unit tests for usage; frontend tests for hook + panel.
