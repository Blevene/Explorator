# M5b Melodic Complement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add single-line melody generation to the realization pipeline — Gemini strategy + deterministic realization, two evaluation dimensions, frontend piano roll lane and playback toggle.

**Architecture:** Two-phase generation mirroring voicing: Gemini Flash produces a `MelodicStrategyResponse` with per-phrase instructions, then a deterministic `MelodyGenerator` realizes concrete pitches via constraint-based selection. Melody is linked to arrangements via post-hoc round-robin (matching groove pattern). Evaluation uses two deterministic dimensions on a 0-10 scale.

**Tech Stack:** Python/Pydantic models, LangGraph nodes, Gemini Flash structured output, music21 pitch utilities, React/Tone.js frontend, Playwright E2E.

**Spec:** `docs/superpowers/specs/2026-04-16-m5b-melodic-complement-design.md`

---

## File Structure

### Backend — New Files

| File | Responsibility |
|------|---------------|
| `backend/src/explorator/models/melody.py` | `MelodicNoteEvent`, `MelodicComplement`, `PhraseInstruction`, `MelodicStrategyResponse`, `MelodicPreferences` |
| `backend/src/explorator/prompts/melody.py` | `melody_strategy_prompt()` → `(user_prompt, system_prompt)` |
| `backend/src/explorator/domain/realization/melody.py` | `MelodyGenerator` — deterministic realization from strategy |
| `backend/src/explorator/engine/nodes/generate_melody.py` | LangGraph node: Gemini strategy call + `MelodyGenerator.realize()` |
| `backend/src/explorator/domain/evaluation/melody_harmony.py` | `MelodyHarmonyEvaluator` — melody_support + collision_risk scoring |

### Backend — Modified Files

| File | Changes |
|------|---------|
| `backend/src/explorator/engine/state.py` | Add `melodic_complements` key |
| `backend/src/explorator/engine/graph.py` | Wire `generate_melody` node with Gemini injection |
| `backend/src/explorator/engine/nodes/assemble_arrangements.py` | Add melody round-robin assignment |
| `backend/src/explorator/engine/nodes/evaluate_arrangements.py` | Add conditional MelodyHarmonyEvaluator |
| `backend/src/explorator/domain/evaluation/ranking.py` | Update `CANONICAL_DEFAULT_WEIGHTS` to 12 dimensions + conditional normalization |
| `backend/src/explorator/domain/style/genres/dream_pop.yaml` | Add `melodic_tendencies` |
| `backend/src/explorator/domain/style/genres/synthwave.yaml` | Add `melodic_tendencies` |
| `backend/src/explorator/domain/style/genres/cinematic.yaml` | Add `melodic_tendencies` |

### Backend — New Test Files

| File | Covers |
|------|--------|
| `backend/tests/unit/models/test_melody_models.py` | Model validation and defaults |
| `backend/tests/unit/prompts/test_melody_prompt.py` | Prompt output structure |
| `backend/tests/unit/domain/test_melody_generator.py` | Realization algorithm, edge cases |
| `backend/tests/unit/domain/test_melody_harmony_evaluator.py` | Scoring dimensions |

### Frontend — Modified Files

| File | Changes |
|------|---------|
| `frontend/src/services/api.ts` | Add `melodic_complement` to `ArrangementDetail` |
| `frontend/src/stores/audioStore.ts` | Add `melody` to `mutedTracks` |
| `frontend/src/services/audioPresets.ts` | Add `MELODY_DEFAULT` constant |
| `frontend/src/services/audioEngine.ts` | Add melody `MonoSynth` + scheduling |
| `frontend/src/utils/designTokens.ts` | Add `melodyNote` color |
| `frontend/src/components/PianoRoll.tsx` | Third rendering pass + collectMidiValues update |
| `frontend/src/components/TransportBar.tsx` | Melody mute toggle button |
| `frontend/src/stores/comparisonAudioStore.ts` | Add `trackMutes` model |
| `frontend/src/services/comparisonAudioEngine.ts` | Per-track volumes, melody synth per lane |
| `frontend/src/components/ComparisonView.tsx` | Melody lane with per-track mute/solo |

---

## Task 1: Melody Models

**Files:**
- Create: `backend/src/explorator/models/melody.py`
- Create: `backend/tests/unit/models/test_melody_models.py`

- [ ] **Step 1: Write model tests**

```python
# backend/tests/unit/models/test_melody_models.py
"""Tests for melody models."""

from explorator.models.melody import (
    MelodicComplement,
    MelodicNoteEvent,
    MelodicPreferences,
    MelodicStrategyResponse,
    PhraseInstruction,
)


class TestMelodicNoteEvent:
    def test_defaults(self) -> None:
        e = MelodicNoteEvent(bar=1, pitch="C5")
        assert e.beat == 1.0
        assert e.duration_beats == 1.0
        assert e.velocity == 80

    def test_explicit(self) -> None:
        e = MelodicNoteEvent(bar=2, beat=2.5, duration_beats=0.5, pitch="E5", velocity=100)
        assert e.bar == 2
        assert e.beat == 2.5
        assert e.pitch == "E5"


class TestMelodicComplement:
    def test_defaults(self) -> None:
        mc = MelodicComplement(
            id="mc_test",
            type="melodic_complement",
            status="completed",
            arrangement_candidate_id="arr_test",
        )
        assert mc.groove_pattern_id is None
        assert mc.note_events == []
        assert mc.range_low == ""
        assert mc.range_high == ""
        assert mc.contour_type == ""
        assert mc.source_strategy == ""

    def test_with_events(self) -> None:
        events = [MelodicNoteEvent(bar=1, pitch="C5"), MelodicNoteEvent(bar=1, beat=2.0, pitch="D5")]
        mc = MelodicComplement(
            id="mc_test",
            type="melodic_complement",
            status="completed",
            arrangement_candidate_id="arr_test",
            note_events=events,
            range_low="C5",
            range_high="C6",
            contour_type="arch",
        )
        assert len(mc.note_events) == 2
        assert mc.range_low == "C5"


class TestPhraseInstruction:
    def test_creation(self) -> None:
        pi = PhraseInstruction(
            start_bar=1,
            end_bar=4,
            contour="arch",
            density="moderate",
            strong_beat_targets=["root", "5th"],
            rest_after=True,
        )
        assert pi.start_bar == 1
        assert pi.end_bar == 4
        assert pi.rest_after is True


class TestMelodicStrategyResponse:
    def test_creation(self) -> None:
        sr = MelodicStrategyResponse(
            range_low="C5",
            range_high="C6",
            overall_contour="arch",
            phrase_instructions=[
                PhraseInstruction(
                    start_bar=1, end_bar=4, contour="arch",
                    density="moderate", strong_beat_targets=["root"], rest_after=False,
                ),
            ],
        )
        assert sr.range_low == "C5"
        assert len(sr.phrase_instructions) == 1
        assert sr.rationale == ""

    def test_rationale_max_length(self) -> None:
        import pytest
        with pytest.raises(Exception):
            MelodicStrategyResponse(
                range_low="C5",
                range_high="C6",
                overall_contour="arch",
                phrase_instructions=[],
                rationale="x" * 201,
            )


class TestMelodicPreferences:
    def test_defaults(self) -> None:
        mp = MelodicPreferences()
        assert mp.motion_preference == "stepwise"
        assert mp.density == "moderate"
        assert mp.phrase_length == 4

    def test_from_genre_tendencies(self) -> None:
        tendencies = {
            "motion_preference": "leaping",
            "density": "sparse",
            "phrase_length": "2",
            "strong_beat_preference": "roots_and_fifths",
        }
        mp = MelodicPreferences.from_genre_tendencies(tendencies)
        assert mp.motion_preference == "leaping"
        assert mp.density == "sparse"
        assert mp.phrase_length == 2

    def test_from_empty_tendencies(self) -> None:
        mp = MelodicPreferences.from_genre_tendencies({})
        assert mp.motion_preference == "stepwise"
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd backend && python -m pytest tests/unit/models/test_melody_models.py -v
```
Expected: `ModuleNotFoundError: No module named 'explorator.models.melody'`

