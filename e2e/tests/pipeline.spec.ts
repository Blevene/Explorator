import { test, expect, goToWorkspace, generateCandidates } from '../fixtures/test-fixtures';

test.describe('Pipeline & SSE', () => {
  test('14: sse-stream-completion', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);

    await page.locator('input').first().fill(testSession.prompt);
    await page.getByRole('button', { name: /generate/i }).click();

    // Wait for candidates
    await page.locator('text=→').first().waitFor({ timeout: 30_000 });

    // Loading cleared, button re-enabled
    await expect(page.getByRole('button', { name: /generate/i })).not.toBeDisabled();

    // No error messages
    await expect(page.locator('text=timed out')).toBeHidden();
    await expect(page.locator('text=Error').first()).toBeHidden();
  });

  test('15: multi-round-generation', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);

    const count1 = await page.locator('text=→').count();
    expect(count1).toBeGreaterThan(0);

    // Generate round 2
    await page.locator('input').first().fill('More dreamy, add suspensions');
    await page.getByRole('button', { name: /generate/i }).click();
    await page.waitForTimeout(2_000);
    await page.locator('text=→').first().waitFor({ timeout: 60_000 });

    // Candidates should still exist
    expect(await page.locator('text=→').count()).toBeGreaterThanOrEqual(count1);
  });

  test('16: generation-mode-switching', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);

    // Select exploratory mode
    await page.getByRole('button', { name: /exploratory/i }).click();

    await generateCandidates(page, testSession.prompt);

    // Mode button still visible
    await expect(page.getByRole('button', { name: /exploratory/i })).toBeVisible();
  });
});
