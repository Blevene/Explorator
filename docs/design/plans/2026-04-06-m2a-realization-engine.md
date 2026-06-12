# M2a Realization Engine Implementation Plan


**Goal:** Implement voicing generation, bass line generation, and arrangement assembly so users can select M1 progressions and realize them into playable arrangements.

**Architecture:** A separate LangGraph `RealizationState` graph with 5 nodes (`load_context → plan_voicings → generate_bass → assemble → persist_realization`). Gemini Flash proposes voicing strategies; a deterministic engine (music21-backed) realizes named pitches. Bass lines are purely deterministic from genre templates. Arrangements are persisted to Neo4j with relationships.

**Tech Stack:** Python 3.12, LangGraph, Pydantic v2, music21, Gemini Flash, Neo4j, FastAPI, SSE

**Spec:** `docs/design/specs/2026-04-05-m2a-realization-engine-design.md`

---

## File Structure

### New Files

```
backend/src/explorator/
  models/
    realization.py              # UPDATE: Add VoicingEvent, BassNoteEvent, VoiceLeadingCheck,
                                #   VoicingPreferences, BassPreferences, VoicingStrategyResponse,
                                #   ChordVoicingInstruction, VariantConfig; update VoicingPlan/BassLine
  models/
    style.py                    # UPDATE: Add voicing_preferences, bass_preferences to GenreProfile
  domain/
    style/
      schema.py                 # UPDATE: Add voicing_preferences, bass_preferences to GenreProfileYAML
    realization/
      __init__.py
      voicing.py                # VoicingGenerator class
      bass.py                   # BassLineGenerator class
      assembly.py               # ArrangementAssembler class
  adapters/
    music21_adapter.py          # UPDATE: Add realize_voicing(), check_voice_leading()
  engine/
    realization_state.py        # RealizationState TypedDict
    realization_graph.py        # build_realization_graph()
    nodes/
      load_context.py           # load_context node
      plan_voicings.py          # plan_voicings node
      generate_bass.py          # generate_bass node
      assemble.py               # assemble node
      persist_realization.py    # persist_realization node
  graph/
    voicing_plan_repo.py
    bass_line_repo.py
    arrangement_candidate_repo.py
    arrangement_family_repo.py
  api/routes/
    realization_rounds.py       # POST /sessions/{id}/realization-rounds, GET arrangements
  prompts/
    voicing.py                  # plan_voicings prompt template
  data/genres/
    dream_pop.yaml              # UPDATE: Add voicing_preferences, bass_preferences
    synthwave.yaml              # UPDATE: same
    cinematic.yaml              # UPDATE: same

backend/tests/
  unit/
    models/
      test_realization.py       # UPDATE: Test new models
    domain/
      test_voicing_generator.py
      test_bass_generator.py
      test_assembly.py
    adapters/
      test_music21_voicing.py
    engine/
      test_realization_state.py
    prompts/
      test_voicing_prompt.py
  integration/
    test_realization_flow.py
```

---

## Task 1: Update Pydantic Models

**Files:**
- Modify: `backend/src/explorator/models/realization.py`
- Modify: `backend/src/explorator/models/style.py`
- Modify: `backend/src/explorator/domain/style/schema.py`
- Test: `backend/tests/unit/models/test_realization.py`

- [ ] **Step 1: Write failing tests for new models**

```python
# backend/tests/unit/models/test_realization.py — ADD these tests

from pydantic import ValidationError
import pytest

from explorator.models.realization import (
    BassLine,
    BassNoteEvent,
    BassPreferences,
    ChordVoicingInstruction,
    VariantConfig,
    VoiceLeadingCheck,
    VoicingEvent,
    VoicingPlan,
    VoicingPreferences,
    VoicingStrategyResponse,
)


class TestVoicingEvent:
    def test_minimal(self):
        e = VoicingEvent(bar=1, pitches=["C4", "E4", "G4"], chord_symbol="C")
        assert e.bar == 1
        assert e.beat == 1.0
        assert e.duration_beats == 4.0
        assert e.pitches == ["C4", "E4", "G4"]
        assert e.chord_symbol == "C"

    def test_full(self):
        e = VoicingEvent(
            bar=2, beat=2.0, duration_beats=2.0,
            pitches=["C3", "G3", "E4", "B4"], chord_symbol="Cmaj7",
        )
        assert e.beat == 2.0
        assert e.duration_beats == 2.0

    def test_missing_pitches_fails(self):
        with pytest.raises(ValidationError):
            VoicingEvent(bar=1, chord_symbol="C")


class TestBassNoteEvent:
    def test_minimal(self):
        e = BassNoteEvent(bar=1, pitch="C2")
        assert e.bar == 1
        assert e.pitch == "C2"
        assert e.beat == 1.0
        assert e.duration_beats == 1.0
        assert e.velocity == 80

    def test_full(self):
        e = BassNoteEvent(bar=3, beat=3.0, duration_beats=0.5, pitch="G2", velocity=100)
        assert e.velocity == 100


class TestVoiceLeadingCheck:
    def test_construction(self):
        vlc = VoiceLeadingCheck(
            common_tones=2,
            total_semitone_distance=5,
            max_leap=3,
            has_parallel_fifths=False,
            has_parallel_octaves=False,
        )
        assert vlc.common_tones == 2
        assert not vlc.has_parallel_fifths


class TestVoicingPreferences:
    def test_defaults(self):
        vp = VoicingPreferences()
        assert vp.default_voicing_type == "open"
        assert vp.default_register == "mid"
        assert vp.default_density == "medium"
        assert vp.default_voice_count == 4
        assert vp.favor_extensions is False
        assert "open" in vp.variant_voicing_types

    def test_custom(self):
        vp = VoicingPreferences(
            default_voicing_type="close",
            default_register="mid_high",
            variant_voicing_types=["close", "drop2"],
        )
        assert vp.default_voicing_type == "close"
        assert len(vp.variant_voicing_types) == 2

    def test_invalid_voicing_type_fails(self):
        with pytest.raises(ValidationError):
            VoicingPreferences(default_voicing_type="invalid")


class TestBassPreferences:
    def test_defaults(self):
        bp = BassPreferences()
        assert bp.default_bass_mode == "supportive"
        assert bp.default_register == "low"
        assert bp.rhythmic_density == "moderate"


class TestChordVoicingInstruction:
    def test_construction(self):
        cvi = ChordVoicingInstruction(
            chord_symbol="Cmaj7",
            voicing_type="open",
            target_register="mid_high",
            extensions_to_include=["7", "9"],
        )
        assert cvi.voicing_type == "open"
        assert cvi.doubling_notes is None

    def test_invalid_voicing_type_fails(self):
        with pytest.raises(ValidationError):
            ChordVoicingInstruction(
                chord_symbol="C",
                voicing_type="invalid",
                target_register="mid",
                extensions_to_include=[],
            )


class TestVoicingStrategyResponse:
    def test_construction(self):
        vsr = VoicingStrategyResponse(
            global_strategy="open spacing, favor 7ths",
            density_level="medium",
            voice_count=4,
            per_chord=[
                ChordVoicingInstruction(
                    chord_symbol="Cmaj7",
                    voicing_type="open",
                    target_register="mid_high",
                    extensions_to_include=["7"],
                ),
            ],
        )
        assert vsr.voice_count == 4
        assert len(vsr.per_chord) == 1


class TestVariantConfig:
    def test_construction(self):
        vc = VariantConfig(voicing_type="drop2")
        assert vc.voicing_type == "drop2"

    def test_invalid_fails(self):
        with pytest.raises(ValidationError):
            VariantConfig(voicing_type="bad")


class TestVoicingPlanTypedEvents:
    def test_voicing_plan_with_typed_events(self):
        events = [
            VoicingEvent(bar=1, pitches=["C4", "E4", "G4", "B4"], chord_symbol="Cmaj7"),
            VoicingEvent(bar=2, pitches=["A3", "C4", "E4", "G4"], chord_symbol="Am7"),
        ]
        vp = VoicingPlan(
            id="vp_01", type="voicing_plan", status="draft",
            voicing_events=events,
        )
        assert len(vp.voicing_events) == 2
        assert vp.voicing_events[0].pitches == ["C4", "E4", "G4", "B4"]


class TestBassLineTypedEvents:
    def test_bass_line_with_typed_events(self):
        events = [
            BassNoteEvent(bar=1, pitch="C2"),
            BassNoteEvent(bar=2, pitch="A1"),
        ]
        bl = BassLine(
            id="bl_01", type="bass_line", status="draft",
            note_events=events,
        )
        assert len(bl.note_events) == 2
        assert bl.note_events[0].pitch == "C2"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/models/test_realization.py -v --tb=short 2>&1 | tail -30`
Expected: ImportError — new classes don't exist yet

- [ ] **Step 3: Implement model changes in realization.py**

Update `backend/src/explorator/models/realization.py`:

```python
"""Realization models: voicings, bass, arrangements."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from explorator.models.base import BaseEntity, CandidateBase

# --- Type aliases ---

VoicingType = Literal["open", "close", "drop2", "drop3"]
RegisterLabel = Literal["low", "mid", "mid_high", "high"]
DensityLevel = Literal["thin", "medium", "full"]


# --- Event models ---

class VoicingEvent(BaseModel):
    """Single chord voicing at a specific bar/beat."""

    bar: int
    beat: float = 1.0
    duration_beats: float = 4.0
    pitches: list[str]
    chord_symbol: str


class BassNoteEvent(BaseModel):
    """Single bass note at a specific bar/beat."""

    bar: int
    beat: float = 1.0
    duration_beats: float = 1.0
    pitch: str
    velocity: int = 80


# --- Voice-leading check ---

class VoiceLeadingCheck(BaseModel):
    """Result of checking voice leading between two adjacent voicings."""

    common_tones: int
    total_semitone_distance: int
    max_leap: int
    has_parallel_fifths: bool
    has_parallel_octaves: bool


# --- Genre preference sub-models ---

class VoicingPreferences(BaseModel):
    """Structured voicing preferences from genre YAML."""

    default_voicing_type: VoicingType = "open"
    default_register: RegisterLabel = "mid"
    default_density: DensityLevel = "medium"
    default_voice_count: int = 4
    favor_extensions: bool = False
    top_voice_continuity: str = "medium"
    variant_voicing_types: list[VoicingType] = Field(
        default_factory=lambda: ["open", "drop2", "close"],
    )


class BassPreferences(BaseModel):
    """Structured bass preferences from genre YAML."""

    default_bass_mode: str = "supportive"
    default_register: str = "low"
    rhythmic_density: str = "moderate"


# --- Gemini response schema ---

class ChordVoicingInstruction(BaseModel):
    """Per-chord voicing instruction from Gemini."""

    chord_symbol: str
    voicing_type: VoicingType
    target_register: RegisterLabel
    extensions_to_include: list[str]
    doubling_notes: list[str] | None = None
    avoid: list[str] | None = None


class VoicingStrategyResponse(BaseModel):
    """Gemini Flash response for voicing strategy."""

    global_strategy: str
    density_level: DensityLevel
    voice_count: int
    per_chord: list[ChordVoicingInstruction]


# --- Variant configuration ---

class VariantConfig(BaseModel):
    """Configuration for a single voicing variant."""

    voicing_type: VoicingType


# --- Existing entities (updated) ---

class VoicingPlan(BaseEntity):
    """How a progression is voiced."""

    progression_candidate_id: str | None = None
    instrument: str = "electric_piano"
    global_strategy: str = ""
    density_level: str = "medium"
    register_profile: str = "mid_high"
    voicing_events: list[VoicingEvent] = Field(default_factory=list)


class BassLine(BaseEntity):
    """Bass realization layer."""

    progression_candidate_id: str | None = None
    style_mode: str = "supportive"
    contour_type: str = "mostly_stepwise"
    rhythmic_density: str = "low"
    relationship_to_harmony: str = "stabilizing"
    note_events: list[BassNoteEvent] = Field(default_factory=list)


class ArrangementCandidate(CandidateBase):
    """Realized musical object combining progression + realization layers."""

    progression_candidate_id: str
    voicing_plan_id: str | None = None
    bass_line_id: str | None = None
    melodic_complement_id: str | None = None
    groove_pattern_id: str | None = None
    instrument_realization_plan_id: str | None = None
    render_artifact_ids: list[str] = Field(default_factory=list)


class ArrangementFamily(BaseEntity):
    """Groups related arrangement variants."""

    session_id: str
    root_arrangement_candidate_id: str
    member_arrangement_candidate_ids: list[str] = Field(default_factory=list)
    family_description: str = ""
```

- [ ] **Step 4: Update GenreProfile in style.py**

Add `voicing_preferences` and `bass_preferences` to `backend/src/explorator/models/style.py`:

```python
"""GenreProfile, GenreRule, AntiPattern, HarmonicGrammar models."""

from typing import Any

from pydantic import Field

from explorator.models.base import BaseEntity
from explorator.models.realization import BassPreferences, VoicingPreferences


class GenreProfile(BaseEntity):
    """Operational representation of genre knowledge."""

    genre: str
    display_name: str = ""
    subgenre: str | None = None
    harmonic_vocabulary: list[str] = Field(default_factory=list)
    harmonic_tendencies: dict[str, str] = Field(default_factory=dict)
    voicing_tendencies: dict[str, str] = Field(default_factory=dict)
    bass_tendencies: dict[str, str] = Field(default_factory=dict)
    groove_tendencies: dict[str, str] = Field(default_factory=dict)
    common_devices: list[str] = Field(default_factory=list)
    anti_patterns: list[str] = Field(default_factory=list)
    experimentation_envelope: dict[str, float] = Field(default_factory=dict)
    voicing_preferences: VoicingPreferences = Field(default_factory=VoicingPreferences)
    bass_preferences: BassPreferences = Field(default_factory=BassPreferences)


# ... rest of file unchanged (GenreRule, AntiPattern, HarmonicGrammar) ...
```

- [ ] **Step 5: Update GenreProfileYAML in schema.py**

Add `voicing_preferences` and `bass_preferences` to `backend/src/explorator/domain/style/schema.py`:

```python
# Add to GenreProfileYAML class (after groove_tendencies):
    voicing_preferences: dict[str, Any] = Field(default_factory=dict)
    bass_preferences: dict[str, Any] = Field(default_factory=dict)
```

Note: Keep these as `dict[str, Any]` in the YAML schema to allow flexible YAML input. The `VoicingPreferences`/`BassPreferences` Pydantic models are used when consuming the data in domain services.

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/models/test_realization.py -v --tb=short 2>&1 | tail -40`
Expected: All tests PASS

- [ ] **Step 7: Run full test suite for regressions**

Run: `cd backend && python -m pytest tests/ -v --tb=short 2>&1 | tail -20`
Expected: All existing tests still pass (the VoicingPlan/BassLine field type change from `list[dict]` to `list[VoicingEvent]`/`list[BassNoteEvent]` may break existing tests that construct with raw dicts — fix those by using the new model types)

- [ ] **Step 8: Commit**

```bash
git add backend/src/explorator/models/realization.py backend/src/explorator/models/style.py backend/src/explorator/domain/style/schema.py backend/tests/unit/models/test_realization.py
git commit -m "feat(m2a): add typed voicing/bass event models and genre preference sub-models"
```

---

## Task 2: Update Genre YAML Files

**Files:**
- Modify: `backend/src/explorator/data/genres/dream_pop.yaml`
- Modify: `backend/src/explorator/data/genres/synthwave.yaml`
- Modify: `backend/src/explorator/data/genres/cinematic.yaml`

Note: The actual genre YAML directory may be at `backend/src/explorator/domain/style/genres/`. Check before editing.

- [ ] **Step 1: Add voicing_preferences and bass_preferences to dream_pop.yaml**

Append to the end of `dream_pop.yaml`:

```yaml
voicing_preferences:
  default_voicing_type: open
  default_register: mid_high
  default_density: medium
  default_voice_count: 4
  favor_extensions: true
  top_voice_continuity: high
  variant_voicing_types:
    - open
    - drop2

bass_preferences:
  default_bass_mode: supportive
  default_register: low
  rhythmic_density: sparse
```

- [ ] **Step 2: Add voicing_preferences and bass_preferences to synthwave.yaml**

Append to the end of `synthwave.yaml`:

```yaml
voicing_preferences:
  default_voicing_type: close
  default_register: mid
  default_density: medium
  default_voice_count: 4
  favor_extensions: false
  top_voice_continuity: medium
  variant_voicing_types:
    - close
    - drop2
    - open

bass_preferences:
  default_bass_mode: supportive
  default_register: low
  rhythmic_density: moderate
```

- [ ] **Step 3: Add voicing_preferences and bass_preferences to cinematic.yaml**

Append to the end of `cinematic.yaml`:

```yaml
voicing_preferences:
  default_voicing_type: open
  default_register: mid
  default_density: full
  default_voice_count: 4
  favor_extensions: true
  top_voice_continuity: high
  variant_voicing_types:
    - open
    - drop3
    - drop2

bass_preferences:
  default_bass_mode: pedal
  default_register: low
  rhythmic_density: sparse
```

- [ ] **Step 4: Verify YAML loads correctly**

Run: `cd backend && python -c "from explorator.domain.style.loader import load_genre_from_yaml; from pathlib import Path; p = load_genre_from_yaml(Path('src/explorator/domain/style/genres/dream_pop.yaml')); print(p.voicing_preferences)"`
Expected: Prints the voicing_preferences dict

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/data/genres/ backend/src/explorator/domain/style/genres/
git commit -m "feat(m2a): add voicing and bass preferences to genre YAML profiles"
```

---

## Task 3: Music21 Adapter — realize_voicing

**Files:**
- Modify: `backend/src/explorator/adapters/music21_adapter.py`
- Create: `backend/tests/unit/adapters/test_music21_voicing.py`

- [ ] **Step 1: Write failing tests for realize_voicing**

```python
# backend/tests/unit/adapters/test_music21_voicing.py

import pytest

from explorator.adapters.music21_adapter import realize_voicing


class TestRealizeVoicingClose:
    """Close voicing: stack pitches ascending within one octave."""

    def test_major_triad_close_mid(self):
        pitches = realize_voicing("C", "close", "mid", voice_count=3, extensions=[])
        assert len(pitches) == 3
        # All pitches should be in mid range (C3-C5)
        for p in pitches:
            octave = int(p[-1])
            assert 3 <= octave <= 5

    def test_maj7_close_mid_high(self):
        pitches = realize_voicing("Cmaj7", "close", "mid_high", voice_count=4, extensions=[])
        assert len(pitches) == 4
        # Should contain C, E, G, B in some voicing
        pitch_names = [p[:-1] for p in pitches]
        assert "C" in pitch_names
        assert "B" in pitch_names

    def test_minor7_close(self):
        pitches = realize_voicing("Am7", "close", "mid", voice_count=4, extensions=[])
        assert len(pitches) == 4


class TestRealizeVoicingOpen:
    """Open voicing: spread across ~2 octaves."""

    def test_maj7_open_mid_high(self):
        pitches = realize_voicing("Cmaj7", "open", "mid_high", voice_count=4, extensions=[])
        assert len(pitches) == 4
        # Open voicing should span more than one octave
        from music21 import pitch as m21pitch
        midi_vals = [m21pitch.Pitch(p).midi for p in pitches]
        span = max(midi_vals) - min(midi_vals)
        assert span >= 12  # at least one octave span


class TestRealizeVoicingDrop2:
    """Drop-2: close position, drop second-from-top down one octave."""

    def test_maj7_drop2(self):
        pitches = realize_voicing("Cmaj7", "drop2", "mid_high", voice_count=4, extensions=[])
        assert len(pitches) == 4
        from music21 import pitch as m21pitch
        midi_vals = sorted([m21pitch.Pitch(p).midi for p in pitches])
        # Drop-2 should have a gap: lowest note is well below others
        assert midi_vals[1] - midi_vals[0] >= 8  # dropped voice creates gap


class TestRealizeVoicingDrop3:
    """Drop-3: close position, drop third-from-top down one octave."""

    def test_maj7_drop3(self):
        pitches = realize_voicing("Cmaj7", "drop3", "mid", voice_count=4, extensions=[])
        assert len(pitches) == 4


class TestRealizeVoicingExtensions:
    """Adding extensions like 9th, 11th."""

    def test_add9(self):
        pitches = realize_voicing("C", "close", "mid", voice_count=4, extensions=["9"])
        assert len(pitches) == 4
        # Should include D (the 9th of C)
        pitch_names = [p[:-1] for p in pitches]
        assert "D" in pitch_names

    def test_voice_count_limits_output(self):
        pitches = realize_voicing("Cmaj7", "close", "mid", voice_count=3, extensions=["9"])
        assert len(pitches) == 3  # voice_count is respected even with extra extensions


class TestRealizeVoicingRegisters:
    """Register clamping."""

    def test_low_register(self):
        pitches = realize_voicing("C", "close", "low", voice_count=3, extensions=[])
        from music21 import pitch as m21pitch
        for p in pitches:
            midi = m21pitch.Pitch(p).midi
            assert 36 <= midi <= 72  # C2-C4 roughly

    def test_high_register(self):
        pitches = realize_voicing("C", "close", "high", voice_count=3, extensions=[])
        from music21 import pitch as m21pitch
        for p in pitches:
            midi = m21pitch.Pitch(p).midi
            assert 72 <= midi <= 108  # C5-C7 roughly
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/adapters/test_music21_voicing.py -v --tb=short 2>&1 | tail -20`
Expected: ImportError — `realize_voicing` doesn't exist yet

