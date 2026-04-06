# M2a: Realization Engine Design

**Date**: 2026-04-05
**Status**: Approved
**Milestone**: M2a (of M2a/M2b/M2c split)
**Depends on**: M1 Harmonic MVP (complete)

## 1. Overview

M2a transforms chord progression skeletons from M1 into playable musical arrangements. Users select progressions from generation results and trigger realization, which produces voicing plans and bass lines assembled into arrangement candidates.

M2a is the first of three sub-milestones splitting the original M2 "Realization MVP":

| Sub-milestone | Scope | Exit Criteria |
|---|---|---|
| **M2a** | Voicing + bass generation, arrangement assembly, persistence | User can select progressions, trigger realization, and receive arrangements with voicing + bass data persisted in Neo4j |
| **M2b** | Arrangement evaluation, ranking, bass mode selector | Arrangements have scorecards (voice leading, register/density, playability), ranked by weighted scoring, user can choose bass mode |
| **M2c** | Piano roll, Tone.js playback, arrangement detail view | User can see and hear arrangements in the browser |

The spec's full M2 exit criteria ("explore realizations, see scorecards, hear playback") is satisfied only when M2a + M2b + M2c are all complete.

## 2. Key Design Decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | Gemini proposes voicing *strategy*, deterministic engine realizes notes | LLMs are unreliable at exact pitch enumeration; keeps quality auditable and testable |
| D2 | One genre-default bass mode per arrangement | Simplifies M2a; user bass mode selection deferred to M2b |
| D3 | 2-3 voicing variants per progression via parameter sweep | One Gemini call per progression, engine sweeps voicing_type (open/drop2/close) for variants |
| D4 | Named pitches canonical (`"C4"`), MIDI numbers derived | Human-readable, music21-native, avoids enharmonic ambiguity; MIDI conversion trivial for M2c |
| D5 | User-initiated realization (not automatic) | Saves Gemini calls on uninteresting progressions; keeps user in control |
| D6 | Voicing preferences in genre YAML profiles | Single source of truth for genre-specific musical knowledge; already loaded by sync pipeline |
| D7 | Three LangGraph nodes (plan_voicings, generate_bass, assemble) over single realize node | Granular SSE progress, independent testability, future parallelization path |
| D8 | Separate RealizationState TypedDict | Avoids polluting ExplorationState with unrelated fields; clean graph boundary |
| D9 | Gemini Flash for plan_voicings (not Pro) | Strategy description is constrained, low-creativity; saves cost and latency |
| D10 | Genre profiles override variant voicing types | Dream Pop might only generate open + drop2; Synthwave might favor close + root-position |

## 3. LangGraph Pipeline

```
load_context → plan_voicings → generate_bass → assemble → persist_realization
```

### Node Descriptions

**load_context** — Hydrates selected progression(s), genre profile (with voicing + bass preferences), and creative brief from Neo4j. Retrieval path:
1. `ProgressionCandidateRepo.get(candidate_id)` → candidate (raises `ValueError` if not found; route handler returns 404)
2. `SessionRepo.get(candidate.session_id)` → session
3. `GenreProfileRepo.query_by_property("genre", session.genre)` → genre profile with voicing/bass preferences
4. `CreativeBriefRepo.query_by_property("session_id", session.id)` → creative brief

**plan_voicings** — One Gemini Flash call per progression returns a `VoicingStrategyResponse`. The deterministic engine then realizes 2-3 `VoicingPlan` variants by sweeping voicing types from the genre's `variant_voicing_types` list. Applies voice-leading optimization between adjacent chords (common-tone retention, minimal leaps).

**generate_bass** — Pure deterministic. Reads `default_bass_mode` from genre profile. Applies genre-specific rhythm templates to chord roots at the genre bass register. No Gemini call.

**assemble** — Combines each voicing variant + the single bass line into an `ArrangementCandidate`. Groups variants under an `ArrangementFamily` per progression. The first variant in sweep order becomes `root_arrangement_candidate_id` on the family.

