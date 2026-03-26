# Functional Specification

## Genre Chord Exploration and Realization System

## 1. Purpose

Build a system that can explore, generate, evaluate, mutate, and rank genre-specific harmonic and arrangement candidates, including:

* chord progressions
* voicings
* bass lines
* melodic complements
* inner voice motion
* groove/accompaniment patterns
* arrangement-level variants

The system is intended as a **creative exploration engine**, not a deterministic composition oracle.

## 2. Goals

The system must:

* accept high-level creative prompts
* normalize them into structured constraints
* generate multiple harmonic candidates
* realize those candidates into arrangement variants
* evaluate them across music-theoretic and genre-fit dimensions
* iteratively refine promising options
* preserve lineage, feedback, and memory
* export structured artifacts for downstream use

## 3. Non-goals

The first version will not try to:

* produce radio-ready full songs
* generate polished audio production or mixing
* infer every genre purely from raw audio
* replace a human composer’s final judgment
* perform dense audio-based MIR as a hard dependency

---

# 4. Primary user stories

## 4.1 Harmonic exploration

As a user, I want to describe a genre, mood, and complexity target and receive multiple chord progression candidates with explanations.

## 4.2 Realization exploration

As a user, I want to keep a progression fixed and explore alternate voicings, bass lines, and melodic complements.

## 4.3 Reharmonization

As a user, I want to provide a melody and receive alternative harmonic treatments appropriate to one or more genres.

## 4.4 Comparative genre transformation

As a user, I want to hear or inspect how the same harmonic idea changes across genres.

## 4.5 Guided refinement

As a user, I want to react to candidates in natural language and have the system adapt the next round.

## 4.6 Export and reuse

As a user, I want MIDI, MusicXML, JSON, and graph-stored provenance for successful ideas.

---

# 5. System modes

## 5.1 Progression mode

Input is a creative brief only. Output is chord progression candidates.

## 5.2 Realization mode

Input is an existing progression. Output is voicings, bass, complements, and groove options.

## 5.3 Reharm mode

Input is melody plus optional genre/style constraints. Output is harmonic alternatives.

## 5.4 Comparative lab mode

Input is a base idea. Output is contrasted interpretations.

## 5.5 Retrieval-assisted mode

Input includes references to prior successful patterns or user-favored ideas. Output is warm-started exploration.

---

# 6. Functional requirements

## 6.1 Intent ingestion and normalization

The system shall:

* accept freeform prompts
* parse explicit constraints such as key, bars, tempo hint, meter, genre, subgenre, complexity, novelty, instrumentation
* parse soft preferences such as “more haunted,” “less jazzy,” “sparser bass,” “more open voicings”
* preserve the original user wording alongside normalized fields
* support user-provided seed materials:

  * progression
  * melody
  * bass line
  * reference tracks/artists
  * prior selected candidate IDs

### Inputs

* natural language prompt
* optional symbolic music objects
* optional prior candidate references

### Outputs

* `CreativeBrief`
* `SessionContext`
* inferred objective weights

### Library options

For typed normalization and validation, **Pydantic v2** is the strongest default because it gives strong validation and JSON Schema generation, which is useful for agent outputs and API contracts. ([Pydantic][1])

### Decision point

**How much parsing should be model-driven vs rule-driven?**

Option A: mostly LLM-driven parsing
Option B: hybrid extraction with regex/rules for obvious constraints plus LLM for softer intent

Recommended:

* hybrid
* rule extraction for deterministic fields
* LLM for aesthetic interpretation

---

## 6.2 Genre/style knowledge modeling

The system shall:

* maintain genre profiles with harmonic, voicing, bass, and groove priors
* support explicit anti-patterns
* support subgenre overrides
* expose an experimentation envelope per style
* allow rule weighting and future user-specific tuning

### Outputs

* `GenreProfile`
* `HarmonicGrammar`
* linked `GenreRule` and `AntiPattern` entities

### Library options

This layer is mostly application logic and data modeling. No specialized music library is sufficient by itself; this is domain knowledge plus structured storage.

### Decision point

**Hard-coded style profiles vs retrieval-backed style profiles**

Option A: curated static profiles
Option B: retrieval-backed profiles from a corpus
Option C: hybrid

Recommended:

* start with curated profiles
* later allow corpus-derived priors

---

## 6.3 Harmonic generation

The system shall:

