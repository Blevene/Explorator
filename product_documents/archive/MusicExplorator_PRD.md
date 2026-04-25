# Genre Chord Exploration and Realization System — PRD + Engineering Functional Spec

**Version**
v0.1

**Status**
Draft

**Owners**
Product:
Engineering:
Research/Music Systems:
Design:

**Last updated**
2026-03-21

---

# 2. Executive summary

Build a system that helps a user explore genre-specific musical ideas through iterative generation, realization, evaluation, and refinement.

The system should support:

* harmonic exploration
* voicing exploration
* bass-line exploration
* melodic complement exploration
* groove/accompaniment exploration
* mutation and variant search
* explainable ranking and export

The system is a **creative copilot and exploration lab**, not a fully autonomous songwriting engine.

---

# 3. Product problem statement

Musicians, producers, and researchers can ask for “dream pop chords,” “neo-soul voicings,” or “a darker bass movement,” but most generation systems either:

* return one-shot chord suggestions with little control,
* do not preserve lineage,
* cannot compare variants systematically,
* or do not separate harmonic structure from musical realization.

Users need a system that can search musical possibility space in a structured way and show why a candidate works.

---

# 4. Product vision

Create a genre-aware, explainable musical exploration engine that treats composition as a layered search problem:

* **intent**
* **style modeling**
* **harmonic generation**
* **realization**
* **evaluation**
* **selection**
* **mutation**
* **memory**

---

# 5. Goals and non-goals

## 5.1 Goals

The system must:

* translate high-level user intent into structured musical constraints
* generate multiple candidate progressions for a target genre
* realize those progressions into voicings, bass lines, complements, and groove patterns
* evaluate candidates across multi-dimensional music criteria
* preserve mutation lineage and provenance
* allow human feedback to redirect search
* export reusable symbolic artifacts

## 5.2 Non-goals

The initial system will not aim to:

* generate polished final studio productions
* replace a DAW
* perform full audio mastering or mixing
* infer every genre solely from raw audio
* model every micro-timing nuance of live performance in v1

---

# 6. Personas

## 6.1 Composer / producer

Wants multiple credible genre-aware options and fast iteration.

## 6.2 Music researcher / experimentalist

Wants structured search, explicit lineage, and analyzable outcomes.

## 6.3 Educator / theorist

Wants clear rationale, Roman numeral analysis, and comparison views.

## 6.4 Tool builder / platform integrator

Wants stable APIs, typed contracts, and exportable graph-native artifacts.

---

# 7. Primary user stories

## 7.1 Harmonic exploration

As a user, I can request progressions for a genre/mood and receive several ranked options with explanations.

## 7.2 Arrangement exploration

As a user, I can fix a progression and explore alternate voicings, bass lines, complements, and groove patterns.

## 7.3 Reharmonization

As a user, I can provide a melody and request multiple harmonic treatments.

## 7.4 Comparative style transformation

As a user, I can reinterpret the same idea across multiple genres.

## 7.5 Guided refinement

As a user, I can react in natural language and have the next search round adapt.

## 7.6 Export

As a user, I can export selected candidates as JSON, MIDI, and later MusicXML.

---

# 8. Product scope

## 8.1 In scope for v1

* prompt normalization
* curated genre profiles
* progression generation
* voicing generation
* bass generation
* arrangement assembly
* symbolic evaluation
* mutation and lineage
* graph persistence
* JSON and MIDI export
* human feedback loop

## 8.2 In scope for v1.5

* melodic complements
* groove generation
* comparison views
* retrieval-assisted warm starts

## 8.3 Later scope

* audio rendering/evaluation
* corpus-derived style priors
* DAW integration
* collaborative sessions

---

# 9. Functional requirements

## 9.1 Intent ingestion and normalization

### Requirements

The system shall:

* accept freeform text prompts
* extract deterministic constraints such as key, meter, bars, tempo hint, instrumentation, complexity, novelty
* infer soft preferences such as darker, floatier, more open, less jazzy
* preserve original wording
* support optional seed materials:

  * progression
  * melody
  * bass line
  * prior candidate ID
  * reference track metadata

### Inputs

* text prompt
* optional symbolic seed objects

### Outputs

* `CreativeBrief`
* `SessionContext`
* `ObjectiveWeights`

### Technical decision point

Use a **hybrid parser**:

* deterministic extraction for explicit fields
* model-assisted interpretation for subjective language

---

## 9.2 Genre/style modeling

### Requirements

The system shall:

* maintain structured `GenreProfile` objects
* encode harmonic, voicing, bass, and groove priors
* encode anti-patterns
* support experimentation envelopes
* support profile versioning

### Outputs

* `GenreProfile`
* `HarmonicGrammar`
* linked `GenreRule` / `AntiPattern`

### Technical decision point

Start with **curated profiles**, not fully learned profiles.

Reason:

* easier evaluation
* easier explainability
* avoids opaque style drift in early versions

---

## 9.3 Harmonic generation

### Requirements

The system shall:

* generate multiple `ProgressionCandidate` objects
* support conservative, balanced, and exploratory modes
* condition on key/mode and phrase length
* optionally condition on melody
* annotate candidates with harmonic rationale and Roman numeral analysis

### Outputs

* `ProgressionCandidate`
* `RomanNumeralAnalysis`
* `ProgressionFamily`

### Technical decision point

Use a **dual internal representation**:

* chord symbols for usability/debugging
* typed harmonic objects for transformations and evaluation

music21 is a strong fit for symbolic music analysis and score-like manipulations, but it should sit behind an internal adapter layer rather than becoming the app’s domain model directly. ([music21.org][2])

---

## 9.4 Mutation and search

### Requirements

The system shall:

* mutate harmonic and arrangement candidates
* track source/result lineage
* support iterative search rounds
* preserve both top-scoring and diverse options
* expose stop conditions

### Outputs

* `MutationRecord`
* `SearchRound`
* `ParetoFrontSnapshot`

### Technical decision point

Recommended search strategy:

* weighted scoring
* Pareto preservation
* diversity-aware finalist selection

---

## 9.5 Voicing generation

### Requirements

The system shall:

* create instrument-aware `VoicingPlan` variants
* control spacing, inversion, density, register, and top-voice continuity
* support multiple voicing families per progression

### Outputs

* `VoicingPlan`
* optional `VoicingEvent[]`

### Technical decision point

Use:

* proposal layer: heuristic or model-assisted
* validation layer: deterministic scoring and constraints

---

## 9.6 Bass-line generation

### Requirements

The system shall:

* generate bass lines aligned to progression and groove assumptions
* support supportive, pedal, syncopated, walking, and countermelodic styles
* encode relationship to harmony

### Outputs

* `BassLine`
* optional `BassNoteEvent[]`

### Technical decision point

Use hybrid generation:

* rule templates for structure
* controlled mutation/model guidance for variation

---

## 9.7 Melodic complement generation

### Requirements

The system shall:

* generate sparse fills or short counterlines
* avoid masking the main melody unless explicitly desired
* obey density and register constraints

### Outputs

* `MelodicComplement`

### Technical decision point

Generate complements after at least an initial groove/arrangement assumption exists.

---

## 9.8 Groove/accompaniment generation

### Requirements

The system shall:

* generate accompaniment patterns appropriate to genre and instrumentation
* support arpeggiated, block, broken, pulsed, and stab-based patterns
* expose density and syncopation controls

### Outputs

* `GroovePattern`

---

## 9.9 Arrangement assembly

### Requirements

The system shall:

* combine progression + voicing + bass + complement + groove into an `ArrangementCandidate`
* support partially populated arrangements
* maintain family grouping and lineage

### Outputs

* `ArrangementCandidate`
* `ArrangementFamily`

---

## 9.10 Evaluation

### Requirements

The system shall score candidates on:

* genre fit
* emotional fit
* theoretical coherence
* cadence quality
* novelty
* loopability
* voicing quality
* bass-line quality
* melodic complement quality
* groove authenticity
* playability
* register/density balance
* melody-harmony compatibility when melody exists

### Outputs

* `EvaluationBundle`
* `TheoryEvaluation`
* `VoiceLeadingEvaluation`
* `RegisterDensityEvaluation`
* `PlayabilityEvaluation`
* `GrooveEvaluation`
* `MelodyHarmonyEvaluation`
* `AggregateScorecard`

### Technical decision point

Use a **hybrid evaluator stack**:

* deterministic/rule-based where possible
* model-assisted for softer judgments
* never rely on model judgment alone for final ranking

---

## 9.11 Memory and retrieval

