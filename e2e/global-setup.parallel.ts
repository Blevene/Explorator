import { execSync } from 'child_process';
import { rmSync } from 'fs';
import path from 'path';

/**
 * Parallel lane setup: build the frontend once. Each Playwright worker then
 * serves this static `dist` via its own `vite preview` (see the `servers`
 * worker fixture in fixtures/test-fixtures.ts), pointed at that worker's own
 * in-memory backend. No shared backend / Neo4j is started here.
 */
export default async function globalSetup(): Promise<void> {
  const root = path.resolve(__dirname, '..');
  const frontend = path.join(root, 'frontend');
  // Remove any stale/partial dist from a prior interrupted build — vite preview
  // would otherwise silently serve whatever happens to be there.
  console.log('[e2e] Removing stale frontend dist…');
  rmSync(path.join(frontend, 'dist'), { recursive: true, force: true });
  console.log('[e2e] Building frontend dist for per-worker preview servers…');
  execSync('npm run build', { cwd: frontend, stdio: 'inherit' });
  console.log('[e2e] Frontend build complete.');
}
