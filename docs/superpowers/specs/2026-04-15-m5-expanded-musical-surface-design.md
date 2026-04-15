# M5 — Expanded Musical Surface: Design Spec

**Date:** 2026-04-15
**Status:** Draft
**Depends on:** M4 (complete), V1 design spec sections 12.5, 14

## 1. Overview

M5 introduces four capabilities that expand the musical surface of Explorator beyond chord progressions, voicings, and bass lines. Each sub-milestone is a vertical slice delivering backend, frontend, and E2E tests as an independently shippable unit.

| Sub-milestone | Feature | Summary |
|---------------|---------|---------|
| M5a | Groove Patterns + GrooveEvaluation | Genre-aware rhythmic templates that drive bass/voicing timing |
| M5b | Melodic Complement Generation | Single-line melody voice on top of arrangements |
| M5c | Genre Research Agent | Full in-app agentic workflow for creating new genre profiles |
| M5d | Retrieval-Assisted Warm Starts | Pattern harvesting from successful sessions + graph-based retrieval for seeding new sessions |

**Not in scope for M5:** MusicXML export (deferred to M5+), vector retrieval (graph-only for now, vector-ready design), reharm mode (v1.5), comparative lab mode (v1.5), InnerVoicePlan (deferred to M6 — melody complement covers the primary melodic gap; inner voice parts are a refinement), InstrumentRealizationPlan active use (partially addressed by genre-specific synth presets in M5b; formal instrument-aware voicing deferred to M6).

---

## 2. M5a — Groove Patterns + GrooveEvaluation

### 2.1 Purpose

The current realization pipeline places bass notes and voicing events with mechanical timing. Groove patterns introduce genre-authentic rhythmic feel — syncopation, swing, accent patterns — so that arrangements sound rhythmically alive.

### 2.2 GroovePattern Model

New entity extending `BaseEntity`. ULID prefix: `gp_`.

```
GrooveEvent(BaseModel):
  """A single rhythmic event in a groove pattern."""
  beat: float                  # beat position within the bar (1.0-based)
  duration_beats: float        # duration in beats
  velocity: int                # 0-127 MIDI velocity
  accent: bool = False         # whether this is an accented beat

GroovePattern(BaseEntity):
  # BaseEntity provides: id, type, created_at, updated_at, version, status, metadata
  session_id: str
  arrangement_candidate_id: str | None  # linked at assembly time; null during generation
  genre: str
  time_signature: str          # e.g. "4/4"
  swing_amount: float          # 0.0 (straight) to 1.0 (full swing)
  density: float               # 0.0 (sparse) to 1.0 (busy)
  pattern_events: list[GrooveEvent]
  source_template: str         # which archetype generated this
  variation_seed: int | None   # for reproducibility
```

Groove is generated per-arrangement (each arrangement candidate can have a different groove variant), not per-session. The `session_id` is for provenance; `arrangement_candidate_id` is linked at assembly time (the assembler sets it). During generation, grooves are grouped by `session_id`.

### 2.3 Generation Approach — Deterministic Templates

No LLM call needed. Rhythm is pattern-math.

**Template archetypes:**
- Straight eighths (default for most genres)
- Syncopated (off-beat emphasis)
- Dotted (long-short pattern)
- Triplet feel (shuffle/swing)
- Sparse (half notes, minimal movement)

**Genre-driven parameterization:** Each genre YAML already has `groove_tendencies` containing `comp_density`, `articulation_style`, and `syncopation_level`. The `GrooveGenerator` service:

1. Reads groove_tendencies from the genre profile
2. Selects and weights template archetypes based on tendencies
3. Applies swing_amount from genre (or derives from articulation_style)
4. Applies density from comp_density
5. Adds controlled variation (accent shifts, ghost notes) to avoid mechanical repetition
6. Outputs 1-4 GroovePattern variants per arrangement

### 2.4 Integration into Bass Generation

`BassLineGenerator` currently has hardcoded rhythmic modes (supportive, pedal, syncopated). With groove:

