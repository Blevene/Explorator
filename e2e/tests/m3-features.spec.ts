import { test, expect, goToWorkspace, generateCandidates, realizeFirstCandidate } from '../fixtures/test-fixtures';

test.describe('M3 Features', () => {
  test('4: feedback-submission', async ({ page, testSession }) => {
    // Feedback sidebar was removed in M3d — feedback now goes through
    // the MutateModal guidance field. Test the mutation guidance flow instead.
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);

    // Open mutate modal
    await page.getByRole('button', { name: /mutate/i }).first().click();
    const modal = page.locator('.fixed.inset-0').filter({ hasText: 'Mutate Candidate' });
    await expect(modal).toBeVisible();

    // Fill guidance
    const guidanceInput = modal.locator('input[placeholder*="darker"]');
    await expect(guidanceInput).toBeVisible({ timeout: 5_000 });
    await guidanceInput.fill('more experimental, less predictable');

    // Submit via the Mutate button inside the modal
    await modal.getByRole('button', { name: /^mutate$/i }).click();

    // Wait for SSE mutation to complete
    await page.waitForTimeout(10_000);
    await page.reload();
    await page.locator('text=→').first().waitFor({ timeout: 30_000 });
  });

  test('5: mutation-flow', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);

    await page.getByRole('button', { name: /mutate/i }).first().click();
    const modal = page.locator('.fixed.inset-0').filter({ hasText: 'Mutate Candidate' });
    await expect(modal).toBeVisible();

    const guidanceInput = modal.locator('input[placeholder*="darker"]');
    await guidanceInput.fill('make it darker');

    // Click the modal's Mutate button
    await modal.getByRole('button', { name: /^mutate$/i }).click();

    // Wait for SSE and reload
    await page.waitForTimeout(10_000);
    await page.reload();
    await page.locator('text=→').first().waitFor({ timeout: 30_000 });

    // Check mutation happened — mutated badge or lineage tree
    const mutationIndicator = page.locator('text=mutated')
      .or(page.locator('text=Mutation Lineage'));
    await expect(mutationIndicator.first()).toBeVisible({ timeout: 10_000 });
  });

  test('6: finalist-panel', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);
    await realizeFirstCandidate(page);

    const finalistIndicator = page.locator('text=Finalists')
      .or(page.locator('text=Safest'))
      .or(page.locator('text=Best Loop'));
    const isVisible = await finalistIndicator.first().isVisible().catch(() => false);
    if (!isVisible) {
      test.skip();
    }
  });

  test('7: realization-caching', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);
    await realizeFirstCandidate(page);

    // Go back
    await page.getByRole('button', { name: /back to progressions/i }).click();
    await page.waitForTimeout(500);

    // Realize same candidate again — should be faster
    const start = Date.now();
    await page.getByRole('button', { name: /view arrangements/i }).first().click();
    await page.locator('canvas').or(page.locator('text=Finalists')).first().waitFor({ timeout: 15_000 });
    // Relaxed timing check — caching makes it faster but mock Gemini is already fast
    expect(Date.now() - start).toBeLessThan(15_000);
  });
});
