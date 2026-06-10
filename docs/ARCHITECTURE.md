# Explorator — System Architecture

**Status:** current as of 2026-04-24 (post-M5d-3, pre-M6).

This document is the developer-onboarding reference for how Explorator is wired together today. For "what does the product do," see the [root README](../README.md). For per-milestone design history, see [`docs/superpowers/specs/`](./superpowers/specs/).

---

## Architectural style

A single-process FastAPI app driving a LangGraph orchestration engine, persisted to Neo4j when present, served to a React SPA. No microservices, no message queue, no separate OLTP database. The app is designed for one human operator per backend instance — the simplifying assumption that lets us treat Neo4j as authoritative for everything (sessions, candidates, lineage, feedback events, pattern library) without a relational adjunct.

Neo4j is **optional and auto-detected**. When it is reachable, behaviour is as described throughout this document. When it is not, the backend runs in a degraded "memory mode" that keeps generation fully working off an in-memory store and disables the long-term-memory features. See [Persistence backends](#persistence-backends) for the mechanism and the per-feature contract.

**Key principles:**

1. **Neo4j is the durable source of truth — when present.** All durable state lives in the graph. There is no PostgreSQL, no Redis, no S3. Exports land on the local filesystem. When Neo4j is absent, an ephemeral in-memory store backs the generation path only (see [Persistence backends](#persistence-backends)).
2. **LangGraph orchestrates; domain services are pure Python.** Generators, evaluators, and adapters know nothing about graph nodes or HTTP. LangGraph wires them together. FastAPI exposes them.
3. **Provenance is a first-class concern.** Every candidate carries its lineage (parent_candidate_id, mutation_op, session_id, round, family_id). The explanation, comparison, and export features all consume this lineage data.
4. **Append-only event logs + denormalized read caches.** User feedback events and pattern curation events are append-only. Where queries need fast scans (e.g., the `/patterns?curated_only=true` filter), we dual-write a denormalized property inside the same Neo4j transaction.
5. **SSE for live progress.** Long-running pipelines (generation, realization, genre research) stream node-level progress events to the frontend. The frontend uses these to drive progress bars, toasts, and step indicators.
6. **Server-side validation; client-side optimism.** Pydantic v2 validates every API boundary. The frontend optimistically updates Zustand stores on user action, then reconciles or rolls back when the API responds.

---

## High-level component diagram

```
                         ┌────────────────────────────────────────┐
                         │              Browser (React)            │
                         │  Vite dev server / npm run preview      │
                         │                                         │
                         │  Views ── Stores (Zustand)              │
                         │   │                                     │
                         │   └─→ /v1/* fetch + SSE                 │
                         │                                         │
                         │  Tone.js ──→ AudioContext (synthesis)   │
                         └────────────────────────────────────────┘
                                          │ HTTP / SSE
                                          ▼
        ┌─────────────────────────────────────────────────────────────┐
        │                      FastAPI app                             │
        │                                                              │
        │   ┌──────────────────────────────────────────────────┐       │
        │   │  Routes: sessions, realization, patterns,        │       │
        │   │          comparisons, export, feedback, genres,  │       │
        │   │          genre_research                          │       │
        │   └──────────────────────────────────────────────────┘       │
        │                       │                                      │
        │   ┌─────────────────────────────┐  ┌────────────────────┐   │
        │   │   LangGraph engine          │  │   Domain services   │   │
        │   │                             │  │                     │   │
        │   │   - exploration graph       │  │   - generators      │   │
        │   │   - realization sub-graph   │◄─┤   - evaluators      │   │
        │   │   - genre research sub-graph│  │   - mutators        │   │
        │   │                             │  │   - adapters        │   │
        │   └─────────────────────────────┘  └────────────────────┘   │
        │                       │                       │              │
        │                       ▼                       │              │
        │   ┌──────────────────────────────────────────┐              │
        │   │         graph repositories                │              │
        │   │   (one per Neo4j node label)              │              │
        │   └──────────────────────────────────────────┘              │
        │                       │                                      │
        └───────────────────────┼──────────────────────────────────────┘
                                │ Bolt
                                ▼
                ┌──────────────────────────────┐    ┌─────────────────┐
                │      Neo4j 5 (community)      │    │  Gemini API      │
                │  Sessions, candidates,        │    │  Pro: creative   │
                │  arrangements, scorecards,    │    │  Flash: tasks    │
                │  feedback events, pattern     │    │                  │
                │  library, genre profiles      │    │                  │
                └──────────────────────────────┘    └─────────────────┘
```

---

## Backend layout

```
backend/src/explorator/
├── api/                # FastAPI: routes, schemas, dependency-injection wiring, SSE
├── adapters/           # External-system clients: Gemini, music21, gemini_mock (E2E)
├── domain/             # Pure domain logic — no DB, no HTTP
│   ├── evaluation/     #   Voice leading, register, playability, groove, melody-harmony, theory scores
│   ├── export/         #   MIDI, JSON sidecar
│   ├── harmony/        #   Progression generator, mutator
│   ├── intent/         #   Prompt parser, feedback interpreter
│   ├── memory/         #   Pattern harvesting extractors (one per pattern type)
│   ├── realization/    #   Voicing, bass, groove, melody generators + arrangement assembler
│   └── style/          #   40+ genre YAMLs, validation schemas, loader
├── engine/             # LangGraph: state TypedDicts, nodes, graph definitions
├── graph/              # Neo4j repositories — one per node label (PatternLibraryRepo, FeedbackEventRepo, etc.)
├── models/             # Pydantic v2 — base entities, domain models, API request/response shapes
├── prompts/            # Centralized Gemini prompt templates (Markdown with {placeholder} interpolation)
└── services/           # Cross-cutting orchestration: pattern_library (harvest, curation), etc.
```

### Layer responsibilities

| Layer | Knows About | Does Not Know About |
|---|---|---|
| `api/` | HTTP, SSE, Pydantic schemas, DI | LangGraph internals, Cypher |
| `engine/` | LangGraph state, node ordering, sub-graph composition | HTTP, Cypher details |
| `graph/` | Cypher, Neo4j driver | LangGraph, Pydantic v2 (translates dicts) |
| `services/` | Multi-repo orchestration, transactions | HTTP, LangGraph |
| `domain/` | Pure music theory + algorithm logic | Anything I/O |
| `adapters/` | Gemini API, music21 library | Domain models (translates input/output) |

---

## Pipelines

Three LangGraph graphs compile at module load and are reused across requests:

### 1. Exploration graph (per generation round)

```
parse_intent           — Gemini Flash: prompt → structured SoftPreferences
load_genre_profile     — Neo4j read: genre YAML → in-memory profile
generate_progressions  — Gemini Pro: 4 chord-progression candidates
evaluate_progressions  — deterministic theory scores + Gemini Flash genre/mood/novelty
rank_progressions      — weighted aggregate, top-K selection
persist_progressions   — Neo4j write: ProgressionCandidate nodes + lineage
[round complete]       — SSE emits round_complete; frontend transitions to candidate cards
```

When a user submits feedback or selects a candidate to mutate, the next round re-enters this graph with adjusted weights and parent lineage.

### 2. Realization sub-graph (per candidate the user clicks Realize on)

```
load_realization_context  — fetch progression + genre profile
plan_voicings             — Gemini Flash: voicing strategy → music21 deterministically realizes named pitches
generate_bass             — genre templates × variant bass modes (supportive, pedal, syncopated)
generate_groove           — 5 archetypes (M5a)
generate_melody           — Gemini melodic strategy → deterministic realization (M5b)
assemble_arrangements     — cross-product of voicing variants × bass modes × grooves
evaluate_arrangements     — voice leading + register + playability + groove + melody-harmony
rank_and_select           — finalist roles: safest / best_loop / most_experimental
persist_realization       — Neo4j write: ArrangementCandidate + AggregateScorecard nodes
harvest_patterns          — extract 5 pattern rows per finalist into PatternLibraryEntry (M5d-1)
persist_round
```

`realize_subgraph` is a sub-graph compiled separately from the full exploration graph because the realize endpoint can run it standalone (for re-realization without re-generation).

### 3. Genre research sub-graph (M5c)

```
research      — Gemini Pro: musicological research → free-text research log
draft         — Gemini Flash: research log → GenreDraftResponse JSON (profile + rules + grammar)
critique      — Gemini Flash with fresh context: independent review → CritiqueResponse
[loop: refine ↔ critique up to 2 iterations if not passed]
validate      — deterministic Pydantic validation against the genre schema
[pending_review]  — user can approve or reject from the UI
[approve] writes the YAMLs to backend/src/explorator/domain/style/genres/
```

This produced 37+ of the 40 shipped genres.

---

## Data model (Neo4j)

### Top-level entity nodes

| Label | Holds | Linked from |
|---|---|---|
| `Session` | id, prompt, genre, mode, created_at | — |
| `ProgressionCandidate` | id, session_id, chord_symbols, family_id, parent_candidate_id, rationale, intent_tags, mutation_lineage_ids | `Session` |
| `ArrangementCandidate` | id, session_id, progression_candidate_id, voicing_plan_id, bass_line_id, groove_pattern_id, melodic_complement_id, weighted_total, rank_within_round, metadata.role | `ProgressionCandidate` (via `progression_candidate_id`) |
| `VoicingPlan` | id, voicing strategy, per-chord instructions, realized pitches | — |
| `BassLine` | id, mode, rhythm template, realized notes | — |
| `GroovePattern` | id, archetype, accents, swing | — |
| `MelodicComplement` | id, contour, range, realized melody | — |
| `AggregateScorecard` | id, candidate_id, weighted_total, per-dimension scores, evaluation lineage | `ProgressionCandidate` or `ArrangementCandidate` |
| `RomanNumeralAnalysis` | id, candidate_id, analysis_events (chord-by-chord) | `ProgressionCandidate` |
| `PatternLibraryEntry` | id, pattern_type, genre, source_candidate_id, abstracted_pattern, success_metrics, weighted_total, deleted_at, is_curated, curated_at | (denormalized linkage via `source_candidate_id`) |
| `UserFeedbackEvent` | id, session_id, candidate_id, feedback_type, content, interpreted_adjustments, weight_deltas | `Session` (`HAS_FEEDBACK`), arbitrary candidate (`ABOUT`) |
| `ObjectiveWeights` | id, profile_name, per-dimension weights, created_at | `Session` (per-session weight history) |
| `ComparisonView` | id, session_id, candidate_ids, comparison_axes, labels | `Session` |
| `ExportPackage` | id, session_id, manifest, file paths | `Session` |
| `GenreProfile` | id, genre, display_name, full YAML payload | — |
| `GenreResearchJob` | id, genre_name, status, research_log, draft_yamls, critique_trail | — |

### Key relationships

- `(Session)-[:HAS_FEEDBACK]->(UserFeedbackEvent)`
- `(UserFeedbackEvent)-[:ABOUT]->(ProgressionCandidate | ArrangementCandidate)`
- `(UserFeedbackEvent)-[:UPDATES]->(ObjectiveWeights)` (text-reaction events only — pattern_curation events use empty weight_deltas)
- Most parent/child relationships are denormalized as `parent_candidate_id` properties rather than edges; we use `MATCH ... WHERE n.parent_candidate_id = $pid` patterns. This is a deliberate simplification for the current scale.

### Indexes

Created at app startup (or via migration scripts in `backend/scripts/migrations/`):

- `pattern_library_sort_idx` on `PatternLibraryEntry(weighted_total, id)` — keyset pagination order key
- `user_feedback_event_type` on `UserFeedbackEvent(feedback_type, candidate_id)` — feedback queries by type
- Uniqueness constraint on `PatternLibraryEntry(source_candidate_id, pattern_type)` — natural key for upsert idempotence

### Soft-delete and curation invariants

- `PatternLibraryEntry.deleted_at` tombstones rows. `list_page` / `iter_all` / `get_by_id` filter `WHERE deleted_at IS NULL`. Re-harvest unconditionally clears `deleted_at` (resurrects the row).
- `is_curated` / `curated_at` are **excluded** from the upsert's `ON MATCH` clause via the `immutable_on_match` tuple, so re-harvest cannot wipe user curation. Tested explicitly in `test_upsert_on_match_preserves_curation_fields`.
- The `CURATION_FANOUT_CYPHER` query lives in `pattern_library_repo.py` as a module constant, shared by both `PatternLibraryRepo.toggle_curation` (standalone) and `curation_service.curate_arrangement` (transactional). Single Cypher string, two callers — eliminates drift risk.

---

## Persistence backends

Neo4j is optional. The backend selects between two persistence backends at startup based on whether Neo4j is reachable — there is exactly one branch point, so the rest of the codebase is backend-agnostic.

### Auto-detect at startup

`graph/connection.py` exposes `probe_driver()`: it creates the driver, verifies connectivity with a timeout, and returns the live `AsyncDriver` if reachable or `None` if not (any connection failure means "no Neo4j" — it never crashes startup). The FastAPI `lifespan` probes once and records the result on `app.state.persistence_mode` (`"neo4j"` or `"memory"`). In Neo4j mode it also initializes the schema and syncs genre profiles; in memory mode it logs a warning that long-term-memory features are disabled.

`GET /v1/capabilities` exposes the mode plus per-feature boolean flags (`durable_persistence`, `pattern_library`, `feedback_learning`, `session_history`, `lineage`, `genre_research`, `curation`) — all `false` in memory mode. The frontend reads this on boot to drive the limited-mode banner and hide/disable the unavailable surfaces.

### The `persistence/` package

`backend/src/explorator/persistence/` is the single place the "which backend?" decision lives:

- **`memory_store.py`** — a process-singleton `MemoryStore` (`label → {id → props}`). Stores `model_dump(mode="json")` dicts and returns deep copies, so reads match the deserialized shape the Neo4j repos already return. Not durable: data is lost on restart, by design.
- **`protocols.py`** — `typing.Protocol` contracts for the generation-path repos, so the factory's union return types stay checkable under mypy strict across both backends.
- **`memory_repos.py`** — in-memory repo implementations with **real** behaviour for the generation path (sessions, candidates, arrangements, scorecards, etc.). Because the engine and API share the `MemoryStore` singleton in one process, engine writes are visible to API reads — exactly the M1→M2 handoff generation needs.
- **`null_repos.py`** — no-op implementations for the learning/recall repos (pattern library, feedback events, objective weights, genre research, provenance, comparisons, explanations, exports/render artifacts). Reads return empties, writes are no-ops — so those endpoints return 200 with neutral data instead of 500.
- **`factory.py`** — `make_<repo>(driver)` helpers: `driver is None` selects the memory/null repo, otherwise the existing Neo4j repo. This is the **only** module that branches on driver presence; nothing else should.

Engine nodes and API dependencies accept `AsyncDriver | None` and resolve their repos through the factory rather than constructing `SessionRepository(driver)` (etc.) directly.

### Genres in memory mode

Genres are special: `StyleService.sync_genres_to_neo4j()` already reads genre YAML from disk and only *writes* to Neo4j. `StyleService` branches internally — in memory mode it serves `get_genre_profile` / `list_genres` straight from the YAML loader, so generation has full genre data with no database.

### Degradation contract

What "graceful" means per feature:

| Feature | Neo4j present | Neo4j absent (memory mode) |
|---|---|---|
| Session create/list | full | full (in-memory) |
| M1 generation + candidates | full | full |
| M2 realization + arrangements | full | full |
| M3 mutations | full | full |
| Genre profiles / rules | from Neo4j | from YAML |
| Feedback re-weighting (load_memory) | full | canonical default weights (no learning) |
| Pattern library (browse/harvest) | full | empty list / no-op harvest |
| Curation (star/unstar) | full | disabled in UI; API 200 no-op or 409 |
| Session history / provenance | full | empty timeline (hidden in UI) |
| Lineage tree | full | derived from candidate metadata only (hidden in UI) |
| Genre research jobs | full | empty / disabled in UI |
| Export | full | works (reads in-memory arrangements) |

---

## Cross-cutting concerns

### SSE (Server-Sent Events)

Long-running graph pipelines stream progress events to the frontend via `sse-starlette`. Each LangGraph node receives an `on_progress` callback in its state and emits structured events: `node_started`, `node_completed`, `round_complete`, etc. The frontend's `useSSEConsumer` hook subscribes per session and updates the relevant Zustand stores.

`sse-starlette` uses `\r\n` line endings (not `\n`) — frontend SSE parsing must use a regex split, not a literal `\n` split. (See `feedback_sse_crlf` memory.)

### Async transactions

The curation service is the canonical example: a single `async with driver.session()` opens a session, then `tx = await neo_session.begin_transaction()` opens a multi-statement transaction. All writes (event create, two relationship creates, fan-out SET) commit together or roll back together. The same pattern is used for session deletion (cascade across labels) and any other multi-write operation that needs atomicity.

### Authentication

There is no authentication. The app runs locally for one operator. Adding auth is deferred until there's a real reason (sharing, multi-tenancy, deployment beyond localhost).

### Configuration

Environment variables in `backend/.env`:

- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` — driver connection
- `GEMINI_API_KEY`, `GEMINI_PRO_MODEL`, `GEMINI_FLASH_MODEL` — Gemini integration
- `GEMINI_MOCK=true` — substitutes `FakeGeminiClient` for E2E. The Playwright global-setup sets this when spawning the backend.

The pytest suite ignores `NEO4J_URI` and uses `NEO4J_TEST_URI` (defaults to `bolt://localhost:7689`) — a separate Docker container with `tmpfs` storage and an autouse `MATCH (n) DETACH DELETE n` between tests. The dev DB on 7688 is never touched by tests.

---

## Frontend layout

See [`frontend/README.md`](../frontend/README.md) for the dev-side details. The high-level pieces:

```
src/views/
├── Dashboard               — session list, "new session" entry point
├── SessionWorkspace        — main flow: prompt → candidates → realization
├── PatternLibraryBrowser   — /patterns, with filters + curation
└── GenreManagement         — /genres, with research-agent UI

src/stores/
├── sessionStore            — current session + history
├── candidateStore          — progression candidates, finalSelection
├── arrangementStore        — arrangement summaries, selectedDetail, toggleCuration
├── audioStore              — single-arrangement playback transport
├── comparisonStore         — multi-arrangement playback (M4c)
├── patternLibraryStore     — list + cursor + toggleCuration fan-out
├── patternFiltersStore     — filter state (genre, type, curated_only)
└── genreResearchStore      — research jobs, drafts, approve/reject

src/services/
├── api.ts                  — top-level fetch wrappers + ArrangementSummary/Detail/etc. types
├── audioEngine.ts          — single-arrangement Tone.js synthesis
├── comparisonAudioEngine.ts — multi-track Tone.js with mute/solo
├── audioUtils.ts           — shared synth presets, scheduling helpers
└── midiUtils.ts            — MIDI download / blob handling
```

Each store follows the same shape: state fields, setters, and async actions that follow the optimistic-then-reconcile pattern. There's no global store composition — stores are independent and components subscribe à la carte via selectors.

---

## E2E architecture

`e2e/` is a separate npm package using Playwright. Three pieces:

- `playwright.config.ts` — single chromium project, fullyParallel: false, workers: 1 (tests aren't isolated enough for parallel). 60s test timeout, 10s expect timeout.
- `global-setup.ts` — spawns backend on :8100 with `GEMINI_MOCK=true` and frontend `npm run preview` on :5199. Cleans stale test sessions before tests run. PIDs go to `.server-pids.json`.
- `global-teardown.ts` — kills both processes.
- `fixtures/test-fixtures.ts` — re-exports Playwright's `test` with a `testSession` fixture that creates a session via API and tears it down after the test.

Tests live in `e2e/tests/<feature>.spec.ts`. The Playwright preview server reads `frontend/dist/` — so any frontend change requires `npm run build` before the next E2E run.

The mock `FakeGeminiClient` returns deterministic structured responses for the main flow but currently returns `"Mock text response"` for `generate_text` calls (used by the genre-research nodes). Four genre-research E2E tests fail because of this; fixing requires either prompt-discriminated JSON fixtures or a research-job cleanup step. Documented in the codebase, deferred.

---

## Operational notes

- **Dev workflow:** `make neo4j-up && make neo4j-test-up && make backend &` then `cd frontend && npm run dev`. Hit ctrl-C on backend to stop.
- **Migration scripts** live in `backend/scripts/migrations/`. They follow the M5d2/M5d3 pattern: idempotent, dry-run by default, `--yes` to apply. New ones get added per milestone.
- **Genre profiles** load lazily on first access — `domain/style/loader.py`. New genres dropped into `domain/style/genres/<name>.yaml` are picked up automatically; the genre research agent writes there directly when a draft is approved.
- **Local data** lives in the `neo4j_data` Docker volume (dev DB) and `tmpfs` (test DB, ephemeral). Wipe dev DB by `docker compose down -v`.

---

## Where to look next

- **Concrete user flow:** root [`README.md`](../README.md) → "A typical session"
- **Frontend UI grammar:** [`docs/DESIGN.md`](./DESIGN.md)
- **Per-milestone history:** [`docs/superpowers/specs/`](./superpowers/specs/) and [`docs/superpowers/plans/`](./superpowers/plans/)
- **Open issues:** GitHub issues #2 (cadence/loopability granularity), #3 (tension_curve dimension)
