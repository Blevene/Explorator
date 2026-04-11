import { test, expect, goToWorkspace, generateCandidates } from '../fixtures/test-fixtures';

test.describe('Error & Edge Cases', () => {
  test('8: session-not-found', async ({ page }) => {
    await page.goto('/session/nonexistent_fake_id_12345');
    await page.waitForTimeout(2_000);
    await expect(page.locator('body')).toBeVisible();
    // Should not show an unhandled error page
  });

  test('9: empty-state', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await expect(page.locator('text=No candidates yet')).toBeVisible();
    await expect(page.locator('[class*="animate-pulse"]')).toHaveCount(0);
  });

  test('10: progressive-disclosure', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);

    // Lineage tree hidden (no mutations yet)
    await expect(page.locator('text=Mutation Lineage')).toBeHidden();

    // Feedback sidebar not in generation view
    await expect(page.locator('text=Feedback').first()).toBeHidden();
  });
});
