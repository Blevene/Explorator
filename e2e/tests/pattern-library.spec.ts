import { test, expect, goToWorkspace, generateCandidates, realizeFirstCandidate } from '../fixtures/test-fixtures';

test.describe('Pattern Library', () => {
  test('session finalists appear in library and can be deleted', async ({ page, testSession }) => {
    // 1. Create + complete a session (finalists are selected by the realization pipeline)
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);
    await realizeFirstCandidate(page);

    // 2. Wait for Sonner's "Saved N patterns to library" toast from the harvest_patterns node
    const savedToast = page.locator('text=/Saved \\d+ patterns to library/');
    await expect(savedToast.first()).toBeVisible({ timeout: 60_000 });

    // 3. Navigate to the library and wait for the first card
    await page.goto('/patterns');
    const firstCard = page.locator('[data-testid^="pattern-card-"]').first();
    await expect(firstCard).toBeVisible({ timeout: 15_000 });

    // Capture the deleted pattern's testid so we can assert it's truly gone (not just
    // backfilled by the next page item, which the page-size count alone can't distinguish).
    const deletedTestId = await firstCard.getAttribute('data-testid');
    expect(deletedTestId).toBeTruthy();

    // 4. Delete the first card
    page.once('dialog', (dialog) => dialog.accept()); // confirm() dialog
    await firstCard.getByRole('button', { name: /delete/i }).click();

    // 5. Assert the specific row disappears from the list (detach, not merely hidden)
    await expect(page.locator(`[data-testid="${deletedTestId}"]`)).toHaveCount(0, { timeout: 10_000 });

    // 6. Reload; the deleted row does not reappear — soft-delete persisted in Neo4j
    await page.reload();
    await expect(page.locator('[data-testid^="pattern-card-"]').first()).toBeVisible({ timeout: 15_000 });
    await expect(page.locator(`[data-testid="${deletedTestId}"]`)).toHaveCount(0, { timeout: 10_000 });
  });
});
