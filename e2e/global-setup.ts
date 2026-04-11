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
    'npm', ['run', 'dev', '--', '--port', String(FRONTEND_PORT), '--strictPort'],
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

  await waitForHealth(`http://localhost:${FRONTEND_PORT}`);
  console.log('[e2e] Frontend ready');
}
