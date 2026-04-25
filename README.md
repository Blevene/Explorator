# MusicExplorator

Genre-aware musical exploration engine. A creative copilot for producers: generate chord progressions, realize them into voiced arrangements with bass, groove, and melodic layers, evaluate and rank the results, mutate promising candidates, and build a personal library of curated patterns over time.

## What It Does

**Create:**
- Translate creative prompts ("dream pop in A major, wistful and haunted") into structured musical constraints
- Generate candidate chord progressions across 40+ genre profiles via Gemini Pro
- **Realize** progressions into arrangements: voicings (open, close, drop-2, drop-3), genre-specific bass modes, groove patterns, and optional melodic complements
- Evaluate arrangements across 12 dimensions (music theory + Gemini scoring)
- **Mutate** promising candidates: transform, extend, substitute, or blend — guided by user feedback

**Refine:**
- Multi-round exploration with per-round finalists (safest / best-loop / most-experimental)
- Free-text feedback loops reweight the scoring across rounds
- Pareto ranking surfaces distinct trade-offs rather than a single "winner"

**Play & compare:**
- Piano roll with amber voicing notes, cyan bass, purple melody
- Tone.js playback with genre-matched synth presets
- DAW-style comparison view: load multiple finalists into mute/solo lanes with synchronized transport

**Export & curate:**
- MIDI + JSON export of any arrangement, with human-readable explanation and full provenance trace
- **Pattern library** — every finalist auto-harvests its progression, voicing, bass, groove, and melody patterns into a reusable corpus
- Star your favourites to build a curated library; filter `/patterns` to curated-only

## Current Status

All feature milestones through **M5d** are shipped. M6 (multi-layer mutation) is specced and awaiting implementation.

### Roadmap

| Milestone | Status | What It Adds |
|---|---|---|
| M0 — Foundations | ✅ Done | Project scaffold, Pydantic models, Neo4j, FastAPI, React shell |
| M1 — Harmonic MVP | ✅ Done | LangGraph exploration flow, Gemini progression generation, theory + Gemini scoring, 3 seed genres |
| M2a — Realization Engine | ✅ Done | Voicing + bass generation, arrangement assembly, Neo4j persistence |
| M2b — Arrangement Evaluation | ✅ Done | Voice leading, register/density, playability evaluators; within-family ranking |
| M2c — Playback & Visualization | ✅ Done | Piano roll, Tone.js playback, split-panel arrangement view |
| M3a — Mutation Loop | ✅ Done | Gemini-driven mutations (substitute, extend, transform) on selected candidates |
| M3b — Feedback Reweighting | ✅ Done | Free-text feedback interpreter updates objective weights across rounds |
| M3c — Pareto Ranking & Finalists | ✅ Done | 3 finalists per round (safest / best-loop / most-experimental), distinct trade-offs |
| M4a — MIDI & JSON Export | ✅ Done | Per-arrangement MIDI + JSON sidecar, combined session export |
| M4b — Explanation, Comparison & Provenance | ✅ Done | Gemini-generated explanations, full lineage trace, comparison view |
| M4c — Comparison Playback | ✅ Done | DAW-style mute/solo lanes, synchronized Tone.js transport for A/B listening |
| M5a — Groove Patterns | ✅ Done | 5 groove archetypes, groove evaluation, accent overlay on piano roll |
| M5b — Melodic Complement | ✅ Done | Two-phase melody generation (Gemini strategy + deterministic realization), melody-harmony eval |
| M5c — Genre Research Agent | ✅ Done | Research → draft → critique → refine → validate pipeline produced 25+ new genre YAMLs |
| M5d-1 — Pattern Harvest | ✅ Done | Silent accumulation: every finalist contributes 5 pattern rows (progression/voicing/bass/groove/melody) |
| M5d-2 — Pattern Library Browser | ✅ Done | `/patterns` view with keyset pagination, genre/type filters, soft-delete |
| M5d-3 — Pattern Curation | ✅ Done | Star finalists and library patterns; "curated only" filter; atomic event-log + denormalized state |
| M6 — Multi-layer Mutation | 🟡 Spec'd | Mutate voicings / bass / groove / melody independently, not just progressions |

### Tests

- **Backend:** 635 tests (unit + integration + API), all green on main
- **Frontend:** 59 vitest tests, tsc strict, `npm run build` clean
- **E2E:** 41 Playwright tests covering happy path, mutations, feedback, comparison, export, M5a-d surfaces. 36 currently green; 4 pre-existing failures in the M5c genre-research spec (mock-infrastructure gap, documented in the spec)

