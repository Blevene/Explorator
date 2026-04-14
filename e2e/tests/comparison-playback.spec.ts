import { test, expect, goToWorkspace, generateCandidates, realizeFirstCandidate } from '../fixtures/test-fixtures';

/**
 * Helper: realize the Nth candidate (0-indexed) by clicking its View Arrangements button.
 * Waits for canvas or Finalists to appear, then navigates back.
 */
async function realizeAndGoBack(page: import('@playwright/test').Page, index: number) {
  const realizeButtons = page.getByRole('button', { name: /view arrangements/i })
  await realizeButtons.nth(index).click()
  await page.locator('canvas').or(page.locator('text=Finalists')).first().waitFor({ timeout: 60_000 })
  await page.getByRole('button', { name: /back to progressions/i }).click()
  await page.waitForTimeout(500)
}

/**
 * Helper: select N candidates for comparison, then click the header "Compare" button
 * to open the comparison view. Candidates must already be generated.
 */
async function openComparison(page: import('@playwright/test').Page, count = 2) {
  // Click per-card "Compare" buttons to select candidates
  for (let i = 0; i < count; i++) {
    // Re-query each time since button text changes after click
    const btn = page.getByRole('button', { name: 'Compare', exact: true }).first()
    await btn.click()
    await page.waitForTimeout(300)
  }

  // Click the header "Compare N candidates" button to open the comparison view
  const compareHeader = page.getByRole('button', { name: /compare \d+ candidates/i })
  await compareHeader.click()

  // Wait for comparison view to render
  await expect(page.locator('text=COMPARING')).toBeVisible({ timeout: 15_000 })
}

test.describe('Comparison Playback (M4c)', () => {
  test('21: comparison-transport-bar-renders', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId)
    await generateCandidates(page, testSession.prompt)

    // Realize two candidates so comparison has arrangement data
    await realizeAndGoBack(page, 0)
    await realizeAndGoBack(page, 1)

    await openComparison(page, 2)

    // Transport bar elements visible
    await expect(page.locator('text=COMPARING')).toBeVisible()
    await expect(page.locator('text=BPM')).toBeVisible()

    // Play button visible (title attribute)
    await expect(page.getByRole('button', { name: /play/i })).toBeVisible()
    // Stop button visible
    await expect(page.getByRole('button', { name: /stop/i })).toBeVisible()
  })

  test('22: lane-sidebars-with-solo-mute', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId)
    await generateCandidates(page, testSession.prompt)

    await realizeAndGoBack(page, 0)
    await realizeAndGoBack(page, 1)

    await openComparison(page, 2)

    // S and M buttons visible (one per lane)
    await expect(page.locator('button:text("S")').first()).toBeVisible()
    await expect(page.locator('button:text("M")').first()).toBeVisible()

    // Click solo on first lane
    await page.locator('button:text("S")').first().click()
    await page.waitForTimeout(200)

    // Click mute on second lane
    await page.locator('button:text("M")').nth(1).click()
    await page.waitForTimeout(200)
  })

  test('23: close-comparison-stops-playback', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId)
    await generateCandidates(page, testSession.prompt)

    await realizeAndGoBack(page, 0)
    await realizeAndGoBack(page, 1)

    await openComparison(page, 2)

    // Close comparison via the X button
    await page.getByRole('button', { name: /close comparison/i }).click()
    await page.waitForTimeout(300)

    // Comparison view should be gone
    await expect(page.locator('text=COMPARING')).not.toBeVisible()
  })

  test('24: single-arrangement-playback-independent', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId)
    await generateCandidates(page, testSession.prompt)

    // Realize first candidate — single arrangement view
    await realizeFirstCandidate(page)

    // Single-arrangement transport should still work
    await expect(page.locator('text=BPM')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Chords', exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Bass', exact: true })).toBeVisible()
  })
})
