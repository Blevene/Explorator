# MusicExplorator v1 — System Design Specification

**Version:** 1.0
**Date:** 2026-03-26
**Status:** Draft

---

## 1. Overview

MusicExplorator is a genre-aware, explainable musical exploration engine that treats composition as a layered search problem. It helps producers explore genre-specific harmonic ideas through iterative generation, realization, evaluation, and refinement.

The system is a creative copilot and exploration lab, not an autonomous songwriting engine. The primary output is DAW-ready MIDI for use in tools like Ableton Live.

### Target User

Producer building in a DAW. Wants multiple credible genre-aware options, fast iteration, and exportable MIDI. Explanation features serve creative decision-making, not academic analysis.

### Initial Genre Support

Three curated genres to start: Dream Pop, Synthwave, Cinematic. The genre system is designed for adaptive expansion via both manual authoring and an agentic research loop.

---

## 2. Architecture

### 2.1 High-Level Layers

```
┌─────────────────────────────────────────────────────────┐
│  FRONTEND — React SPA (Vite + Tailwind)                 │
│  Session workspace, candidate cards + detail split,     │
│  Tone.js playback, chat sidebar                         │
└─────────────────────────┬───────────────────────────────┘
                          │ REST + SSE
┌─────────────────────────┴───────────────────────────────┐
│  API LAYER — FastAPI + Pydantic v2                      │
│  Sessions, rounds, candidates, feedback, export         │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────┴───────────────────────────────┐
│  ENGINE — LangGraph (inner loop only)                   │
│  Generate → evaluate → realize → rank → mutate loop     │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────┴───────────────────────────────┐
│  DOMAIN SERVICES — Pure Python modules                  │
│  Style, Harmony, Realization, Evaluation                │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────┴───────────────────────────────┐
│  INFRASTRUCTURE                                         │
│  Neo4j (Docker), Filesystem, Gemini API, music21 adapter│
└─────────────────────────────────────────────────────────┘
```

### 2.2 Key Boundaries

- **FastAPI** owns HTTP, auth, sessions, request validation, response shaping
- **LangGraph** owns the generate-evaluate-mutate loop only — called by FastAPI per round
- **Domain services** are pure Python modules — no HTTP, no framework coupling
- **Infrastructure** accessed through repository/adapter interfaces only

### 2.3 Mapping to Architecture Document Layers

| Architecture Layer | Design Component |
|---|---|
| L0 — User/Creative Direction | Frontend: prompt bar, constraints, feedback |
| L1 — Intent Interpretation | LangGraph: `parse_intent` node + domain intent service |
| L2 — Style/Genre Knowledge | LangGraph: `load_genre` node + Style Service + YAML files |
| L3 — Core Harmonic Search | LangGraph: `generate`, `mutate` nodes + Harmony Service |
| L4 — Musical Realization | LangGraph: `realize` node + Realization Service |
| L5 — Symbolic Analysis | LangGraph: `evaluate_progressions`, `evaluate_arrangements` nodes + Evaluation Service |
| L6 — Ranking/Selection | LangGraph: `rank_and_select`, `check_stop` nodes |
| L7 — Memory/Adaptation | LangGraph: `load_memory`, `persist_round` nodes + Graph Repository |
| L8 — Presentation/Export | Frontend views + Export Service |

---

## 3. Monorepo Structure

