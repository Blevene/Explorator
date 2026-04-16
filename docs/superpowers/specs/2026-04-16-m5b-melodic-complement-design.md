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
- Melody velocity variation from groove accents
- `melodic_deviation_tolerance` in experimentation envelope

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

New entity extending `BaseEntity`. ULID prefix: `mc_`. Lives in `models/realization.py` alongside `VoicingPlan`, `BassLine`, `ArrangementCandidate`.

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
    note_events: list[MelodicNoteEvent]
    range_low: str              # e.g. "C5"
    range_high: str             # e.g. "C6"
    contour_type: str           # "arch", "descending", "wave", "static"
    source_strategy: str        # reference to the strategy that generated this
```

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

New prompt template at `prompts/melody.py`, following the `prompts/voicing.py` pattern. Returns `(system_prompt, user_prompt)`.

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
    rationale: str                  # one sentence
```

One Gemini Flash call per arrangement candidate. Phrase instructions cover the full progression — for an 8-bar progression with 4-bar phrases, you get 2 `PhraseInstruction` entries.

---

## 5. Deterministic Melody Realization (Phase 2)

New domain service `MelodyGenerator` at `domain/realization/melody.py`, following the `GrooveGenerator` pattern.

### 5.1 Input

`MelodicStrategyResponse` + chord progression + voicing events + beat grid (from GroovePattern or straight-eighths fallback).

### 5.2 Algorithm (per phrase)

**Step 1 — Set up beat grid.** Collect onset positions from the groove pattern (or synthesize straight-eighths) for bars in this phrase. Filter to match density (in 4/4):
- **Sparse**: beats 1 and 3
- **Moderate**: beats 1, 2, 3, 4
- **Active**: all eighth-note positions from the grid

**Step 2 — Strong beat targeting.** For each downbeat position, pick a pitch from the current chord that matches the phrase's `strong_beat_targets`. If the target scale degree isn't present in the chord (e.g. "7th" on a simple triad), fall back to the nearest available chord tone. Selection prefers pitches within the strategy's range that maintain stepwise or small-interval motion from the previous note. First note of first phrase defaults to a chord tone of the opening chord within the upper third of the range.

**Step 3 — Weak beat filling.** For non-downbeat positions, use diatonic passing tones and neighbor tones to connect strong-beat pitches. Genre `motion_preference` controls interval size: stepwise limits to 2nds, leaping allows 4ths/5ths, mixed allows 3rds freely with occasional larger leaps.

**Step 4 — Contour shaping.** Apply the phrase's contour directive as a pitch-direction bias. "Arch" biases upward in the first half, downward in the second. "Ascending" biases upward throughout. "Descending" biases downward throughout. "Wave" alternates bias direction every 2 beats. "Static" applies no directional bias, letting chord-tone constraints alone determine pitch direction. The bias is soft — it influences tone selection when multiple valid options exist, it doesn't override chord-tone constraints.

**Step 5 — Collision avoidance.** After note selection, check each event against voicing events on the same bar/beat. If a unison or minor 2nd collision exists, shift the melody note up by a diatonic step. If the shift creates a new collision or exceeds range ceiling, try shifting down instead. Hard constraint, always enforced.

**Step 6 — Phrase boundaries.** If `rest_after` is true, insert a quarter-rest gap after the last note of the phrase.

**Step 7 — Resolution rule.** The final phrase's last note must be a chord tone of the final chord, preferring root or 5th.

### 5.3 Output

`MelodicComplement` entity with populated `note_events`, `range_low`/`range_high` from strategy, `contour_type` from `overall_contour`, `source_strategy` referencing the strategy response.

No motif repetition — each phrase is independently realized. Velocity is uniform (80); groove accent influence on melody velocity is a future enhancement.

---

## 6. Pipeline Integration

New LangGraph node `generate_melody` in `engine/nodes/generate_melody.py`, following the `generate_groove.py` pattern.

### 6.1 Pipeline Position

```
plan_voicings → generate_bass → generate_groove → generate_melody → assemble_arrangements
```

### 6.2 Node Logic

1. Read from state: `voicing_plans`, `bass_lines`, `groove_patterns`, `progression_candidates`, genre profile
2. For each arrangement combination (voicing plan + bass line + groove pattern):
   - Extract voicing register summary (highest note per bar) and bass range
   - Build beat grid from groove pattern, or synthesize straight-eighths fallback if `groove_patterns` is empty
   - Call `melody_strategy_prompt()` → Gemini Flash → `MelodicStrategyResponse`
   - Call `MelodyGenerator.realize()` with strategy + chord progression + voicing events + beat grid
   - Produce `MelodicComplement` entity with `arrangement_candidate_id = None` (linked at assembly time)
3. Write `melodic_complements` list to state

### 6.3 Assembly Changes

