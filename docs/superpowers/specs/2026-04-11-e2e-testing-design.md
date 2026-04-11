# E2E Testing with Playwright — Design Specification

**Version**: v1.0
**Date**: 2026-04-11
**Status**: Draft

---

## 1. Overview

Add Playwright E2E tests that exercise the full stack (frontend → backend → Neo4j) with a mock Gemini adapter for speed and determinism. The mock replaces the real Gemini client when `GEMINI_MOCK=true`, returning valid structured responses instantly.

## 2. Infrastructure

### 2.1 Directory Structure

```
e2e/
  playwright.config.ts        # Playwright configuration
  global-setup.ts             # Start backend + frontend
  global-teardown.ts          # Kill processes
  tests/
    happy-path.spec.ts        # Tests 1-3
    m3-features.spec.ts       # Tests 4-7
    error-edge.spec.ts        # Tests 8-10
    ux-coherence.spec.ts      # Tests 11-13
  fixtures/
    test-fixtures.ts          # Page helpers, session creation
```

### 2.2 FakeGeminiClient

**File:** `backend/src/explorator/adapters/gemini_mock.py`

A drop-in replacement for `GeminiClient` that returns pre-built valid Pydantic model instances based on `response_model` type. No network calls. Deterministic output.

Supported response models:
- `CreativeBrief` — returns dream_pop, A major, 4 bars
- `ProgressionCandidate` batch — returns 4 candidates with realistic chord_events
- `TheoryEvaluation` — returns scores in 6.0–8.5 range
- `VoicingStrategyResponse` — returns open voicing, mid_high register, 4 voices with per_chord instructions
- `FeedbackInterpretation` — returns weight deltas and "neutral" satisfaction
- `MutationResponse` — returns one substitute_chord mutation

### 2.3 Mock Activation

**File:** `backend/src/explorator/api/deps.py`

When `GEMINI_MOCK=true` env var is set, `get_gemini_client()` returns `FakeGeminiClient()` instead of `GeminiClient(api_key=...)`.

### 2.4 Test Lifecycle

- `globalSetup`: Start backend (`uvicorn` with `GEMINI_MOCK=true`) on port 8100, frontend (`vite`) on port 5199. Wait for both to be healthy.
- Each test: Creates a fresh session via API, operates on that session.
- `globalTeardown`: Kill backend + frontend processes.
- Neo4j: Assumed running (same dev instance on ports 7475/7688).

### 2.5 Playwright Config

- Base URL: `http://localhost:5199`
- Browser: Chromium only (sufficient for E2E)
- Timeout: 30s per action (mock responses are instant, but SSE streams take a moment)
- Retries: 0 in local, 1 in CI
- Video: on-failure only

## 3. Test Suite

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
- Click "Realize" on same candidate again (from back button + re-click)
- Verify: no loading spinner appears (instant cache hit)

### 3.2 M3 Features

**Test 4: `feedback-submission`**
- Navigate to realization view (generate + realize)
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
- Verify: arrangements appear immediately (no pipeline progress, no loading spinner > 1s)

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
- Before realization: verify feedback sidebar NOT visible (or shows placeholder)
- In realization view with no arrangement selected: verify feedback input disabled/placeholder says "Select arrangement"

### 3.4 UX Coherence

**Test 11: `navigation-flow`**
- Dashboard → Create → Workspace → Generate → Realize → Back to progressions → Realize different candidate → Back to Dashboard
- At each step verify:
  - Back links work and navigate correctly
  - No orphaned loading spinners
  - No stale data from previous views (e.g., old candidate list)

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
Each with valid chord_events (4 bars), roman_numerals, scores in 6.0–8.5 range. Different chord progressions per candidate for diversity testing.

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
    "per_chord": [...]  # One ChordVoicingInstruction per chord
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

## 5. Boundaries

- No visual regression testing (screenshots) — just functional assertions
- No performance benchmarking — just "doesn't time out"
- No multi-browser — Chromium only
- No mobile viewport tests
- Neo4j must be running (not started by tests)
- `npm run build` not required — tests run against Vite dev server
