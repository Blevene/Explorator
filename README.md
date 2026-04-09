# MusicExplorator

Genre-aware musical exploration engine. A creative copilot that helps producers explore genre-specific harmonic ideas through iterative generation, realization, evaluation, and refinement.

## What It Does

- Translate high-level creative prompts ("dream pop in A major, wistful and haunted") into structured musical constraints
- Generate multiple candidate chord progressions for a target genre using Gemini Pro
- **Realize** progressions into voiced arrangements with bass lines — multiple voicing types and bass modes per genre
- Evaluate candidates with hybrid scoring (deterministic music theory + Gemini Flash)
- **Visualize** arrangements on a piano roll with amber voicing notes and cyan bass notes
- **Play** arrangements in the browser with genre-matched Tone.js synthesis
- Display ranked results with Roman numeral analysis and per-dimension scores
- Real-time progress tracking via SSE as the LangGraph engine runs

## Current Status: M2 Realization MVP Complete

The system generates chord progressions, realizes them into voiced arrangements with bass lines, evaluates and ranks them, and lets you see and hear the results:

### M2a — Realization Engine
- **Voicing Generation:** Gemini Flash proposes voicing strategy → deterministic engine realizes named pitches (open, close, drop-2, drop-3)
- **Bass Line Generation:** Genre-specific rhythm templates (supportive, pedal, syncopated)
- **Arrangement Assembly:** Cross-product of voicing variants × bass modes per genre
- **5-node LangGraph flow:** load_context → plan_voicings → generate_bass → assemble → persist_realization

### M2b — Arrangement Evaluation
- **Three Deterministic Evaluators:** Voice leading quality, register/density balance, playability
- **Within-Family Ranking:** Quality filter + weighted scoring across 9 dimensions
- **Genre-Scoped Multi-Bass:** Each genre explores 2 bass modes automatically
- **Voice-Leading Optimization:** Inversion sweep minimizes voice movement between chords

### M2c — Playback & Visualization
- **Piano Roll:** Canvas-based pitch grid with amber voicing notes, cyan bass notes, playback cursor
- **Tone.js Playback:** Genre-matched synth presets (Dream Pop = pad, Synthwave = saw, Cinematic = warm triangle)
- **Full Transport:** Play/pause/stop, tempo slider, loop toggle, per-track mute (voicing/bass), volume
- **Split-Panel Layout:** Arrangement list (left) + detail view with piano roll + scores (right)
- **Score Panel:** 9-dimension bar chart (3 arrangement + 6 progression scores)

### M1 — Harmonic MVP (Foundation)
- **LangGraph Engine:** 6-node flow (parse intent → load genre → generate → evaluate → select → persist)
- **Gemini Integration:** Pro for creative generation, Flash for intent parsing + evaluation scoring
- **music21 Adapter:** Roman numeral analysis, voicing realization, voice-leading analysis
- **Hybrid Evaluation:** Deterministic loopability/cadence/coherence + Gemini genre fit/novelty/emotional fit
- **Genre System:** 3 curated profiles (Dream Pop, Synthwave, Cinematic) with voicing + bass preferences
- **Frontend:** Candidate card grid with scores, prompt bar with generation mode toggle, real-time pipeline progress

### Tests
- **Backend:** 245 passing (unit + integration)
- **Frontend:** TypeScript strict, builds clean

### Roadmap

| Milestone | Status | What It Adds |
|-----------|--------|-------------|
| M0 — Foundations | Done | Project scaffold, models, Neo4j, API, frontend shell |
| M1 — Harmonic MVP | Done | LangGraph engine, Gemini progression generation, theory evaluation |
| M2a — Realization Engine | Done | Voicing + bass generation, arrangement assembly, Neo4j persistence |
| M2b — Arrangement Evaluation | Done | 3 evaluators, ranking, multi-bass, voice-leading optimization |
| M2c — Playback & Visualization | Done | Piano roll, Tone.js playback, split-panel arrangement view |
| M3 — Guided Search | Planned | Multi-round mutation, feedback loop, Pareto ranking |
| M4 — Export | Planned | MIDI export, candidate explanations, comparison views |
| M5 — Expanded Surface | Planned | Melodic complements, groove patterns, genre research agent |

## Tech Stack

**Backend:** Python 3.12, FastAPI, Pydantic v2, LangGraph, Neo4j, music21, Gemini API (google-genai)

**Frontend:** React 19, TypeScript, Vite, Tailwind CSS v4, Zustand, Tone.js

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
# Terminal 1: Backend (port 8000)
cd backend && uv run uvicorn explorator.api.app:create_app --factory --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Frontend (port 5174, proxies API to backend)
cd frontend && npm run dev -- --host 0.0.0.0 --port 5174

