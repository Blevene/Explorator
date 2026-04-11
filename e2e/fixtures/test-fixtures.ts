import { test as base, type Page } from '@playwright/test';

const API_BASE = 'http://localhost:8100/v1';

export interface TestSession {
  sessionId: string;
  prompt: string;
}

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

async function goToWorkspace(page: Page, sessionId: string): Promise<void> {
  await page.goto(`/session/${sessionId}`);
  await page.waitForLoadState('networkidle');
}

async function generateCandidates(page: Page, prompt: string): Promise<void> {
  const input = page.locator('input').first();
  await input.fill(prompt);
  await page.getByRole('button', { name: /generate/i }).click();
  // Wait for at least one candidate card with chord symbols (→)
  await page.locator('text=→').first().waitFor({ timeout: 60_000 });
}

async function realizeFirstCandidate(page: Page): Promise<void> {
  await page.getByRole('button', { name: /realize/i }).first().click();
  // Wait for arrangement view (canvas or arrangement list)
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
