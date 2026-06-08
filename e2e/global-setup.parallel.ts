import { execSync } from 'child_process';
import path from 'path';

/**
 * Parallel lane setup: build the frontend once. Each Playwright worker then
 * serves this static `dist` via its own `vite preview` (see the `servers`
 * worker fixture in fixtures/test-fixtures.ts), pointed at that worker's own
 * in-memory backend. No shared backend / Neo4j is started here.
 */
export default async function globalSetup(): Promise<void> {
  const root = path.resolve(__dirname, '..');
  console.log('[e2e] Building frontend dist for per-worker preview servers…');
  execSync('npm run build', { cwd: path.join(root, 'frontend'), stdio: 'inherit' });
  console.log('[e2e] Frontend build complete.');
}