```
explorator/
├── backend/
│   ├── src/
│   │   └── explorator/
│   │       ├── api/                  # FastAPI routes, middleware, deps
│   │       │   ├── routes/
│   │       │   │   ├── sessions.py
│   │       │   │   ├── rounds.py
│   │       │   │   ├── candidates.py
│   │       │   │   ├── feedback.py
│   │       │   │   ├── export.py
│   │       │   │   └── genres.py
│   │       │   ├── middleware.py
│   │       │   ├── deps.py
│   │       │   └── sse.py            # Server-Sent Events for round progress
│   │       ├── engine/               # LangGraph workflow
│   │       │   ├── graph.py          # Graph definition and compilation
│   │       │   ├── state.py          # ExplorationState TypedDict
│   │       │   └── nodes/
│   │       │       ├── parse_intent.py
│   │       │       ├── load_genre.py
│   │       │       ├── load_memory.py
│   │       │       ├── generate.py
│   │       │       ├── evaluate_progressions.py
│   │       │       ├── select_top_progressions.py
│   │       │       ├── realize.py
│   │       │       ├── evaluate_arrangements.py
│   │       │       ├── rank_and_select.py
│   │       │       ├── check_stop.py
│   │       │       ├── mutate.py
│   │       │       └── persist_round.py
│   │       ├── domain/               # Pure domain services
│   │       │   ├── style/            # Genre profiles, rules, anti-patterns
│   │       │   │   ├── genres/
│   │       │   │   │   ├── dream_pop.yaml
│   │       │   │   │   ├── synthwave.yaml
│   │       │   │   │   ├── cinematic.yaml
│   │       │   │   │   └── drafts/   # Agentic research outputs pending review
│   │       │   │   ├── rules/
│   │       │   │   │   ├── dream_pop_rules.yaml
│   │       │   │   │   ├── synthwave_rules.yaml
│   │       │   │   │   └── cinematic_rules.yaml
│   │       │   │   ├── grammars/
│   │       │   │   │   ├── dream_pop_grammar.yaml
│   │       │   │   │   ├── synthwave_grammar.yaml
│   │       │   │   │   └── cinematic_grammar.yaml
│   │       │   │   ├── loader.py     # Validates YAML, syncs to Neo4j
│   │       │   │   ├── schema.py     # Pydantic models for genre data
│   │       │   │   └── service.py    # Genre profile retrieval, rule lookup
│   │       │   ├── harmony/          # Generation, mutation, analysis
│   │       │   │   ├── generator.py
│   │       │   │   ├── mutator.py
│   │       │   │   ├── analyzer.py   # Roman numeral analysis
│   │       │   │   └── service.py
│   │       │   ├── realization/      # Voicing, bass, arrangement assembly
│   │       │   │   ├── voicing.py
│   │       │   │   ├── bass.py
│   │       │   │   ├── assembly.py
│   │       │   │   └── service.py
│   │       │   ├── evaluation/       # Scoring, ranking, Pareto
│   │       │   │   ├── theory.py
│   │       │   │   ├── voice_leading.py
│   │       │   │   ├── register_density.py
│   │       │   │   ├── playability.py
│   │       │   │   ├── groove.py
│   │       │   │   ├── melody_harmony.py
│   │       │   │   ├── aggregate.py
│   │       │   │   ├── ranking.py    # Pareto + diversity + weighted
│   │       │   │   └── service.py
│   │       │   └── intent/           # Prompt parsing, feedback interpretation
│   │       │       ├── parser.py
│   │       │       ├── feedback.py   # Feedback → ObjectiveWeights adjustment
│   │       │       └── service.py
│   │       ├── models/               # Pydantic v2 canonical object model
│   │       │   ├── base.py           # BaseEntity, Candidate, Evaluation interfaces
│   │       │   ├── session.py        # Session, SessionContext, CreativeBrief
│   │       │   ├── style.py          # GenreProfile, GenreRule, AntiPattern, HarmonicGrammar
│   │       │   ├── harmony.py        # ProgressionCandidate, ProgressionFamily, RomanNumeralAnalysis, ChordEvent
│   │       │   ├── realization.py    # ArrangementCandidate, ArrangementFamily, VoicingPlan, BassLine
│   │       │   ├── evaluation.py     # EvaluationBundle, all evaluation types, AggregateScorecard, ObjectiveWeights
│   │       │   ├── search.py         # SearchPlan, SearchRound, MutationRecord, ParetoFrontSnapshot, FinalSelection
│   │       │   ├── memory.py         # PatternLibraryEntry, UserPreferenceProfile, UserFeedbackEvent
│   │       │   └── export.py         # CandidateExplanation, ComparisonView, RenderArtifact, ExportPackage
│   │       ├── adapters/             # External integrations
│   │       │   ├── music21_adapter.py  # Thin wrapper: Roman numeral, intervals, chord parsing
│   │       │   └── gemini.py           # Gemini client: Pro + Flash model routing
│   │       ├── graph/                # Neo4j repository layer
│   │       │   ├── repository.py     # Base repository with common CRUD
│   │       │   ├── session_repo.py
│   │       │   ├── candidate_repo.py
│   │       │   ├── evaluation_repo.py
│   │       │   ├── style_repo.py
│   │       │   ├── memory_repo.py
│   │       │   ├── schema.py         # Cypher constraints, indexes
│   │       │   └── migrations/       # Schema migration scripts
│   │       └── export/               # MIDI generation, artifact packaging
│   │           ├── midi.py           # pretty_midi integration
│   │           ├── json_export.py
│   │           └── service.py
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── conftest.py
│   ├── pyproject.toml                # uv, ruff, mypy config
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/               # Reusable UI components
│   │   │   ├── CandidateCard.tsx
│   │   │   ├── PianoRoll.tsx
│   │   │   ├── ScoreBar.tsx
│   │   │   ├── PlaybackControls.tsx
│   │   │   └── PromptBar.tsx
│   │   ├── views/                    # Page-level views
│   │   │   ├── Dashboard.tsx
│   │   │   ├── SessionWorkspace.tsx
│   │   │   ├── CandidateDetail.tsx
│   │   │   └── ComparisonView.tsx
│   │   ├── stores/                   # Zustand state management
│   │   │   ├── sessionStore.ts
│   │   │   ├── candidateStore.ts
│   │   │   └── playbackStore.ts
│   │   ├── services/                 # API client, SSE
│   │   │   ├── api.ts
│   │   │   └── sse.ts
│   │   ├── audio/                    # Tone.js playback engine
│   │   │   └── player.ts
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   └── vite.config.ts
├── product_documents/                # Existing product docs
├── docs/
│   └── superpowers/
│       └── specs/
├── docker-compose.yml                # Neo4j + backend + frontend dev
├── Makefile                          # dev commands: start, test, lint, sync-genres
└── .gitignore
```

---

## 4. LangGraph Engine

### 4.1 Exploration State

```python
class ExplorationState(TypedDict):
    # Session context
    session_id: str
    session_context: SessionContext
    creative_brief: CreativeBrief
    genre_profile: GenreProfile
    harmonic_grammar: HarmonicGrammar
    objective_weights: ObjectiveWeights
    user_preference_profile: UserPreferenceProfile | None

    # Memory (loaded before generation)
    prior_patterns: list[PatternLibraryEntry]
    feedback_history: list[UserFeedbackEvent]

    # Generation outputs
    progression_candidates: list[ProgressionCandidate]
    top_progressions: list[ProgressionCandidate]
    arrangement_candidates: list[ArrangementCandidate]

    # Evaluation outputs
    progression_evaluations: list[EvaluationBundle]
    arrangement_evaluations: list[EvaluationBundle]
    pareto_front: ParetoFrontSnapshot | None

    # Search control
    search_plan: SearchPlan
    mutation_records: list[MutationRecord]
    round_number: int
    generation_mode: str  # conservative | balanced | exploratory
    stop_condition_met: bool
    random_seed: int | None  # For reproducible rounds (PRD 17.2)
```

### 4.2 Graph Flow

```
parse_intent
    → load_genre
    → load_memory
    → generate
    → evaluate_progressions
    → select_top_progressions
    → realize
    → evaluate_arrangements
    → rank_and_select
    → check_stop
        → if not met: mutate → evaluate_progressions (loop back)
        → if met: persist_round → END
```

### 4.3 Generation Modes

The `generation_mode` field in `ExplorationState` controls candidate diversity and risk:

| Mode | Candidates (N) | Top Selection (K) | Behavior |
|---|---|---|---|
| **conservative** | 8 | 3 | Stick close to genre archetype progressions. Low harmonic deviation tolerance. Prioritize genre_fit and loopability. |
| **balanced** | 12 | 4 | Mix of archetypal and moderately adventurous options. Default mode. |
| **exploratory** | 16 | 6 | Push toward the edges of the genre's experimentation envelope. Higher novelty weight, relax genre_fit floor. |

These defaults come from `SearchPlan`. Users can toggle mode in the UI prompt bar. The mode adjusts both candidate count and the diversity constraint in `select_top_progressions`.

### 4.4 SearchPlan Lifecycle

A `SearchPlan` is created automatically during session creation (`POST /v1/sessions`). Default values are loaded from genre-specific configuration:

```python
SearchPlan(
    search_strategy="beam_plus_mutation",
    initial_generation_count=12,        # N, overridden by generation_mode
    progression_selection_count=4,       # K, overridden by generation_mode
    arrangement_selection_count=4,
    max_rounds=4,
    mutation_budget_per_round=6,
    diversity_target=0.65,
    stop_conditions=StopConditions(
        target_score=8.5,               # Tunable per genre
        max_rounds=4,
    ),
    random_seed=None,                    # Set for reproducible rounds
)
```

The SearchPlan is persisted to Neo4j as `(Session)-[:USES_SEARCH_PLAN]->(SearchPlan)`. It can be updated via feedback-driven adjustments but is not directly editable by the user in v1.

