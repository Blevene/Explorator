# Explorator — System Architecture

**Status:** current as of 2026-10 (post-M5d, configurable LLM provider; pre-M6).

This document is the developer-onboarding reference for how Explorator is wired together today. For "what does the product do," see the [root README](../README.md). For per-milestone design history, see [`docs/design/specs/`](./design/specs/).

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
                ┌──────────────────────────────┐    ┌─────────────────────┐
                │      Neo4j 5 (community)      │    │  LLM provider        │
                │  Sessions, candidates,        │    │  (Gemini or OpenAI-  │
                │  arrangements, scorecards,    │    │   compatible)        │
                │  feedback events, pattern     │    │  Pro: creative       │
                │  library, genre profiles      │    │  Flash: tasks        │
                └──────────────────────────────┘    └─────────────────────┘
```

---

## Backend layout

```
backend/src/explorator/
├── api/                # FastAPI: routes, schemas, dependency-injection wiring, SSE
├── adapters/           # LLMClient protocol (llm.py) + Gemini / OpenAI-compatible clients, structured-output parsing, token usage, FakeLLMClient (llm_mock, E2E), music21
├── domain/             # Pure domain logic — no DB, no HTTP
│   ├── evaluation/     #   Voice leading, register, playability, groove, melody-harmony, theory scores
│   ├── export/         #   MIDI, JSON sidecar
│   ├── harmony/        #   Progression generator, mutator
│   ├── intent/         #   Prompt parser, feedback interpreter
│   ├── memory/         #   Pattern harvesting extractors (one per pattern type)
│   ├── realization/    #   Voicing, bass, groove, melody generators + arrangement assembler
│   └── style/          #   39 genre YAMLs, validation schemas, loader
├── engine/             # LangGraph: state TypedDicts, nodes, graph definitions
├── graph/              # Neo4j repositories — one per node label (PatternLibraryRepo, FeedbackEventRepo, etc.)
├── models/             # Pydantic v2 — base entities, domain models, API request/response shapes
├── prompts/            # Centralized LLM prompt templates (Markdown with {placeholder} interpolation)
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
| `adapters/` | LLM providers (via `LLMClient`), music21 library | Domain models (translates input/output) |

---

## Pipelines

Three LangGraph graphs, each built and compiled per request by its route (`build_exploration_graph` in `engine/graph.py`, `build_realization_subgraph` in the same file, `build_genre_research_graph` in `engine/genre_research_graph.py`). Persist nodes write to Neo4j, or to the in-memory store in memory mode.

### 1. Exploration graph (per generation round, `POST /sessions/{id}/rounds`)

One round runs M1 generation and M2 realization end to end:

```
parse_intent             — LLM flash: prompt → structured SoftPreferences
load_genre               — genre profile (Neo4j, or YAML in memory mode)
load_memory              — session objective weights (feedback re-weighting, M3b)
generate                 — LLM pro: 8 chord-progression candidates
evaluate_progressions    — deterministic theory scores + LLM flash genre/mood/novelty
select_top_progressions  — weighted aggregate, top-3 go on to realization
load_context             ┐
plan_voicings            │
generate_bass            │  the M2 realization nodes (see 2. below)
generate_groove          │
generate_melody          │
assemble                 │
evaluate_arrangements    │
rank_and_select          ┘
check_stop               — stop condition met? → persist_realization, else → mutate (M3a loop, max_rounds=2)
mutate                   — harmonic scope → evaluate_progressions; arrangement scope → evaluate_arrangements
persist_realization      — write ArrangementCandidate + AggregateScorecard nodes
harvest_patterns         — extract 5 pattern rows per finalist into PatternLibraryEntry (M5d-1)
persist_round            — write the round; SSE emits round_completed
```

User-initiated mutations (`POST /sessions/{id}/mutate`) do not re-enter this graph: the route runs `HarmonyMutator` on each selected candidate, then the realization sub-graph on the children. Feedback (`POST /sessions/{id}/feedback`) records an event and updates the session weights, which the next round's `load_memory` node applies.

### 2. Realization sub-graph