- The generator receives a `GroovePattern` as input
- Bass note onset positions come from `pattern_events[].beat` rather than fixed templates
- Bass note velocities follow `pattern_events[].velocity` and `accent` flags
- The existing `syncopated` mode becomes one flavor within the groove system
- Backward compatible: if no GroovePattern is provided, existing behavior is preserved

### 2.5 GrooveEvaluation Activation

The stub exists in `evaluation.py` with three dimensions:

- **groove_authenticity** (deterministic): composite score from density match, syncopation match, and swing consistency relative to genre expectations. Since groove is deterministically generated from genre parameters, LLM evaluation would be circular — this dimension uses the same deterministic approach as the other two.
- **rhythmic_coherence** (deterministic): density consistency across bars, syncopation level matches genre expectation, swing consistency.
- **style_alignment** (deterministic): compare generated groove parameters against genre template expectations — density match, syncopation level match, accent pattern similarity.

Wires into existing `EvaluationBundle` (via `groove_evaluation_id`) and `AggregateScorecard` weighted scoring. New weight entries added to `ObjectiveWeights`.

### 2.6 Pipeline Integration

New LangGraph node: `generate_groove` in `engine/nodes/generate_groove.py`. Inserts between `generate_bass` and `assemble_arrangements` in the realization subgraph. The node reads `groove_tendencies` from the genre profile in state and produces `GroovePattern` instances. `GrooveGenerator` domain service lives at `domain/realization/groove.py`.

### 2.7 Frontend Changes

- Piano roll already renders note events — groove changes the timing of those events, so rhythmic differences show up automatically in the visualization
- Add a subtle beat grid overlay to the piano roll showing groove emphasis points (accent markers on the grid)
- Comparison playback: groove differences become audible through the existing Tone.js engine — no new UI components needed, the audio engine already renders note timing as-is

### 2.8 E2E Tests (4-5 new)

- Groove pattern generated for a session
- Bass line timing influenced by groove (different from default mechanical placement)
- GrooveEvaluation scores appear in scorecard
- Groove emphasis visible in piano roll
- Backward compatibility: sessions without groove still work

---

## 3. M5b — Melodic Complement Generation

### 3.1 Purpose

Adds a single-line melody voice on top of existing arrangements. The melody fits the harmonic progression, respects the voicing register, follows genre-appropriate conventions, and aligns with the groove pattern when present.

### 3.2 MelodicComplement Model

New entity extending `BaseEntity`. ULID prefix: `mc_`.

The existing `Melody` stub in `stubs.py` (with `source_type: "user_supplied"`) is reserved for user-supplied melody input in reharm mode (v1.5). `MelodicComplement` is a separate entity for system-generated melody because: (a) it has different fields (contour_type, source_strategy, groove_pattern_id) that don't apply to user input, (b) it links to ArrangementCandidate while Melody links to Session, (c) keeping them separate avoids type-discriminator branching in the generation pipeline. The `Melody` stub remains untouched for v1.5.

```
MelodicNoteEvent(BaseModel):
  """A single note event in a melodic complement."""
  bar: int
  beat: float = 1.0             # beat position within the bar
  duration_beats: float = 1.0
  pitch: str                    # e.g. "C5"
  velocity: int = 80

MelodicComplement(BaseEntity):
  # BaseEntity provides: id, type, created_at, updated_at, version, status, metadata
  arrangement_candidate_id: str
  groove_pattern_id: str | None    # from M5a if available
  note_events: list[MelodicNoteEvent]
  range_low: str                   # e.g. "C5"
  range_high: str                  # e.g. "C6"
  contour_type: str                # "arch", "descending", "wave", "static", etc.
  source_strategy: str             # reference to the strategy that generated this
```

`ArrangementCandidate.melodic_complement_id` (already nullable in the model) gets populated when a melody is generated.

### 3.3 Generation Approach — Gemini + Deterministic Constraints

Two-phase process, same pattern as voicing generation:

**Phase 1 — Strategy (Gemini Flash):** Given chord progression, voicing register, bass range, groove pattern (if present), and genre profile, Gemini produces a `MelodicStrategyResponse`:

- Register range (stay above voicings, avoid collision zone)
- Contour direction per phrase
- Rhythmic density guidance (sparse vs. active, influenced by groove if present)
- Tension/release points relative to chord changes
- Genre-specific idioms (e.g. dream_pop: favor stepwise motion with occasional octave leaps)
- **Strong-beat targeting overrides**: the strategy can specify preferred scale degrees on strong beats (e.g. "target 7ths and 9ths" for dream_pop, "target roots and 5ths" for cinematic). This overrides the default chord-tone targeting in Phase 2.
- **Phrase structure**: phrase length (2-bar or 4-bar), motif repetition pattern (e.g. "AABA", "call-and-response"), rest placement between phrases. Without explicit phrase structure, melodies sound like a continuous stream of notes.

**Phase 2 — Realization (deterministic):** `MelodyGenerator` service takes the strategy and produces concrete pitch events. New prompt template in `prompts/melody.py` following existing `prompts/voicing.py` pattern.

**Default targeting rules** (overridable by Phase 1 strategy):
- Chord-tone targeting on strong beats (root, 3rd, 5th of current chord) — or strategy-specified scale degrees
- Passing/neighbor tones on weak beats

**Hard constraints** (not overridable):
- Range enforcement: stay within specified register, avoid voicing collision zone (no unisons or minor 2nds against voicing notes on the same beat)
- Groove alignment: when a GroovePattern is available, melodic onsets respect the beat grid (melody doesn't fight the groove). When no GroovePattern is available (M5b without M5a, or legacy sessions), the melody generator defaults to a straight-eighths beat grid.
- Resolution rules: phrases end on chord tones, final phrase resolves to tonic area
- Phrase boundaries: insert rests at phrase boundaries as specified by the strategy (or default to 4-bar phrases with quarter-rest gaps)

### 3.4 Pipeline Integration

New LangGraph node: `generate_melody` in `engine/nodes/generate_melody.py`. `MelodyGenerator` domain service at `domain/realization/melody.py`. Inserts between `generate_groove` and `assemble_arrangements`.

Full realization subgraph after M5a + M5b:

1. `plan_voicings` → VoicingPlan
2. `generate_bass` → BassLine
3. `generate_groove` → GroovePattern (M5a)
4. **`generate_melody`** → MelodicComplement (M5b)
5. `assemble_arrangements` → ArrangementCandidate (now includes groove_pattern + melodic_complement)

`ArrangementAssembler.assemble_one()` gains optional `groove_pattern: GroovePattern | None = None` and `melodic_complement: MelodicComplement | None = None` parameters (backward-compatible with `None` defaults). `assemble_family()` updated similarly.

### 3.5 MelodyHarmonyEvaluation — Conditional Activation

The stub exists with three dimensions:

- **melody_support_score** (deterministic): chord-tone ratio on strong beats, voice-leading smoothness of the melody line itself
- **tension_justification_score** (Gemini Flash): "are non-chord tones used purposefully or do they sound like wrong notes?"
- **collision_risk_score** (deterministic): count of unisons/minor 2nds between melody and voicing on the same beat

Only active when `melodic_complement_id` is non-null. No impact on melody-less arrangements.

### 3.6 Frontend Changes

- **Piano roll:** Melody renders as a distinct color lane (above voicing, visually distinct from bass). Uses a unique color from design tokens.
- **Single-arrangement playback:** Melody gets its own instrument toggle button alongside Chords/Bass in the transport bar.
- **Comparison playback:** Melody becomes a new lane with its own mute/solo in the DAW view.
- **audioStore.ts type change:** `mutedTracks` type expands from `{ voicing: boolean; bass: boolean }` to include `melody: boolean`. `toggleMute` union type gains `"melody"`. Reset function updates accordingly.
- **Melody synth preset per genre:** Data-driven from genre YAML (new `melody_preset` field under a `playback_hints` section in the genre profile) so that M5c-created genres get their own preset without frontend code changes. Existing genres ship with defaults: dream_pop: soft pad lead, synthwave: saw lead, cinematic: legato strings. `audioPresets.ts` reads the preset name from the arrangement data and maps to Tone.js synth parameters.

### 3.7 E2E Tests (5-6 new)

- Melody generated as part of realization
- Melody renders in piano roll as distinct lane
- Melody playback toggle in single-arrangement view
- Melody mute/solo in comparison view
- Melody register avoids voicing collision zone
- MelodyHarmonyEvaluation scores appear when melody present

---

## 4. M5c — Genre Research Agent

### 4.1 Purpose

A full in-app workflow for creating new genre profiles. The user requests a genre from the web UI, an agentic loop researches and drafts the YAML files, the user reviews and approves in-app, and the approved genre syncs to Neo4j.

### 4.2 Agentic Loop — 6 Steps

1. **RESEARCH** (Gemini Pro): Given genre name + optional reference artists, research harmonic vocabulary, voicing conventions, bass patterns, groove tendencies, common devices, and experimentation boundaries. Produces a structured research document.

2. **DRAFT** (Gemini Pro, structured output): Synthesize research into three YAML structures matching existing Pydantic schemas — `GenreProfileYAML`, `GenreRulesYAML`, `HarmonicGrammarYAML`. Gemini outputs JSON that maps to the Pydantic models.

3. **CRITIQUE** (Gemini Pro, fresh context): Independent review of the draft for musical accuracy, internal consistency, completeness relative to existing genres, and plausible weight ranges. Produces a critique with specific actionable items. "Fresh context" means a separate LLM invocation that receives only the draft YAMLs and genre name — not the research/generation chat history — so the critique is independent and not biased by the generation rationale.

4. **REFINE** (Gemini Pro, max 2 iterations): Apply critique, regenerate draft, re-validate. If iteration 2 still has major issues, flag for human attention rather than looping forever.

5. **VALIDATE** (deterministic): Pydantic schema validation against `GenreProfileYAML` / `GenreRulesYAML` / `HarmonicGrammarYAML`. Weight range checks (all weights 0-1, experimentation envelope values sane). Catches anything the LLM got structurally wrong.

6. **OUTPUT**: Write draft YAMLs to `genres/drafts/<genre_name>/`, store research log and critique trail in Neo4j for provenance.

### 4.3 GenreResearchJob Model

Does **not** extend `BaseEntity` — it has its own lifecycle status that doesn't map to the standard `BaseEntity.status` semantics (active/archived). ULID prefix: `grj_`. Stored as a Neo4j node. Research log and critique trail are stored as JSON string properties (not separate linked nodes) since they are always read together with the job.

```
CritiqueEntry(BaseModel):
  """A single critique/refine iteration."""
  iteration: int
  critique: str
  resolution: str

GenreResearchJob(BaseModel):
  id: str                      # grj_{ULID}
  genre_name: str
  reference_artists: list[str]
  status: str                  # researching | drafting | critiquing | refining | validating | pending_review | approved | rejected
  current_step: int            # 1-6
  research_log: str            # raw research output
  critique_trail: list[CritiqueEntry]
  draft_yamls: dict            # {profile: {...}, rules: {...}, grammar: {...}}
  rejection_reason: str | None = None
  created_at: datetime
  updated_at: datetime
```

### 4.4 Backend API

All endpoints under the `/v1/` prefix, consistent with existing router registration in `app.py`. Added to a new `genre_research.router` mounted alongside the existing `genres.router`.

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/v1/genres/research` | Kick off research job (genre name, optional references). Returns 409 Conflict if genre_name matches an existing genre or an in-progress job. |
| GET | `/v1/genres/research/{job_id}` | Poll job status (JSON response) |
| GET | `/v1/genres/research/{job_id}/stream` | SSE progress stream (separate endpoint, matching existing SSE pattern in `api/sse.py`) |
| GET | `/v1/genres/drafts` | List all pending drafts |
| GET | `/v1/genres/drafts/{job_id}` | Get draft YAMLs + research log + critique trail |
| POST | `/v1/genres/drafts/{job_id}/approve` | Approve: copy drafts to `genres/`, sync to Neo4j |
| POST | `/v1/genres/drafts/{job_id}/reject` | Reject with optional reason, archive |

### 4.5 Frontend — Genre Management View

Accessible from a "Genres" nav item or settings area. State managed by a new `genreResearchStore.ts` (Zustand, following existing store-per-domain pattern).

**Genre library panel:** Shows existing genres (dream_pop, synthwave, cinematic) plus any pending drafts with their status.

**Request form:** Genre name input, optional reference artists textarea, "Research" button.

**Progress view:** Real-time SSE updates showing which step the agent is on (Researching... Drafting... Critiquing... Refining... Validating...).

**Review view:** Displays the three generated YAMLs in readable format — not raw YAML, but formatted cards showing harmonic vocabulary, groove tendencies, rules, anti-patterns, grammar. Alongside: research log and critique trail for transparency.

**Approve/Reject:** Buttons with optional feedback field on reject.

### 4.6 Scope Boundaries

- No inline YAML editing in the UI — reject with notes and re-run, or edit files manually
- No partial approval — all three YAMLs or none
- No auto-research on session creation — genre library is explicitly managed
- No genre deletion from UI in M5c — manual file removal if needed

### 4.7 E2E Tests (4-5 new)

- Request a genre research job, verify SSE progress updates
- Review a completed draft (YAMLs, research log, critique trail visible)
- Approve draft: genre appears in library and is available for session creation
- Reject draft: genre archived with reason
- New genre usable in a generation session after approval

---

## 5. M5d — Retrieval-Assisted Warm Starts

### 5.1 Purpose

The system learns from successful sessions by harvesting patterns into a library, then offers those patterns as warm starts for new sessions. Graph-based retrieval via Neo4j, designed so vector embeddings can be added later without restructuring.

### 5.2 Pattern Harvesting

**Trigger:** When a session reaches finalist selection (user picks winners), the system automatically extracts patterns from those finalists.

**Pattern types harvested:**

| Type | What's extracted |
|------|-----------------|
| progression | Chord sequence abstracted to Roman numerals + genre context |
| voicing | Register profile + density + voice count |
| bass | Bass mode + rhythmic characteristics |
| groove | Groove template parameters (M5a, if present) |
| melody | Contour type + range + density (M5b, if present) |

Each becomes a `PatternLibraryEntry` (model already exists in `memory.py`, extends `BaseEntity`). ULID prefix: `pl_`.

**Schema migration needed:** The existing stub has `source_candidate_id: str | None = None` and `notes: str`. M5d adds an `embedding: list[float] | None = None` field for vector-readiness (stays null in M5d). The `notes` field is retained. `source_candidate_id` becomes required (non-None) since patterns are always harvested from a finalist.

```
PatternLibraryEntry(BaseEntity):
  # BaseEntity provides: id, type, created_at, updated_at, version, status, metadata
  # Existing fields from stub:
  pattern_type: str            # progression | voicing | bass | groove | melody
  genre: str
  tags: list[str]              # auto-generated from musical properties
  source_candidate_id: str     # provenance (required — always harvested from a finalist)
  abstracted_pattern: dict     # the reusable pattern data
  success_metrics: dict        # evaluation scores that made this worth saving
  notes: str                   # optional context
  # New field for M5d:
  embedding: list[float] | None = None  # null for now, vector-ready
```

**Auto-tagging:** Tags are derived from musical properties:
- Progression: cadence type, loopability level, complexity
- Voicing: register (low/mid/high), density, voice count
- Bass: mode, rhythmic density
- Groove: swing level, syncopation level, density
- Melody: contour type, range width, rhythmic density

### 5.3 Retrieval — Graph Queries

`RetrievalQuery` model activates with:
- `target_store`: "pattern_library"
- `query_tags`: genre + pattern_type + optional tag filters
- `top_k`: how many results (default 5)

Implementation: Neo4j Cypher query matching `PatternLibraryEntry` nodes by genre, filtering by pattern_type and tags, ordering by `success_metrics.weighted_total` descending, limited to top_k.

**Vector-readiness (design only, not implemented in M5d):**
- `embedding` field exists but stays null
- Retrieval service uses a strategy interface: `GraphRetrieval` now, `VectorRetrieval` swappable later
- When embeddings are populated, the query path can use Neo4j vector index or an external store — swap at the strategy level without changing the API or frontend

### 5.4 Backend API

All endpoints under `/v1/`, added to a new `patterns.router`.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/v1/patterns` | List patterns with optional filters: `?genre=X&pattern_type=Y&tags=a,b` |
| GET | `/v1/patterns/{id}` | Get single pattern with provenance details |
| DELETE | `/v1/patterns/{id}` | Delete a pattern from the library |
| GET | `/v1/sessions/{id}/warm-starts` | Get warm-start suggestions for a session (by genre, returns top_k per pattern_type) |
| POST | `/v1/sessions/{id}/warm-starts` | Apply selected pattern IDs to the session's SearchPlan |

### 5.5 Warm Start Integration

On session creation, after the user selects a genre and submits their creative brief:

1. System queries the pattern library for that genre (if no matches exist, the warm-start panel simply doesn't appear — the feature degrades gracefully to "start fresh")
2. If matches exist, presents them as optional warm-start suggestions
3. User selects patterns to seed the session, or skips to start fresh
4. Selected patterns influence the SearchPlan:
   - **Progression warm start:** Seeds the first generation round with the pattern's chord sequence as an initial candidate
   - **Voicing warm start:** Sets voicing strategy defaults (register profile, density, voice count)
   - **Bass warm start:** Presets bass generation parameters (mode, rhythmic density)
   - **Groove warm start:** Uses the pattern's groove template as the starting point
   - **Melody warm start:** Presets melodic strategy (contour, range, density)

**Conflict resolution:** If the user selects multiple warm-start patterns with potentially conflicting parameters (e.g. a sparse voicing pattern and a full-density groove pattern), the patterns are applied in type order (progression → voicing → bass → groove → melody) and the generation pipeline reconciles any tension — the LLM strategy phases (voicing, melody) receive all warm-start parameters as context and produce a coherent strategy. No hard enforcement of cross-type consistency at selection time.

### 5.6 Frontend Changes

State managed by a new `patternLibraryStore.ts` (Zustand, following existing store-per-domain pattern).

**Session creation flow:** After genre selection, a "Warm Start" panel appears if relevant patterns exist in the library. Each pattern shows: type icon, tags, source genre, score summary. Toggle to select/deselect. "Start Fresh" button skips all warm starts.

**Pattern library browser:** Accessible from the Genres view or a dedicated nav item. Browse all harvested patterns with filters by genre, type, and tags. View provenance (which session produced each pattern). Delete individual patterns.

**Auto-harvest notification:** After finalist selection, a toast notification: "N patterns saved to your library" with a link to view them in the library browser.

### 5.7 E2E Tests (5-6 new)

- Pattern harvested automatically after finalist selection
- Pattern appears in library browser with correct tags
- Warm start panel appears on session creation when patterns exist
- Warm start seeds generation with pattern data
- Start fresh skips warm start
- Pattern deletion from library

---

## 6. Sequencing and Dependencies

```
M5a (Groove) ──► M5b (Melody) ──► M5d (Retrieval)
                                       ▲
M5c (Genre Agent) ─────────────────────┘
```

- **M5a before M5b:** Melody generation benefits from groove context (rhythmic alignment)
- **M5c independent:** Can run in parallel with M5a/M5b — no code dependency, just expands the genre palette
- **M5d last:** Retrieval harvests patterns from all other features. Benefits from groove and melody patterns existing.

### Estimated E2E Test Count

| Milestone | Existing | New | Total |
|-----------|----------|-----|-------|
| Pre-M5 | 24 | — | 24 |
| M5a | 24 | 4-5 | 28-29 |
| M5b | 28-29 | 5-6 | 33-35 |
| M5c | 33-35 | 4-5 | 37-40 |
| M5d | 37-40 | 5-6 | 42-46 |

---

## 7. Open GitHub Issues Addressed

- **#2 (Cadence/loopability scoring granularity):** M5a's GrooveEvaluation adds rhythmic dimensions to scoring. Cadence scoring granularity can be refined as part of the evaluation weight rebalancing when groove scores are added.
- **#3 (Implement tension_curve dimension):** Not directly addressed in M5. Remains deferred — tension_curve would fit naturally as an additional evaluation dimension in a future milestone once melody exists (M5b provides the musical context for tension analysis).
