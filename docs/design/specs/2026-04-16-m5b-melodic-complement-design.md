# M5b — Melodic Complement Generation: Design Spec

**Date:** 2026-04-16
**Status:** Draft
**Depends on:** M5a (complete), M5 expanded musical surface design spec (sections 3.1–3.7)

## 1. Overview

M5b adds a single-line melody voice on top of existing arrangements. The melody fits the harmonic progression, respects the voicing register, follows genre-appropriate conventions, and aligns with the groove pattern when present.

**Generation approach:** Two-phase, mirroring the voicing pattern — Gemini Flash for strategy (Phase 1), deterministic realization into concrete pitches (Phase 2).

### 1.1 Scope

**In scope:**
- MelodicComplement model and entity lifecycle
- Genre YAML `melodic_tendencies` section for all three genres
- Gemini strategy prompt producing per-phrase instructions
- Deterministic melody realization with constraint-based pitch selection
- Strategy-driven phrase length (2 or 4 bars), no motif repetition
- Fallback straight-eighths beat grid when no groove pattern available
- Two deterministic evaluation dimensions (melody_support, collision_risk)
- Frontend: piano roll melody lane, transport mute toggle, comparison view lane
- Single default melody synth for all genres

**Not in scope (deferred):**
- Motif repetition / recall (AABA, call-and-response patterns)
- Genre-specific melody synth presets (`playback_hints` / `melody_preset` in YAML) — deferred to M5c
- Gemini `tension_justification_score` evaluation dimension
- Explicit tension/release point mapping in strategy response — implicitly handled via per-phrase contour and strong-beat targets; explicit tension fields deferred until tension evaluation is activated
- Melody velocity variation from groove accents
- `melodic_deviation_tolerance` in experimentation envelope
- Melody regeneration on arrangement-scope mutations (see Section 6.5)

### 1.2 Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Generation approach | Gemini strategy + deterministic realization | Proven pattern in codebase (voicing), debuggable, cost-effective. Swappable to LLM realization later if needed. |
| Phrase structure | Strategy-driven length, no motif repetition | Variable phrase length is cheap (loop boundary). Motif repetition is complex and deferrable. |
| Groove fallback | Synthesize straight-eighths grid | Keeps code path uniform — generator always receives a beat grid. |
| Synth presets | Single default for all genres | Core value is melodic correctness, not timbre. Genre presets land naturally with M5c. |
| Evaluation | Two deterministic dimensions only | Covers real failure modes (wrong notes, collisions). LLM tension call is quality-of-life, not blocking. |

---

## 2. MelodicComplement Model

New entity extending `BaseEntity`. ULID prefix: `mc_`. Lives in `models/melody.py` (new file, following the M5a precedent where `GroovePattern` lives in `models/groove.py` rather than `models/realization.py`).

Separate from the existing `Melody` stub in `stubs.py`, which is reserved for user-supplied melody input in reharm mode (v1.5). Different fields, different lifecycle, different pipeline linkage.

```python
class MelodicNoteEvent(BaseModel):
    bar: int
    beat: float = 1.0           # beat position within the bar (1.0-based)
    duration_beats: float = 1.0
    pitch: str                  # e.g. "C5"
    velocity: int = 80

class MelodicComplement(BaseEntity):
    arrangement_candidate_id: str
    groove_pattern_id: str | None = None
    note_events: list[MelodicNoteEvent] = Field(default_factory=list)
    range_low: str = ""         # e.g. "C5"
    range_high: str = ""        # e.g. "C6"
    contour_type: str = ""      # "arch", "descending", "wave", "static"
    source_strategy: str = ""   # reference to the strategy that generated this
```

Field defaults follow `VoicingPlan`/`BassLine` conventions (`default_factory=list` for event lists, empty-string defaults for string fields). The entity is linked to the arrangement via `arrangement_candidate_id`, not to the session directly — melody is a per-arrangement artifact, like voicing and bass.

`ArrangementCandidate.melodic_complement_id` (already nullable in the model) gets populated at assembly time.

**ExplorationState** gains a new key: `melodic_complements: list[dict[str, Any]]`, following the same pattern as `groove_patterns`.

---

## 3. Genre YAML Extensions