# Open http://localhost:5174
```

### Usage

1. Open the frontend in your browser
2. Create a new session with a prompt like "Dream pop in A major, wistful and haunted"
3. Click **Generate** (adjust mode: conservative/balanced/exploratory)
4. Watch the pipeline progress bar as it runs through 6 stages
5. See candidate cards with chord symbols, Roman numerals, scores, and rationale
6. Click **Realize** on a candidate to generate voiced arrangements
7. Browse the split-panel view: arrangement cards (left) with voicing type + bass mode tags
8. Click an arrangement to see its piano roll visualization
9. Click **Play** to hear it with genre-matched synth sounds
10. Use transport controls: tempo, loop, mute voicing/bass independently

### Test

```bash
make test        # Full suite (requires Neo4j)
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
  → User clicks "Realize"
  → Voicing Strategy (Gemini Flash) → Deterministic Realization
  → Bass Line Generation (genre templates)
  → Arrangement Assembly (voicing × bass cross-product)
  → Arrangement Evaluation (voice leading + register + playability)
  → Within-Family Ranking (weighted 9-dimension scoring)
  → Piano Roll + Tone.js Playback
```

Two LangGraph pipelines: M1 exploration (6 nodes) and M2 realization (7 nodes). FastAPI owns HTTP/sessions. Domain services are pure Python. Neo4j stores all candidates and lineage.

## Project Structure

```
explorator/
├── backend/
│   └── src/explorator/
│       ├── api/          # FastAPI routes (sessions, rounds, candidates, realization)
│       ├── adapters/     # Gemini client, music21 adapter (voicing, voice leading)
│       ├── domain/
│       │   ├── evaluation/  # Voice leading, register density, playability evaluators
│       │   ├── harmony/     # Progression generation
│       │   ├── intent/      # Prompt parsing
│       │   ├── realization/ # Voicing generator, bass generator, arrangement assembler
│       │   └── style/       # Genre profiles, YAML loader, sync
│       ├── engine/       # LangGraph state, nodes, graph definitions
│       ├── graph/        # Neo4j repositories
│       ├── models/       # Pydantic v2 domain models
│       ├── prompts/      # Centralized Gemini prompt templates
│       └── export/       # MIDI generation (M4+)
├── frontend/
│   └── src/
│       ├── views/        # Dashboard, SessionWorkspace
│       ├── components/   # CandidateCard, ArrangementList, PianoRoll, TransportBar, ScorePanel
│       ├── stores/       # Zustand state (session, candidate, arrangement, audio)
│       └── services/     # API client, SSE, audio engine, MIDI utils
├── docs/
│   ├── DESIGN.md         # Frontend design language (studio monitor aesthetic)
│   └── superpowers/      # Design specs + implementation plans
├── product_documents/    # PRD, functional spec, architecture docs
├── docker-compose.yml    # Neo4j
└── Makefile
```

## Configuration

| Service | Port | Purpose |
|---------|------|---------|
| Neo4j Browser | 7475 | Graph visualization |
| Neo4j Bolt | 7688 | Driver connection |
| Backend | 8000 | FastAPI API |
| Frontend | 5174 | Vite dev server (proxies /v1 to backend) |

## Genre Profiles

Three curated genres ship with the system, each with harmonic vocabulary, voicing preferences, bass preferences, rules, and grammars:

- **Dream Pop** — Open voicings, mid-high register, supportive + pedal bass, borrowed minor iv, slow harmonic rhythm (default 4 bars)
- **Synthwave** — Close/drop-2 voicings, mid register, supportive + syncopated bass, minor key, steady pulse (default 4 bars)
- **Cinematic** — Open/drop-3 voicings, mid register, pedal + supportive bass, wide register, chromatic mediants (default 8 bars)

Genre profiles are YAML files in `backend/src/explorator/domain/style/genres/`. Each defines voicing preferences (`variant_voicing_types`, `default_register`, `favor_extensions`) and bass preferences (`variant_bass_modes`, `rhythmic_density`).

## Evaluation Dimensions

Each arrangement is scored on 9 dimensions:

### Arrangement Quality (M2b — deterministic)

| Dimension | Weight | What It Measures |
|-----------|--------|-----------------|
| Voice Leading | 0.15 | Smoothness, common-tone retention, parallel motion avoidance |
| Register Density | 0.12 | Mud zone avoidance, spacing balance, bass-voicing separation |
| Playability | 0.12 | Hand span feasibility, voice count limits |

### Progression Quality (M1 — hybrid deterministic + Gemini)

| Dimension | Weight | What It Measures |
|-----------|--------|-----------------|
| Genre Fit | 0.10 | Authenticity to target genre |
| Emotional Fit | 0.10 | Alignment with target mood |
| Novelty | 0.10 | Creativity/unexpectedness |
| Theoretical Coherence | 0.10 | Diatonic fit via Roman numeral analysis |
| Cadence Quality | 0.10 | Strength of ending cadence |
| Loopability | 0.11 | How well the progression loops |