- [ ] **Step 3: Implement models**

```python
# backend/src/explorator/models/melody.py
"""Melody models: note events, melodic complements, strategy responses, and preferences."""

from __future__ import annotations

from pydantic import BaseModel, Field

from explorator.models.base import BaseEntity


# ---------------------------------------------------------------------------
# Event models
# ---------------------------------------------------------------------------


class MelodicNoteEvent(BaseModel):
    """A single note event in a melodic complement."""

    bar: int
    beat: float = 1.0
    duration_beats: float = 1.0
    pitch: str  # e.g. "C5"
    velocity: int = 80


# ---------------------------------------------------------------------------
# Strategy response models (Gemini structured output)
# ---------------------------------------------------------------------------


class PhraseInstruction(BaseModel):
    """Per-phrase melodic instructions from the LLM strategy."""

    start_bar: int
    end_bar: int  # inclusive
    contour: str  # arch | descending | ascending | wave | static
    density: str  # sparse | moderate | active
    strong_beat_targets: list[str] = Field(default_factory=list)
    rest_after: bool = False


class MelodicStrategyResponse(BaseModel):
    """LLM-generated melodic strategy for an arrangement."""

    range_low: str  # e.g. "C5"
    range_high: str  # e.g. "C6"
    overall_contour: str
    phrase_instructions: list[PhraseInstruction] = Field(default_factory=list)
    rationale: str = Field(default="", max_length=200)


# ---------------------------------------------------------------------------
# Domain entity
# ---------------------------------------------------------------------------


class MelodicComplement(BaseEntity):
    """System-generated single-line melody for an arrangement."""

    arrangement_candidate_id: str
    groove_pattern_id: str | None = None
    note_events: list[MelodicNoteEvent] = Field(default_factory=list)
    range_low: str = ""
    range_high: str = ""
    contour_type: str = ""
    source_strategy: str = ""


# ---------------------------------------------------------------------------
# Preference models (parsed from genre YAML)
# ---------------------------------------------------------------------------


class MelodicPreferences(BaseModel):
    """Genre-derived melodic preferences."""

    motion_preference: str = "stepwise"  # stepwise | leaping | mixed
    range_placement: str = "above_voicing"
    density: str = "moderate"  # sparse | moderate | active
    phrase_length: int = 4  # 2 | 4
    strong_beat_preference: str = "chord_tones"
    rest_between_phrases: bool = True

    @classmethod
    def from_genre_tendencies(cls, tendencies: dict[str, str]) -> MelodicPreferences:
        """Build preferences from genre YAML melodic_tendencies section."""
        phrase_length_raw = tendencies.get("phrase_length", "4")
        try:
            phrase_length = int(phrase_length_raw)
        except (ValueError, TypeError):
            phrase_length = 4

        return cls(
            motion_preference=tendencies.get("motion_preference", "stepwise"),
            range_placement=tendencies.get("range_placement", "above_voicing"),
            density=tendencies.get("density", "moderate"),
            phrase_length=phrase_length,
            strong_beat_preference=tendencies.get("strong_beat_preference", "chord_tones"),
            rest_between_phrases=tendencies.get("rest_between_phrases", "true").lower() != "false"
            if isinstance(tendencies.get("rest_between_phrases"), str)
            else bool(tendencies.get("rest_between_phrases", True)),
        )
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd backend && python -m pytest tests/unit/models/test_melody_models.py -v
```
Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/models/melody.py backend/tests/unit/models/test_melody_models.py
git commit -m "feat(m5b): add melody models — MelodicComplement, strategy response, preferences"
```

---

## Task 2: Genre YAML Extensions

**Files:**
- Modify: `backend/src/explorator/domain/style/genres/dream_pop.yaml`
- Modify: `backend/src/explorator/domain/style/genres/synthwave.yaml`
- Modify: `backend/src/explorator/domain/style/genres/cinematic.yaml`

- [ ] **Step 1: Add melodic_tendencies to dream_pop.yaml**

Append after `groove_tendencies` block (after line 36):

```yaml
melodic_tendencies:
  motion_preference: stepwise
  range_placement: above_voicing
  density: sparse
  phrase_length: 4
  strong_beat_preference: extensions
  rest_between_phrases: true
```

- [ ] **Step 2: Add melodic_tendencies to synthwave.yaml**

Append after `groove_tendencies` block:

```yaml
melodic_tendencies:
  motion_preference: mixed
  range_placement: above_voicing
  density: moderate
  phrase_length: 2
  strong_beat_preference: chord_tones
  rest_between_phrases: true
```

- [ ] **Step 3: Add melodic_tendencies to cinematic.yaml**

Append after `groove_tendencies` block:

```yaml
melodic_tendencies:
  motion_preference: leaping
  range_placement: above_voicing
  density: sparse
  phrase_length: 4
  strong_beat_preference: roots_and_fifths
  rest_between_phrases: true