Each genre profile gets a new `melodic_tendencies` section, following the pattern of `voicing_tendencies`, `bass_tendencies`, and `groove_tendencies`.

```yaml
melodic_tendencies:
  motion_preference: stepwise      # stepwise | leaping | mixed
  range_placement: above_voicing   # above_voicing | interleaved (above_voicing for M5b)
  density: sparse                  # sparse | moderate | active
  phrase_length: 4                 # 2 | 4 (bars)
  strong_beat_preference: extensions  # chord_tones | extensions | roots_and_fifths
  rest_between_phrases: true
```

### 3.1 Per-Genre Defaults

| Genre | motion_preference | density | phrase_length | strong_beat_preference |
|-------|-------------------|---------|---------------|----------------------|
| dream_pop | stepwise | sparse | 4 | extensions |
| synthwave | mixed | moderate | 2 | chord_tones |
| cinematic | leaping | sparse | 4 | roots_and_fifths |

All three genres use `range_placement: above_voicing` and `rest_between_phrases: true`.

No `melodic_deviation_tolerance` in the experimentation envelope. Melody quality is governed by Phase 2's hard constraints and the two deterministic evaluation dimensions, not a deviation bound.

---

## 4. Melody Strategy Prompt (Phase 1)

New prompt template at `prompts/melody.py`, following the `prompts/voicing.py` pattern. Returns `(user_prompt, system_prompt)` (same order as `voicing_strategy_prompt`).

### 4.1 System Prompt

"You are an expert melodist composing a single-line melody over an existing arrangement."

### 4.2 User Prompt Context

All available from state at generation time:

- Chord progression with bar numbers
- Key center and mode
- Voicing register summary (highest notes per bar — so melody knows the ceiling to stay above)
- Bass range summary (lowest notes — for full picture)
- Groove pattern summary (beat grid with accents, or "straight eighths" fallback)
- Genre melodic tendencies (the YAML section from Section 3)

### 4.3 Structured Output — MelodicStrategyResponse

Lives in `models/melody.py` alongside `MelodicComplement`.

```python
class PhraseInstruction(BaseModel):
    start_bar: int
    end_bar: int                    # inclusive
    contour: str                    # "arch", "descending", "ascending", "wave", "static"
    density: str                    # "sparse", "moderate", "active"
    strong_beat_targets: list[str]  # e.g. ["root", "7th", "5th"] — scale degrees to favor
    rest_after: bool                # insert rest gap after this phrase

class MelodicStrategyResponse(BaseModel):
    range_low: str                  # e.g. "C5"
    range_high: str                 # e.g. "C6"
    overall_contour: str            # summary descriptor
    phrase_instructions: list[PhraseInstruction]
    rationale: str = Field(default="", max_length=200)  # matches VoicingStrategyResponse convention
```

One Gemini Flash call per arrangement candidate. Phrase instructions cover the full progression — for an 8-bar progression with 4-bar phrases, you get 2 `PhraseInstruction` entries.

---

## 5. Deterministic Melody Realization (Phase 2)

New domain service `MelodyGenerator` at `domain/realization/melody.py`, following the `GrooveGenerator` pattern.

### 5.1 Input

`MelodicStrategyResponse` + chord progression + key center and mode + voicing events + beat grid (from GroovePattern or straight-eighths fallback).

### 5.2 Algorithm (per phrase)

**Step 1 — Set up beat grid.** Collect onset positions from the groove pattern (or synthesize straight-eighths) for bars in this phrase. **Coordinate transformation**: GroovePattern events use absolute beat positions; these must be converted to per-bar `(bar, beat_within_bar)` pairs before use — this is the same transformation needed for groove-driven bass (see `d4b792c`). Filter the per-bar positions to match density (in 4/4):
- **Sparse**: beats 1 and 3
- **Moderate**: beats 1, 2, 3, 4
- **Active**: all eighth-note positions from the grid

Groove accent events are included regardless of density filter — if the groove marks beat 2.5 as accented, it appears even at "moderate" density.

**Phrase length vs. progression length**: If the progression length is not evenly divisible by the phrase length (e.g. 7 bars with 4-bar phrases), the final phrase is truncated to cover the remaining bars. Single-bar remainders are merged into the preceding phrase rather than standing alone.