- [ ] **Step 3: Implement realize_voicing in music21_adapter.py**

Add to `backend/src/explorator/adapters/music21_adapter.py`:

```python
from explorator.models.realization import VoicingType, RegisterLabel

# Register boundaries as MIDI note numbers
_REGISTER_BOUNDS: dict[str, tuple[int, int]] = {
    "low": (36, 60),       # C2 - C4
    "mid": (48, 72),       # C3 - C5
    "mid_high": (60, 84),  # C4 - C6
    "high": (72, 96),      # C5 - C7
}

# Extension intervals from root (in semitones)
_EXTENSION_SEMITONES: dict[str, int] = {
    "9": 14,    # major 9th
    "b9": 13,
    "#9": 15,
    "11": 17,   # perfect 11th
    "#11": 18,
    "13": 21,   # major 13th
    "b13": 20,
}


def realize_voicing(
    chord_symbol: str,
    voicing_type: str,
    target_register: str,
    voice_count: int,
    extensions: list[str],
) -> list[str]:
    """Realize a chord symbol into named pitches using a voicing technique.

    Args:
        chord_symbol: e.g. "Cmaj7", "Am7", "F#m9"
        voicing_type: "open", "close", "drop2", "drop3"
        target_register: "low", "mid", "mid_high", "high"
        voice_count: number of voices (3-5)
        extensions: additional intervals like ["9", "13"]

    Returns:
        List of named pitches, e.g. ["C3", "G3", "E4", "B4"]
    """
    from music21 import chord as m21chord
    from music21 import pitch as m21pitch

    # Parse chord to get pitch classes
    cs = m21chord.Chord(_normalize_chord_for_voicing(chord_symbol))
    root = cs.root()
    pitch_classes = list(cs.pitches)

    # Add extensions
    for ext in extensions:
        semitones = _EXTENSION_SEMITONES.get(ext)
        if semitones is not None:
            ext_pitch = m21pitch.Pitch(root.midi + semitones)
            # Only add if not already present (by pitch class)
            if ext_pitch.pitchClass not in [p.pitchClass for p in pitch_classes]:
                pitch_classes.append(ext_pitch)

    # Limit to voice_count (keep root + most important tones)
    if len(pitch_classes) > voice_count:
        # Priority: root, then 3rd/7th, then extensions from original chord
        pitch_classes = _select_voices(pitch_classes, root, voice_count)

    # Build close position in target register
    lo, hi = _REGISTER_BOUNDS.get(target_register, (48, 72))
    mid_midi = (lo + hi) // 2
    close_pitches = _build_close_position(pitch_classes, mid_midi)

    # Apply voicing technique
    if voicing_type == "close":
        voiced = close_pitches
    elif voicing_type == "open":
        voiced = _apply_open_voicing(close_pitches)
    elif voicing_type == "drop2":
        voiced = _apply_drop2(close_pitches)
    elif voicing_type == "drop3":
        voiced = _apply_drop3(close_pitches)
    else:
        voiced = close_pitches

    # Clamp to register
    voiced = _clamp_to_register(voiced, lo, hi)

    # Sort low to high and convert to named pitches
    voiced.sort(key=lambda p: p.midi)
    return [p.nameWithOctave for p in voiced]


def _normalize_chord_for_voicing(symbol: str) -> str:
    """Normalize chord symbol for music21 parsing."""
    # Reuse existing normalization
    return _normalize_chord_symbol(symbol)


def _select_voices(
    pitches: list, root, voice_count: int,
) -> list:
    """Select the most important voices up to voice_count."""
    from music21 import interval

    root_pc = root.pitchClass
    # Score each pitch: root=10, 3rd/7th=8, 5th=5, extensions=3
    scored = []
    for p in pitches:
        semis = (p.pitchClass - root_pc) % 12
        if semis == 0:
            score = 10  # root
        elif semis in (3, 4):
            score = 8  # 3rd
        elif semis in (10, 11):
            score = 8  # 7th
        elif semis == 7:
            score = 5  # 5th
        else:
            score = 3  # extension
        scored.append((score, p))

    scored.sort(key=lambda x: -x[0])
    return [p for _, p in scored[:voice_count]]


def _build_close_position(pitch_classes: list, target_midi: int) -> list:
    """Stack pitches in close position near target_midi."""
    from music21 import pitch as m21pitch

    result = []
    for pc in pitch_classes:
        p = m21pitch.Pitch(pc.pitchClass)
        # Place near target
        while p.midi < target_midi - 6:
            p.octave += 1
        while p.midi > target_midi + 6:
            p.octave -= 1
        result.append(p)

    # Sort ascending and compress into close position (within one octave)
    result.sort(key=lambda p: p.midi)
    for i in range(1, len(result)):
        while result[i].midi - result[i - 1].midi > 12:
            result[i].octave -= 1
        while result[i].midi <= result[i - 1].midi:
            result[i].octave += 1

    return result


def _apply_open_voicing(close_pitches: list) -> list:
    """Spread voicing across ~2 octaves by alternating skip/step."""
    if len(close_pitches) < 3:
        return close_pitches
    result = list(close_pitches)
    # Drop every other interior voice down an octave
    for i in range(1, len(result) - 1, 2):
        result[i].octave -= 1
    return result


def _apply_drop2(close_pitches: list) -> list:
    """Drop second-from-top voice down one octave."""
    if len(close_pitches) < 3:
        return close_pitches
    result = list(close_pitches)
    result.sort(key=lambda p: p.midi)
    # Second from top
    idx = len(result) - 2
    result[idx].octave -= 1
    return result


def _apply_drop3(close_pitches: list) -> list:
    """Drop third-from-top voice down one octave."""
    if len(close_pitches) < 4:
        return _apply_drop2(close_pitches)
    result = list(close_pitches)
    result.sort(key=lambda p: p.midi)
    idx = len(result) - 3
    result[idx].octave -= 1
    return result


def _clamp_to_register(pitches: list, lo: int, hi: int) -> list:
    """Shift pitches into register bounds by octave transposition."""
    result = []
    for p in pitches:
        while p.midi < lo:
            p.octave += 1
        while p.midi > hi:
            p.octave -= 1
        result.append(p)
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/adapters/test_music21_voicing.py -v --tb=short 2>&1 | tail -30`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/adapters/music21_adapter.py backend/tests/unit/adapters/test_music21_voicing.py
git commit -m "feat(m2a): add realize_voicing to music21 adapter"
```

---

## Task 4: Music21 Adapter — check_voice_leading

**Files:**
- Modify: `backend/src/explorator/adapters/music21_adapter.py`
- Modify: `backend/tests/unit/adapters/test_music21_voicing.py`

- [ ] **Step 1: Write failing tests for check_voice_leading**

Add to `backend/tests/unit/adapters/test_music21_voicing.py`:

```python
from explorator.adapters.music21_adapter import check_voice_leading
from explorator.models.realization import VoiceLeadingCheck


class TestCheckVoiceLeading:
    def test_identical_voicings(self):
        result = check_voice_leading(
            ["C4", "E4", "G4", "B4"],
            ["C4", "E4", "G4", "B4"],
        )
        assert isinstance(result, VoiceLeadingCheck)
        assert result.common_tones == 4
        assert result.total_semitone_distance == 0
        assert result.max_leap == 0

    def test_smooth_voice_leading(self):
        # Cmaj7 → Am7: C stays, E stays, G stays, B→A (2 semitones)
        result = check_voice_leading(
            ["C4", "E4", "G4", "B4"],
            ["C4", "E4", "G4", "A4"],
        )
        assert result.common_tones == 3
        assert result.total_semitone_distance == 2
        assert result.max_leap == 2

    def test_parallel_fifths_detected(self):
        # Voice 1: C4→D4, Voice 2: G4→A4 — parallel fifths
        result = check_voice_leading(
            ["C4", "G4"],
            ["D4", "A4"],
        )
        assert result.has_parallel_fifths is True

    def test_no_parallel_fifths(self):
        result = check_voice_leading(
            ["C4", "E4", "G4"],
            ["C4", "F4", "A4"],
        )
        assert result.has_parallel_fifths is False

    def test_parallel_octaves_detected(self):
        # Voice 1: C3→D3, Voice 2: C4→D4 — parallel octaves
        result = check_voice_leading(
            ["C3", "C4"],
            ["D3", "D4"],
        )
        assert result.has_parallel_octaves is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/adapters/test_music21_voicing.py::TestCheckVoiceLeading -v --tb=short 2>&1 | tail -15`
Expected: ImportError — `check_voice_leading` doesn't exist yet

- [ ] **Step 3: Implement check_voice_leading**

Add to `backend/src/explorator/adapters/music21_adapter.py`:

```python
from explorator.models.realization import VoiceLeadingCheck


