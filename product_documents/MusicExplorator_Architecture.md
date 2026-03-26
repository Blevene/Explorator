# Full Layered Architecture Diagram

```text
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 0 — USER / CREATIVE DIRECTION                               │
│                                                                     │
│  Inputs:                                                            │
│  - Genre                                                             │
│  - Mood / emotional target                                           │
│  - Key / tonal center                                                │
│  - Complexity target                                                 │
│  - Novelty target                                                    │
│  - Phrase length / form                                              │
│  - Instrumentation                                                   │
│  - Optional melody / bass / reference songs                          │
│  - Human feedback loop                                               │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 1 — INTENT INTERPRETATION & CREATIVE CONSTRAINTS             │
│                                                                     │
│  Modules:                                                           │
│  - Preference Adapter                                               │
│  - Constraint Parser                                                │
│  - Session Context Manager                                          │
│                                                                     │
│  Outputs:                                                           │
│  - Structured creative brief                                        │
│  - Search constraints                                               │
│  - Optimization targets                                             │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 2 — STYLE / GENRE KNOWLEDGE MODEL                            │
│                                                                     │
│  Modules:                                                           │
│  - Genre Analyst                                                    │
│  - Harmonic Grammar Builder                                         │
│  - Genre Rule Library                                               │
│  - Anti-Pattern Detector                                            │
│                                                                     │
│  Outputs:                                                           │
│  - Genre profile                                                    │
│  - Harmonic vocabulary                                              │
│  - Cadential norms                                                  │
│  - Rhythm/accompaniment priors                                      │
│  - Allowed experimentation envelope                                 │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 3 — CORE HARMONIC SEARCH                                     │
│                                                                     │
│  Modules:                                                           │
│  - Harmony Generator                                                │
│  - Progression Mutator                                              │
│  - Reharmonization Engine                                           │
│  - Search Policy Manager                                            │
│                                                                     │
│  Outputs:                                                           │
│  - Candidate chord progressions                                     │
│  - Roman numeral interpretations                                    │
│  - Mutation histories                                               │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 4 — MUSICAL REALIZATION                                      │
│                                                                     │
│  Modules:                                                           │
│  - Voicing Designer                                                 │
│  - Bass Line Generator                                              │
│  - Melodic Complement Agent                                         │
│  - Inner Voice Motion Agent                                         │
│  - Accompaniment / Groove Pattern Agent                             │
│  - Instrument Realization Adapter                                   │
│                                                                     │
│  Outputs:                                                           │
│  - Arrangement candidates                                           │
│  - Chord voicings                                                   │
│  - Bass motion                                                      │
│  - Counterlines / fills                                             │
│  - Rhythmic comping patterns                                        │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 5 — SYMBOLIC & AUDIO-SIDE ANALYSIS                           │
│                                                                     │
│  Modules:                                                           │
│  - Theory Critic                                                    │
│  - Voice-Leading Evaluator                                          │
│  - Register / Density Analyzer                                      │
│  - Playability Evaluator                                            │
│  - Groove Authenticity Critic                                       │
│  - Melody-Harmony Compatibility Evaluator                           │
│  - Optional MIDI/Render Evaluator                                   │
│                                                                     │
│  Outputs:                                                           │
│  - Per-candidate scorecards                                         │
│  - Explanatory critiques                                            │
│  - Failure diagnoses                                                │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 6 — RANKING, SELECTION, AND EXPERIMENT CONTROL               │
│                                                                     │
│  Modules:                                                           │
│  - Multi-objective Ranker                                           │
│  - Diversity Selector                                               │
│  - Pareto Front Manager                                             │
│  - Exploration/Exploitation Controller                              │
│  - Stop Condition Manager                                           │
│                                                                     │
│  Outputs:                                                           │
│  - Best candidates                                                  │
│  - Diverse finalists                                                │
│  - Next-round mutation targets                                      │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 7 — MEMORY, LEARNING, AND ADAPTATION                         │
│                                                                     │
│  Modules:                                                           │
│  - Pattern Library                                                  │
│  - User Preference Memory                                           │
│  - Session Artifact Store                                           │
│  - Retrieval Layer                                                  │
│  - Feedback Assimilation Engine                                     │
│                                                                     │
│  Outputs:                                                           │
│  - Reusable patterns                                                │
│  - User-tuned priors                                                │
│  - Search warm starts                                               │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 8 — PRESENTATION / EXPORT                                    │
│                                                                     │
│  Modules:                                                           │
│  - Explanation Formatter                                            │
│  - Comparative View Builder                                         │
│  - MIDI / MusicXML / JSON Exporter                                  │
│  - Session Trace / Provenance Report                                │
│                                                                     │
│  Outputs:                                                           │
│  - Ranked results                                                   │
│  - Why-this-works explanations                                      │
│  - Variants and mutation paths                                      │
│  - Exportable musical objects                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

# 1. Architectural intent

The system is designed as a **layered creative search and realization platform**.

Its purpose is not merely to “generate chords,” but to:

* interpret artistic intent
* model genre-specific harmonic language
* search harmonic possibilities
* realize those harmonies into playable/music-like forms
* evaluate them across multiple musical dimensions
* iteratively refine them
* preserve both discoveries and user taste

This makes it closer to a **musical design lab** than a simple generator.

---

# 2. Layer-by-layer specification

## Layer 0 — User / Creative Direction

This is the human-facing control layer.

### Responsibilities

* capture high-level creative intent
* allow under-specified artistic prompts
* permit optional hard constraints
* accept iterative feedback

### Inputs

* “Neo-soul, darker, medium complexity, 8 bars”
* “Dream pop in A major, wistful, loopable”
* “Give me jazz-gospel voicings over these chords”
* “Keep the progression, change the bass movement”
* “More haunting, less functional”

### Design principle

This layer should support both:

* **structured composition requests**
* **fuzzy aesthetic requests**

---

## Layer 1 — Intent Interpretation & Creative Constraints

This layer converts human language into machine-usable structure.

### Components

#### Preference Adapter

Maps language like:

* “moodier”
* “more commercial”
* “less jazzy”
* “more tension”
  into parameter adjustments.

#### Constraint Parser

Extracts explicit constraints:

* key
* bar length
* tempo assumption
* harmonic density
* allowed dissonance
* instrumentation target

#### Session Context Manager

Tracks:

* active prompt
* previous variants
* feedback history
* current candidate family

### Output contract

A **Creative Brief Object** like:

```json
{
  "genre": "dream pop",
  "mood": ["wistful", "haunted"],
  "key": "A major",
  "bars": 8,
  "complexity": "medium",
  "novelty": "moderate",
  "loop_preference": true,
  "instrumentation": ["electric piano", "pad", "bass", "guitar texture"],
  "user_constraints": {
    "avoid_strong_classical_cadences": true,
    "prefer_open_voicings": true
  }
}
```

---

## Layer 2 — Style / Genre Knowledge Model

This layer defines what “in genre” means.

### Components

#### Genre Analyst

Builds a genre profile from:

* known genre conventions
* harmonic color tendencies
* voicing expectations
* rhythmic patterns
* typical bass behavior
* acceptable experimentation range

#### Harmonic Grammar Builder

Translates genre knowledge into operational rules:

* preferred chord qualities
* progression archetypes
* cadence types
* borrowed chord likelihoods
* harmonic rhythm norms

#### Genre Rule Library

Reusable style templates:

* neo-soul
* jazz
* dream pop
* synthwave
* house
* cinematic ambient
* indie folk
* gospel
* funk
* trap-soul

#### Anti-Pattern Detector

Defines what likely breaks genre identity.

For example, for dream pop:

* overly dominant-functional cadences
* too many dense altered dominants
* overly busy bassline in every bar

### Output contract

A **Genre Profile Object**.

---

## Layer 3 — Core Harmonic Search

This is the symbolic harmony engine.

### Components

#### Harmony Generator

Generates candidate progressions from:

* genre profile
* key/mode
* phrase length
* desired novelty range

#### Progression Mutator

Applies controlled changes:

* swap IV → iv
* add backdoor dominant
* insert passing diminished
* move to slash chord
* convert plain triad to extension-based voicing target chord

#### Reharmonization Engine

If melody exists, it proposes alternate harmonic supports.

#### Search Policy Manager

Determines search strategy:

* beam search
* evolutionary search
* random exploration with constraints
* Pareto-front preservation

### Output

A set of **Progression Candidates** with:

* chord symbols
* harmonic function tags
* rationale
* mutation lineage

### Key principle

This layer generates **harmonic structures**, not full arrangements.

---

## Layer 4 — Musical Realization

This layer turns chord skeletons into musical textures.

### Components

#### Voicing Designer

Chooses:

* inversion
* spacing
* register
* extension density
* top voice continuity
* instrument-appropriate voicing style

#### Bass Line Generator

Defines:

* root-driven or non-root bass motion
* passing tones
* pedal points
* syncopation
* walking vs sustained vs countermelodic behavior

#### Melodic Complement Agent

Creates:

* fills
* hooks
* top-line fragments
* response phrases
* non-primary melodic fragments

#### Inner Voice Motion Agent

Handles:

* common-tone retention
* semitone resolution
* suspended inner motion
* chorale-like or cluster-like movement

#### Accompaniment / Groove Pattern Agent

Generates rhythmic articulation:

* arpeggiation
* block comping
* stabs
* syncopation
* pulse patterns
* broken chord figures

#### Instrument Realization Adapter

Adjusts output for:

* piano
* guitar
* synth pad
* Rhodes
* strings
* ensemble contexts

### Output

An **Arrangement Candidate**:

* progression
* voicings
* bass line
* complement line
* rhythm pattern
* register plan

This is the point where abstract harmony becomes a musical object.

---

## Layer 5 — Symbolic & Audio-Side Analysis

This layer critiques what has been generated.

### Components

#### Theory Critic

Assesses:

* tonal coherence
* functional plausibility
* genre fit
* cadence design
* progression shape
* cliché risk

#### Voice-Leading Evaluator

Checks:

* common tones
* stepwise motion
* unresolved tension
* awkward leaps
* semitone elegance

#### Register / Density Analyzer

Checks:

* mud in lower-mid range
* overstacking of tensions
* spacing imbalance
* register collisions

#### Playability Evaluator

Assesses:

* pianist feasibility
* guitarist feasibility
* ensemble practicality
* simplification needs

#### Groove Authenticity Critic

Checks whether the rhythmic realization feels genre-consistent.

#### Melody-Harmony Compatibility Evaluator

If melody exists:

* does the harmony support or fight the line?
* are tensions justified?
* does bass undermine melodic clarity?

#### Optional MIDI/Render Evaluator

If a rendering layer exists:

* analyze output clips
* compare similarity to intended reference zone
* run learned evaluators or embeddings

### Output

A **Scorecard + Critique Bundle** per candidate.

---

## Layer 6 — Ranking, Selection, and Experiment Control

This layer decides what survives.

### Components

#### Multi-objective Ranker

Combines scores like:

* genre fit
* emotional fit
* coherence
* novelty
* voicing quality
* bass quality
* playability
* loopability

#### Diversity Selector

Prevents top-5 results from all being near-duplicates.

#### Pareto Front Manager

Preserves candidates that are strong on different axes:

* safest
* richest
* weirdest viable
* best for topline
* best loop
* best performance practicality

#### Exploration/Exploitation Controller

Determines whether to:

* keep searching
* refine top options
* explore further mutation

#### Stop Condition Manager

Stops when:

* quality threshold hit
* diversity sufficient
* budget exhausted
* user preference stabilized

---

## Layer 7 — Memory, Learning, and Adaptation

This layer allows growth and continuity.

### Components

#### Pattern Library

Stores:

* successful progressions
* voicing schemas
* bass devices
* genre-specific accompaniment formulas
* mutation recipes

#### User Preference Memory

Stores:

* preferred complexity
* favorite genres
* tolerance for dissonance
* dislike of over-busy arrangements
* preference for open voicings, etc.

#### Session Artifact Store

Stores:

* candidates
* revisions
* critique traces
* score histories

#### Retrieval Layer

Supplies prior good patterns at generation time.

#### Feedback Assimilation Engine

Translates feedback like:

* “This is too busy”
* “I like the second one but darker”
  into future search bias.

---

## Layer 8 — Presentation / Export

This is the delivery layer.

### Components

#### Explanation Formatter

Presents:

* why the result fits the genre
* what makes it experimental
* what changed between variants

#### Comparative View Builder

Shows:

* safe vs experimental
* alternate bass options
* same chords, different voicings
* same progression, different grooves

#### MIDI / MusicXML / JSON Exporter

Allows downstream usage.

#### Session Trace / Provenance Report

Provides explainability:

* which mutations happened
* which scoring dimensions improved
* why a candidate was selected

---

# 3. Agent map by layer

Here is the canonical agent assignment.

```text
Layer 1:
- Preference Adapter
- Constraint Parser

