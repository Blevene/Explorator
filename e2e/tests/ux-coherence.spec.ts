import { test, expect, goToWorkspace, generateCandidates, realizeFirstCandidate } from '../fixtures/test-fixtures';

test.describe('UX Coherence', () => {
  test('11: navigation-flow', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('text=Explorator')).toBeVisible();

    // Create session
    await page.locator('input').first().fill('Navigation test, dream pop, 4 bars');
    await page.getByRole('button', { name: /explore/i }).click();
    await page.waitForURL(/\/session\//);

    // Wait for auto-generate to produce candidates
    await page.locator('text=→').first().waitFor({ timeout: 60_000 });

    // Realize
    await page.getByRole('button', { name: /view arrangements/i }).first().click();
    await page.locator('canvas').or(page.locator('text=Finalists')).first().waitFor({ timeout: 60_000 });

    // Back to progressions
    await page.getByRole('button', { name: /back to progressions/i }).click();
    await page.waitForTimeout(500);

    // Candidates still there
    expect(await page.locator('text=→').count()).toBeGreaterThan(0);

    // No orphaned spinners
    await expect(page.locator('[class*="animate-pulse"]')).toHaveCount(0);

    // Back to dashboard
    await page.getByRole('link', { name: /dashboard/i }).click();
    await page.waitForURL('/');
    await expect(page.locator('text=Explorator')).toBeVisible();
  });

  test('12: view-state-consistency', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);

    // Count candidate cards using View Arrangements buttons (one per candidate)
    const realizeButtons = page.getByRole('button', { name: /view arrangements/i });
    const cardCount = await realizeButtons.count();
    expect(cardCount).toBeGreaterThan(0);

    // Check heading count matches
    const heading = page.locator('text=/\\d+ candidate/');
    const headingText = await heading.textContent() ?? '';
    const headingCount = parseInt(headingText.match(/(\d+)/)?.[1] ?? '0');
    expect(cardCount).toBe(headingCount);

    // Realize and go back
    await realizeFirstCandidate(page);
    await page.getByRole('button', { name: /back to progressions/i }).click();
    await page.waitForTimeout(500);

    // Candidates still present
    const allActionButtons = page.getByRole('button', { name: /view arrangements/i });
    expect(await allActionButtons.count()).toBe(cardCount);
    await expect(page.locator('[class*="animate-pulse"]')).toHaveCount(0);
  });

  test('13: interaction-affordances', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);

    // The session was created with a prompt, so auto-generate may fire.
    // Wait for candidates to appear (auto-generate) or for a settled state.
    const input = page.locator('input').first();

    // Wait for either candidates or the generate button to be available
    await page.locator('text=→').or(page.getByRole('button', { name: /generate/i })).first().waitFor({ timeout: 30_000 });

    // If candidates already exist (auto-generated), verify button is enabled
    const genButton = page.getByRole('button', { name: /generate/i });
    const hasCards = await page.locator('text=→').first().isVisible().catch(() => false);
    if (hasCards) {
      await expect(genButton).not.toBeDisabled();
    } else {
      // No auto-generate — test disabled state
      await input.fill('');
      await page.waitForTimeout(200);
      await expect(genButton).toBeDisabled();
      await input.fill(testSession.prompt);
      await genButton.click();
      await page.locator('text=→').first().waitFor({ timeout: 60_000 });
      await expect(genButton).not.toBeDisabled();
    }
  });
});
