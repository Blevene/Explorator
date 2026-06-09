import { execSync } from 'child_process';
import { rmSync } from 'fs';
import path from 'path';

/**
 * Produce a clean frontend `dist` for `vite preview` to serve. Removes any
 * stale/partial dist from a prior interrupted build (vite preview would
 * otherwise silently serve whatever happens to be there), then rebuilds.
 *
 * Shared by BOTH global-setups — the parallel lane (per-worker preview servers)
 * and the Neo4j lane (single shared preview on :5199) — so neither ever serves
 * a stale or missing bundle after frontend edits.
 *
 * NOTE: this `rm -rf dist` + rebuild runs once per lane *process*, so under
 * `make e2e` the frontend is built twice (once per lane). That's intentional —
 * correctness over speed, each lane guarantees its own fresh bundle. The catch:
 * because it blows away `dist`, the two lanes MUST NOT run CONCURRENTLY — one
 * lane's `rm -rf dist` would yank the bundle out from under the other's running
 * `vite preview`. `make e2e` runs them SEQUENTIALLY (e2e-parallel, then
 * e2e-neo4j), so the double build is harmless there; only ad-hoc parallel
 * invocation would race.
 */
export function ensureFreshBuild(): void {
  const root = path.resolve(__dirname, '..');
  const frontend = path.join(root, 'frontend');
  console.log('[e2e] Removing stale frontend dist…');
  rmSync(path.join(frontend, 'dist'), { recursive: true, force: true });
  console.log('[e2e] Building frontend dist…');
  execSync('npm run build', { cwd: frontend, stdio: 'inherit' });
  console.log('[e2e] Frontend build complete.');
}

/**
 * Parallel lane setup: build the frontend once. Each Playwright worker then
 * serves this static `dist` via its own `vite preview` (see the `servers`
 * worker fixture in fixtures/test-fixtures.ts), pointed at that worker's own
 * in-memory backend. No shared backend / Neo4j is started here.
 */
export default async function globalSetup(): Promise<void> {
  ensureFreshBuild();
}
