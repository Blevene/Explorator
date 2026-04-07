# M2b Arrangement Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic arrangement evaluation, within-family ranking, multi-bass exploration, and voice-leading optimization to the realization pipeline.

**Architecture:** Three deterministic evaluators score arrangements on voice leading, register/density, and playability. A rank_and_select node filters and ranks within each ArrangementFamily. The generate_bass node now produces multiple bass variants per genre, and the voicing generator optimizes voice leading via inversion sweep.

**Tech Stack:** Python 3.12, LangGraph, Pydantic v2, music21, Neo4j, FastAPI

**Spec:** `docs/superpowers/specs/2026-04-07-m2b-arrangement-evaluation-design.md`

---

## File Structure

### New Files

```
backend/src/explorator/
  domain/evaluation/
    voice_leading.py            # VoiceLeadingEvaluator class
    register_density.py         # RegisterDensityEvaluator class
    playability.py              # PlayabilityEvaluator class
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
  models/realization.py              # add variant_bass_modes to BassPreferences
  domain/realization/bass.py         # add syncopated mode template
  domain/realization/voicing.py      # implement inversion sweep
  engine/nodes/generate_bass.py      # multi-bass from variant_bass_modes
  engine/nodes/assemble_arrangements.py  # cross-product voicing × bass
  engine/nodes/persist_realization.py    # persist evals + scorecards + status
  engine/realization_graph.py        # insert evaluate_arrangements + rank_and_select
  engine/realization_state.py        # add evaluation/scorecard/selected fields
  api/routes/realization_rounds.py   # enrich GET responses with scores
  domain/style/genres/dream_pop.yaml
  domain/style/genres/synthwave.yaml
  domain/style/genres/cinematic.yaml
```

---

## Task 1: Model + Genre YAML Updates

**Files:**
- Modify: `backend/src/explorator/models/realization.py`
- Modify: `backend/src/explorator/domain/style/genres/dream_pop.yaml`
- Modify: `backend/src/explorator/domain/style/genres/synthwave.yaml`
- Modify: `backend/src/explorator/domain/style/genres/cinematic.yaml`
- Test: `backend/tests/unit/models/test_realization.py`

- [ ] **Step 1: Write test for variant_bass_modes field**

Add to `backend/tests/unit/models/test_realization.py`:

```python
class TestBassPreferencesVariantModes:
    def test_default_variant_bass_modes(self):
        bp = BassPreferences()
        assert bp.variant_bass_modes == ["supportive"]

    def test_custom_variant_bass_modes(self):
        bp = BassPreferences(variant_bass_modes=["supportive", "pedal"])
        assert len(bp.variant_bass_modes) == 2
```

- [ ] **Step 2: Run test — expect fail**

Run: `cd /home/angel/Documents/code/Explorator/backend && .venv/bin/python -m pytest tests/unit/models/test_realization.py::TestBassPreferencesVariantModes -v --tb=short`
Expected: AttributeError — field doesn't exist

- [ ] **Step 3: Add variant_bass_modes to BassPreferences**

In `backend/src/explorator/models/realization.py`, add to `BassPreferences`:

```python
class BassPreferences(BaseModel):
    """Structured bass preferences from genre YAML."""

    default_bass_mode: str = "supportive"
    default_register: str = "low"
    rhythmic_density: str = "moderate"
    variant_bass_modes: list[str] = Field(default_factory=lambda: ["supportive"])
```

- [ ] **Step 4: Run test — expect pass**

- [ ] **Step 5: Update genre YAMLs**

Add `variant_bass_modes` to each genre's `bass_preferences` section:

**dream_pop.yaml** — add under `bass_preferences`:
```yaml
  variant_bass_modes:
    - supportive
    - pedal
```

**synthwave.yaml** — add under `bass_preferences`:
```yaml
  variant_bass_modes:
    - supportive
    - syncopated
```

**cinematic.yaml** — add under `bass_preferences`:
```yaml
  variant_bass_modes:
    - pedal
    - supportive
```

- [ ] **Step 6: Commit**

```bash
git add backend/src/explorator/models/realization.py backend/tests/unit/models/test_realization.py backend/src/explorator/domain/style/genres/
git commit -m "feat(m2b): add variant_bass_modes to BassPreferences and genre YAMLs"
```

---

## Task 2: Syncopated Bass Mode

**Files:**
- Modify: `backend/src/explorator/domain/realization/bass.py`
- Create: `backend/tests/unit/domain/test_bass_syncopated.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/domain/test_bass_syncopated.py

from explorator.domain.realization.bass import BassLineGenerator
from explorator.models.realization import BassLine, BassNoteEvent, BassPreferences


class TestSyncopatedBassMode:
    def test_syncopated_produces_two_events_per_bar(self):
        gen = BassLineGenerator()
        prefs = BassPreferences(default_bass_mode="syncopated", default_register="low", rhythmic_density="moderate")
        bl = gen.generate(["Cm", "Fm"], prefs, genre="synthwave")
        assert bl.style_mode == "syncopated"
        # Syncopated: beat 1 (duration 1.0) + beat 3.5 (duration 0.5) = 2 events per bar
        assert len(bl.note_events) == 4  # 2 bars × 2 events

    def test_syncopated_beat_positions(self):
        gen = BassLineGenerator()
        prefs = BassPreferences(default_bass_mode="syncopated", default_register="low")
        bl = gen.generate(["C"], prefs, genre="synthwave")
        events = bl.note_events
        assert events[0].beat == 1.0
        assert events[0].duration_beats == 1.0
        assert events[1].beat == 3.5
        assert events[1].duration_beats == 0.5

    def test_syncopated_root_notes(self):
        gen = BassLineGenerator()
        prefs = BassPreferences(default_bass_mode="syncopated", default_register="low")
        bl = gen.generate(["Am7", "Dm7"], prefs, genre="synthwave")
        assert bl.note_events[0].pitch.startswith("A")
        assert bl.note_events[2].pitch.startswith("D")

    def test_syncopated_ignores_density(self):
        """Syncopated mode uses same template regardless of rhythmic_density."""
        gen = BassLineGenerator()
        sparse = gen.generate(["C"], BassPreferences(default_bass_mode="syncopated", rhythmic_density="sparse"), genre="synthwave")
        active = gen.generate(["C"], BassPreferences(default_bass_mode="syncopated", rhythmic_density="active"), genre="synthwave")
        assert len(sparse.note_events) == len(active.note_events)
```

- [ ] **Step 2: Run tests — expect fail**

Run: `cd /home/angel/Documents/code/Explorator/backend && .venv/bin/python -m pytest tests/unit/domain/test_bass_syncopated.py -v --tb=short`

- [ ] **Step 3: Implement syncopated mode in bass.py**

Add a `_syncopated_events` method to `BassLineGenerator`. Read the existing `_supportive_events` and `_pedal_events` methods for the pattern, then add:

```python
def _syncopated_events(self, root: str, octave: int, bar: int) -> list[BassNoteEvent]:
    """Syncopated: root on beat 1, root on 'and' of beat 3. Density-independent."""
    pitch = f"{root}{octave}"
    return [
        BassNoteEvent(bar=bar, beat=1.0, duration_beats=1.0, pitch=pitch),
        BassNoteEvent(bar=bar, beat=3.5, duration_beats=0.5, pitch=pitch),
    ]
```

Update the mode dispatch in `generate()` to call `_syncopated_events` when `style_mode == "syncopated"`.

- [ ] **Step 4: Run tests — expect pass**

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/domain/realization/bass.py backend/tests/unit/domain/test_bass_syncopated.py
git commit -m "feat(m2b): add syncopated bass mode template"
```

---

## Task 3: Multi-Bass Generation

**Files:**
- Modify: `backend/src/explorator/engine/nodes/generate_bass.py`

- [ ] **Step 1: Update generate_bass to produce multiple bass lines**

Currently the node generates 1 bass line per progression. Update it to read `variant_bass_modes` from the genre profile's `bass_preferences` and generate one bass line per mode per progression.

Key changes:
- Read `variant_bass_modes` from `bass_prefs_data` (default `["supportive"]` for backward compat)
- Loop: for each candidate, for each mode in `variant_bass_modes`, generate a bass line
- Override `prefs.default_bass_mode` with the current mode for each generation
- Tag each bass line with its mode via `style_mode` field

The bass lines list in state grows from N (one per progression) to N × M (one per progression × mode).

- [ ] **Step 2: Run existing tests — no regressions**

Run: `cd /home/angel/Documents/code/Explorator/backend && .venv/bin/python -m pytest tests/unit/ -q --tb=short`

- [ ] **Step 3: Commit**

```bash
git add backend/src/explorator/engine/nodes/generate_bass.py
git commit -m "feat(m2b): generate multiple bass lines from variant_bass_modes"
```

---

## Task 4: Cross-Product Assembly

**Files:**
- Modify: `backend/src/explorator/engine/nodes/assemble_arrangements.py`

- [ ] **Step 1: Update assemble to cross-product voicing × bass**

Currently the node maps 1 bass line per progression. Update to:
- Group bass lines by `progression_candidate_id` (now many per progression)
- For each progression: create arrangements for every combination of (voicing_plan, bass_line)
- Each family now contains (voicing_variants × bass_variants) arrangements

Key change: replace the 1:1 `bl_by_prog` dict with a 1:N `bls_by_prog` dict, then iterate the cross-product.

```python
# Before (M2a):
bl_by_prog: dict[str, BassLine] = {}
# After (M2b):
bls_by_prog: dict[str, list[BassLine]] = {}
```

In the assembly loop, for each progression:
```python
for vp in voicing_plans:
    for bl in bass_lines:
        ac = assembler.assemble_one(
            progression_candidate_id=candidate.id,
            session_id=session_id,
            voicing_plan=vp,
            bass_line=bl,
            intent_tags=intent_tags,
            rationale=f"{vp.global_strategy} + {bl.style_mode} bass",
        )
        all_candidates.append(ac)
```

Then create one family per progression containing all its arrangement candidates.

- [ ] **Step 2: Run existing tests — no regressions**

- [ ] **Step 3: Commit**

```bash
git add backend/src/explorator/engine/nodes/assemble_arrangements.py
git commit -m "feat(m2b): cross-product voicing × bass in arrangement assembly"
```

---

## Task 5: Voice-Leading Inversion Sweep

**Files:**
- Modify: `backend/src/explorator/domain/realization/voicing.py`
- Create: `backend/tests/unit/domain/test_voicing_inversion.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/domain/test_voicing_inversion.py

from explorator.domain.realization.voicing import VoicingGenerator
from explorator.models.realization import (
    ChordVoicingInstruction,
    VariantConfig,
    VoicingPreferences,
    VoicingStrategyResponse,
)


def _make_strategy(chords: list[str]) -> VoicingStrategyResponse:
    return VoicingStrategyResponse(
        global_strategy="test", density_level="medium", voice_count=4,
        per_chord=[
            ChordVoicingInstruction(
                chord_symbol=c, voicing_type="close",
                target_register="mid", extensions_to_include=[],
            ) for c in chords
        ],
    )


class TestVoicingInversionSweep:
    def test_produces_valid_voicings(self):
        gen = VoicingGenerator()
        prefs = VoicingPreferences(default_register="mid")
        plan = gen.realize(_make_strategy(["C", "F", "G", "C"]), ["C", "F", "G", "C"], prefs, VariantConfig(voicing_type="close"))
        assert len(plan.voicing_events) == 4
        for event in plan.voicing_events:
            assert len(event.pitches) == 4

    def test_reduces_voice_movement(self):
        """Inversion sweep should produce smoother voice leading than no optimization."""
        from explorator.adapters.music21_adapter import check_voice_leading
        gen = VoicingGenerator()
        prefs = VoicingPreferences(default_register="mid")
        plan = gen.realize(_make_strategy(["C", "Am", "F", "G"]), ["C", "Am", "F", "G"], prefs, VariantConfig(voicing_type="close"))
        # Check voice leading between adjacent chords
        total_distance = 0
        for i in range(len(plan.voicing_events) - 1):
            vl = check_voice_leading(plan.voicing_events[i].pitches, plan.voicing_events[i + 1].pitches)
            total_distance += vl.total_semitone_distance
        # Optimized voice leading should have reasonable total distance
        # (not asserting exact value — just that it doesn't explode)
        assert total_distance < 60  # 4 transitions × 4 voices × ~3.5 semitones avg

    def test_avoids_parallel_fifths(self):
        """Inversion sweep should avoid parallel fifths when possible."""
        from explorator.adapters.music21_adapter import check_voice_leading
        gen = VoicingGenerator()
        prefs = VoicingPreferences(default_register="mid")
        plan = gen.realize(_make_strategy(["C", "D", "E", "F"]), ["C", "D", "E", "F"], prefs, VariantConfig(voicing_type="close"))
        parallel_count = 0
        for i in range(len(plan.voicing_events) - 1):
            vl = check_voice_leading(plan.voicing_events[i].pitches, plan.voicing_events[i + 1].pitches)
            if vl.has_parallel_fifths:
                parallel_count += 1
        # Should have few or no parallel fifths
        assert parallel_count <= 1
