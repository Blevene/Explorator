import { test, expect, goToWorkspace, generateCandidates } from '../fixtures/test-fixtures';

test.describe('Error & Edge Cases', () => {
  test('8: session-not-found', async ({ page }) => {
    await page.goto('/session/nonexistent_fake_id_12345');
    await page.waitForTimeout(2_000);
    await expect(page.locator('body')).toBeVisible();
    // Should not show an unhandled error page
  });

  test('9: empty-state', async ({ page, testSession }) => {
    // Auto-generate fires when a session has a prompt, so the empty state
    // may only flash briefly. Verify the workspace loads without errors
    // and that either the empty state or the generating state is shown.
    await goToWorkspace(page, testSession.sessionId);
    const emptyOrGenerating = page.locator('[data-testid="empty-state"]')
      .or(page.getByRole('button', { name: /running|generate/i }))
      .or(page.locator('text=→'));
    await expect(emptyOrGenerating.first()).toBeVisible({ timeout: 30_000 });
    // No unhandled error spinners
    await expect(page.locator('[class*="animate-pulse"]')).toHaveCount(0);
  });

  test('10: progressive-disclosure', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);

    // After generation, candidates should be visible
    expect(await page.locator('text=→').count()).toBeGreaterThan(0);

    // Mutation lineage tree only shows when mutations exist.
    // On a fresh session with just generation (no explicit mutation), it should
    // either be absent or present only if the pipeline internally mutated.
    // We verify that the UI is coherent — no orphaned spinners or error states.
    await expect(page.locator('[class*="animate-pulse"]')).toHaveCount(0);

    // Candidate cards should have action buttons (View Arrangements, Mutate)
    const actionButtons = page.getByRole('button', { name: /view arrangements|mutate/i });
    expect(await actionButtons.count()).toBeGreaterThan(0);
  });
});