### 4.5 Conditional Entry Points (System Modes)

**MVP modes:**

- **Full exploration** (default): User provides a prompt. All nodes execute.
- **Realization mode**: User provides chords as chord symbols (e.g., "Amaj7 → C#m7 → Dmaj9 → Dm6"). The system parses these into a `ProgressionCandidate` via `parse_intent`, then runs `load_genre → load_memory → realize → evaluate_arrangements → rank_and_select → check_stop`. Skips `generate`, `evaluate_progressions`, and `select_top_progressions`.

**Deferred modes (v1.5):**

- **Reharm mode**: User provides melody. Enters at `generate` with melody conditioning.
- **Comparative lab mode**: Same idea run through multiple genre profiles in parallel.
- **Retrieval-assisted mode**: Prior patterns seeded into generation.

### 4.6 Node Details

| Node | Responsibility | Gemini Model | Domain Service |
|---|---|---|---|
| `parse_intent` | Extract constraints + soft preferences from prompt. If feedback exists, produce adjusted ObjectiveWeights. | Flash | `intent.parser`, `intent.feedback` |
| `load_genre` | Load GenreProfile, HarmonicGrammar, GenreRules, AntiPatterns from Neo4j | None (data fetch) | `style.service` |
| `load_memory` | Load UserPreferenceProfile, prior successful patterns for this genre, feedback history | None (data fetch) | `memory_repo` |
| `generate` | Produce N ProgressionCandidates (N from SearchPlan/generation_mode). Use genre profile, grammar, constraints. Warm-start from prior patterns if available. | Pro | `harmony.generator` |
| `evaluate_progressions` | Score progressions on theory dimensions (genre_fit, theoretical_coherence, cadence_quality, novelty, loopability, emotional_fit). Hybrid: deterministic checks + Gemini scoring. | Flash | `evaluation.theory` |
| `select_top_progressions` | Filter to top K progressions (K from SearchPlan/generation_mode) by score + diversity. Discard weak candidates before realization. | None (deterministic) | `evaluation.ranking` |
| `realize` | For each top progression: generate VoicingPlan + BassLine. Assemble ArrangementCandidates. | Pro | `realization.voicing`, `realization.bass`, `realization.assembly` |
| `evaluate_arrangements` | Full scorecard: theory + voice leading + register/density + playability. Hybrid scoring. | Flash | `evaluation.service` |
| `rank_and_select` | Multi-objective ranking: weighted scores + Pareto front construction + diversity-aware selection. | None (deterministic) | `evaluation.ranking` |
| `check_stop` | Check: top score > threshold, diversity target met, round budget exhausted, user satisfaction estimate (see Section 11.4). | None (deterministic) | Engine logic |
| `mutate` | Apply controlled mutations to promising candidates. Track MutationRecord with source, changes, reason. | Pro | `harmony.mutator` |
| `persist_round` | Save all candidates, evaluations, mutation records, lineage to Neo4j. Update SearchRound. | None (data write) | Graph repositories |

### 4.7 Mutation Loop-Back Behavior

In v1, the mutation loop always returns to `evaluate_progressions` regardless of mutation scope. This is a deliberate simplification:

- **Harmonic mutations** (chord substitution, cadence change): Loop-back to `evaluate_progressions` is correct — the progression itself changed.
- **Arrangement mutations** (bass line, voicing): Loop-back to `evaluate_progressions` causes unnecessary re-evaluation of unchanged progressions. This is acceptable in v1 because rounds are bounded by `max_rounds` and the extra evaluation is cheap (Gemini Flash).

**Future optimization (M3+):** Add conditional routing based on `MutationRecord.mutation_scope`. If scope is arrangement-only, loop back to `realize` or `evaluate_arrangements` directly.

### 4.8 Feedback → Reweighting Flow

1. User submits feedback via chat sidebar (e.g., "bass is too busy, voicings should be more open")
2. `POST /v1/candidates/:id/feedback` → Gemini Flash interprets feedback into two outputs:
   - `interpreted_adjustments`: semantic map (e.g., `"reduce_bass_motion": true`)
   - `adjusted_weights`: numerical deltas applied to current ObjectiveWeights (e.g., `voicing_quality: +0.04, bass_line_quality: -0.02`)
3. Gemini Flash produces both forms in a single structured output call. The semantic form is stored for explainability; the numerical form is applied to weights.
4. The system creates a new `ObjectiveWeights` by applying deltas to the current weights, then renormalizing to sum to 1.0.
5. Users cannot manually override auto-computed weights in v1. If the auto-adjustment feels wrong, they can submit follow-up feedback.
6. Next round's `parse_intent` node loads the adjusted weights into `ExplorationState`.
7. Evaluation and ranking nodes use the new weights.

---

## 5. Domain Model

### 5.1 Shared Interfaces

```python
class BaseEntity(BaseModel):
    id: str
    type: str
    created_at: datetime
    updated_at: datetime
    version: int = 1
    status: str
    metadata: dict[str, Any] = {}

class CandidateBase(BaseEntity):
    session_id: str
    family_id: str | None
    intent_tags: list[str] = []
    rationale: str
    mutation_lineage_ids: list[str] = []
    warnings: list[str] = []

class EvaluationBase(BaseEntity):
    candidate_id: str
    evaluation_type: str
    notes: list[str] = []
```

### 5.2 MVP Pydantic Models

**Intent/Session family:**
- `Session` — top-level container for one exploration run
- `SessionContext` — dynamic in-session state (active phase, current round, search budget, stop condition state)
- `CreativeBrief` — normalized user intent (genre, mood, key, bars, complexity, novelty, constraints, generation_mode)
- `UserPreferenceProfile` — persistent user taste model (complexity band, voicing preferences, genre biases)
- `ObjectiveWeights` — configurable scoring weights per dimension

**Style/Rule family:**
- `GenreProfile` — harmonic, voicing, bass, groove tendencies + experimentation envelope
- `GenreRule` — individual reusable rule with weight and applicability conditions
- `AntiPattern` — pattern that breaks genre identity with severity score
- `HarmonicGrammar` — chord qualities, borrowed chords, cadence archetypes, harmonic rhythm defaults

**Musical Generation family:**
- `ProgressionCandidate` (extends CandidateBase) — chord_events as JSON array, generator_mode, source_type
- `ProgressionFamily` — groups related harmonic variants with root member
- `RomanNumeralAnalysis` — per-chord Roman numeral interpretation with confidence
- `ChordEvent` — bar, beat, duration, symbol, function_label (embedded in ProgressionCandidate, not a node)
- `ArrangementCandidate` (extends CandidateBase) — links to progression, voicing plan, bass line
- `ArrangementFamily` — groups related arrangement variants
- `VoicingPlan` — instrument, global strategy, density, register, voicing_events as JSON array
- `BassLine` — style mode, contour type, rhythmic density, note_events as JSON array