def check_voice_leading(
    prev_pitches: list[str],
    next_pitches: list[str],
) -> VoiceLeadingCheck:
    """Check voice leading quality between two adjacent voicings.

    Assumes voices are paired by index (sorted low to high).
    """
    from music21 import pitch as m21pitch

    prev = sorted([m21pitch.Pitch(p) for p in prev_pitches], key=lambda p: p.midi)
    nxt = sorted([m21pitch.Pitch(p) for p in next_pitches], key=lambda p: p.midi)

    n_voices = min(len(prev), len(nxt))

    common_tones = 0
    total_dist = 0
    max_leap = 0
    intervals_prev: list[int] = []
    intervals_next: list[int] = []

    for i in range(n_voices):
        dist = abs(nxt[i].midi - prev[i].midi)
        if dist == 0:
            common_tones += 1
        total_dist += dist
        if dist > max_leap:
            max_leap = dist

    # Check parallel fifths and octaves
    has_parallel_fifths = False
    has_parallel_octaves = False

    for i in range(n_voices):
        for j in range(i + 1, n_voices):
            interval_prev = (prev[j].midi - prev[i].midi) % 12
            interval_next = (nxt[j].midi - nxt[i].midi) % 12

            motion_i = nxt[i].midi - prev[i].midi
            motion_j = nxt[j].midi - prev[j].midi

            # Both voices must actually move and move in the same direction
            if motion_i == 0 or motion_j == 0:
                continue
            if (motion_i > 0) != (motion_j > 0):
                continue

            # Parallel fifths: both intervals are perfect fifths (7 semitones)
            if interval_prev == 7 and interval_next == 7:
                has_parallel_fifths = True

            # Parallel octaves: both intervals are octaves/unisons (0 semitones)
            if interval_prev == 0 and interval_next == 0:
                has_parallel_octaves = True

    return VoiceLeadingCheck(
        common_tones=common_tones,
        total_semitone_distance=total_dist,
        max_leap=max_leap,
        has_parallel_fifths=has_parallel_fifths,
        has_parallel_octaves=has_parallel_octaves,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/adapters/test_music21_voicing.py -v --tb=short 2>&1 | tail -30`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/adapters/music21_adapter.py backend/tests/unit/adapters/test_music21_voicing.py
git commit -m "feat(m2a): add check_voice_leading to music21 adapter"
```

---

## Task 5: VoicingGenerator Domain Service

**Files:**
- Create: `backend/src/explorator/domain/realization/__init__.py`
- Create: `backend/src/explorator/domain/realization/voicing.py`
- Create: `backend/tests/unit/domain/test_voicing_generator.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/domain/test_voicing_generator.py

import pytest

from explorator.domain.realization.voicing import VoicingGenerator
from explorator.models.realization import (
    ChordVoicingInstruction,
    VariantConfig,
    VoicingEvent,
    VoicingPlan,
    VoicingPreferences,
    VoicingStrategyResponse,
)


class TestVoicingGeneratorRealize:
    """Test deterministic voicing realization."""

    def _make_strategy(self) -> VoicingStrategyResponse:
        return VoicingStrategyResponse(
            global_strategy="open spacing, favor 7ths",
            density_level="medium",
            voice_count=4,
            per_chord=[
                ChordVoicingInstruction(
                    chord_symbol="Cmaj7",
                    voicing_type="open",
                    target_register="mid_high",
                    extensions_to_include=[],
                ),
                ChordVoicingInstruction(
                    chord_symbol="Am7",
                    voicing_type="open",
                    target_register="mid_high",
                    extensions_to_include=[],
                ),
            ],
        )

    def test_realize_produces_voicing_plan(self):
        gen = VoicingGenerator()
        strategy = self._make_strategy()
        chord_symbols = ["Cmaj7", "Am7"]
        variant = VariantConfig(voicing_type="open")
        prefs = VoicingPreferences(default_register="mid_high")

        plan = gen.realize(strategy, chord_symbols, prefs, variant)

        assert isinstance(plan, VoicingPlan)
        assert len(plan.voicing_events) == 2
        assert plan.voicing_events[0].chord_symbol == "Cmaj7"
        assert plan.voicing_events[1].chord_symbol == "Am7"

    def test_voicing_events_have_correct_pitches(self):
        gen = VoicingGenerator()
        strategy = self._make_strategy()
        chord_symbols = ["Cmaj7", "Am7"]
        variant = VariantConfig(voicing_type="close")
        prefs = VoicingPreferences(default_register="mid_high")

        plan = gen.realize(strategy, chord_symbols, prefs, variant)

        for event in plan.voicing_events:
            assert isinstance(event, VoicingEvent)
            assert len(event.pitches) == 4  # voice_count from strategy
            # Each pitch should be a valid named pitch
            for p in event.pitches:
                assert any(c.isdigit() for c in p)  # has octave number

    def test_variant_overrides_voicing_type(self):
        gen = VoicingGenerator()
        strategy = self._make_strategy()
        chord_symbols = ["Cmaj7", "Am7"]
        prefs = VoicingPreferences()

        plan_open = gen.realize(strategy, chord_symbols, prefs, VariantConfig(voicing_type="open"))
        plan_close = gen.realize(strategy, chord_symbols, prefs, VariantConfig(voicing_type="close"))

        # Different voicing types should produce different pitch arrangements
        assert plan_open.voicing_events[0].pitches != plan_close.voicing_events[0].pitches

    def test_generate_variants_produces_multiple_plans(self):
        gen = VoicingGenerator()
        strategy = self._make_strategy()
        chord_symbols = ["Cmaj7", "Am7"]
        prefs = VoicingPreferences(variant_voicing_types=["open", "drop2", "close"])

        plans = gen.generate_variants(strategy, chord_symbols, prefs)

        assert len(plans) == 3
        for plan in plans:
            assert isinstance(plan, VoicingPlan)
            assert plan.global_strategy == "open spacing, favor 7ths"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/domain/test_voicing_generator.py -v --tb=short 2>&1 | tail -15`
Expected: ImportError

- [ ] **Step 3: Create domain/realization/__init__.py**

```python
# backend/src/explorator/domain/realization/__init__.py
```

(Empty file — just makes it a package)

- [ ] **Step 4: Implement VoicingGenerator**

```python
# backend/src/explorator/domain/realization/voicing.py

"""Deterministic voicing realization from Gemini strategies."""

from ulid import ULID

from explorator.adapters.music21_adapter import check_voice_leading, realize_voicing
from explorator.models.realization import (
    ChordVoicingInstruction,
    VariantConfig,
    VoicingEvent,
    VoicingPlan,
    VoicingPreferences,
    VoicingStrategyResponse,
)
from explorator.utils import utc_now


class VoicingGenerator:
    """Realizes voicing strategies into concrete pitched VoicingPlans."""

    def realize(
        self,
        strategy: VoicingStrategyResponse,
        chord_symbols: list[str],
        prefs: VoicingPreferences,
        variant: VariantConfig,
    ) -> VoicingPlan:
        """Realize a voicing strategy into a VoicingPlan for one variant."""
        events: list[VoicingEvent] = []
        prev_pitches: list[str] | None = None

        for bar_idx, symbol in enumerate(chord_symbols):
            # Get per-chord instruction (fall back to defaults)
            instruction = self._get_instruction(strategy, bar_idx, symbol, prefs)

            # Override voicing_type with variant
            voicing_type = variant.voicing_type

            # Realize pitches
            pitches = realize_voicing(
                chord_symbol=symbol,
                voicing_type=voicing_type,
                target_register=instruction.target_register,
                voice_count=strategy.voice_count,
                extensions=instruction.extensions_to_include,
            )

            # Voice-leading optimization: try inversions, pick best
            if prev_pitches is not None:
                pitches = self._optimize_voice_leading(
                    prev_pitches, pitches, symbol, voicing_type,
                    instruction.target_register, strategy.voice_count,
                    instruction.extensions_to_include,
                )

            events.append(VoicingEvent(
                bar=bar_idx + 1,
                pitches=pitches,
                chord_symbol=symbol,
            ))
            prev_pitches = pitches

        now = utc_now()
        return VoicingPlan(
            id=f"vp_{ULID()}",
            type="voicing_plan",
            status="draft",
            created_at=now,
            updated_at=now,
            global_strategy=strategy.global_strategy,
            density_level=strategy.density_level,
            register_profile=prefs.default_register,
            voicing_events=events,
        )

    def generate_variants(
        self,
        strategy: VoicingStrategyResponse,
        chord_symbols: list[str],
        prefs: VoicingPreferences,
    ) -> list[VoicingPlan]:
        """Generate multiple voicing plan variants by sweeping voicing types."""
        return [
            self.realize(strategy, chord_symbols, prefs, VariantConfig(voicing_type=vt))
            for vt in prefs.variant_voicing_types
        ]

    def _get_instruction(
        self,
        strategy: VoicingStrategyResponse,
        bar_idx: int,
        chord_symbol: str,
        prefs: VoicingPreferences,
    ) -> ChordVoicingInstruction:
        """Get the per-chord instruction, falling back to genre defaults."""
        if bar_idx < len(strategy.per_chord):
            return strategy.per_chord[bar_idx]
        # Fallback: use genre defaults
        return ChordVoicingInstruction(
            chord_symbol=chord_symbol,
            voicing_type=prefs.default_voicing_type,
            target_register=prefs.default_register,
            extensions_to_include=[],
        )

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
        """Try to minimize voice movement from previous chord."""
        best = current_pitches
        best_check = check_voice_leading(prev_pitches, current_pitches)
        best_cost = best_check.total_semitone_distance - (best_check.common_tones * 4)

        if best_check.has_parallel_fifths or best_check.has_parallel_octaves:
            best_cost += 100  # heavy penalty

        # V1: accept the initial voicing. The cost function and parallel
        # motion checks are wired up for M2b evaluation to use.
        # Inversion search can be added here later if quality needs it.
        return best
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/domain/test_voicing_generator.py -v --tb=short 2>&1 | tail -20`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/explorator/domain/realization/ backend/tests/unit/domain/test_voicing_generator.py
git commit -m "feat(m2a): add VoicingGenerator domain service"
```

---

## Task 6: BassLineGenerator Domain Service

**Files:**
- Create: `backend/src/explorator/domain/realization/bass.py`
- Create: `backend/tests/unit/domain/test_bass_generator.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/domain/test_bass_generator.py

import pytest

from explorator.domain.realization.bass import BassLineGenerator
from explorator.models.realization import BassLine, BassNoteEvent, BassPreferences


class TestBassLineGeneratorSupportive:
    def test_dream_pop_supportive(self):
        gen = BassLineGenerator()
        prefs = BassPreferences(
            default_bass_mode="supportive",
            default_register="low",
            rhythmic_density="sparse",
        )
        chord_symbols = ["Cmaj7", "Am7", "Fmaj7", "G7"]

        bl = gen.generate(chord_symbols, prefs, genre="dream_pop")

        assert isinstance(bl, BassLine)
        assert bl.style_mode == "supportive"
        assert len(bl.note_events) == 4  # one per chord (sparse = whole note)
        assert bl.note_events[0].pitch.startswith("C")  # root of Cmaj7
        assert bl.note_events[1].pitch.startswith("A")  # root of Am7
        assert bl.note_events[0].duration_beats == 4.0  # whole note

    def test_synthwave_supportive(self):
        gen = BassLineGenerator()
        prefs = BassPreferences(
            default_bass_mode="supportive",
            default_register="low",
            rhythmic_density="moderate",
        )
        chord_symbols = ["Cm", "Fm"]

        bl = gen.generate(chord_symbols, prefs, genre="synthwave")

        assert isinstance(bl, BassLine)
        # Moderate density = root + octave per bar = 2 events per chord
        assert len(bl.note_events) == 4  # 2 chords × 2 events each

    def test_cinematic_pedal(self):
        gen = BassLineGenerator()
        prefs = BassPreferences(
            default_bass_mode="pedal",
            default_register="low",
            rhythmic_density="sparse",
        )
        chord_symbols = ["Cmaj7", "Am7", "Fmaj7", "G7"]

        bl = gen.generate(chord_symbols, prefs, genre="cinematic")

        assert isinstance(bl, BassLine)
        assert bl.style_mode == "pedal"
        # Cinematic sparse: root + occasional 5th every other bar
        assert len(bl.note_events) >= 4  # at least one per bar

    def test_bass_register_is_low(self):
        gen = BassLineGenerator()
        prefs = BassPreferences(default_register="low")
        chord_symbols = ["C"]

        bl = gen.generate(chord_symbols, prefs, genre="dream_pop")

        # Bass notes should be in octave 2
        octave = int(bl.note_events[0].pitch[-1])
        assert octave <= 3

    def test_bass_line_entity_fields(self):
        gen = BassLineGenerator()
        prefs = BassPreferences()
        chord_symbols = ["C"]

        bl = gen.generate(chord_symbols, prefs, genre="dream_pop")

        assert bl.type == "bass_line"
        assert bl.status == "draft"
        assert bl.id.startswith("bl_")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/domain/test_bass_generator.py -v --tb=short 2>&1 | tail -15`
Expected: ImportError

- [ ] **Step 3: Implement BassLineGenerator**

```python
# backend/src/explorator/domain/realization/bass.py

"""Deterministic bass line generation from genre templates."""

from ulid import ULID

from explorator.adapters.music21_adapter import _normalize_chord_symbol
from explorator.models.realization import BassLine, BassNoteEvent, BassPreferences
from explorator.utils import utc_now


# Bass register: octave number for each register label
_BASS_OCTAVE: dict[str, int] = {
    "sub_low": 1,
    "low": 2,
}


class BassLineGenerator:
    """Generates bass lines from chord symbols using genre-specific templates."""

    def generate(
        self,
        chord_symbols: list[str],
        prefs: BassPreferences,
        genre: str,
    ) -> BassLine:
        """Generate a bass line for a chord progression."""
        octave = _BASS_OCTAVE.get(prefs.default_register, 2)
        events: list[BassNoteEvent] = []

        for bar_idx, symbol in enumerate(chord_symbols):
            root = self._extract_root(symbol)
            bar = bar_idx + 1
            bar_events = self._apply_template(
                root, octave, bar, prefs, genre,
            )
            events.extend(bar_events)

        now = utc_now()
        return BassLine(
            id=f"bl_{ULID()}",
            type="bass_line",
            status="draft",
            created_at=now,
            updated_at=now,
            style_mode=prefs.default_bass_mode,
            rhythmic_density=prefs.rhythmic_density,
            note_events=events,
        )

    def _apply_template(
        self,
        root: str,
        octave: int,
        bar: int,
        prefs: BassPreferences,
        genre: str,
    ) -> list[BassNoteEvent]:
        """Apply genre-specific rhythm template to a root note."""
        pitch = f"{root}{octave}"

        if prefs.rhythmic_density == "sparse":
            # Whole note: one event per bar
            if prefs.default_bass_mode == "pedal" and bar % 2 == 0:
                # Pedal: add 5th on beat 3 every other bar
                fifth = self._fifth_above(root, octave)
                return [
                    BassNoteEvent(bar=bar, beat=1.0, duration_beats=2.0, pitch=pitch),
                    BassNoteEvent(bar=bar, beat=3.0, duration_beats=2.0, pitch=fifth),
                ]
            return [BassNoteEvent(bar=bar, beat=1.0, duration_beats=4.0, pitch=pitch)]

        if prefs.rhythmic_density == "moderate":
            # Root on beat 1, octave on beat 3
            octave_up = f"{root}{octave + 1}"
            return [
                BassNoteEvent(bar=bar, beat=1.0, duration_beats=2.0, pitch=pitch),
                BassNoteEvent(bar=bar, beat=3.0, duration_beats=2.0, pitch=octave_up),
            ]

        # Active: root quarter notes (placeholder for future modes)
        return [
            BassNoteEvent(bar=bar, beat=float(b), duration_beats=1.0, pitch=pitch)
            for b in range(1, 5)
        ]

    def _extract_root(self, chord_symbol: str) -> str:
        """Extract root note name from chord symbol."""
        from music21 import harmony

        try:
            cs = harmony.ChordSymbol(_normalize_chord_symbol(chord_symbol))
            root = cs.root()
            name = root.name
            # Normalize: music21 uses '-' for flat, we want 'b'
            return name.replace("-", "b")
        except Exception:
            # Fallback: take first 1-2 chars
            root = chord_symbol[0]
            if len(chord_symbol) > 1 and chord_symbol[1] in ("#", "b"):
                root += chord_symbol[1]
            return root

    def _fifth_above(self, root: str, octave: int) -> str:
        """Get the perfect fifth above a root note."""
        from music21 import pitch as m21pitch

        p = m21pitch.Pitch(f"{root}{octave}")
        fifth = m21pitch.Pitch(p.midi + 7)
        name = fifth.name.replace("-", "b")
        return f"{name}{fifth.octave}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/domain/test_bass_generator.py -v --tb=short 2>&1 | tail -20`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/domain/realization/bass.py backend/tests/unit/domain/test_bass_generator.py
git commit -m "feat(m2a): add BassLineGenerator domain service"
```

---

## Task 7: ArrangementAssembler Domain Service

**Files:**
- Create: `backend/src/explorator/domain/realization/assembly.py`
- Create: `backend/tests/unit/domain/test_assembly.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/domain/test_assembly.py

from explorator.domain.realization.assembly import ArrangementAssembler
from explorator.models.realization import (
    ArrangementCandidate,
    ArrangementFamily,
    BassLine,
    BassNoteEvent,
    VoicingEvent,
    VoicingPlan,
)


def _make_voicing_plan(vp_id: str) -> VoicingPlan:
    return VoicingPlan(
        id=vp_id, type="voicing_plan", status="draft",
        voicing_events=[VoicingEvent(bar=1, pitches=["C4", "E4", "G4"], chord_symbol="C")],
    )


def _make_bass_line() -> BassLine:
    return BassLine(
        id="bl_01", type="bass_line", status="draft",
        note_events=[BassNoteEvent(bar=1, pitch="C2")],
    )


class TestArrangementAssembler:
    def test_assemble_single(self):
        assembler = ArrangementAssembler()
        vp = _make_voicing_plan("vp_01")
        bl = _make_bass_line()

        ac = assembler.assemble_one(
            progression_candidate_id="prog_01",
            session_id="sess_01",
            voicing_plan=vp,
            bass_line=bl,
            intent_tags=["dreamy"],
            rationale="open voicing, mid-high register",
        )

        assert isinstance(ac, ArrangementCandidate)
        assert ac.progression_candidate_id == "prog_01"
        assert ac.voicing_plan_id == "vp_01"
        assert ac.bass_line_id == "bl_01"
        assert ac.session_id == "sess_01"
        assert ac.type == "arrangement_candidate"
        assert ac.status == "draft"

    def test_assemble_family(self):
        assembler = ArrangementAssembler()
        bl = _make_bass_line()
        plans = [_make_voicing_plan(f"vp_{i}") for i in range(3)]

        family, candidates = assembler.assemble_family(
            progression_candidate_id="prog_01",
            session_id="sess_01",
            voicing_plans=plans,
            bass_line=bl,
            intent_tags=["dreamy"],
        )

        assert isinstance(family, ArrangementFamily)
        assert len(candidates) == 3
        # Root is first in sweep order
        assert family.root_arrangement_candidate_id == candidates[0].id
        assert len(family.member_arrangement_candidate_ids) == 3
        for ac in candidates:
            assert ac.id in family.member_arrangement_candidate_ids
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/domain/test_assembly.py -v --tb=short 2>&1 | tail -15`
Expected: ImportError

- [ ] **Step 3: Implement ArrangementAssembler**

```python
# backend/src/explorator/domain/realization/assembly.py

"""Combines voicing plans + bass lines into arrangement candidates."""

from ulid import ULID

from explorator.models.realization import (
    ArrangementCandidate,
    ArrangementFamily,
    BassLine,
    VoicingPlan,
)
from explorator.utils import utc_now


class ArrangementAssembler:
    """Assembles voicing plans and bass lines into arrangement candidates."""

    def assemble_one(
        self,
        progression_candidate_id: str,
        session_id: str,
        voicing_plan: VoicingPlan,
        bass_line: BassLine,
        intent_tags: list[str],
        rationale: str,
    ) -> ArrangementCandidate:
        """Create a single ArrangementCandidate from a voicing plan + bass line."""
        now = utc_now()
        return ArrangementCandidate(
            id=f"arr_{ULID()}",
            type="arrangement_candidate",
            status="draft",
            created_at=now,
            updated_at=now,
            session_id=session_id,
            progression_candidate_id=progression_candidate_id,
            voicing_plan_id=voicing_plan.id,
            bass_line_id=bass_line.id,
            intent_tags=intent_tags,
            rationale=rationale,
        )

    def assemble_family(
        self,
        progression_candidate_id: str,
        session_id: str,
        voicing_plans: list[VoicingPlan],
        bass_line: BassLine,
        intent_tags: list[str],
    ) -> tuple[ArrangementFamily, list[ArrangementCandidate]]:
        """Assemble multiple voicing variants into a family of arrangements."""
        candidates = [
            self.assemble_one(
                progression_candidate_id=progression_candidate_id,
                session_id=session_id,
                voicing_plan=vp,
                bass_line=bass_line,
                intent_tags=intent_tags,
                rationale=f"{vp.global_strategy} ({vp.register_profile} register)",
            )
            for vp in voicing_plans
        ]

        now = utc_now()
        family = ArrangementFamily(
            id=f"fam_{ULID()}",
            type="arrangement_family",
            status="active",
            created_at=now,
            updated_at=now,
            session_id=session_id,
            root_arrangement_candidate_id=candidates[0].id,
            member_arrangement_candidate_ids=[c.id for c in candidates],
        )

        return family, candidates
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/domain/test_assembly.py -v --tb=short 2>&1 | tail -15`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/domain/realization/assembly.py backend/tests/unit/domain/test_assembly.py
git commit -m "feat(m2a): add ArrangementAssembler domain service"
```

---

## Task 8: Voicing Prompt Template

**Files:**
- Create: `backend/src/explorator/prompts/voicing.py`
- Create: `backend/tests/unit/prompts/test_voicing_prompt.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/prompts/test_voicing_prompt.py

from explorator.prompts.voicing import voicing_strategy_prompt


class TestVoicingStrategyPrompt:
    def test_contains_chord_symbols(self):
        user, system = voicing_strategy_prompt(
            chord_symbols=["Cmaj7", "Am7", "Fmaj7", "G7"],
            key_center="C",
            mode="major",
            genre="dream_pop",
            voicing_tendencies={"spacing": "open", "register_bias": "mid_high"},
            voice_count=4,
        )
        assert "Cmaj7" in user
        assert "Am7" in user

    def test_contains_genre(self):
        user, system = voicing_strategy_prompt(
            chord_symbols=["Cm", "Fm"],
            key_center="C",
            mode="minor",
            genre="synthwave",
            voicing_tendencies={},
            voice_count=4,
        )
        assert "synthwave" in user.lower() or "synthwave" in system.lower()

    def test_contains_voice_count(self):
        user, system = voicing_strategy_prompt(
            chord_symbols=["C"],
            key_center="C",
            mode="major",
            genre="dream_pop",
            voicing_tendencies={},
            voice_count=3,
        )
        assert "3" in user

    def test_system_prompt_mentions_json(self):
        _, system = voicing_strategy_prompt(
            chord_symbols=["C"],
            key_center="C",
            mode="major",
            genre="dream_pop",
            voicing_tendencies={},
            voice_count=4,
        )
        assert "json" in system.lower() or "JSON" in system
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/prompts/test_voicing_prompt.py -v --tb=short 2>&1 | tail -15`
Expected: ImportError

- [ ] **Step 3: Implement voicing prompt**

```python
# backend/src/explorator/prompts/voicing.py

"""Prompt template for Gemini Flash voicing strategy generation."""


def voicing_strategy_prompt(
    chord_symbols: list[str],
    key_center: str,
    mode: str,
    genre: str,
    voicing_tendencies: dict[str, str],
    voice_count: int,
) -> tuple[str, str]:
    """Build prompt for voicing strategy generation.

    Returns (user_prompt, system_prompt).
    """
    genre_display = genre.replace("_", " ")
    chords = " → ".join(chord_symbols)

    tendencies_text = ""
    if voicing_tendencies:
        items = [f"  - {k}: {v}" for k, v in voicing_tendencies.items()]
        tendencies_text = "Genre voicing tendencies:\n" + "\n".join(items) + "\n\n"

    user_prompt = (
        f"Create a voicing strategy for this {genre_display} chord progression:\n\n"
        f"Progression: {chords}\n"
        f"Key: {key_center} {mode}\n"
        f"Voices: {voice_count}\n\n"
        f"{tendencies_text}"
        "For each chord, specify:\n"
        "- voicing_type: one of 'open', 'close', 'drop2', 'drop3'\n"
        "- target_register: one of 'low', 'mid', 'mid_high', 'high'\n"
        "- extensions_to_include: list of extensions like '7', '9', '13'\n"
        "- doubling_notes: optional, e.g. ['root']\n"
        "- avoid: optional, e.g. ['double_third']\n\n"
        "Also provide:\n"
        "- global_strategy: a short description of the overall voicing approach\n"
        "- density_level: 'thin', 'medium', or 'full'\n"
        f"- voice_count: {voice_count}\n"
    )

    system_prompt = (
        f"You are a music arranger specializing in {genre_display}. "
        f"Create a voicing strategy for a {voice_count}-voice arrangement. "
        "Return valid JSON matching the schema. "
        "Consider smooth voice leading between chords, genre-appropriate register choices, "
        "and tasteful use of extensions."
    )

    return user_prompt, system_prompt
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/prompts/test_voicing_prompt.py -v --tb=short 2>&1 | tail -15`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/prompts/voicing.py backend/tests/unit/prompts/test_voicing_prompt.py
git commit -m "feat(m2a): add voicing strategy prompt template"
```

---

## Task 9: RealizationState and Repositories

**Files:**
- Create: `backend/src/explorator/engine/realization_state.py`
- Create: `backend/src/explorator/graph/voicing_plan_repo.py`
- Create: `backend/src/explorator/graph/bass_line_repo.py`
- Create: `backend/src/explorator/graph/arrangement_candidate_repo.py`
- Create: `backend/src/explorator/graph/arrangement_family_repo.py`

- [ ] **Step 1: Create RealizationState**

```python
# backend/src/explorator/engine/realization_state.py

"""State type for the M2a realization LangGraph pipeline."""

from typing import Any, TypedDict


class RealizationState(TypedDict, total=False):
    """State flowing through the realization graph."""

    # Input
    session_id: str
    progression_candidate_ids: list[str]

    # Hydrated by load_context
    progression_candidates: list[dict[str, Any]]
    genre_profile: dict[str, Any]
    creative_brief: dict[str, Any]

    # Produced by plan_voicings
    voicing_strategies: list[dict[str, Any]]
    voicing_plans: list[dict[str, Any]]

    # Produced by generate_bass
    bass_lines: list[dict[str, Any]]

    # Produced by assemble
    arrangement_candidates: list[dict[str, Any]]
    arrangement_families: list[dict[str, Any]]

    # SSE callback
    on_progress: Any
```

Note: State fields use `dict[str, Any]` (serialized form) following M1's pattern where state carries JSON-serializable dicts, and nodes validate into Pydantic models as needed.

- [ ] **Step 2: Create repository files**

```python
# backend/src/explorator/graph/voicing_plan_repo.py

from explorator.graph.repository import BaseRepository


class VoicingPlanRepo(BaseRepository):
    label = "VoicingPlan"
```

```python
# backend/src/explorator/graph/bass_line_repo.py

from explorator.graph.repository import BaseRepository


class BassLineRepo(BaseRepository):
    label = "BassLine"
```

```python
# backend/src/explorator/graph/arrangement_candidate_repo.py

from explorator.graph.repository import BaseRepository


class ArrangementCandidateRepo(BaseRepository):
    label = "ArrangementCandidate"
```

```python
# backend/src/explorator/graph/arrangement_family_repo.py

from explorator.graph.repository import BaseRepository


class ArrangementFamilyRepo(BaseRepository):
    label = "ArrangementFamily"
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/explorator/engine/realization_state.py backend/src/explorator/graph/voicing_plan_repo.py backend/src/explorator/graph/bass_line_repo.py backend/src/explorator/graph/arrangement_candidate_repo.py backend/src/explorator/graph/arrangement_family_repo.py
git commit -m "feat(m2a): add RealizationState and Neo4j repositories"
```

---

## Task 10: LangGraph Nodes — load_context, plan_voicings, generate_bass, assemble, persist_realization

**Files:**
- Create: `backend/src/explorator/engine/nodes/load_context.py`
- Create: `backend/src/explorator/engine/nodes/plan_voicings.py`
- Create: `backend/src/explorator/engine/nodes/generate_bass.py`
- Create: `backend/src/explorator/engine/nodes/assemble.py`
- Create: `backend/src/explorator/engine/nodes/persist_realization.py`

- [ ] **Step 1: Implement load_context node**

```python
# backend/src/explorator/engine/nodes/load_context.py

"""Hydrate realization context from Neo4j."""

import logging
from typing import Any

from neo4j import AsyncDriver

from explorator.engine.realization_state import RealizationState
from explorator.graph.repository import BaseRepository

logger = logging.getLogger(__name__)


class ProgressionCandidateRepo(BaseRepository):
    label = "ProgressionCandidate"


class SessionRepo(BaseRepository):
    label = "Session"


class GenreProfileRepo(BaseRepository):
    label = "GenreProfile"


class CreativeBriefRepo(BaseRepository):
    label = "CreativeBrief"


async def load_context(
    state: RealizationState, *, driver: AsyncDriver,
) -> dict[str, Any]:
    """Load progression candidates, genre profile, and creative brief."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "load_context"})

    candidate_ids = state.get("progression_candidate_ids", [])
    if not candidate_ids:
        msg = "No progression_candidate_ids provided"
        raise ValueError(msg)

    pc_repo = ProgressionCandidateRepo(driver)
    session_repo = SessionRepo(driver)
    genre_repo = GenreProfileRepo(driver)
    brief_repo = CreativeBriefRepo(driver)

    # Load candidates
    candidates = []
    session_id = None
    for cid in candidate_ids:
        candidate = await pc_repo.get_by_id(cid)
        if candidate is None:
            msg = f"ProgressionCandidate not found: {cid}"
            raise ValueError(msg)
        candidates.append(candidate)
        if session_id is None:
            session_id = candidate.get("session_id")

    # Load session to get genre
    session = await session_repo.get_by_id(session_id)
    if session is None:
        msg = f"Session not found: {session_id}"
        raise ValueError(msg)

    genre_name = session.get("genre", "dream_pop")

    # Load genre profile
    genre_profiles = await genre_repo.query_by_property("genre", genre_name)
    genre_profile = genre_profiles[0] if genre_profiles else {"genre": genre_name}

    # Load creative brief
    briefs = await brief_repo.query_by_property("session_id", session_id)
    brief = briefs[0] if briefs else {}

    if callback:
        await callback("node_completed", {
            "node": "load_context",
            "candidates_loaded": len(candidates),
            "genre": genre_name,
        })

    return {
        "session_id": session_id,
        "progression_candidates": candidates,
        "genre_profile": genre_profile,
        "creative_brief": brief,
    }
```

- [ ] **Step 2: Implement plan_voicings node**

```python
# backend/src/explorator/engine/nodes/plan_voicings.py

"""Generate voicing plans via Gemini strategy + deterministic realization."""

import logging
from typing import Any

from explorator.adapters.gemini import GeminiClient, ModelTier
from explorator.domain.realization.voicing import VoicingGenerator
from explorator.engine.realization_state import RealizationState
from explorator.models.harmony import ProgressionCandidate
from explorator.models.realization import (
    VoicingPreferences,
    VoicingStrategyResponse,
)
from explorator.prompts.voicing import voicing_strategy_prompt

logger = logging.getLogger(__name__)


async def plan_voicings(
    state: RealizationState, *, gemini: GeminiClient,
) -> dict[str, Any]:
    """Generate voicing strategies and realize into VoicingPlans."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "plan_voicings"})

    genre_profile = state.get("genre_profile", {})
    genre = genre_profile.get("genre", "dream_pop")
    voicing_tendencies = genre_profile.get("voicing_tendencies", {})
    voicing_prefs_data = genre_profile.get("voicing_preferences", {})
    prefs = VoicingPreferences.model_validate(voicing_prefs_data) if voicing_prefs_data else VoicingPreferences()

    generator = VoicingGenerator()
    all_strategies: list[dict[str, Any]] = []
    all_plans: list[dict[str, Any]] = []

    for candidate_data in state.get("progression_candidates", []):
        candidate = ProgressionCandidate.model_validate(candidate_data)
        chord_symbols = [e.symbol for e in candidate.chord_events]

        # Get Gemini strategy
        user_prompt, system_prompt = voicing_strategy_prompt(
            chord_symbols=chord_symbols,
            key_center=candidate.key_center,
            mode=candidate.mode,
            genre=genre,
            voicing_tendencies=voicing_tendencies,
            voice_count=prefs.default_voice_count,
        )

        try:
            strategy = await gemini.generate_structured(
                prompt=user_prompt,
                response_model=VoicingStrategyResponse,
                tier=ModelTier.FLASH,
                system_prompt=system_prompt,
            )
        except Exception:
            logger.warning("Gemini voicing strategy failed — using defaults", exc_info=True)
            from explorator.models.realization import ChordVoicingInstruction
            strategy = VoicingStrategyResponse(
                global_strategy=f"default {genre} voicing",
                density_level=prefs.default_density,
                voice_count=prefs.default_voice_count,
                per_chord=[
                    ChordVoicingInstruction(
                        chord_symbol=s,
                        voicing_type=prefs.default_voicing_type,
                        target_register=prefs.default_register,
                        extensions_to_include=[],
                    )
                    for s in chord_symbols
                ],
            )

        all_strategies.append(strategy.model_dump(mode="json"))

        # Realize variants
        plans = generator.generate_variants(strategy, chord_symbols, prefs)
        for plan in plans:
            plan.progression_candidate_id = candidate.id
            all_plans.append(plan.model_dump(mode="json"))

    if callback:
        await callback("node_completed", {
            "node": "plan_voicings",
            "strategies": len(all_strategies),
            "plans": len(all_plans),
        })

    return {
        "voicing_strategies": all_strategies,
        "voicing_plans": all_plans,
    }
```

- [ ] **Step 3: Implement generate_bass node**

```python
# backend/src/explorator/engine/nodes/generate_bass.py

"""Generate bass lines deterministically from genre templates."""

import logging
from typing import Any

from explorator.domain.realization.bass import BassLineGenerator
from explorator.engine.realization_state import RealizationState
from explorator.models.harmony import ProgressionCandidate
from explorator.models.realization import BassPreferences

logger = logging.getLogger(__name__)


async def generate_bass(state: RealizationState) -> dict[str, Any]:
    """Generate one bass line per progression candidate."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "generate_bass"})

    genre_profile = state.get("genre_profile", {})
    genre = genre_profile.get("genre", "dream_pop")
    bass_prefs_data = genre_profile.get("bass_preferences", {})
    prefs = BassPreferences.model_validate(bass_prefs_data) if bass_prefs_data else BassPreferences()

    generator = BassLineGenerator()
    all_bass: list[dict[str, Any]] = []

    for candidate_data in state.get("progression_candidates", []):
        candidate = ProgressionCandidate.model_validate(candidate_data)
        chord_symbols = [e.symbol for e in candidate.chord_events]

        bl = generator.generate(chord_symbols, prefs, genre=genre)
        bl.progression_candidate_id = candidate.id
        all_bass.append(bl.model_dump(mode="json"))

    if callback:
        await callback("node_completed", {
            "node": "generate_bass",
            "bass_lines": len(all_bass),
        })

    return {"bass_lines": all_bass}
```

- [ ] **Step 4: Implement assemble node**

```python
# backend/src/explorator/engine/nodes/assemble.py

"""Assemble voicing plans + bass lines into arrangement candidates."""

import logging
from typing import Any

from explorator.domain.realization.assembly import ArrangementAssembler
from explorator.engine.realization_state import RealizationState
from explorator.models.harmony import ProgressionCandidate
from explorator.models.realization import BassLine, VoicingPlan

logger = logging.getLogger(__name__)


async def assemble(state: RealizationState) -> dict[str, Any]:
    """Combine voicing plans and bass lines into arrangement candidates."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "assemble"})

    session_id = state.get("session_id", "")
    assembler = ArrangementAssembler()

    # Group voicing plans by progression_candidate_id
    vp_by_prog: dict[str, list[VoicingPlan]] = {}
    for vp_data in state.get("voicing_plans", []):
        vp = VoicingPlan.model_validate(vp_data)
        pid = vp.progression_candidate_id or ""
        vp_by_prog.setdefault(pid, []).append(vp)

    # Map bass lines by progression_candidate_id
    bl_by_prog: dict[str, BassLine] = {}
    for bl_data in state.get("bass_lines", []):
        bl = BassLine.model_validate(bl_data)
        pid = bl.progression_candidate_id or ""
        bl_by_prog[pid] = bl

    all_candidates: list[dict[str, Any]] = []
    all_families: list[dict[str, Any]] = []

    for candidate_data in state.get("progression_candidates", []):
        candidate = ProgressionCandidate.model_validate(candidate_data)
        plans = vp_by_prog.get(candidate.id, [])
        bass = bl_by_prog.get(candidate.id)

        if not plans or bass is None:
            logger.warning("Missing voicing plans or bass line for %s", candidate.id)
            continue

        family, candidates = assembler.assemble_family(
            progression_candidate_id=candidate.id,
            session_id=session_id,
            voicing_plans=plans,
            bass_line=bass,
            intent_tags=candidate.intent_tags,
        )

        all_candidates.extend(c.model_dump(mode="json") for c in candidates)
        all_families.append(family.model_dump(mode="json"))

    if callback:
        await callback("node_completed", {
            "node": "assemble",
            "arrangements": len(all_candidates),
            "families": len(all_families),
        })

    return {
        "arrangement_candidates": all_candidates,
        "arrangement_families": all_families,
    }
```

- [ ] **Step 5: Implement persist_realization node**

```python
# backend/src/explorator/engine/nodes/persist_realization.py

"""Persist all realization entities to Neo4j."""

import json
import logging
from typing import Any

from neo4j import AsyncDriver

from explorator.engine.realization_state import RealizationState
from explorator.graph.arrangement_candidate_repo import ArrangementCandidateRepo
from explorator.graph.arrangement_family_repo import ArrangementFamilyRepo
from explorator.graph.bass_line_repo import BassLineRepo
from explorator.graph.voicing_plan_repo import VoicingPlanRepo

logger = logging.getLogger(__name__)


async def persist_realization(
    state: RealizationState, *, driver: AsyncDriver,
) -> dict[str, Any]:
    """Write all realization entities and relationships to Neo4j."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "persist_realization"})

    vp_repo = VoicingPlanRepo(driver)
    bl_repo = BassLineRepo(driver)
    ac_repo = ArrangementCandidateRepo(driver)
    af_repo = ArrangementFamilyRepo(driver)

    saved = 0
    failed = 0

    # 1. Persist VoicingPlans
    for vp_data in state.get("voicing_plans", []):
        try:
            from explorator.models.realization import VoicingPlan
            vp = VoicingPlan.model_validate(vp_data)
            await vp_repo.create(vp)
            saved += 1
        except Exception:
            logger.exception("Failed to persist VoicingPlan")
            failed += 1

    # 2. Persist BassLines
    for bl_data in state.get("bass_lines", []):
        try:
            from explorator.models.realization import BassLine
            bl = BassLine.model_validate(bl_data)
            await bl_repo.create(bl)
            saved += 1
        except Exception:
            logger.exception("Failed to persist BassLine")
            failed += 1

    # 3. Persist ArrangementCandidates + relationships
    for ac_data in state.get("arrangement_candidates", []):
        try:
            from explorator.models.realization import ArrangementCandidate
            ac = ArrangementCandidate.model_validate(ac_data)
            await ac_repo.create(ac)

            # Create relationships
            await _create_relationship(driver, "ProgressionCandidate", ac.progression_candidate_id, "REALIZED_AS", "ArrangementCandidate", ac.id)
            if ac.voicing_plan_id:
                await _create_relationship(driver, "ArrangementCandidate", ac.id, "USES_VOICING_PLAN", "VoicingPlan", ac.voicing_plan_id)
            if ac.bass_line_id:
                await _create_relationship(driver, "ArrangementCandidate", ac.id, "USES_BASS_LINE", "BassLine", ac.bass_line_id)
            saved += 1
        except Exception:
            logger.exception("Failed to persist ArrangementCandidate")
            failed += 1

    # 4. Persist ArrangementFamilies + relationships
    for af_data in state.get("arrangement_families", []):
        try:
            from explorator.models.realization import ArrangementFamily
            af = ArrangementFamily.model_validate(af_data)
            await af_repo.create(af)

            for member_id in af.member_arrangement_candidate_ids:
                await _create_relationship(driver, "ArrangementFamily", af.id, "CONTAINS", "ArrangementCandidate", member_id)
            saved += 1
        except Exception:
            logger.exception("Failed to persist ArrangementFamily")
            failed += 1

    arrangement_ids = [ac.get("id") for ac in state.get("arrangement_candidates", [])]

    if callback:
        await callback("realization_completed", {
            "arrangement_candidate_ids": arrangement_ids,
            "saved": saved,
            "failed": failed,
        })

    return {}


async def _create_relationship(
    driver: AsyncDriver,
    from_label: str,
    from_id: str,
    rel_type: str,
    to_label: str,
    to_id: str,
) -> None:
    """Create a Neo4j relationship between two nodes."""
    query = (
        f"MATCH (a:{from_label} {{id: $from_id}}) "
        f"MATCH (b:{to_label} {{id: $to_id}}) "
        f"CREATE (a)-[:{rel_type}]->(b)"
    )
    async with driver.session() as session:
        await session.run(query, from_id=from_id, to_id=to_id)
```

- [ ] **Step 6: Commit**

```bash
git add backend/src/explorator/engine/nodes/load_context.py backend/src/explorator/engine/nodes/plan_voicings.py backend/src/explorator/engine/nodes/generate_bass.py backend/src/explorator/engine/nodes/assemble.py backend/src/explorator/engine/nodes/persist_realization.py backend/src/explorator/engine/realization_state.py
git commit -m "feat(m2a): add all realization LangGraph nodes"
```

---

## Task 11: Realization Graph and API Route

**Files:**
- Create: `backend/src/explorator/engine/realization_graph.py`
- Create: `backend/src/explorator/api/routes/realization_rounds.py`
- Modify: `backend/src/explorator/api/routes/__init__.py` (or wherever routes are registered)

- [ ] **Step 1: Implement realization graph**

```python
# backend/src/explorator/engine/realization_graph.py

"""Build and compile the M2a realization LangGraph flow."""

from functools import partial
from typing import Any

from langgraph.graph import END, StateGraph
from neo4j import AsyncDriver

from explorator.adapters.gemini import GeminiClient
from explorator.engine.nodes.assemble import assemble
from explorator.engine.nodes.generate_bass import generate_bass
from explorator.engine.nodes.load_context import load_context
from explorator.engine.nodes.persist_realization import persist_realization
from explorator.engine.nodes.plan_voicings import plan_voicings
from explorator.engine.realization_state import RealizationState


def build_realization_graph(gemini: GeminiClient, driver: AsyncDriver) -> Any:
    """Build and compile the M2a realization flow."""
    graph = StateGraph(RealizationState)

    graph.add_node("load_context", partial(load_context, driver=driver))
    graph.add_node("plan_voicings", partial(plan_voicings, gemini=gemini))
    graph.add_node("generate_bass", generate_bass)
    graph.add_node("assemble", assemble)
    graph.add_node("persist_realization", partial(persist_realization, driver=driver))

    graph.set_entry_point("load_context")
    graph.add_edge("load_context", "plan_voicings")
    graph.add_edge("plan_voicings", "generate_bass")
    graph.add_edge("generate_bass", "assemble")
    graph.add_edge("assemble", "persist_realization")
    graph.add_edge("persist_realization", END)

    return graph.compile()
```

- [ ] **Step 2: Implement API route**

```python
# backend/src/explorator/api/routes/realization_rounds.py

"""API route for triggering realization rounds."""

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from explorator.adapters.gemini import GeminiClient
from explorator.api.dependencies import get_gemini_client, get_neo4j_driver
from explorator.api.sse import SSEChannel
from explorator.engine.realization_graph import build_realization_graph
from explorator.graph.repository import BaseRepository

logger = logging.getLogger(__name__)

router = APIRouter()


class TriggerRealizationRequest(BaseModel):
    progression_candidate_ids: list[str]


class SessionRepo(BaseRepository):
    label = "Session"


class ArrangementCandidateRepo(BaseRepository):
    label = "ArrangementCandidate"


@router.post("/sessions/{session_id}/realization-rounds")
async def trigger_realization(
    session_id: str,
    request: TriggerRealizationRequest,
    gemini: GeminiClient = Depends(get_gemini_client),
    driver=Depends(get_neo4j_driver),
) -> EventSourceResponse:
    """Trigger a realization round and stream progress via SSE."""
    # Verify session exists
    repo = SessionRepo(driver)
    session = await repo.get_by_id(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if not request.progression_candidate_ids:
        raise HTTPException(status_code=422, detail="At least one progression_candidate_id required")

    channel = SSEChannel()
    graph = build_realization_graph(gemini, driver)

    initial_state = {
        "session_id": session_id,
        "progression_candidate_ids": request.progression_candidate_ids,
        "on_progress": channel.send,
    }

    async def run_and_close() -> None:
        try:
            await graph.ainvoke(initial_state)
        except ValueError as e:
            await channel.send("realization_error", {"error": str(e)})
        except Exception as e:
            logger.exception("Realization round failed")
            await channel.send("realization_error", {"error": str(e)})
        finally:
            await channel.close()

    asyncio.create_task(run_and_close())
    return EventSourceResponse(channel.stream())


@router.get("/candidates/{candidate_id}/arrangements")
async def list_arrangements(
    candidate_id: str,
    driver=Depends(get_neo4j_driver),
) -> list[dict[str, Any]]:
    """List arrangement candidates for a progression."""
    repo = ArrangementCandidateRepo(driver)
    results = await repo.query_by_property("progression_candidate_id", candidate_id)
    return results


@router.get("/arrangements/{arrangement_id}")
async def get_arrangement(
    arrangement_id: str,
    driver=Depends(get_neo4j_driver),
) -> dict[str, Any]:
    """Get full arrangement detail including voicing and bass events."""
    ac_repo = ArrangementCandidateRepo(driver)
    arrangement = await ac_repo.get_by_id(arrangement_id)
    if arrangement is None:
        raise HTTPException(status_code=404, detail="Arrangement not found")

    # Enrich with voicing plan and bass line data
    from explorator.graph.voicing_plan_repo import VoicingPlanRepo
    from explorator.graph.bass_line_repo import BassLineRepo

    vp_id = arrangement.get("voicing_plan_id")
    bl_id = arrangement.get("bass_line_id")

    if vp_id:
        vp_repo = VoicingPlanRepo(driver)
        arrangement["voicing_plan"] = await vp_repo.get_by_id(vp_id)
    if bl_id:
        bl_repo = BassLineRepo(driver)
        arrangement["bass_line"] = await bl_repo.get_by_id(bl_id)

    return arrangement
```

- [ ] **Step 3: Register the router**

Find where routers are registered (likely `backend/src/explorator/api/app.py` or similar) and add:

```python
from explorator.api.routes.realization_rounds import router as realization_router
app.include_router(realization_router, prefix="/v1")
```

- [ ] **Step 4: Commit**

```bash
git add backend/src/explorator/engine/realization_graph.py backend/src/explorator/api/routes/realization_rounds.py
git commit -m "feat(m2a): add realization graph and API routes"
```

---

## Task 12: Integration Test

**Files:**
- Create: `backend/tests/integration/test_realization_flow.py`

- [ ] **Step 1: Write integration test**

```python
# backend/tests/integration/test_realization_flow.py

"""Integration test for the M2a realization pipeline.

Requires Neo4j running on ports 7475/7688 and GEMINI_API_KEY set.
"""

import asyncio
import os

import pytest

from explorator.adapters.gemini import GeminiClient
from explorator.engine.realization_graph import build_realization_graph


@pytest.fixture
def gemini():
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        pytest.skip("GEMINI_API_KEY not set")
    return GeminiClient(api_key=api_key)


@pytest.fixture
async def driver():
    from neo4j import AsyncGraphDatabase
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7688")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "explorator")
    drv = AsyncGraphDatabase.driver(uri, auth=(user, password))
    yield drv
    await drv.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_realization_flow_end_to_end(gemini, driver):
    """Test the full realization pipeline with a real progression in Neo4j."""
    # This test requires a progression candidate to already exist in Neo4j
    # (created by running an M1 generation round first).
    # For CI, this would be seeded in a fixture.

    # For now, verify the graph compiles and the node chain is correct
    graph = build_realization_graph(gemini, driver)
    assert graph is not None

    # Verify graph has all expected nodes
    # (LangGraph compiled graph exposes node names)
    node_names = set(graph.nodes.keys())
    expected = {"load_context", "plan_voicings", "generate_bass", "assemble", "persist_realization"}
    assert expected.issubset(node_names), f"Missing nodes: {expected - node_names}"
```

- [ ] **Step 2: Run integration test**

Run: `cd backend && python -m pytest tests/integration/test_realization_flow.py -v --tb=short -m integration 2>&1 | tail -15`
Expected: PASS (graph compilation test)

- [ ] **Step 3: Run full test suite**

Run: `cd backend && python -m pytest tests/ -v --tb=short 2>&1 | tail -30`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/tests/integration/test_realization_flow.py
git commit -m "feat(m2a): add realization flow integration test"
```

---

## Task 13: Final Verification

- [ ] **Step 1: Run full test suite one last time**

Run: `cd backend && python -m pytest tests/ -v --tb=short 2>&1 | tail -40`
Expected: All tests PASS, no regressions

- [ ] **Step 2: Verify file structure matches spec**

Run: `find backend/src/explorator/domain/realization -type f && find backend/src/explorator/engine/nodes -name "*context*" -o -name "*voicing*" -o -name "*bass*" -o -name "*assemble*" -o -name "*persist_real*" && find backend/src/explorator/graph -name "*voicing*" -o -name "*bass_line*" -o -name "*arrangement*"`

Expected: All files from the spec's Section 11 exist

- [ ] **Step 3: Final commit with any fixups**

```bash
git status
# If any unstaged changes remain, stage and commit
```