```

- [ ] **Step 2: Run tests — expect fail (optimization not implemented)**

- [ ] **Step 3: Implement inversion sweep**

Replace the `_optimize_voice_leading()` passthrough in `backend/src/explorator/domain/realization/voicing.py`:

```python
def _optimize_voice_leading(
    self,
    prev_pitches: list[str],
    current_pitches: list[str],
    chord_symbol: str,
    voicing_type: str,
    target_register: str,
    voice_count: int,
    extensions: list[str],
) -> list[str]:
    """Try inversions of current voicing, pick the one with best voice leading."""
    from music21 import pitch as m21pitch

    candidates = [current_pitches]

    # Generate inversions: rotate bottom notes up one octave
    midi_sorted = sorted(
        [m21pitch.Pitch(p) for p in current_pitches],
        key=lambda p: p.midi,
    )
    for n_rotate in range(1, min(len(midi_sorted), 4)):
        inversion = list(midi_sorted)
        for i in range(n_rotate):
            inversion[i] = m21pitch.Pitch(inversion[i].midi + 12)
        # Clamp to register
        lo, hi = _REGISTER_BOUNDS.get(target_register, (48, 72))
        clamped = []
        for p in inversion:
            while p.midi < lo:
                p.octave += 1
            while p.midi > hi:
                p.octave -= 1
            clamped.append(p)
        clamped.sort(key=lambda p: p.midi)
        candidates.append([p.nameWithOctave for p in clamped])

    # Score each candidate against previous chord
    best = candidates[0]
    best_cost = float("inf")
    for candidate in candidates:
        vl = check_voice_leading(prev_pitches, candidate)
        cost = vl.total_semitone_distance - (vl.common_tones * 4)
        if vl.has_parallel_fifths:
            cost += 100
        if vl.has_parallel_octaves:
            cost += 100
        if cost < best_cost:
            best_cost = cost
            best = candidate

    return best
```

Import `_REGISTER_BOUNDS` from the adapter or define it locally. The function is called per-chord inside `realize()` when `prev_pitches is not None`.

- [ ] **Step 4: Run tests — expect pass**

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/domain/realization/voicing.py backend/tests/unit/domain/test_voicing_inversion.py
git commit -m "feat(m2b): implement voice-leading inversion sweep"
```

---

## Task 6: VoiceLeadingEvaluator

**Files:**
- Create: `backend/src/explorator/domain/evaluation/voice_leading.py`
- Create: `backend/tests/unit/domain/test_voice_leading_evaluator.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/domain/test_voice_leading_evaluator.py

from explorator.domain.evaluation.voice_leading import VoiceLeadingEvaluator
from explorator.models.evaluation import AggregateScorecard, VoiceLeadingEvaluation
from explorator.models.realization import VoicingEvent, VoicingPlan


def _make_plan(events: list[list[str]], symbols: list[str]) -> VoicingPlan:
    return VoicingPlan(
        id="vp_test", type="voicing_plan", status="draft",
        voicing_events=[
            VoicingEvent(bar=i + 1, pitches=pitches, chord_symbol=symbols[i])
            for i, pitches in enumerate(events)
        ],
    )


class TestVoiceLeadingEvaluator:
    def test_perfect_voice_leading(self):
        """Identical voicings = perfect score."""
        plan = _make_plan(
            [["C4", "E4", "G4", "B4"]] * 4,
            ["Cmaj7"] * 4,
        )
        evaluator = VoiceLeadingEvaluator()
        result = evaluator.evaluate(plan)
        assert isinstance(result, VoiceLeadingEvaluation)
        assert result.smoothness_score >= 9.0
        assert result.common_tone_retention_score >= 9.0

    def test_parallel_fifths_penalized(self):
        """Parallel fifths should tank the resolution_quality score."""
        plan = _make_plan(
            [["C4", "G4"], ["D4", "A4"]],
            ["C", "Dm"],
        )
        evaluator = VoiceLeadingEvaluator()
        result = evaluator.evaluate(plan)
        assert result.resolution_quality < 9.0  # penalized

    def test_large_leaps_penalized(self):
        """Big jumps should lower smoothness."""
        plan = _make_plan(
            [["C3", "E3", "G3", "B3"], ["C5", "E5", "G5", "B5"]],
            ["Cmaj7", "Cmaj7"],
        )
        evaluator = VoiceLeadingEvaluator()
        result = evaluator.evaluate(plan)
        assert result.smoothness_score < 7.0

    def test_overall_score_returned(self):
        """Evaluator returns an overall 0-10 score."""
        plan = _make_plan(
            [["C4", "E4", "G4", "B4"], ["C4", "E4", "G4", "A4"]],
            ["Cmaj7", "Am7"],
        )
        evaluator = VoiceLeadingEvaluator()
        result = evaluator.evaluate(plan)
        assert 0.0 <= result.smoothness_score <= 10.0
        assert 0.0 <= result.resolution_quality <= 10.0

    def test_single_chord_scores_perfect(self):
        """One chord = no transitions = perfect."""
        plan = _make_plan([["C4", "E4", "G4"]], ["C"])
        evaluator = VoiceLeadingEvaluator()
        result = evaluator.evaluate(plan)
        assert result.smoothness_score == 10.0
```

- [ ] **Step 2: Run tests — expect fail**

- [ ] **Step 3: Implement VoiceLeadingEvaluator**