```
load_context            — fetch progression + genre profile
plan_voicings           — LLM flash: voicing strategy → music21 deterministically realizes named pitches
generate_bass           — genre templates × variant bass modes (supportive, pedal, syncopated)
generate_groove         — 5 archetypes (M5a)
generate_melody         — LLM melodic strategy → deterministic realization (M5b)
assemble                — cross-product of voicing plans × bass lines; groove patterns and melodic complements assigned round-robin
evaluate_arrangements   — voice leading + register + playability + groove + melody-harmony
rank_and_select         — finalist roles: safest / best_loop / most_experimental
persist_realization     — write ArrangementCandidate + AggregateScorecard nodes; SSE emits realization_completed
```

`build_realization_subgraph` runs these nodes on their own. It is used by `POST /sessions/{id}/realization-rounds` (on-demand realization of a candidate that has no arrangements yet) and by `/mutate` for mutated children. It does not harvest patterns.

### 3. Genre research sub-graph (M5c)

```
research      — LLM pro: musicological research → free-text research log
draft         — LLM flash: research log → GenreDraftResponse JSON (profile + rules + grammar)
critique      — LLM flash with fresh context: independent review → CritiqueResponse
refine        — LLM flash: revise the draft from the critique
[loop: refine ↔ critique up to 2 iterations if not passed]
validate      — deterministic Pydantic validation against the genre schema
output        — store the draft on the job, status pending_review
[pending_review]  — user can approve or reject from the UI
[approve] writes profile/rules/grammar YAMLs to domain/style/{genres,rules,grammars}/ and syncs them to Neo4j
```

This produced 36 of the 39 shipped genres.

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

Created at app startup by `init_schema` (`graph/schema.py`), among others:

- `pattern_library_genre`, `pattern_library_genre_type`, `pattern_library_weighted_total` on `PatternLibraryEntry`
- `pattern_library_natural_key` — uniqueness constraint on `PatternLibraryEntry(source_candidate_id, pattern_type)`, the natural key for upsert idempotence

Migration-only (run once from `backend/scripts/migrations/`):

- `pattern_library_sort_idx` on `PatternLibraryEntry(weighted_total, id)` — keyset pagination order key (m5d2)
- `user_feedback_event_type` on `UserFeedbackEvent(feedback_type, candidate_id)` — feedback queries by type (m5d3)

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

Long-running graph pipelines stream progress events to the frontend via `sse-starlette`. Each LangGraph node receives an `on_progress` callback in its state and emits structured events: `node_started`, `node_completed`, `candidates_preview`, `token_usage`, `pattern_harvest`, the terminal `round_completed` / `realization_completed` / `mutation_completed`, and `round_error` / `realization_error` / `mutation_error`. Genre research streams `genre_research` events. Each trigger endpoint returns its own SSE stream; the frontend reads it with `hooks/streamSSE.ts` inside `useGenerationFlow`, `useRealizationFlow` and `useMutationFlow`, which update the relevant Zustand stores.

`sse-starlette` uses `\r\n` line endings (not `\n`) — frontend SSE parsing must use a regex split, not a literal `\n` split (see `hooks/streamSSE.ts`).

### Async transactions

The curation service is the canonical example: a single `async with driver.session()` opens a session, then `tx = await neo_session.begin_transaction()` opens a multi-statement transaction. All writes (event create, two relationship creates, fan-out SET) commit together or roll back together. The same pattern is used for session deletion (cascade across labels) and any other multi-write operation that needs atomicity.

### Token usage instrumentation

LLM token consumption is measured at the adapter choke point and surfaced live to the operator (ADR 011). `adapters/usage.py` holds a `UsageAccumulator` (by-model + by-phase breakdowns and an estimated cost) behind a `ContextVar`. Each adapter (`gemini.py`, `openai_compat.py`) records provider usage after each call, and nodes that fall back to defaults after an LLM failure call `usage.record_fallback(node)`; `engine/graph.py` wraps every node with `_instrument(name, fn)`, which tags the active phase and emits a live `token_usage` SSE event as the round's cumulative total grows. The round route opens the scope around `graph.ainvoke` and always emits a terminal `token_usage` — even on failure, since the tokens were billed. Because `contextvars` copy by reference into asyncio child tasks, the parallel `evaluate_progressions` fan-out aggregates into the one accumulator without any per-call plumbing.

The frontend stores live + committed usage (`candidateStore`) and renders `TokenUsagePanel`: round headline (tokens + estimated cost), an expandable per-phase breakdown, and a per-session footer (resets on reload — not persisted). Cost is computed from configurable per-tier rates and labeled an estimate, or shown as "not priced" when no `LLM_PRICE_*` rates apply; a fallback badge lists the nodes that defaulted; mock-mode numbers are flagged `is_synthetic` and badged.

