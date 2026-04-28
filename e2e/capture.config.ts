/**
 * Playwright config for `capture-screenshots.spec.ts` only.
 *
 * Stripped-down version of `e2e/playwright.config.ts`:
 *   - No globalSetup/globalTeardown (we run against the live dev stack,
 *     not a freshly-spawned test backend).
 *   - Points testDir at this directory and matches the capture spec
 *     by filename.
 *   - Long per-test timeout because real Gemini calls take 30–90s each
 *     and the spec hits the API four times.
 */
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: '.',
  testMatch: /capture-screenshots\.spec\.ts$/,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 15 * 60 * 1000,
  expect: { timeout: 15_000 },
  use: {
    trace: 'off',
    video: 'off',
    screenshot: 'off',
  },
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
});