### Requirements

The system shall:

* store reusable successful patterns
* store user feedback and preference shifts
* support retrieval by genre, mood, tags, and abstract pattern traits
* link reused memory back into provenance

### Outputs

* `PatternLibraryEntry`
* `RetrievalQuery`
* `RetrievalResult`
* updated `UserPreferenceProfile`

---

## 9.12 Provenance and explainability

### Requirements

The system shall:

* preserve mutation lineage
* preserve search-round decisions
* preserve score deltas
* generate user-facing “why this works” explanations
* support developer/debug traces

### Outputs

* `MutationRecord`
* `ProvenanceTrace`
* `CandidateExplanation`
* `ComparisonView`

---

## 9.13 Export

### Requirements

The system shall export:

* canonical JSON
* MIDI in v1
* MusicXML later
* explanation/report bundle

pretty_midi remains a practical option for MIDI generation/manipulation, while music21 is the better fit for notation-oriented symbolic workflows and later MusicXML work. ([music21.org][2])

---

# 10. System architecture

## 10.1 Logical services

### A. API Gateway / Session API

Responsibilities:

* session creation
* prompt submission
* candidate retrieval
* feedback submission
* export requests

### B. Orchestration Service

Responsibilities:

* manage workflow state
* call generator/evaluator modules
* coordinate rounds and stop conditions

### C. Style Service

Responsibilities:

* genre profile retrieval
* rule/anti-pattern lookup
* experimentation envelope access

### D. Harmony Service

Responsibilities:

* progression generation
* Roman numeral analysis
* harmonic mutation

### E. Realization Service

Responsibilities:

* voicing generation
* bass-line generation
* complement generation
* groove generation
* arrangement assembly

### F. Evaluation Service

Responsibilities:

* deterministic scoring
* model-assisted scoring
* aggregate score generation
* Pareto tagging

### G. Graph Persistence Service

Responsibilities:

* Neo4j reads/writes
* lineage/provenance storage
* candidate family storage
* pattern memory storage

### H. Export Service

Responsibilities:

* MIDI creation
* artifact packaging
* download manifest generation

---

# 11. Service boundaries and ownership

## API Gateway

Owns:

* request validation
* auth/session boundary
* response shaping

## Orchestration Service

Owns:

* session state transitions
* round execution
* retry/failure policy
* stop conditions

## Domain services

Own:

* pure musical logic
* deterministic scoring
* domain object construction

## Graph Persistence Service

Owns:

* durable entity identity
* relationships
* graph schema migrations

## Export Service

Owns:

* final artifact generation
* object-to-file adapters

---

# 12. API surface

## 12.1 Create session

`POST /v1/sessions`

### Request

```json
{
  "mode": "full_exploration",
  "prompt": "Dream pop in A major, wistful and haunted, 8 bars, moderate novelty, open voicings"
}
```

### Response

```json
{
  "session_id": "sess_001",
  "status": "active",
  "creative_brief": { "...": "..." }
}
```

---

## 12.2 Submit prompt / initialize run

`POST /v1/sessions/{session_id}/run`

### Request

```json
{
  "prompt": "Keep the harmony soft and loopable",
  "seed_progression_id": null,
  "seed_melody": null
}
```

### Response

```json
{
  "round_id": "round_001",
  "status": "running"
}
```

---

## 12.3 Get candidates

`GET /v1/sessions/{session_id}/candidates`

### Query params

* `type=progression|arrangement`
* `round=latest|N`
* `status=candidate|selected|rejected`

### Response

```json
{
  "items": [
    {
      "candidate_id": "arr_01",
      "type": "arrangement",
      "summary": "Floating dream-pop loop with borrowed iv",
      "scorecard": { "...": "..." }
    }
  ]
}
```

---

## 12.4 Get candidate detail

`GET /v1/candidates/{candidate_id}`

### Response

Returns:

* canonical object
* evaluation bundle
* lineage
* explanation
* linked artifacts

---

## 12.5 Submit feedback

`POST /v1/candidates/{candidate_id}/feedback`

### Request

```json
{
  "feedback_type": "text_reaction",
  "content": "I like this, but the bass is too directed and the voicings should feel wider."
}
```

### Response

```json
{
  "feedback_event_id": "fb_01",
  "interpreted_adjustments": {
    "reduce_bass_motion": true,
    "increase_voicing_openness": true
  }
}
```

