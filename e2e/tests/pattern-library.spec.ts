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

  test('curate a pattern, filter to curated-only, persist across reload', async ({ page, testSession }) => {
    test.setTimeout(120_000);

    // 1. Run a session to seed patterns.
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);
    await realizeFirstCandidate(page);
    await expect(page.locator('text=/Saved \\d+ patterns to library/').first())
      .toBeVisible({ timeout: 60_000 });

    // 2. Go to library, wait for first card.
    await page.goto('/patterns');
    await expect(page.locator('[data-testid^="pattern-card-"]').first()).toBeVisible({ timeout: 15_000 });

    // Find a card that is not yet curated (the first card may already be curated from a prior run).
    const targetCard = page.locator('[data-testid^="pattern-card-"]')
      .filter({ has: page.getByRole('button', { name: 'Mark as curated' }) })
      .first();
    await expect(targetCard).toBeVisible({ timeout: 10_000 });
    const starredTestId = await targetCard.getAttribute('data-testid');
    expect(starredTestId).toBeTruthy();

    // 3. Click its star; expect the button to flip and the Curated toast to fire.
    await targetCard.getByRole('button', { name: 'Mark as curated' }).click();
    // Optimistic update: button flips to "Remove from curated" immediately.
    await expect(
      page.locator(`[data-testid="${starredTestId}"]`)
        .getByRole('button', { name: 'Remove from curated' }),
    ).toBeVisible({ timeout: 10_000 });
    // Sonner renders each toast as <li data-sonner-toast data-type="success"> with a
    // nested <div data-title> containing the message text "Curated".
    await expect(
      page.locator('[data-sonner-toast][data-type="success"] [data-title]')
        .filter({ hasText: /^Curated$/ })
        .first(),
    ).toBeVisible({ timeout: 15_000 });

    // 4. Toggle the Curated-only filter on.
    await page.getByLabel('Curated only').check();

    // 5. Only curated items visible; our starred card is one of them.
    await expect(page.locator(`[data-testid="${starredTestId}"]`)).toBeVisible();
    await expect(
      page.locator(`[data-testid="${starredTestId}"]`)
        .getByRole('button', { name: 'Remove from curated' }),
    ).toBeVisible();

    // 6. Reload — data persists across reload, filter state may or may not; we verify
    //    by re-enabling the filter and checking the starred card is still there with filled star.
    await page.reload();
    const cardAfterReload = page.locator(`[data-testid="${starredTestId}"]`);
    await expect(cardAfterReload).toBeVisible({ timeout: 15_000 });
    await expect(
      cardAfterReload.getByRole('button', { name: 'Remove from curated' }),
    ).toBeVisible();
    await page.getByLabel('Curated only').check();
    await expect(cardAfterReload).toBeVisible();
  });
});
