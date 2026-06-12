# M2b: Arrangement Evaluation Design

**Date**: 2026-04-07
**Status**: Approved
**Milestone**: M2b (of M2a/M2b/M2c split)
**Depends on**: M2a Realization Engine (complete)

## 1. Overview

M2b adds evaluation, ranking, and multi-bass exploration to the M2a realization pipeline. The system generates multiple bass line variants per progression (genre-scoped), evaluates all arrangement candidates on voice leading, register/density, and playability, then ranks within each family and surfaces the best.

### Key Decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | Fully deterministic evaluators (no Gemini) | Voicing quality is measurable from note data; no subjective judgment needed |
| D2 | Rank within ArrangementFamily, minimum-quality filter | Cross-family comparison is meaningless; variants of the same progression are the meaningful axis |
| D3 | Genre-scoped multi-bass (2 modes per genre) | System explores the space; user sees ranked results without manual mode selection |
| D4 | Tiered scoring weights (new evaluators weighted higher) | New scores differentiate variants; M1 scores are shared across variants |
| D5 | Voice-leading inversion sweep in VoicingGenerator | Improves generation quality; evaluation validates a better baseline |

### Pipeline (updated)

```
load_context → plan_voicings → generate_bass → assemble
  → evaluate_arrangements → rank_and_select → persist_realization
```

Two new nodes inserted between `assemble` and `persist_realization`.

## 2. Genre YAML Extension — Multi-Bass

Each genre profile gets a `variant_bass_modes` list in `bass_preferences`:

```yaml
bass_preferences:
  default_bass_mode: supportive
  default_register: low
  rhythmic_density: sparse
  variant_bass_modes:
    - supportive
    - pedal
```

### Genre Defaults

| Genre | variant_bass_modes | Rationale |
|---|---|---|
| Dream Pop | `[supportive, pedal]` | Sparse root + pedal tone exploration |
| Synthwave | `[supportive, syncopated]` | Driving root + rhythmic variation |
| Cinematic | `[pedal, supportive]` | Pedal tone primary + root fallback |

**BassPreferences model update:**
```python
variant_bass_modes: list[str] = Field(default_factory=lambda: ["supportive"])
```

### New Bass Mode: Syncopated

Template for syncopated mode (needed for Synthwave):
- Beat 1: root note, duration 1.0
- Beat 2: rest (no event)
- Beat 3.5: root note, duration 0.5 (the "and" of 3)
- Beat 4: rest (no event)

Register follows genre `default_register`. Applied per bar like existing templates. Syncopated mode is density-independent — it uses the same template regardless of `rhythmic_density` setting, since the syncopation pattern IS the rhythmic variation.

### Arrangement Space

With 2-3 voicing variants × 2 bass variants = 4-6 arrangements per progression. For 2 selected progressions, that's 8-12 arrangements entering evaluation.

## 3. Evaluators

Three new deterministic evaluators in `domain/evaluation/`. All take an `ArrangementCandidate` (resolved to its voicing and bass event data) and return a score 0-10 with notes.

### 3.1 VoiceLeadingEvaluator

**Input:** `VoicingPlan.voicing_events` (list of VoicingEvent)
**Output:** `VoiceLeadingEvaluation` (existing model in `models/evaluation.py`)

Algorithm — for each pair of adjacent voicing events:
1. Call `check_voice_leading(prev.pitches, next.pitches)` → `VoiceLeadingCheck`
2. Accumulate across the progression:
   - `avg_common_tones`: mean common tones per transition
   - `avg_semitone_distance`: mean total movement per transition
   - `max_leap_anywhere`: worst single voice leap across all transitions
   - `parallel_violations`: total count of parallel 5ths + octaves

Scoring (start at 10.0):
- `-1.5` per parallel violation
- `-0.5` per transition where `total_semitone_distance > 8`
- `+0.5` per transition with `common_tones >= 2` (capped at +2.0 total bonus)
- Clamp to [0.0, 10.0]

Map to existing model fields (normalization formulas):
- `smoothness_score` = `max(0, 10.0 - (avg_semitone_distance / 2.0))` — lower movement = higher smoothness
- `common_tone_retention_score` = `min(10.0, avg_common_tones * 3.3)` — 3+ common tones = 10
- `awkward_leap_penalty` = `max(0, 10.0 - (max_leap_anywhere / 2.4))` — leaps > 24 semitones = 0
- `resolution_quality` = `max(0, 10.0 - (parallel_violations * 1.5))` — each violation costs 1.5

