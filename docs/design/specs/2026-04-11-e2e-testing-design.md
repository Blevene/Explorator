# E2E Testing with Playwright — Design Specification

**Version**: v1.1
**Date**: 2026-04-11
**Status**: Approved (v1.1 — gap analysis additions)

---

## 1. Overview

Add Playwright E2E tests that exercise the full stack (frontend → backend → Neo4j) with a mock Gemini adapter for speed and determinism. The mock replaces the real Gemini client when `GEMINI_MOCK=true`, returning valid structured responses instantly.

## 2. Infrastructure

### 2.1 Directory Structure

```
e2e/
  playwright.config.ts        # Playwright configuration
  global-setup.ts             # Start backend + frontend, health check
  global-teardown.ts          # Kill processes
  tests/
    happy-path.spec.ts        # Tests 1-3
    m3-features.spec.ts       # Tests 4-7
    error-edge.spec.ts        # Tests 8-10
    ux-coherence.spec.ts      # Tests 11-13
    pipeline.spec.ts          # Tests 14-16
    audio.spec.ts             # Test 17
  fixtures/
    test-fixtures.ts          # Page helpers, session creation, cleanup
```

### 2.2 FakeGeminiClient

**File:** `backend/src/explorator/adapters/gemini_mock.py`

A drop-in replacement for `GeminiClient` that returns pre-built valid Pydantic model instances based on `response_model` type. No network calls. Deterministic output.

**Type dispatch:** The mock inspects `response_model` (the Pydantic class passed to `generate_structured`) and returns the matching fixture. If `response_model` is unknown, raises `ValueError` — this ensures new LLM calls get explicit mock support rather than silently passing.