**Evaluation/Search family:**
- `EvaluationBundle` — groups all evaluations for one candidate
- `TheoryEvaluation` (extends EvaluationBase) — genre_fit, emotional_fit, theoretical_coherence, cadence_quality, novelty, loopability
- `VoiceLeadingEvaluation` (extends EvaluationBase) — smoothness, common_tone_retention, awkward_leap_penalty, resolution_quality
- `RegisterDensityEvaluation` (extends EvaluationBase) — register_balance, mud_risk, overcrowding_risk, spacing_quality
- `PlayabilityEvaluation` (extends EvaluationBase) — piano_playability, guitar_playability, ensemble_playability
- `GrooveEvaluation` (extends EvaluationBase) — groove_authenticity, rhythmic_coherence, style_alignment. **Deferred to M5** (requires GroovePattern). Model defined now for forward compatibility.
- `MelodyHarmonyEvaluation` (extends EvaluationBase) — melody_support, tension_justification, collision_risk. **Conditional**: active only when melody exists. Deferred to v1.5 (reharm mode). Model defined now for forward compatibility.
- `AggregateScorecard` — weighted_total, rank_within_round, pareto_tags, per-dimension scores
- `SearchPlan` — search strategy, generation count, selection counts, max rounds, diversity target, stop conditions
- `SearchRound` — round number, input/generated/selected/eliminated candidate IDs
- `MutationRecord` — source, result, scope, changes, reason, predicted effects, actual score delta
- `ParetoFrontSnapshot` — candidate IDs on the non-dominated front, axes
- `FinalSelection` — selected candidate IDs with roles (safest, best loop, most experimental viable)

**Memory/Learning family:**
- `UserFeedbackEvent` — feedback type, content, interpreted adjustments, timestamp
- `PatternLibraryEntry` — abstracted pattern, genre, tags, success metrics (deferred to M5 but modeled now)
- `RetrievalQuery` — target store, query tags, top_k. **Deferred to M5** (retrieval-assisted mode). Model defined for forward compatibility.
- `RetrievalResult` — matched entry IDs, scores. **Deferred to M5**. Model defined for forward compatibility.

**Musical input family (stub models for forward compatibility):**
- `Melody` — source type (user_supplied | generated), note_events as JSON array, range. **Deferred to v1.5** (reharm mode). Model stubbed now so intent ingestion can accept optional melody seed.
- `InstrumentRealizationPlan` — instrument roles, orchestration notes. **Deferred to M5** (instrument-aware voicing). Model stubbed for forward compatibility.

**Provenance family:**
- `ProvenanceTrace` — session_id, ordered list of provenance events (step, action, object_id). Tracks the full decision lineage of a session. **Active in M4** alongside CandidateExplanation.

**Presentation/Export family (M4+):**
- `CandidateExplanation` — summary, why_it_works, what_is_experimental, recommended_use_cases
- `ComparisonView` — candidate IDs, comparison axes, labels
- `RenderArtifact` — artifact type (midi/json), path, metadata
- `ExportPackage` — included candidate IDs, included artifact IDs, formats, notes

### 5.3 Contract Rules

All service/module responses include:
- `id`, `type`, `created_at`, `version`, `status`
- `rationale` — why this result was produced
- `warnings[]` — any concerns or caveats
- Domain payload

---

## 6. Neo4j Graph Schema

### 6.1 MVP Node Labels

**Core (M0-M1):**
Session, SessionContext, CreativeBrief, UserPreferenceProfile, ObjectiveWeights, SearchPlan, GenreProfile, GenreRule, AntiPattern, HarmonicGrammar, ProgressionCandidate, ProgressionFamily, RomanNumeralAnalysis

**Realization (M2):**
ArrangementCandidate, ArrangementFamily, VoicingPlan, BassLine

**Evaluation (M1+):**
EvaluationBundle, Evaluation, AggregateScorecard

Individual evaluation types are stored as a single `Evaluation` node in Neo4j with a `evaluation_type` discriminator property and `scores_json` property. This avoids graph node explosion while the Pydantic models remain fully typed per evaluation kind. Do NOT use multi-label typing for evaluation nodes — the discriminator pattern is canonical.

Evaluation type availability by milestone:
- **M1 (progression-level):** TheoryEvaluation only (genre_fit, emotional_fit, theoretical_coherence, cadence_quality, novelty, loopability)
- **M2 (arrangement-level):** + VoiceLeadingEvaluation, RegisterDensityEvaluation, PlayabilityEvaluation
- **M5:** + GrooveEvaluation (requires GroovePattern)
- **v1.5:** + MelodyHarmonyEvaluation (requires melody input / reharm mode)

**Search (M3):**
SearchRound, MutationRecord, ParetoFrontSnapshot, FinalSelection, UserFeedbackEvent

**Export (M4):**
CandidateExplanation, ComparisonView, RenderArtifact, ExportPackage, ProvenanceTrace

### 6.2 Event Storage

Musical event arrays are stored as JSON properties on parent nodes, not as separate nodes:
- `ProgressionCandidate.chord_events_json`
- `VoicingPlan.voicing_events_json`
- `BassLine.note_events_json`

Promote to first-class event nodes only if query patterns demand it (e.g., "find all arrangements where bass approaches borrowed iv by semitone").

### 6.3 Core Relationships

