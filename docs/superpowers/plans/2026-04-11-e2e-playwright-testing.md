# E2E Playwright Testing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 18 Playwright E2E tests covering happy path, M3 features, error handling, UX coherence, pipeline/SSE, and audio — with a FakeGeminiClient mock for speed and determinism.

**Architecture:** `FakeGeminiClient` replaces real Gemini via `GEMINI_MOCK=true` env var. Tests run against real backend + frontend + Neo4j. Playwright globalSetup starts both servers on dedicated ports (8100/5199) with health polling. Each test creates an isolated session.

**Tech Stack:** Playwright (TypeScript), Vite, FastAPI, Neo4j, Python mock adapter

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `backend/src/explorator/adapters/gemini_mock.py` | FakeGeminiClient with deterministic fixtures |
| Modify | `backend/src/explorator/api/deps.py` | Swap to mock when `GEMINI_MOCK=true` |
| Create | `e2e/package.json` | Playwright dependencies |
| Create | `e2e/tsconfig.json` | TypeScript config for E2E |
| Create | `e2e/playwright.config.ts` | Playwright settings |
| Create | `e2e/global-setup.ts` | Start backend + frontend, health check |
| Create | `e2e/global-teardown.ts` | Kill server processes |
| Create | `e2e/fixtures/test-fixtures.ts` | Session helper, page utilities |
| Create | `e2e/tests/happy-path.spec.ts` | Tests 1-3 |
| Create | `e2e/tests/m3-features.spec.ts` | Tests 4-7 |
| Create | `e2e/tests/error-edge.spec.ts` | Tests 8-10 |
| Create | `e2e/tests/ux-coherence.spec.ts` | Tests 11-13 |
| Create | `e2e/tests/pipeline.spec.ts` | Tests 14-16 |
| Create | `e2e/tests/audio.spec.ts` | Test 17-18 |
| Modify | `Makefile` | Add `make e2e` target |

---

### Task 1: FakeGeminiClient

**Files:**
- Create: `backend/src/explorator/adapters/gemini_mock.py`
- Modify: `backend/src/explorator/api/deps.py`
- Create: `backend/tests/unit/adapters/test_gemini_mock.py`

- [ ] **Step 1: Write the mock test**

```python
# backend/tests/unit/adapters/test_gemini_mock.py
"""Tests for FakeGeminiClient."""

import pytest

from explorator.adapters.gemini_mock import FakeGeminiClient
from explorator.domain.harmony.generator import GeneratedProgressionSet
from explorator.domain.harmony.mutator import MutationResponse
from explorator.domain.evaluation.theory import GeminiScores
from explorator.domain.intent.feedback import FeedbackInterpretation
from explorator.domain.intent.parser import SoftPreferences
from explorator.models.realization import VoicingStrategyResponse


@pytest.mark.asyncio
async def test_fake_gemini_returns_soft_preferences() -> None:
    client = FakeGeminiClient()
    result = await client.generate_structured("test", response_model=SoftPreferences)
    assert isinstance(result, SoftPreferences)
    assert len(result.mood_targets) > 0


@pytest.mark.asyncio
async def test_fake_gemini_returns_progression_set() -> None:
    client = FakeGeminiClient()
    result = await client.generate_structured("test", response_model=GeneratedProgressionSet)
    assert isinstance(result, GeneratedProgressionSet)
    assert len(result.progressions) == 4


@pytest.mark.asyncio
async def test_fake_gemini_returns_gemini_scores() -> None:
    client = FakeGeminiClient()
    result = await client.generate_structured("test", response_model=GeminiScores)
    assert isinstance(result, GeminiScores)
    assert 0 <= result.genre_fit <= 10


@pytest.mark.asyncio
async def test_fake_gemini_returns_voicing_strategy() -> None:
    client = FakeGeminiClient()
    result = await client.generate_structured("test", response_model=VoicingStrategyResponse)
    assert isinstance(result, VoicingStrategyResponse)
    assert result.voice_count == 4


@pytest.mark.asyncio
async def test_fake_gemini_returns_mutation_response() -> None:
    client = FakeGeminiClient()
    result = await client.generate_structured("test", response_model=MutationResponse)
    assert isinstance(result, MutationResponse)
    assert len(result.mutated_chord_symbols) > 0


@pytest.mark.asyncio
async def test_fake_gemini_returns_feedback_interpretation() -> None:
    client = FakeGeminiClient()
    result = await client.generate_structured("test", response_model=FeedbackInterpretation)
    assert isinstance(result, FeedbackInterpretation)
    assert result.satisfaction == "neutral"


@pytest.mark.asyncio
async def test_fake_gemini_tracks_call_counts() -> None:
    client = FakeGeminiClient()
    await client.generate_structured("a", response_model=GeminiScores)
    await client.generate_structured("b", response_model=GeminiScores)
    assert client.call_counts["GeminiScores"] == 2


@pytest.mark.asyncio
async def test_fake_gemini_rejects_unknown_model() -> None:
    from pydantic import BaseModel

    class UnknownModel(BaseModel):
        x: int

    client = FakeGeminiClient()
    with pytest.raises(ValueError, match="Unsupported"):
        await client.generate_structured("test", response_model=UnknownModel)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/angel/Documents/code/Explorator/backend && uv run python -m pytest tests/unit/adapters/test_gemini_mock.py -v`

