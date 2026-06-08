import { test as base, type Page } from '@playwright/test';

const API_BASE = 'http://localhost:8100/v1';

export interface TestSession {
  sessionId: string;
  prompt: string;
}

async function createTestSession(
  prompt = 'Dream pop in A major, wistful, 4 bars',
  genre = 'dream_pop',
): Promise<TestSession> {
  const res = await fetch(`${API_BASE}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ genre, prompt, mode: 'full_exploration' }),
  });
  if (!res.ok) throw new Error(`Failed to create session: ${res.status}`);
  const data = await res.json();
  return { sessionId: data.session_id, prompt };
}

async function goToWorkspace(page: Page, sessionId: string): Promise<void> {
  await page.goto(`/session/${sessionId}`);
  await page.waitForLoadState('networkidle');
}

/**
 * Ensure candidates are generated. With auto-generate, navigating to a fresh
 * session starts generation automatically. This helper waits for that to finish,
 * or triggers generation manually if needed.
 */
async function generateCandidates(page: Page, prompt: string): Promise<void> {
  // Check if generation is already running (auto-generate) or candidates exist
  const genButton = page.getByRole('button', { name: /generate|running/i });
  const isRunning = await genButton.textContent().then(t => /running/i.test(t ?? '')).catch(() => false);

  if (!isRunning) {
    // Check if candidates already exist
    const hasCards = await page.locator('text=→').first().isVisible().catch(() => false);
    if (hasCards) return;

    // No auto-generate fired — trigger manually
    const input = page.locator('input').first();
    await input.fill(prompt);
    await page.getByRole('button', { name: /generate/i }).click();
  }

  // Wait for candidates to appear
  await page.locator('text=→').first().waitFor({ timeout: 60_000 });
}

async function realizeFirstCandidate(page: Page): Promise<void> {
  await page.getByRole('button', { name: /realize|view arrangements/i }).first().click();
  await page.locator('canvas').or(page.locator('text=Finalists')).first().waitFor({ timeout: 60_000 });
}

// Extended test fixture with per-test session
export const test = base.extend<{ testSession: TestSession }>({
  testSession: async ({}, use) => {
    const session = await createTestSession();
    await use(session);
  },
});

export { createTestSession, goToWorkspace, generateCandidates, realizeFirstCandidate };
export { expect } from '@playwright/test';
