import { test, expect } from '../fixtures/test-fixtures';

const API_BASE = 'http://localhost:8100/v1';

test.describe('Genre Research Agent (M5c)', () => {
  test('34: research-job-lifecycle', async ({ page }) => {
    // Navigate to genre management
    await page.goto('/genres');
    await page.waitForLoadState('networkidle');

    // Verify existing genres visible
    await expect(page.locator('text=Dream Pop')).toBeVisible({ timeout: 10_000 });

    // Start research
    await page.getByRole('button', { name: /research new genre/i }).click();
    await page.locator('input[placeholder*="Shoegaze"]').fill('ambient_jazz');
    await page.getByRole('button', { name: /start research/i }).click();

    // Verify progress view appears with step indicator. Match the exact
    // step-label text to avoid collisions with "Research New Genre" button
    // and "Genre library & research" heading.
    await expect(page.getByText('Research', { exact: true })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText('Draft', { exact: true })).toBeVisible();

    // Wait for job to complete (pending_review)
    await expect(page.locator('text=Ready for review').or(page.locator('text=Pending Review'))).toBeVisible({ timeout: 120_000 });
  });

  test('35: review-draft-content', async ({ page }) => {
    // Start a research job via API
    const startRes = await fetch(`${API_BASE}/genres/research`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ genre_name: 'test_review_genre', reference_artists: [] }),
    });
    const { job_id } = await startRes.json();

    // Poll until pending_review
    let status = 'researching';
    for (let i = 0; i < 60 && status !== 'pending_review' && status !== 'failed'; i++) {
      await page.waitForTimeout(2000);
      const pollRes = await fetch(`${API_BASE}/genres/research/${job_id}`);
      const job = await pollRes.json();
      status = job.status;
    }
    expect(status).toBe('pending_review');

    // Fetch draft detail
    const draftRes = await fetch(`${API_BASE}/genres/drafts/${job_id}`);
    const draft = await draftRes.json();

    // Verify all three YAML structures present
    expect(draft.draft_yamls).toBeDefined();
    expect(draft.draft_yamls.profile).toBeDefined();
    expect(draft.draft_yamls.profile.genre).toBe('test_review_genre');
    expect(draft.draft_yamls.rules).toBeDefined();
    expect(draft.draft_yamls.grammar).toBeDefined();

    // Verify research log and critique trail
    expect(draft.research_log).toBeTruthy();
    expect(draft.critique_trail).toBeDefined();
  });

  test('36: approve-flow', async ({ page }) => {
    // Start and wait for a research job via API
    const startRes = await fetch(`${API_BASE}/genres/research`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ genre_name: 'test_approve_genre', reference_artists: [] }),
    });
    const { job_id } = await startRes.json();

    let status = 'researching';
    for (let i = 0; i < 60 && status !== 'pending_review' && status !== 'failed'; i++) {
      await page.waitForTimeout(2000);
      const pollRes = await fetch(`${API_BASE}/genres/research/${job_id}`);
      const job = await pollRes.json();
      status = job.status;
    }
    expect(status).toBe('pending_review');

    // Approve
    const approveRes = await fetch(`${API_BASE}/genres/drafts/${job_id}/approve`, { method: 'POST' });
    expect(approveRes.ok).toBe(true);

    // Verify genre appears in list
    const genresRes = await fetch(`${API_BASE}/genres`);
    const genres = await genresRes.json();
    const names = genres.items.map((g: any) => g.genre);
    expect(names).toContain('test_approve_genre');
  });

  test('37: new-genre-usable-in-session', async ({ page }) => {
    // Verify the approved genre from test 36 is usable
    const genresRes = await fetch(`${API_BASE}/genres`);
    const genres = await genresRes.json();
    const hasGenre = genres.items.some((g: any) => g.genre === 'test_approve_genre');

    if (!hasGenre) {
      test.skip();
      return;
    }

    // Create a session with the new genre
    const sessionRes = await fetch(`${API_BASE}/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: 'Test approve genre in C major, 4 bars', mode: 'full_exploration' }),
    });
    expect(sessionRes.ok).toBe(true);
  });

  test('38: reject-flow', async ({ page }) => {
    const startRes = await fetch(`${API_BASE}/genres/research`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ genre_name: 'test_reject_genre', reference_artists: [] }),
    });
    const { job_id } = await startRes.json();

    let status = 'researching';
    for (let i = 0; i < 60 && status !== 'pending_review' && status !== 'failed'; i++) {
      await page.waitForTimeout(2000);
      const pollRes = await fetch(`${API_BASE}/genres/research/${job_id}`);
      const job = await pollRes.json();
      status = job.status;
    }
    expect(status).toBe('pending_review');

    // Reject with reason
    const rejectRes = await fetch(`${API_BASE}/genres/drafts/${job_id}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: 'Harmonic vocabulary too generic' }),
    });
    expect(rejectRes.ok).toBe(true);

    // Verify rejected
    const jobRes = await fetch(`${API_BASE}/genres/research/${job_id}`);
    const job = await jobRes.json();
    expect(job.status).toBe('rejected');
    expect(job.rejection_reason).toBe('Harmonic vocabulary too generic');

    // Verify not in genres list
    const genresRes = await fetch(`${API_BASE}/genres`);
    const genres = await genresRes.json();
    const names = genres.items.map((g: any) => g.genre);
    expect(names).not.toContain('test_reject_genre');
  });

  test('39: duplicate-prevention', async ({ page }) => {
    // Try to research an existing genre
    const res1 = await fetch(`${API_BASE}/genres/research`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ genre_name: 'dream_pop', reference_artists: [] }),
    });
    expect(res1.status).toBe(409);

    // Start a job, then try duplicate
    const res2 = await fetch(`${API_BASE}/genres/research`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ genre_name: 'test_dup_genre', reference_artists: [] }),
    });
    expect(res2.ok).toBe(true);

    const res3 = await fetch(`${API_BASE}/genres/research`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ genre_name: 'test_dup_genre', reference_artists: [] }),
    });
    expect(res3.status).toBe(409);
  });
});