```
// Session ownership
(Session)-[:HAS_BRIEF]->(CreativeBrief)
(Session)-[:HAS_CONTEXT]->(SessionContext)
(Session)-[:USES_SEARCH_PLAN]->(SearchPlan)
(Session)-[:USES_OBJECTIVE_WEIGHTS]->(ObjectiveWeights)
(Session)-[:HAS_ROUND]->(SearchRound)
(Session)-[:HAS_FINAL_SELECTION]->(FinalSelection)
(Session)-[:HAS_FEEDBACK]->(UserFeedbackEvent)

// Style
(CreativeBrief)-[:TARGETS_GENRE]->(GenreProfile)
(GenreProfile)-[:USES_GRAMMAR]->(HarmonicGrammar)
(GenreProfile)-[:HAS_RULE]->(GenreRule)
(GenreProfile)-[:HAS_ANTI_PATTERN]->(AntiPattern)

// Generation + lineage (bidirectional family edges for flexible querying)
(Session)-[:GENERATED_PROGRESSION]->(ProgressionCandidate)
(Session)-[:GENERATED_ARRANGEMENT]->(ArrangementCandidate)
(ProgressionFamily)-[:HAS_MEMBER]->(ProgressionCandidate)
(ProgressionFamily)-[:ROOT_MEMBER]->(ProgressionCandidate)
(ArrangementFamily)-[:HAS_MEMBER]->(ArrangementCandidate)
(ArrangementFamily)-[:ROOT_MEMBER]->(ArrangementCandidate)
(ProgressionCandidate)-[:HAS_ANALYSIS]->(RomanNumeralAnalysis)
(ProgressionCandidate)-[:REALIZED_AS]->(ArrangementCandidate)

// Arrangement composition
(ArrangementCandidate)-[:USES_VOICING_PLAN]->(VoicingPlan)
(ArrangementCandidate)-[:USES_BASS_LINE]->(BassLine)

// Evaluation
(ProgressionCandidate)-[:HAS_EVALUATION]->(EvaluationBundle)
(ArrangementCandidate)-[:HAS_EVALUATION]->(EvaluationBundle)
(EvaluationBundle)-[:HAS_EVAL]->(Evaluation)  // type discriminated
(EvaluationBundle)-[:HAS_SCORECARD]->(AggregateScorecard)

// Mutation + lineage
(ProgressionCandidate)-[:MUTATED_INTO]->(ProgressionCandidate)
(ArrangementCandidate)-[:MUTATED_INTO]->(ArrangementCandidate)
(MutationRecord)-[:SOURCE]->(ProgressionCandidate|ArrangementCandidate)
(MutationRecord)-[:RESULT]->(ProgressionCandidate|ArrangementCandidate)
(MutationRecord)-[:APPLIES_IN_ROUND]->(SearchRound)

// Search rounds
(SearchRound)-[:INPUT_CANDIDATE]->(ProgressionCandidate|ArrangementCandidate)
(SearchRound)-[:GENERATED]->(ProgressionCandidate|ArrangementCandidate)
(SearchRound)-[:SELECTED]->(ProgressionCandidate|ArrangementCandidate)
(SearchRound)-[:ELIMINATED]->(ProgressionCandidate|ArrangementCandidate)

// Selection
(FinalSelection)-[:SELECTS {role}]->(ArrangementCandidate)

// Feedback
(UserFeedbackEvent)-[:ABOUT]->(ProgressionCandidate|ArrangementCandidate)
(UserFeedbackEvent)-[:UPDATES]->(UserPreferenceProfile)

// Provenance (M4)
(Session)-[:HAS_PROVENANCE]->(ProvenanceTrace)

// Export (M4)
(CandidateExplanation)-[:EXPLAINS]->(ProgressionCandidate|ArrangementCandidate)
(ComparisonView)-[:COMPARES]->(ArrangementCandidate)
(RenderArtifact)-[:RENDERS]->(ArrangementCandidate)
(ExportPackage)-[:INCLUDES]->(RenderArtifact)
(ExportPackage)-[:INCLUDES_CANDIDATE]->(ArrangementCandidate)
```

### 6.4 Multi-Label Strategy

Use multi-labels for broader queries:
- `(:ProgressionCandidate:Candidate)`
- `(:ArrangementCandidate:Candidate)`
- `(:GenreRule:Rule)`, `(:AntiPattern:Rule)`

Note: Evaluation nodes use a single `Evaluation` label with a `evaluation_type` property discriminator (see Section 6.1). Do not apply multi-labels to evaluation nodes.

---

## 7. Genre System

### 7.1 Authoring Surface

Genre profiles, rules, and grammars are authored as YAML files in the repository. YAML is readable, diffable, and version-controlled. A producer or music theorist can author/review without touching Python.

### 7.2 File Structure

```
domain/style/
├── genres/
│   ├── dream_pop.yaml
│   ├── synthwave.yaml
│   └── cinematic.yaml
├── rules/
│   ├── dream_pop_rules.yaml
│   ├── synthwave_rules.yaml
│   └── cinematic_rules.yaml
├── grammars/
│   ├── dream_pop_grammar.yaml
│   ├── synthwave_grammar.yaml
│   └── cinematic_grammar.yaml
├── loader.py         # Validates YAML against Pydantic, syncs to Neo4j
└── schema.py         # Pydantic models for genre data
```

### 7.3 Sync Mechanism

On app startup or via CLI (`explorator sync-genres`), the loader:
1. Reads all YAML files
2. Validates against Pydantic models in `schema.py`
3. Upserts to Neo4j (MERGE on genre_profile_id)
4. Reports validation errors, skips invalid files

### 7.4 Genre Research Agent Loop

An agentic workflow that bootstraps new genre profiles from research. Given a genre name and optional reference artists, it:

```
1. RESEARCH (Gemini Pro)
   - Query for harmonic, voicing, bass, rhythmic characteristics
   - Typical devices and anti-patterns
   - Reference artists and historical context

2. DRAFT (Gemini Pro + structured output)
   - Synthesize research into candidate GenreProfile
   - Validates against schema.py

3. CRITIQUE (Gemini Pro, fresh context)
   - Musical accuracy, genre specificity, completeness
   - Internal consistency (anti-patterns vs rules)
   - Distinctiveness from existing genres

4. REFINE (Gemini Pro, max 2 loops)
   - Apply critique, re-validate
   - Stop when no material issues remain

5. VALIDATE (deterministic)
   - Pydantic schema validation
   - Weight range checks
   - Uniqueness check vs existing profiles

6. OUTPUT
   - Genre YAML, rules YAML, grammar YAML → drafts/ directory
   - Research log (markdown with sources/reasoning)
   - Critique trail (for human review transparency)
   - Status: PENDING HUMAN REVIEW
```

Draft files land in `genres/drafts/<genre_name>/`. A human reviews and promotes to active by moving files to the main directories.

CLI: `explorator research-genre "trap-soul" --references "Bryson Tiller, 6LACK"`

---

## 8. API Surface

### 8.1 Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/v1/sessions` | Create session with initial prompt |
| GET | `/v1/sessions` | List sessions (dashboard) |
| GET | `/v1/sessions/:id` | Session detail + current context |
| POST | `/v1/sessions/:id/rounds` | Trigger a generation round |
| GET | `/v1/sessions/:id/rounds/:rid/events` | SSE stream for round progress |
| GET | `/v1/sessions/:id/candidates` | List candidates (filterable by type, round, status) |
| GET | `/v1/candidates/:id` | Full candidate detail + evaluation + lineage |
| POST | `/v1/candidates/:id/feedback` | Submit natural language feedback |
| POST | `/v1/candidates/:id/mutate` | Trigger targeted mutation |
| POST | `/v1/sessions/:id/export` | Export selected candidates |
| GET | `/v1/genres` | List available genre profiles |

