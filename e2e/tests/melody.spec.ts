import { test, expect, goToWorkspace, generateCandidates, realizeFirstCandidate } from '../fixtures/test-fixtures';

/**
 * Helper: realize the Nth candidate and navigate back.
 */
async function realizeAndGoBack(page: import('@playwright/test').Page, index: number) {
  const realizeButtons = page.getByRole('button', { name: /view arrangements/i })
  await realizeButtons.nth(index).click()
  await page.locator('canvas').or(page.locator('text=Finalists')).first().waitFor({ timeout: 60_000 })
  await page.getByRole('button', { name: /back to progressions/i }).click()
  await page.waitForTimeout(500)
}

/**
 * Helper: select N candidates for comparison, then open comparison view.
 */
async function openComparison(page: import('@playwright/test').Page, count = 2) {
  for (let i = 0; i < count; i++) {
    const btn = page.getByRole('button', { name: 'Compare', exact: true }).first()
    await btn.click()
    await page.waitForTimeout(300)
  }
  const compareHeader = page.getByRole('button', { name: /compare \d+ candidates/i })
  await compareHeader.click()
  await expect(page.locator('text=COMPARING')).toBeVisible({ timeout: 30_000 })
}

test.describe('Melodic Complement (M5b)', () => {
  test('29: melody-mute-button-visible', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);
    await realizeFirstCandidate(page);

    // Transport bar should show all three track mute buttons
    await expect(page.getByRole('button', { name: 'Chords', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Bass', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Melody', exact: true })).toBeVisible();
  });

  test('30: melody-mute-toggle', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);
    await realizeFirstCandidate(page);

    const melodyBtn = page.getByRole('button', { name: 'Melody', exact: true });
    await expect(melodyBtn).toBeVisible();

    // Click to mute — button should visually change (opacity/color)
    await melodyBtn.click();
    await page.waitForTimeout(200);

    // Click again to unmute
    await melodyBtn.click();
    await page.waitForTimeout(200);

    // Button should still be there and functional
    await expect(melodyBtn).toBeVisible();
  });

  test('31: melody-in-comparison-view', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);

    // Realize at least 2 candidates for comparison
    await realizeAndGoBack(page, 0);
    await realizeAndGoBack(page, 1);
    await openComparison(page, 2);

    // Per-track mute buttons (V, B, M) should be visible in comparison lanes
    await expect(page.getByRole('button', { name: /mute voicing/i }).first()).toBeVisible();
    await expect(page.getByRole('button', { name: /mute bass/i }).first()).toBeVisible();
    await expect(page.getByRole('button', { name: /mute melody/i }).first()).toBeVisible();
  });

  test('32: melody-scores-in-comparison', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);

    await realizeAndGoBack(page, 0);
    await realizeAndGoBack(page, 1);
    await openComparison(page, 2);

    // Score comparison table should include melody dimensions
    await expect(page.locator('text=Melody Support')).toBeVisible();
    await expect(page.locator('text=Collision Risk')).toBeVisible();
  });

  test('33: piano-roll-renders-with-melody', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);
    await realizeFirstCandidate(page);

    // Piano roll canvas should render (melody notes contribute to MIDI range)
    await expect(page.locator('canvas')).toBeVisible();

    // BPM and all mute buttons confirm full realization pipeline ran
    await expect(page.locator('text=BPM')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Melody', exact: true })).toBeVisible();
  });
});
