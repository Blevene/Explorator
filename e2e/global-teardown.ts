import { readFileSync, unlinkSync } from 'fs';
import path from 'path';
import { cleanGenreResearchState, removeTempCatalog } from './global-setup';

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
    for (const [name, pid] of Object.entries(pids)) {
      try {
        process.kill(-(pid as number), 'SIGTERM');
        console.log(`[e2e] Killed ${name} (pid ${pid})`);
      } catch { /* already dead */ }
    }
    unlinkSync(PID_FILE);
  } catch { /* no PID file */ }

  removeTempCatalog();
}