`ArrangementAssembler.assemble_one()` gains an optional `melodic_complement: MelodicComplement | None = None` parameter. When present, sets `arrangement_candidate.melodic_complement_id` and merges melody note events into the arrangement's render data. `assemble_family()` updated to pass melodic complements through the cross-product alongside groove patterns.

### 6.4 Backward Compatibility

If `melodic_complements` is empty in state (legacy sessions, or generation skipped), assembly proceeds without melody. No behavior change for existing sessions.

---

## 7. MelodyHarmonyEvaluation

Implements the existing stub in `evaluation.py` with two deterministic dimensions. Only active when `ArrangementCandidate.melodic_complement_id` is non-null.

### 7.1 Dimensions

**melody_support_score** (deterministic) — two sub-metrics averaged:
- *Chord-tone ratio on strong beats*: proportion of downbeat melody notes that are chord tones (or strategy-specified target degrees) of the current chord. Perfect score at 1.0, degrades linearly.
- *Voice-leading smoothness*: proportion of consecutive melody intervals that are a 3rd or smaller. Penalizes large leaps unless genre `motion_preference` is "leaping" (in which case 4ths/5ths don't penalize).

**collision_risk_score** (deterministic) — count of unisons and minor 2nds between melody note events and voicing events on the same bar/beat. Scored as `1.0 - (collision_count / total_melody_events)`, floored at 0.0. A collision-free melody scores 1.0.

### 7.2 Weight Integration

New weight entries in `ObjectiveWeights`: `melody_support: 0.15`, `collision_risk: 0.10`.

**Conditional weight normalization:** At evaluation time, check whether the session's arrangements include melodic complements. If yes, use the full weight set (existing weights rebalanced proportionally so the total including melody dimensions sums to 1.0). If no, use existing weights unchanged. This is a session-level check — all candidates in a session go through the same pipeline.

### 7.3 Deferred

`tension_justification_score` field stays in the model as `None`. No LLM call. Can be activated later without changing the evaluation pipeline interface.

---

## 8. Frontend Changes

**Implementation note:** Invoke the `frontend-design` skill when implementing this section for piano roll lane design, transport bar changes, and comparison view melody integration.

### 8.1 Piano Roll

`PianoRoll.tsx` gains a third note lane for melody, rendered in a distinct color from the design tokens (separate from voicing and bass colors). Melody notes render in the same coordinate space — they naturally sit above voicing events due to their higher register. No structural change to the canvas rendering logic, just a third pass over `melodic_complement.note_events`.

### 8.2 Transport Bar

`TransportBar.tsx` gets a third mute toggle button for melody alongside the existing Chords and Bass toggles.

### 8.3 Audio Store

`audioStore.ts` `mutedTracks` expands from `{ voicing: boolean; bass: boolean }` to `{ voicing: boolean; bass: boolean; melody: boolean }`. `toggleMute` union type gains `"melody"`. Reset function updated.

### 8.4 Melody Synth

Single default synth for all genres: a simple triangle-wave lead with moderate attack/release. Added to `audioPresets.ts` as a top-level `MELODY_DEFAULT` preset, not per-genre. Genre-specific presets deferred to M5c.

### 8.5 Comparison Playback

Melody becomes a new lane with its own mute/solo in the DAW comparison view, following the same pattern as voicing and bass lanes.

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

| File | Action | Purpose |
|------|--------|---------|
| `models/realization.py` | Edit | Add `MelodicNoteEvent`, `MelodicComplement` |
| `engine/state.py` | Edit | Add `melodic_complements` key |
| `domain/style/genres/dream_pop.yaml` | Edit | Add `melodic_tendencies` |
| `domain/style/genres/synthwave.yaml` | Edit | Add `melodic_tendencies` |
| `domain/style/genres/cinematic.yaml` | Edit | Add `melodic_tendencies` |
| `prompts/melody.py` | Create | Strategy prompt template |
| `domain/realization/melody.py` | Create | `MelodyGenerator` service |
| `engine/nodes/generate_melody.py` | Create | LangGraph node |
| `engine/graph.py` | Edit | Wire `generate_melody` into pipeline |
| `domain/realization/assembler.py` | Edit | Accept optional melody in assembly |
| `domain/evaluation/melody_harmony.py` | Create | `MelodyHarmonyEvaluator` |
| `domain/evaluation/` (orchestrator) | Edit | Conditional activation, weight normalization |
| `frontend/src/stores/audioStore.ts` | Edit | Add melody to `mutedTracks` |
| `frontend/src/services/audioPresets.ts` | Edit | Add `MELODY_DEFAULT` preset |
| `frontend/src/components/PianoRoll.tsx` | Edit | Melody lane rendering |
| `frontend/src/components/TransportBar.tsx` | Edit | Melody mute toggle |
| `frontend/src/components/ComparisonView.tsx` | Edit | Melody lane in DAW view |
| `e2e/tests/` | Create | 5-6 new test files |
