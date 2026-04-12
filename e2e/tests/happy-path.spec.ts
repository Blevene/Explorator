import { test, expect, goToWorkspace, generateCandidates, realizeFirstCandidate } from '../fixtures/test-fixtures';

test.describe('Happy Path', () => {
  test('1: dashboard-create-session', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('text=Explorator')).toBeVisible();

    await page.locator('input').first().fill('Dream pop in A major, wistful, 4 bars');
    await page.getByRole('button', { name: /explore/i }).click();

    await page.waitForURL(/\/session\//);
    // Use .first() because other test sessions with similar prompts may exist
    await expect(page.locator('text=Dream pop').first()).toBeVisible();
  });

  test('2: generation-flow', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);

    // Cards with chord symbols
    const cards = page.locator('text=→');
    expect(await cards.count()).toBeGreaterThan(0);

    // Score badges
    const scores = page.locator('.font-mono').filter({ hasText: /^\d+\.\d/ });
    expect(await scores.count()).toBeGreaterThan(0);
  });

  test('3: realization-flow', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);
    await realizeFirstCandidate(page);

    await expect(page.locator('canvas')).toBeVisible();
    await expect(page.locator('text=BPM')).toBeVisible();
    await expect(page.locator('text=Scores').first()).toBeVisible();
  });
});