---

## 12.6 Mutate candidate

`POST /v1/candidates/{candidate_id}/mutate`

### Request

```json
{
  "mutation_scope": ["bass_line", "voicing"],
  "goal": "more floating, less directed"
}
```

---

## 12.7 Export selected candidates

`POST /v1/sessions/{session_id}/export`

### Request

```json
{
  "candidate_ids": ["arr_01", "arr_03"],
  "formats": ["json", "midi"]
}
```

### Response

```json
{
  "export_package_id": "export_01",
  "artifacts": [
    {
      "artifact_type": "midi",
      "path": "..."
    }
  ]
}
```

---

# 13. Data contracts

## 13.1 Canonical contract style

Use typed models for all external and internal contracts.

Pydantic v2 is a strong fit here because it provides typed model validation, validators, and schema generation, all of which are useful for API contracts and agent/module outputs. ([Pydantic][1])

## 13.2 Required top-level models

* `Session`
* `CreativeBrief`
* `SessionContext`
* `UserPreferenceProfile`
* `GenreProfile`
* `HarmonicGrammar`
* `ProgressionCandidate`
* `ArrangementCandidate`
* `EvaluationBundle`
* `AggregateScorecard`
* `MutationRecord`
* `SearchRound`
* `FinalSelection`
* `CandidateExplanation`
* `RenderArtifact`

## 13.3 Contract rules

All service/module responses must include:

* `id`
* `type`
* `created_at`
* `version`
* `status`
* `rationale`
* `warnings[]`
* domain payload

---

# 14. Orchestration design

## 14.1 Workflow pattern

Recommended flow:

1. parse prompt
2. normalize brief
3. load genre profile
4. generate progression candidates
5. evaluate progression candidates
6. realize top progression candidates
7. evaluate arrangements
8. rank and diversify
9. mutate promising candidates
10. re-evaluate
11. select finalists
12. persist provenance and artifacts

## 14.2 Framework options

LangGraph is a reasonable choice when you want explicit graph/state orchestration with nodes, shared state, and long-running/stateful workflows. Its docs describe node functions operating over shared state and position it as a low-level orchestration framework. ([LangChain Docs][3])

### Decision point

Use:

* **LangGraph** for experimentation speed and clear graph workflows
* **custom orchestrator** if you want stricter platform control and less framework coupling

Recommended starting choice:

* LangGraph for v1 research/prototype
* keep a clean internal state abstraction so you can swap later

---

# 15. Persistence architecture

## 15.1 Graph persistence

Use Neo4j for:

* sessions
* briefs
* genre profiles
* candidate families
* mutation lineage
* evaluations
* feedback
* pattern memory
* provenance

Neo4j’s official Python driver is the supported Python integration point, and the official manual covers connection/session/query patterns. ([Graph Database & Analytics][4])

## 15.2 Blob/object storage

Store:

* MIDI files
* later MusicXML
* export bundles
* session snapshots

## 15.3 Event modeling decision

Start with:

* high-level graph nodes
* dense musical event arrays as structured properties

Promote note/chord events to first-class nodes only if query needs justify it.

---

# 16. Library and framework decision matrix

## 16.1 Typed models and validation

**Recommended:** Pydantic v2
Pros:

* strong validation
* nested model support
* validators
* JSON Schema generation ([Pydantic][1])

## 16.2 Symbolic music engine

**Recommended:** music21 behind an adapter layer
Pros:

* symbolic music toolkit
* theory-oriented capabilities
* suitable for score-like and analytical workflows ([music21.org][2])

## 16.3 MIDI export

**Recommended:** pretty_midi for MIDI path, music21 for notation path
Pros:

* practical MIDI generation/manipulation flow
* keeps notation concerns separate

## 16.4 Orchestration

**Recommended for v1:** LangGraph
Alternative:

* custom orchestrator

## 16.5 Graph access

**Recommended:** Neo4j Python driver
Pros:

* official support
* clear connection/transaction model ([Graph Database & Analytics][4])

---

# 17. NFRs

## 17.1 Explainability

Every selected candidate must have:

* rationale
* key score drivers
* lineage summary
* user-facing explanation

## 17.2 Reproducibility

Given:

* same seed
* same objective weights
* same deterministic modules
  the system should support replayable rounds where feasible.

