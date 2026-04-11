import { test, expect, goToWorkspace, generateCandidates, realizeFirstCandidate } from '../fixtures/test-fixtures';

test.describe('M3 Features', () => {
  test('4: feedback-submission', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);
    await realizeFirstCandidate(page);

    // Select an arrangement
    await page.locator('[class*="cursor-pointer"]').filter({ hasText: /\d+\.\d/ }).first().click();

    // Submit feedback
    const feedbackInput = page.locator('input[placeholder*="experimental"]')
      .or(page.locator('input[placeholder*="more"]'));
    await feedbackInput.fill('more experimental, less predictable');
    await page.getByRole('button', { name: /send/i }).click();

    await expect(page.locator('text=Understood')).toBeVisible({ timeout: 15_000 });
    await expect(page.locator('text=Weights').or(page.locator('text=Genre Fit'))).toBeVisible();
  });

  test('5: mutation-flow', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);

    await page.getByRole('button', { name: /mutate/i }).first().click();
    await expect(page.locator('text=Mutate Candidate')).toBeVisible();

    await page.locator('input[placeholder*="darker"]')
      .or(page.locator('input[placeholder*="tension"]'))
      .fill('make it darker');
    await page.locator('button:has-text("Mutate")').last().click();

    // Wait and reload to see results
    await page.waitForTimeout(5_000);
    await page.reload();
    await page.waitForTimeout(2_000);

    await expect(page.locator('text=mutated')).toBeVisible({ timeout: 10_000 });
    await expect(page.locator('text=Mutation Lineage')).toBeVisible();
  });

  test('6: finalist-panel', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);
    await realizeFirstCandidate(page);

    await expect(page.locator('text=Finalists')).toBeVisible({ timeout: 10_000 });
    const badges = page.locator('text=Safest')
      .or(page.locator('text=Best Loop'))
      .or(page.locator('text=Most Experimental'));
    await expect(badges.first()).toBeVisible();
  });

  test('7: realization-caching', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);
    await realizeFirstCandidate(page);

    // Go back
    await page.getByText('Back to progressions').or(page.getByText('Back')).click();
    await page.waitForTimeout(500);

    // Realize same candidate again — should be instant
    const start = Date.now();
    await page.getByRole('button', { name: /realize/i }).first().click();
    await page.locator('canvas').waitFor({ timeout: 5_000 });
    expect(Date.now() - start).toBeLessThan(3_000);
  });
});
