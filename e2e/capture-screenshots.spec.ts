/**
 * Capture README screenshots from the running dev stack.
 *
 * Drives the live dev frontend (default http://localhost:5173) through a real
 * session and saves PNGs into `docs/images/`. Uses real Gemini calls — the
 * dev backend's GEMINI_API_KEY supplies content.
 *
 * Pre-reqs (verified at start; script aborts if missing):
 *   - Neo4j dev container running on bolt://localhost:7688 (`make neo4j-up`)
 *   - Backend on http://localhost:8000 (`make backend`)
 *   - Frontend on http://localhost:5173 (`cd frontend && npm run dev`)
 *
 * Run from repo root:
 *   (cd e2e && npx playwright test ../scripts/capture-screenshots.spec.ts \
 *        --config capture.config.ts)
 */
import { test, expect, type Page } from '@playwright/test';
import { mkdirSync } from 'fs';
import path from 'path';

const FRONTEND = process.env.FRONTEND_URL ?? 'http://localhost:5173';
const BACKEND = process.env.BACKEND_URL ?? 'http://localhost:8000';
const OUT_DIR = path.resolve(__dirname, '..', 'docs', 'images');

const PROMPT = 'Late-night dream pop in A major, wistful and ethereal, 4 bars';
const RESEARCH_GENRE = `screenshot_genre_${Date.now()}`;

mkdirSync(OUT_DIR, { recursive: true });

async function shoot(page: Page, name: string, fullPage = false): Promise<void> {
  const file = path.join(OUT_DIR, `${name}.png`);
  await page.screenshot({ path: file, fullPage });
  console.log(`  saved ${path.relative(process.cwd(), file)}`);
}

/**
 * Drive the homepage flow (matches `happy-path` test #1) and wait for
 * generated candidates. Falls back to triggering generation manually if
 * the workspace's auto-generate doesn't kick in (race-prone in dev).
 */
async function createSessionViaApi(): Promise<string> {
  const res = await fetch(`${BACKEND}/v1/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    // `conservative` keeps n_candidates low (4) so real Gemini finishes in
    // ~30–60s rather than the 2–3 min for full_exploration's 12 candidates.
    body: JSON.stringify({ prompt: PROMPT, mode: 'conservative' }),
  });
  if (!res.ok) throw new Error(`createSession: ${res.status} ${await res.text()}`);
  const data = (await res.json()) as { session_id: string };
  return data.session_id;
}

async function openSessionAndGenerate(page: Page, sessionId: string): Promise<void> {
  // `networkidle` hangs because the workspace opens an SSE channel that
  // never goes quiet. `domcontentloaded` is enough — Playwright auto-waits
  // for selectors below.
  await page.goto(`${FRONTEND}/session/${sessionId}`, { waitUntil: 'domcontentloaded' });
  // Brief mount window so the prompt input populates before we look for cards
  await page.waitForTimeout(1500);

  // Auto-generate may or may not have fired; if no cards in 5s, push the
  // Generate button manually.
  const cardSelector = page.locator('text=→').first();
  const sawCards = await cardSelector.isVisible({ timeout: 5_000 }).catch(() => false);
  if (!sawCards) {
    const genButton = page.getByRole('button', { name: /^generate$/i });
    if (await genButton.isVisible().catch(() => false)) {
      await genButton.click();
    }
  }
  await cardSelector.waitFor({ timeout: 5 * 60 * 1000 });
  await page.waitForTimeout(800);
}

async function realizeAndBack(page: Page, idx: number): Promise<void> {
  const buttons = page.getByRole('button', { name: /view arrangements/i });
  await buttons.nth(idx).click();
  await page.locator('canvas').or(page.locator('text=Finalists')).first().waitFor({ timeout: 90_000 });
  await page.getByRole('button', { name: /back to progressions/i }).click();
  await page.waitForTimeout(600);
}

test('capture README screenshots', async ({ page }) => {
  test.setTimeout(15 * 60 * 1000); // 15-minute budget for real Gemini calls

  console.log(`frontend: ${FRONTEND}`);
  console.log(`backend:  ${BACKEND}`);
  console.log(`out:      ${OUT_DIR}\n`);

  // ── 1. Session workspace with generated progressions ────────────────────
  console.log('[1/4] Session workspace with generated progressions');
  const sessionId = await createSessionViaApi();
  console.log(`  session: ${sessionId}`);
  await openSessionAndGenerate(page, sessionId);
  await shoot(page, '01-session-workspace');

  // ── 2. Realized arrangement with piano roll ─────────────────────────────
  console.log('[2/4] Realized arrangement with piano roll');
  await page.getByRole('button', { name: /view arrangements/i }).first().click();
  await page.locator('canvas').first().waitFor({ timeout: 90_000 });
  await page.waitForTimeout(1500);
  await shoot(page, '02-realization-piano-roll');

  await page.getByRole('button', { name: /back to progressions/i }).click();
  await page.waitForTimeout(600);
  await realizeAndBack(page, 1);

  // ── 3. Comparison view ──────────────────────────────────────────────────
  console.log('[3/4] Comparison view');
  for (let i = 0; i < 2; i++) {
    const compareBtn = page.getByRole('button', { name: 'Compare', exact: true }).first();
    await compareBtn.click();
    await page.waitForTimeout(300);
  }
  await page.getByRole('button', { name: /compare \d+ candidates/i }).click();
  await expect(page.locator('text=COMPARING')).toBeVisible({ timeout: 30_000 });
  // Comparison view is an inline panel below the workspace. Wait for both
  // lane canvases to mount, then `clip` the page screenshot to the panel's
  // bounding box (top of COMPARING bar → bottom of last canvas).
  await page.locator('canvas').nth(1).waitFor({ timeout: 30_000 });
  await page.waitForTimeout(2000);
  const comparingBox = await page.locator('text=COMPARING').first().boundingBox();
  const lastCanvasBox = await page.locator('canvas').last().boundingBox();
  if (comparingBox && lastCanvasBox) {
    const top = Math.max(0, comparingBox.y - 12);
    const bottom = lastCanvasBox.y + lastCanvasBox.height + 24;
    await page.screenshot({
      path: path.join(OUT_DIR, '03-comparison-view.png'),
      fullPage: true,
      clip: { x: 0, y: top, width: 1440, height: bottom - top },
    });
    console.log('  saved docs/images/03-comparison-view.png');
  } else {
    console.log('  WARNING: bounding boxes missing — falling back to viewport');
    await shoot(page, '03-comparison-view');
  }

  // ── 4. Genre research progress view ─────────────────────────────────────
  // The progress view is a component-local state inside GenreManagement —
  // it only renders after clicking "Research New Genre" and submitting the
  // form, not by visiting `/genres` while a job runs in the background.
  console.log('[4/4] Genre research progress');
  await page.goto(`${FRONTEND}/genres`, { waitUntil: 'domcontentloaded' });
  await page.getByRole('button', { name: /research new genre/i }).click();
  await page.locator('input[placeholder*="Shoegaze"]').fill(RESEARCH_GENRE);
  await page.getByRole('button', { name: /start research/i }).click();

  // Progress view shows step labels (Research / Draft / Critique). Wait
  // for at least a few seconds of stage progress so the indicator looks
  // alive in the screenshot.
  await page.getByText('Research', { exact: true }).first().waitFor({ timeout: 30_000 });
  await page.waitForTimeout(5000);
  await shoot(page, '04-genre-research');

  console.log('\ndone');
});
