# MusicExplorator

Genre-aware musical exploration engine. A creative copilot that helps producers explore genre-specific harmonic ideas through iterative generation, realization, evaluation, and refinement.

## What It Does

- Translate high-level creative prompts ("dream pop in A major, wistful and haunted") into structured musical constraints
- Generate multiple candidate chord progressions for a target genre using Gemini Pro
- Evaluate candidates with hybrid scoring (deterministic music theory + Gemini Flash)
- Display ranked results with Roman numeral analysis and per-dimension scores
- Real-time progress tracking via SSE as the LangGraph engine runs
- Export as MIDI for use in DAWs like Ableton (M4)

## Current Status: M1 Harmonic MVP Complete

The system generates and evaluates genre-specific chord progressions end-to-end:

- **LangGraph Engine:** 6-node flow (parse intent → load genre → generate → evaluate → select → persist)
- **Gemini Integration:** Pro for creative generation, Flash for intent parsing + evaluation scoring
- **music21 Adapter:** Roman numeral analysis with flat/sharp normalization
- **Hybrid Evaluation:** Deterministic loopability/cadence/coherence checks + Gemini genre fit/novelty/emotional fit
- **Genre System:** 3 curated profiles auto-synced to Neo4j on startup
- **Frontend:** Candidate card grid with scores, prompt bar with generation mode toggle, real-time pipeline progress bar
- **Tests:** 147 passing (136 unit + 11 integration)

### Roadmap

| Milestone | Status | What It Adds |
|-----------|--------|-------------|
| M0 — Foundations | Done | Project scaffold, models, Neo4j, API, frontend shell |
| M1 — Harmonic MVP | Done | LangGraph engine, Gemini progression generation, theory evaluation, candidate cards |
| M2 — Realization MVP | Next | Voicing + bass generation, piano roll, Tone.js playback |
| M3 — Guided Search | Planned | Multi-round mutation, feedback loop, Pareto ranking |
| M4 — Export | Planned | MIDI export, candidate explanations, comparison views |
| M5 — Expanded Surface | Planned | Melodic complements, groove patterns, genre research agent |

## Tech Stack

**Backend:** Python 3.12, FastAPI, Pydantic v2, LangGraph, Neo4j, music21, Gemini API (google-genai)

**Frontend:** React 18, TypeScript, Vite, Tailwind CSS, Zustand, TanStack Query

**Tooling:** uv, ruff, mypy (strict), pytest, Docker Compose

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+
- Docker
- A Gemini API key

### Setup

```bash
# Clone and enter the project
git clone git@github.com:Blevene/Explorator.git
cd Explorator

# Copy env and add your Gemini API key
cp .env.example backend/.env
# Edit backend/.env and set GEMINI_API_KEY

# Start Neo4j
make neo4j-up

# Install backend dependencies
cd backend && uv sync --all-extras && cd ..

# Install frontend dependencies
cd frontend && npm install && cd ..
```

### Run

```bash
# Terminal 1: Backend (port 8001)
cd backend && uv run uvicorn explorator.api.app:create_app --factory --host 0.0.0.0 --port 8001 --reload

# Terminal 2: Frontend (port 5173/5174, proxies API to backend)
make frontend

# Open http://localhost:5173 (or whichever port Vite assigns)
```

### Generate Progressions

1. Open the frontend in your browser
2. Create a new session with a prompt like "Dream pop in A major, wistful and haunted"
3. In the workspace, click **Generate** (or adjust the mode: conservative/balanced/exploratory)
4. Watch the pipeline progress bar as it runs through 6 stages
5. See candidate cards with chord symbols, Roman numerals, scores, and rationale

### Test

```bash
make test        # Full suite (147 tests, requires Neo4j)
make test-unit   # Unit tests only (no Neo4j needed)
make lint        # ruff + mypy
```

## Architecture

```
User Prompt
  → Intent Parser (regex + Gemini Flash)
  → Genre Profile (YAML → Neo4j)
  → Harmony Generator (Gemini Pro)
  → Theory Evaluator (deterministic + Gemini Flash)
  → Ranking (weighted top-K selection)
  → Persist to Neo4j
  → Candidate Cards in UI
```

The LangGraph engine orchestrates this as a stateful graph flow. FastAPI owns HTTP/sessions. Domain services are pure Python. Neo4j stores all candidates and lineage.

## Project Structure

```
explorator/
├── backend/
│   └── src/explorator/
│       ├── api/          # FastAPI routes (sessions, rounds, candidates, genres)
│       ├── adapters/     # Gemini client, music21 adapter
│       ├── domain/       # Intent parsing, harmony generation, evaluation, genre system
│       ├── engine/       # LangGraph state, nodes, graph definition
│       ├── graph/        # Neo4j repositories
│       ├── models/       # Pydantic v2 domain models (46 classes)
│       └── export/       # MIDI generation (M4+)
├── frontend/
│   └── src/
│       ├── views/        # Dashboard, SessionWorkspace
│       ├── components/   # CandidateCard, PromptBar
│       ├── stores/       # Zustand state
│       └── services/     # API client, SSE
├── product_documents/    # PRD, specs, architecture docs
├── docs/                 # Design specs, implementation plans
├── docker-compose.yml    # Neo4j
└── Makefile
```

## Configuration

| Service | Port | Purpose |
|---------|------|---------|
| Neo4j Browser | 7475 | Graph visualization |
| Neo4j Bolt | 7688 | Driver connection |
| Backend | 8001 | FastAPI API |
| Frontend | 5173 | Vite dev server |

## Genre Profiles

Three curated genres ship with the system, each with harmonic vocabulary, rules, anti-patterns, and grammars:

- **Dream Pop** — Open voicings, borrowed minor iv, slow harmonic rhythm, soft cadences (default 4 bars)
- **Synthwave** — Minor key, arpeggiated patterns, root-heavy bass, steady pulse (default 4 bars)
- **Cinematic** — Wide register, pedal tones, chromatic mediants, dynamic density (default 8 bars)

Genre profiles are YAML files in `backend/src/explorator/domain/style/genres/`. New genres can be added manually or via the genre research agent (M5).

## Evaluation Dimensions

Each candidate is scored on 6 dimensions:

| Dimension | Source | What It Measures |
|-----------|--------|-----------------|
| Genre Fit | Gemini Flash | How authentically the progression represents the target genre |
| Emotional Fit | Gemini Flash | How well it matches the target mood |
| Novelty | Gemini Flash | How creative/unexpected for the genre |
| Theoretical Coherence | Deterministic | Diatonic fit via Roman numeral analysis |
| Cadence Quality | Deterministic | Strength of the ending cadence (V→I, IV→I, etc.) |
| Loopability | Deterministic | How well the progression loops back to the start |