## Tech Stack

**Backend:** Python 3.13, FastAPI, Pydantic v2, LangGraph, Neo4j 5 (community), music21, Gemini API (google-genai), ULID, sse-starlette

**Frontend:** React 19, TypeScript 5 (strict), Vite 7, Tailwind CSS v4, Zustand 5, Tone.js 15, sonner (toasts), Playwright 1.50 for E2E

**Tooling:** uv, ruff, mypy (strict), pytest + pytest-asyncio, vitest, Docker Compose, Makefile

## Quick Start

### Prerequisites

- Python 3.13+
- Node.js 20+
- Docker
- A Gemini API key

### Setup

```bash
git clone git@github.com:Blevene/Explorator.git
cd Explorator

# Copy env and add your Gemini API key
cp .env.example backend/.env
# Edit backend/.env and set GEMINI_API_KEY

# Start Neo4j (dev + isolated test containers)
make neo4j-up
make neo4j-test-up     # only needed if you plan to run the backend test suite

# Install backend dependencies
cd backend && uv sync --all-extras && cd ..

# Install frontend dependencies
cd frontend && npm install && cd ..
```

### Run

```bash
# Terminal 1: Backend (port 8000)
make backend
# equivalent to:
# cd backend && uv run uvicorn explorator.api.app:create_app --factory --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Frontend (Vite dev server, default port 5173, proxies /v1 to backend)
cd frontend && npm run dev -- --host 0.0.0.0

# Open http://localhost:5173 (or whatever port Vite reports)
```

### A typical session

1. **Create a session** with a prompt like *"Dream pop in A major, wistful and haunted"*.
2. Click **Generate** (mode: conservative / balanced / exploratory). Watch the SSE-driven pipeline progress.
3. Candidate cards appear with chord symbols, Roman numerals, 9-dimension scores, and rationale.
4. Click **Realize** on a candidate → voicings, bass, groove, and melody are generated and evaluated.
5. The arrangement list (left) shows the grouped results; the detail view (right) shows piano roll + scores.
6. **Play** an arrangement with genre-matched Tone.js synthesis. Mute/unmute voicing, bass, groove, melody independently.
7. **Compare** two or three finalists side-by-side in DAW-style lane view.
8. **Submit feedback** in plain text — the scorer reweights and you can launch the next round.
9. **Mutate** a promising candidate to explore substitutions / extensions / transformations.
10. **Export** as MIDI + JSON with a Gemini-generated explanation and full provenance trace.
11. **Star** finalists to add them to your curated pattern library. Filter `/patterns` to `Curated only` to browse just your keepers.

### Test

```bash
make test              # Full backend suite — auto-starts isolated test Neo4j on :7689
make test-unit         # Backend unit tests only
make test-integration  # Backend integration tests (real Neo4j fixtures)
make lint              # ruff + mypy strict

cd frontend && npm run test:unit   # vitest

make e2e               # Playwright — spawns backend (8100) + frontend preview (5199) internally
```

The pytest suite wipes the DB between tests, so it runs against a dedicated `neo4j-test` container (port 7689) — the dev DB on 7688 is never touched. The `make test*` targets bring it up automatically. If you invoke pytest directly, run `make neo4j-test-up` first or override `NEO4J_TEST_URI` / `NEO4J_TEST_PASSWORD`.

E2E spawns its own backend + frontend processes; no manual startup needed.

## Architecture

Two LangGraph pipelines composed into one unified graph:

```
User prompt
  → parse_intent (Gemini Flash)
  → load_genre_profile (Neo4j)
  → generate_progressions (Gemini Pro, 4 candidates)
  → evaluate_progressions (deterministic + Gemini Flash)
  → rank_progressions
  → persist_progressions (Neo4j)
     [round completes: SSE emits round_complete]

User selects a candidate to realize:
  → load_realization_context
  → plan_voicings (Gemini Flash) → realize deterministically (music21)
  → generate_bass (genre templates × variant modes)
  → generate_groove (5 archetypes)
  → generate_melody (Gemini strategy → deterministic realization)
  → assemble_arrangements (voicing × bass × groove cross-product)
  → evaluate_arrangements (voice leading + register + playability + melody-harmony + groove)
  → rank_and_select (finalists: safest / best_loop / most_experimental)
  → persist_realization
  → harvest_patterns (5 pattern rows per finalist → PatternLibraryEntry in Neo4j)
  → persist_round

User feedback loop:
  → interpret_feedback (Gemini Flash → weight_deltas)
  → update_objective_weights (per-session scorer state)
  → back to generate_progressions or mutate_candidates

User curation:
  → POST /v1/arrangements/{id}/curation (atomic event + fan-out in one Neo4j tx)
  → UserFeedbackEvent appended, is_curated/curated_at denormalized across facet rows
```

