import { spawn } from 'child_process';
import { readdirSync, unlinkSync, writeFileSync } from 'fs';
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

/**
 * Wipe research jobs and approved test genres from Neo4j AND the on-disk
 * catalog. Genre-research tests create jobs (`ambient_jazz`, `test_*`) and
 * the approve flow leaves a GenreProfile node in Neo4j *plus* YAML files
 * in `backend/src/explorator/domain/style/{genres,rules,grammars}/`.
 * Without this cleanup the duplicate-prevention check 409s on subsequent
 * runs and the polling loops time out (no `job_id`, no progression to
 * `pending_review`).
 *
 * NOTE: this is a stopgap. Real fix is to make the catalog directory
 * configurable so the approve endpoint writes to a temp dir under e2e
 * instead of mutating tracked source paths. Tracked separately.
 */
const GENRE_PROFILE_NAMES = ['ambient_jazz', 'test_review_genre', 'test_approve_genre', 'test_reject_genre', 'test_dup_genre'] as const;

// The exact YAML filenames the approve flow writes per genre name.
// Keep in sync with the genre-research approve endpoint.
const ARTIFACT_SUFFIXES_BY_DIR: Record<string, readonly string[]> = {
  genres: ['.yaml'],
  rules: ['_rules.yaml'],
  grammars: ['_grammar.yaml'],
};

export async function cleanGenreResearchState(): Promise<void> {
  // 1. Neo4j: research jobs + any test genre nodes
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
    proc.stderr?.on('data', (chunk) => { stderr += chunk.toString(); });
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

  // 2. Filesystem: YAMLs leaked by the approve endpoint. Allowlist the exact
  //    filenames each test genre would produce; never sweep by prefix (a real
  //    genre named `test_drum_machine` would not exist today, but defending
  //    against future foot-guns is cheaper than recovering from one).
  const styleRoot = path.join(ROOT, 'backend/src/explorator/domain/style');
  let deleted = 0;
  for (const [sub, suffixes] of Object.entries(ARTIFACT_SUFFIXES_BY_DIR)) {
    const dir = path.join(styleRoot, sub);
    let names: string[];
    try {
      names = readdirSync(dir);
    } catch (err) {
      // Only ENOENT is "fine" (dir doesn't exist on a fresh checkout);
      // anything else (perms, EIO) is a real problem worth surfacing.
      if ((err as NodeJS.ErrnoException).code === 'ENOENT') continue;
      throw err;
    }
    for (const name of names) {
      const matches = GENRE_PROFILE_NAMES.some((g) =>
        suffixes.some((s) => name === `${g}${s}`),
      );
      if (matches) {
        unlinkSync(path.join(dir, name));
        deleted += 1;
      }
    }
  }
  if (deleted > 0) {
    console.log(`[e2e] Removed ${deleted} stale test genre YAMLs from on-disk catalog`);
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
  // Clean stale genre-research state so the duplicate-prevention check in the
  // research API doesn't 409 on the second run of this suite.
  await cleanGenreResearchState();

  await waitForHealth(`http://localhost:${FRONTEND_PORT}`);
  console.log('[e2e] Frontend ready');
}