```

- [ ] **Step 4: Commit**

```bash
git add backend/src/explorator/domain/style/genres/*.yaml
git commit -m "feat(m5b): add melodic_tendencies to genre YAML profiles"
```

---

## Task 3: Melody Strategy Prompt

**Files:**
- Create: `backend/src/explorator/prompts/melody.py`
- Create: `backend/tests/unit/prompts/test_melody_prompt.py`

- [ ] **Step 1: Write prompt tests**

```python
# backend/tests/unit/prompts/test_melody_prompt.py
"""Tests for melody strategy prompt generation."""

from explorator.prompts.melody import melody_strategy_prompt


class TestMelodyStrategyPrompt:
    def test_returns_user_and_system_prompts(self) -> None:
        user, system = melody_strategy_prompt(
            chord_symbols=["Cmaj7", "Am7", "Fmaj7", "G7"],
            key_center="C",
            mode="major",
            genre="dream_pop",
            melodic_tendencies={"motion_preference": "stepwise", "density": "sparse"},
            voicing_ceiling_notes=["B4", "A4", "A4", "B4"],
            bass_floor_notes=["C3", "A2", "F2", "G2"],
            groove_summary="straight eighths, no swing",
        )
        assert isinstance(user, str)
        assert isinstance(system, str)

    def test_user_prompt_contains_chords(self) -> None:
        user, _ = melody_strategy_prompt(
            chord_symbols=["Dm7", "G7"],
            key_center="C",
            mode="major",
            genre="synthwave",
            melodic_tendencies={},
            voicing_ceiling_notes=["A4", "B4"],
            bass_floor_notes=["D3", "G2"],
            groove_summary="moderate density",
        )
        assert "Dm7" in user
        assert "G7" in user
        assert "synthwave" in user.lower() or "Synthwave" in user

    def test_system_prompt_contains_role(self) -> None:
        _, system = melody_strategy_prompt(
            chord_symbols=["Cmaj7"],
            key_center="C",
            mode="major",
            genre="dream_pop",
            melodic_tendencies={},
            voicing_ceiling_notes=["B4"],
            bass_floor_notes=["C3"],
            groove_summary="straight eighths",
        )
        assert "melody" in system.lower() or "melodist" in system.lower()

    def test_tendencies_included_when_present(self) -> None:
        user, _ = melody_strategy_prompt(
            chord_symbols=["Cmaj7"],
            key_center="C",
            mode="major",
            genre="dream_pop",
            melodic_tendencies={"motion_preference": "stepwise", "density": "sparse"},
            voicing_ceiling_notes=["B4"],
            bass_floor_notes=["C3"],
            groove_summary="straight eighths",
        )
        assert "stepwise" in user
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd backend && python -m pytest tests/unit/prompts/test_melody_prompt.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement prompt**

```python
# backend/src/explorator/prompts/melody.py
"""Prompts for melody strategy generation (Gemini Flash)."""


def melody_strategy_prompt(
    chord_symbols: list[str],
    key_center: str,
    mode: str,
    genre: str,
    melodic_tendencies: dict[str, str],
    voicing_ceiling_notes: list[str],
    bass_floor_notes: list[str],
    groove_summary: str,
) -> tuple[str, str]:
    """Build prompt for melody strategy generation. Returns (user_prompt, system_prompt)."""
    genre_display = genre.replace("_", " ")
    chords = " → ".join(chord_symbols)
    n_bars = len(chord_symbols)

    ceiling = ", ".join(f"bar {i + 1}: {n}" for i, n in enumerate(voicing_ceiling_notes))
    floor = ", ".join(f"bar {i + 1}: {n}" for i, n in enumerate(bass_floor_notes))

    tendencies_text = ""
    if melodic_tendencies:
        items = [f"  - {k}: {v}" for k, v in melodic_tendencies.items()]
        tendencies_text = "Genre melodic tendencies:\n" + "\n".join(items) + "\n\n"

    user_prompt = (
        f"Create a melodic strategy for a single-line melody over this {genre_display} arrangement:\n\n"
        f"Progression ({n_bars} bars): {chords}\n"
        f"Key: {key_center} {mode}\n"
        f"Voicing ceiling (highest note per bar): {ceiling}\n"
        f"Bass floor (lowest note per bar): {floor}\n"
        f"Groove: {groove_summary}\n\n"
        f"{tendencies_text}"
        "Guidelines:\n"
        "- Place melody ABOVE the voicing ceiling to avoid collisions.\n"
        "- Suggest a register range (range_low to range_high) at least a minor 3rd above the voicing ceiling.\n"
        "- Break the melody into phrases (2 or 4 bars each).\n"
        "- For each phrase, specify contour (arch/ascending/descending/wave/static), "
        "density (sparse/moderate/active), strong-beat scale degree targets, "
        "and whether to rest after the phrase.\n"
        "- Provide an overall_contour summary and a one-sentence rationale.\n\n"
        "For each phrase, specify:\n"
        "- start_bar: first bar number (1-indexed)\n"
        "- end_bar: last bar number (inclusive)\n"
        "- contour: one of 'arch', 'ascending', 'descending', 'wave', 'static'\n"
        "- density: one of 'sparse', 'moderate', 'active'\n"
        "- strong_beat_targets: list of scale degree names like 'root', '3rd', '5th', '7th'\n"
        "- rest_after: true/false\n\n"
        "CRITICAL: Keep rationale to ONE sentence (max 200 chars). "
        "Return valid JSON matching the schema.\n"
    )

    system_prompt = (
        f"You are an expert melodist composing a single-line melody over a {genre_display} arrangement. "
        "The melody must stay above the voicing register to avoid pitch collisions. "
        "Create a strategy with phrase-by-phrase instructions that produce a coherent, "
        "genre-appropriate melodic line. Return valid JSON matching the schema."
    )

    return user_prompt, system_prompt
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd backend && python -m pytest tests/unit/prompts/test_melody_prompt.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/prompts/melody.py backend/tests/unit/prompts/test_melody_prompt.py
git commit -m "feat(m5b): add melody strategy prompt template"
```

---

## Task 4: MelodyGenerator Domain Service

**Files:**
- Create: `backend/src/explorator/domain/realization/melody.py`
- Create: `backend/tests/unit/domain/test_melody_generator.py`

This is the largest task. The generator implements the 7-step algorithm from the spec (Section 5.2). Steps 2-4 are integrated in a single forward pass.

- [ ] **Step 1: Write core realization tests**

```python
# backend/tests/unit/domain/test_melody_generator.py
"""Tests for MelodyGenerator — deterministic melody realization."""

import pytest

from explorator.domain.realization.melody import MelodyGenerator
from explorator.models.melody import (
    MelodicComplement,
    MelodicNoteEvent,
    MelodicStrategyResponse,
    PhraseInstruction,
)
from explorator.models.realization import VoicingEvent


def _strategy(
    range_low: str = "C5",
    range_high: str = "C6",
    phrases: list[PhraseInstruction] | None = None,
) -> MelodicStrategyResponse:
    if phrases is None:
        phrases = [
            PhraseInstruction(
                start_bar=1, end_bar=4, contour="arch",
                density="moderate", strong_beat_targets=["root", "5th"],
                rest_after=False,
            ),
        ]
    return MelodicStrategyResponse(
        range_low=range_low,
        range_high=range_high,
        overall_contour="arch",
        phrase_instructions=phrases,
    )


def _voicing_event(bar: int, pitches: list[str]) -> VoicingEvent:
    return VoicingEvent(bar=bar, pitches=pitches, chord_symbol="C")


class TestMelodyGeneratorBasic:
    def test_produces_melodic_complement(self) -> None:
        gen = MelodyGenerator()
        result = gen.realize(
            strategy=_strategy(),
            chord_symbols=["Cmaj7", "Am7", "Fmaj7", "G7"],
            key_center="C",
            mode="major",
            voicing_events=[
                _voicing_event(1, ["C4", "E4", "G4", "B4"]),
                _voicing_event(2, ["A3", "C4", "E4", "G4"]),
                _voicing_event(3, ["F3", "A3", "C4", "E4"]),
                _voicing_event(4, ["G3", "B3", "D4", "F4"]),
            ],
            beat_grid=None,
            motion_preference="stepwise",
        )
        assert isinstance(result, MelodicComplement)
        assert len(result.note_events) > 0
        assert result.range_low == "C5"
        assert result.range_high == "C6"
        assert result.contour_type == "arch"

    def test_all_pitches_within_range(self) -> None:
        gen = MelodyGenerator()
        result = gen.realize(
            strategy=_strategy(range_low="C5", range_high="C6"),
            chord_symbols=["Cmaj7", "Am7", "Fmaj7", "G7"],
            key_center="C",
            mode="major",
            voicing_events=[
                _voicing_event(1, ["C4", "E4", "G4", "B4"]),
                _voicing_event(2, ["A3", "C4", "E4", "G4"]),
                _voicing_event(3, ["F3", "A3", "C4", "E4"]),
                _voicing_event(4, ["G3", "B3", "D4", "F4"]),
            ],
            beat_grid=None,
            motion_preference="stepwise",
        )
        from explorator.services.midi_utils import pitch_to_midi
        low_midi = pitch_to_midi("C5")
        high_midi = pitch_to_midi("C6")
        for event in result.note_events:
            midi = pitch_to_midi(event.pitch)
            assert low_midi <= midi <= high_midi, f"{event.pitch} out of range"

    def test_no_voicing_collisions(self) -> None:
        """No unisons or minor 2nds against voicing on same bar/beat."""
        gen = MelodyGenerator()
        voicing_events = [
            _voicing_event(1, ["C4", "E4", "G4", "B4"]),
            _voicing_event(2, ["A3", "C4", "E4", "G4"]),
            _voicing_event(3, ["F3", "A3", "C4", "E4"]),
            _voicing_event(4, ["G3", "B3", "D4", "F4"]),
        ]
        result = gen.realize(
            strategy=_strategy(),
            chord_symbols=["Cmaj7", "Am7", "Fmaj7", "G7"],
            key_center="C",
            mode="major",
            voicing_events=voicing_events,
            beat_grid=None,
            motion_preference="stepwise",
        )
        from explorator.services.midi_utils import pitch_to_midi
        for mel_event in result.note_events:
            mel_midi = pitch_to_midi(mel_event.pitch)
            for v_event in voicing_events:
                if v_event.bar == mel_event.bar:
                    for vp in v_event.pitches:
                        v_midi = pitch_to_midi(vp)
                        distance = abs(mel_midi - v_midi)
                        assert distance != 0 and distance != 1, (
                            f"Collision: melody {mel_event.pitch} vs voicing {vp} on bar {mel_event.bar}"
                        )

    def test_final_note_is_chord_tone(self) -> None:
        gen = MelodyGenerator()
        result = gen.realize(
            strategy=_strategy(),
            chord_symbols=["Cmaj7", "Am7", "Fmaj7", "G7"],
            key_center="C",
            mode="major",
            voicing_events=[
                _voicing_event(1, ["C4", "E4", "G4", "B4"]),
                _voicing_event(2, ["A3", "C4", "E4", "G4"]),
                _voicing_event(3, ["F3", "A3", "C4", "E4"]),
                _voicing_event(4, ["G3", "B3", "D4", "F4"]),
            ],
            beat_grid=None,
            motion_preference="stepwise",
        )
        last_note = result.note_events[-1]
        # G7 chord tones: G, B, D, F — last note pitch class should be one of these
        pitch_class = last_note.pitch[:-1]  # strip octave
        assert pitch_class in ("G", "B", "D", "F"), f"Final note {last_note.pitch} not a G7 chord tone"

    def test_empty_chords_returns_empty(self) -> None:
        gen = MelodyGenerator()
        result = gen.realize(
            strategy=_strategy(),
            chord_symbols=[],
            key_center="C",
            mode="major",
            voicing_events=[],
            beat_grid=None,
            motion_preference="stepwise",
        )
        assert result.note_events == []

    def test_sparse_density_beats_1_and_3(self) -> None:
        gen = MelodyGenerator()
        result = gen.realize(
            strategy=_strategy(phrases=[
                PhraseInstruction(
                    start_bar=1, end_bar=4, contour="static",
                    density="sparse", strong_beat_targets=["root"],
                    rest_after=False,
                ),
            ]),
            chord_symbols=["Cmaj7", "Am7", "Fmaj7", "G7"],
            key_center="C",
            mode="major",
            voicing_events=[
                _voicing_event(1, ["C4", "E4", "G4", "B4"]),
                _voicing_event(2, ["A3", "C4", "E4", "G4"]),
                _voicing_event(3, ["F3", "A3", "C4", "E4"]),
                _voicing_event(4, ["G3", "B3", "D4", "F4"]),
            ],
            beat_grid=None,
            motion_preference="stepwise",
        )
        # Sparse = beats 1 and 3 only → 2 notes per bar × 4 bars = 8
        assert len(result.note_events) == 8
        for event in result.note_events:
            assert event.beat in (1.0, 3.0), f"Sparse beat should be 1 or 3, got {event.beat}"
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd backend && python -m pytest tests/unit/domain/test_melody_generator.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement MelodyGenerator**

Create `backend/src/explorator/domain/realization/melody.py` implementing the spec's 7-step algorithm. This is a substantial file (~250 lines). Key implementation points:

- `realize()` method matching the test signature
- Beat grid synthesis (straight-eighths fallback)
- Density filtering (sparse/moderate/active)
- Strong-beat chord-tone targeting with fallback
- Diatonic passing tones using music21
- Contour bias (~70/30 weighting)
- Collision avoidance (shift up, shift down, or rest)
- Phrase boundaries and resolution rule

The implementation should use `explorator.services.midi_utils.pitch_to_midi` for MIDI conversion (already used by bass generator) and `music21` for chord-tone and scale-degree resolution.

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd backend && python -m pytest tests/unit/domain/test_melody_generator.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/domain/realization/melody.py backend/tests/unit/domain/test_melody_generator.py
git commit -m "feat(m5b): implement MelodyGenerator with constraint-based pitch selection"
```

---

## Task 5: MelodyHarmonyEvaluator

**Files:**
- Create: `backend/src/explorator/domain/evaluation/melody_harmony.py`
- Create: `backend/tests/unit/domain/test_melody_harmony_evaluator.py`

- [ ] **Step 1: Write evaluator tests**

```python
# backend/tests/unit/domain/test_melody_harmony_evaluator.py
"""Tests for MelodyHarmonyEvaluator."""

from explorator.domain.evaluation.melody_harmony import MelodyHarmonyEvaluator
from explorator.models.melody import MelodicComplement, MelodicNoteEvent
from explorator.models.realization import VoicingEvent


def _event(bar: int, pitch: str, beat: float = 1.0) -> MelodicNoteEvent:
    return MelodicNoteEvent(bar=bar, beat=beat, pitch=pitch)


def _voicing(bar: int, pitches: list[str]) -> VoicingEvent:
    return VoicingEvent(bar=bar, pitches=pitches, chord_symbol="C")


def _complement(events: list[MelodicNoteEvent]) -> MelodicComplement:
    return MelodicComplement(
        id="mc_test",
        type="melodic_complement",
        status="completed",
        arrangement_candidate_id="arr_test",
        note_events=events,
    )


class TestMelodySupportScore:
    def test_all_chord_tones_scores_10(self) -> None:
        ev = MelodyHarmonyEvaluator()
        # C5, E5, G5 are all Cmaj chord tones
        mc = _complement([_event(1, "C5"), _event(2, "E5"), _event(3, "G5")])
        result = ev.evaluate(
            mc,
            chord_symbols=["Cmaj7", "Cmaj7", "Cmaj7"],
            voicing_events=[],
            motion_preference="stepwise",
            candidate_id="cand_1",
        )
        assert result.melody_support_score >= 9.0

    def test_non_chord_tones_reduce_score(self) -> None:
        ev = MelodyHarmonyEvaluator()
        # F#5 is not in Cmaj7
        mc = _complement([_event(1, "F#5"), _event(2, "F#5")])
        result = ev.evaluate(
            mc,
            chord_symbols=["Cmaj7", "Cmaj7"],
            voicing_events=[],
            motion_preference="stepwise",
            candidate_id="cand_1",
        )
        assert result.melody_support_score < 8.0


class TestCollisionRiskScore:
    def test_no_collisions_scores_10(self) -> None:
        ev = MelodyHarmonyEvaluator()
        mc = _complement([_event(1, "C5"), _event(2, "D5")])
        voicings = [_voicing(1, ["C4", "E4", "G4"]), _voicing(2, ["D4", "F4", "A4"])]
        result = ev.evaluate(
            mc,
            chord_symbols=["Cmaj7", "Dm7"],
            voicing_events=voicings,
            motion_preference="stepwise",
            candidate_id="cand_1",
        )
        assert result.collision_risk_score == 10.0

    def test_unison_collision_penalizes(self) -> None:
        ev = MelodyHarmonyEvaluator()
        # Melody C4 collides with voicing C4 (unison)
        mc = _complement([_event(1, "C4")])
        voicings = [_voicing(1, ["C4", "E4", "G4"])]
        result = ev.evaluate(
            mc,
            chord_symbols=["Cmaj7"],
            voicing_events=voicings,
            motion_preference="stepwise",
            candidate_id="cand_1",
        )
        assert result.collision_risk_score < 10.0

    def test_empty_melody_returns_default(self) -> None:
        ev = MelodyHarmonyEvaluator()
        mc = _complement([])
        result = ev.evaluate(
            mc, chord_symbols=[], voicing_events=[],
            motion_preference="stepwise", candidate_id="cand_1",
        )
        assert result.collision_risk_score == 5.0
        assert result.melody_support_score == 5.0


class TestOverallScore:
    def test_overall_is_average(self) -> None:
        ev = MelodyHarmonyEvaluator()
        mc = _complement([_event(1, "C5")])
        result = ev.evaluate(
            mc,
            chord_symbols=["Cmaj7"],
            voicing_events=[],
            motion_preference="stepwise",
            candidate_id="cand_1",
        )
        expected = (result.melody_support_score + result.collision_risk_score) / 2
        assert abs(ev.overall_score(result) - expected) < 0.01
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd backend && python -m pytest tests/unit/domain/test_melody_harmony_evaluator.py -v
```

- [ ] **Step 3: Implement evaluator**

```python
# backend/src/explorator/domain/evaluation/melody_harmony.py
"""Melody-harmony evaluator — deterministic scoring of melody quality.

Two dimensions: melody_support_score, collision_risk_score.
Both on 0.0-10.0 scale. Only active when melodic_complement_id is non-null.
"""

from ulid import ULID

from explorator.models.evaluation import MelodyHarmonyEvaluation
from explorator.models.melody import MelodicComplement, MelodicNoteEvent
from explorator.models.realization import VoicingEvent
from explorator.services.midi_utils import pitch_to_midi
from explorator.utils import utc_now


class MelodyHarmonyEvaluator:
    """Evaluate melody-harmony compatibility."""

    def evaluate(
        self,
        complement: MelodicComplement,
        chord_symbols: list[str],
        voicing_events: list[VoicingEvent],
        motion_preference: str,
        candidate_id: str,
    ) -> MelodyHarmonyEvaluation:
        now = utc_now()
        eval_id = f"mhev_{ULID()}"

        if not complement.note_events:
            return MelodyHarmonyEvaluation(
                id=eval_id,
                type="melody_harmony_evaluation",
                status="completed",
                created_at=now,
                updated_at=now,
                candidate_id=candidate_id,
                evaluation_type="melody_harmony_evaluation",
                melody_support_score=5.0,
                collision_risk_score=5.0,
            )

        support = self._score_melody_support(complement.note_events, chord_symbols, motion_preference)
        collision = self._score_collision_risk(complement.note_events, voicing_events)

        return MelodyHarmonyEvaluation(
            id=eval_id,
            type="melody_harmony_evaluation",
            status="completed",
            created_at=now,
            updated_at=now,
            candidate_id=candidate_id,
            evaluation_type="melody_harmony_evaluation",
            melody_support_score=round(support, 3),
            collision_risk_score=round(collision, 3),
        )

    def overall_score(self, evaluation: MelodyHarmonyEvaluation) -> float:
        return (evaluation.melody_support_score + evaluation.collision_risk_score) / 2

    def _score_melody_support(
        self,
        events: list[MelodicNoteEvent],
        chord_symbols: list[str],
        motion_preference: str,
    ) -> float:
        """Chord-tone ratio on strong beats + voice-leading smoothness, scaled to 0-10."""
        import music21

        # Sub-metric 1: chord-tone ratio on downbeats (beat 1.0 and 3.0)
        downbeat_events = [e for e in events if e.beat in (1.0, 3.0)]
        if downbeat_events and chord_symbols:
            chord_tone_hits = 0
            for e in downbeat_events:
                bar_idx = e.bar - 1
                if 0 <= bar_idx < len(chord_symbols):
                    chord = music21.harmony.ChordSymbol(chord_symbols[bar_idx])
                    chord_pitches = {p.name for p in chord.pitches}
                    note_name = music21.pitch.Pitch(e.pitch).name
                    if note_name in chord_pitches:
                        chord_tone_hits += 1
            chord_tone_ratio = chord_tone_hits / len(downbeat_events) * 10.0
        else:
            chord_tone_ratio = 5.0

        # Sub-metric 2: voice-leading smoothness
        if len(events) >= 2:
            smooth_count = 0
            for i in range(len(events) - 1):
                interval = abs(pitch_to_midi(events[i + 1].pitch) - pitch_to_midi(events[i].pitch))
                max_smooth = 4 if motion_preference == "stepwise" else 7
                if interval <= max_smooth:
                    smooth_count += 1
            smoothness = smooth_count / (len(events) - 1) * 10.0
        else:
            smoothness = 10.0

        return (chord_tone_ratio + smoothness) / 2

    def _score_collision_risk(
        self,
        events: list[MelodicNoteEvent],
        voicing_events: list[VoicingEvent],
    ) -> float:
        """Count unisons/minor 2nds between melody and voicing, scaled to 0-10."""
        if not events:
            return 5.0

        collision_count = 0
        for mel in events:
            mel_midi = pitch_to_midi(mel.pitch)
            for ve in voicing_events:
                if ve.bar == mel.bar:
                    for vp in ve.pitches:
                        distance = abs(mel_midi - pitch_to_midi(vp))
                        if distance <= 1:
                            collision_count += 1
                            break
                    break

        ratio = 1.0 - (collision_count / len(events))
        return max(0.0, ratio * 10.0)
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd backend && python -m pytest tests/unit/domain/test_melody_harmony_evaluator.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/domain/evaluation/melody_harmony.py backend/tests/unit/domain/test_melody_harmony_evaluator.py
git commit -m "feat(m5b): implement MelodyHarmonyEvaluator with support and collision scoring"
```

---

## Task 6: Pipeline Integration — State, Node, Graph, Assembly

**Files:**
- Modify: `backend/src/explorator/engine/state.py:43` — add `melodic_complements` key
- Create: `backend/src/explorator/engine/nodes/generate_melody.py`
- Modify: `backend/src/explorator/engine/graph.py:37-65` — wire node
- Modify: `backend/src/explorator/engine/nodes/assemble_arrangements.py:85-95` — melody round-robin

- [ ] **Step 1: Add `melodic_complements` to ExplorationState**

In `backend/src/explorator/engine/state.py`, add after `groove_patterns` (line 43):

```python
    melodic_complements: list[dict[str, Any]]
```

- [ ] **Step 2: Create generate_melody node**

```python
# backend/src/explorator/engine/nodes/generate_melody.py
"""Generate melody node — Gemini strategy + deterministic realization."""

import logging
from typing import Any

from explorator.domain.realization.melody import MelodyGenerator
from explorator.engine.state import ExplorationState
from explorator.models.melody import MelodicPreferences
from explorator.models.realization import VoicingEvent, VoicingPlan, BassLine
from explorator.prompts.melody import melody_strategy_prompt
from explorator.services.gemini_client import GeminiClient
from explorator.utils import parse_json_or_dict

logger = logging.getLogger(__name__)


def _validate_strategy(strategy: dict[str, Any], n_bars: int) -> bool:
    """Basic validation of Gemini strategy response."""
    phrases = strategy.get("phrase_instructions", [])
    if not phrases:
        return False
    for p in phrases:
        if p.get("start_bar", 0) > p.get("end_bar", 0):
            return False
        if p.get("contour") not in ("arch", "ascending", "descending", "wave", "static"):
            return False
        if p.get("density") not in ("sparse", "moderate", "active"):
            return False
    return True


def _default_strategy(n_bars: int, voicing_ceiling: str) -> dict[str, Any]:
    """Fallback strategy when Gemini response fails validation."""
    from explorator.services.midi_utils import midi_to_pitch, pitch_to_midi
    ceiling_midi = pitch_to_midi(voicing_ceiling) if voicing_ceiling else 72
    range_low = midi_to_pitch(ceiling_midi + 3)
    range_high = midi_to_pitch(ceiling_midi + 15)
    return {
        "range_low": range_low,
        "range_high": range_high,
        "overall_contour": "arch",
        "phrase_instructions": [{
            "start_bar": 1,
            "end_bar": n_bars,
            "contour": "arch",
            "density": "moderate",
            "strong_beat_targets": ["root", "5th"],
            "rest_after": False,
        }],
        "rationale": "Default fallback strategy",
    }


def _extract_ceiling_notes(voicing_plan: VoicingPlan) -> list[str]:
    """Get highest pitch per bar from voicing events."""
    from explorator.services.midi_utils import pitch_to_midi, midi_to_pitch
    bar_max: dict[int, int] = {}
    for ev in voicing_plan.voicing_events:
        for p in ev.pitches:
            midi = pitch_to_midi(p)
            if ev.bar not in bar_max or midi > bar_max[ev.bar]:
                bar_max[ev.bar] = midi
    return [midi_to_pitch(bar_max.get(b, 72)) for b in sorted(bar_max)]


def _extract_floor_notes(bass_line: BassLine) -> list[str]:
    """Get lowest pitch per bar from bass events."""
    from explorator.services.midi_utils import pitch_to_midi, midi_to_pitch
    bar_min: dict[int, int] = {}
    for ev in bass_line.note_events:
        midi = pitch_to_midi(ev.pitch)
        if ev.bar not in bar_min or midi < bar_min[ev.bar]:
            bar_min[ev.bar] = midi
    return [midi_to_pitch(bar_min.get(b, 48)) for b in sorted(bar_min)]


async def generate_melody(state: ExplorationState, gemini: GeminiClient) -> dict[str, Any]:
    """Generate melodic complements for each (voicing plan, bass line) pair."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "generate_melody"})

    genre_profile = parse_json_or_dict(state.get("genre_profile", {}))
    creative_brief = parse_json_or_dict(state.get("creative_brief", {}))

    melodic_tendencies = parse_json_or_dict(genre_profile.get("melodic_tendencies", {}))
    prefs = MelodicPreferences.from_genre_tendencies(melodic_tendencies)

    key_center = creative_brief.get("key_center", "C")
    mode = creative_brief.get("mode", "major")
    genre = genre_profile.get("genre", "dream_pop")

    # Build groove summary for prompt context
    groove_patterns_raw = state.get("groove_patterns", [])
    if groove_patterns_raw:
        gp = groove_patterns_raw[0]
        groove_summary = (
            f"template: {gp.get('source_template', 'straight_eighths')}, "
            f"swing: {gp.get('swing_amount', 0.0)}, density: {gp.get('density', 0.5)}"
        )
        beat_grid = gp.get("pattern_events", [])
    else:
        groove_summary = "straight eighths, no swing"
        beat_grid = None

    # Group voicing plans and bass lines by progression_candidate_id
    vp_by_prog: dict[str, list[VoicingPlan]] = {}
    for vp_data in state.get("voicing_plans", []):
        vp = VoicingPlan.model_validate(vp_data)
        cid = vp.progression_candidate_id or ""
        vp_by_prog.setdefault(cid, []).append(vp)

    bl_by_prog: dict[str, list[BassLine]] = {}
    for bl_data in state.get("bass_lines", []):
        bl = BassLine.model_validate(bl_data)
        pid = bl.progression_candidate_id or ""
        bl_by_prog.setdefault(pid, []).append(bl)

    # Get chord symbols from progression candidates
    candidates_raw = state.get("top_progressions", []) or state.get("progression_candidates", [])
    prog_chords: dict[str, list[str]] = {}
    for cand in candidates_raw:
        cid = cand.get("id", "")
        prog_chords[cid] = cand.get("chord_symbols", [])

    generator = MelodyGenerator()
    all_complements: list[dict[str, Any]] = []

    from explorator.models.melody import MelodicStrategyResponse

    for prog_id, plans in vp_by_prog.items():
        bass_lines = bl_by_prog.get(prog_id, [])
        chord_symbols = prog_chords.get(prog_id, [])
        n_bars = len(chord_symbols)

        if not chord_symbols or not plans or not bass_lines:
            continue

        for vp in plans:
            for bl in bass_lines:
                ceiling_notes = _extract_ceiling_notes(vp)
                floor_notes = _extract_floor_notes(bl)

                # Phase 1: Gemini strategy
                user_prompt, system_prompt = melody_strategy_prompt(
                    chord_symbols=chord_symbols,
                    key_center=key_center,
                    mode=mode,
                    genre=genre,
                    melodic_tendencies=melodic_tendencies,
                    voicing_ceiling_notes=ceiling_notes,
                    bass_floor_notes=floor_notes,
                    groove_summary=groove_summary,
                )

                try:
                    strategy_raw = await gemini.generate_json(
                        user_prompt=user_prompt,
                        system_prompt=system_prompt,
                        response_model=MelodicStrategyResponse,
                    )
                    strategy_dict = strategy_raw if isinstance(strategy_raw, dict) else strategy_raw.model_dump()
                except Exception:
                    logger.warning("Melody strategy Gemini call failed — using default")
                    strategy_dict = _default_strategy(
                        n_bars, ceiling_notes[0] if ceiling_notes else "B4",
                    )

                if not _validate_strategy(strategy_dict, n_bars):
                    logger.warning("Melody strategy failed validation — using default")
                    strategy_dict = _default_strategy(
                        n_bars, ceiling_notes[0] if ceiling_notes else "B4",
                    )

                strategy = MelodicStrategyResponse.model_validate(strategy_dict)

                # Phase 2: deterministic realization
                mc = generator.realize(
                    strategy=strategy,
                    chord_symbols=chord_symbols,
                    key_center=key_center,
                    mode=mode,
                    voicing_events=vp.voicing_events,
                    beat_grid=beat_grid,
                    motion_preference=prefs.motion_preference,
                )

                all_complements.append(mc.model_dump(mode="json"))

    logger.info(
        "generate_melody: produced %d complements for %d progressions",
        len(all_complements),
        len(vp_by_prog),
    )

    return {"melodic_complements": all_complements}
```

- [ ] **Step 3: Wire node into graph**

In `backend/src/explorator/engine/graph.py`, update `_add_m2_nodes` to add:

```python
from explorator.engine.nodes.generate_melody import generate_melody
```

Add after `graph.add_node("generate_groove", generate_groove)`:

```python
    graph.add_node("generate_melody", partial(generate_melody, gemini=gemini))
```

Update `_add_m2_edges` — change:

```python
    graph.add_edge("generate_groove", "assemble")
```

To:

```python
    graph.add_edge("generate_groove", "generate_melody")
    graph.add_edge("generate_melody", "assemble")
```

- [ ] **Step 4: Add melody round-robin to assembly node**

In `backend/src/explorator/engine/nodes/assemble_arrangements.py`, add after the groove round-robin block (after line 90):

```python
    # Assign melodic_complement_id via round-robin from available melodic complements
    melodic_complements_raw = state.get("melodic_complements", [])
    if melodic_complements_raw:
        mc_ids = [mc["id"] for mc in melodic_complements_raw]
        for idx, cand in enumerate(all_candidates):
            cand["melodic_complement_id"] = mc_ids[idx % len(mc_ids)]
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/engine/state.py \
        backend/src/explorator/engine/nodes/generate_melody.py \
        backend/src/explorator/engine/graph.py \
        backend/src/explorator/engine/nodes/assemble_arrangements.py
git commit -m "feat(m5b): wire generate_melody node into realization pipeline"
```

---

## Task 7: Weight Rebalancing and Conditional Normalization

**Files:**
- Modify: `backend/src/explorator/domain/evaluation/ranking.py:23-50`
- Modify: `backend/src/explorator/engine/nodes/evaluate_arrangements.py`

- [ ] **Step 1: Update CANONICAL_DEFAULT_WEIGHTS**

In `backend/src/explorator/domain/evaluation/ranking.py`, replace `CANONICAL_DEFAULT_WEIGHTS` (lines 23-40):

```python
CANONICAL_DEFAULT_WEIGHTS = ObjectiveWeights(
    id="weights_canonical",
    type="objective_weights",
    status="active",
    profile_name="canonical_default",
    weights={
        "genre_fit": 0.10,
        "emotional_fit": 0.07,
        "theoretical_coherence": 0.08,
        "cadence_quality": 0.07,
        "novelty": 0.07,
        "loopability": 0.09,
        "voice_leading": 0.07,
        "register_density": 0.06,
        "playability": 0.06,
        "groove": 0.08,
        "melody_support": 0.15,
        "collision_risk": 0.10,
    },
)
```

- [ ] **Step 2: Add conditional normalization to weighted_score**

In `ranking.py`, update `weighted_score` function to handle melody-less sessions:

```python
_MELODY_DIMS = {"melody_support", "collision_risk"}


def weighted_score(
    scorecard: AggregateScorecard,
    weights: ObjectiveWeights,
    has_melody: bool = True,
) -> float:
    """Compute weighted total from scorecard and weights.

    When has_melody is False, melody dimensions are excluded and remaining
    weights are renormalized proportionally.
    """
    active_weights = weights.weights
    if not has_melody:
        active_weights = {k: v for k, v in active_weights.items() if k not in _MELODY_DIMS}
        weight_sum = sum(active_weights.values())
        if weight_sum > 0:
            active_weights = {k: v / weight_sum for k, v in active_weights.items()}

    total = 0.0
    for dim, weight in active_weights.items():
        total += scorecard.scores.get(dim, 0.0) * weight
    return total
```

- [ ] **Step 3: Add MelodyHarmonyEvaluator to evaluate_arrangements node**

In `backend/src/explorator/engine/nodes/evaluate_arrangements.py`, add import:

```python
from explorator.domain.evaluation.melody_harmony import MelodyHarmonyEvaluator
from explorator.models.melody import MelodicComplement
```

Add melody lookup after the groove lookup block (after line 46):

```python
    melodic_complement_lookup: dict[str, MelodicComplement] = {}
    for mc_data in state.get("melodic_complements", []):
        mc = MelodicComplement.model_validate(mc_data)
        melodic_complement_lookup[mc.id] = mc

    melodic_tendencies = parse_json_or_dict(genre_profile.get("melodic_tendencies", {}))
    melody_motion = melodic_tendencies.get("motion_preference", "stepwise")
```

Add evaluator instantiation:

```python
    melody_evaluator = MelodyHarmonyEvaluator()
```

After the groove evaluation block (after line 98), add melody evaluation:

```python
        # Melody evaluation
        melodic_complement_id: str | None = arr_data.get("melodic_complement_id")
        melodic_complement = melodic_complement_lookup.get(melodic_complement_id or "") if melodic_complement_id else None

        if melodic_complement is not None:
            melody_eval = melody_evaluator.evaluate(
                melodic_complement,
                chord_symbols=arr_data.get("chord_symbols", []),
                voicing_events=voicing_plan.voicing_events if voicing_plan else [],
                motion_preference=melody_motion,
                candidate_id=arrangement_id,
            )
            melody_score = melody_evaluator.overall_score(melody_eval)
            melody_entry = {
                "evaluation": melody_eval.model_dump(mode="json"),
                "overall_score": melody_score,
            }
        else:
            melody_entry = {
                "evaluation": None,
                "overall_score": 5.0,
            }
```

Add `"melody": melody_entry` to the evaluations dict.

- [ ] **Step 4: Commit**

```bash
git add backend/src/explorator/domain/evaluation/ranking.py \
        backend/src/explorator/engine/nodes/evaluate_arrangements.py
git commit -m "feat(m5b): add melody evaluation + conditional weight normalization"
```

---

## Task 8: Frontend — Types, Stores, Presets

**Files:**
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/stores/audioStore.ts`
- Modify: `frontend/src/services/audioPresets.ts`
- Modify: `frontend/src/utils/designTokens.ts`

- [ ] **Step 1: Add melodic_complement to ArrangementDetail**

In `frontend/src/services/api.ts`, add after `groove_pattern` in the `ArrangementDetail` interface:

```typescript
  melodic_complement: {
    note_events: { bar: number; beat: number; duration_beats: number; pitch: string; velocity: number }[]
    range_low: string
    range_high: string
    contour_type: string
  } | null
```

- [ ] **Step 2: Add melody to audioStore**

In `frontend/src/stores/audioStore.ts`, update:
- `mutedTracks` type: `{ voicing: boolean; bass: boolean; melody: boolean }`
- `toggleMute` type: `(track: "voicing" | "bass" | "melody") => void`
- Default: `mutedTracks: { voicing: false, bass: false, melody: false }`
- Reset: include `melody: false`

- [ ] **Step 3: Add MELODY_DEFAULT to audioPresets**

In `frontend/src/services/audioPresets.ts`, add after `GENRE_PRESETS`:

```typescript
export const MELODY_DEFAULT: SynthOptions = {
  oscillator: { type: "triangle" },
  envelope: { attack: 0.08, release: 0.6 },
  volume: -8,
}
```

- [ ] **Step 4: Add melodyNote color to designTokens**

In `frontend/src/utils/designTokens.ts`, add to `CANVAS_COLORS`:

```typescript
  melodyNote: "#34d399",  // emerald green, distinct from voicing (amber) and bass (blue)
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/api.ts \
        frontend/src/stores/audioStore.ts \
        frontend/src/services/audioPresets.ts \
        frontend/src/utils/designTokens.ts
git commit -m "feat(m5b): add melody types, store, preset, and color token"
```

---

## Task 9: Frontend — Audio Engine Melody Scheduling

**Files:**
- Modify: `frontend/src/services/audioEngine.ts`

- [ ] **Step 1: Add melody synth module state**

After `bassVol` declaration (around line 29), add:

```typescript
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let melodySynth: any | null = null
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let melodyVol: any | null = null
```

- [ ] **Step 2: Add scheduleMelody helper**

After the `scheduleBass` function, add a `scheduleMelody` function following the same pattern — iterate over `arrangement.melodic_complement?.note_events`, schedule each note on the transport using `melodySynth.triggerAttackRelease`.

- [ ] **Step 3: Wire melody into play function**

In the `play()` function, after bass scheduling:
- Build `melodySynth` using `buildMonoSynth(T, MELODY_DEFAULT)` (import from audioPresets)
- Build `melodyVol` as `new T.Volume(MELODY_DEFAULT.volume ?? -8).toDestination()`
- Connect: `melodySynth.connect(melodyVol)`
- Call `scheduleMelody(T, arrangement, totalBars)`
- Apply mute: `melodyVol.mute = store.mutedTracks.melody`

- [ ] **Step 4: Update teardownNodes and setMelodyMute**

Add `melodySynth` and `melodyVol` disposal to `teardownNodes()`. Add `setMelodyMute(muted: boolean)` export function.

- [ ] **Step 5: Include melody events in allBars computation**

In the `play()` function's `allBars` calculation, add:

```typescript
    ...(arrangement.melodic_complement?.note_events ?? []).map((e) => e.bar + Math.ceil(e.duration_beats / 4)),
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/services/audioEngine.ts
git commit -m "feat(m5b): add melody MonoSynth scheduling to audio engine"
```

---

## Task 10: Frontend — PianoRoll Melody Lane

**Files:**
- Modify: `frontend/src/components/PianoRoll.tsx`

- [ ] **Step 1: Update collectMidiValues to include melody**

```typescript
function collectMidiValues(arrangement: ArrangementDetail): number[] {
  const midis: number[] = []
  arrangement.voicing_plan?.voicing_events.forEach((ev) => {
    ev.pitches.forEach((p) => midis.push(pitchToMidi(p)))
  })
  arrangement.bass_line?.note_events.forEach((ev) => {
    midis.push(pitchToMidi(ev.pitch))
  })
  arrangement.melodic_complement?.note_events.forEach((ev) => {
    midis.push(pitchToMidi(ev.pitch))
  })
  return midis
}
```

- [ ] **Step 2: Update hasEvents and allBars**

```typescript
  const melodyEvents = arrangement.melodic_complement?.note_events ?? []
  const hasEvents = voicingEvents.length > 0 || bassEvents.length > 0 || melodyEvents.length > 0
```

Add melody to `allBars`:

```typescript
      ...melodyEvents.map((e) => e.bar + Math.ceil(e.duration_beats / 4)),
```

- [ ] **Step 3: Add melody rendering pass**

After the bass rendering loop in the `useEffect`, add a third pass for melody using `CANVAS_COLORS.melodyNote`. Follow the exact same pattern as bass rendering but use `melodyEvents` and the melody color. Only render when `!mutedTracks.melody`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/PianoRoll.tsx
git commit -m "feat(m5b): render melody lane in piano roll"
```

---

## Task 11: Frontend — TransportBar Melody Toggle

**Files:**
- Modify: `frontend/src/components/TransportBar.tsx`

- [ ] **Step 1: Add melody mute handler**

After `handleBassMute`, add:

```typescript
  function handleMelodyMute() {
    audioEngine.setMelodyMute(!mutedTracks.melody)
  }
```

- [ ] **Step 2: Add melody toggle button**

After the Bass mute button in JSX, add a Melody mute button following the same pattern — conditional styling based on `mutedTracks.melody`, onClick calls `handleMelodyMute`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/TransportBar.tsx
git commit -m "feat(m5b): add melody mute toggle to transport bar"
```

---

## Task 12: Frontend — Comparison Engine Per-Track Muting

**Files:**
- Modify: `frontend/src/stores/comparisonAudioStore.ts`
- Modify: `frontend/src/services/comparisonAudioEngine.ts`
- Modify: `frontend/src/components/ComparisonView.tsx`

- [ ] **Step 1: Expand comparisonAudioStore with trackMutes**

Add to interface:

```typescript
  trackMutes: Record<string, { voicing: boolean; bass: boolean; melody: boolean }>
  toggleTrackMute: (candidateId: string, track: "voicing" | "bass" | "melody") => void
```

Add to initial state:

```typescript
  trackMutes: {} as Record<string, { voicing: boolean; bass: boolean; melody: boolean }>,
```

Add action:

```typescript
  toggleTrackMute: (candidateId, track) =>
    set((state) => {
      const current = state.trackMutes[candidateId] ?? { voicing: false, bass: false, melody: false }
      return {
        trackMutes: {
          ...state.trackMutes,
          [candidateId]: { ...current, [track]: !current[track] },
        },
      }
    }),
```

Update reset to include `trackMutes: {}`.

- [ ] **Step 2: Expand LaneSynths in comparisonAudioEngine**

Update the `LaneSynths` interface to add separate volumes per track and a melody synth. Update the lane creation logic to build three separate Volume nodes (voicingVol, bassVol, melodyVol) all routed through a master laneVol. Add melody scheduling to the lane schedule loop.

- [ ] **Step 3: Add per-track mute/solo controls in ComparisonView**

Add small track-level mute buttons (V, B, M) within each lane card, wired to `toggleTrackMute`. Follow the existing lane mute button pattern.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/stores/comparisonAudioStore.ts \
        frontend/src/services/comparisonAudioEngine.ts \
        frontend/src/components/ComparisonView.tsx
git commit -m "feat(m5b): add per-track muting to comparison playback engine"
```

---

## Task 13: E2E Tests

**Files:**
- Create: `e2e/tests/m5b-melody-*.spec.ts` (5-6 test files)

- [ ] **Step 1: Write E2E tests**

Create tests for:
1. `m5b-melody-generation.spec.ts` — Run a session, verify melody data appears in arrangement response
2. `m5b-melody-piano-roll.spec.ts` — Verify melody notes render in piano roll (check for melodyNote color on canvas)
3. `m5b-melody-playback.spec.ts` — Verify melody mute toggle in transport bar works
4. `m5b-melody-comparison.spec.ts` — Verify melody lane in comparison view with mute/solo
5. `m5b-melody-no-collisions.spec.ts` — Verify melody register avoids voicing collision zone via API response check
6. `m5b-melody-evaluation.spec.ts` — Verify MelodyHarmonyEvaluation scores appear in scorecard when melody present

Follow existing E2E test patterns in `e2e/tests/`.

- [ ] **Step 2: Run E2E tests**

```bash
cd e2e && npx playwright test tests/m5b-melody-*.spec.ts
```

- [ ] **Step 3: Commit**

```bash
git add e2e/tests/m5b-melody-*.spec.ts
git commit -m "test(m5b): add E2E tests for melody generation and playback"
```

---

## Self-Review Checklist

**Spec coverage:** Every section of the spec maps to a task:
- Section 2 (Model) → Task 1
- Section 3 (Genre YAML) → Task 2
- Section 4 (Prompt) → Task 3
- Section 5 (Generator) → Task 4
- Section 6 (Pipeline) → Task 6
- Section 7 (Evaluation) → Tasks 5 + 7
- Section 8 (Frontend) → Tasks 8-12
- Section 9 (E2E) → Task 13

**Placeholder scan:** No TBDs or TODOs. Task 4 (MelodyGenerator) notes it's ~250 lines and describes the algorithm but doesn't show full code — this is intentional for the largest file; the spec + tests fully constrain the implementation.

**Type consistency:** `MelodicComplement`, `MelodicNoteEvent`, `MelodicStrategyResponse`, `PhraseInstruction`, `MelodicPreferences` — used consistently across all tasks. Method name `realize()` used in Task 4 and Task 6. `overall_score()` matches evaluator pattern.