**Key design choices:**
- **Neo4j is the source of truth** — sessions, candidates, arrangements, scorecards, feedback events, pattern library entries, lineage. No separate OLTP database.
- **Dual-write for read-path performance** — e.g., curation writes both an append-only event and a denormalized boolean flag, inside one transaction. Event log is authoritative; flag is a cache for fast filter queries.
- **Domain services are pure Python** — generators, evaluators, adapters. FastAPI owns HTTP + SSE; LangGraph owns orchestration; domain owns music theory.
- **Provenance is built in, not bolted on** — every candidate carries its full lineage (parent_candidate_id, mutation_op, session_id, round), enabling the explanation and comparison features.

## Project Structure

```
explorator/
├── backend/
│   └── src/explorator/
│       ├── api/                           # FastAPI routes + schemas
│       │   ├── routes/                    #   sessions, realization, patterns, comparisons, export, feedback, genres, genre_research
│       │   └── schemas/
│       ├── adapters/                      # Gemini client, music21 adapter, gemini_mock (E2E)
│       ├── domain/
│       │   ├── evaluation/                # Voice leading, register/density, playability, groove, melody-harmony, theory scores
│       │   ├── export/                    # MIDI builder, JSON sidecar
│       │   ├── harmony/                   # Progression generator, mutator
│       │   ├── intent/                    # Prompt parser, feedback interpreter
│       │   ├── memory/                    # Pattern harvesting extractors
│       │   ├── realization/               # Voicing, bass, groove, melody generators + arrangement assembler
│       │   └── style/                     # 40+ genre YAMLs, rules, grammars, schemas
│       ├── engine/                        # LangGraph state + nodes + unified graph
│       │   └── nodes/
│       │       └── genre_research/        # M5c research agent sub-graph (research → draft → critique → refine → validate)
│       ├── graph/                         # Neo4j repositories (one per node label)
│       ├── models/                        # Pydantic v2 domain models
│       ├── prompts/                       # Centralized Gemini prompt templates
│       └── services/
│           └── pattern_library/           # Cursor, filters, harvest service, curation service
├── frontend/
│   └── src/
│       ├── views/                         # Dashboard, SessionWorkspace, PatternLibraryBrowser, GenreManagement
│       ├── components/                    # CandidateCard, ArrangementList, FinalistPanel, PianoRoll, TransportBar,
│       │                                  #   ComparisonView, ExportModal, StarButton, PatternCard, etc.
│       ├── stores/                        # Zustand — session, candidate, arrangement, audio, comparison, patternLibrary,
│       │                                  #   patternFilters, genreResearch
│       ├── services/                      # API client, SSE consumer, audio engines (single + comparison), MIDI utils
│       └── lib/                           # Toast wrapper, utilities
├── e2e/
│   ├── tests/                             # 14 spec files covering happy path + every milestone's surfaces
│   ├── fixtures/                          # Playwright fixtures (testSession, goToWorkspace, generateCandidates, etc.)
│   └── playwright.config.ts
├── docs/
│   ├── ARCHITECTURE.md                    # Current system architecture (successor to product_documents/)
│   ├── DESIGN.md                          # Frontend design language (studio monitor aesthetic)
│   ├── manual-test/                       # Per-milestone manual QA checklists
│   └── superpowers/                       # Design specs + implementation plans (point-in-time, preserved)
├── product_documents/
│   └── archive/                           # Original PRD, functional spec, etc. — frozen at project inception
├── docker-compose.yml                     # Neo4j dev (7688) + test (7689) containers
└── Makefile
```

## Configuration