**Call counting:** The mock tracks call count per response_model type via a `call_counts: dict[str, int]` attribute. This enables tests to verify that caching works (e.g., second realization doesn't trigger new Gemini calls).

Supported response models:
- `CreativeBrief` — returns dream_pop, A major, 4 bars
- `HarmonyGeneratorResponse` (or whatever the batch generation model is) — returns 4 candidates with realistic chord_events
- `TheoryEvaluation` — returns scores in 6.0–8.5 range
- `VoicingStrategyResponse` — returns open voicing, mid_high register, 4 voices with per_chord instructions
- `FeedbackInterpretation` — returns weight deltas and "neutral" satisfaction
- `MutationResponse` — returns one substitute_chord mutation

### 2.3 Mock Activation

**File:** `backend/src/explorator/api/deps.py`

When `GEMINI_MOCK=true` env var is set, `get_gemini_client()` returns `FakeGeminiClient()` instead of `GeminiClient(api_key=...)`.

### 2.4 Test Lifecycle

**globalSetup:**
1. Start backend (`uvicorn` with `GEMINI_MOCK=true`) on port 8100
2. Start frontend (`vite --port 5199`) proxying API to port 8100
3. Health check: poll `GET http://localhost:8100/v1/sessions` every 500ms until 200 response, timeout after 30s
4. Health check: poll `GET http://localhost:5199` until 200, timeout after 15s

**Per-test isolation:**
- `beforeEach`: Create a fresh session via `POST /v1/sessions` with unique prompt. Store `session_id`.
- Tests operate only on their own session. No cross-test state leakage.
- No explicit cleanup needed — sessions accumulate but don't interfere since each test uses its own `session_id`.

**globalTeardown:** Kill backend + frontend processes by PID.

**Neo4j:** Assumed running on ports 7475/7688 (dev instance). For CI, a `docker-compose.test.yml` starts Neo4j before the test run.

### 2.5 Playwright Config

- Base URL: `http://localhost:5199`
- Browser: Chromium only (sufficient for E2E)
- Timeout: 30s per action (mock responses are instant, but SSE streams + LangGraph node execution takes a moment)
- Retries: 0 in local, 1 in CI
- Video: on-failure only
- Workers: 1 (serial execution — shared Neo4j instance)

### 2.6 CI Configuration

```yaml
# .github/workflows/e2e.yml (or equivalent)
services:
  neo4j:
    image: neo4j:5-community
    ports: ["7475:7474", "7688:7687"]
    env:
      NEO4J_AUTH: neo4j/explorator_dev

steps:
  - Install backend: cd backend && uv sync --all-extras
  - Install frontend: cd frontend && npm ci
  - Install Playwright: cd e2e && npx playwright install chromium
  - Run tests: cd e2e && npx playwright test
```

## 3. Test Suite (18 tests)

### 3.1 Happy Path

**Test 1: `dashboard-create-session`**
- Navigate to `/`
- Verify "Explorator" heading visible
- Type prompt in input
- Click "Explore"
- Verify redirect to `/session/:id`
- Verify session prompt visible in workspace header

**Test 2: `generation-flow`**
- Create session, navigate to workspace
- Type prompt, click "Generate"
- Wait for pipeline: verify at least one progress pill becomes active
- Wait for completion: verify candidate cards appear (count > 0)
- Verify each card has: chord symbols, score badge, key/mode badge

**Test 3: `realization-flow`**
- Generate candidates (reuse generation flow)
- Click "Realize" on first candidate
- Verify: arrangement list panel appears with at least one arrangement
- Verify: piano roll canvas element visible
- Verify: transport bar with play button visible
- Verify: score panel visible with weighted total

### 3.2 M3 Features

**Test 4: `feedback-submission`**
- Navigate to realization view (generate + realize)
- Select an arrangement in the list
- In feedback sidebar, type "more experimental, less predictable"
- Click "Send"
- Verify: interpretation bubble appears ("Understood: ...")
- Verify: weight bars section appears with 9 dimensions

**Test 5: `mutation-flow`**
- Generate candidates
- Click "Mutate" on a candidate card
- Verify: mutation modal appears with chord progression
- Type guidance, click "Mutate" button in modal
- Wait for SSE completion
- Reload candidates
- Verify: new candidate appears with "mutated" badge
- Verify: lineage tree section becomes visible

**Test 6: `finalist-panel`**
- Generate candidates, realize one
- Verify: "Finalists" section visible in arrangement list
- Verify: at least one role badge visible (Safest, Best Loop, or Most Experimental)

**Test 7: `realization-caching`**
- Generate, realize candidate A
- Verify arrangement list appears
- Click back to progressions
- Click realize on candidate A again
- Verify: arrangements appear immediately (no pipeline progress bar, no loading spinner > 1s)

### 3.3 Error & Edge Cases

**Test 8: `session-not-found`**
- Navigate to `/session/nonexistent_id`
- Verify: no crash (page renders)
- Verify: appropriate empty/error state

**Test 9: `empty-state`**
- Create session, navigate to workspace
- Without generating, verify: "No candidates yet" message visible
- Verify: no loading spinners, no error messages

**Test 10: `progressive-disclosure`**
- Create session, generate candidates
- Before any mutations: verify lineage tree NOT visible
- Before realization: verify feedback sidebar NOT visible in generation view
- In realization view with no arrangement selected: verify feedback input placeholder says "Select arrangement"

### 3.4 UX Coherence

**Test 11: `navigation-flow`**
- Dashboard → Create → Workspace → Generate → Realize → Back to progressions → Realize different candidate → Back to Dashboard
- At each step verify:
  - Back links work and navigate correctly
  - No orphaned loading spinners
  - No stale data from previous views (e.g., old candidate list)
  - URL reflects current view

**Test 12: `view-state-consistency`**
- Generate candidates
- Note candidate count shown in heading
- Count rendered candidate cards — must match heading count
- Realize a candidate, check arrangement weighted_total
- Go back to progressions — verify candidates still present (not cleared)
- Verify no loading spinner visible when data is already loaded

**Test 13: `interaction-affordances`**
- While generation is running: verify Generate button is disabled
- While generation is running: verify prompt input is disabled
- In realization with no arrangement selected: verify feedback input disabled
- After selecting an arrangement: verify feedback input enabled
- After generation completes: verify no phantom pipeline progress bar visible
- Click Generate when field is empty: verify button stays disabled (no error thrown)

### 3.5 Pipeline & SSE

**Test 14: `sse-stream-completion`**
- Generate candidates
- Monitor the SSE event stream: verify `round_completed` event is received (stream terminates cleanly)
- Verify: loading state clears after stream ends
- Verify: no error message displayed

**Test 15: `multi-round-generation`**
- Generate candidates (round 1)
- Note candidate count
- Submit feedback to adjust weights
- Generate again (round 2)
- Verify: new candidates appear (count increases or at least doesn't decrease)
- Verify: candidates from round 1 still present (list grows, not replaced)

**Test 16: `generation-mode-switching`**
- Create session
- Select "exploratory" mode
- Generate candidates
- Verify candidates appear
- Verify mode selection persists visually after generation

### 3.6 Audio

**Test 17: `audio-playback-controls`**
- Realize an arrangement
- Click play button — verify it visually changes to pause icon
- Click pause — verify it changes back to play icon
- Click stop — verify play button is in initial state
- Toggle voicing mute (V) — verify visual state change
- Toggle bass mute (B) — verify visual state change
- Adjust tempo slider — verify BPM display updates
- Adjust volume slider — verify dB display updates

Note: We cannot verify actual audio output in headless Playwright. We verify the UI state changes and that no JS errors are thrown.

### 3.7 Concurrent & Feedback Integration

**Test 18: `feedback-affects-next-round`**
- Generate candidates, realize, submit feedback ("prefer more loopable progressions")
- Go back to progressions
- Generate again (round 2)
- Verify: generation completes without error
- Verify: candidates appear (the feedback-adjusted weights were loaded by load_memory)

## 4. FakeGeminiClient Response Fixtures

All responses use deterministic data (no randomness) for reproducible tests.

### CreativeBrief
```python
{
    "genre": "dream_pop",
    "key_center": "A",
    "mode": "major",
    "phrase_length_bars": 4,
    "mood_targets": ["wistful", "ethereal"],
    "tempo_suggestion": 120,
}
```

### ProgressionCandidate (generated batch of 4)
Each with valid chord_events (4 bars), roman_numerals, scores in 6.0–8.5 range. Different chord progressions per candidate for diversity testing. Use only music21-safe chord symbols (e.g., Amaj7, F#m7, Dmaj7, E7 — no exotic types like 13sus4).

### TheoryEvaluation
Scores: genre_fit=7.5, emotional_fit=7.0, theoretical_coherence=8.0, cadence_quality=7.0, novelty=6.5, loopability=8.0

### VoicingStrategyResponse
```python
{
    "global_strategy": "Open voicings with 7th extensions for dream pop shimmer",
    "density_level": "medium",
    "voice_count": 4,
    "register_profile": "mid_high",
    "rationale": "Ethereal texture via spread voicings",
    "per_chord": [...]  # One ChordVoicingInstruction per chord with music21-safe symbols
}
```

### FeedbackInterpretation
```python
{
    "interpreted_adjustments": {"increase_novelty": True, "reduce_predictability": True},
    "weight_deltas": {"novelty": 0.03, "genre_fit": -0.02, "loopability": -0.01},
    "satisfaction": "neutral",
}
```

### MutationResponse
```python
{
    "mutated_chord_symbols": ["Amaj7", "F#m9", "Dmaj7", "Esus4"],
    "mutations": [{
        "operation": "substitute_chord",
        "position": 1,
        "original_value": "F#m7",
        "new_value": "F#m9",
        "description": "Added 9th for color",
        "reason": "Increases novelty",
        "predicted_score_changes": ["novelty: +0.5"],
    }],
}
```

## 5. Flakiness Mitigation

- **Serial execution** (1 worker) — avoids Neo4j race conditions between parallel tests
- **Per-test session isolation** — each test creates its own session, no shared state
- **Health check polling** in globalSetup — no race between server startup and first test
- **Deterministic mock** — no randomness, no network calls, same output every run
- **Generous action timeout** (30s) — SSE streams through LangGraph nodes take a few seconds even with mock Gemini
- **music21-safe fixtures** — all chord symbols in fixtures are known-valid to music21

## 6. Boundaries

- No visual regression testing (screenshots) — just functional assertions
- No performance benchmarking — just "doesn't time out"
- No multi-browser — Chromium only
- No mobile viewport tests
- No real Gemini smoke test (deferred — would need separate CI job with API key)
- Audio tests verify UI state only — cannot verify actual sound output in headless mode
- `npm run build` not required — tests run against Vite dev server
