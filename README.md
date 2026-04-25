# MusicExplorator

A creative copilot for music producers. Generate chord progressions, realize them into voiced arrangements with bass / groove / melody, evaluate and rank the results, mutate promising candidates, and build a personal library of curated patterns over time.

## What it does

**Create**
- Translate creative prompts (*"dream pop in A major, wistful and haunted"*) into structured musical constraints
- Generate candidate chord progressions across 40+ genre profiles via Gemini Pro
- Realize progressions into arrangements: voicings (open, close, drop-2, drop-3), genre-specific bass modes, groove patterns, optional melodic complement
- Score arrangements across 12 dimensions (deterministic music theory + Gemini)
- Mutate promising candidates: substitute, extend, transform — guided by user feedback

**Refine**
- Multi-round exploration with per-round finalists (safest / best-loop / most-experimental)
- Plain-text feedback reweights the scorer across rounds
- Pareto ranking surfaces distinct trade-offs rather than a single "winner"

**Play & compare**
- Piano roll with amber voicing, blue bass, emerald melody, groove-accent overlay
- Tone.js playback with genre-matched synth presets
- DAW-style comparison view: load multiple finalists into mute/solo lanes with synchronized transport

**Export & curate**
- MIDI + JSON export of any arrangement, with Gemini-generated explanation and full provenance trace
- Pattern library: every finalist auto-harvests its progression, voicing, bass, groove, and melody patterns
- Star your favourites; filter `/patterns` to *Curated only*

## Status

