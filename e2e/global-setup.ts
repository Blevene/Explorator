import { spawn } from 'child_process';
import { writeFileSync } from 'fs';
import path from 'path';

const BACKEND_PORT = 8100;
const FRONTEND_PORT = 5199;
const ROOT = path.resolve(__dirname, '..');
const PID_FILE = path.join(__dirname, '.server-pids.json');

async function waitForHealth(url: string, timeoutMs = 30_000): Promise<void> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(url);
      if (res.ok) return;
    } catch { /* not ready */ }
    await new Promise(r => setTimeout(r, 500));
  }
  throw new Error(`Health check failed: ${url} not ready after ${timeoutMs}ms`);
}

async function cleanTestSessions(): Promise<void> {
  try {
    const res = await fetch(`http://localhost:${BACKEND_PORT}/v1/sessions`);
    if (!res.ok) return;
    const data = await res.json();
    const sessions: { session_id: string }[] = data.items ?? data ?? [];
    for (const s of sessions) {
      await fetch(`http://localhost:${BACKEND_PORT}/v1/sessions/${s.session_id}`, {
        method: 'DELETE',
      });
    }
    if (sessions.length > 0) {
      console.log(`[e2e] Cleaned ${sessions.length} stale test sessions`);
    }
  } catch {
    // Backend not ready yet or no sessions — fine
  }
}

export default async function globalSetup() {
  console.log(`[e2e] Starting backend on port ${BACKEND_PORT} (GEMINI_MOCK=true)`);
  const backend = spawn(
    'uv', ['run', 'uvicorn', 'explorator.api.app:create_app', '--factory',
           '--host', '0.0.0.0', '--port', String(BACKEND_PORT)],
    {
      cwd: path.join(ROOT, 'backend'),
      env: { ...process.env, GEMINI_MOCK: 'true' },
      stdio: 'pipe',
      detached: true,
    },
  );
  backend.unref();

  console.log(`[e2e] Starting frontend on port ${FRONTEND_PORT}`);
  const frontend = spawn(
    'npm', ['run', 'preview', '--', '--port', String(FRONTEND_PORT), '--strictPort'],
    {
      cwd: path.join(ROOT, 'frontend'),
      env: { ...process.env, VITE_API_TARGET: `http://localhost:${BACKEND_PORT}` },
      stdio: 'pipe',
      detached: true,
    },
  );
  frontend.unref();

  writeFileSync(PID_FILE, JSON.stringify({
    backend: backend.pid,
    frontend: frontend.pid,
  }));

  await waitForHealth(`http://localhost:${BACKEND_PORT}/v1/sessions`);
  console.log('[e2e] Backend ready');

  // Clean stale sessions from prior test runs to avoid strict mode violations
  await cleanTestSessions();

  await waitForHealth(`http://localhost:${FRONTEND_PORT}`);
  console.log('[e2e] Frontend ready');
}