**persist_realization** — Writes entities to Neo4j in dependency order: VoicingPlan → BassLine → ArrangementCandidate → ArrangementFamily (relationships require target nodes to exist first). See Section 8 for relationships.

### Data Flow Example

```
1 selected progression (Cmaj7 → Am9 → Fmaj7 → G7)
    ↓ Gemini Flash
1 VoicingStrategyResponse ("open, mid-high, 4 voices, favor 7ths")
    ↓ deterministic engine sweeps [open, drop2, close]
3 VoicingPlans (one per voicing type)
    ↓ deterministic bass (supportive mode, Dream Pop)
1 BassLine (root whole notes at octave 2)
    ↓ assemble
3 ArrangementCandidates (one per voicing variant, sharing the bass line)
    ↓ grouped under
1 ArrangementFamily
```

## 4. Data Models

### New Pydantic Models

```python
class VoicingEvent(BaseModel):
    bar: int
    beat: float = 1.0
    duration_beats: float = 4.0
    pitches: list[str]          # ["C3", "G3", "E4", "B4"]
    chord_symbol: str           # "Cmaj7"

class BassNoteEvent(BaseModel):
    bar: int
    beat: float = 1.0
    duration_beats: float = 1.0
    pitch: str                  # "C2"
    velocity: int = 80
```

### Updated Existing Models

- `VoicingPlan.voicing_events: list[VoicingEvent]` (was `list[dict[str, Any]]`)
- `BassLine.note_events: list[BassNoteEvent]` (was `list[dict[str, Any]]`)

### BaseEntity Field Conventions

All M2a entities inherit `BaseEntity` which requires `id`, `type`, and `status`. Convention for new entities:

| Entity | `id` | `type` | `status` |
|---|---|---|---|
| VoicingPlan | `uuid4()` | `"voicing_plan"` | `"draft"` |
| BassLine | `uuid4()` | `"bass_line"` | `"draft"` |
| ArrangementCandidate | `uuid4()` | `"arrangement_candidate"` | `"draft"` |
| ArrangementFamily | `uuid4()` | `"arrangement_family"` | `"active"` |

