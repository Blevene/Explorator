import { test as base, type Page } from '@playwright/test';
import { spawn, type ChildProcess } from 'child_process';
import net from 'net';
import path from 'path';

/**
 * Two execution lanes, selected by E2E_PER_WORKER_BACKEND:
 *
 *  - unset  → SHARED lane: tests talk to the single backend/frontend that
 *    global-setup spawned on :8100/:5199 (Neo4j-backed). Run serially.
 *
 *  - "1"    → PER-WORKER lane: each Playwright worker (its own OS process)
 *    spawns its OWN backend in in-memory mode (NEO4J_URI unreachable) plus a
 *    frontend preview on worker-indexed ports. Zero shared state → safe to run
 *    fullyParallel. Used for generation/realization/UI specs that don't need
 *    durable learning features.
 *
 * Because Playwright workers are separate processes, a module-level `activeApiBase`
 * set by the worker-scoped fixture is worker-local — free helpers below read it
 * without threading the base through every call site.
 *
 * INVARIANT: every free helper that reads `activeApiBase` (createTestSession and
 * anything it calls) MUST run from within a test that uses the `servers` /
 * `testSession` fixture. Those fixtures are what assign `activeApiBase` to this
 * worker's actual backend; a helper invoked before either fixture has run (e.g.
 * from a bare `beforeAll` or top-level module code) would silently read the stale
 * SHARED-lane default and hit the wrong (or non-existent) backend.
 */
const PER_WORKER = process.env.E2E_PER_WORKER_BACKEND === '1';
const SHARED_BACKEND_PORT = 8100;
const SHARED_FRONTEND_PORT = 5199;
const ROOT = path.resolve(__dirname, '..', '..');

let activeApiBase = `http://localhost:${SHARED_BACKEND_PORT}/v1`;

export interface TestSession {
  sessionId: string;
  prompt: string;
}

interface WorkerServers {
  apiBase: string;
  frontendURL: string;
}

async function waitForHealth(url: string, timeoutMs = 90_000): Promise<void> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(url);
      if (res.ok) return;
    } catch { /* not ready */ }
    await new Promise((r) => setTimeout(r, 300));
  }
  throw new Error(`Health check failed: ${url} not ready after ${timeoutMs}ms`);
}

/**
 * Fast pre-flight: throw immediately if `port` is already bound (a leaked/stale
 * uvicorn or vite from a poisoned prior run). Without this, a busy port turns
 * into a slow death — vite --strictPort exits and uvicorn fails to bind, but the
 * subsequent waitForHealth would spin the full timeout before surfacing it.
 */
async function assertPortFree(port: number, label: string): Promise<void> {
  await new Promise<void>((resolve, reject) => {
    const sock = new net.Socket();
    const done = (err?: Error): void => {
      sock.removeAllListeners();
      sock.destroy();
      err ? reject(err) : resolve();
    };
    sock.setTimeout(500);
    // A successful connect means something is already listening → port busy.
    sock.once('connect', () => done(
      new Error(`Port ${port} (${label}) is already in use — a stale/leaked ` +
                `process is holding it. Kill it before re-running the e2e suite.`),
    ));
    // Connection refused (or any connect error) means the port is free.
    sock.once('error', () => done());
    sock.once('timeout', () => done());
    sock.connect(port, '127.0.0.1');
  });
}

function spawnBackend(port: number): ChildProcess {
  // Invoke the venv interpreter directly (not `uv run`) so concurrent workers
  // don't contend on uv's project lock.
  const python = path.join(ROOT, 'backend', '.venv', 'bin', 'python');
  return spawn(
    python, ['-m', 'uvicorn', 'explorator.api.app:create_app', '--factory',
             '--host', '0.0.0.0', '--port', String(port)],
    {
      cwd: path.join(ROOT, 'backend'),
      // NEO4J_URI points at a dead port → probe fails → in-memory mode.
      env: { ...process.env, GEMINI_MOCK: 'true', NEO4J_URI: 'bolt://localhost:9999' },
      stdio: 'ignore',
      detached: true,
    },
  );
}

function spawnFrontend(port: number, backendPort: number): ChildProcess {
  return spawn(
    'npm', ['run', 'preview', '--', '--port', String(port), '--strictPort'],
    {
      cwd: path.join(ROOT, 'frontend'),
      env: { ...process.env, VITE_API_TARGET: `http://localhost:${backendPort}` },
      stdio: 'ignore',
      detached: true,
    },
  );
}

/**
 * Tear down a detached child's whole process group. SIGTERM first, then await
 * the child's 'exit' (so we don't return while ports are still bound); if it
 * hasn't exited within `graceMs`, escalate to SIGKILL on the group. Best-effort:
 * a process that's already gone (ESRCH) is fine. `unref()` so a hung kill can
 * never keep this worker alive.
 */