The **overall score** (single 0-10 value) is computed by the evaluator and returned alongside the detailed breakdown. It's stored on the `AggregateScorecard.scores["voice_leading"]`.

### 3.2 RegisterDensityEvaluator

**Input:** `VoicingPlan.voicing_events` + `BassLine.note_events`
**Output:** `RegisterDensityEvaluation` (existing model)

Algorithm — for each bar, collect all pitches (voicing + bass) as MIDI values:
1. **Mud zone check**: count pitches in MIDI 36-52 (C2-E3). More than 2 = mud violation. This is an absolute range (physics of harmonic interference), not genre-dependent.
2. **Spacing balance**: compute intervals between adjacent sorted pitches. Flag if any gap > 19 semitones while another gap < 3 semitones (imbalance).
3. **Register alignment**: compute voicing centroid (mean MIDI of voicing pitches, rounded to nearest integer). Check if it falls within genre's preferred register bounds using the existing `_REGISTER_BOUNDS` dict from `music21_adapter.py`: low=(36,60), mid=(48,72), mid_high=(60,84), high=(72,96).
4. **Bass-voicing separation**: lowest voicing pitch must be at least 7 semitones above the bass pitch. Below that = collision.

Scoring (start at 10.0, per bar then averaged):
- `-2.0` per bar with mud zone violation
- `-1.5` per bar with spacing imbalance
- `-1.0` per bar where voicing centroid outside genre register
- `-1.0` per bar with bass-voicing collision
- Clamp to [0.0, 10.0]

Map to existing model fields (normalization formulas):
- `register_balance_score` = `max(0, 10.0 - (bars_outside_register * 2.5))` — 4+ bars out = 0
- `mud_risk_score` = `max(0, 10.0 - (mud_violation_bars * 2.0))` — inverse of mud count
- `overcrowding_risk_score` = `max(0, 10.0 - (imbalance_bars * 1.5))` — inverse of spacing issues
- `spacing_quality` = `max(0, 10.0 - (collision_bars * 2.5))` — inverse of bass-voicing collisions

### 3.3 PlayabilityEvaluator

**Input:** `VoicingPlan.voicing_events`
**Output:** `PlayabilityEvaluation` (existing model)

Algorithm — for each voicing event:
1. Sort pitches by MIDI value
2. Total span: `max(midi) - min(midi)` in semitones
3. Voice count: `len(pitches)`
4. Check hand span: > 15 semitones = unreachable for most pianists
5. Check voice count: > 5 = physically impossible with one hand

Scoring (start at 10.0, per voicing then averaged):
- `-3.0` per voicing with span > 15
- `-1.0` per voicing with span 13-15 (stretchy)
- `-2.0` per voicing with > 5 notes
- Clamp to [0.0, 10.0]

Map to existing model fields:
- `piano_playability` = the primary score (hand span + voice count)
- `guitar_playability` = 0.0 (deferred — not meaningful for current voicing types)
- `ensemble_playability` = same as piano_playability for now (single-instrument focus)
- `simplification_recommendations` = list of issues found (e.g., "Bar 3: span of 17 semitones exceeds comfortable range")

## 4. Rank and Select

### Within-Family Ranking

For each `ArrangementFamily`:

**Step 1 — Minimum quality filter:** Reject any arrangement where any evaluator score < 3.0. Set `status="rejected"`. These are fundamentally broken. If fewer than 2 arrangements survive the filter in a family, keep all survivors (don't reject the last one standing).

**Step 2 — Combine scores:** Each arrangement gets a weighted total across all 9 dimensions:

| Dimension | Weight | Source |
|---|---|---|
| voice_leading | 0.15 | VoiceLeadingEvaluator |
| register_density | 0.12 | RegisterDensityEvaluator |
| playability | 0.12 | PlayabilityEvaluator |
| genre_fit | 0.10 | M1 TheoryEvaluation (from ProgressionCandidate) |
| emotional_fit | 0.10 | M1 TheoryEvaluation |
| theoretical_coherence | 0.10 | M1 TheoryEvaluation |
| cadence_quality | 0.10 | M1 TheoryEvaluation |
| novelty | 0.10 | M1 TheoryEvaluation |
| loopability | 0.11 | M1 TheoryEvaluation |

New evaluators total: 0.39. M1 dimensions total: 0.61 (5 × 0.10 + loopability 0.11). Loopability is weighted slightly higher because loopable arrangements have longer practical usefulness for producers.

**Step 3 — Select top N:** Keep top 2 per family. Set `status="selected"`. Update `ArrangementFamily.root_arrangement_candidate_id` to highest scorer.

**Step 4 — Set rank:** `AggregateScorecard.rank_within_round` for ordering.

### Reading M1 Scores

The M1 `TheoryEvaluation` and `AggregateScorecard` are persisted on the `ProgressionCandidate` in Neo4j. The `load_context` node already fetches the candidate data. The M1 scores are read from `candidate.metadata["scores"]` (set by M1's `persist_round` node) and applied uniformly to all arrangement variants of that progression.

**Fallback for missing M1 scores:** If `candidate.metadata["scores"]` is missing or a specific dimension key is absent, use `0.5` as the raw dimension score (neutral — neither penalizes nor rewards). The dimension's weight is preserved in the weighted sum; it is NOT redistributed to other dimensions. This ensures the total always sums correctly.

```python
# Pseudo-code for score reading:
m1_scores = candidate_metadata.get("scores", {})
for dim in ["genre_fit", "emotional_fit", "theoretical_coherence",
            "cadence_quality", "novelty", "loopability"]:
    score = m1_scores.get(dim, 5.0)  # 5.0 = neutral on 0-10 scale
```

## 5. Voice-Leading Inversion Sweep

Enhancement to `VoicingGenerator._optimize_voice_leading()` in `domain/realization/voicing.py`. This method currently exists as a passthrough (returns the input unchanged). M2b replaces it with the inversion sweep.

**Integration point:** Called inside `VoicingGenerator.realize()`, per-chord, per-variant. After `realize_voicing()` produces the initial pitches for a chord, `_optimize_voice_leading()` considers inversions and returns the best one. This happens before the pitches are stored as a `VoicingEvent`.

Algorithm for each chord after the first:
1. Start with the voicing from `realize_voicing()` as the base candidate
2. Generate inversion candidates by rotating the pitch set within the register:
   - Original (as-is)
   - First inversion: move bottom note up one octave
   - Second inversion: move bottom two notes up one octave  
   - Third inversion (if 4+ voices): move bottom three notes up one octave
3. Clamp each candidate to the target register (shift pitches that went out of bounds). Cost is computed on the clamped pitches.
4. Score each against previous chord using `check_voice_leading()`:
   - Cost = `total_semitone_distance - (common_tones * 4)`
   - `+100` penalty if `has_parallel_fifths`, `+100` penalty if `has_parallel_octaves` (penalties stack — both = +200)
5. Pick the candidate with lowest cost

Complexity: O(inversions × voices) per chord. For 4-voice chords with 4 inversions across 4-8 bars = 64-128 comparisons. Well within performance budget.

## 6. RealizationState Changes

New fields added to `RealizationState`:

```python
# Produced by evaluate_arrangements
evaluations: list[dict[str, Any]]       # VoiceLeading/RegisterDensity/Playability evals
scorecards: list[dict[str, Any]]        # AggregateScorecard per arrangement

# Produced by rank_and_select
selected_arrangements: list[dict[str, Any]]  # top-ranked per family
```

## 7. API Changes

No new endpoints. Enriched responses on existing M2a endpoints:

**`GET /v1/candidates/{id}/arrangements`** — each arrangement now includes:
- `weighted_total: float`
- `status: str` ("draft" | "selected" | "rejected")
- `rank_within_round: int`

**`GET /v1/arrangements/{id}`** — now includes:
- `scorecard: { scores: {voice_leading: 8.2, register_density: 7.5, ...}, weighted_total: 8.1 }`
- `evaluations: { voice_leading: {...}, register_density: {...}, playability: {...} }`

The enrichment happens in the route handler by fetching the `AggregateScorecard` and evaluation entities from Neo4j.

## 8. Persistence Changes

`persist_realization` now additionally writes:
- `VoiceLeadingEvaluation` nodes (one per arrangement)
- `RegisterDensityEvaluation` nodes (one per arrangement)
- `PlayabilityEvaluation` nodes (one per arrangement)
- `EvaluationBundle` nodes (one per arrangement, linking the three evals)
- `AggregateScorecard` nodes (one per arrangement, with all 9 dimension scores)
- Updated `status` on `ArrangementCandidate` nodes ("selected" or "rejected")

New relationships:
```
(ArrangementCandidate)-[:HAS_EVALUATION]->(EvaluationBundle)
(EvaluationBundle)-[:INCLUDES]->(VoiceLeadingEvaluation)
(EvaluationBundle)-[:INCLUDES]->(RegisterDensityEvaluation)
(EvaluationBundle)-[:INCLUDES]->(PlayabilityEvaluation)
(ArrangementCandidate)-[:HAS_SCORECARD]->(AggregateScorecard)
```

Write order: Evaluations → EvaluationBundle → AggregateScorecard → update ArrangementCandidate status.

## 9. File Structure

### New Files

```
backend/src/explorator/
  domain/evaluation/
    voice_leading.py            # VoiceLeadingEvaluator
    register_density.py         # RegisterDensityEvaluator
    playability.py              # PlayabilityEvaluator
  engine/nodes/
    evaluate_arrangements.py    # runs 3 evaluators per arrangement
    rank_and_select.py          # within-family ranking + quality filter

backend/tests/unit/
  domain/
    test_voice_leading_evaluator.py
    test_register_density_evaluator.py
    test_playability_evaluator.py
    test_voicing_inversion.py
    test_bass_syncopated.py
  engine/
    test_rank_and_select.py
```

### Modified Files

```
backend/src/explorator/
  domain/realization/
    voicing.py                  # inversion sweep in _optimize_voice_leading
    bass.py                     # syncopated mode template
  engine/
    nodes/generate_bass.py      # multi-bass from variant_bass_modes
    nodes/assemble_arrangements.py  # cross-product voicing × bass
    nodes/persist_realization.py    # persist evals + scorecards + status
    realization_graph.py        # insert evaluate_arrangements + rank_and_select
    realization_state.py        # add evaluation/scorecard/selected fields
  models/
    realization.py              # add variant_bass_modes to BassPreferences
  api/routes/
    realization_rounds.py       # enrich GET responses with scores
  data/genres/ (or domain/style/genres/)
    dream_pop.yaml              # add variant_bass_modes
    synthwave.yaml              # add variant_bass_modes
    cinematic.yaml              # add variant_bass_modes
```

## 10. Existing Model Alignment

The evaluation models in `models/evaluation.py` already define:
- `VoiceLeadingEvaluation`: `smoothness_score`, `common_tone_retention_score`, `awkward_leap_penalty`, `resolution_quality`
- `RegisterDensityEvaluation`: `register_balance_score`, `mud_risk_score`, `overcrowding_risk_score`, `spacing_quality`
- `PlayabilityEvaluation`: `piano_playability`, `guitar_playability`, `ensemble_playability`, `simplification_recommendations`
- `EvaluationBundle`: links all evaluation IDs + scorecard
- `AggregateScorecard`: `scores: dict[str, float]`, `weighted_total`, `rank_within_round`

These models are used as-is — no modifications needed. The evaluators populate the existing fields with computed scores.

## 11. Performance Budget

| Node | Target | Notes |
|---|---|---|
| generate_bass (updated) | <400ms | 2 modes × N progressions, still deterministic |
| assemble (updated) | <200ms | Cross-product is pure combination |
| evaluate_arrangements | <500ms | 3 evaluators × 4-6 arrangements, all deterministic |
| rank_and_select | <100ms | Simple math on scored arrays |
| persist_realization (updated) | <800ms | More entities to write (evals + scorecards) |

Total pipeline with M2b additions: ~5-6s for 2 progressions. Still under M1's 15-20s baseline.

## 12. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Scoring thresholds too strict (filter rejects everything) | No arrangements survive | Start with 3.0 minimum; tune based on real output |
| M1 scores unavailable on candidate metadata | Ranking uses incomplete data | Fall back to 0.5 (neutral) for missing M1 dimensions |
| Syncopated bass mode sounds bad for some genres | Low-quality arrangements | Only Synthwave uses it; evaluation will score it down if muddy |
| Inversion sweep picks wrong inversion | Worse voice leading than before | Cost function is conservative; parallel motion penalty is heavy |
| 4-6 arrangements per progression overwhelms UI | Cluttered results | rank_and_select keeps only top 2 per family |