## 17.3 Extensibility

The system must support future additions:

* audio evaluators
* DAW integration
* learned style profiles
* finer-grained event graphs

## 17.4 Performance

v1 should optimize for:

* acceptable interactive latency
* strong traceability
* correctness over maximal throughput

---

# 18. Risks and mitigations

## Risk: over-coupling to a music library

Mitigation:

* keep internal object model independent
* use adapter layer around music21

## Risk: overly subjective ranking

Mitigation:

* hybrid scoring
* deterministic constraints first
* model judgment as a contributor, not sole arbiter

## Risk: graph over-modeling

Mitigation:

* high-level node model first
* promote event nodes later only if needed

## Risk: agent orchestration complexity

Mitigation:

* modular single orchestrator pattern initially
* avoid premature multi-service agent fragmentation

## Risk: genre stereotype rigidity

Mitigation:

* separate rules from soft priors
* preserve experimentation envelope
* use user feedback for correction

---

# 19. Milestone plan

## Milestone 0 — Foundations

Deliverables:

* canonical object model
* genre profile schema
* graph schema
* API contracts
* seed curated genre profiles

Exit criteria:

* can persist/read a session and a simple progression candidate

## Milestone 1 — Harmonic MVP

Deliverables:

* prompt normalization
* progression generation
* Roman numeral analysis
* progression evaluation
* graph persistence

Exit criteria:

* user can request 8-bar genre-specific progressions and receive ranked results

## Milestone 2 — Realization MVP

Deliverables:

* voicing generation
* bass-line generation
* arrangement assembly
* arrangement evaluation
* lineage tracking

Exit criteria:

* user can explore multiple realizations of one progression

## Milestone 3 — Guided search

Deliverables:

* mutation engine
* search rounds
* feedback ingestion
* diversity-aware ranking
* finalist selection

Exit criteria:

* user can refine candidates over multiple rounds with feedback

## Milestone 4 — Export and explanation

Deliverables:

* MIDI export
* explanation objects
* comparison views
* export packages

Exit criteria:

* user can export and inspect finalists with clear rationale

## Milestone 5 — Expanded musical surface

Deliverables:

* melodic complements
* groove patterns
* retrieval-assisted warm starts

Exit criteria:

* system supports more arrangement-complete exploration

---

# 20. Engineering workstreams

## Backend platform

* FastAPI
* typed contracts
* auth/session framework

## Music domain engine

* symbolic adapter layer
* harmony generation
* realization modules
* evaluators

## Orchestration

* round engine
* mutation flow
* stop conditions
* retries/failures

## Persistence

* Neo4j schema/migrations
* graph repository layer
* artifact storage

## UX / presentation

* comparison views
* explanation rendering
* candidate detail views
* lineage views

---

# 21. Open technical questions

1. How deterministic should generation be under fixed seeds?
2. Should style profiles remain hand-authored through v1.5?
3. How soon do we need MusicXML relative to MIDI?
4. Should groove generation remain symbolic only at first?
5. When do individual event nodes justify graph expansion?
6. Should retrieval be graph-only first, with vector search deferred?

---

# 22. Recommended implementation baseline

For the first build, I’d recommend:

* **FastAPI + Pydantic v2** for APIs and typed contracts ([Pydantic][1])
* **LangGraph** or a thin equivalent stateful orchestrator for iterative search flow ([LangChain Docs][3])
* **music21** behind adapters for symbolic music logic ([music21.org][2])
* **Neo4j + official Python driver** for graph persistence and lineage ([Graph Database & Analytics][4])
* **pretty_midi** for MIDI export path

The clean next artifact would be an **engineering-ready spec package** with:

* endpoint definitions,
* Pydantic model stubs,
* Neo4j entity/edge mapping,
* and a milestone-by-milestone build plan.

[1]: https://docs.pydantic.dev/latest/?utm_source=chatgpt.com "Welcome to Pydantic - Pydantic Validation"
[2]: https://music21.org/?utm_source=chatgpt.com "music21 Documentation — music21 Documentation"
[3]: https://docs.langchain.com/oss/python/langgraph/overview?utm_source=chatgpt.com "LangGraph overview - Docs by LangChain"
[4]: https://neo4j.com/docs/python-manual/current/?utm_source=chatgpt.com "Neo4j Python Driver Manual"