```python
# backend/src/explorator/domain/evaluation/voice_leading.py

"""Deterministic voice leading quality evaluator."""

from ulid import ULID

from explorator.adapters.music21_adapter import check_voice_leading
from explorator.models.evaluation import VoiceLeadingEvaluation
from explorator.models.realization import VoicingPlan
from explorator.utils import utc_now


class VoiceLeadingEvaluator:
    """Evaluates voice leading quality of a voicing plan."""

    def evaluate(self, plan: VoicingPlan) -> VoiceLeadingEvaluation:
        """Score voice leading across all transitions in a voicing plan."""
        events = plan.voicing_events
        if len(events) <= 1:
            return self._perfect_score(plan.id)

        total_common = 0
        total_distance = 0
        max_leap = 0
        parallel_violations = 0
        jumpy_transitions = 0
        smooth_transitions = 0
        n_transitions = len(events) - 1

        for i in range(n_transitions):
            vl = check_voice_leading(events[i].pitches, events[i + 1].pitches)
            total_common += vl.common_tones
            total_distance += vl.total_semitone_distance
            if vl.max_leap > max_leap:
                max_leap = vl.max_leap
            if vl.has_parallel_fifths:
                parallel_violations += 1
            if vl.has_parallel_octaves:
                parallel_violations += 1
            if vl.total_semitone_distance > 8:
                jumpy_transitions += 1
            if vl.common_tones >= 2:
                smooth_transitions += 1

        avg_common = total_common / n_transitions
        avg_distance = total_distance / n_transitions

        # Overall score (spec algorithm)
        overall = 10.0
        overall -= parallel_violations * 1.5
        overall -= jumpy_transitions * 0.5
        overall += min(smooth_transitions * 0.5, 2.0)
        overall = max(0.0, min(10.0, overall))

        # Field-level scores (normalization formulas from spec)
        smoothness = max(0.0, 10.0 - (avg_distance / 2.0))
        common_tone_retention = min(10.0, avg_common * 3.3)
        awkward_leap_penalty = max(0.0, 10.0 - (max_leap / 2.4))
        resolution_quality = max(0.0, 10.0 - (parallel_violations * 1.5))

        now = utc_now()
        return VoiceLeadingEvaluation(
            id=f"vl_eval_{ULID()}",
            type="voice_leading_evaluation",
            status="completed",
            created_at=now,
            updated_at=now,
            candidate_id=plan.progression_candidate_id or plan.id,
            evaluation_type="voice_leading",
            smoothness_score=round(smoothness, 2),
            common_tone_retention_score=round(common_tone_retention, 2),
            awkward_leap_penalty=round(awkward_leap_penalty, 2),
            resolution_quality=round(resolution_quality, 2),
        )

    def overall_score(self, evaluation: VoiceLeadingEvaluation) -> float:
        """Compute the single 0-10 overall score for the aggregate scorecard."""
        return round(
            (evaluation.smoothness_score + evaluation.common_tone_retention_score
             + evaluation.awkward_leap_penalty + evaluation.resolution_quality) / 4.0,
            2,
        )

    def _perfect_score(self, candidate_id: str) -> VoiceLeadingEvaluation:
        now = utc_now()
        return VoiceLeadingEvaluation(
            id=f"vl_eval_{ULID()}",
            type="voice_leading_evaluation",
            status="completed",
            created_at=now,
            updated_at=now,
            candidate_id=candidate_id,
            evaluation_type="voice_leading",
            smoothness_score=10.0,
            common_tone_retention_score=10.0,
            awkward_leap_penalty=10.0,
            resolution_quality=10.0,
        )
```

- [ ] **Step 4: Run tests — expect pass**

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/domain/evaluation/voice_leading.py backend/tests/unit/domain/test_voice_leading_evaluator.py
git commit -m "feat(m2b): add VoiceLeadingEvaluator"
```

---

## Task 7: RegisterDensityEvaluator

**Files:**
- Create: `backend/src/explorator/domain/evaluation/register_density.py`
- Create: `backend/tests/unit/domain/test_register_density_evaluator.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/domain/test_register_density_evaluator.py

from explorator.domain.evaluation.register_density import RegisterDensityEvaluator
from explorator.models.evaluation import RegisterDensityEvaluation
from explorator.models.realization import BassLine, BassNoteEvent, VoicingEvent, VoicingPlan


def _make_plan_and_bass(voicing_pitches: list[list[str]], bass_pitches: list[str]) -> tuple[VoicingPlan, BassLine]:
    vp = VoicingPlan(
        id="vp_test", type="voicing_plan", status="draft",
        voicing_events=[
            VoicingEvent(bar=i + 1, pitches=p, chord_symbol="C")
            for i, p in enumerate(voicing_pitches)
        ],
    )
    bl = BassLine(
        id="bl_test", type="bass_line", status="draft",
        note_events=[
            BassNoteEvent(bar=i + 1, pitch=p)
            for i, p in enumerate(bass_pitches)
        ],
    )
    return vp, bl


class TestRegisterDensityEvaluator:
    def test_clean_arrangement_scores_high(self):
        vp, bl = _make_plan_and_bass(
            [["C4", "E4", "G4", "B4"]] * 4,
            ["C2"] * 4,
        )
        evaluator = RegisterDensityEvaluator()
        result = evaluator.evaluate(vp, bl, preferred_register="mid_high")
        assert isinstance(result, RegisterDensityEvaluation)
        assert result.spacing_quality >= 8.0

    def test_mud_zone_penalized(self):
        """Three notes in C2-E3 = mud."""
        vp, bl = _make_plan_and_bass(
            [["C2", "D2", "E2", "G2"]],
            ["C1"],
        )
        evaluator = RegisterDensityEvaluator()
        result = evaluator.evaluate(vp, bl, preferred_register="low")
        assert result.mud_risk_score < 8.0

    def test_bass_voicing_collision(self):
        """Bass and voicing overlap = collision."""
        vp, bl = _make_plan_and_bass(
            [["C3", "E3", "G3"]],
            ["B2"],  # only 1 semitone below lowest voicing note
        )
        evaluator = RegisterDensityEvaluator()
        result = evaluator.evaluate(vp, bl, preferred_register="mid")
        assert result.spacing_quality < 9.0

    def test_register_misalignment(self):
        """Voicing in wrong register."""
        vp, bl = _make_plan_and_bass(
            [["C2", "E2", "G2", "B2"]],  # low register
            ["C1"],
        )
        evaluator = RegisterDensityEvaluator()
        result = evaluator.evaluate(vp, bl, preferred_register="high")  # expects high
        assert result.register_balance_score < 8.0
```

- [ ] **Step 2: Run tests — expect fail**

- [ ] **Step 3: Implement RegisterDensityEvaluator**

```python
# backend/src/explorator/domain/evaluation/register_density.py

"""Deterministic register and density balance evaluator."""

from ulid import ULID

from explorator.models.evaluation import RegisterDensityEvaluation
from explorator.models.realization import BassLine, VoicingPlan
from explorator.utils import utc_now

# Mud zone: C2(36) to E3(52) — absolute, physics-based
_MUD_ZONE = (36, 52)

# Register bounds (MIDI): matches music21_adapter._REGISTER_BOUNDS
_REGISTER_BOUNDS: dict[str, tuple[int, int]] = {
    "low": (36, 60),
    "mid": (48, 72),
    "mid_high": (60, 84),
    "high": (72, 96),
}


