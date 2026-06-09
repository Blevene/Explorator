import { readFileSync, unlinkSync } from 'fs';
import path from 'path';
import { cleanGenreResearchState, removeTempCatalog } from './global-setup';
import { killProcessGroup } from './fixtures/test-fixtures';

const PID_FILE = path.join(__dirname, '.server-pids.json');

export default async function globalTeardown() {
  // Wipe Neo4j leftovers (dev-shared DB persists between runs). The on-disk
  // catalog is the temp dir, removed below — no per-file cleanup needed any more.
  try {
    await cleanGenreResearchState();
  } catch (err) {
    console.warn(`[e2e] cleanGenreResearchState in teardown failed:`, err);
  }

  try {
    const pids = JSON.parse(readFileSync(PID_FILE, 'utf-8'));
    // Graceful-settle + SIGKILL-escalation per group (mirrors the parallel lane's
    // killTree). A bare SIGTERM returned immediately, so a back-to-back `make e2e`
    // could re-enter global-setup while vite's :5199 socket was still bound and
    // trip `--strictPort`. killProcessGroup waits for the group to actually die
    // (SIGKILL if it overstays) plus a short settle so the port is truly released.
    for (const [name, pid] of Object.entries(pids)) {
      await killProcessGroup(pid as number);
      console.log(`[e2e] Killed ${name} (pid ${pid})`);
    }
    unlinkSync(PID_FILE);
  } catch { /* no PID file */ }

  removeTempCatalog();
}
