# MusicExplorator

Genre-aware musical exploration engine. A creative copilot that helps producers explore genre-specific harmonic ideas through iterative generation, realization, evaluation, and refinement.

## What It Does

- Translate high-level creative prompts ("dream pop in A major, wistful and haunted") into structured musical constraints
- Generate multiple candidate chord progressions for a target genre
- Realize progressions into voicings, bass lines, and arrangements
- Evaluate candidates across multi-dimensional music criteria
- Iteratively refine through mutation and human feedback
- Export as MIDI for use in DAWs like Ableton

## Current Status: M0 Foundations Complete

The foundation layer is built and working:

- **Backend:** FastAPI + Pydantic v2 with 46 domain models
- **Database:** Neo4j graph persistence with 30 constraints
- **Genre System:** 3 curated profiles (Dream Pop, Synthwave, Cinematic) as YAML
- **API:** Session CRUD + genre list endpoints
- **Frontend:** React + Vite + Tailwind with Dashboard and session creation
- **Tests:** 124 passing (113 unit + 11 integration)

### Roadmap

| Milestone | Status | What It Adds |
|-----------|--------|-------------|
| M0 — Foundations | Done | Project scaffold, models, Neo4j, API, frontend shell |
| M1 — Harmonic MVP | Next | LangGraph engine, Gemini-powered progression generation, Roman numeral analysis |
| M2 — Realization MVP | Planned | Voicing + bass generation, piano roll, Tone.js playback |
| M3 — Guided Search | Planned | Multi-round mutation, feedback loop, Pareto ranking |
| M4 — Export | Planned | MIDI export, candidate explanations, comparison views |
| M5 — Expanded Surface | Planned | Melodic complements, groove patterns, genre research agent |

## Tech Stack

**Backend:** Python 3.12, FastAPI, Pydantic v2, LangGraph, Neo4j, music21, Gemini API

**Frontend:** React 18, TypeScript, Vite, Tailwind CSS, Zustand, TanStack Query, Tone.js

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
git clone <repo-url>
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

# Terminal 2: Frontend (port 5173, proxies API to backend)
make frontend

# Open http://localhost:5173
```

### Test

```bash
make test        # Full suite (124 tests, requires Neo4j)
make test-unit   # Unit tests only (no Neo4j needed)
make lint        # ruff + mypy
```

## Project Structure

```
explorator/
├── backend/
│   └── src/explorator/
│       ├── api/          # FastAPI routes, middleware
│       ├── adapters/     # Gemini client, music21 adapter
│       ├── domain/       # Genre profiles, harmony, realization, evaluation
│       ├── engine/       # LangGraph workflow (M1+)
│       ├── graph/        # Neo4j repositories
│       ├── models/       # Pydantic v2 domain models
│       └── export/       # MIDI generation (M4+)
├── frontend/
│   └── src/
│       ├── views/        # Dashboard, SessionWorkspace
│       ├── stores/       # Zustand state
│       └── services/     # API client
├── product_documents/    # PRD, specs, architecture docs
├── docs/                 # Design specs, implementation plans
├── docker-compose.yml    # Neo4j
└── Makefile
```

## Configuration

Neo4j runs on non-default ports to avoid conflicts:

| Service | Port | Purpose |
|---------|------|---------|
| Neo4j Browser | 7475 | Graph visualization |
| Neo4j Bolt | 7688 | Driver connection |
| Backend | 8001 | FastAPI API |
| Frontend | 5173 | Vite dev server |

## Genre Profiles

Three curated genres ship with the system:

- **Dream Pop** — Open voicings, borrowed minor iv, slow harmonic rhythm, soft cadences
- **Synthwave** — Minor key, arpeggiated patterns, root-heavy bass, steady pulse
- **Cinematic** — Wide register, pedal tones, chromatic mediants, dynamic density

Genre profiles are YAML files in `backend/src/explorator/domain/style/genres/`. New genres can be added manually or via the genre research agent (M5).