class RegisterDensityEvaluator:
    """Evaluates register and density balance of an arrangement."""

    def evaluate(
        self,
        voicing_plan: VoicingPlan,
        bass_line: BassLine,
        preferred_register: str = "mid",
    ) -> RegisterDensityEvaluation:
        """Score register/density balance across all bars."""
        from music21 import pitch as m21pitch

        n_bars = len(voicing_plan.voicing_events)
        if n_bars == 0:
            return self._perfect_score(voicing_plan.id)

        mud_bars = 0
        imbalance_bars = 0
        register_miss_bars = 0
        collision_bars = 0

        reg_lo, reg_hi = _REGISTER_BOUNDS.get(preferred_register, (48, 72))

        for i, ve in enumerate(voicing_plan.voicing_events):
            voicing_midi = sorted([m21pitch.Pitch(p).midi for p in ve.pitches])

            # Get bass MIDI for this bar
            bass_midi = None
            if i < len(bass_line.note_events):
                bass_midi = m21pitch.Pitch(bass_line.note_events[i].pitch).midi

            all_midi = sorted(voicing_midi + ([bass_midi] if bass_midi is not None else []))

            # 1. Mud zone check
            mud_count = sum(1 for m in all_midi if _MUD_ZONE[0] <= m <= _MUD_ZONE[1])
            if mud_count > 2:
                mud_bars += 1

            # 2. Spacing balance
            if len(all_midi) >= 2:
                gaps = [all_midi[j + 1] - all_midi[j] for j in range(len(all_midi) - 1)]
                if max(gaps) > 19 and min(gaps) < 3:
                    imbalance_bars += 1

            # 3. Register alignment (voicing centroid)
            if voicing_midi:
                centroid = round(sum(voicing_midi) / len(voicing_midi))
                if centroid < reg_lo or centroid > reg_hi:
                    register_miss_bars += 1

            # 4. Bass-voicing separation
            if bass_midi is not None and voicing_midi:
                separation = voicing_midi[0] - bass_midi
                if separation < 7:
                    collision_bars += 1

        # Normalization formulas from spec
        register_balance = max(0.0, 10.0 - (register_miss_bars * 2.5))
        mud_risk = max(0.0, 10.0 - (mud_bars * 2.0))
        overcrowding_risk = max(0.0, 10.0 - (imbalance_bars * 1.5))
        spacing_quality = max(0.0, 10.0 - (collision_bars * 2.5))

        now = utc_now()
        return RegisterDensityEvaluation(
            id=f"rd_eval_{ULID()}",
            type="register_density_evaluation",
            status="completed",
            created_at=now,
            updated_at=now,
            candidate_id=voicing_plan.progression_candidate_id or voicing_plan.id,
            evaluation_type="register_density",
            register_balance_score=round(register_balance, 2),
            mud_risk_score=round(mud_risk, 2),
            overcrowding_risk_score=round(overcrowding_risk, 2),
            spacing_quality=round(spacing_quality, 2),
        )

    def overall_score(self, evaluation: RegisterDensityEvaluation) -> float:
        """Single 0-10 score for aggregate scorecard."""
        return round(
            (evaluation.register_balance_score + evaluation.mud_risk_score
             + evaluation.overcrowding_risk_score + evaluation.spacing_quality) / 4.0,
            2,
        )

    def _perfect_score(self, candidate_id: str) -> RegisterDensityEvaluation:
        now = utc_now()
        return RegisterDensityEvaluation(
            id=f"rd_eval_{ULID()}",
            type="register_density_evaluation",
            status="completed",
            created_at=now, updated_at=now,
            candidate_id=candidate_id, evaluation_type="register_density",
            register_balance_score=10.0, mud_risk_score=10.0,
            overcrowding_risk_score=10.0, spacing_quality=10.0,
        )
```

- [ ] **Step 4: Run tests — expect pass**

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/domain/evaluation/register_density.py backend/tests/unit/domain/test_register_density_evaluator.py
git commit -m "feat(m2b): add RegisterDensityEvaluator"
```

---

## Task 8: PlayabilityEvaluator

**Files:**
- Create: `backend/src/explorator/domain/evaluation/playability.py`
- Create: `backend/tests/unit/domain/test_playability_evaluator.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/domain/test_playability_evaluator.py

from explorator.domain.evaluation.playability import PlayabilityEvaluator
from explorator.models.evaluation import PlayabilityEvaluation
from explorator.models.realization import VoicingEvent, VoicingPlan


def _make_plan(events: list[list[str]]) -> VoicingPlan:
    return VoicingPlan(
        id="vp_test", type="voicing_plan", status="draft",
        voicing_events=[
            VoicingEvent(bar=i + 1, pitches=p, chord_symbol="C")
            for i, p in enumerate(events)
        ],
    )


class TestPlayabilityEvaluator:
    def test_comfortable_voicing_scores_high(self):
        plan = _make_plan([["C4", "E4", "G4", "B4"]])  # span = 11 semitones
        evaluator = PlayabilityEvaluator()
        result = evaluator.evaluate(plan)
        assert isinstance(result, PlayabilityEvaluation)
        assert result.piano_playability >= 9.0

    def test_wide_stretch_penalized(self):
        plan = _make_plan([["C3", "E3", "G3", "E5"]])  # span = 28 semitones
        evaluator = PlayabilityEvaluator()
        result = evaluator.evaluate(plan)
        assert result.piano_playability < 7.0

    def test_stretchy_span_mild_penalty(self):
        plan = _make_plan([["C4", "E4", "G4", "D5"]])  # span = 14 semitones (just under 15)
        evaluator = PlayabilityEvaluator()
        result = evaluator.evaluate(plan)
        assert result.piano_playability >= 8.0  # mild penalty at most

    def test_too_many_notes(self):
        plan = _make_plan([["C4", "D4", "E4", "F4", "G4", "A4"]])  # 6 notes
        evaluator = PlayabilityEvaluator()
        result = evaluator.evaluate(plan)
        assert result.piano_playability < 8.0

    def test_simplification_recommendations(self):
        plan = _make_plan([["C3", "E3", "G3", "E5"]])  # wide
        evaluator = PlayabilityEvaluator()
        result = evaluator.evaluate(plan)
        assert len(result.simplification_recommendations) > 0

    def test_guitar_deferred(self):
        plan = _make_plan([["C4", "E4", "G4"]])
        evaluator = PlayabilityEvaluator()
        result = evaluator.evaluate(plan)
        assert result.guitar_playability == 0.0
```

- [ ] **Step 2: Run tests — expect fail**

- [ ] **Step 3: Implement PlayabilityEvaluator**

```python
# backend/src/explorator/domain/evaluation/playability.py

"""Deterministic playability evaluator."""

from ulid import ULID

from explorator.models.evaluation import PlayabilityEvaluation
from explorator.models.realization import VoicingPlan
from explorator.utils import utc_now


class PlayabilityEvaluator:
    """Evaluates physical playability of a voicing plan."""

    def evaluate(self, plan: VoicingPlan) -> PlayabilityEvaluation:
        """Score playability across all voicing events."""
        from music21 import pitch as m21pitch

        events = plan.voicing_events
        if not events:
            return self._perfect_score(plan.id)

        total_penalty = 0.0
        recommendations: list[str] = []

        for ve in events:
            midi = sorted([m21pitch.Pitch(p).midi for p in ve.pitches])
            span = midi[-1] - midi[0] if len(midi) >= 2 else 0
            n_voices = len(midi)

            bar_penalty = 0.0
            if span > 15:
                bar_penalty += 3.0
                recommendations.append(
                    f"Bar {ve.bar}: span of {span} semitones exceeds comfortable range"
                )
            elif span >= 13:
                bar_penalty += 1.0

            if n_voices > 5:
                bar_penalty += 2.0
                recommendations.append(
                    f"Bar {ve.bar}: {n_voices} voices exceeds single-hand limit"
                )

            total_penalty += bar_penalty

        avg_penalty = total_penalty / len(events)
        piano_score = max(0.0, min(10.0, 10.0 - avg_penalty))

        now = utc_now()
        return PlayabilityEvaluation(
            id=f"play_eval_{ULID()}",
            type="playability_evaluation",
            status="completed",
            created_at=now,
            updated_at=now,
            candidate_id=plan.progression_candidate_id or plan.id,
            evaluation_type="playability",
            piano_playability=round(piano_score, 2),
            guitar_playability=0.0,
            ensemble_playability=round(piano_score, 2),
            simplification_recommendations=recommendations,
        )

    def overall_score(self, evaluation: PlayabilityEvaluation) -> float:
        """Single 0-10 score for aggregate scorecard."""
        return evaluation.piano_playability

    def _perfect_score(self, candidate_id: str) -> PlayabilityEvaluation:
        now = utc_now()
        return PlayabilityEvaluation(
            id=f"play_eval_{ULID()}",
            type="playability_evaluation",
            status="completed",
            created_at=now, updated_at=now,
            candidate_id=candidate_id, evaluation_type="playability",
            piano_playability=10.0, guitar_playability=0.0,
            ensemble_playability=10.0, simplification_recommendations=[],
        )
```