Layer 2:
- Genre Analyst
- Harmonic Grammar Builder
- Anti-Pattern Detector

Layer 3:
- Harmony Generator
- Progression Mutator
- Reharmonization Agent
- Search Policy Controller

Layer 4:
- Voicing Designer
- Bass Line Generator
- Melodic Complement Agent
- Inner Voice Motion Agent
- Groove Pattern Agent
- Instrument Realization Adapter

Layer 5:
- Theory Critic
- Voice-Leading Evaluator
- Register/Density Analyzer
- Playability Evaluator
- Groove Critic
- Melody-Harmony Compatibility Evaluator

Layer 6:
- Multi-objective Ranker
- Diversity Selector
- Pareto Manager
- Exploration Controller

Layer 7:
- Pattern Librarian
- User Preference Memory Manager
- Retrieval Agent
- Feedback Assimilator

Layer 8:
- Explanation Formatter
- Comparative Presenter
- Export Agent
```

---

# 4. End-to-end data flow

## Step 1: User prompt

Example:

> Dream pop, wistful but haunted, A major, 8 bars, moderate novelty, give me open voicings and a simple melodic complement.

## Step 2: Intent normalization

The system converts this into structured constraints.

## Step 3: Genre modeling

The genre model defines:

* common harmony types
* voicing priors
* groove assumptions
* anti-patterns

## Step 4: Harmonic generation

Several progression families are produced:

* conservative
* balanced
* exploratory

## Step 5: Realization

Each promising progression gets:

* voicing set
* bass line
* melodic complement
* accompaniment pattern

## Step 6: Evaluation

Each arrangement candidate receives:

* harmonic score
* voicing score
* bass score
* complement score
* density score
* genre authenticity score

## Step 7: Selection

Candidates are ranked and diversified.

## Step 8: Mutation loop

The system mutates promising candidates.

## Step 9: Memory update

Successful ideas are stored.

## Step 10: Presentation

Final outputs are explained and exportable.

---

# 5. Control loop specification

The system should run as an iterative search loop.

```text
Initialize session
  ->