**Steps 2–4 are integrated, not sequential passes.** For each onset position in the beat grid, the generator selects a pitch by applying Steps 2, 3, and 4 together as selection criteria. The description below separates them for clarity, but implementation interleaves them in a single forward pass through the beat grid.

**Step 2 — Strong beat targeting.** For each downbeat position, pick a pitch from the current chord that matches the phrase's `strong_beat_targets`. If the target scale degree isn't present in the chord (e.g. "7th" on a simple triad), fall back to the nearest available chord tone measured in semitones from where the target degree would have been. Selection prefers pitches within the strategy's range that maintain stepwise or small-interval motion from the previous note. First note of first phrase defaults to a chord tone of the opening chord within the upper third of the range; if no chord tone falls in that sub-range, use the highest chord tone within the full range.

**Step 3 — Weak beat filling.** For non-downbeat positions, use diatonic passing tones and neighbor tones (relative to the current key center and mode) to connect strong-beat pitches. Genre `motion_preference` controls interval size: stepwise limits to 2nds, leaping allows 4ths/5ths, mixed allows 3rds freely with occasional larger leaps.

**Step 4 — Contour shaping.** Applied as a pitch-direction bias during Steps 2-3 tone selection, not as a separate rewrite pass. When multiple valid pitches exist for a position, contour biases the selection with ~70/30 weighting toward the preferred direction (vs. uniform random among valid options). "Arch" biases upward in the first half, downward in the second. "Ascending" biases upward throughout. "Descending" biases downward throughout. "Wave" alternates bias direction every 2 beats. "Static" applies no directional bias, letting chord-tone constraints alone determine pitch direction.

**Step 5 — Collision avoidance.** After note selection, check each event against voicing events on the same bar/beat. If a unison or minor 2nd collision exists, shift the melody note up by a diatonic step. If the shift creates a new collision or exceeds range ceiling, try shifting down instead. If both directions create collisions or exceed range, omit the note (insert a rest). Hard constraint, always enforced.

**Step 6 — Phrase boundaries.** If `rest_after` is true, insert a quarter-rest gap after the last note of the phrase.

**Step 7 — Resolution rule.** The final phrase's last note must be a chord tone of the final chord, preferring root or 5th. (Intentional simplification: the original M5 spec says "resolves to tonic area," but targeting the final chord's tones is simpler to implement and produces correct results when the progression ends on tonic, which is the common case for all three initial genres. For progressions ending on non-tonic chords — e.g. deceptive cadences — this still produces a consonant ending.)

### 5.3 Validation of MelodicStrategyResponse

Before realization, validate the Gemini response:
- Phrase instructions must cover all bars of the progression without gaps or overlaps
- `start_bar` must be <= `end_bar` for each instruction
- `range_low` must be below `range_high`
- All `contour` and `density` values must be from the allowed enums

If validation fails, fall back to a default strategy: single phrase covering the full progression, "arch" contour, "moderate" density, chord-tone strong-beat targets, range one octave above the voicing ceiling.

### 5.4 Output

`MelodicComplement` entity with populated `note_events`, `range_low`/`range_high` from strategy, `contour_type` from `overall_contour`, `source_strategy` referencing the strategy response.

No motif repetition — each phrase is independently realized. Velocity is uniform (80); groove accent influence on melody velocity is a future enhancement.

---

## 6. Pipeline Integration

New LangGraph node `generate_melody` in `engine/nodes/generate_melody.py`. This is a **hybrid node**: it follows `generate_groove.py` for state access and return patterns, but follows `plan_voicings` for the LLM strategy call (requires Gemini client injection via `partial(generate_melody, gemini=gemini)` in `graph.py`, matching the `plan_voicings` pattern at `graph.py:44`).

### 6.1 Pipeline Position

```
plan_voicings → generate_bass → generate_groove → generate_melody → assemble_arrangements
```

### 6.2 Node Logic