- [ ] **Step 4: Run tests — expect pass**

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/domain/evaluation/playability.py backend/tests/unit/domain/test_playability_evaluator.py
git commit -m "feat(m2b): add PlayabilityEvaluator"
```

---

## Task 9: evaluate_arrangements Node

**Files:**
- Create: `backend/src/explorator/engine/nodes/evaluate_arrangements.py`

- [ ] **Step 1: Implement evaluate_arrangements**

```python
# backend/src/explorator/engine/nodes/evaluate_arrangements.py

"""Run three deterministic evaluators on all arrangement candidates."""

import logging
from typing import Any

from explorator.domain.evaluation.playability import PlayabilityEvaluator
from explorator.domain.evaluation.register_density import RegisterDensityEvaluator
from explorator.domain.evaluation.voice_leading import VoiceLeadingEvaluator
from explorator.engine.realization_state import RealizationState
from explorator.models.realization import BassLine, VoicingPlan

logger = logging.getLogger(__name__)


async def evaluate_arrangements(state: RealizationState) -> dict[str, Any]:
    """Evaluate all arrangement candidates on voice leading, register, playability."""
    callback = state.get("on_progress")
    if callback:
        n = len(state.get("arrangement_candidates", []))
        await callback("node_started", {"node": "evaluate_arrangements", "count": n})

    vl_evaluator = VoiceLeadingEvaluator()
    rd_evaluator = RegisterDensityEvaluator()
    play_evaluator = PlayabilityEvaluator()

    genre_profile = state.get("genre_profile", {})
    voicing_prefs = genre_profile.get("voicing_preferences", {})
    preferred_register = voicing_prefs.get("default_register", "mid") if isinstance(voicing_prefs, dict) else "mid"

    # Build lookup: id → VoicingPlan, id → BassLine
    vp_lookup: dict[str, VoicingPlan] = {}
    for vp_data in state.get("voicing_plans", []):
        vp = VoicingPlan.model_validate(vp_data)
        vp_lookup[vp.id] = vp

    bl_lookup: dict[str, BassLine] = {}
    for bl_data in state.get("bass_lines", []):
        bl = BassLine.model_validate(bl_data)
        bl_lookup[bl.id] = bl

    all_evaluations: list[dict[str, Any]] = []

    for ac_data in state.get("arrangement_candidates", []):
        ac_id = ac_data.get("id", "")
        vp_id = ac_data.get("voicing_plan_id")
        bl_id = ac_data.get("bass_line_id")

        vp = vp_lookup.get(vp_id) if vp_id else None
        bl = bl_lookup.get(bl_id) if bl_id else None

        if vp is None:
            logger.warning("No voicing plan found for arrangement %s", ac_id)
            continue

        # Voice leading
        vl_eval = vl_evaluator.evaluate(vp)
        vl_overall = vl_evaluator.overall_score(vl_eval)

        # Register density
        rd_eval = rd_evaluator.evaluate(vp, bl or BassLine(id="empty", type="bass_line", status="draft"), preferred_register)
        rd_overall = rd_evaluator.overall_score(rd_eval)

        # Playability
        play_eval = play_evaluator.evaluate(vp)
        play_overall = play_evaluator.overall_score(play_eval)

        all_evaluations.append({
            "arrangement_candidate_id": ac_id,
            "voice_leading": vl_eval.model_dump(mode="json"),
            "voice_leading_overall": vl_overall,
            "register_density": rd_eval.model_dump(mode="json"),
            "register_density_overall": rd_overall,
            "playability": play_eval.model_dump(mode="json"),
            "playability_overall": play_overall,
        })

    if callback:
        await callback("node_completed", {
            "node": "evaluate_arrangements",
            "evaluated": len(all_evaluations),
        })

    return {"evaluations": all_evaluations}
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/explorator/engine/nodes/evaluate_arrangements.py
git commit -m "feat(m2b): add evaluate_arrangements LangGraph node"
```

---

## Task 10: rank_and_select Node

**Files:**
- Create: `backend/src/explorator/engine/nodes/rank_and_select.py`
- Create: `backend/tests/unit/engine/test_rank_and_select.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/engine/test_rank_and_select.py

from explorator.engine.nodes.rank_and_select import _rank_family, _compute_weighted_total

# Weight config from spec
WEIGHTS = {
    "voice_leading": 0.15,
    "register_density": 0.12,
    "playability": 0.12,
    "genre_fit": 0.10,
    "emotional_fit": 0.10,
    "theoretical_coherence": 0.10,
    "cadence_quality": 0.10,
    "novelty": 0.10,
    "loopability": 0.11,
}


class TestComputeWeightedTotal:
    def test_all_perfect(self):
        scores = {k: 10.0 for k in WEIGHTS}
        total = _compute_weighted_total(scores, WEIGHTS)
        assert abs(total - 10.0) < 0.01

    def test_all_zero(self):
        scores = {k: 0.0 for k in WEIGHTS}
        total = _compute_weighted_total(scores, WEIGHTS)
        assert total == 0.0

    def test_missing_m1_scores_fallback(self):
        """Missing M1 dimensions use 5.0 fallback."""
        scores = {"voice_leading": 8.0, "register_density": 7.0, "playability": 9.0}
        total = _compute_weighted_total(scores, WEIGHTS)
        # M1 dims at 5.0 × 0.61 + new dims weighted
        assert 5.0 < total < 9.0


