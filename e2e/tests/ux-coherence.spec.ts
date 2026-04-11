import { test, expect, goToWorkspace, generateCandidates, realizeFirstCandidate } from '../fixtures/test-fixtures';

test.describe('UX Coherence', () => {
  test('11: navigation-flow', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('text=Explorator')).toBeVisible();

    // Create session
    await page.locator('input').first().fill('Navigation test, dream pop, 4 bars');
    await page.getByRole('button', { name: /explore/i }).click();
    await page.waitForURL(/\/session\//);

    // Generate
    const promptInput = page.locator('input').first();
    await promptInput.fill('Navigation test, dream pop, 4 bars');
    await page.getByRole('button', { name: /generate/i }).click();
    await page.locator('text=→').first().waitFor({ timeout: 30_000 });

    // Realize
    await page.getByRole('button', { name: /realize/i }).first().click();
    await page.locator('canvas').or(page.locator('text=Finalists')).first().waitFor({ timeout: 30_000 });

    // Back to progressions
    await page.getByText('Back to progressions').or(page.getByText('Back')).click();
    await page.waitForTimeout(500);

    // Candidates still there
    expect(await page.locator('text=→').count()).toBeGreaterThan(0);

    // No orphaned spinners
    await expect(page.locator('[class*="animate-pulse"]')).toHaveCount(0);

    // Back to dashboard
    await page.getByText('Back').first().click();
    await page.waitForURL('/');
    await expect(page.locator('text=Explorator')).toBeVisible();
  });

  test('12: view-state-consistency', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);

    // Count heading
    const heading = page.locator('text=/\\d+ candidate/');
    const headingText = await heading.textContent() ?? '';
    const headingCount = parseInt(headingText.match(/(\d+)/)?.[1] ?? '0');

    // Count actual cards
    const cards = page.locator('text=→');
    expect(await cards.count()).toBe(headingCount);

    // Realize and go back
    await realizeFirstCandidate(page);
    await page.getByText('Back to progressions').or(page.getByText('Back')).click();
    await page.waitForTimeout(500);

    // Candidates still present
    expect(await page.locator('text=→').count()).toBe(headingCount);
    await expect(page.locator('[class*="animate-pulse"]')).toHaveCount(0);
  });

  test('13: interaction-affordances', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);

    // Generate button disabled when empty
    const genButton = page.getByRole('button', { name: /generate/i });
    await expect(genButton).toBeDisabled();

    // Fill and generate
    await page.locator('input').first().fill(testSession.prompt);
    await genButton.click();

    // While running: button + input disabled
    await expect(genButton).toBeDisabled();

    // Wait for completion
    await page.locator('text=→').first().waitFor({ timeout: 30_000 });

    // After: button re-enabled
    await expect(genButton).not.toBeDisabled();
  });
});