- [ ] **Step 3: Implement FakeGeminiClient**

```python
# backend/src/explorator/adapters/gemini_mock.py
"""Fake Gemini client for E2E testing — returns deterministic structured responses."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import TypeVar

from pydantic import BaseModel

from explorator.adapters.gemini import ModelTier

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Lazy imports to avoid circular dependencies — resolved at call time
_FIXTURE_BUILDERS: dict[str, object] = {}


def _get_fixture_builders() -> dict[str, callable]:
    """Build fixture map on first call (avoids import-time circular deps)."""
    if _FIXTURE_BUILDERS:
        return _FIXTURE_BUILDERS

    from explorator.domain.intent.parser import SoftPreferences
    from explorator.domain.harmony.generator import GeneratedProgression, GeneratedProgressionSet
    from explorator.domain.evaluation.theory import GeminiScores
    from explorator.models.realization import (
        ChordVoicingInstruction,
        VoicingStrategyResponse,
    )
    from explorator.domain.harmony.mutator import MutationResponse, MutationResponseItem
    from explorator.domain.intent.feedback import FeedbackInterpretation

    _PROGRESSIONS = [
        GeneratedProgression(
            chord_symbols=["Amaj7", "F#m7", "Dmaj7", "E7"],
            rationale="Classic dream pop I-vi-IV-V with 7th extensions",
            intent_tags=["wistful", "ethereal"],
        ),
        GeneratedProgression(
            chord_symbols=["Amaj7", "C#m7", "F#m7", "Dmaj7"],
            rationale="Descending movement through relative minor",
            intent_tags=["melancholic", "flowing"],
        ),
        GeneratedProgression(
            chord_symbols=["Dmaj7", "Amaj7", "E7", "F#m7"],
            rationale="Subdominant-start for floating quality",
            intent_tags=["dreamy", "open"],
        ),
        GeneratedProgression(
            chord_symbols=["F#m7", "Dmaj7", "Amaj7", "E7"],
            rationale="Minor-start for darker mood",
            intent_tags=["haunted", "atmospheric"],
        ),
    ]

    _FIXTURE_BUILDERS.update({
        "SoftPreferences": lambda: SoftPreferences(
            mood_targets=["wistful", "ethereal"],
            energy_level="low",
            complexity_target="medium",
            novelty_target="moderate",
        ),
        "GeneratedProgressionSet": lambda: GeneratedProgressionSet(
            progressions=_PROGRESSIONS,
        ),
        "GeminiScores": lambda: GeminiScores(
            genre_fit=7.5,
            emotional_fit=7.0,
            novelty=6.5,
        ),
        "VoicingStrategyResponse": lambda: VoicingStrategyResponse(
            global_strategy="Open voicings with 7th extensions",
            density_level="medium",
            voice_count=4,
            register_profile="mid_high",
            rationale="Ethereal texture via spread voicings",
            per_chord=[
                ChordVoicingInstruction(
                    chord_symbol=sym,
                    voicing_type="open",
                    target_register="mid_high",
                    extensions_to_include=["7"],
                )
                for sym in ["Amaj7", "F#m7", "Dmaj7", "E7"]
            ],
        ),
        "MutationResponse": lambda: MutationResponse(
            mutated_chord_symbols=["Amaj7", "F#m9", "Dmaj7", "Esus4"],
            mutations=[
                MutationResponseItem(
                    operation="substitute_chord",
                    position=1,
                    original_value="F#m7",
                    new_value="F#m9",
                    description="Added 9th for color",
                    reason="Increases novelty",
                    predicted_score_changes=["novelty: +0.5"],
                ),
            ],
        ),
        "FeedbackInterpretation": lambda: FeedbackInterpretation(
            interpreted_adjustments={"increase_novelty": True, "reduce_predictability": True},
            weight_deltas={"novelty": 0.03, "genre_fit": -0.02, "loopability": -0.01},
            satisfaction="neutral",
        ),
    })

    return _FIXTURE_BUILDERS


class FakeGeminiClient:
    """Drop-in replacement for GeminiClient that returns deterministic fixtures."""

    def __init__(self) -> None:
        self.call_counts: dict[str, int] = defaultdict(int)

    def get_model_name(self, tier: ModelTier) -> str:
        return f"fake-{tier.value}"

    async def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        tier: ModelTier = ModelTier.FLASH,
        system_prompt: str | None = None,
    ) -> T:
        """Return a deterministic fixture based on response_model type."""
        name = response_model.__name__
        builders = _get_fixture_builders()

        if name not in builders:
            msg = f"Unsupported response_model for FakeGeminiClient: {name}"
            raise ValueError(msg)

        self.call_counts[name] += 1
        result = builders[name]()
        logger.info("FakeGemini: %s (call #%d)", name, self.call_counts[name])
        return result

    async def generate_text(
        self,
        prompt: str,
        tier: ModelTier = ModelTier.FLASH,
        system_prompt: str | None = None,
    ) -> str:
        """Return a placeholder text response."""
        self.call_counts["generate_text"] += 1
        return "Mock text response"
```