class TestRankFamily:
    def test_rejects_below_threshold(self):
        candidates = [
            {"id": "a", "scores": {"voice_leading": 2.0, "register_density": 8.0, "playability": 8.0}},
            {"id": "b", "scores": {"voice_leading": 7.0, "register_density": 7.0, "playability": 7.0}},
        ]
        selected, rejected = _rank_family(candidates, WEIGHTS, min_threshold=3.0)
        assert len(rejected) == 1
        assert rejected[0]["id"] == "a"

    def test_selects_top_2(self):
        candidates = [
            {"id": "a", "scores": {"voice_leading": 9.0, "register_density": 9.0, "playability": 9.0}},
            {"id": "b", "scores": {"voice_leading": 8.0, "register_density": 8.0, "playability": 8.0}},
            {"id": "c", "scores": {"voice_leading": 7.0, "register_density": 7.0, "playability": 7.0}},
        ]
        selected, rejected = _rank_family(candidates, WEIGHTS, min_threshold=3.0, top_n=2)
        assert len(selected) == 2
        assert selected[0]["id"] == "a"  # highest score first

    def test_keeps_all_if_fewer_than_top_n(self):
        candidates = [
            {"id": "a", "scores": {"voice_leading": 9.0, "register_density": 9.0, "playability": 9.0}},
        ]
        selected, rejected = _rank_family(candidates, WEIGHTS, min_threshold=3.0, top_n=2)
        assert len(selected) == 1
```

- [ ] **Step 2: Run tests — expect fail**

- [ ] **Step 3: Implement rank_and_select**

```python
# backend/src/explorator/engine/nodes/rank_and_select.py

"""Within-family ranking and selection of arrangement candidates."""

import logging
from typing import Any

from ulid import ULID

from explorator.engine.realization_state import RealizationState
from explorator.models.evaluation import AggregateScorecard
from explorator.utils import utc_now

logger = logging.getLogger(__name__)

# Scoring weights from spec
DEFAULT_WEIGHTS: dict[str, float] = {
    "voice_leading": 0.15,
    "register_density": 0.12,
    "playability": 0.12,
    "genre_fit": 0.10,
    "emotional_fit": 0.10,
    "theoretical_coherence": 0.10,
    "cadence_quality": 0.10,
    "novelty": 0.10,
    "loopability": 0.11,
}

M1_FALLBACK = 5.0  # neutral score for missing M1 dimensions
MIN_THRESHOLD = 3.0
TOP_N = 2


def _compute_weighted_total(scores: dict[str, float], weights: dict[str, float]) -> float:
    """Compute weighted total. Missing dimensions use M1_FALLBACK."""
    total = 0.0
    for dim, weight in weights.items():
        total += scores.get(dim, M1_FALLBACK) * weight
    return round(total, 2)