* generate multiple candidate chord progressions from a creative brief and genre profile
* support conservative, balanced, and exploratory generation modes
* support key-aware and mode-aware generation
* support multiple phrase lengths and harmonic rhythms
* support partial conditioning on melody or bass
* provide rationale tags and harmonic intent

### Outputs

* `ProgressionCandidate`
* `RomanNumeralAnalysis`
* `ProgressionFamily`

### Library options

For symbolic music reasoning, **music21** is the strongest official option among the commonly used Python libraries because it is designed for symbolic music analysis and transformation. It is well suited for Roman numeral analysis, harmony representation, and score-like symbolic work. ([music21.org][2])

For lighter MIDI-centric manipulation, **pretty_midi** is useful, but it is less theory-centric than music21. ([craffel.github.io][3])

### Decision points

**Representation for harmonic objects**

* string chord symbols only
* typed chord objects
* dual representation

Recommended:

* dual representation
* store chord symbols for clarity
* derive typed harmonic objects for theory operations

**Primary symbolic engine**

* music21 as canonical harmony engine
* custom harmony engine
* mixed approach

Recommended:

* music21 for theory operations
* custom wrapper layer for stable internal semantics

Reason: music21 is powerful, but its internal model should not become your domain model. ([music21.org][2])

---

## 6.4 Harmonic mutation and search

The system shall:

* mutate candidate progressions in controlled ways
* track each mutation with explicit provenance
* support beam-style search, mutation loops, and Pareto-aware selection
* preserve both high-scoring and high-diversity candidates
* support mutation scopes:

  * harmonic
  * voicing
  * bass
  * complement
  * groove

### Outputs

* `MutationRecord`
* updated candidates
* `SearchRound`
* `ParetoFrontSnapshot`

### Library options

This is application logic. The main technical dependency is the orchestration framework.

**LangGraph** is a strong fit if you want explicit stateful graph-based orchestration with multi-step flows and shared state. Its docs describe it as a low-level orchestration framework for stateful agents. ([LangChain Docs][4])

### Decision point

**Agent orchestration framework**

* LangGraph
* custom async workflow engine
* Temporal-like workflow layer with LLM tasks
* simple service orchestration without an agent framework

Recommended:

* LangGraph or a thin custom orchestrator if you expect many iterative graph-shaped loops
* custom orchestration if you want strict determinism and low framework coupling

My recommendation for this project:

* use **LangGraph** if experimentation speed matters more than minimizing framework footprint
* use a custom orchestration layer if you already expect strong productization and long-term platform control

---

## 6.5 Voicing generation

The system shall:

* transform a progression into one or more voicing plans
* support instrument-aware voicing strategies
* control spacing, inversion, density, top note continuity, and register
* support genre-specific voicing idioms
* optionally generate multiple voicing families for the same progression

### Outputs

* `VoicingPlan`
* optional `VoicingEvent` sequence

### Library options

* **music21** for symbolic pitch/chord relationships and score-like manipulation ([music21.org][2])
* custom voicing engine for practical heuristics
* optionally `pretty_midi` after voicings are finalized for rendering/export ([craffel.github.io][3])

### Decision point

**Rule-based vs model-proposed voicings**

* rule-only
* LLM-proposed with rules checking
* search-based voicing optimization

Recommended:

* LLM or heuristic proposal
* deterministic rule-based validation and scoring after proposal

---

## 6.6 Bass line generation

The system shall:

* generate bass lines conditioned on progression, genre, and groove
* support supportive, pedal, walking, syncopated, countermelodic, and sparse modes
* generate note-event outputs aligned to meter
* preserve bass-to-harmony relationship metadata

### Outputs

* `BassLine`
* optional `BassNoteEvent` sequence

### Decision point

**Bass generation style**

* symbolic search
* rule templates
* model proposals
* hybrid

Recommended:

* hybrid
* templates and constraints for groove integrity
* model-guided variation for contour interest

---

## 6.7 Melodic complement generation

The system shall:

* generate non-primary melodic support lines
* support sparse fills, countermelodies, and short motifs
* keep melodic complements distinct from the main melody
* support density and range control
* avoid frequent collisions with melody and core harmony unless intentional

### Outputs

* `MelodicComplement`

### Decision point

**Should complements be generated before or after groove?**

Option A: before groove
Option B: after groove
Option C: co-generated

Recommended:

* after initial groove assumptions are known
* then iterate jointly if needed

---

## 6.8 Inner voice planning

The system shall:

* represent and optimize inner motion where musically relevant
* track common-tone retention
* model suspensions and semitone resolutions
* support simplification for less harmony-dense genres

### Outputs

