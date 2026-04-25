import { readFileSync, unlinkSync } from 'fs';
import path from 'path';
import { cleanGenreResearchState } from './global-setup';

const PID_FILE = path.join(__dirname, '.server-pids.json');

export default async function globalTeardown() {
  // Clean leaked test artifacts before stopping the backend, so anyone running
  // tests outside our setup script (e.g. `git status` after a successful run)
  // doesn't see the YAML/Neo4j leftovers. global-setup also cleans on start
  // for safety against abnormal exits — the two together make the suite
  // idempotent regardless of how the previous run ended.
  try {
    await cleanGenreResearchState();
  } catch (err) {
    console.warn(`[e2e] cleanGenreResearchState in teardown failed:`, err);
  }

  try {
    const pids = JSON.parse(readFileSync(PID_FILE, 'utf-8'));
    for (const [name, pid] of Object.entries(pids)) {
      try {
        process.kill(-(pid as number), 'SIGTERM');
        console.log(`[e2e] Killed ${name} (pid ${pid})`);
      } catch { /* already dead */ }
    }
    unlinkSync(PID_FILE);
  } catch { /* no PID file */ }
}