1. Read from state: `voicing_plans`, `bass_lines`, `groove_patterns`, `progression_candidates`, genre profile (including key center and mode)
2. For each (voicing plan, bass line) pair per progression:
   - Extract voicing register summary (highest note per bar) and bass range
   - Select a groove pattern for beat grid context: use the first available groove pattern for this progression, or synthesize a straight-eighths fallback if `groove_patterns` is empty. (Melody does not need per-groove variants — the beat grid is used for rhythmic alignment, not as a distinguishing factor. The groove round-robin assignment in assembly may assign a different groove to the final arrangement, but the rhythmic grid differences between groove variants are minor enough that the melody remains valid.)
   - Call `melody_strategy_prompt()` → Gemini Flash → `MelodicStrategyResponse`
   - Validate response (Section 5.3); fall back to default strategy on failure
   - Call `MelodyGenerator.realize()` with strategy + chord progression + key center/mode + voicing events + beat grid
   - Produce `MelodicComplement` entity with `arrangement_candidate_id = None` (linked at assembly time)
3. Write `melodic_complements` list to state

One melody per (voicing plan, bass line) pair. This matches the assembly cross-product granularity — the `assemble_arrangements` node builds one `ArrangementCandidate` per (VP x BL) pair.

### 6.3 Assembly Changes

Melody linkage follows the **groove round-robin pattern** used in `assemble_arrangements.py:85-90`. After the cross-product loop builds `all_candidates`, a second pass assigns `melodic_complement_id` from the `melodic_complements` state list:

```python
# Assign melodic_complement_id via round-robin (matching groove pattern)
melodic_complements_raw = state.get("melodic_complements", [])
if melodic_complements_raw:
    mc_ids = [mc["id"] for mc in melodic_complements_raw]
    for idx, cand in enumerate(all_candidates):
        cand["melodic_complement_id"] = mc_ids[idx % len(mc_ids)]
```

No changes to `assemble_one()` or `assemble_family()` — melody is linked post-hoc on the serialized dicts, not passed as a constructor parameter.

### 6.4 Backward Compatibility

If `melodic_complements` is empty in state (legacy sessions, or generation skipped), the round-robin assignment is skipped and `melodic_complement_id` remains `None`. No behavior change for existing sessions.

### 6.5 Known Limitation: Mutation Loop

The arrangement-scope mutation loop in the pipeline re-enters at `evaluate_arrangements`, skipping `generate_melody`. This means mutated arrangements retain their original melody — if a mutation changes voicing register, the melody is not regenerated to match. The `collision_risk_score` evaluation dimension will catch new collisions introduced by the mutation, penalizing the arrangement's score. Full melody regeneration on mutation is deferred as a future enhancement.

---

## 7. MelodyHarmonyEvaluation

Implements the existing stub in `evaluation.py` with two deterministic dimensions. Only active when `ArrangementCandidate.melodic_complement_id` is non-null.

### 7.1 Dimensions

All scores use the 0.0–10.0 scale, consistent with existing evaluators (`VoiceLeadingEvaluator`, `GrooveEvaluator`, etc.).