* `InnerVoicePlan`

### Decision point

**Explicit inner voices for every genre?**

Recommended:

* no
* make this optional or low-weight for genres where inner motion is not central

---

## 6.9 Groove/accompaniment generation

The system shall:

* generate rhythmic accompaniment patterns appropriate to genre and instrumentation
* support block chords, broken chords, arpeggiation, stabs, pulses, and sparse atmospherics
* align harmonic rhythm with groove behavior
* expose syncopation and density controls

### Outputs

* `GroovePattern`

### Decision point

**Separate groove engine vs arrangement co-generation**

Recommended:

* separate groove representation
* compose it into arrangement later

That makes comparative experiments much easier.

---

## 6.10 Arrangement assembly

The system shall:

* assemble progression, voicing, bass, complements, inner motion, and groove into an `ArrangementCandidate`
* support partially populated arrangement candidates
* allow multiple arrangements per progression
* preserve family grouping and lineage

### Outputs

* `ArrangementCandidate`
* `ArrangementFamily`

---

## 6.11 Evaluation

The system shall score both progression candidates and arrangement candidates.

### Required evaluation dimensions

* genre fit
* emotional fit
* theoretical coherence
* cadence quality
* novelty
* loopability
* voicing quality
* bass line quality
* melodic complement quality
* groove authenticity
* playability
* density/register balance
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

### Library options

* **music21** for symbolic analysis and some rule-driven theory checks ([music21.org][2])
* custom scoring modules for arrangement-level criteria
* optional audio/MIDI evaluators later using rendered MIDI

### Decision point

**Single scalar score vs multi-objective frontier**

Recommended:

* multi-objective scoring internally
* weighted scalar only for ranking convenience
* preserve Pareto fronts for creative diversity

---

## 6.12 Search control and ranking

The system shall:

* support multi-round search
* rank candidates with configurable objective weights
* preserve diversity among finalists
* expose stop conditions
* support user-guided reweighting after feedback

### Outputs

* `SearchPlan`
* `SearchRound`
* `ObjectiveWeights`
* `FinalSelection`

### Decision point

**Ranking strategy**

* weighted sum only
* weighted sum + diversity
* Pareto front + diversity + weighted fallback

Recommended:

* Pareto front + diversity + weighted fallback

---

## 6.13 Session memory and retrieval

The system shall:

* store successful abstracted patterns
* store user preference signals
* retrieve prior patterns by genre, mood, voicing traits, and tags
* support warm-start generation from memory
* maintain provenance for why a pattern was reused

### Outputs

* `PatternLibraryEntry`
* `RetrievalQuery`
* `RetrievalResult`
* updated `UserPreferenceProfile`

### Decision point

**Memory store architecture**

* graph only
* graph + vector store
* relational + graph + vector

Recommended:

* graph for lineage/provenance
* optional vector store for semantic retrieval over explanations/tags/pattern summaries

---

## 6.14 Provenance and explainability

The system shall:

* record why candidates were generated, selected, or discarded
* preserve mutation lineage
* preserve score deltas across rounds
* produce user-facing explanations
* support developer/debug traces

### Outputs

* `MutationRecord`
* `ProvenanceTrace`
* `CandidateExplanation`
* `ComparisonView`

This is a core requirement, not a nice-to-have.

---

## 6.15 Export

The system shall support export of:

* JSON object model
* MIDI
* MusicXML
* human-readable comparison/report output

### Library options

* **pretty_midi** is a strong default for MIDI creation/manipulation/export in Python. ([craffel.github.io][3])
* **music21** is useful for MusicXML/notation-oriented symbolic output. ([music21.org][2])

### Decision point

**Canonical export engine**

* pretty_midi for MIDI and music21 for notation
* all export through music21
* custom export adapters

Recommended:

* pretty_midi for MIDI
* music21 for notation-oriented exports
* internal neutral object model in front of both

---

# 7. Core services

## 7.1 API service

Responsibilities:

* session creation
* prompt submission
* retrieval of candidates and scorecards
* user feedback submission
* export requests

Suggested stack:

* FastAPI + Pydantic v2
* async endpoints where helpful

Pydantic v2 is especially relevant here because of validation and JSON Schema generation. ([Pydantic][1])

## 7.2 Orchestration service

Responsibilities:

* execute generation/evaluation/mutation workflows
* manage shared state across rounds
* call model/tool nodes

Suggested options:

* LangGraph
* custom orchestrator

LangGraph is explicitly designed around stateful graph-based agent workflows. ([LangChain Docs][4])