async function killTree(proc: ChildProcess, graceMs = 5_000): Promise<void> {
  if (proc.pid === undefined) return;
  const pid = proc.pid;
  proc.unref();

  // Already exited? Nothing to do.
  if (proc.exitCode !== null || proc.signalCode !== null) return;

  const exited = new Promise<void>((resolve) => proc.once('exit', () => resolve()));

  try { process.kill(-pid, 'SIGTERM'); } catch { /* already gone */ return; }

  let timer: NodeJS.Timeout | undefined;
  const timedOut = new Promise<'timeout'>((resolve) => {
    timer = setTimeout(() => resolve('timeout'), graceMs);
    timer.unref();
  });

  const result = await Promise.race([exited.then(() => 'exited' as const), timedOut]);
  if (timer) clearTimeout(timer);

  if (result === 'timeout') {
    try { process.kill(-pid, 'SIGKILL'); } catch { /* already gone */ }
    // Give the group a brief moment to actually die after SIGKILL.
    await Promise.race([
      exited,
      new Promise<void>((resolve) => setTimeout(resolve, 1_000).unref()),
    ]);
  }
}

async function createTestSession(
  prompt = 'Dream pop in A major, wistful, 4 bars',
  genre = 'dream_pop',
): Promise<TestSession> {
  const res = await fetch(`${activeApiBase}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ genre, prompt, mode: 'full_exploration' }),
  });
  if (!res.ok) throw new Error(`Failed to create session: ${res.status}`);
  const data = await res.json();
  return { sessionId: data.session_id, prompt };
}

async function goToWorkspace(page: Page, sessionId: string): Promise<void> {
  await page.goto(`/session/${sessionId}`);
  await page.waitForLoadState('networkidle');
}

/**
 * Ensure candidates are generated. With auto-generate, navigating to a fresh
 * session starts generation automatically. This helper waits for that to finish,
 * or triggers generation manually if needed.
 */
async function generateCandidates(page: Page, prompt: string): Promise<void> {
  const genButton = page.getByRole('button', { name: /generate|running/i });
  const isRunning = await genButton.textContent().then(t => /running/i.test(t ?? '')).catch(() => false);

  if (!isRunning) {
    const hasCards = await page.locator('text=→').first().isVisible().catch(() => false);
    if (hasCards) return;

    const input = page.getByLabel('Generation prompt');
    await input.fill(prompt);
    await page.getByRole('button', { name: /generate/i }).click();
  }

  await page.locator('text=→').first().waitFor({ timeout: 60_000 });
}

async function realizeFirstCandidate(page: Page): Promise<void> {
  await page.getByRole('button', { name: /realize|view arrangements/i }).first().click();
  await page.locator('canvas').or(page.locator('text=Finalists')).first().waitFor({ timeout: 60_000 });
}

// Worker-scoped servers (per-worker memory backend, or the shared backend) +
// per-test session and baseURL wiring.
export const test = base.extend<
  { testSession: TestSession },
  { servers: WorkerServers }
>({
  servers: [async ({}, use, workerInfo) => {
    if (!PER_WORKER) {
      activeApiBase = `http://localhost:${SHARED_BACKEND_PORT}/v1`;
      await use({
        apiBase: activeApiBase,
        frontendURL: `http://localhost:${SHARED_FRONTEND_PORT}`,
      });
      return;
    }

    const idx = workerInfo.parallelIndex;
    const backendPort = 8200 + idx;
    const frontendPort = 5300 + idx;

    // Declared before the spawns so the finally can clean up whichever handle
    // exists if a later spawn or health check throws — otherwise the already-
    // spawned detached process leaks and poisons later runs by holding its port.
    let backend: ChildProcess | undefined;
    let frontend: ChildProcess | undefined;
    try {
      await assertPortFree(backendPort, 'backend');
      backend = spawnBackend(backendPort);
      await waitForHealth(`http://localhost:${backendPort}/v1/capabilities`);

      await assertPortFree(frontendPort, 'frontend');
      frontend = spawnFrontend(frontendPort, backendPort);
      await waitForHealth(`http://localhost:${frontendPort}`);

      activeApiBase = `http://localhost:${backendPort}/v1`;
      await use({ apiBase: activeApiBase, frontendURL: `http://localhost:${frontendPort}` });
    } finally {
      if (frontend) await killTree(frontend);
      if (backend) await killTree(backend);
    }
  }, { scope: 'worker' }],

  // Override Playwright's built-in baseURL with this worker's frontend.
  baseURL: async ({ servers }, use) => {
    await use(servers.frontendURL);
  },

  testSession: async ({ servers }, use) => {
    activeApiBase = servers.apiBase;
    const session = await createTestSession();
    await use(session);
  },
});

export { createTestSession, goToWorkspace, generateCandidates, realizeFirstCandidate };
export { expect } from '@playwright/test';