### 8.2 SSE Event Flow

During a generation round, the SSE stream emits:

```
event: node_started
data: {"node": "parse_intent", "round": 1}

event: node_completed
data: {"node": "parse_intent", "brief": {...}}

event: node_started
data: {"node": "generate"}

event: candidates_preview
data: {"count": 8, "type": "progression"}

event: node_completed
data: {"node": "evaluate_progressions", "top_count": 4}

event: node_completed
data: {"node": "realize", "arrangements_count": 4}

event: node_completed
data: {"node": "rank_and_select", "top_score": 8.4}

event: round_completed
data: {"round": 1, "candidates_count": 4, "top_score": 8.4, "stop_met": false}
```

### 8.3 Feedback Response

`POST /v1/candidates/:id/feedback` returns:

```json
{
  "feedback_event_id": "fb_01",
  "interpreted_adjustments": {
    "reduce_bass_motion": true,
    "increase_voicing_openness": true
  },
  "adjusted_weights": {
    "voicing_quality": 0.14,
    "bass_line_quality": 0.05
  }
}
```

---

## 9. Frontend

### 9.1 Tech Stack

- React 18 + TypeScript
- Vite for build/dev
- Tailwind CSS for styling (dark theme, producer-oriented aesthetic)
- TanStack Query for API state management
- Zustand for client-side UI state
- Tone.js for MIDI playback

Note: The frontend-design skill will be invoked during implementation for detailed UI design.

### 9.2 View Structure

```
/ (Dashboard)
├── Session list — past explorations, status, genre tags
├── Quick-start — "New Exploration" prompt modal

/session/:id (Session Workspace) — primary view
├── Header — session name, genre badge, round counter, generation_mode toggle
├── Prompt Bar — text input + constraint controls (key, bars, complexity, novelty)
├── Candidate Area:
│   ├── Grid View (default) — card tiles with mini scorecards, tags, overall score
│   └── Detail View — list + piano roll split panel
├── Action Bar — "Generate Round", "Export Selected", "Compare"
├── Chat Sidebar (collapsible) — feedback refinement
│   └── Shows interpreted adjustments after each message

/session/:id/candidate/:cid (Candidate Detail)
├── Piano roll visualization
├── Full scorecard (all dimensions as bar charts)
├── Chord symbols + Roman numeral analysis
├── Lineage tree (mutation history)
├── Playback controls
├── "Mutate" and "Export" actions

/session/:id/compare (Comparison View)
├── Side-by-side 2-3 candidates
├── Score overlay chart
├── Diff highlighting (what changed between mutations)
```

### 9.3 Playback

- Backend sends MIDI note data as JSON (pitch, start, duration, velocity per voice)
- Frontend renders through Tone.js: PolySynth for chords, MonoSynth for bass
- Play/pause/scrub controls per candidate
- No .mid file needed for browser playback — only for export

### 9.4 Real-Time Updates

SSE from FastAPI during generation rounds. Frontend shows progress indicator as each LangGraph node completes.

---

## 10. Adapters

### 10.1 music21 Adapter

Thin wrapper exposing only the specific music21 functions needed:

- `analyze_roman_numerals(key, chords) → RomanNumeralAnalysis`
- `check_voice_leading(voicing_a, voicing_b) → VoiceLeadingMetrics`
- `calculate_intervals(pitch_a, pitch_b) → IntervalInfo`
- `parse_chord_symbol(symbol) → ChordInfo`
- `check_register_density(voicing) → RegisterDensityMetrics`

Pydantic models are the source of truth. music21 objects are created transiently for computation and immediately converted back to Pydantic types. No music21 types leak into domain services.

### 10.2 Gemini Client

Routes requests to the appropriate model:

- `gemini-flash-latest` — structured extraction, scoring, high-volume evaluation
- `gemini-pro-latest` — creative generation, mutation planning, explanation synthesis

All Gemini calls use Pydantic models for structured output schemas.

---

## 11. Evaluation Framework

### 11.1 Scoring Dimensions

**Harmonic domain (progression-level):**
- Genre fit
- Emotional fit
- Theoretical coherence
- Cadence quality
- Novelty
- Loopability

**Realization domain (arrangement-level):**
- Voicing quality (smoothness, top-voice continuity)
- Voice leading quality
- Bass line quality
- Register/density balance
- Playability (piano, guitar, ensemble)

**Conditional:**
- Melody-harmony compatibility (only when melody exists)
- Groove authenticity (active when groove pattern exists, deferred to M5)

### 11.2 Hybrid Evaluation Strategy

- **Deterministic first:** Range checks, spacing heuristics, cadence classification, density thresholds, playability constraints, conflict detection
- **Model-assisted second:** Genre-fit judgment, emotional-fit interpretation, novelty estimation, anti-pattern plausibility checks (Gemini Flash)
- **Never sole authority:** LLM scores are one input among deterministic scorers. Never the sole ranking authority.

### 11.3 Ranking Strategy

These are sequential steps applied in order:

1. **Weighted sum** — Compute a single scalar per candidate using ObjectiveWeights. This is the primary ranking signal.
2. **Pareto front** — After weighted scoring, identify non-dominated candidates across key axes (genre_fit, novelty, loopability, playability). Candidates on the Pareto front are preserved even if their weighted sum is lower.
3. **Diversity penalty** — Among the top-N candidates (weighted + Pareto survivors), penalize near-duplicates. Diversity is measured by edit distance on chord symbols + Euclidean distance in score space.
4. **Final selection roles** — From the diverse finalist set, assign roles:
   - **Safest:** Highest weighted sum with genre_fit above 8.0
   - **Best loop:** Highest loopability score
   - **Most experimental viable:** Highest novelty with weighted_total above 7.0 floor

### 11.4 Stop Conditions

Stop conditions are checked after each round. The round ends when ANY condition is met:

- **Quality threshold:** Top candidate weighted_total exceeds a configurable threshold (default: 8.5, tunable per genre via SearchPlan)
- **Diversity sufficient:** At least 3 candidates on the Pareto front with pairwise edit distance > 2 chord changes
- **Budget exhausted:** Round count exceeds `SearchPlan.max_rounds` (default: 4). When budget is exhausted, the system returns the best available candidates regardless of quality threshold.
- **User satisfaction:** If the user has submitted positive feedback on a candidate (e.g., selected, starred), the system can terminate early. Inferred from feedback history, not a heuristic.