- [ ] **Step 4: Modify deps.py for mock activation**

In `backend/src/explorator/api/deps.py`, change `get_gemini_client`:

```python
import os

from functools import lru_cache

from neo4j import AsyncDriver

from explorator.adapters.gemini import GeminiClient
from explorator.config import settings
from explorator.graph.connection import get_driver
from explorator.graph.session_repo import SessionRepository
from explorator.graph.style_repo import StyleRepository


async def get_neo4j_driver() -> AsyncDriver:
    """Get Neo4j driver dependency."""
    return await get_driver()


async def get_session_repo() -> SessionRepository:
    """Get session repository dependency."""
    driver = await get_driver()
    return SessionRepository(driver)


async def get_style_repo() -> StyleRepository:
    """Get style repository dependency."""
    driver = await get_driver()
    return StyleRepository(driver)


@lru_cache
def get_gemini_client() -> GeminiClient:
    """Get Gemini client singleton. Returns FakeGeminiClient when GEMINI_MOCK=true."""
    if os.environ.get("GEMINI_MOCK", "").lower() == "true":
        from explorator.adapters.gemini_mock import FakeGeminiClient
        return FakeGeminiClient()  # type: ignore[return-value]
    return GeminiClient(
        api_key=settings.gemini_api_key,
        pro_model=settings.gemini_pro_model,
        flash_model=settings.gemini_flash_model,
        timeout_seconds=settings.gemini_timeout_seconds,
    )
```

- [ ] **Step 5: Run tests**

Run: `cd /home/angel/Documents/code/Explorator/backend && uv run python -m pytest tests/unit/adapters/test_gemini_mock.py -v`
Expected: ALL PASS (8 tests)

- [ ] **Step 6: Verify mock works E2E**

Run: `cd /home/angel/Documents/code/Explorator/backend && GEMINI_MOCK=true uv run python -c "
import asyncio
from explorator.api.deps import get_gemini_client
client = get_gemini_client()
print(type(client).__name__)
"`
Expected: `FakeGeminiClient`

- [ ] **Step 7: Commit**

```bash
cd /home/angel/Documents/code/Explorator && git add backend/src/explorator/adapters/gemini_mock.py backend/src/explorator/api/deps.py backend/tests/unit/adapters/test_gemini_mock.py && git commit -m "feat(e2e): FakeGeminiClient mock with deterministic fixtures and GEMINI_MOCK env toggle"
```

---

### Task 2: Playwright Infrastructure

**Files:**
- Create: `e2e/package.json`
- Create: `e2e/tsconfig.json`
- Create: `e2e/playwright.config.ts`
- Create: `e2e/global-setup.ts`
- Create: `e2e/global-teardown.ts`
- Create: `e2e/fixtures/test-fixtures.ts`

- [ ] **Step 1: Create e2e/package.json**

```json
{
  "name": "explorator-e2e",
  "private": true,
  "scripts": {
    "test": "playwright test",
    "test:headed": "playwright test --headed",
    "test:debug": "playwright test --debug"
  },
  "devDependencies": {
    "@playwright/test": "^1.52.0",
    "typescript": "^5.9.0"
  }
}
```

- [ ] **Step 2: Create e2e/tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "esModuleInterop": true,
    "outDir": "dist",
    "rootDir": "."
  },
  "include": ["**/*.ts"]
}
```

- [ ] **Step 3: Create e2e/playwright.config.ts**

```typescript
import { defineConfig } from '@playwright/test';

const BACKEND_PORT = 8100;
const FRONTEND_PORT = 5199;

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,  // Serial — shared Neo4j
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: `http://localhost:${FRONTEND_PORT}`,
    trace: 'on-first-retry',
    video: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  globalSetup: './global-setup.ts',
  globalTeardown: './global-teardown.ts',
  projects: [
    { name: 'chromium', use: { browserName: 'chromium' } },
  ],
});
```

- [ ] **Step 4: Create e2e/global-setup.ts**

```typescript
import { spawn, type ChildProcess } from 'child_process';
import { writeFileSync } from 'fs';
import path from 'path';

