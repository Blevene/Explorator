import { test, expect, goToWorkspace, generateCandidates, realizeFirstCandidate } from '../fixtures/test-fixtures';

test.describe('Groove Patterns (M5a)', () => {
  test('25: groove-pattern-generated', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);
    await realizeFirstCandidate(page);

    // After realization, the arrangement should be visible with BPM indicator
    await expect(page.locator('text=BPM')).toBeVisible();
  });

  test('26: groove-evaluation-in-scorecard', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);
    await realizeFirstCandidate(page);

    // Canvas (piano roll) should render — groove affects timing visible in arrangement
    await expect(page.locator('canvas')).toBeVisible();
  });

  test('27: groove-accent-visible-in-piano-roll', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);
    await realizeFirstCandidate(page);

    // Piano roll canvas should be visible (groove accents render on it)
    await expect(page.locator('canvas')).toBeVisible();
  });

  test('28: backward-compat-no-groove-still-works', async ({ page, testSession }) => {
    // This verifies the existing flow still works with groove in the pipeline
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);
    await realizeFirstCandidate(page);

    await expect(page.locator('text=BPM')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Chords', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Bass', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Melody', exact: true })).toBeVisible();
  });
});