---

## 12. Infrastructure

### 12.1 Docker Compose (Development)

```yaml
services:
  neo4j:
    image: neo4j:5-community
    ports: ["7474:7474", "7687:7687"]
    environment:
      NEO4J_AUTH: neo4j/explorator_dev
    volumes:
      - neo4j_data:/data

  backend:
    build: ./backend
    ports: ["8000:8000"]
    depends_on: [neo4j]
    environment:
      NEO4J_URI: bolt://neo4j:7687
      GEMINI_API_KEY: ${GEMINI_API_KEY}
    volumes:
      - ./backend/src:/app/src
      - ./artifacts:/app/artifacts

  frontend:
    build: ./frontend
    ports: ["5173:5173"]
    volumes:
      - ./frontend/src:/app/src
```

### 12.2 Artifact Storage

MIDI files and export bundles stored on local filesystem at `./artifacts/`. Path structure:

```
artifacts/
├── sessions/
│   └── <session_id>/
│       ├── midi/
│       │   └── <candidate_id>.mid
│       └── exports/
│           └── <export_package_id>/
```

---

## 13. Milestone Roadmap

### M0 — Foundations

**Deliverables:**
- Monorepo scaffold: uv + ruff + mypy, Vite + Tailwind
- Docker Compose: Neo4j + backend + frontend dev
- Pydantic canonical models (BaseEntity, CandidateBase, EvaluationBase + all MVP models)
- Neo4j schema: constraints, indexes, Cypher skeleton
- Genre YAML loader + 3 curated genre profiles (dream pop, synthwave, cinematic)
- FastAPI skeleton with session CRUD
- React SPA skeleton with routing and Tailwind dark theme
- Gemini client with Pro/Flash routing

**Exit criteria:** Can create a session, load a genre profile from YAML into Neo4j, see the session in the frontend dashboard.

### M1 — Harmonic MVP

M1 is progression-only. The LangGraph engine runs a partial flow that stops before realization. No voicings, bass lines, or arrangements yet.

**LangGraph flow for M1:** `parse_intent → load_genre → generate → evaluate_progressions → select_top_progressions → persist_round`

Note: `load_memory`, `realize`, `evaluate_arrangements`, `rank_and_select`, `check_stop`, and `mutate` nodes are stubbed or absent in M1. They are added in M2 and M3 respectively.

**Deliverables:**
- Intent parsing (Gemini Flash → CreativeBrief)
- LangGraph engine with M1 partial flow (see above)
- Harmony service: progression generation + Roman numeral analysis
- music21 adapter: Roman numeral analysis, chord parsing
- TheoryEvaluation only (genre fit, coherence, cadence, novelty, loopability, emotional fit)
- ObjectiveWeights with default profiles per genre
- Candidate card grid in frontend (showing progression candidates, not arrangements)
- SSE progress stream
- Generation mode control (conservative/balanced/exploratory)

**Exit criteria:** User can prompt for genre-specific progressions and see ranked results with Roman numeral analysis and theory scores in the UI. No playback, no voicings, no bass lines.

### M2 — Realization MVP

M2 extends the LangGraph flow to include realization and arrangement-level evaluation.

**LangGraph flow for M2:** `parse_intent → load_genre → generate → evaluate_progressions → select_top_progressions → realize → evaluate_arrangements → rank_and_select → persist_round`

Note: `check_stop` and `mutate` are still absent — single-round only. Added in M3.

**Deliverables:**
- Voicing generation (Gemini Pro + validation)
- Bass line generation (hybrid: rule templates + Gemini Pro)
- Arrangement assembly (combine progression + voicing + bass into ArrangementCandidate)
- Arrangement-level evaluations: VoiceLeadingEvaluation, RegisterDensityEvaluation, PlayabilityEvaluation
- `rank_and_select` node with weighted scoring (Pareto + diversity added in M3)
- Detail view with piano roll
- Tone.js basic playback (PolySynth + MonoSynth)
- Realization mode (user provides chords, skip generation)

**Exit criteria:** User can explore multiple realizations of a progression, see full scorecards, and hear basic playback.

### M3 — Guided Search

M3 completes the full iterative LangGraph loop.

**LangGraph flow for M3:** Full flow as defined in Section 4.2 including `load_memory`, `check_stop`, and `mutate` with loop-back.

**Deliverables:**
- Mutation engine (Gemini Pro + controlled mutations)
- `check_stop` node with configurable stop conditions (see Section 11.4)
- `mutate` node with loop-back to `evaluate_progressions`
- `load_memory` node (load feedback history + user preference profile)
- Feedback ingestion via chat sidebar
- Feedback → ObjectiveWeights reweighting (see Section 4.5)
- Pareto front construction + diversity-aware ranking
- Lineage tracking in Neo4j (MutationRecord, family relationships, MUTATED_INTO edges)

**Exit criteria:** User can refine candidates over multiple rounds with natural language feedback, see mutation lineage, and get diverse finalists.

### M4 — Export and Explanation

**Deliverables:**
- MIDI export via pretty_midi
- JSON export bundles
- CandidateExplanation generation (Gemini Pro)
- Comparison view (side-by-side with score overlay)
- RenderArtifact and ExportPackage persistence
- Session provenance trace

**Exit criteria:** User can export finalists as MIDI for Ableton with clear rationale, and compare candidates side-by-side.

### M5 — Expanded Musical Surface

**Deliverables:**
- Melodic complement generation
- Groove pattern generation
- Genre research agent (agentic YAML authoring loop)
- PatternLibraryEntry storage and retrieval
- Retrieval-assisted warm starts

**Exit criteria:** System supports fuller arrangement exploration and self-expanding genre knowledge.

---

## 14. Intentional Deferrals

| Feature | Source | Deferred To | Reason |
|---|---|---|---|
| MelodicComplement | FuncSpec 6.7 | M5 | Phase 2 per spec |
| GroovePattern | FuncSpec 6.9 | M5 | Phase 2 per spec |
| InnerVoicePlan | FuncSpec 6.8 | M5 | Optional per genre |
| Reharm mode | FuncSpec 5.3 | v1.5 | Requires melody ingestion pipeline |
| Comparative lab mode | FuncSpec 5.4 | v1.5 | Requires multi-genre parallel runs |
| MusicXML export | FuncSpec 6.15 | M5+ | Phase 2 per spec |
| Vector retrieval | FuncSpec 8.3 | M5 | Graph-only retrieval for MVP |
| Audio/MIDI evaluator | Architecture L5 | Phase 3 | Per architecture doc |
| Instrument-aware voicing | FuncSpec 6.5 | M2+ | Start simple, refine later |
| Corpus-derived style priors | PRD 8.3 | Phase 3 | Curated profiles first |
| DAW integration | PRD 8.3 | Phase 3 | MIDI export covers v1 |
| Collaborative sessions | PRD 8.3 | Phase 3 | Single user for v1 |
| Melody entity (active use) | CanonicalObjectModel 5.10 | v1.5 | Requires reharm mode; model stubbed now for optional seed input |
| InstrumentRealizationPlan (active use) | CanonicalObjectModel 5.13 | M5 | Requires instrument-aware voicing; model stubbed now |
| RetrievalQuery / RetrievalResult | CanonicalObjectModel 7.3-7.4 | M5 | Requires full retrieval subsystem; models defined for forward compatibility |

