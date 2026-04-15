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

**Not in scope for M5:** MusicXML export (deferred to M5+), vector retrieval (graph-only for now, vector-ready design), reharm mode (v1.5), comparative lab mode (v1.5).

---

## 2. M5a — Groove Patterns + GrooveEvaluation

### 2.1 Purpose

The current realization pipeline places bass notes and voicing events with mechanical timing. Groove patterns introduce genre-authentic rhythmic feel — syncopation, swing, accent patterns — so that arrangements sound rhythmically alive.

### 2.2 GroovePattern Model

New entity (activates the concept referenced in existing stubs):

```
GroovePattern:
  id: str
  session_id: str
  arrangement_candidate_id: str | None  # linked after assembly; null during generation
  genre: str
  time_signature: str          # e.g. "4/4"
  swing_amount: float          # 0.0 (straight) to 1.0 (full swing)
  density: float               # 0.0 (sparse) to 1.0 (busy)
  pattern_events: list[dict]   # [{beat: float, duration: float, velocity: float, accent: bool}]
  source_template: str         # which archetype generated this
  variation_seed: int | None   # for reproducibility
```

Groove is generated per-arrangement (each arrangement candidate can have a different groove variant), not per-session. The `session_id` is for provenance; the `arrangement_candidate_id` is the functional link.

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

- **groove_authenticity** (Gemini Flash): "does this groove feel right for the genre?" Same hybrid pattern as other evaluations.
- **rhythmic_coherence** (deterministic): density consistency across bars, syncopation level matches genre expectation, swing consistency.
- **style_alignment** (deterministic): compare generated groove parameters against genre template expectations — density match, syncopation level match, accent pattern similarity.

Wires into existing `EvaluationBundle` (via `groove_evaluation_id`) and `AggregateScorecard` weighted scoring. New weight entries added to `ObjectiveWeights`.

### 2.6 Frontend Changes

- Piano roll already renders note events — groove changes the timing of those events, so rhythmic differences show up automatically in the visualization
- Add a subtle beat grid overlay to the piano roll showing groove emphasis points (accent markers on the grid)
- Comparison playback: groove differences become audible through the existing Tone.js engine — no new UI components needed, the audio engine already renders note timing as-is

### 2.7 E2E Tests (4-5 new)

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

New entity (distinct from the `Melody` stub which is for user-supplied input in reharm mode):

```
MelodicComplement:
  id: str
  arrangement_candidate_id: str
  groove_pattern_id: str | None    # from M5a if available
  note_events: list[dict]          # [{pitch: str, onset_beat: float, duration: float, velocity: float}]
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

**Phase 2 — Realization (deterministic):** `MelodyGenerator` service takes the strategy and produces concrete pitch events:

- Chord-tone targeting on strong beats (root, 3rd, 5th of current chord)
- Passing/neighbor tones on weak beats
- Range enforcement: stay within specified register, avoid voicing collision zone (no unisons or minor 2nds against voicing notes on the same beat)
- Groove alignment: when a GroovePattern is available, melodic onsets respect the beat grid (melody doesn't fight the groove)
- Resolution rules: phrases end on chord tones, final phrase resolves to tonic area

### 3.4 Pipeline Integration

Melody generates after voicing + bass + groove (if available), before assembly:

1. `plan_voicings` → VoicingPlan
2. `generate_bass` → BassLine
3. `generate_groove` → GroovePattern (M5a, if available)
4. **`generate_melody`** → MelodicComplement (new node)
5. `assemble` → ArrangementCandidate (now includes melodic_complement)

`ArrangementAssembler` gains a `melodic_complement` input alongside voicing_plan, bass_line, and groove_pattern.

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
- **Melody synth preset per genre:** dream_pop: soft pad lead, synthwave: saw lead, cinematic: legato strings. Added to `audioPresets.ts`.

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

3. **CRITIQUE** (Gemini Pro, fresh context): Independent review of the draft for musical accuracy, internal consistency, completeness relative to existing genres, and plausible weight ranges. Produces a critique with specific actionable items.

4. **REFINE** (Gemini Pro, max 2 iterations): Apply critique, regenerate draft, re-validate. If iteration 2 still has major issues, flag for human attention rather than looping forever.

5. **VALIDATE** (deterministic): Pydantic schema validation against `GenreProfileYAML` / `GenreRulesYAML` / `HarmonicGrammarYAML`. Weight range checks (all weights 0-1, experimentation envelope values sane). Catches anything the LLM got structurally wrong.

6. **OUTPUT**: Write draft YAMLs to `genres/drafts/<genre_name>/`, store research log and critique trail in Neo4j for provenance.

### 4.3 GenreResearchJob Model

```
GenreResearchJob:
  id: str
  genre_name: str
  reference_artists: list[str]
  status: str                  # researching | drafting | critiquing | refining | validating | pending_review | approved | rejected
  current_step: int            # 1-6
  research_log: str            # raw research output
  critique_trail: list[dict]   # [{iteration: int, critique: str, resolution: str}]
  draft_yamls: dict            # {profile: {...}, rules: {...}, grammar: {...}}
  rejection_reason: str | None
  created_at: datetime
  updated_at: datetime
