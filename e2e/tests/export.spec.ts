import { test, expect, goToWorkspace, generateCandidates } from '../fixtures/test-fixtures';

test.describe('Export Modal', () => {
  test('export button opens modal', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);

    // Export button only appears when candidates exist
    const exportBtn = page.getByRole('button', { name: /^export$/i });
    await expect(exportBtn).toBeVisible();
    await exportBtn.click();

    // Verify modal opens with expected content
    await expect(page.getByText('Export Arrangements')).toBeVisible();
    await expect(page.getByText('Combined MIDI')).toBeVisible();
    await expect(page.getByText('JSON')).toBeVisible();
  });

  test('modal close button works', async ({ page, testSession }) => {
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);

    await page.getByRole('button', { name: /^export$/i }).click();
    await expect(page.getByText('Export Arrangements')).toBeVisible();

    // Click the close button (aria-label="Close", displays ✕)
    await page.getByRole('button', { name: 'Close' }).click();
    await expect(page.getByText('Export Arrangements')).not.toBeVisible();
  });
});