`ArrangementCandidate` extends `CandidateBase`, which also requires `session_id` (from the progression's session), `rationale` (set to a description of the voicing variant, e.g., "open voicing, mid-high register"), and `intent_tags` (inherited from the source progression).

### Gemini Response Schema

```python
VoicingType = Literal["open", "close", "drop2", "drop3"]
RegisterLabel = Literal["low", "mid", "mid_high", "high"]
DensityLevel = Literal["thin", "medium", "full"]

class ChordVoicingInstruction(BaseModel):
    chord_symbol: str
    voicing_type: VoicingType
    target_register: RegisterLabel
    extensions_to_include: list[str]
    doubling_notes: list[str] | None = None
    avoid: list[str] | None = None

class VoicingStrategyResponse(BaseModel):
    global_strategy: str
    density_level: DensityLevel
    voice_count: int               # 3, 4, or 5
    per_chord: list[ChordVoicingInstruction]
```

**Gemini validation fallback**: If Gemini returns an invalid `voicing_type` or missing `voice_count`, the node falls back to genre YAML defaults (`default_voicing_type`, `default_voice_count`). Invalid `per_chord` entries are replaced with genre defaults for that chord. A warning is logged but generation proceeds — partial strategy is better than no strategy.

### Variant Configuration

```python
class VariantConfig(BaseModel):
    voicing_type: VoicingType
```

Genre profiles provide `variant_voicing_types` to override the default sweep list.

### Voice-Leading Check (used internally by VoicingGenerator)

```python
class VoiceLeadingCheck(BaseModel):
    common_tones: int              # number of shared pitches between adjacent voicings
    total_semitone_distance: int   # sum of all voice movements in semitones
    max_leap: int                  # largest single voice movement in semitones
    has_parallel_fifths: bool
    has_parallel_octaves: bool
```

### Genre Preference Sub-Models (added to style.py)

```python
class VoicingPreferences(BaseModel):
    default_voicing_type: VoicingType = "open"
    default_register: RegisterLabel = "mid"
    default_density: DensityLevel = "medium"
    default_voice_count: int = 4
    favor_extensions: bool = False
    top_voice_continuity: str = "medium"       # "low", "medium", "high"
    variant_voicing_types: list[VoicingType] = Field(default_factory=lambda: ["open", "drop2", "close"])

class BassPreferences(BaseModel):
    default_bass_mode: str = "supportive"      # "supportive", "pedal", "walking", "syncopated"
    default_register: str = "low"              # "sub_low", "low"
    rhythmic_density: str = "moderate"         # "sparse", "moderate", "active"
```

Update `GenreProfile` to include:
```python
class GenreProfile(BaseEntity):
    # ... existing fields ...
    voicing_preferences: VoicingPreferences = Field(default_factory=VoicingPreferences)
    bass_preferences: BassPreferences = Field(default_factory=BassPreferences)
```

Default factories ensure backward compatibility — existing genres without these fields in YAML get sensible defaults.

## 5. RealizationState

```python
class RealizationState(TypedDict, total=False):
    # Input
    session_id: str
    progression_candidate_ids: list[str]

    # Hydrated by load_context
    progression_candidates: list[ProgressionCandidate]
    genre_profile: GenreProfile
    creative_brief: CreativeBrief

    # Produced by plan_voicings
    voicing_strategies: list[VoicingStrategyResponse]
    voicing_plans: list[VoicingPlan]

    # Produced by generate_bass
    bass_lines: list[BassLine]

    # Produced by assemble
    arrangement_candidates: list[ArrangementCandidate]

    # SSE callback
    on_progress: Any
```

Separate from `ExplorationState`. Built by `build_realization_graph()`. M1 graph is untouched.

## 6. Genre YAML Extension

New fields added to each genre profile:

```yaml
voicing_preferences:
  default_voicing_type: open
  default_register: mid_high
  default_density: medium
  default_voice_count: 4
  favor_extensions: true
  top_voice_continuity: high
  variant_voicing_types: [open, drop2]

bass_preferences:
  default_bass_mode: supportive
  default_register: low
  rhythmic_density: sparse
```

### Genre Defaults

| Genre | Voicing Type | Register | Variants | Bass Mode | Bass Density |
|---|---|---|---|---|---|
| Dream Pop | open | mid_high | open, drop2 | supportive | sparse |
| Synthwave | close | mid | close, drop2, open | supportive | moderate |
| Cinematic | open | mid | open, drop3, drop2 | pedal | sparse |

Existing `voicing_tendencies` and `bass_tendencies` dicts remain for Gemini prompt context. These new structured fields are consumed programmatically by the engine.

## 7. Deterministic Algorithms

### Voicing Realization

`VoicingGenerator.realize(strategy, chord_events, genre_profile, variant_config)` → `VoicingPlan`

Per chord in the progression:

1. Parse chord symbol via music21 adapter → pitch classes (`Cmaj7` → `[C, E, G, B]`)
2. Add requested extensions from `ChordVoicingInstruction` (e.g., 9th → add D)
3. Apply voicing technique from `variant_config.voicing_type`:
   - **close**: stack pitches ascending within one octave from target register
   - **open**: spread across ~2 octaves, alternate skip/step
   - **drop-2**: close position, drop second-from-top voice down one octave
   - **drop-3**: close position, drop third-from-top voice down one octave
4. Clamp to target register (low=C2-C4, mid=C3-C5, mid_high=C4-C6, high=C5-C7)
5. Apply genre constraints: remove doublings if `favor_extensions`, enforce `voice_count`
6. **Voice-leading optimization** (pairwise, greedy — not global):
   - For the first chord in the progression, use the default inversion from the voicing technique
   - For each subsequent chord, generate all valid inversions within the target register
   - Score each candidate inversion using `check_voice_leading(prev_pitches, candidate_pitches)`:
     - Cost = `total_semitone_distance - (common_tones * 4)` (common tones reduce cost)
     - Reject candidates with `has_parallel_fifths` or `has_parallel_octaves`
     - Among remaining candidates, pick the one with lowest cost
   - This is O(inversions × voices) per chord — fast for 4-voice chords with 3-4 inversions
7. Output: `VoicingEvent(pitches=["C3", "G3", "E4", "B4"], ...)`

New music21 adapter functions:
- `realize_voicing(chord_symbol, voicing_type, target_register, voice_count, extensions)` → `list[str]`
- `check_voice_leading(prev_pitches: list[str], next_pitches: list[str])` → `VoiceLeadingCheck`

### Bass Realization

`BassLineGenerator.generate(progression, genre_profile)` → `BassLine`

Pure deterministic. Reads `bass_preferences` from genre profile. For "supportive" mode:

| Genre | Pattern | Register |
|---|---|---|
| Dream Pop | Root whole note per bar | Octave 2 |
| Synthwave | Root on beat 1, octave on beat 3 | Octave 2 |
| Cinematic | Root on beat 1 sustained, 5th on beat 3 every other bar | Octave 1-2 |

No Gemini call for supportive mode. More complex modes (walking, syncopated, countermelodic) deferred to M2b.

## 8. Neo4j Persistence

### New Relationships

```
(ProgressionCandidate)-[:REALIZED_AS]->(ArrangementCandidate)
(ArrangementCandidate)-[:USES_VOICING_PLAN]->(VoicingPlan)
(ArrangementCandidate)-[:USES_BASS_LINE]->(BassLine)
(ArrangementFamily)-[:CONTAINS]->(ArrangementCandidate)
```

### New Repositories

Following M1's `BaseRepository` pattern:
- `VoicingPlanRepo`
- `BassLineRepo`
- `ArrangementCandidateRepo`
- `ArrangementFamilyRepo`

Unlike M1's property-only persistence, M2a writes actual Neo4j relationships since the arrangement graph is inherently relational.

### Persist Write Order

`persist_realization` writes in dependency order:

1. **VoicingPlan nodes** — one per variant (2-3 per progression)
2. **BassLine nodes** — one per progression
3. **ArrangementCandidate nodes** — one per variant, then create relationships:
   - `(ProgressionCandidate)-[:REALIZED_AS]->(ArrangementCandidate)`
   - `(ArrangementCandidate)-[:USES_VOICING_PLAN]->(VoicingPlan)`
   - `(ArrangementCandidate)-[:USES_BASS_LINE]->(BassLine)`
4. **ArrangementFamily node** — one per progression, then:
   - `(ArrangementFamily)-[:CONTAINS]->(ArrangementCandidate)` for each variant

Each relationship is created via a Cypher `MATCH ... CREATE` after both endpoints exist. The repos handle node creation; relationship creation uses direct Cypher via the Neo4j driver (same pattern as future M2b evaluation linking).

## 9. API Surface

### New Endpoints

```
POST /v1/sessions/{session_id}/realization-rounds
Body: { "progression_candidate_ids": ["uuid1", "uuid2"] }
Response: SSE stream

GET /v1/candidates/{id}/arrangements
Response: list of ArrangementCandidate summaries

GET /v1/arrangements/{id}
Response: full arrangement detail (voicing events + bass events)
```

### SSE Events

```
event: node_started    data: {"node": "load_context"}
event: node_started    data: {"node": "plan_voicings"}
event: node_started    data: {"node": "generate_bass"}
event: node_started    data: {"node": "assemble"}
event: node_started    data: {"node": "persist_realization"}
event: realization_completed    data: {"arrangement_candidate_ids": [...]}
```

Node names use actual M2a names (not the spec's `realize`). The terminal event is `realization_completed` (not M1's `round_completed`) to distinguish the two pipeline types in frontend routing. Both divergences are intentional.

## 10. Performance Budget

| Node | Target | Notes |
|---|---|---|
| load_context | <500ms | Neo4j reads, proven fast in M1 |
| plan_voicings | ~2-3s | One Gemini Flash call per progression |
| generate_bass | <200ms | Pure deterministic |
| assemble | <100ms | Pure combination |
| persist_realization | <500ms | Neo4j writes with relationships |
| **Total per progression** | **~3-4s** | |

For 2 selected progressions x 3 variants = 6 arrangements in ~7-8s. Well under M1's 15-20s baseline.

## 11. File Structure

### Backend Additions

```
backend/src/explorator/
  domain/realization/
    __init__.py
    voicing.py          # VoicingGenerator class
    bass.py             # BassLineGenerator class
    assembly.py         # ArrangementAssembler class
  engine/
    nodes/
      load_context.py
      plan_voicings.py
      generate_bass.py
      assemble.py
      persist_realization.py
    realization_graph.py  # build_realization_graph()
    realization_state.py  # RealizationState TypedDict
  graph/
    voicing_plan_repo.py
    bass_line_repo.py
    arrangement_candidate_repo.py
    arrangement_family_repo.py
  api/routes/
    realization_rounds.py
  prompts/
    voicing.py          # plan_voicings prompt template
```

### Model Updates

```
backend/src/explorator/models/
  realization.py        # Add VoicingEvent, BassNoteEvent, VariantConfig;
                        # Update VoicingPlan.voicing_events, BassLine.note_events
```

### Genre YAML Updates

```
backend/src/explorator/data/genres/
  dream_pop.yaml        # Add voicing_preferences, bass_preferences
  synthwave.yaml
  cinematic.yaml
```

## 12. Explicit Deferrals

| Requirement | Spec Ref | Deferred To | Rationale |
|---|---|---|---|
| VoiceLeadingEvaluator | R4, S11.1 | M2b | Evaluation depends on generation being proven first |
| RegisterDensityEvaluator | R4, S11.1 | M2b | Same |
| PlayabilityEvaluator | R4, S11.1 | M2b | Same |
| `evaluate_arrangements` node | R11, S4.2 | M2b | Evaluation node follows evaluator services |
| `rank_and_select` for arrangements | R5, S4.2 | M2b | Ranking requires scores to rank by |
| Hybrid evaluation strategy | R16, S11.2 | M2b | Part of evaluation milestone |
| User bass mode selector | R20, S4.5 | M2b | Genre-default sufficient for M2a |
| External chord input (realization mode) | R8, S4.6 | M2c | Separate input flow, lower priority than core pipeline |
| Piano roll visualization | R6, S9.3 | M2c | Frontend milestone |
| Tone.js playback | R7, S9.3 | M2c | Frontend milestone |
| Pareto front ranking | S13 | M3 | Spec already defers this |
| Multiple bass modes per arrangement | R20 | M2b | User selection added with evaluation |
| Mode-scaling voicing toggle (conservative/balanced/exploratory) | — | Post-M2a | Planned enhancement once evaluation can rank variants |
| MIDI derivation/export | R14 | M2c | Only needed for Tone.js playback |

## 13. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Gemini Flash voicing strategies are too vague | Deterministic engine can't realize meaningful pitches | Fall back to genre YAML defaults if strategy fields are empty; add structured validation on response |
| Voice-leading optimization is computationally expensive | Slow generation for long progressions | Limit to pairwise comparison (each chord vs. previous only); no global optimization |
| Voicing events stored as JSON blobs in Neo4j | Not queryable by Cypher for M2b evaluation | Flag as known limitation; M2b may need property extraction at persist time |
| Genre doesn't store on ProgressionCandidate | load_context requires extra hop (candidate → session → genre) | Acceptable; session is always loaded anyway |