Parse creative brief
  ->
Build genre profile
  ->
Generate progression candidates
  ->
Evaluate progression candidates
  ->
Realize top candidates
  ->
Evaluate arrangement candidates
  ->
Rank + diversify
  ->
Mutate / branch promising candidates
  ->
Re-evaluate
  ->
Check stop condition
      -> if no, continue search
      -> if yes, present outputs + store memory
```

### Stop conditions

The system can terminate when:

* top score exceeds threshold
* diversity target reached
* user likes a family of outputs
* search rounds exceed cap
* novelty objective satisfied

---

# 6. Canonical interfaces and contracts

Below are the important internal objects.

## A. CreativeBrief

```json
{
  "genre": "neo-soul",
  "mood": ["warm", "late-night", "slightly unresolved"],
  "key": "D minor",
  "bars": 8,
  "complexity": "medium-high",
  "novelty": "moderate",
  "instrumentation": ["rhodes", "bass", "drums"],
  "constraints": {
    "prefer_loopability": true,
    "avoid_overly_classical_cadence": true
  }
}
```

## B. GenreProfile

```json
{
  "genre": "neo-soul",
  "harmonic_vocabulary": ["m9", "maj9", "13", "alt", "slash chords", "modal interchange"],
  "cadence_tendencies": ["soft resolution", "backdoor dominant", "delayed closure"],
  "voicing_tendencies": ["rootless", "clustered mids", "smooth top note motion"],
  "bass_tendencies": ["economical", "groove-led", "sometimes non-root emphasis"],
  "groove_tendencies": ["syncopated comping", "laid-back pulse"],
  "anti_patterns": ["plain triadic pop loop with no color", "overly rigid functional cadence"]
}
```

## C. ProgressionCandidate

```json
{
  "id": "prog_01",
  "key": "D minor",
  "bars": 8,
  "chords": ["Dm9", "G13", "Cmaj9", "Fmaj7", "Bbmaj9", "Em7b5", "A7alt", "Dm9"],
  "roman": ["i9", "IV13", "bVIImaj9", "bIIImaj7", "VImaj9", "iiø", "V7alt", "i9"],
  "generator_mode": "balanced",
  "rationale": "warm circular motion with a richer return cadence",
  "mutation_lineage": []
}
```

## D. ArrangementCandidate

```json
{
  "id": "arr_01",
  "progression_id": "prog_01",
  "voicings": [
    ["F-C-E-A"],
    ["F-B-E-A"],
    ["E-B-D-G"],
    ["E-A-C-F"]
  ],
  "bass_line": ["D", "G", "C", "F", "Bb", "E", "A", "D"],
  "melodic_complement": ["A", "B", "G", "A", "F", "G", "C#", "D"],
  "inner_voice_strategy": "retain common tones and semitone-resolve altered dominant",
  "accompaniment_pattern": "syncopated rhodes stabs with light anticipations",
  "instrument_profile": "rhodes trio"
}
```

## E. EvaluationScorecard

```json
{
  "candidate_id": "arr_01",
  "scores": {
    "genre_fit": 8.9,
    "emotional_fit": 8.4,
    "theoretical_coherence": 8.8,
    "novelty": 7.1,
    "loopability": 8.0,
    "voicing_quality": 8.7,
    "bass_line_quality": 8.2,
    "melodic_complement_quality": 7.8,
    "groove_authenticity": 8.5,
    "playability": 7.9,
    "density_balance": 8.3
  },
  "critic_notes": [
    "Strong harmonic color with convincing voicing continuity",
    "Bass is supportive but could be more rhythmically distinctive",
    "Complement line fits but risks competing if a vocal enters"
  ]
}
```

## F. MutationRecord

```json
{
  "source_candidate_id": "arr_01",
  "variant_candidate_id": "arr_01b",
  "changes": [
    "replace Fmaj7 with Fm9",
    "simplify melodic complement in bars 5-6",
    "use pedal D in bass for first two bars"
  ],
  "reason": "increase wistfulness and reduce mid-phrase clutter"
}
```

---

# 7. Scoring framework

The system should not optimize to one scalar too early, but it still needs a scoring layer.

## Harmonic domain

* genre fit
* emotional fit
* theoretical coherence
* cadence quality
* novelty
* loopability

## Realization domain

* voicing smoothness
* top-line continuity
* bass clarity and interest
* inner voice quality
* accompaniment authenticity
* density balance
* register balance
* playability

## Optional production-aware domain

* mix-space friendliness
* arrangement headroom for vocal
* ensemble compatibility

### Recommended ranking strategy

Use a combination of:

* weighted sum
* Pareto front
* diversity penalty

This avoids over-selecting near-identical outputs.

---

# 8. Mutation and exploration policies

The system should mutate at multiple levels.

## Harmonic mutations

* borrowed chord insertion
* cadence softening
* secondary dominant insertion
* modal shift
* slash chord replacement

## Voicing mutations

* spread vs close
* top note target change
* remove root
* add or remove tensions
* inversion changes

## Bass mutations

* root reinforcement
* pedal tone
* approach tones
* contrary motion
* syncopation increase/decrease

## Melodic complement mutations

* simplify
* increase motif repetition
* delay entry
* restrict to chord tones
* add one expressive tension

## Groove mutations

* make more sparse
* move from block to broken chords
* add offbeat anticipations
* align or oppose bass rhythm

---

# 9. Modes of operation

The architecture should support several user modes.

## A. Harmonic exploration mode

Focus on progression discovery.

## B. Realization mode

User already has chords; system explores voicing/bass/complements.

## C. Reharm mode

User provides melody; system explores alternate harmonic supports.

## D. Genre transformation mode

Hold core phrase structure constant, reinterpret it in another genre.

## E. Comparative lab mode

Produce 3–5 deliberately contrasted realizations.

---

# 10. Explainability requirements

This system should be highly explainable.

For each result, it should tell the user:

* why it fits the requested genre
* which devices were used
* what makes it safer or more experimental
* how the bass and voicing reinforce the mood
* what changed from prior variants

This is especially important because creative systems otherwise feel arbitrary.

---

# 11. Suggested MVP vs full system

## MVP

Build:

* Layer 1 intent parser
* Layer 2 genre analyst
* Layer 3 harmony generator
* Layer 4 voicing + bass generator
* Layer 5 theory critic
* Layer 6 ranker
* basic memory

This already gives a strong system.

## Phase 2

Add:

* melodic complement agent
* groove pattern generator
* diversity-aware selection
* mutation lineage tracking

## Phase 3

Add:

* MIDI rendering
* learned/audio evaluators
* user taste adaptation over time
* export formats

---

# 12. Concise architectural summary

This is the core conceptual stack:

```text
Intent
 -> Style Model
 -> Harmonic Search
 -> Musical Realization
 -> Evaluation
 -> Selection
 -> Mutation Loop
 -> Memory
 -> Presentation
```

And the deeper musical insight is:

* **Layer 3** decides *what harmony exists*
* **Layer 4** decides *how that harmony actually lives*
* **Layer 5** decides *whether it works*
* **Layer 6** decides *what survives and evolves*

That separation is what makes the architecture robust.
.