**Measured example** — a real `dream_pop` round consumed ~13,900 tokens (~7.6k in / 6.3k out), ~$0.022 estimated, across 21 calls (20 Flash + 1 Pro). Distribution by phase: `plan_voicings` ~64%, `generate_melody` ~15%, `evaluate_progressions` ~14%, `generate` (the single Pro call) ~5%, `parse_intent` ~1%. The cost lever is `plan_voicings`, not the Pro-tier progression generation.

### Authentication

There is no authentication. The app runs locally for one operator. Adding auth is deferred until there's a real reason (sharing, multi-tenancy, deployment beyond localhost).

### Configuration

`backend/.env` is read by the `Settings` class (`config.py`), which uses only its own fields. `check_setting_names()` runs first: an unknown `LLM_*` / `GEMINI_*` key in `backend/.env` is fatal (a misspelt `LLM_PROVIDER` would otherwise leave Gemini selected and send the key to Google); other unknown keys, and shell variables that closely match a setting name, are logged as warnings at startup. Settings (from `backend/.env` or the process environment):

- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` — driver connection
- `LLM_PROVIDER` (`gemini` default or `openai`), `LLM_API_KEY`, `LLM_PRO_MODEL`, `LLM_FLASH_MODEL`, `LLM_TIMEOUT_SECONDS`; openai only: `LLM_BASE_URL`, `LLM_MAX_RETRIES`, `LLM_MAX_CONCURRENCY`, `LLM_CONTEXT_TOKENS`, `LLM_EXTRA_BODY` — LLM integration; full reference in README "LLM providers" and ADR 012. The legacy `GEMINI_*` names are deprecated aliases honoured only under `gemini`.
- `LLM_PRICE_PRO_INPUT`, `LLM_PRICE_PRO_OUTPUT`, `LLM_PRICE_FLASH_INPUT`, `LLM_PRICE_FLASH_OUTPUT` — USD per 1M tokens, used for the token-usage cost *estimate* (defaults: pro 1.25 / 10.0, flash 0.30 / 2.50). Tune to your billing tier; non-Gemini providers show "not priced" unless set.
- `EXPORT_DIR` — MIDI/JSON export root (default `exports`, relative to the backend working directory, i.e. `backend/exports`).

Process environment only (export them or prefix the command — never put them in `backend/.env`):

- `LLM_MOCK=true` — substitutes `FakeLLMClient` (deterministic output, no key or endpoint needed). The Playwright setups set it when spawning backends; for a manual no-key run use `LLM_MOCK=true make backend`. The deprecated `GEMINI_MOCK=true` still works and logs a warning.
- `OPENAI_API_KEY` — read by the OpenAI SDK when `LLM_API_KEY` and `LLM_BASE_URL` are both empty.
- `EXPLORATOR_STYLE_DIR` — overrides the genre catalog directory (default: bundled `domain/style/`). E2E points it at a temp copy so genre approval doesn't write to source-controlled YAML.

The pytest suite ignores `NEO4J_URI` / `NEO4J_PASSWORD` and uses `NEO4J_TEST_URI` (default `bolt://localhost:7689`) and `NEO4J_TEST_PASSWORD` (default `explorator_test`) — a separate Docker container with `tmpfs` storage and an autouse `MATCH (n) DETACH DELETE n` between tests. The dev DB on 7688 is never touched by tests.

---

## Frontend layout

See [`frontend/README.md`](../frontend/README.md) for the dev-side details. The high-level pieces:

