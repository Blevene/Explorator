import { defineConfig } from '@playwright/test';

// Parallel lane. Each worker spawns its own in-memory backend + frontend (see
// the `servers` fixture), so tests are fully isolated and run in parallel.
process.env.E2E_PER_WORKER_BACKEND = '1';

export default defineConfig({
  testDir: './tests',
  // These need durable Neo4j-backed learning features and run serially in the
  // Neo4j lane (playwright.neo4j.config.ts):
  //   genre-research / pattern-library — gated off entirely in memory mode
  //   m3-features (feedback) / error-edge — poke learning/lineage surfaces
  // Everything else is generation / realization / UI and is memory-safe.
  testIgnore: [
    '**/genre-research.spec.ts',
    '**/pattern-library.spec.ts',
    '**/m3-features.spec.ts',
    '**/error-edge.spec.ts',
    // 2-lane comparison view doesn't fully come up under in-memory mode; runs
    // in the Neo4j lane where it passes.
    '**/comparison-playback.spec.ts',
  ],
  fullyParallel: true,
  workers: process.env.E2E_WORKERS ? Number(process.env.E2E_WORKERS) : 4,
  retries: process.env.CI ? 1 : 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  use: {
    // baseURL is set per-worker by the `servers` fixture.
    trace: 'on-first-retry',
    video: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  globalSetup: './global-setup.parallel.ts',
  projects: [
    { name: 'chromium', use: { browserName: 'chromium' } },
  ],
});