```

### 4.4 Backend API

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/genres/research` | Kick off research job (genre name, optional references) |
| GET | `/api/genres/research/{job_id}` | Poll status + SSE progress stream |
| GET | `/api/genres/drafts` | List all pending drafts |
| GET | `/api/genres/drafts/{job_id}` | Get draft YAMLs + research log + critique trail |
| POST | `/api/genres/drafts/{job_id}/approve` | Approve: copy drafts to `genres/`, sync to Neo4j |
| POST | `/api/genres/drafts/{job_id}/reject` | Reject with optional reason, archive |

SSE streaming for progress updates — same pattern as the existing generation pipeline.

### 4.5 Frontend — Genre Management View

Accessible from a "Genres" nav item or settings area.

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

Each becomes a `PatternLibraryEntry` (model already exists):

```
PatternLibraryEntry:
  id: str
  pattern_type: str            # progression | voicing | bass | groove | melody
  genre: str
  tags: list[str]              # auto-generated from musical properties
  source_candidate_id: str     # provenance
  abstracted_pattern: dict     # the reusable pattern data
  success_metrics: dict        # evaluation scores that made this worth saving
  embedding: list[float] | None  # null for now, vector-ready
  created_at: datetime
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

### 5.4 Warm Start Integration

On session creation, after the user selects a genre and submits their creative brief:

1. System queries the pattern library for that genre
2. If matches exist, presents them as optional warm-start suggestions
3. User selects patterns to seed the session, or skips to start fresh
4. Selected patterns influence the SearchPlan:
   - **Progression warm start:** Seeds the first generation round with the pattern's chord sequence as an initial candidate
   - **Voicing warm start:** Sets voicing strategy defaults (register profile, density, voice count)
   - **Bass warm start:** Presets bass generation parameters (mode, rhythmic density)
   - **Groove warm start:** Uses the pattern's groove template as the starting point
   - **Melody warm start:** Presets melodic strategy (contour, range, density)

### 5.5 Frontend Changes

**Session creation flow:** After genre selection, a "Warm Start" panel appears if relevant patterns exist in the library. Each pattern shows: type icon, tags, source genre, score summary. Toggle to select/deselect. "Start Fresh" button skips all warm starts.

**Pattern library browser:** Accessible from the Genres view or a dedicated nav item. Browse all harvested patterns with filters by genre, type, and tags. View provenance (which session produced each pattern). Delete individual patterns.

**Auto-harvest notification:** After finalist selection, a toast notification: "N patterns saved to your library" with a link to view them in the library browser.

### 5.6 E2E Tests (5-6 new)

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