```
src/views/
├── Dashboard               — session list, "new session" entry point
├── SessionWorkspace        — main flow: prompt → candidates → realization
└── PatternLibraryBrowser   — /patterns, with filters + curation
(GenreManagement — /genres, with research-agent UI — lives in src/components/)

src/stores/
├── sessionStore            — current session + history
├── candidateStore          — progression candidates, finalSelection
├── arrangementStore        — arrangement summaries, selectedDetail, toggleCuration
├── audioStore              — single-arrangement playback transport
├── comparisonAudioStore    — multi-arrangement playback (M4c)
├── patternLibraryStore     — list + cursor + toggleCuration fan-out
├── patternFiltersStore     — filter state (genre, type, curated_only)
├── genreResearchStore      — research jobs, drafts, approve/reject
├── capabilitiesStore       — persistence mode + feature flags from /v1/capabilities
└── exportStore             — export packages (create + list)

src/services/
├── api.ts                  — top-level fetch wrappers + ArrangementSummary/Detail/etc. types
├── audioEngine.ts          — single-arrangement Tone.js synthesis
├── comparisonAudioEngine.ts — multi-track Tone.js with mute/solo
├── audioUtils.ts           — shared synth presets, scheduling helpers
├── audioPresets.ts         — genre synth presets shared by both audio engines
├── midiUtils.ts            — MIDI download / blob handling
└── sse.ts                  — TokenUsage types for the token_usage SSE event

src/hooks/
├── streamSSE.ts            — shared SSE POST-stream reader (CRLF-safe parsing, timeout/abort)
└── useGenerationFlow, useRealizationFlow, useMutationFlow — round / realization / mutation streams
```

Each store follows the same shape: state fields, setters, and async actions that follow the optimistic-then-reconcile pattern. There's no global store composition — stores are independent and components subscribe à la carte via selectors.

---

## E2E architecture

`e2e/` is a separate npm package using Playwright, with two lanes (single chromium project each, 60s test timeout, 10s expect timeout):

- `playwright.config.ts` — parallel lane (`make e2e-parallel`, the one CI runs). fullyParallel, 4 workers (`E2E_WORKERS`); each worker spawns its own `LLM_MOCK=true` in-memory backend (:8200+n) and `vite preview` (:5300+n) via the `servers` fixture. `global-setup.parallel.ts` only rebuilds `frontend/dist`. Ignores the Neo4j-only specs.
- `playwright.neo4j.config.ts` — Neo4j lane (`make e2e-neo4j`), serial, for genre-research, pattern-library and m3-features. `global-setup.ts` spawns one backend on :8100 (`LLM_MOCK=true`, dev Neo4j) and `npm run preview` on :5199, hard-fails unless the backend is in neo4j mode, and cleans stale test sessions and research state (Cypher cleanup via `docker exec`; set `NEO4J_CONTAINER` if the container isn't `explorator-neo4j-1`). PIDs go to `.server-pids.json`; `global-teardown.ts` kills both processes.
- `fixtures/test-fixtures.ts` — re-exports Playwright's `test` with the per-worker `servers` fixture and a `testSession` fixture that creates a session via API and tears it down after the test.

Tests live in `e2e/tests/<feature>.spec.ts`. The preview servers serve `frontend/dist/`; both global-setups delete and rebuild it at the start of each lane, so no manual build is needed (don't run the two lanes concurrently — they share `dist`).

The mock `FakeLLMClient` returns deterministic structured responses for the main flow. Its `generate_text` returns stage-specific fixtures for genre-research prompts (matched on the `<!-- stage: … -->` tag in each template) and `"Mock text response"` otherwise.

---

## Operational notes

- **Dev workflow:** `make neo4j-up` (returns once the container is healthy — the backend probes Neo4j once at startup and otherwise falls back to memory mode), `make backend` (:8000), then `make frontend` (:5173, proxying `/v1` to :8000). Plain `npm run dev` proxies to `VITE_API_TARGET`, which defaults to `http://localhost:8100` (the E2E backend). `make test` starts the test DB itself. Without an LLM key, use `LLM_MOCK=true make backend`. Hit ctrl-C on backend to stop.
- **Migration scripts** live in `backend/scripts/migrations/`. They follow the M5d2/M5d3 pattern: idempotent, dry-run by default, `--yes` to apply. New ones get added per milestone.
- **Genre profiles** live as YAML in `domain/style/{genres,rules,grammars}/`. In Neo4j mode they are synced into Neo4j at startup and after a research draft is approved, then read from Neo4j; in memory mode they are read straight from YAML. After hand-editing YAML, restart the backend.
- **Local data** lives in the `neo4j_data` Docker volume (dev DB) and `tmpfs` (test DB, ephemeral). Wipe dev DB by `docker compose down -v`.

---

## Where to look next

- **Concrete user flow:** root [`README.md`](../README.md) → "A first session"
- **Frontend UI grammar:** [`docs/DESIGN.md`](./DESIGN.md)
- **Per-milestone history:** [`docs/design/specs/`](./design/specs/) and [`docs/design/plans/`](./design/plans/)
- **Open issues:** GitHub issues #2 (cadence/loopability granularity), #3 (tension_curve dimension)