---

## 15. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Over-coupling to music21 | Thin adapter layer; Pydantic models are source of truth; music21 objects never leak into domain |
| Overly subjective LLM ranking | Hybrid scoring: deterministic first, LLM as contributor not sole arbiter |
| Genre stereotype rigidity | Separate hard rules from soft priors; experimentation envelope; user feedback correction |
| Graph over-modeling | High-level nodes first; event arrays as properties; promote only on query pressure |
| LangGraph coupling | Clean state abstraction; LangGraph owns only inner loop; swappable with custom orchestrator |
| Gemini API latency | Flash for high-volume calls; Pro only for creative/nuanced; SSE keeps user informed during rounds |
| Genre research agent quality | Human gate before activation; research log for audit trail; max 2 refine loops |

---

## 16. Error Handling and Resilience

### 16.1 Gemini API Failures

| Failure Mode | Handling |
|---|---|
| **Timeout (>30s)** | Retry once with exponential backoff (2s, then 4s). If still failing, return partial results with a warning. For `generate`: return fewer candidates. For `evaluate_*`: skip LLM-assisted scoring, use deterministic scores only. |
| **Rate limit (429)** | Queue and retry with backoff. SSE emits `event: rate_limited` so the frontend shows "Waiting for API capacity..." |
| **Malformed structured output** | Validate Gemini response against Pydantic model. If validation fails, retry once with a stricter prompt. If still invalid, log the raw response and skip that candidate/evaluation with a warning. |
| **API unreachable** | After 3 retries, abort the round. Return any candidates generated so far with `status: partial`. SSE emits `event: round_error`. |

### 16.2 Neo4j Failures

| Failure Mode | Handling |
|---|---|
| **Connection refused on startup** | Backend fails to start with a clear error message. Docker healthcheck gates backend startup on Neo4j availability. |
| **Connection lost mid-round** | The `persist_round` node retries 3 times. If persistence fails, candidates remain in memory and are returned to the frontend via the API response. A warning is shown: "Results not saved — retry save or export now." |
| **Query timeout** | `load_genre` and `load_memory` have a 5s timeout. If exceeded, proceed with empty memory (no warm-start) and log a warning. |

### 16.3 music21 Failures

| Failure Mode | Handling |
|---|---|
| **Chord symbol parse failure** | If `parse_chord_symbol` fails (e.g., unrecognized notation like "Xaug#11b9"), return a validation error to the user in realization mode. In generation mode, skip the unparseable candidate and log a warning. |
| **Roman numeral analysis failure** | If `analyze_roman_numerals` fails for a candidate, store the candidate without analysis and add a warning to the `RomanNumeralAnalysis` output: "Analysis unavailable." |
| **Unexpected exception** | Catch all music21 exceptions at the adapter boundary. Never let music21 exceptions propagate into domain services. Log the full traceback and return a degraded result. |

### 16.4 LangGraph Mid-Execution Failures

If a node fails after previous nodes have succeeded:

1. All successfully-produced candidates up to the failure point are preserved in `ExplorationState`.
2. `persist_round` is called with a `status: partial` flag.
3. SSE emits `event: round_error` with the failing node name and error summary.
4. The frontend shows partial results with a "Round incomplete" banner and a "Retry" button.
5. Retry re-enters the graph at the failed node, not from the beginning.

### 16.5 Concurrency

A session allows only one active round at a time. If `POST /v1/sessions/:id/rounds` is called while a round is running, the API returns `409 Conflict` with the current round's status. The frontend disables the "Generate Round" button while a round is in progress (tracked via SSE state).

---

## 17. Operational Details

### 17.1 Authentication

v1 is single-user, local-first. No authentication is required. The API accepts all requests without auth headers. A stub auth middleware is included in `api/middleware.py` with a `TODO: implement auth` marker for future multi-user support. `UserPreferenceProfile` is scoped to a single default user.

### 17.2 ID Generation

All entity IDs use the format `{type_prefix}_{ulid}` where:
- `type_prefix` is a short string (e.g., `sess`, `prog`, `arr`, `eval`, `mut`, `fb`)
- `ulid` is a ULID (Universally Unique Lexicographically Sortable Identifier)

ULIDs are chosen over UUIDs because they are time-ordered, which makes Neo4j index scans and debugging easier. The `python-ulid` package provides generation.

### 17.3 Configuration

Configuration is managed via environment variables with Pydantic Settings:

```python
class Settings(BaseSettings):
    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "explorator_dev"

    # Gemini
    gemini_api_key: str
    gemini_pro_model: str = "gemini-pro-latest"
    gemini_flash_model: str = "gemini-flash-latest"

    # Generation defaults
    default_max_rounds: int = 4
    default_target_score: float = 8.5
    default_generation_mode: str = "balanced"

    # Timeouts
    gemini_timeout_seconds: int = 30
    neo4j_query_timeout_seconds: int = 5

    model_config = SettingsConfigDict(env_file=".env")
```

### 17.4 Testing Strategy

| Layer | Test Type | What to Test | How to Mock |
|---|---|---|---|
| Domain services | Unit tests | Pure business logic, scoring, ranking, chord parsing | No mocks needed — pure functions |
| music21 adapter | Unit tests | Adapter input/output contracts | Test with known chord inputs and expected outputs |
| Gemini adapter | Unit tests | Structured output parsing, error handling | Mock HTTP responses with recorded fixtures |
| LangGraph engine | Integration tests | Full flow execution, state transitions, node ordering | Mock Gemini adapter, use real domain services |
| Graph repository | Integration tests | Neo4j CRUD, relationship creation, queries | Use a test Neo4j container (testcontainers-python) |
| API routes | Integration tests | Request/response contracts, SSE streams, error responses | Mock engine, test HTTP layer |
| Frontend | Component tests | Candidate cards, piano roll, playback controls | Vitest + React Testing Library |