## 7.3 Theory and symbolic engine

Responsibilities:

* chord parsing
* Roman numeral analysis
* interval logic
* symbolic transformations
* notation-oriented generation

Suggested options:

* music21 as primary
* custom wrappers around it

## 7.4 Render/export service

Responsibilities:

* MIDI rendering
* MusicXML export
* artifact packaging

Suggested options:

* pretty_midi for MIDI
* music21 for MusicXML

## 7.5 Graph persistence service

Responsibilities:

* session graph storage
* lineage/provenance
* memory/pattern graph
* candidate relationships

Suggested options:

* Neo4j with official Python driver

The Neo4j Python Driver is the official library for Python access. ([Graph Database & Analytics][5])

---

# 8. Data storage functional spec

## 8.1 Graph database

Use Neo4j for:

* sessions
* briefs
* genre profiles
* candidate families
* mutation lineage
* evaluations
* pattern memory
* provenance traces

### Library

* official Neo4j Python driver ([Graph Database & Analytics][5])

### Decision point

**How much of the musical event structure goes into the graph?**

Recommended:

* store high-level entities as nodes
* keep dense event payloads as JSON properties initially
* promote to event nodes only when query needs justify it

## 8.2 Document/object storage

Use object/blob storage for:

* rendered MIDI
* MusicXML
* session snapshots
* export bundles

## 8.3 Optional vector retrieval

Use a vector store only if you want semantic retrieval over:

* pattern summaries
* user preference language
* candidate explanations
* corpus-derived style notes

Recommended:

* optional for phase 2
* not required for MVP

---

# 9. Agent/service boundaries

## 9.1 Suggested agent modules

* Intent Interpreter
* Genre Analyst
* Harmony Generator
* Mutation Planner
* Voicing Designer
* Bass Generator
* Complement Generator
* Groove Generator
* Theory Critic
* Arrangement Critic
* Ranker
* Memory Retriever
* Explanation Generator

## 9.2 Decision point

**True multi-agent system vs modular single orchestrator**

Recommended:

* modular single orchestrator with specialized submodules first
* treat “agents” as separable roles, not necessarily separately deployed services

This keeps the system easier to debug.

---

# 10. Interfaces and contracts

## 10.1 Internal contract style

Use typed models for every major entity:

* `CreativeBrief`
* `GenreProfile`
* `ProgressionCandidate`
* `ArrangementCandidate`
* `EvaluationBundle`
* `MutationRecord`
* `SearchRound`
* `FinalSelection`

### Library

* Pydantic v2 for model validation and JSON Schema generation ([Pydantic][1])

## 10.2 Tool contract requirement

Every generator/evaluator module must accept:

* session context
* candidate IDs or seed object
* objective weights
* optional user feedback delta

And must return:

* typed output object
* rationale
* diagnostics/warnings
* optional provenance metadata

---

# 11. Evaluation framework requirements

## 11.1 Deterministic evaluators

Should include:

* range checks
* playability heuristics
* spacing heuristics
* cadence classification
* density thresholds
* conflict detection

## 11.2 Model-assisted evaluators

Should include:

* genre-fit judgment
* emotional-fit interpretation
* explanation synthesis
* novelty estimation
* anti-pattern plausibility checks

## 11.3 Decision point

**Can LLM evaluators be trusted directly for ranking?**

Recommended:

* no
* use them as one input among deterministic or semi-deterministic scorers
* never make them the sole scoring authority

---

# 12. MVP scope

## 12.1 MVP included

* prompt normalization
* curated genre profiles
* progression generation
* voicing generation
* bass generation
* theory evaluation
* aggregate ranking
* Neo4j persistence
* JSON + MIDI export
* mutation lineage
* user feedback loop

## 12.2 MVP excluded

* raw audio generation
* audio embedding evaluation
* automatic corpus learning from large music datasets
* DAW plugin integration
* collaborative multi-user editing

---

# 13. Phase 2 scope

* melodic complements
* groove/accompaniment engine
* MusicXML export
* retrieval-enhanced pattern memory
* comparative visualization
* richer user preference modeling
* event-level graph expansion where useful

---

# 14. Phase 3 scope

* audio rendering and evaluation
* reference-track-aware similarity scoring
* corpus-derived style priors
* interactive human-in-the-loop audition tools
* plugin or DAW integration
* adaptive user taste model

---

# 15. Library options by subsystem

## 15.1 Typed models / API contracts

**Recommended:** Pydantic v2
Why:

* strong validation
* JSON Schema output
* clean API contracts ([Pydantic][1])

Alternative:

* dataclasses + custom validation
* attrs

Decision:

* Pydantic unless you have a strong reason not to

## 15.2 Agent orchestration

**Option A:** LangGraph
Good for:

* stateful graph workflows
* iterative agent loops
* explicit state passing ([LangChain Docs][4])

**Option B:** custom orchestrator
Good for:

* strict control
* lower dependency footprint
* clearer determinism

Recommendation:

* LangGraph for experimentation-heavy v1
* custom orchestrator if platform rigor outranks speed

## 15.3 Symbolic music engine

**Option A:** music21
Good for:

* theory-heavy symbolic analysis
* Roman numeral analysis
* notation-friendly symbolic transformations ([music21.org][2])

**Option B:** custom symbolic engine
Good for:

* strict internal semantics
* tighter control
* reduced library abstraction mismatch

Recommendation:

* music21 behind your own domain adapter layer

## 15.4 MIDI/render

**Option A:** pretty_midi
Good for:

* Python MIDI manipulation/render prep
* note-oriented export flow ([craffel.github.io][3])

**Option B:** music21 export path
Good for:

* notation-centric workflows

Recommendation:

* pretty_midi for MIDI
* music21 for notation/MusicXML

## 15.5 Graph persistence

**Recommended:** Neo4j + official Python driver
Why:

* graph lineage and provenance fit the problem well
* official driver is straightforward for Python integration ([Graph Database & Analytics][5])

---

# 16. Major technical decision points

## 16.1 Canonical internal representation

Choose between:

* chord-symbol centric
* event-centric symbolic
* layered dual representation

Recommended:

* layered dual representation

## 16.2 Orchestration style

Choose between:

* agent framework
* service workflow
* hybrid

Recommended:

* hybrid with explicit typed state

## 16.3 Evaluation authority

Choose between:

* LLM-first scoring
* deterministic-first scoring
* hybrid

Recommended:

* hybrid, deterministic-first where possible

## 16.4 Storage architecture

Choose between:

* graph only
* graph + blob
* graph + blob + vector

Recommended:

* graph + blob for MVP
* add vector later only if retrieval needs justify it

## 16.5 Event granularity in graph

Choose between:

* high-level entities only
* full event graph

Recommended:

* high-level first

## 16.6 Symbolic library dependency depth

Choose between:

* wrap music21 lightly
* deeply couple to music21
* use custom core

Recommended:

* custom core domain model with music21 adapters

This is one of the most important decisions in the system.

---

# 17. Risks and mitigations

## Risk: over-coupling to a symbolic music library

Mitigation:

* keep internal canonical object model separate
* use adapters

## Risk: brittle genre stereotypes

Mitigation:

* separate hard rules from soft priors
* preserve experimentation envelopes
* allow user correction and weight tuning

## Risk: too much LLM subjectivity in ranking

Mitigation:

* score with mixed evaluators
* preserve diagnostic explanations
* avoid sole dependence on model judgment

## Risk: graph over-modeling

Mitigation:

* keep event payloads as properties until query pressure proves otherwise

## Risk: orchestration complexity too early

Mitigation:

* start with a single orchestrator and module boundaries
* split into distributed agents only when needed

---

# 18. Recommended implementation baseline

My recommended baseline stack is:

* **FastAPI + Pydantic v2** for service layer and contracts ([Pydantic][1])
* **LangGraph** for iterative orchestration if you want explicit graph workflows quickly ([LangChain Docs][4])
* **music21** as the primary symbolic analysis/manipulation adapter ([music21.org][2])
* **pretty_midi** for MIDI export/render preparation ([craffel.github.io][3])
* **Neo4j + official Python driver** for lineage/provenance/memory graph ([Graph Database & Analytics][5])


[1]: https://docs.pydantic.dev/latest/?utm_source=chatgpt.com "Welcome to Pydantic - Pydantic Validation"
[2]: https://music21.org/?utm_source=chatgpt.com "music21 Documentation — music21 Documentation"
[3]: https://craffel.github.io/pretty-midi/?utm_source=chatgpt.com "pretty_midi 0.2.11 documentation"
[4]: https://docs.langchain.com/oss/python/langgraph/overview?utm_source=chatgpt.com "LangGraph overview - Docs by LangChain"
[5]: https://neo4j.com/docs/python-manual/current/?utm_source=chatgpt.com "Neo4j Python Driver Manual"
