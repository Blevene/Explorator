import { readFileSync, unlinkSync } from 'fs';
import path from 'path';

const PID_FILE = path.join(__dirname, '.server-pids.json');

export default async function globalTeardown() {
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