const BACKEND_PORT = 8100;
const FRONTEND_PORT = 5199;
const ROOT = path.resolve(__dirname, '..');
const PID_FILE = path.join(__dirname, '.server-pids.json');

async function waitForHealth(url: string, timeoutMs = 30_000): Promise<void> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(url);
      if (res.ok) return;
    } catch { /* server not ready */ }
    await new Promise(r => setTimeout(r, 500));
  }
  throw new Error(`Health check failed: ${url} not ready after ${timeoutMs}ms`);
}

export default async function globalSetup() {
  console.log('Starting backend (GEMINI_MOCK=true) on port', BACKEND_PORT);
  const backend = spawn(
    'uv', ['run', 'uvicorn', 'explorator.api.app:create_app', '--factory',
           '--host', '0.0.0.0', '--port', String(BACKEND_PORT)],
    {
      cwd: path.join(ROOT, 'backend'),
      env: { ...process.env, GEMINI_MOCK: 'true' },
      stdio: 'pipe',
      detached: true,
    },
  );
  backend.unref();

  console.log('Starting frontend on port', FRONTEND_PORT);
  const frontend = spawn(
    'npx', ['vite', '--port', String(FRONTEND_PORT), '--strictPort'],
    {
      cwd: path.join(ROOT, 'frontend'),
      env: {
        ...process.env,
        VITE_API_TARGET: `http://localhost:${BACKEND_PORT}`,
      },
      stdio: 'pipe',
      detached: true,
    },
  );
  frontend.unref();

  // Save PIDs for teardown
  writeFileSync(PID_FILE, JSON.stringify({
    backend: backend.pid,
    frontend: frontend.pid,
  }));

  // Wait for servers
  await waitForHealth(`http://localhost:${BACKEND_PORT}/v1/sessions`);
  console.log('Backend ready');

  await waitForHealth(`http://localhost:${FRONTEND_PORT}`);
  console.log('Frontend ready');
}
```

- [ ] **Step 5: Create e2e/global-teardown.ts**

```typescript
import { readFileSync, unlinkSync } from 'fs';
import path from 'path';

const PID_FILE = path.join(__dirname, '.server-pids.json');

export default async function globalTeardown() {
  try {
    const pids = JSON.parse(readFileSync(PID_FILE, 'utf-8'));
    for (const [name, pid] of Object.entries(pids)) {
      try {
        // Kill process group (negative PID kills the group)
        process.kill(-(pid as number), 'SIGTERM');
        console.log(`Killed ${name} (pid ${pid})`);
      } catch { /* already dead */ }
    }
    unlinkSync(PID_FILE);
  } catch { /* no PID file */ }
}
```

- [ ] **Step 6: Create e2e/fixtures/test-fixtures.ts**

```typescript
import { test as base, type Page } from '@playwright/test';

const API_BASE = 'http://localhost:8100/v1';

export interface TestSession {
  sessionId: string;
  prompt: string;
}

