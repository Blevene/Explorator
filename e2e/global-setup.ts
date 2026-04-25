import { spawn } from 'child_process';
import { cpSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'fs';
import { tmpdir } from 'os';
import path from 'path';

const BACKEND_PORT = 8100;
const FRONTEND_PORT = 5199;
const ROOT = path.resolve(__dirname, '..');
const PID_FILE = path.join(__dirname, '.server-pids.json');
const STYLE_DIR_FILE = path.join(__dirname, '.style-dir.txt');

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

/**
 * Wipe research jobs and approved test genres from Neo4j.
 *
 * Test genres are written to a temp catalog directory (via
 * EXPLORATOR_STYLE_DIR set on the spawned backend), so disk leaks
 * disappear at teardown when we rm the temp dir. Neo4j leaks need
 * explicit cleanup since the dev-shared DB persists.
 */
export async function cleanGenreResearchState(): Promise<void> {
  const container = process.env.NEO4J_CONTAINER ?? 'explorator-neo4j-1';
  const queries = [
    'MATCH (n:GenreResearchJob) DETACH DELETE n',
    'MATCH (n) WHERE n.genre IS NOT NULL AND (n.genre =~ "test_.*" OR n.genre = "ambient_jazz") DETACH DELETE n',
  ];
  for (const cypher of queries) {
    const proc = spawn('docker', [
      'exec', '-i', container,
      'cypher-shell', '-u', 'neo4j', '-p', 'explorator_dev', '-d', 'neo4j',
      cypher,
    ], { stdio: ['ignore', 'ignore', 'pipe'] });
    let stderr = '';
    proc.stderr?.on('data', (chunk: Buffer) => { stderr += chunk.toString(); });
    const code = await new Promise<number | null>((resolve) =>
      proc.on('close', (c) => resolve(c)),
    );
    if (code !== 0) {
      console.warn(
        `[e2e] WARNING: cypher cleanup against container '${container}' exited ${code}. ` +
        `Set NEO4J_CONTAINER if your container name differs. stderr: ${stderr.trim()}`,
      );
    }
  }
}

/**
 * Stage a temp genre catalog and return its path. The spawned backend
 * is pointed at this dir via EXPLORATOR_STYLE_DIR, so the approve
 * endpoint writes test YAMLs *here* rather than mutating the
 * source-controlled `domain/style/` tree. The path is recorded in
 * .style-dir.txt for global-teardown to remove.
 */
function prepareTempCatalog(): string {
  const sourceCatalog = path.join(ROOT, 'backend/src/explorator/domain/style');
  const tmpRoot = mkdtempSync(path.join(tmpdir(), 'explorator-e2e-style-'));
  // Copy only the YAML-bearing subdirs — runtime ignores everything else, and
  // pulling in loader.py / __pycache__ / CLAUDE.md would just be noise.
  for (const sub of ['genres', 'rules', 'grammars']) {
    mkdirSync(path.join(tmpRoot, sub), { recursive: true });
    cpSync(path.join(sourceCatalog, sub), path.join(tmpRoot, sub), { recursive: true });
  }
  writeFileSync(STYLE_DIR_FILE, tmpRoot);
  return tmpRoot;
}

export default async function globalSetup() {
  const styleDir = prepareTempCatalog();
  console.log(`[e2e] Catalog staged at ${styleDir}`);

  console.log(`[e2e] Starting backend on port ${BACKEND_PORT} (GEMINI_MOCK=true)`);
  const backend = spawn(
    'uv', ['run', 'uvicorn', 'explorator.api.app:create_app', '--factory',
           '--host', '0.0.0.0', '--port', String(BACKEND_PORT)],
    {
      cwd: path.join(ROOT, 'backend'),
      env: {
        ...process.env,
        GEMINI_MOCK: 'true',
        EXPLORATOR_STYLE_DIR: styleDir,
      },
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
  // Wipe stale Neo4j research-job/genre nodes from the dev-shared DB.
  // (Disk catalog leaks are handled by the temp dir + teardown rm.)
  await cleanGenreResearchState();

  await waitForHealth(`http://localhost:${FRONTEND_PORT}`);
  console.log('[e2e] Frontend ready');
}

/**
 * Best-effort recovery of the temp catalog path written by setup, so
 * teardown can remove it. Returns null if the file is missing or
 * unreadable — teardown will warn rather than fail.
 */
export function readTempCatalogPath(): string | null {
  try {
    return readFileSync(STYLE_DIR_FILE, 'utf-8').trim() || null;
  } catch {
    return null;
  }
}

export function removeTempCatalog(): void {
  const dir = readTempCatalogPath();
  if (!dir) return;
  try {
    rmSync(dir, { recursive: true, force: true });
    rmSync(STYLE_DIR_FILE, { force: true });
    console.log(`[e2e] Removed temp catalog at ${dir}`);
  } catch (err) {
    console.warn(`[e2e] Could not remove temp catalog ${dir}:`, err);
  }
}
