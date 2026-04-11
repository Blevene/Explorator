import { test, expect, goToWorkspace, generateCandidates, realizeFirstCandidate } from '../fixtures/test-fixtures';

test.describe('Audio & Feedback Integration', () => {
  test('17: audio-playback-controls', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);
    await realizeFirstCandidate(page);

    // Transport bar elements
    await expect(page.locator('text=BPM')).toBeVisible();
    await expect(page.locator('text=Vol')).toBeVisible();
    await expect(page.locator('button:has-text("V")')).toBeVisible();
    await expect(page.locator('button:has-text("B")')).toBeVisible();

    // Toggle voicing mute
    await page.locator('button:has-text("V")').click();
    await page.waitForTimeout(200);

    // Toggle bass mute
    await page.locator('button:has-text("B")').click();
    await page.waitForTimeout(200);

    // No JS errors should have occurred (Playwright captures uncaught)
  });

  test('18: feedback-affects-next-round', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);
    await realizeFirstCandidate(page);

    // Select arrangement
    await page.locator('[class*="cursor-pointer"]').filter({ hasText: /\d+\.\d/ }).first().click();

    // Submit feedback
    const feedbackInput = page.locator('input[placeholder*="experimental"]')
      .or(page.locator('input[placeholder*="more"]'));
    await feedbackInput.fill('prefer more loopable progressions');
    await page.getByRole('button', { name: /send/i }).click();
    await expect(page.locator('text=Understood')).toBeVisible({ timeout: 15_000 });

    // Back to progressions
    await page.getByText('Back to progressions').or(page.getByText('Back')).click();
    await page.waitForTimeout(500);

    // Generate round 2 with feedback applied
    await page.locator('input').first().fill('Continue with feedback applied');
    await page.getByRole('button', { name: /generate/i }).click();

    // Should complete without error
    await page.locator('text=→').first().waitFor({ timeout: 60_000 });
    await expect(page.locator('text=Error').first()).toBeHidden();
  });
});
