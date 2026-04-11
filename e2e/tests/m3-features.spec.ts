import { test, expect, goToWorkspace, generateCandidates, realizeFirstCandidate } from '../fixtures/test-fixtures';

test.describe('M3 Features', () => {
  test('4: feedback-submission', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);
    await realizeFirstCandidate(page);

    // Select an arrangement in the list panel
    await page.locator('[class*="rounded-md"][class*="cursor-pointer"]').first().click();
    await page.waitForTimeout(500);

    // Feedback input should be enabled
    const feedbackInput = page.locator('input[placeholder*="experimental"]');
    await expect(feedbackInput).toBeVisible({ timeout: 5_000 });
    await feedbackInput.fill('more experimental, less predictable');
    await page.getByRole('button', { name: /send/i }).click();

    await expect(page.locator('text=Understood')).toBeVisible({ timeout: 15_000 });
  });

  test('5: mutation-flow', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);

    await page.getByRole('button', { name: /mutate/i }).first().click();
    await expect(page.locator('text=Mutate Candidate')).toBeVisible();

    const guidanceInput = page.locator('input[placeholder*="darker"]')
      .or(page.locator('input[placeholder*="tension"]'));
    await guidanceInput.fill('make it darker');

    // Click the modal's Mutate button (the purple one inside the modal)
    await page.locator('[class*="bg-purple-600"]').filter({ hasText: /mutate/i }).click();

    // Wait for SSE and reload
    await page.waitForTimeout(8_000);
    await page.reload();
    await page.locator('text=→').first().waitFor({ timeout: 30_000 });

    await expect(page.locator('text=mutated')).toBeVisible({ timeout: 10_000 });
  });

  test('6: finalist-panel', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);
    await realizeFirstCandidate(page);

    await expect(page.locator('text=Finalists')).toBeVisible({ timeout: 10_000 });
  });

  test('7: realization-caching', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);
    await realizeFirstCandidate(page);

    // Go back — use specific button text
    await page.getByRole('button', { name: /back to progressions/i }).click();
    await page.waitForTimeout(500);

    // Realize same candidate again — should be instant
    const start = Date.now();
    await page.getByRole('button', { name: /realize/i }).first().click();
    await page.locator('canvas').waitFor({ timeout: 5_000 });
    expect(Date.now() - start).toBeLessThan(3_000);
  });
});
