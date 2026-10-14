import { defineConfig } from '@playwright/test';

// Serial Neo4j lane. Reuses the single shared backend/frontend that global-setup
// spawns on :8100/:5199 (Neo4j-backed). For the specs that need durable
// learning features (pattern library, genre research) or poke feedback/lineage.
// Runs against the disposable test Neo4j (:7689, `make neo4j-test-up`), because
// setup deletes every session and research job; never point it at the dev DB.
const FRONTEND_PORT = 5199;

export default defineConfig({
  testDir: './tests',
  testMatch: [
    '**/genre-research.spec.ts',
    '**/pattern-library.spec.ts',
    '**/m3-features.spec.ts',
  ],
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: `http://localhost:${FRONTEND_PORT}`,
    trace: 'on-first-retry',
    video: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  globalSetup: './global-setup.ts',
  globalTeardown: './global-teardown.ts',
  projects: [
    { name: 'chromium', use: { browserName: 'chromium' } },
  ],
});