def _rank_family(
    candidates: list[dict[str, Any]],
    weights: dict[str, float],
    min_threshold: float = MIN_THRESHOLD,
    top_n: int = TOP_N,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Rank candidates within a family. Returns (selected, rejected)."""
    rejected = []
    survivors = []

    for c in candidates:
        scores = c.get("scores", {})
        # Check minimum quality on new evaluator dimensions
        new_dims = ["voice_leading", "register_density", "playability"]
        if any(scores.get(d, M1_FALLBACK) < min_threshold for d in new_dims):
            c["status"] = "rejected"
            rejected.append(c)
        else:
            c["weighted_total"] = _compute_weighted_total(scores, weights)
            survivors.append(c)

    # Sort by weighted total descending
    survivors.sort(key=lambda c: c.get("weighted_total", 0), reverse=True)

    # Select top N
    selected = survivors[:top_n]
    for i, c in enumerate(selected):
        c["status"] = "selected"
        c["rank"] = i + 1

    # Remaining survivors are not selected but not rejected
    for c in survivors[top_n:]:
        c["status"] = "draft"

    return selected, rejected


async def rank_and_select(state: RealizationState) -> dict[str, Any]:
    """Rank arrangement candidates within each family."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "rank_and_select"})

    evaluations = state.get("evaluations", [])
    candidates = list(state.get("arrangement_candidates", []))
    families = list(state.get("arrangement_families", []))

    # Build eval lookup: arrangement_id → scores
    eval_lookup: dict[str, dict[str, float]] = {}
    for ev in evaluations:
        ac_id = ev.get("arrangement_candidate_id", "")
        eval_lookup[ac_id] = {
            "voice_leading": ev.get("voice_leading_overall", M1_FALLBACK),
            "register_density": ev.get("register_density_overall", M1_FALLBACK),
            "playability": ev.get("playability_overall", M1_FALLBACK),
        }

    # Read M1 scores from progression candidates
    m1_scores_by_prog: dict[str, dict[str, float]] = {}
    for pc in state.get("progression_candidates", []):
        pc_id = pc.get("id", "")
        metadata = pc.get("metadata", {})
        m1_scores_by_prog[pc_id] = metadata.get("scores", {})

    # Attach scores to each candidate
    for c in candidates:
        ac_id = c.get("id", "")
        prog_id = c.get("progression_candidate_id", "")
        scores = dict(eval_lookup.get(ac_id, {}))
        scores.update(m1_scores_by_prog.get(prog_id, {}))
        c["scores"] = scores

    # Group candidates by family
    family_members: dict[str, list[dict[str, Any]]] = {}
    for c in candidates:
        prog_id = c.get("progression_candidate_id", "")
        family_members.setdefault(prog_id, []).append(c)

    all_scorecards: list[dict[str, Any]] = []
    all_selected: list[dict[str, Any]] = []

    for prog_id, members in family_members.items():
        selected, rejected = _rank_family(members, DEFAULT_WEIGHTS)
        all_selected.extend(selected)

        # Build scorecards for all evaluated candidates
        for c in members:
            now = utc_now()
            sc = AggregateScorecard(
                id=f"score_{ULID()}",
                type="aggregate_scorecard",
                status="completed",
                created_at=now,
                updated_at=now,
                candidate_id=c["id"],
                scores=c.get("scores", {}),
                weighted_total=c.get("weighted_total", 0.0),
                rank_within_round=c.get("rank", 0),
            )
            all_scorecards.append(sc.model_dump(mode="json"))

    # Update family root to highest scorer
    for fam in families:
        prog_id = None
        for c in candidates:
            if c.get("id") in fam.get("member_arrangement_candidate_ids", []):
                prog_id = c.get("progression_candidate_id")
                break
        if prog_id and prog_id in family_members:
            members = family_members[prog_id]
            best = max(members, key=lambda c: c.get("weighted_total", 0), default=None)
            if best:
                fam["root_arrangement_candidate_id"] = best["id"]

    if callback:
        await callback("node_completed", {
            "node": "rank_and_select",
            "selected": len(all_selected),
            "total": len(candidates),
        })

    return {
        "arrangement_candidates": candidates,  # updated with status/scores
        "arrangement_families": families,  # updated root
        "scorecards": all_scorecards,
        "selected_arrangements": [c for c in candidates if c.get("status") == "selected"],
    }
```

- [ ] **Step 4: Run tests — expect pass**

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/engine/nodes/rank_and_select.py backend/tests/unit/engine/test_rank_and_select.py
git commit -m "feat(m2b): add rank_and_select node with within-family ranking"
```

---

## Task 11: State, Graph, and Persistence Updates

**Files:**
- Modify: `backend/src/explorator/engine/realization_state.py`
- Modify: `backend/src/explorator/engine/realization_graph.py`
- Modify: `backend/src/explorator/engine/nodes/persist_realization.py`

- [ ] **Step 1: Update RealizationState**

Add to `backend/src/explorator/engine/realization_state.py`:

```python
    # Produced by evaluate_arrangements
    evaluations: list[dict[str, Any]]
    scorecards: list[dict[str, Any]]

    # Produced by rank_and_select
    selected_arrangements: list[dict[str, Any]]
```

- [ ] **Step 2: Update realization_graph.py**

Insert the two new nodes between `assemble` and `persist_realization`:

```python
from explorator.engine.nodes.evaluate_arrangements import evaluate_arrangements
from explorator.engine.nodes.rank_and_select import rank_and_select

# In build_realization_graph():
graph.add_node("evaluate_arrangements", evaluate_arrangements)
graph.add_node("rank_and_select", rank_and_select)

# Update edges:
graph.add_edge("assemble", "evaluate_arrangements")
graph.add_edge("evaluate_arrangements", "rank_and_select")
graph.add_edge("rank_and_select", "persist_realization")
# Remove: graph.add_edge("assemble", "persist_realization")
```

- [ ] **Step 3: Update persist_realization**

Add persistence for evaluations, scorecards, and status updates. After the existing entity writes, add:

```python
# 5. Persist evaluation entities
for eval_data in state.get("evaluations", []):
    for eval_type in ["voice_leading", "register_density", "playability"]:
        if eval_type in eval_data:
            eval_entity = eval_data[eval_type]
            label = eval_entity.get("type", "evaluation").replace("_", " ").title().replace(" ", "")
            # Use generic create with appropriate label
            try:
                query = f"CREATE (n:{label} $props) SET n.id = $props.id"
                async with driver.session() as session:
                    from explorator.graph.repository import _neo4j_safe
                    await session.run(query, props=_neo4j_safe(eval_entity))
            except Exception:
                logger.exception("Failed to persist %s", label)

# 6. Persist scorecards
for sc_data in state.get("scorecards", []):
    try:
        query = "CREATE (n:AggregateScorecard $props) SET n.id = $props.id"
        async with driver.session() as session:
            from explorator.graph.repository import _neo4j_safe
            await session.run(query, props=_neo4j_safe(sc_data))
        # Create relationship
        ac_id = sc_data.get("candidate_id")
        if ac_id:
            await _create_relationship(driver, "ArrangementCandidate", ac_id, "HAS_SCORECARD", "AggregateScorecard", sc_data["id"])
    except Exception:
        logger.exception("Failed to persist scorecard")

# 7. Update ArrangementCandidate statuses
for ac_data in state.get("arrangement_candidates", []):
    status = ac_data.get("status")
    ac_id = ac_data.get("id")
    if status in ("selected", "rejected") and ac_id:
        try:
            query = "MATCH (n:ArrangementCandidate {id: $id}) SET n.status = $status"
            async with driver.session() as session:
                await session.run(query, id=ac_id, status=status)
        except Exception:
            logger.exception("Failed to update status for %s", ac_id)
```

- [ ] **Step 4: Run full test suite**

Run: `cd /home/angel/Documents/code/Explorator/backend && .venv/bin/python -m pytest tests/unit/ -q --tb=short`

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/engine/realization_state.py backend/src/explorator/engine/realization_graph.py backend/src/explorator/engine/nodes/persist_realization.py
git commit -m "feat(m2b): update state, graph, and persistence for evaluation pipeline"
```

---

## Task 12: API Enrichment

**Files:**
- Modify: `backend/src/explorator/api/routes/realization_rounds.py`

- [ ] **Step 1: Enrich GET /arrangements/{id} with scorecard**

Update the `get_arrangement` endpoint to fetch and include the `AggregateScorecard` and evaluation data:

```python
# In get_arrangement(), after fetching voicing_plan and bass_line:

# Fetch scorecard
class ScorecardRepo(BaseRepository):
    label = "AggregateScorecard"

sc_repo = ScorecardRepo(driver)
scorecards = await sc_repo.query_by_property("candidate_id", arrangement_id)
if scorecards:
    arrangement["scorecard"] = scorecards[0]
```

- [ ] **Step 2: Enrich GET /candidates/{id}/arrangements with scores**

Update `list_arrangements` to include `weighted_total`, `status`, and `rank_within_round` from the scorecard:

```python
# In list_arrangements():
results = await repo.query_by_property("progression_candidate_id", candidate_id)

# Enrich each result with scorecard data
sc_repo = ScorecardRepo(driver)
for r in results:
    scorecards = await sc_repo.query_by_property("candidate_id", r.get("id"))
    if scorecards:
        sc = scorecards[0]
        r["weighted_total"] = sc.get("weighted_total", 0.0)
        r["rank_within_round"] = sc.get("rank_within_round", 0)
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/explorator/api/routes/realization_rounds.py
git commit -m "feat(m2b): enrich arrangement API responses with scores"
```

---

## Task 13: Integration Test and Final Verification

**Files:**
- Modify: `backend/tests/integration/test_realization_flow.py`

- [ ] **Step 1: Update integration test**

Add to `test_realization_flow.py`:

```python
@pytest.mark.integration
def test_realization_graph_has_evaluation_nodes(gemini, driver):
    """Graph should include evaluate_arrangements and rank_and_select."""
    from explorator.engine.realization_graph import build_realization_graph
    graph = build_realization_graph(gemini, driver)
    node_names = set(graph.nodes.keys())
    expected = {
        "load_context", "plan_voicings", "generate_bass", "assemble",
        "evaluate_arrangements", "rank_and_select", "persist_realization",
    }
    assert expected.issubset(node_names), f"Missing nodes: {expected - node_names}"
```

- [ ] **Step 2: Run full test suite**

Run: `cd /home/angel/Documents/code/Explorator/backend && .venv/bin/python -m pytest tests/unit/ tests/integration/test_realization_flow.py -v --tb=short`
Expected: All tests PASS

- [ ] **Step 3: Verify file structure**

Run: `find src/explorator/domain/evaluation -name "*.py" -not -name "__pycache__" | sort && find src/explorator/engine/nodes -name "*.py" | sort`

- [ ] **Step 4: Commit**

```bash
git add backend/tests/integration/test_realization_flow.py
git commit -m "feat(m2b): update integration test for evaluation pipeline"
```