| Service | Port | Purpose |
|---|---|---|
| Neo4j Browser (dev) | 7475 | Graph visualization |
| Neo4j Bolt (dev) | 7688 | Driver connection for the running app |
| Neo4j Browser (test) | 7476 | Isolated test DB browser |
| Neo4j Bolt (test) | 7689 | Pytest-only — tests wipe between runs |
| Backend (dev) | 8000 | FastAPI via `make backend` |
| Frontend (dev) | 5173 (Vite default) | `npm run dev` |
| Backend (E2E) | 8100 | Spawned by Playwright global-setup, with `GEMINI_MOCK=true` |
| Frontend (E2E) | 5199 | `npm run preview` against the production build |

## Genre Profiles

40+ genre YAMLs ship with the system in `backend/src/explorator/domain/style/genres/`. Each defines:

- **Harmonic vocabulary** and tendencies (functional strength, chromaticism, borrowed-chord tolerance, cadence preference)
- **Voicing preferences** (default + variant types, register, density)
- **Bass preferences** (default + variant modes, rhythmic density)
- **Groove tendencies** (comp density, articulation, syncopation)
- **Melodic tendencies** (motion preference, range placement, phrase length)
- **Experimentation envelope** (per-layer tolerance for deviation from the baseline)

The seed set is 3 hand-curated genres (Dream Pop, Synthwave, Cinematic). The remaining 37+ were produced by the M5c **genre research agent** — a research → draft → critique → refine → validate pipeline that synthesizes musicological research into the YAML schema deterministically validated by Pydantic.

## Evaluation Dimensions

Each arrangement is scored across 12 dimensions, aggregated into a single `weighted_total`:

### Progression quality (hybrid deterministic + Gemini)
| Dimension | What It Measures |
|---|---|
| Genre Fit | Authenticity to target genre (Gemini Flash) |
| Emotional Fit | Alignment with target mood (Gemini Flash) |
| Novelty | Creativity / unexpectedness (Gemini Flash) |
| Theoretical Coherence | Diatonic fit via Roman numeral analysis (deterministic) |
| Cadence Quality | Strength of ending cadence (deterministic) |
| Loopability | How well the progression loops (deterministic) |

### Arrangement quality (deterministic)
| Dimension | What It Measures |
|---|---|
| Voice Leading | Smoothness, common-tone retention, parallel-motion avoidance |
| Register Density | Mud-zone avoidance, spacing balance, bass–voicing separation |
| Playability | Hand-span feasibility, voice count limits |
| Groove Quality | Archetype consistency, per-genre groove tendency fit |
| Melody–Harmony | Melody–chord-tone alignment, contour cohesion |
| Tension Curve | (Deferred — tracked as GitHub #3) |

Weights are per-session and mutated by user feedback (M3b). The default weight profile is balanced; a session that says *"more adventurous, less predictable"* pushes novelty up and loopability down.

## External Integrations

| System | Role |
|---|---|
| **Gemini Pro** | Creative generation (progressions, mutations, voicing strategy, melodic strategy, explanations) |
| **Gemini Flash** | Fast deterministic tasks (intent parsing, theory scoring, feedback interpretation, genre critique) |
| **Neo4j** | Single source of truth — sessions, candidates, arrangements, scorecards, feedback events, pattern library, lineage |
| **music21** | Roman numeral analysis, voicing realization, voice-leading analysis |
| **Tone.js** | Browser-side synthesis with genre-matched presets |

## Known Issues / Deferred Work

- **M5c E2E flakiness** — 4 tests in `e2e/tests/genre-research.spec.ts` fail because `FakeGeminiClient.generate_text` returns non-JSON. Root cause and fix strategy documented in the commit log. Net E2E: 36/41 green.
- **Backend comparison endpoint test** — previously failed due to TestClient event-loop collision; converted to AsyncClient.
- **Warm-start retrieval** — the pattern library is populated but retrieval doesn't yet favor curated patterns during generation. Tracked for the next post-M5d PR.
- **GitHub issues:** #2 (cadence/loopability scoring granularity), #3 (implement tension_curve dimension).

## Further Reading

- **Frontend design language:** `docs/DESIGN.md` — "studio monitor" aesthetic, color palette, typography, interaction patterns
- **Current system architecture:** `docs/ARCHITECTURE.md` — the single source of truth for how the app is wired today
- **Historical design specs + implementation plans:** `docs/superpowers/specs/` and `docs/superpowers/plans/` — point-in-time records of each milestone's brainstorm → spec → plan → execution cycle
- **Original product documents:** `product_documents/archive/` — the pre-implementation PRD, functional spec, hybrid graph model, and architecture docs. Preserved as a time capsule; divergence from current reality is expected and acceptable
