import { test, expect, goToWorkspace, generateCandidates } from '../fixtures/test-fixtures';

test.describe('Pipeline & SSE', () => {
  test('14: sse-stream-completion', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);

    await page.locator('input').first().fill(testSession.prompt);
    await page.getByRole('button', { name: /generate/i }).click();

    // Wait for candidates (means stream completed successfully)
    await page.locator('text=→').first().waitFor({ timeout: 60_000 });

    // Loading cleared, button re-enabled
    await expect(page.getByRole('button', { name: /generate/i })).not.toBeDisabled();

    // No timeout or error messages
    await expect(page.locator('text=timed out')).toBeHidden();
  });

  test('15: multi-round-generation', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);

    // Count candidate cards (use the View Arrangements button as proxy — one per candidate)
    const realizeButtons = page.getByRole('button', { name: /view arrangements/i });
    const count1 = await realizeButtons.count();
    expect(count1).toBeGreaterThan(0);

    // Generate round 2
    await page.locator('input').first().fill('More dreamy, add suspensions');
    await page.getByRole('button', { name: /generate/i }).click();
    await page.locator('text=→').first().waitFor({ timeout: 60_000 });

    // Should have at least as many candidates
    expect(await realizeButtons.count()).toBeGreaterThanOrEqual(count1);
  });

  test('16: generation-mode-switching', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);

    await page.getByRole('button', { name: /exploratory/i }).click();
    await generateCandidates(page, testSession.prompt);

    await expect(page.getByRole('button', { name: /exploratory/i })).toBeVisible();
  });
});
