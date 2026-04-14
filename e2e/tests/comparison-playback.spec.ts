import { test, expect, goToWorkspace, generateCandidates, realizeFirstCandidate } from '../fixtures/test-fixtures';

/**
 * Helper: select N candidates for comparison and open the comparison view.
 * Requires candidates to already be generated.
 */
async function openComparison(page: import('@playwright/test').Page, count = 2) {
  const compareButtons = page.getByRole('button', { name: 'Compare', exact: true })
  const buttonCount = await compareButtons.count()
  const toSelect = Math.min(count, buttonCount)

  for (let i = 0; i < toSelect; i++) {
    await compareButtons.nth(i).click()
    await page.waitForTimeout(200)
  }

  // Wait for comparison view to render
  await expect(page.locator('text=COMPARING')).toBeVisible({ timeout: 5_000 })
}

test.describe('Comparison Playback (M4c)', () => {
  test('21: comparison-transport-bar-renders', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId)
    await generateCandidates(page, testSession.prompt)

    // Need arrangements for comparison — realize first candidate
    await realizeFirstCandidate(page)
    await page.getByRole('button', { name: /back to progressions/i }).click()
    await page.waitForTimeout(500)

    await openComparison(page, 2)

    // Transport bar elements visible
    await expect(page.locator('text=COMPARING')).toBeVisible()
    await expect(page.locator('text=BPM')).toBeVisible()

    // Play button visible
    await expect(page.getByRole('button', { name: /play/i })).toBeVisible()
    // Stop button visible
    await expect(page.getByRole('button', { name: /stop/i })).toBeVisible()
  })

  test('22: lane-sidebars-with-solo-mute', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId)
    await generateCandidates(page, testSession.prompt)

    await realizeFirstCandidate(page)
    await page.getByRole('button', { name: /back to progressions/i }).click()
    await page.waitForTimeout(500)

    await openComparison(page, 2)

    // S and M buttons visible (one per lane)
    await expect(page.locator('button:text("S")').first()).toBeVisible()
    await expect(page.locator('button:text("M")').first()).toBeVisible()

    // Click solo on first lane — should highlight
    await page.locator('button:text("S")').first().click()
    await page.waitForTimeout(200)

    // Click mute on second lane — should dim
    await page.locator('button:text("M")').nth(1).click()
    await page.waitForTimeout(200)
  })

  test('23: close-comparison-stops-playback', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId)
    await generateCandidates(page, testSession.prompt)

    await realizeFirstCandidate(page)
    await page.getByRole('button', { name: /back to progressions/i }).click()
    await page.waitForTimeout(500)

    await openComparison(page, 2)

    // Close comparison
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
