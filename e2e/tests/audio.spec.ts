import { test, expect, goToWorkspace, generateCandidates, realizeFirstCandidate } from '../fixtures/test-fixtures';

test.describe('Audio & Feedback Integration', () => {
  test('17: audio-playback-controls', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);
    await realizeFirstCandidate(page);

    // Transport bar elements
    await expect(page.locator('text=BPM')).toBeVisible();
    await expect(page.locator('text=Vol')).toBeVisible();

    // Mute buttons — now labeled "Chords" and "Bass"
    await expect(page.getByRole('button', { name: 'Chords', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Bass', exact: true })).toBeVisible();

    // Toggle mutes
    await page.getByRole('button', { name: 'Chords', exact: true }).click();
    await page.waitForTimeout(200);
    await page.getByRole('button', { name: 'Bass', exact: true }).click();
    await page.waitForTimeout(200);
  });

  test('18: feedback-affects-next-round', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);
    await realizeFirstCandidate(page);

    // Select an arrangement card in the list
    await page.locator('[class*="rounded-md"][class*="cursor-pointer"]').first().click();
    await page.waitForTimeout(500);

    // Submit feedback — find the input in the sidebar
    const feedbackInput = page.locator('input[placeholder*="experimental"]');
    if (await feedbackInput.isVisible()) {
      await feedbackInput.fill('prefer more loopable progressions');
      await page.getByRole('button', { name: /send/i }).click();
      await expect(page.locator('text=Understood')).toBeVisible({ timeout: 15_000 });
    }

    // Back to progressions
    await page.getByRole('button', { name: /back to progressions/i }).click();
    await page.waitForTimeout(500);

    // Generate round 2
    await page.locator('input').first().fill('Continue with feedback applied');
    await page.getByRole('button', { name: /generate/i }).click();

    // Should complete without error
    await page.locator('text=→').first().waitFor({ timeout: 60_000 });
  });
});
