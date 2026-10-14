# Contributing

This is a small, opinionated codebase. The conventions below aren't bureaucracy — they exist because we hit specific problems without them.

## Before you start

Read these once:

1. [`README.md`](./README.md) — what the system is, how to run it locally
2. [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) — current system architecture
3. [`docs/decisions/`](./docs/decisions/) — ADRs for the load-bearing decisions. If you're proposing something that contradicts one, that's the document to read first.
4. [`docs/DESIGN.md`](./docs/DESIGN.md) — frontend design language, if you're touching UI

## Local development

See [README § Quick start](./README.md#quick-start) for the bootstrap. The short form:

```bash
cp .env.example backend/.env  # set LLM_API_KEY (see README "LLM providers")
make neo4j-up                  # dev Neo4j on :7688 — returns once healthy
cd backend  && uv sync --all-extras && cd ..
cd frontend && npm install && cd ..
make backend                   # FastAPI on :8000 (terminal 1)
make frontend                  # Vite on :5173, /v1 proxied to :8000 (terminal 2)
```

- `make frontend` points the Vite proxy at `make backend` (:8000). Plain `npm run dev` proxies `/v1` to `VITE_API_TARGET`, which defaults to `http://localhost:8100` (the E2E backend).
- `backend/.env` holds only backend settings (`LLM_*`, legacy `GEMINI_*`, `NEO4J_*`, …); an unknown `LLM_*` / `GEMINI_*` key there stops startup (a typo could route your key to the wrong provider); other unknown keys, and misspelled-looking shell variables, only warn. `LLM_MOCK`, `OPENAI_API_KEY` and LLM-server variables such as `OLLAMA_CONTEXT_LENGTH` are read from the process environment only — export them or prefix the command.
- No LLM key? `LLM_MOCK=true make backend` swaps in a fake LLM client with deterministic output.
- The backend probes Neo4j once at startup; if it logs "In-memory mode", Neo4j wasn't ready — restart the backend.
- `make up` / `make down` run the whole stack in Docker instead (UI on :8080; see the README quick start). These are production-style images with no hot reload, so use them to check a clean build, not for day-to-day work. The backend container runs as your user and bind-mounts `backend/.env`, `backend/exports/` and the genre catalog. Docker and native therefore share settings, exports and approved genres, as well as the Neo4j volume.

Most backend tests need a separate Neo4j on :7689, and `make test` / `make test-integration` bring it up automatically. `make test-unit` and the frontend checks (`npm run lint`, `npm run test:unit`, `npm run build`) need no Docker. Before the first `make e2e*` run, install the E2E package and browser once: `cd e2e && npm install && npx playwright install --with-deps chromium`.

Optional: `uvx pre-commit install` mirrors CI's ruff / whitespace gates as local git hooks (see `.pre-commit-config.yaml`).

## Workflow conventions

The project follows a deliberate **brainstorm → spec → plan → execute → review** loop, particularly for feature-sized work. Historical artifacts live in [`docs/design/specs/`](./docs/design/specs/) and [`docs/design/plans/`](./docs/design/plans/) — read a few to get a feel for the shape before writing your own.

**For small fixes** (≤ a few hundred lines, no architectural change): a focused PR or direct commit to `main` with tests is fine. See e.g. commit `aa2f9ad` (test fixes) for the shape.

**For features**: brainstorm with the user / collaborator first → write a spec → write an implementation plan → execute the plan task-by-task → request review. See PR #5 (M5d-2), PR #8 (M5d-3) for examples.

### Branch / PR conventions

- Feature branches: `feature/<milestone-or-name>` (e.g. `feature/m5d3-pattern-curation`)
- Fix branches: `fix/<short-description>` (e.g. `fix/test-db-isolation`)
- Commit messages: `type(scope): subject`. Types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`. Scope is usually the milestone or subsystem (`feat(m5d-3)`, `fix(testing)`, `docs(architecture)`).
- We prefer **merge commits over squash** for feature branches — the per-task commits encode the TDD cadence and make bisecting easy. See PR #5 / PR #8 for the pattern.
- For tiny one-shot fixes, a direct commit to `main` is acceptable if the diff is small and self-contained.

## Code conventions

### Python (backend)

- **Python 3.13+.** Use modern syntax (`X | None`, not `Optional[X]`).
- **Pydantic v2** for all models. `BaseEntity` in `backend/src/explorator/models/base.py` is the canonical inheritance root for persistent domain entities — it carries `id`, `type`, `created_at`, `updated_at`, `version`, `status`, `metadata`.
- **Linting:** `make lint` runs `ruff check` and `mypy` strict. Both must pass before commit.
- **Tests:** `pytest`, `pytest-asyncio`. Strong preference for **integration tests against real Neo4j** for any code that touches Cypher — mocking the driver doesn't catch parameter binding or label-scoping bugs.
- **Test discipline:**
  - Unit tests: pure logic, no external systems. `backend/tests/unit/`.
  - Integration tests: hit the test Neo4j ([ADR-009](./docs/decisions/009-isolated-test-neo4j.md)). `backend/tests/integration/`.
  - API tests: hit the running FastAPI app with `httpx.AsyncClient` (not the sync `TestClient` — see `test_post_comparison_returns_201` history for why). `backend/tests/api/`.
  - Service tests: service-layer behaviour against the test Neo4j. `backend/tests/services/`.
- **Dependencies:** after changing `backend/pyproject.toml`, run `uv lock` and commit `backend/uv.lock`; CI installs with `uv sync --locked` and fails on a stale lock.
- **No mocking the database in integration tests.** (The cost of mock/prod divergence outweighs the cost of running tests against a real Neo4j.)

### TypeScript (frontend)

- **TypeScript 5 strict.** Run `npx tsc -b` in `frontend/` to verify (the root `tsconfig.json` only holds project references, so `tsc --noEmit` checks nothing); `npm run build` runs the same check, as CI does.
- **No central API client class** — each `frontend/src/api/<feature>.ts` exports plain async functions.
- **Stores are flat Zustand** — actions sit alongside state on a single `create<State>(set, get => ({...}))` call. No middleware unless we have a real reason.
- **Type mirrors** — when a backend Pydantic schema changes, update the matching TS interface in `api/types.ts` or `services/api.ts` in the same commit. The header docstring on `api/types.ts` notes the convention.
- **Optimistic UI with rollback** ([ADR-007](./docs/decisions/007-optimistic-ui-with-rollback.md)) is the pattern for any user action that hits the backend. Snapshot, optimistic update, reconcile / rollback. Toast on both paths.
- **Toasts via the wrapper** — import from `lib/toast`, never directly from `sonner`.
- **Palette via CSS custom properties** ([ADR-008](./docs/decisions/008-css-custom-properties-design-tokens.md)). Use `style={{ color: 'var(--accent-primary)' }}` rather than `text-amber-500`. Tailwind is for layout / spacing / typography only.
- **Tests:** vitest. Component tests via `@testing-library/react`. Store tests exercise actions in isolation. E2E tests live in `e2e/` (separate npm package).

### Both

- **TDD when implementing features**, especially the load-bearing invariants. Failing test first, watch it fail, implement, watch it pass, commit. The TDD cadence is visible in the commit history of feature branches (see PR #8 commits like `7611b7c`, `f2e289a`).
- **Don't add features, refactors, or abstractions beyond what the task requires.** A bug fix doesn't need surrounding cleanup. A one-shot operation doesn't need a helper.
- **Comment the WHY, not the WHAT.** If a comment explains what the code does, the code probably needs better names. Comment when the WHY is non-obvious — invariants, hidden constraints, workarounds for specific bugs.

## Where to put things

- **New backend feature?** Domain logic in `domain/`, repo methods in `graph/`, orchestration in `engine/nodes/` or `services/`, HTTP in `api/routes/`. See [ADR-002](./docs/decisions/002-langgraph-orchestration-pure-domain.md) for the boundaries.
- **New API endpoint with composite writes?** Use a service in `services/` that opens one Neo4j transaction. See [ADR-006](./docs/decisions/006-atomic-event-fan-out-one-transaction.md).
- **New event-log-able user action?** Reuse `UserFeedbackEvent` with a new `feedback_type` discriminator unless you have a strong reason for a new label. See [ADR-003](./docs/decisions/003-event-log-plus-denormalized-cache.md).
- **New frontend store?** Mirror the existing pattern (state + setters + async actions). See `patternLibraryStore.ts` for the canonical example.
- **New LLM prompt?** Markdown template in `backend/src/explorator/prompts/<area>/`. Centralized — never inline in node code. Prompts are provider-neutral (they run on Gemini and on OpenAI-compatible models).
- **New genre?** Add the profile, rules and grammar YAMLs under `backend/src/explorator/domain/style/{genres,rules,grammars}/` and restart the backend — genres are synced into Neo4j at startup. Or use the M5c research agent to generate one (approved drafts are written and synced immediately).
- **New ADR?** See [`docs/decisions/README.md`](./docs/decisions/README.md) for the one-line "what belongs here" rule.

## Things to avoid

- Skipping tests because "this is too simple to break" — the load-bearing tests in this codebase exist because of specific incidents.
- Bypassing pre-commit hooks (`--no-verify`) without a real reason.
- Adding optional fields with `?:` when the field is mandatory but nullable (use `T | null` instead). See [PR #8 review](./docs/design/plans/2026-04-24-m5d3-pattern-curation.md) for an example.
- Using Tailwind color classes for the app palette ([ADR-008](./docs/decisions/008-css-custom-properties-design-tokens.md)).
- Inline Cypher duplicated across two call-sites — extract to a module constant. See `CURATION_FANOUT_CYPHER` in `pattern_library_repo.py` for the pattern.
- Long-running transactions with slow operations inside. Probes that take more than a few ms should run outside the tx.

## Communication

- For feature-sized work, propose the spec (or a brainstorm summary) for review before writing the plan.
- For architecturally-significant decisions, write an ADR. The act of writing it forces clarity about consequences and revisit conditions.
- For incidents (test broke, deployment failed, data lost), a brief post-mortem in the commit message is appreciated. The specific commits referenced in this guide (`aa2f9ad`, `f2e289a`, `d8234f4`) follow this convention.

## Questions

If a convention here doesn't fit a specific case, deviate deliberately and document why in the commit message or PR description. Conventions exist to encode lessons; they shouldn't override judgment.