**melody_support_score** (deterministic) — two sub-metrics averaged:
- *Chord-tone ratio on strong beats*: `ratio * 10.0` where ratio is the proportion of downbeat melody notes that are chord tones (or strategy-specified target degrees) of the current chord. Perfect score at 10.0, degrades linearly.
- *Voice-leading smoothness*: `ratio * 10.0` where ratio is the proportion of consecutive melody intervals that are a 3rd or smaller. Penalizes large leaps unless genre `motion_preference` is "leaping" (in which case 4ths/5ths don't penalize).

**collision_risk_score** (deterministic) — count of unisons and minor 2nds between melody note events and voicing events on the same bar/beat. Scored as `(1.0 - (collision_count / total_melody_events)) * 10.0`, floored at 0.0. A collision-free melody scores 10.0.

When `melodic_complement_id` is null (no melody), the evaluation node returns a default score of 5.0 for both dimensions (matching the groove evaluator's pattern for missing groove patterns at `evaluate_arrangements.py:97`).

### 7.2 Weight Integration

`CANONICAL_DEFAULT_WEIGHTS` in `ranking.py` is updated with all 12 dimensions summing to 1.0. Existing weights are scaled by 0.75 to make room for the two melody dimensions (0.25 total):

| Dimension | Current | With Melody |
|-----------|---------|-------------|
| genre_fit | 0.13 | 0.10 |
| emotional_fit | 0.09 | 0.07 |
| theoretical_coherence | 0.11 | 0.08 |
| cadence_quality | 0.09 | 0.07 |
| novelty | 0.09 | 0.07 |
| loopability | 0.12 | 0.09 |
| voice_leading | 0.10 | 0.07 |
| register_density | 0.08 | 0.06 |
| playability | 0.08 | 0.06 |
| groove | 0.11 | 0.08 |
| **melody_support** | — | **0.15** |
| **collision_risk** | — | **0.10** |
| **Total** | 1.00 | **1.00** |

**Conditional weight normalization:** Normalization happens at weight *application* time (in `weighted_score()` in `ranking.py`), not at storage time. `ObjectiveWeights` stores the full 12-dimension weight set (summing to 1.0). At scoring time, check whether the session's arrangements include melodic complements. If yes, apply all weights as stored. If no, exclude `melody_support` and `collision_risk` weights and renormalize the remaining 10 weights proportionally so they sum to 1.0 (i.e., divide each by 0.75). This preserves the existing `ObjectiveWeights` validator while allowing melody-less sessions to score correctly. This is a session-level check — all candidates in a session go through the same pipeline.

The `MelodyHarmonyEvaluator` uses ULID prefix `mhev_` for its evaluation entity IDs.

### 7.3 Deferred

`tension_justification_score` field stays in the model as `None`. No LLM call. Can be activated later without changing the evaluation pipeline interface.

---

## 8. Frontend Changes

**Implementation note:** Invoke the `frontend-design` skill when implementing this section for piano roll lane design, transport bar changes, and comparison view melody integration.

### 8.1 Piano Roll

`PianoRoll.tsx` gains a third note lane for melody, rendered in a distinct color from the design tokens (separate from voicing and bass colors). Melody notes render in the same coordinate space — they naturally sit above voicing events due to their higher register. A third rendering pass over `melodic_complement.note_events`.

**Required updates to existing functions:**
- `collectMidiValues()` (line 30): must include melody note pitches in MIDI range calculation, or the canvas Y-axis will clip melody notes (since melody has the highest pitches in the arrangement)
- `hasEvents` guard (line 66): must include melody events so the "No events to display" fallback accounts for melody-only scenarios
- `allBars` calculation (line 84): must include melody bar extents for total bar count

### 8.2 Transport Bar

`TransportBar.tsx` gets a third mute toggle button for melody alongside the existing Chords and Bass toggles.

### 8.3 Audio Store

`audioStore.ts` `mutedTracks` expands from `{ voicing: boolean; bass: boolean }` to `{ voicing: boolean; bass: boolean; melody: boolean }`. `toggleMute` union type gains `"melody"`. Reset function updated.

### 8.4 Melody Synth

Single default `MonoSynth` (melody is single-line, so monophonic is correct — matching bass which also uses `MonoSynth`). Triangle-wave oscillator with moderate attack/release. Added to `audioPresets.ts` as a standalone `MELODY_DEFAULT: SynthOptions` constant, **not** part of the `GenrePreset` interface. The `audioEngine.ts` play function constructs the melody synth from this constant directly, not via `getPreset()`. Genre-specific presets deferred to M5c (at which point `GenrePreset` gains a `melody` field).

### 8.5 Comparison Playback

The current comparison audio engine (`comparisonAudioEngine.ts`) uses **per-lane muting** — one shared `Volume` node per candidate, with `mutedLanes: Record<string, boolean>` in `comparisonAudioStore.ts`. Voicing and bass within a lane share a single volume and cannot be independently muted.

Adding melody as a separately mutable track within each lane requires expanding `LaneSynths` from `{ poly, mono, vol }` to separate volumes per track:

```typescript
interface LaneSynths {
  poly: PolySynth        // voicing
  mono: MonoSynth        // bass
  melody: MonoSynth      // melody (new)
  voicingVol: Volume      // per-track volume (new)
  bassVol: Volume         // per-track volume (new)
  melodyVol: Volume       // per-track volume (new)
  laneVol: Volume         // master lane volume (existing vol, renamed)
}
```

`comparisonAudioStore.ts` expands from `mutedLanes` to a two-dimensional model: `trackMutes: Record<string, { voicing: boolean; bass: boolean; melody: boolean }>` keyed by `candidateId`. The existing `toggleMute(candidateId)` for lane-level muting is preserved; a new `toggleTrackMute(candidateId, track)` handles per-track muting within a lane.

### 8.6 Conditional Rendering

All melody UI elements are conditional on `melodic_complement_id` being non-null in the arrangement data. Legacy arrangements without melody show no melody toggle, no melody lane — no visual change from current behavior.

---

## 9. E2E Tests (5-6 new)

1. Melody generated as part of realization pipeline
2. Melody renders in piano roll as distinct color lane
3. Melody playback toggle in single-arrangement view
4. Melody mute/solo in comparison view
5. Melody register avoids voicing collision zone (no unisons/minor 2nds)
6. MelodyHarmonyEvaluation scores appear when melody present, absent when not

**Expected test count after M5b:** 33-35 (28 existing + 5-6 new).

---

## 10. File Manifest

### Backend

| File | Action | Purpose |
|------|--------|---------|
| `models/melody.py` | Create | `MelodicNoteEvent`, `MelodicComplement`, `PhraseInstruction`, `MelodicStrategyResponse` |
| `engine/state.py` | Edit | Add `melodic_complements` key |
| `domain/style/genres/dream_pop.yaml` | Edit | Add `melodic_tendencies` |
| `domain/style/genres/synthwave.yaml` | Edit | Add `melodic_tendencies` |
| `domain/style/genres/cinematic.yaml` | Edit | Add `melodic_tendencies` |
| `prompts/melody.py` | Create | Strategy prompt template |
| `domain/realization/melody.py` | Create | `MelodyGenerator` service |
| `engine/nodes/generate_melody.py` | Create | LangGraph node (hybrid: groove state pattern + voicing Gemini pattern) |
| `engine/nodes/assemble_arrangements.py` | Edit | Add melody round-robin assignment (matching groove pattern at lines 85-90) |
| `engine/graph.py` | Edit | Wire `generate_melody` into pipeline with `partial(generate_melody, gemini=gemini)` |
| `domain/evaluation/melody_harmony.py` | Create | `MelodyHarmonyEvaluator` (ULID prefix `mhev_`) |
| `engine/nodes/evaluate_arrangements.py` | Edit | Add conditional MelodyHarmonyEvaluator call (matching groove evaluator pattern at lines 87-98) |
| `domain/evaluation/ranking.py` | Edit | Update `CANONICAL_DEFAULT_WEIGHTS` with 12-dimension weight set; conditional normalization in `weighted_score()` |

### Frontend

| File | Action | Purpose |
|------|--------|---------|
| `frontend/src/services/api.ts` | Edit | Add `melodic_complement` to `ArrangementDetail` interface |
| `frontend/src/stores/audioStore.ts` | Edit | Add `melody` to `mutedTracks` and `toggleMute` union |
| `frontend/src/services/audioPresets.ts` | Edit | Add standalone `MELODY_DEFAULT: SynthOptions` constant |
| `frontend/src/services/audioEngine.ts` | Edit | Add melody `MonoSynth` scheduling to playback |
| `frontend/src/services/comparisonAudioEngine.ts` | Edit | Expand `LaneSynths` for per-track volumes; add melody synth per lane |
| `frontend/src/stores/comparisonAudioStore.ts` | Edit | Add `trackMutes` model and `toggleTrackMute()` action |
| `frontend/src/utils/designTokens.ts` | Edit | Add melody color token |
| `frontend/src/components/PianoRoll.tsx` | Edit | Melody lane rendering; update `collectMidiValues`, `hasEvents`, `allBars` |
| `frontend/src/components/TransportBar.tsx` | Edit | Melody mute toggle |
| `frontend/src/components/ComparisonView.tsx` | Edit | Melody lane with per-track mute/solo in DAW view |

### Tests

| File | Action | Purpose |
|------|--------|---------|
| `backend/tests/unit/domain/test_melody_generator.py` | Create | Unit tests for `MelodyGenerator` (realization algorithm, edge cases) |
| `backend/tests/unit/domain/test_melody_harmony_evaluator.py` | Create | Unit tests for `MelodyHarmonyEvaluator` |
| `backend/tests/unit/prompts/test_melody_prompt.py` | Create | Unit tests for melody strategy prompt |
| `e2e/tests/` | Create | 5-6 new E2E test files |
