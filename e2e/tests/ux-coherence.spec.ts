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
    await page.locator('input').first().fill('Navigation test, dream pop, 4 bars');
    await page.getByRole('button', { name: /generate/i }).click();
    await page.locator('text=→').first().waitFor({ timeout: 60_000 });

    // Realize
    await page.getByRole('button', { name: /realize/i }).first().click();
    await page.locator('canvas').or(page.locator('text=Finalists')).first().waitFor({ timeout: 60_000 });

    // Back to progressions — use specific button
    await page.getByRole('button', { name: /back to progressions/i }).click();
    await page.waitForTimeout(500);

    // Candidates still there
    expect(await page.locator('text=→').count()).toBeGreaterThan(0);

    // No orphaned spinners
    await expect(page.locator('[class*="animate-pulse"]')).toHaveCount(0);

    // Back to dashboard — use the header "Back" link
    await page.getByRole('link', { name: /back/i }).click();
    await page.waitForURL('/');
    await expect(page.locator('text=Explorator')).toBeVisible();
  });

  test('12: view-state-consistency', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);

    // Count candidate cards using Realize buttons (one per candidate)
    const realizeButtons = page.getByRole('button', { name: /realize/i });
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
    expect(await realizeButtons.count()).toBe(cardCount);
    await expect(page.locator('[class*="animate-pulse"]')).toHaveCount(0);
  });

  test('13: interaction-affordances', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);

    // The session was created with a prompt, so the input may already have text.
    // Clear it first to test the disabled state.
    const input = page.locator('input').first();
    await input.fill('');
    await page.waitForTimeout(200);

    const genButton = page.getByRole('button', { name: /generate/i });
    await expect(genButton).toBeDisabled();

    // Fill and generate
    await input.fill(testSession.prompt);
    await genButton.click();

    // With mock Gemini, generation is fast — the disabled state may flash by.
    // Just verify the end state: candidates appear and button is re-enabled.
    await page.locator('text=→').first().waitFor({ timeout: 60_000 });
    await expect(genButton).not.toBeDisabled();
  });
});