**M0 → M5d shipped.** M6 (multi-layer mutation) is specced and pending. See [`docs/superpowers/plans/`](./docs/superpowers/plans/) for the milestone history, or [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md#pipelines) for the current pipeline shape.

| | |
|---|---|
| Backend | 635 tests (unit + integration + API), all green |
| Frontend | 59 vitest, tsc strict, `npm run build` clean |
| E2E | 41 Playwright; 36 green, 4 pre-existing M5c genre-research failures (mock-infrastructure gap) |

## Quick start

**Prerequisites:** Python 3.13+, Node.js 20+, Docker, a Gemini API key.

```bash
git clone git@github.com:Blevene/Explorator.git
cd Explorator

# Configure
cp .env.example backend/.env
# Edit backend/.env and set GEMINI_API_KEY

# Bring up Neo4j (dev container on :7688)
make neo4j-up

# Install deps
cd backend  && uv sync --all-extras && cd ..
cd frontend && npm install         && cd ..
```

**Run**

```bash
# Terminal 1 — Backend on :8000
make backend

# Terminal 2 — Frontend (Vite dev server, default :5173, proxies /v1)
cd frontend && npm run dev -- --host 0.0.0.0
```

Open http://localhost:5173.

**Test**

```bash
make test                       # Backend full suite (auto-starts isolated test Neo4j on :7689)
make lint                       # ruff + mypy strict
cd frontend && npm run test:unit
make e2e                        # Playwright — spawns its own backend + frontend internally
```

The pytest suite wipes the DB between tests, so it runs against a dedicated `neo4j-test` container on port 7689 — the dev DB on 7688 is never touched. `make test*` brings the test container up automatically; if you invoke pytest directly, run `make neo4j-test-up` first.

## A first session

1. **Create a session** — prompt like *"Dream pop in A major, wistful and haunted"*.
2. **Generate** (mode: conservative / balanced / exploratory). Watch the SSE pipeline progress; candidate cards appear with chord symbols, Roman numerals, scores, and rationale.
3. **Realize** a candidate → voicings, bass, groove, and melody are generated and evaluated. Three finalists surface with role badges.
4. **Play** an arrangement with genre-matched synth. Mute/unmute voicing, bass, groove, melody independently.
5. **Compare** two or three finalists in DAW-style lane view with synchronized transport.
6. **Submit feedback** in plain text — the scorer reweights and you can launch the next round.
7. **Mutate** a promising candidate to explore substitutions / extensions / transformations.
8. **Export** as MIDI + JSON with explanation and provenance trace.
9. **Star** finalists to add them to your curated library. Browse all patterns at `/patterns`; filter to *Curated only* for just your keepers.

## Architecture (overview)

Single-process FastAPI app driving a LangGraph orchestration engine, persisted to Neo4j, served to a React SPA. Three LangGraph graphs compose at startup: an exploration pipeline (intent → generate → evaluate → rank → persist), a realization sub-graph (voicing → bass → groove → melody → assemble → evaluate → rank → persist → harvest), and a genre-research sub-graph (research → draft → critique → refine → validate).

**Key design choices**
- **Neo4j is the single source of truth** — sessions, candidates, arrangements, scorecards, feedback events, pattern library, lineage. No relational adjunct.
- **Domain services are pure Python** — generators, evaluators, adapters know nothing about HTTP or graph orchestration.
- **Append-only event log + denormalized read cache** — feedback events and pattern curation events are append-only; denormalized fields (e.g. `is_curated` on `PatternLibraryEntry`) are dual-written in the same Neo4j transaction for fast filter queries.
- **Provenance is first-class** — every candidate carries `parent_candidate_id`, `mutation_op`, `session_id`, `round`, `family_id`. Powers explanation, comparison, and export features.

Full architecture, data model, and pipeline diagrams: [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md).

## Project layout

```
explorator/
├── backend/src/explorator/    # FastAPI + LangGraph + domain services + Neo4j repos
├── frontend/src/              # React 19 + Zustand + Tone.js
├── e2e/                       # Playwright (spawns its own backend + frontend)
├── docs/
│   ├── ARCHITECTURE.md        # Current system architecture (start here)
│   ├── DESIGN.md              # Frontend design language ("studio monitor")
│   ├── decisions/             # ADRs — load-bearing decisions
│   ├── manual-test/           # Per-milestone manual QA checklists
│   └── superpowers/           # Historical design specs + implementation plans
├── product_documents/archive/ # Pre-implementation product docs (time capsule)
├── docker-compose.yml         # Neo4j dev (7688) + test (7689) containers
└── Makefile
```

## Tech stack

**Backend:** Python 3.13 · FastAPI · Pydantic v2 · LangGraph · Neo4j 5 · music21 · Gemini API · sse-starlette · ULID

**Frontend:** React 19 · TypeScript 5 (strict) · Vite 7 · Tailwind CSS v4 · Zustand 5 · Tone.js 15 · sonner

**Tooling:** uv · ruff · mypy strict · pytest + pytest-asyncio · vitest · Playwright · Docker Compose

## Configuration

| Service | Port | Purpose |
|---|---|---|
| Neo4j Browser (dev) | 7475 | Graph visualization |
| Neo4j Bolt (dev) | 7688 | Driver connection for the running app |
| Neo4j Browser (test) | 7476 | Isolated test DB browser |
| Neo4j Bolt (test) | 7689 | Pytest-only — tests wipe between runs |
| Backend (dev) | 8000 | FastAPI via `make backend` |
| Frontend (dev) | 5173 | Vite dev server (`npm run dev`) |
| Backend (E2E) | 8100 | Spawned by Playwright with `GEMINI_MOCK=true` |
| Frontend (E2E) | 5199 | `npm run preview` against the production build |

## Genre profiles

40+ genre YAMLs ship in `backend/src/explorator/domain/style/genres/`. Each defines harmonic vocabulary, voicing/bass/groove/melodic preferences, and an experimentation envelope. Three are hand-curated seed genres (Dream Pop, Synthwave, Cinematic); the rest were produced by the **M5c genre research agent** — a research → draft → critique → refine → validate pipeline that synthesizes musicological research into the YAML schema and validates deterministically with Pydantic.

## Evaluation dimensions

Each arrangement is scored across **12 dimensions**, aggregated into a single `weighted_total`. Weights are per-session and mutated by user feedback (M3b).

**Progression quality** (hybrid deterministic + Gemini)
| Dimension | What it measures |
|---|---|
| Genre Fit | Authenticity to target genre (Gemini Flash) |
| Emotional Fit | Alignment with target mood (Gemini Flash) |
| Novelty | Creativity / unexpectedness (Gemini Flash) |
| Theoretical Coherence | Diatonic fit via Roman numeral analysis (deterministic) |
| Cadence Quality | Strength of ending cadence (deterministic) |
| Loopability | How well the progression loops (deterministic) |

**Arrangement quality** (deterministic)
| Dimension | What it measures |
|---|---|
| Voice Leading | Smoothness, common-tone retention, parallel-motion avoidance |
| Register Density | Mud-zone avoidance, spacing balance, bass–voicing separation |
| Playability | Hand-span feasibility, voice count limits |
| Groove Quality | Archetype consistency, per-genre groove tendency fit |
| Melody–Harmony | Melody–chord-tone alignment, contour cohesion |
| Tension Curve | (Deferred — tracked as GitHub #3) |

## Known limitations

- **Single operator, no auth** — designed to run locally for one user. Adding auth is deferred until there's a real reason (sharing, multi-tenancy).
- **M5c E2E flakiness** — 4 tests in `e2e/tests/genre-research.spec.ts` fail because `FakeGeminiClient.generate_text` returns non-JSON. Documented; needs dedicated test-infrastructure work.
- **Warm-start retrieval doesn't favor curated patterns yet** — the library is populated and curation works, but retrieval still uses score-ordered top-K. Natural follow-up once there's curated data to tune against.
- **GitHub issues:** [#2](https://github.com/Blevene/Explorator/issues/2) (cadence/loopability granularity), [#3](https://github.com/Blevene/Explorator/issues/3) (tension_curve dimension).

## Further reading

- [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) — current system architecture, data model, pipelines, invariants
- [`docs/DESIGN.md`](./docs/DESIGN.md) — frontend design language (studio monitor aesthetic), CSS tokens, component patterns
- [`docs/decisions/`](./docs/decisions/) — ADRs for the load-bearing architectural decisions
- [`docs/superpowers/specs/`](./docs/superpowers/specs/) and [`docs/superpowers/plans/`](./docs/superpowers/plans/) — point-in-time milestone records (preserved, not maintained)
- [`product_documents/archive/`](./product_documents/archive/) — pre-implementation product docs (time capsule)