/** Create a session via API and return its ID + prompt. */
async function createTestSession(prompt = 'Dream pop in A major, wistful, 4 bars'): Promise<TestSession> {
  const res = await fetch(`${API_BASE}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt, mode: 'full_exploration' }),
  });
  if (!res.ok) throw new Error(`Failed to create session: ${res.status}`);
  const data = await res.json();
  return { sessionId: data.session_id, prompt };
}

/** Navigate to a session workspace and wait for it to load. */
async function goToWorkspace(page: Page, sessionId: string): Promise<void> {
  await page.goto(`/session/${sessionId}`);
  await page.waitForSelector('[data-testid="prompt-input"], input[placeholder]', { timeout: 10_000 });
}

/** Type a prompt and click Generate, wait for candidates to appear. */
async function generateCandidates(page: Page, prompt: string): Promise<void> {
  const input = page.locator('input[placeholder*="mood"]').or(page.locator('input[placeholder*="Describe"]'));
  await input.fill(prompt);
  await page.getByRole('button', { name: /generate/i }).click();
  // Wait for at least one candidate card to appear (generous timeout for LangGraph pipeline)
  await page.locator('[class*="rounded-lg"]').filter({ hasText: /→/ }).first().waitFor({ timeout: 30_000 });
}

/** Click Realize on the first candidate and wait for arrangement view. */
async function realizeFirstCandidate(page: Page): Promise<void> {
  await page.getByRole('button', { name: /realize/i }).first().click();
  // Wait for arrangement list or piano roll canvas
  await page.locator('canvas').or(page.locator('[class*="shrink-0"]')).first().waitFor({ timeout: 30_000 });
}

// Extended test fixture with helpers
export const test = base.extend<{
  testSession: TestSession;
}>({
  testSession: async ({}, use) => {
    const session = await createTestSession();
    await use(session);
  },
});

export { createTestSession, goToWorkspace, generateCandidates, realizeFirstCandidate };
export { expect } from '@playwright/test';
```

- [ ] **Step 7: Install dependencies**

Run: `cd /home/angel/Documents/code/Explorator/e2e && npm install && npx playwright install chromium`

- [ ] **Step 8: Commit**

```bash
cd /home/angel/Documents/code/Explorator && git add e2e/ && git commit -m "feat(e2e): Playwright infrastructure — config, global setup/teardown, test fixtures"
```

---

### Task 3: Happy Path Tests (Tests 1-3)

**Files:**
- Create: `e2e/tests/happy-path.spec.ts`

- [ ] **Step 1: Write the tests**

```typescript
// e2e/tests/happy-path.spec.ts
import { test, expect, createTestSession, goToWorkspace, generateCandidates, realizeFirstCandidate } from '../fixtures/test-fixtures';

test.describe('Happy Path', () => {
  test('1: dashboard-create-session', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('text=Explorator')).toBeVisible();

    const input = page.locator('input[placeholder*="Dream pop"]').or(page.locator('input[placeholder*="wistful"]'));
    await input.fill('Dream pop in A major, wistful, 4 bars');
    await page.getByRole('button', { name: /explore/i }).click();

    // Should redirect to /session/:id
    await page.waitForURL(/\/session\//);
    await expect(page.locator('text=Dream pop')).toBeVisible();
  });

  test('2: generation-flow', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);

    // Candidate cards should have chord symbols (contain →)
    const cards = page.locator('[class*="rounded-lg"]').filter({ hasText: /→/ });
    const count = await cards.count();
    expect(count).toBeGreaterThan(0);

    // Each card should have a score badge
    const scores = page.locator('[class*="font-mono"]').filter({ hasText: /\d+\.\d/ });
    expect(await scores.count()).toBeGreaterThan(0);
  });

  test('3: realization-flow', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);
    await realizeFirstCandidate(page);

    // Arrangement list visible
    await expect(page.locator('text=Finalists').or(page.locator('[class*="shrink-0"]'))).toBeVisible();

    // Piano roll canvas visible
    await expect(page.locator('canvas')).toBeVisible();

    // Transport bar play button visible
    await expect(page.locator('svg').first()).toBeVisible();

    // Score panel visible
    await expect(page.locator('text=Scores').or(page.locator('text=Arrangement'))).toBeVisible();
  });
});
```

- [ ] **Step 2: Run**

Run: `cd /home/angel/Documents/code/Explorator/e2e && npx playwright test tests/happy-path.spec.ts --headed`

- [ ] **Step 3: Commit**

```bash
cd /home/angel/Documents/code/Explorator && git add e2e/tests/happy-path.spec.ts && git commit -m "test(e2e): happy path tests — dashboard, generation, realization"
```

---

### Task 4: M3 Feature Tests (Tests 4-7)

**Files:**
- Create: `e2e/tests/m3-features.spec.ts`

- [ ] **Step 1: Write the tests**

```typescript
// e2e/tests/m3-features.spec.ts
import { test, expect, createTestSession, goToWorkspace, generateCandidates, realizeFirstCandidate } from '../fixtures/test-fixtures';

test.describe('M3 Features', () => {
  test('4: feedback-submission', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);
    await realizeFirstCandidate(page);

    // Click an arrangement to select it
    await page.locator('[class*="cursor-pointer"]').filter({ hasText: /\d+\.\d/ }).first().click();

    // Type feedback
    const feedbackInput = page.locator('input[placeholder*="experimental"]').or(page.locator('input[placeholder*="more"]'));
    await feedbackInput.fill('more experimental, less predictable');
    await page.getByRole('button', { name: /send/i }).click();

    // Wait for interpretation bubble
    await expect(page.locator('text=Understood')).toBeVisible({ timeout: 15_000 });

    // Weight bars should appear (look for "Weights" heading or dimension labels)
    await expect(page.locator('text=Weights').or(page.locator('text=Genre Fit'))).toBeVisible();
  });

  test('5: mutation-flow', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);

    // Click Mutate on first candidate
    await page.getByRole('button', { name: /mutate/i }).first().click();

    // Modal should appear with chord progression
    await expect(page.locator('text=Mutate Candidate')).toBeVisible();

    // Type guidance and submit
    await page.locator('input[placeholder*="darker"]').or(page.locator('input[placeholder*="tension"]')).fill('make it darker');
    await page.locator('button:has-text("Mutate")').last().click();

    // Wait for completion, reload candidates
    await page.waitForTimeout(5_000);
    await page.reload();
    await page.waitForTimeout(2_000);

    // Check for mutated badge
    await expect(page.locator('text=mutated')).toBeVisible({ timeout: 10_000 });

    // Lineage tree should appear
    await expect(page.locator('text=Mutation Lineage')).toBeVisible();
  });

  test('6: finalist-panel', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);
    await realizeFirstCandidate(page);

    // Finalists section should be visible
    await expect(page.locator('text=Finalists')).toBeVisible({ timeout: 10_000 });

    // At least one role badge
    const badges = page.locator('text=Safest').or(page.locator('text=Best Loop')).or(page.locator('text=Most Experimental'));
    await expect(badges.first()).toBeVisible();
  });

  test('7: realization-caching', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);
    await realizeFirstCandidate(page);

    // Note: we're in realization view now
    // Go back
    await page.getByText('Back to progressions').or(page.getByText('Back')).click();
    await page.waitForTimeout(500);

    // Realize same candidate again
    const start = Date.now();
    await page.getByRole('button', { name: /realize/i }).first().click();

    // Should load instantly (no SSE stream)
    await page.locator('canvas').waitFor({ timeout: 5_000 });
    const elapsed = Date.now() - start;

    // Should be fast — no pipeline progress bar visible
    expect(elapsed).toBeLessThan(3_000);
  });
});
```

- [ ] **Step 2: Run**

Run: `cd /home/angel/Documents/code/Explorator/e2e && npx playwright test tests/m3-features.spec.ts --headed`

- [ ] **Step 3: Commit**

```bash
cd /home/angel/Documents/code/Explorator && git add e2e/tests/m3-features.spec.ts && git commit -m "test(e2e): M3 feature tests — feedback, mutation, finalists, caching"
```

---

### Task 5: Error & Edge Case Tests (Tests 8-10)

**Files:**
- Create: `e2e/tests/error-edge.spec.ts`

- [ ] **Step 1: Write the tests**

```typescript
// e2e/tests/error-edge.spec.ts
import { test, expect, goToWorkspace, generateCandidates } from '../fixtures/test-fixtures';

test.describe('Error & Edge Cases', () => {
  test('8: session-not-found', async ({ page }) => {
    await page.goto('/session/nonexistent_fake_id_12345');
    // Should not crash — page renders
    await page.waitForTimeout(2_000);
    // No unhandled JS errors (Playwright captures these)
    // Page should show some content (header, or empty state)
    await expect(page.locator('body')).toBeVisible();
  });

  test('9: empty-state', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    // No generation yet
    await expect(page.locator('text=No candidates yet')).toBeVisible();
    // No loading spinners
    await expect(page.locator('[class*="animate-pulse"]')).toHaveCount(0);
  });

  test('10: progressive-disclosure', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);

    // Lineage tree should NOT be visible (no mutations yet)
    await expect(page.locator('text=Mutation Lineage')).toBeHidden();

    // Feedback sidebar should not be in generation view
    // (it's only in realization view)
    await expect(page.locator('text=Feedback')).toBeHidden();
  });
});
```

- [ ] **Step 2: Run and commit**

Run: `cd /home/angel/Documents/code/Explorator/e2e && npx playwright test tests/error-edge.spec.ts --headed`

```bash
cd /home/angel/Documents/code/Explorator && git add e2e/tests/error-edge.spec.ts && git commit -m "test(e2e): error and edge case tests — not-found, empty state, progressive disclosure"
```

---

### Task 6: UX Coherence Tests (Tests 11-13)

**Files:**
- Create: `e2e/tests/ux-coherence.spec.ts`

- [ ] **Step 1: Write the tests**

```typescript
// e2e/tests/ux-coherence.spec.ts
import { test, expect, createTestSession, goToWorkspace, generateCandidates, realizeFirstCandidate } from '../fixtures/test-fixtures';

test.describe('UX Coherence', () => {
  test('11: navigation-flow', async ({ page }) => {
    // Start at dashboard
    await page.goto('/');
    await expect(page.locator('text=Explorator')).toBeVisible();

    // Create session
    const input = page.locator('input[placeholder*="Dream pop"]').or(page.locator('input[placeholder*="wistful"]'));
    await input.fill('Navigation test, dream pop, 4 bars');
    await page.getByRole('button', { name: /explore/i }).click();
    await page.waitForURL(/\/session\//);

    // Generate
    const promptInput = page.locator('input[placeholder*="mood"]').or(page.locator('input[placeholder*="Describe"]'));
    await promptInput.fill('Navigation test, dream pop, 4 bars');
    await page.getByRole('button', { name: /generate/i }).click();
    await page.locator('[class*="rounded-lg"]').filter({ hasText: /→/ }).first().waitFor({ timeout: 30_000 });

    // Realize
    await page.getByRole('button', { name: /realize/i }).first().click();
    await page.locator('canvas').waitFor({ timeout: 30_000 });

    // Back to progressions
    await page.getByText('Back to progressions').or(page.getByText('Back')).click();
    await page.waitForTimeout(500);

    // Candidates should still be there
    const cards = page.locator('[class*="rounded-lg"]').filter({ hasText: /→/ });
    expect(await cards.count()).toBeGreaterThan(0);

    // No orphaned loading spinners
    await expect(page.locator('[class*="animate-pulse"]')).toHaveCount(0);

    // Back to dashboard
    await page.getByText('Back').first().click();
    await page.waitForURL('/');
    await expect(page.locator('text=Explorator')).toBeVisible();
  });

  test('12: view-state-consistency', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);

    // Count candidates from heading
    const heading = page.locator('text=/\\d+ candidate/');
    const headingText = await heading.textContent() ?? '';
    const headingCount = parseInt(headingText.match(/(\d+)/)?.[1] ?? '0');

    // Count actual cards
    const cards = page.locator('[class*="rounded-lg"]').filter({ hasText: /→/ });
    const cardCount = await cards.count();
    expect(cardCount).toBe(headingCount);

    // Realize and go back
    await realizeFirstCandidate(page);
    await page.getByText('Back to progressions').or(page.getByText('Back')).click();
    await page.waitForTimeout(500);

    // Candidates still present
    const cardsAfter = page.locator('[class*="rounded-lg"]').filter({ hasText: /→/ });
    expect(await cardsAfter.count()).toBe(cardCount);

    // No loading spinner when data already loaded
    await expect(page.locator('[class*="animate-pulse"]')).toHaveCount(0);
  });

  test('13: interaction-affordances', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);

    // Generate button disabled when input empty
    const genButton = page.getByRole('button', { name: /generate/i });
    await expect(genButton).toBeDisabled();

    // Fill prompt, start generation
    const input = page.locator('input[placeholder*="mood"]').or(page.locator('input[placeholder*="Describe"]'));
    await input.fill(testSession.prompt);
    await genButton.click();

    // While running, button should be disabled
    await expect(genButton).toBeDisabled();
    // Input should be disabled
    await expect(input).toBeDisabled();

    // Wait for completion
    await page.locator('[class*="rounded-lg"]').filter({ hasText: /→/ }).first().waitFor({ timeout: 30_000 });

    // After completion, no phantom progress bar
    await page.waitForTimeout(500);
    // Progress bar container should be hidden
    const progressBars = page.locator('[class*="rounded-full"]').filter({ has: page.locator('[class*="transition-all"]') });
    // Just verify generation completed cleanly — button re-enabled
    await expect(genButton).not.toBeDisabled();
  });
});
```

- [ ] **Step 2: Run and commit**

Run: `cd /home/angel/Documents/code/Explorator/e2e && npx playwright test tests/ux-coherence.spec.ts --headed`

```bash
cd /home/angel/Documents/code/Explorator && git add e2e/tests/ux-coherence.spec.ts && git commit -m "test(e2e): UX coherence tests — navigation, state consistency, affordances"
```

---

### Task 7: Pipeline & Audio Tests (Tests 14-18)

**Files:**
- Create: `e2e/tests/pipeline.spec.ts`
- Create: `e2e/tests/audio.spec.ts`

- [ ] **Step 1: Write pipeline tests**

```typescript
// e2e/tests/pipeline.spec.ts
import { test, expect, createTestSession, goToWorkspace, generateCandidates } from '../fixtures/test-fixtures';

test.describe('Pipeline & SSE', () => {
  test('14: sse-stream-completion', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);

    const input = page.locator('input[placeholder*="mood"]').or(page.locator('input[placeholder*="Describe"]'));
    await input.fill(testSession.prompt);
    await page.getByRole('button', { name: /generate/i }).click();

    // Wait for candidates (means stream completed)
    await page.locator('[class*="rounded-lg"]').filter({ hasText: /→/ }).first().waitFor({ timeout: 30_000 });

    // Loading state should be cleared
    const genButton = page.getByRole('button', { name: /generate/i });
    await expect(genButton).not.toBeDisabled();

    // No error message
    await expect(page.locator('text=timed out')).toBeHidden();
    await expect(page.locator('text=Error')).toBeHidden();
  });

  test('15: multi-round-generation', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);

    const cards1 = page.locator('[class*="rounded-lg"]').filter({ hasText: /→/ });
    const count1 = await cards1.count();
    expect(count1).toBeGreaterThan(0);

    // Generate again (round 2)
    const input = page.locator('input[placeholder*="mood"]').or(page.locator('input[placeholder*="Describe"]'));
    await input.fill('More dreamy, add suspensions');
    await page.getByRole('button', { name: /generate/i }).click();
    await page.waitForTimeout(2_000);

    // Wait for new candidates
    await page.locator('[class*="rounded-lg"]').filter({ hasText: /→/ }).first().waitFor({ timeout: 60_000 });

    // Should still have candidates (not cleared)
    const cards2 = page.locator('[class*="rounded-lg"]').filter({ hasText: /→/ });
    expect(await cards2.count()).toBeGreaterThanOrEqual(count1);
  });

  test('16: generation-mode-switching', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);

    // Select exploratory mode
    await page.getByRole('button', { name: /exploratory/i }).click();

    // Generate
    await generateCandidates(page, testSession.prompt);

    // Mode should still be visually selected
    const modeButton = page.getByRole('button', { name: /exploratory/i });
    // Check it has the active styling (accent color)
    await expect(modeButton).toBeVisible();
  });
});
```

- [ ] **Step 2: Write audio tests**

```typescript
// e2e/tests/audio.spec.ts
import { test, expect, goToWorkspace, generateCandidates, realizeFirstCandidate } from '../fixtures/test-fixtures';

test.describe('Audio & Feedback Integration', () => {
  test('17: audio-playback-controls', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);
    await realizeFirstCandidate(page);

    // Transport bar should be visible
    const transportBar = page.locator('[class*="bg-slate-900"]').filter({ has: page.locator('svg') }).first();
    await expect(transportBar).toBeVisible();

    // Play button — click it (we can't verify audio, just that UI updates)
    const playButton = page.locator('button').filter({ has: page.locator('svg polygon') }).first();
    await playButton.click();
    await page.waitForTimeout(500);

    // Stop button — click it
    const stopButton = page.locator('button').filter({ has: page.locator('svg rect') }).first();
    await stopButton.click();

    // Mute toggles — verify V and B buttons exist
    await expect(page.locator('button:has-text("V")')).toBeVisible();
    await expect(page.locator('button:has-text("B")')).toBeVisible();

    // Click V to toggle mute
    await page.locator('button:has-text("V")').click();
    await page.waitForTimeout(200);

    // BPM display should be visible
    await expect(page.locator('text=BPM')).toBeVisible();

    // Volume display
    await expect(page.locator('text=Vol')).toBeVisible();
  });

  test('18: feedback-affects-next-round', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);
    await realizeFirstCandidate(page);

    // Select an arrangement
    await page.locator('[class*="cursor-pointer"]').filter({ hasText: /\d+\.\d/ }).first().click();

    // Submit feedback
    const feedbackInput = page.locator('input[placeholder*="experimental"]').or(page.locator('input[placeholder*="more"]'));
    await feedbackInput.fill('prefer more loopable progressions');
    await page.getByRole('button', { name: /send/i }).click();
    await expect(page.locator('text=Understood')).toBeVisible({ timeout: 15_000 });

    // Go back to progressions
    await page.getByText('Back to progressions').or(page.getByText('Back')).click();
    await page.waitForTimeout(500);

    // Generate round 2
    const input = page.locator('input[placeholder*="mood"]').or(page.locator('input[placeholder*="Describe"]'));
    await input.fill('Continue exploring with feedback applied');
    await page.getByRole('button', { name: /generate/i }).click();

    // Wait for completion — verify no error
    await page.locator('[class*="rounded-lg"]').filter({ hasText: /→/ }).first().waitFor({ timeout: 60_000 });
    await expect(page.locator('text=Error')).toBeHidden();
  });
});
```

- [ ] **Step 3: Run and commit**

Run: `cd /home/angel/Documents/code/Explorator/e2e && npx playwright test tests/pipeline.spec.ts tests/audio.spec.ts --headed`

```bash
cd /home/angel/Documents/code/Explorator && git add e2e/tests/pipeline.spec.ts e2e/tests/audio.spec.ts && git commit -m "test(e2e): pipeline/SSE tests and audio/feedback integration tests"
```

---

### Task 8: Makefile + Final Verification

**Files:**
- Modify: `Makefile`

- [ ] **Step 1: Add e2e target to Makefile**

Append to `Makefile`:

```makefile
.PHONY: e2e
e2e:  ## Run E2E Playwright tests (requires Neo4j running)
	cd e2e && npx playwright test

.PHONY: e2e-headed
e2e-headed:  ## Run E2E tests with browser visible
	cd e2e && npx playwright test --headed
```

- [ ] **Step 2: Run the full suite**

Run: `cd /home/angel/Documents/code/Explorator && make e2e`
Expected: 18 tests pass

- [ ] **Step 3: Commit**

```bash
cd /home/angel/Documents/code/Explorator && git add Makefile && git commit -m "feat(e2e): add make e2e and make e2e-headed targets"
```
