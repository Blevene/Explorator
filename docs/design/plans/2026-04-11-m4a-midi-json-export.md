# M4a — MIDI & JSON Export Implementation Plan


**Goal:** Export arrangement candidates as MIDI files (for Ableton) and human-readable JSON sidecars, with Neo4j persistence and a frontend export modal.

**Architecture:** Two renderers (MIDI via pretty_midi, JSON via stdlib) behind an orchestrator that loads arrangement data from Neo4j, renders files, persists RenderArtifact/ExportPackage nodes, and writes files to disk. Frontend export modal in React/Zustand with batch candidate selection and format options.

**Tech Stack:** Python (pretty_midi, FastAPI), Neo4j, React/Zustand, JSZip

**Spec:** `docs/design/specs/2026-04-11-m4-export-explanation-design.md` (v1.2, Sections 2.1–2.7)

---

### Task 1: Add pretty-midi dependency and EXPORT_DIR config

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/src/explorator/config.py`
- Modify: `.gitignore`

- [ ] **Step 1: Add pretty-midi to pyproject.toml**

In `backend/pyproject.toml`, add `"pretty-midi>=0.2.10"` to the dependencies list.

- [ ] **Step 2: Add EXPORT_DIR to Settings**

In `backend/src/explorator/config.py`, add to the `Settings` class:

```python
export_dir: str = "exports"
```

- [ ] **Step 3: Add exports/ to .gitignore**

Append to `.gitignore`:

```
exports/
```

- [ ] **Step 4: Install and verify**

Run: `cd backend && pip install -e . && python -c "import pretty_midi; print(pretty_midi.__version__)"`
Expected: Version prints without error.

- [ ] **Step 5: Commit**

```bash
git add backend/pyproject.toml backend/src/explorator/config.py .gitignore
git commit -m "chore: add pretty-midi dependency and EXPORT_DIR config"
```

---

### Task 2: Implement pitch_str_to_midi utility

**Files:**
- Modify: `backend/src/explorator/utils.py`
- Create: `backend/tests/unit/test_pitch_utils.py`
- Modify: `backend/src/explorator/domain/evaluation/register_density.py`

- [ ] **Step 1: Write failing tests for pitch_str_to_midi**

Create `backend/tests/unit/test_pitch_utils.py`:

```python
"""Tests for pitch_str_to_midi utility."""

import pytest

from explorator.utils import pitch_str_to_midi


class TestPitchStrToMidi:
    """Pure-Python pitch string to MIDI note number conversion."""

    def test_middle_c(self):
        assert pitch_str_to_midi("C4") == 60

    def test_a3(self):
        assert pitch_str_to_midi("A3") == 57

    def test_c3(self):
        assert pitch_str_to_midi("C3") == 48

    def test_sharp(self):
        assert pitch_str_to_midi("F#4") == 66

    def test_flat_standard(self):
        assert pitch_str_to_midi("Bb3") == 58

    def test_flat_music21_format(self):
        """music21 uses B- not Bb."""
        assert pitch_str_to_midi("B-3") == 58

    def test_e_flat_music21(self):
        assert pitch_str_to_midi("E-4") == 63

    def test_lowest_midi(self):
        assert pitch_str_to_midi("C-1") == 0

    def test_high_note(self):
        assert pitch_str_to_midi("C8") == 108

    def test_invalid_pitch_raises(self):
        with pytest.raises(ValueError):
            pitch_str_to_midi("X9")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            pitch_str_to_midi("")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/test_pitch_utils.py -v`
Expected: FAIL with `ImportError` (function not defined yet).

- [ ] **Step 3: Implement pitch_str_to_midi**

Add to `backend/src/explorator/utils.py`:

```python
import re

# Semitone offsets from C for each note name
_NOTE_SEMITONES = {
    "C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11,
}

_PITCH_RE = re.compile(r"^([A-Ga-g])([#b\-]?)(-?\d+)$")


def pitch_str_to_midi(pitch: str) -> int:
    """Convert pitch string to MIDI note number. Pure Python, no music21.

    Handles: "C4" → 60, "F#4" → 66, "Bb3" → 58, "B-3" → 58 (music21 format).
    Raises ValueError for unparseable input.
    """
    m = _PITCH_RE.match(pitch.strip())
    if not m:
        raise ValueError(f"Cannot parse pitch string: {pitch!r}")
    note, accidental, octave_str = m.groups()
    base = _NOTE_SEMITONES[note.upper()]
    octave = int(octave_str)
    midi = (octave + 1) * 12 + base
    if accidental == "#":
        midi += 1
    elif accidental in ("b", "-"):
        midi -= 1
    return midi
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/test_pitch_utils.py -v`
Expected: All 11 tests PASS.

- [ ] **Step 5: Refactor register_density.py to use shared utility**

In `backend/src/explorator/domain/evaluation/register_density.py`, replace the `_pitch_to_midi` function (around lines 148-154):

```python
# Remove the old function:
# def _pitch_to_midi(pitch: str) -> int | None:
#     try:
#         from music21 import pitch as m21pitch
#         return m21pitch.Pitch(pitch).midi
#     except Exception:
#         return None

# Replace with import:
from explorator.utils import pitch_str_to_midi
```

Then update all call sites in the same file that called `_pitch_to_midi(p)` to call `pitch_str_to_midi(p)`. The old function returned `int | None`; the new one raises `ValueError`. Wrap calls in try/except where the old code checked for `None`:

```python
try:
    midi_val = pitch_str_to_midi(p)
except ValueError:
    continue  # skip unparseable pitches, same as old None behavior
```

- [ ] **Step 6: Run full test suite to verify no regressions**

Run: `cd backend && python -m pytest tests/ -v --tb=short`
Expected: All existing tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/src/explorator/utils.py backend/tests/unit/test_pitch_utils.py backend/src/explorator/domain/evaluation/register_density.py
git commit -m "feat: add pitch_str_to_midi utility, refactor register_density"
```

---

### Task 3: Implement MIDI renderer

**Files:**
- Create: `backend/src/explorator/domain/export/__init__.py`
- Create: `backend/src/explorator/domain/export/midi_renderer.py`
- Create: `backend/tests/unit/domain/test_midi_renderer.py`

- [ ] **Step 1: Create the export domain package**

Create empty `backend/src/explorator/domain/export/__init__.py`.

- [ ] **Step 2: Write failing tests for MIDI renderer**

Create `backend/tests/unit/domain/test_midi_renderer.py`:

```python
"""Tests for MIDI renderer."""

import pretty_midi
import pytest

from explorator.domain.export.midi_renderer import (
    MidiRenderError,
    render_combined_midi,
    render_separate_midi,
)
from explorator.models.realization import BassLine, BassNoteEvent, VoicingEvent, VoicingPlan


def _make_voicing_plan() -> VoicingPlan:
    return VoicingPlan(
        id="vp-1",
        type="VoicingPlan",
        status="active",
        voicing_events=[
            VoicingEvent(bar=0, beat=1.0, duration_beats=4.0, pitches=["C3", "E3", "G3"], chord_symbol="C"),
            VoicingEvent(bar=1, beat=1.0, duration_beats=4.0, pitches=["F3", "A3", "C4"], chord_symbol="F"),
        ],
    )


def _make_bass_line() -> BassLine:
    return BassLine(
        id="bl-1",
        type="BassLine",
        status="active",
        note_events=[
            BassNoteEvent(bar=0, beat=1.0, duration_beats=2.0, pitch="C2", velocity=90),
            BassNoteEvent(bar=0, beat=3.0, duration_beats=2.0, pitch="E2", velocity=80),
            BassNoteEvent(bar=1, beat=1.0, duration_beats=4.0, pitch="F2", velocity=85),
        ],
    )


class TestRenderCombinedMidi:
    def test_returns_bytes(self):
        result = render_combined_midi(_make_voicing_plan(), _make_bass_line(), bpm=120.0)
        assert isinstance(result, bytes)

    def test_parseable_by_pretty_midi(self):
        import io
        result = render_combined_midi(_make_voicing_plan(), _make_bass_line(), bpm=120.0)
        midi = pretty_midi.PrettyMIDI(io.BytesIO(result))
        assert len(midi.instruments) == 2

    def test_chord_track_has_correct_notes(self):
        import io
        result = render_combined_midi(_make_voicing_plan(), _make_bass_line(), bpm=120.0)
        midi = pretty_midi.PrettyMIDI(io.BytesIO(result))
        chord_track = midi.instruments[0]
        # 2 chords * 3 pitches each = 6 notes
        assert len(chord_track.notes) == 6

    def test_bass_track_has_correct_notes(self):
        import io
        result = render_combined_midi(_make_voicing_plan(), _make_bass_line(), bpm=120.0)
        midi = pretty_midi.PrettyMIDI(io.BytesIO(result))
        bass_track = midi.instruments[1]
        assert len(bass_track.notes) == 3

    def test_chord_velocity_is_80(self):
        import io
        result = render_combined_midi(_make_voicing_plan(), _make_bass_line(), bpm=120.0)
        midi = pretty_midi.PrettyMIDI(io.BytesIO(result))
        for note in midi.instruments[0].notes:
            assert note.velocity == 80

    def test_bass_velocity_from_event(self):
        import io
        result = render_combined_midi(_make_voicing_plan(), _make_bass_line(), bpm=120.0)
        midi = pretty_midi.PrettyMIDI(io.BytesIO(result))
        bass_notes = sorted(midi.instruments[1].notes, key=lambda n: n.start)
        assert bass_notes[0].velocity == 90
        assert bass_notes[1].velocity == 80

    def test_time_conversion_at_120bpm(self):
        """Bar 0, beat 1 at 120 BPM = 0.0 seconds. Bar 1, beat 1 = 2.0 seconds."""
        import io
        result = render_combined_midi(_make_voicing_plan(), _make_bass_line(), bpm=120.0)
        midi = pretty_midi.PrettyMIDI(io.BytesIO(result))
        chord_notes = sorted(midi.instruments[0].notes, key=lambda n: n.start)
        assert abs(chord_notes[0].start - 0.0) < 0.01
        assert abs(chord_notes[3].start - 2.0) < 0.01  # bar 1 starts at 2.0s

    def test_gm_programs(self):
        import io
        result = render_combined_midi(_make_voicing_plan(), _make_bass_line(), bpm=120.0)
        midi = pretty_midi.PrettyMIDI(io.BytesIO(result))
        assert midi.instruments[0].program == 0   # Acoustic Grand Piano
        assert midi.instruments[1].program == 33  # Electric Bass Finger


class TestRenderSeparateMidi:
    def test_returns_dict_with_chords_and_bass(self):
        result = render_separate_midi(_make_voicing_plan(), _make_bass_line(), bpm=120.0)
        assert isinstance(result, dict)
        assert "chords" in result
        assert "bass" in result

    def test_each_file_has_one_instrument(self):
        import io
        result = render_separate_midi(_make_voicing_plan(), _make_bass_line(), bpm=120.0)
        chords_midi = pretty_midi.PrettyMIDI(io.BytesIO(result["chords"]))
        bass_midi = pretty_midi.PrettyMIDI(io.BytesIO(result["bass"]))
        assert len(chords_midi.instruments) == 1
        assert len(bass_midi.instruments) == 1


class TestMidiValidation:
    def test_empty_voicing_raises(self):
        empty_vp = VoicingPlan(id="vp-e", type="VoicingPlan", status="active", voicing_events=[])
        empty_bl = BassLine(id="bl-e", type="BassLine", status="active", note_events=[])
        with pytest.raises(MidiRenderError):
            render_combined_midi(empty_vp, empty_bl, bpm=120.0)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/domain/test_midi_renderer.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 4: Implement the MIDI renderer**

Create `backend/src/explorator/domain/export/midi_renderer.py`:

```python
"""MIDI renderer — converts VoicingPlan + BassLine to MIDI bytes."""

from __future__ import annotations

import io
from typing import Any

import pretty_midi

from explorator.models.realization import BassLine, VoicingPlan
from explorator.utils import pitch_str_to_midi


class MidiRenderError(Exception):
    """Raised when MIDI rendering fails validation."""


_CHORD_VELOCITY = 80
_CHORD_PROGRAM = 0   # Acoustic Grand Piano
_BASS_PROGRAM = 33   # Electric Bass Finger


def _time_sec(bar: int, beat: float, beats_per_bar: int, bpm: float) -> float:
    """Convert 0-indexed bar + 1-indexed beat to absolute seconds."""
    return (bar * beats_per_bar + (beat - 1)) * (60.0 / bpm)


def _duration_sec(duration_beats: float, bpm: float) -> float:
    return duration_beats * (60.0 / bpm)


def _build_tracks(
    voicing_plan: VoicingPlan,
    bass_line: BassLine,
    bpm: float,
    beats_per_bar: int,
) -> tuple[pretty_midi.Instrument, pretty_midi.Instrument]:
    """Build chord and bass Instrument objects."""
    chord_inst = pretty_midi.Instrument(program=_CHORD_PROGRAM, name="Chords")
    for ev in voicing_plan.voicing_events:
        start = _time_sec(ev.bar, ev.beat, beats_per_bar, bpm)
        end = start + _duration_sec(ev.duration_beats, bpm)
        for pitch in ev.pitches:
            midi_num = pitch_str_to_midi(pitch)
            chord_inst.notes.append(
                pretty_midi.Note(velocity=_CHORD_VELOCITY, pitch=midi_num, start=start, end=end)
            )

    bass_inst = pretty_midi.Instrument(program=_BASS_PROGRAM, name="Bass")
    for ev in bass_line.note_events:
        start = _time_sec(ev.bar, ev.beat, beats_per_bar, bpm)
        end = start + _duration_sec(ev.duration_beats, bpm)
        midi_num = pitch_str_to_midi(ev.pitch)
        bass_inst.notes.append(
            pretty_midi.Note(velocity=ev.velocity, pitch=midi_num, start=start, end=end)
        )

    total_notes = len(chord_inst.notes) + len(bass_inst.notes)
    if total_notes == 0:
        raise MidiRenderError("No notes to render — VoicingPlan and BassLine are both empty")

    return chord_inst, bass_inst


def _to_bytes(midi: pretty_midi.PrettyMIDI) -> bytes:
    buf = io.BytesIO()
    midi.write(buf)
    return buf.getvalue()


def render_combined_midi(
    voicing_plan: VoicingPlan,
    bass_line: BassLine,
    bpm: float,
    beats_per_bar: int = 4,
) -> bytes:
    """One MIDI file with two tracks (chords + bass)."""
    chord_inst, bass_inst = _build_tracks(voicing_plan, bass_line, bpm, beats_per_bar)
    midi = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    midi.instruments.append(chord_inst)
    midi.instruments.append(bass_inst)
    return _to_bytes(midi)


def render_separate_midi(
    voicing_plan: VoicingPlan,
    bass_line: BassLine,
    bpm: float,
    beats_per_bar: int = 4,
) -> dict[str, bytes]:
    """Separate MIDI files: {"chords": bytes, "bass": bytes}."""
    chord_inst, bass_inst = _build_tracks(voicing_plan, bass_line, bpm, beats_per_bar)

    chords_midi = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    chords_midi.instruments.append(chord_inst)

    bass_midi = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    bass_midi.instruments.append(bass_inst)

    return {"chords": _to_bytes(chords_midi), "bass": _to_bytes(bass_midi)}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/domain/test_midi_renderer.py -v`
Expected: All 12 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/src/explorator/domain/export/ backend/tests/unit/domain/test_midi_renderer.py
git commit -m "feat: MIDI renderer with combined and separate modes"
```

---

### Task 4: Implement JSON renderer

**Files:**
- Create: `backend/src/explorator/domain/export/json_renderer.py`
- Create: `backend/tests/unit/domain/test_json_renderer.py`

- [ ] **Step 1: Write failing tests for JSON renderer**

Create `backend/tests/unit/domain/test_json_renderer.py`:

```python
"""Tests for JSON sidecar renderer."""

import json

from explorator.domain.export.json_renderer import JsonRenderContext, render_json
from explorator.models.realization import (
    ArrangementCandidate,
    BassLine,
    BassNoteEvent,
    VoicingEvent,
    VoicingPlan,
)
from explorator.models.session import CreativeBrief, Session


def _make_context() -> JsonRenderContext:
    session = Session(
        id="sess-1", type="Session", status="active",
        metadata={"prompt": "dreamy synthwave, 4 bars"},
    )
    brief = CreativeBrief(
        id="cb-1", type="CreativeBrief", status="active",
        genre="synthwave", key_center="C", mode="major",
        tempo_hint_bpm=118, meter="4/4",
    )
    from explorator.models.harmony import ProgressionCandidate
    candidate = ProgressionCandidate(
        id="pc-1", type="ProgressionCandidate", status="active",
        session_id="sess-1", rationale="test",
        chord_symbols=["Cmaj7", "Am7", "Fmaj7", "G7"],
        roman_numerals=["Imaj7", "vim7", "IVmaj7", "V7"],
        metadata={"label": "C", "role": "best"},
    )
    arrangement = ArrangementCandidate(
        id="ac-1", type="ArrangementCandidate", status="active",
        session_id="sess-1", rationale="test",
        progression_candidate_id="pc-1",
    )
    voicing_plan = VoicingPlan(
        id="vp-1", type="VoicingPlan", status="active",
        voicing_events=[
            VoicingEvent(bar=0, beat=1.0, duration_beats=4.0, pitches=["C3", "E3", "G3", "B3"], chord_symbol="Cmaj7"),
        ],
    )
    bass_line = BassLine(
        id="bl-1", type="BassLine", status="active",
        note_events=[
            BassNoteEvent(bar=0, beat=1.0, duration_beats=2.0, pitch="C2", velocity=90),
        ],
    )
    return JsonRenderContext(
        session=session,
        creative_brief=brief,
        candidate=candidate,
        arrangement=arrangement,
        voicing_plan=voicing_plan,
        bass_line=bass_line,
        scores={"tension_curve": 0.82, "voice_leading": 0.91},
        mutation_summaries=["reharmonize bar 3"],
    )


class TestRenderJson:
    def test_returns_valid_json(self):
        result = render_json(_make_context())
        parsed = json.loads(result)
        assert "explorator_version" in parsed

    def test_session_section(self):
        parsed = json.loads(render_json(_make_context()))
        assert parsed["session"]["genre"] == "synthwave"
        assert parsed["session"]["bpm"] == 118

    def test_candidate_chords(self):
        parsed = json.loads(render_json(_make_context()))
        assert parsed["candidate"]["chords"] == ["Cmaj7", "Am7", "Fmaj7", "G7"]

    def test_candidate_scores(self):
        parsed = json.loads(render_json(_make_context()))
        assert parsed["candidate"]["scores"]["voice_leading"] == 0.91

    def test_no_neo4j_ids(self):
        """Internal IDs like 'vp-1', 'bl-1' should not appear."""
        result = render_json(_make_context())
        assert "vp-1" not in result
        assert "bl-1" not in result
        assert "ac-1" not in result
        assert "cb-1" not in result

    def test_lineage_mutations(self):
        parsed = json.loads(render_json(_make_context()))
        assert parsed["candidate"]["lineage"]["mutations"] == ["reharmonize bar 3"]

    def test_voicings_included(self):
        parsed = json.loads(render_json(_make_context()))
        assert len(parsed["candidate"]["voicings"]) == 1
        assert parsed["candidate"]["voicings"][0]["pitches"] == ["C3", "E3", "G3", "B3"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/domain/test_json_renderer.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement the JSON renderer**

Create `backend/src/explorator/domain/export/json_renderer.py`:

```python
"""JSON sidecar renderer — human-readable export for DAW reference."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from explorator.models.realization import ArrangementCandidate, BassLine, VoicingPlan
from explorator.models.session import CreativeBrief, Session

# Forward-declared to avoid circular imports at runtime.
from explorator.models.harmony import ProgressionCandidate

_VERSION = "0.4.0"


@dataclass
class JsonRenderContext:
    """All data needed to render a JSON sidecar for one candidate."""

    session: Session
    creative_brief: CreativeBrief
    candidate: ProgressionCandidate
    arrangement: ArrangementCandidate
    voicing_plan: VoicingPlan
    bass_line: BassLine
    scores: dict[str, float]
    mutation_summaries: list[str]


def render_json(ctx: JsonRenderContext) -> str:
    """Produce a human-readable JSON sidecar string."""
    from explorator.utils import utc_now

    doc: dict[str, Any] = {
        "explorator_version": _VERSION,
        "exported_at": utc_now().isoformat(),
        "session": {
            "id": ctx.session.id,
            "prompt": ctx.session.metadata.get("prompt", ""),
            "genre": ctx.creative_brief.genre,
            "bpm": ctx.creative_brief.tempo_hint_bpm,
            "key": f"{ctx.creative_brief.key_center or 'C'} {ctx.creative_brief.mode or 'major'}",
            "meter": ctx.creative_brief.meter,
        },
        "candidate": {
            "id": ctx.candidate.id,
            "label": ctx.candidate.metadata.get("label", ""),
            "role": ctx.candidate.metadata.get("role", ""),
            "chords": ctx.candidate.chord_symbols,
            "roman_numerals": ctx.candidate.roman_numerals,
            "scores": ctx.scores,
            "voicings": [
                {
                    "bar": ev.bar,
                    "beat": ev.beat,
                    "chord": ev.chord_symbol,
                    "pitches": ev.pitches,
                    "duration_beats": ev.duration_beats,
                }
                for ev in ctx.voicing_plan.voicing_events
            ],
            "bass_line": [
                {
                    "bar": ev.bar,
                    "beat": ev.beat,
                    "pitch": ev.pitch,
                    "velocity": ev.velocity,
                    "duration_beats": ev.duration_beats,
                }
                for ev in ctx.bass_line.note_events
            ],
            "lineage": {
                "origin_round": ctx.candidate.metadata.get("origin_round", 1),
                "mutations": ctx.mutation_summaries,
            },
        },
    }
    return json.dumps(doc, indent=2)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/domain/test_json_renderer.py -v`
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/domain/export/json_renderer.py backend/tests/unit/domain/test_json_renderer.py
git commit -m "feat: JSON sidecar renderer for DAW reference export"
```

---

### Task 5: Update models and add Neo4j repositories

**Files:**
- Modify: `backend/src/explorator/models/export.py`
- Create: `backend/src/explorator/graph/render_artifact_repo.py`
- Create: `backend/src/explorator/graph/export_package_repo.py`

- [ ] **Step 1: Add session_id to RenderArtifact and CandidateExplanation**

In `backend/src/explorator/models/export.py`, add `session_id: str` to `RenderArtifact`:

```python
class RenderArtifact(BaseEntity):
    """Exported render or file."""

    session_id: str
    candidate_id: str
    artifact_type: str
    path: str
    render_metadata: dict[str, Any] = Field(default_factory=dict)
```

And add `session_id: str` to `CandidateExplanation`:

```python
class CandidateExplanation(BaseEntity):
    """Human-readable explanation of one result."""

    session_id: str
    candidate_id: str
    summary: str = ""
    why_it_works: list[str] = Field(default_factory=list)
    what_is_experimental: list[str] = Field(default_factory=list)
    recommended_use_cases: list[str] = Field(default_factory=list)
```

- [ ] **Step 2: Create RenderArtifactRepo**

Create `backend/src/explorator/graph/render_artifact_repo.py`:

```python
"""Repository for RenderArtifact nodes."""

from explorator.graph.repository import BaseRepository


class RenderArtifactRepo(BaseRepository):
    label = "RenderArtifact"
```

- [ ] **Step 3: Create ExportPackageRepo**

Create `backend/src/explorator/graph/export_package_repo.py`:

```python
"""Repository for ExportPackage nodes."""

from explorator.graph.repository import BaseRepository


class ExportPackageRepo(BaseRepository):
    label = "ExportPackage"
```

- [ ] **Step 4: Run existing tests to check for regressions from model changes**

Run: `cd backend && python -m pytest tests/ -v --tb=short`
Expected: All pass. The new `session_id` fields have no defaults, so any test constructing `RenderArtifact` or `CandidateExplanation` without `session_id` will fail — check and fix any such tests.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/models/export.py backend/src/explorator/graph/render_artifact_repo.py backend/src/explorator/graph/export_package_repo.py
git commit -m "feat: add session_id to RenderArtifact/CandidateExplanation, create export repos"
```

---

### Task 6: Implement export orchestrator

**Files:**
- Create: `backend/src/explorator/domain/export/orchestrator.py`
- Create: `backend/tests/unit/domain/test_export_orchestrator.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/domain/test_export_orchestrator.py`:

```python
"""Tests for export orchestrator — file naming and package assembly."""

import json
import os
import shutil
import tempfile

import pytest

from explorator.domain.export.orchestrator import (
    ExportRequest,
    build_filename,
    render_and_write_artifacts,
)
from explorator.models.realization import (
    BassLine,
    BassNoteEvent,
    VoicingEvent,
    VoicingPlan,
)


class TestBuildFilename:
    def test_midi_combined(self):
        name = build_filename("C", "a3f2b1", "midi_combined")
        assert name == "candidate-C-a3f2b1-chords-bass.mid"

    def test_midi_separate_chords(self):
        name = build_filename("C", "a3f2b1", "midi_separate_chords")
        assert name == "candidate-C-a3f2b1-chords.mid"

    def test_midi_separate_bass(self):
        name = build_filename("C", "a3f2b1", "midi_separate_bass")
        assert name == "candidate-C-a3f2b1-bass.mid"

    def test_json(self):
        name = build_filename("E", "d7c4e9", "json")
        assert name == "candidate-E-d7c4e9.json"


class TestRenderAndWriteArtifacts:
    def test_writes_combined_midi_to_disk(self, tmp_path):
        vp = VoicingPlan(
            id="vp-1", type="VoicingPlan", status="active",
            voicing_events=[
                VoicingEvent(bar=0, beat=1.0, duration_beats=4.0, pitches=["C3", "E3"], chord_symbol="C"),
            ],
        )
        bl = BassLine(
            id="bl-1", type="BassLine", status="active",
            note_events=[
                BassNoteEvent(bar=0, beat=1.0, duration_beats=4.0, pitch="C2", velocity=80),
            ],
        )
        req = ExportRequest(
            label="C",
            short_id="a3f2b1",
            voicing_plan=vp,
            bass_line=bl,
            bpm=120.0,
            beats_per_bar=4,
            formats=["midi_combined"],
            output_dir=str(tmp_path),
        )
        artifacts = render_and_write_artifacts(req)
        assert len(artifacts) == 1
        assert artifacts[0]["artifact_type"] == "midi_combined"
        assert os.path.exists(artifacts[0]["path"])

    def test_writes_all_formats(self, tmp_path):
        vp = VoicingPlan(
            id="vp-1", type="VoicingPlan", status="active",
            voicing_events=[
                VoicingEvent(bar=0, beat=1.0, duration_beats=4.0, pitches=["C3"], chord_symbol="C"),
            ],
        )
        bl = BassLine(
            id="bl-1", type="BassLine", status="active",
            note_events=[
                BassNoteEvent(bar=0, beat=1.0, duration_beats=4.0, pitch="C2", velocity=80),
            ],
        )
        req = ExportRequest(
            label="C",
            short_id="a3f2b1",
            voicing_plan=vp,
            bass_line=bl,
            bpm=120.0,
            beats_per_bar=4,
            formats=["midi_combined", "midi_separate", "json"],
            output_dir=str(tmp_path),
            json_context=None,  # JSON rendering tested separately; skip if None
        )
        artifacts = render_and_write_artifacts(req)
        # midi_combined (1) + midi_separate (2: chords + bass) = 3 files (no json without context)
        assert len(artifacts) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/domain/test_export_orchestrator.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement the orchestrator**

Create `backend/src/explorator/domain/export/orchestrator.py`:

```python
"""Export orchestrator — coordinates rendering and file writing."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from explorator.domain.export.json_renderer import JsonRenderContext, render_json
from explorator.domain.export.midi_renderer import (
    MidiRenderError,
    render_combined_midi,
    render_separate_midi,
)
from explorator.models.realization import BassLine, VoicingPlan


_FILENAME_MAP = {
    "midi_combined": "candidate-{label}-{sid}-chords-bass.mid",
    "midi_separate_chords": "candidate-{label}-{sid}-chords.mid",
    "midi_separate_bass": "candidate-{label}-{sid}-bass.mid",
    "json": "candidate-{label}-{sid}.json",
}


def build_filename(label: str, short_id: str, artifact_type: str) -> str:
    """Build the export filename for a given artifact type."""
    template = _FILENAME_MAP[artifact_type]
    return template.format(label=label, sid=short_id)


@dataclass
class ExportRequest:
    """All data needed to render artifacts for one candidate."""

    label: str
    short_id: str
    voicing_plan: VoicingPlan
    bass_line: BassLine
    bpm: float
    beats_per_bar: int
    formats: list[str]
    output_dir: str
    json_context: JsonRenderContext | None = None


def render_and_write_artifacts(req: ExportRequest) -> list[dict[str, Any]]:
    """Render requested formats and write to disk. Returns artifact metadata list."""
    os.makedirs(req.output_dir, exist_ok=True)
    artifacts: list[dict[str, Any]] = []

    for fmt in req.formats:
        if fmt == "midi_combined":
            data = render_combined_midi(req.voicing_plan, req.bass_line, req.bpm, req.beats_per_bar)
            fname = build_filename(req.label, req.short_id, "midi_combined")
            path = os.path.join(req.output_dir, fname)
            with open(path, "wb") as f:
                f.write(data)
            artifacts.append({"artifact_type": "midi_combined", "path": path, "filename": fname})

        elif fmt == "midi_separate":
            separate = render_separate_midi(req.voicing_plan, req.bass_line, req.bpm, req.beats_per_bar)
            for voice, key in [("chords", "chords"), ("bass", "bass")]:
                fname = build_filename(req.label, req.short_id, f"midi_separate_{voice}")
                path = os.path.join(req.output_dir, fname)
                with open(path, "wb") as f:
                    f.write(separate[key])
                artifacts.append({"artifact_type": f"midi_separate_{voice}", "path": path, "filename": fname})

        elif fmt == "json":
            if req.json_context is None:
                continue
            data_str = render_json(req.json_context)
            fname = build_filename(req.label, req.short_id, "json")
            path = os.path.join(req.output_dir, fname)
            with open(path, "w") as f:
                f.write(data_str)
            artifacts.append({"artifact_type": "json", "path": path, "filename": fname})

    return artifacts
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/domain/test_export_orchestrator.py -v`
Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/domain/export/orchestrator.py backend/tests/unit/domain/test_export_orchestrator.py
git commit -m "feat: export orchestrator with file naming and disk write"
```

---

### Task 7: Implement export API route

**Files:**
- Create: `backend/src/explorator/api/routes/exports.py`
- Modify: `backend/src/explorator/api/app.py`
- Modify: `backend/src/explorator/api/routes/sessions.py`

- [ ] **Step 1: Create the exports router**

Create `backend/src/explorator/api/routes/exports.py`:

```python
"""Export API routes — create packages, list packages, download artifacts."""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from neo4j import AsyncDriver
from pydantic import BaseModel

from explorator.api.deps import get_neo4j_driver
from explorator.config import Settings, get_settings
from explorator.domain.export.json_renderer import JsonRenderContext, render_json
from explorator.domain.export.orchestrator import ExportRequest, render_and_write_artifacts
from explorator.graph.export_package_repo import ExportPackageRepo
from explorator.graph.render_artifact_repo import RenderArtifactRepo
from explorator.graph.repository import BaseRepository
from explorator.utils import utc_now

router = APIRouter()


class ExportRequestBody(BaseModel):
    arrangement_candidate_ids: list[str]
    formats: list[str]


@router.post("/sessions/{session_id}/export")
async def create_export(
    session_id: str,
    body: ExportRequestBody,
    driver: AsyncDriver = Depends(get_neo4j_driver),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Create an export package for selected candidates and formats."""
    from uuid import uuid4

    pkg_repo = ExportPackageRepo(driver)
    artifact_repo = RenderArtifactRepo(driver)

    package_id = str(uuid4())
    output_dir = os.path.join(settings.export_dir, session_id, package_id)
    all_artifacts: list[dict[str, Any]] = []
    included_candidate_ids: list[str] = []

    # Load shared session data once
    async with driver.session() as neo_session:
        # Get creative brief for BPM and meter
        brief_result = await neo_session.run(
            "MATCH (n:CreativeBrief) WHERE n.session_id = $sid RETURN n LIMIT 1",
            sid=session_id,
        )
        brief_record = await brief_result.single()
        if not brief_record:
            raise HTTPException(status_code=404, detail="Session has no creative brief")
        brief_props = dict(brief_record["n"])
        bpm = brief_props.get("tempo_hint_bpm", 120)
        meter = brief_props.get("meter", "4/4")
        beats_per_bar = int(meter.split("/")[0]) if "/" in str(meter) else 4

    for ac_id in body.arrangement_candidate_ids:
        # Load arrangement + related data
        async with driver.session() as neo_session:
            ac_result = await neo_session.run(
                "MATCH (ac:ArrangementCandidate {id: $id}) RETURN ac", id=ac_id,
            )
            ac_record = await ac_result.single()
            if not ac_record:
                continue
            ac_props = dict(ac_record["ac"])

            vp_id = ac_props.get("voicing_plan_id")
            bl_id = ac_props.get("bass_line_id")
            pc_id = ac_props.get("progression_candidate_id")
            if not vp_id or not bl_id:
                continue

            vp_result = await neo_session.run("MATCH (n:VoicingPlan {id: $id}) RETURN n", id=vp_id)
            bl_result = await neo_session.run("MATCH (n:BassLine {id: $id}) RETURN n", id=bl_id)
            vp_record = await vp_result.single()
            bl_record = await bl_result.single()
            if not vp_record or not bl_record:
                continue

        from explorator.graph.repository import BaseRepository
        vp_props = BaseRepository._neo4j_deserialize(dict(vp_record["n"]))
        bl_props = BaseRepository._neo4j_deserialize(dict(bl_record["n"]))

        from explorator.models.realization import VoicingPlan, BassLine
        voicing_plan = VoicingPlan(**vp_props)
        bass_line = BassLine(**bl_props)

        label = ac_props.get("metadata", {}).get("label", ac_id[:6]) if isinstance(ac_props.get("metadata"), dict) else ac_id[:6]
        short_id = ac_id[:6]

        # Build JSON context if json format requested
        json_ctx = None
        if "json" in body.formats and pc_id:
            async with driver.session() as neo_session:
                pc_result = await neo_session.run("MATCH (n:ProgressionCandidate {id: $id}) RETURN n", id=pc_id)
                sess_result = await neo_session.run("MATCH (n:Session {id: $id}) RETURN n", id=session_id)
                cb_result = await neo_session.run(
                    "MATCH (n:CreativeBrief) WHERE n.session_id = $sid RETURN n LIMIT 1", sid=session_id
                )
                pc_record = await pc_result.single()
                sess_record = await sess_result.single()
                cb_record = await cb_result.single()

            if pc_record and sess_record and cb_record:
                from explorator.models.harmony import ProgressionCandidate
                from explorator.models.session import Session, CreativeBrief

                pc_props = BaseRepository._neo4j_deserialize(dict(pc_record["n"]))
                sess_props = BaseRepository._neo4j_deserialize(dict(sess_record["n"]))
                cb_props = BaseRepository._neo4j_deserialize(dict(cb_record["n"]))

                # Gather scores from AggregateScorecard if available
                async with driver.session() as neo_session:
                    score_result = await neo_session.run(
                        "MATCH (n:AggregateScorecard) WHERE n.candidate_id = $cid RETURN n LIMIT 1",
                        cid=ac_id,
                    )
                    score_record = await score_result.single()
                scores = {}
                if score_record:
                    sc_props = BaseRepository._neo4j_deserialize(dict(score_record["n"]))
                    scores = sc_props.get("dimension_scores", {})

                # Gather mutation summaries
                async with driver.session() as neo_session:
                    mut_result = await neo_session.run(
                        "MATCH (n:MutationRecord) WHERE n.source_candidate_id = $cid OR n.result_candidate_id = $cid RETURN n.mutation_type as mt",
                        cid=pc_props.get("id", ""),
                    )
                    mut_records = [r["mt"] async for r in mut_result]

                json_ctx = JsonRenderContext(
                    session=Session(**sess_props),
                    creative_brief=CreativeBrief(**cb_props),
                    candidate=ProgressionCandidate(**pc_props),
                    arrangement=ArrangementCandidate(**{**ac_props, "session_id": session_id}),
                    voicing_plan=voicing_plan,
                    bass_line=bass_line,
                    scores=scores,
                    mutation_summaries=mut_records,
                )

        from explorator.models.realization import ArrangementCandidate
        req = ExportRequest(
            label=label,
            short_id=short_id,
            voicing_plan=voicing_plan,
            bass_line=bass_line,
            bpm=float(bpm),
            beats_per_bar=beats_per_bar,
            formats=body.formats,
            output_dir=output_dir,
            json_context=json_ctx,
        )

        artifacts = render_and_write_artifacts(req)
        all_artifacts.extend(artifacts)
        included_candidate_ids.append(ac_id)

    if not all_artifacts:
        raise HTTPException(status_code=400, detail="No exportable candidates found")

    # Persist RenderArtifact nodes
    artifact_ids: list[str] = []
    for art in all_artifacts:
        from uuid import uuid4 as uuid4_art
        art_id = str(uuid4_art())
        await artifact_repo.create({
            "id": art_id,
            "type": "RenderArtifact",
            "status": "active",
            "session_id": session_id,
            "candidate_id": included_candidate_ids[0] if included_candidate_ids else "",
            "artifact_type": art["artifact_type"],
            "path": art["path"],
            "render_metadata": {"filename": art["filename"]},
        })
        art["id"] = art_id
        artifact_ids.append(art_id)

    # Persist ExportPackage node
    await pkg_repo.create({
        "id": package_id,
        "type": "ExportPackage",
        "status": "active",
        "session_id": session_id,
        "included_candidate_ids": included_candidate_ids,
        "included_artifact_ids": artifact_ids,
        "formats": body.formats,
        "notes": [],
    })

    # Create relationships
    async with driver.session() as neo_session:
        await neo_session.run(
            "MATCH (s:Session {id: $sid}), (pkg:ExportPackage {id: $pid}) MERGE (s)-[:HAS_EXPORT]->(pkg)",
            sid=session_id, pid=package_id,
        )
        for art in all_artifacts:
            await neo_session.run(
                "MATCH (a:RenderArtifact {id: $aid}), (ac:ArrangementCandidate {id: $acid}) MERGE (a)-[:RENDERS]->(ac)",
                aid=art["id"], acid=included_candidate_ids[0] if included_candidate_ids else "",
            )
            await neo_session.run(
                "MATCH (pkg:ExportPackage {id: $pid}), (a:RenderArtifact {id: $aid}) MERGE (pkg)-[:INCLUDES]->(a)",
                pid=package_id, aid=art["id"],
            )
        for ac_id in included_candidate_ids:
            await neo_session.run(
                "MATCH (pkg:ExportPackage {id: $pid}), (ac:ArrangementCandidate {id: $acid}) MERGE (pkg)-[:INCLUDES_CANDIDATE]->(ac)",
                pid=package_id, acid=ac_id,
            )

    return {
        "id": package_id,
        "session_id": session_id,
        "included_candidate_ids": included_candidate_ids,
        "formats": body.formats,
        "artifacts": [{"id": a["id"], "filename": a["filename"], "artifact_type": a["artifact_type"]} for a in all_artifacts],
    }


@router.get("/sessions/{session_id}/exports")
async def list_exports(
    session_id: str,
    driver: AsyncDriver = Depends(get_neo4j_driver),
) -> list[dict[str, Any]]:
    """List all export packages for a session."""
    repo = ExportPackageRepo(driver)
    return await repo.query_by_property("session_id", session_id)


@router.get("/exports/{package_id}/artifacts/{artifact_id}/download")
async def download_artifact(
    package_id: str,
    artifact_id: str,
    driver: AsyncDriver = Depends(get_neo4j_driver),
) -> FileResponse:
    """Download a single export artifact."""
    repo = RenderArtifactRepo(driver)
    artifacts = await repo.query_by_property("id", artifact_id)
    if not artifacts:
        raise HTTPException(status_code=404, detail="Artifact not found")
    artifact = artifacts[0]
    path = artifact.get("path", "")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Artifact file not found on disk")

    filename = artifact.get("render_metadata", {}).get("filename", os.path.basename(path))
    media_type = "audio/midi" if path.endswith(".mid") else "application/json"
    return FileResponse(path, media_type=media_type, filename=filename)
```

- [ ] **Step 2: Register the router in app.py**

In `backend/src/explorator/api/app.py`, add the import and registration:

```python
from explorator.api.routes import exports
# ... existing includes ...
app.include_router(exports.router, prefix="/v1")
```

- [ ] **Step 3: Update session delete for filesystem cleanup**

In `backend/src/explorator/api/routes/sessions.py`, update the `delete_session` handler to delete files **before** Neo4j nodes:

```python
import os
import shutil
from explorator.config import Settings, get_settings

# Add settings dependency to the handler signature:
# async def delete_session(..., settings: Settings = Depends(get_settings)):

# Before the existing Cypher DELETE, add:
export_dir = os.path.join(settings.export_dir, session_id)
if os.path.isdir(export_dir):
    shutil.rmtree(export_dir)

# Then the existing DETACH DELETE queries follow
```

- [ ] **Step 4: Verify the server starts**

Run: `cd backend && python -m uvicorn explorator.api.app:app --host 0.0.0.0 --port 8000 &`
Then: `curl -s http://0.0.0.0:8000/v1/sessions | head -c 100`
Expected: JSON response (empty list or existing sessions). Kill the server after verification.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/api/routes/exports.py backend/src/explorator/api/app.py backend/src/explorator/api/routes/sessions.py
git commit -m "feat: export API route with create, list, download endpoints"
```

---

### Task 8: Add jszip dependency and frontend export store

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/src/stores/exportStore.ts`
- Modify: `frontend/src/services/api.ts`

- [ ] **Step 1: Install jszip**

Run: `cd frontend && npm install jszip`

- [ ] **Step 2: Add API client functions**

In `frontend/src/services/api.ts`, add:

```typescript
export interface ExportArtifact {
  id: string;
  filename: string;
  artifact_type: string;
}

export interface ExportPackage {
  id: string;
  session_id: string;
  included_candidate_ids: string[];
  formats: string[];
  artifacts: ExportArtifact[];
}

export async function createExportPackage(
  sessionId: string,
  arrangementCandidateIds: string[],
  formats: string[],
): Promise<ExportPackage> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ arrangement_candidate_ids: arrangementCandidateIds, formats }),
  });
  if (!res.ok) throw new Error(`Export failed: ${res.statusText}`);
  return res.json();
}

export async function listExportPackages(sessionId: string): Promise<ExportPackage[]> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/exports`);
  if (!res.ok) throw new Error(`Failed to list exports: ${res.statusText}`);
  return res.json();
}

export function getArtifactDownloadUrl(packageId: string, artifactId: string): string {
  return `${API_BASE}/exports/${packageId}/artifacts/${artifactId}/download`;
}
```

- [ ] **Step 3: Create exportStore.ts**

Create `frontend/src/stores/exportStore.ts`:

```typescript
import { create } from "zustand";
import {
  createExportPackage,
  listExportPackages,
  type ExportPackage,
} from "../services/api";

interface ExportState {
  packages: ExportPackage[];
  isExporting: boolean;
  exportError: string | null;
  lastExportedPackage: ExportPackage | null;
  fetchPackages: (sessionId: string) => Promise<void>;
  createExport: (
    sessionId: string,
    candidateIds: string[],
    formats: string[],
  ) => Promise<void>;
  clearError: () => void;
  reset: () => void;
}

export const useExportStore = create<ExportState>((set) => ({
  packages: [],
  isExporting: false,
  exportError: null,
  lastExportedPackage: null,

  fetchPackages: async (sessionId) => {
    const packages = await listExportPackages(sessionId);
    set({ packages });
  },

  createExport: async (sessionId, candidateIds, formats) => {
    set({ isExporting: true, exportError: null });
    try {
      const pkg = await createExportPackage(sessionId, candidateIds, formats);
      set((state) => ({
        isExporting: false,
        lastExportedPackage: pkg,
        packages: [...state.packages, pkg],
      }));
    } catch (err) {
      set({
        isExporting: false,
        exportError: err instanceof Error ? err.message : "Export failed",
      });
    }
  },

  clearError: () => set({ exportError: null }),
  reset: () =>
    set({
      packages: [],
      isExporting: false,
      exportError: null,
      lastExportedPackage: null,
    }),
}));
```

- [ ] **Step 4: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no TypeScript errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/services/api.ts frontend/src/stores/exportStore.ts
git commit -m "feat: frontend export store and API client for MIDI/JSON export"
```

---

### Task 9: Build ExportModal component

**Files:**
- Create: `frontend/src/components/ExportModal.tsx`
- Modify: `frontend/src/views/SessionWorkspace.tsx`

- [ ] **Step 1: Create ExportModal.tsx**

Create `frontend/src/components/ExportModal.tsx`:

```tsx
import { useState } from "react";
import JSZip from "jszip";
import { useExportStore } from "../stores/exportStore";
import { getArtifactDownloadUrl } from "../services/api";
import type { ExportPackage } from "../services/api";

interface Props {
  sessionId: string;
  candidates: Array<{
    id: string;
    label: string;
    role: string;
    chords: string[];
  }>;
  onClose: () => void;
}

export default function ExportModal({ sessionId, candidates, onClose }: Props) {
  const { isExporting, exportError, lastExportedPackage, createExport, packages } =
    useExportStore();

  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => {
    const finalists = new Set<string>();
    for (const c of candidates) {
      if (["best", "runner-up", "wildcard"].includes(c.role)) {
        finalists.add(c.id);
      }
    }
    return finalists.size > 0 ? finalists : new Set(candidates.map((c) => c.id));
  });

  const [formats, setFormats] = useState<Set<string>>(
    new Set(["midi_combined", "json"]),
  );

  const toggleCandidate = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleFormat = (fmt: string) => {
    setFormats((prev) => {
      const next = new Set(prev);
      if (next.has(fmt)) next.delete(fmt);
      else next.add(fmt);
      return next;
    });
  };

  const handleExport = async () => {
    await createExport(sessionId, Array.from(selectedIds), Array.from(formats));
  };

  const handleDownloadAll = async (pkg: ExportPackage) => {
    const zip = new JSZip();
    for (const art of pkg.artifacts) {
      const url = getArtifactDownloadUrl(pkg.id, art.id);
      const res = await fetch(url);
      const blob = await res.blob();
      zip.file(art.filename, blob);
    }
    const content = await zip.generateAsync({ type: "blob" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(content);
    a.download = `export-${pkg.id.slice(0, 6)}.zip`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg rounded-lg bg-[var(--surface-1)] p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">
            Export Session
          </h2>
          <button
            onClick={onClose}
            className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          >
            ✕
          </button>
        </div>

        {/* Candidate selector */}
        <div className="mb-4">
          <div className="mb-2 text-xs font-semibold uppercase text-[var(--text-secondary)]">
            Select candidates
          </div>
          {candidates.map((c) => (
            <label
              key={c.id}
              className="mb-1 flex cursor-pointer items-center gap-2 rounded border border-[var(--border)] p-2 hover:bg-[var(--surface-2)]"
            >
              <input
                type="checkbox"
                checked={selectedIds.has(c.id)}
                onChange={() => toggleCandidate(c.id)}
              />
              <span className="font-semibold">{c.label}</span>
              {c.role && (
                <span className="rounded bg-[var(--surface-2)] px-1.5 py-0.5 text-[10px]">
                  {c.role}
                </span>
              )}
              <span className="text-xs text-[var(--text-secondary)]">
                {c.chords.join(" → ")}
              </span>
            </label>
          ))}
        </div>

        {/* Format selector */}
        <div className="mb-4">
          <div className="mb-2 text-xs font-semibold uppercase text-[var(--text-secondary)]">
            Formats
          </div>
          <div className="flex gap-4">
            {[
              { key: "midi_combined", label: "Combined MIDI" },
              { key: "midi_separate", label: "Separate MIDI" },
              { key: "json", label: "JSON" },
            ].map(({ key, label }) => (
              <label key={key} className="flex cursor-pointer items-center gap-1 text-sm">
                <input
                  type="checkbox"
                  checked={formats.has(key)}
                  onChange={() => toggleFormat(key)}
                />
                {label}
              </label>
            ))}
          </div>
        </div>

        {/* Export button */}
        <button
          onClick={handleExport}
          disabled={isExporting || selectedIds.size === 0 || formats.size === 0}
          className="w-full rounded bg-[var(--accent-primary)] py-2 text-sm font-semibold text-white disabled:opacity-50"
        >
          {isExporting
            ? "Exporting..."
            : `Export ${selectedIds.size} candidate${selectedIds.size !== 1 ? "s" : ""}`}
        </button>

        {exportError && (
          <div className="mt-2 text-sm text-red-400">{exportError}</div>
        )}

        {/* Post-export: download links */}
        {lastExportedPackage && (
          <div className="mt-4 rounded border border-[var(--border)] p-3">
            <div className="mb-2 text-xs font-semibold text-[var(--text-secondary)]">
              Export complete
            </div>
            {lastExportedPackage.artifacts.map((art) => (
              <a
                key={art.id}
                href={getArtifactDownloadUrl(lastExportedPackage.id, art.id)}
                download
                className="mb-1 block text-sm text-[var(--accent-primary)] underline"
              >
                {art.filename}
              </a>
            ))}
            {lastExportedPackage.artifacts.length > 1 && (
              <button
                onClick={() => handleDownloadAll(lastExportedPackage)}
                className="mt-2 w-full rounded border border-[var(--accent-primary)] py-1 text-sm text-[var(--accent-primary)]"
              >
                Download All (.zip)
              </button>
            )}
          </div>
        )}

        {/* Export history */}
        {packages.length > 0 && (
          <details className="mt-4">
            <summary className="cursor-pointer text-xs text-[var(--text-secondary)]">
              Previous exports ({packages.length})
            </summary>
            <div className="mt-2 space-y-1">
              {packages.map((pkg) => (
                <div key={pkg.id} className="text-xs text-[var(--text-secondary)]">
                  {pkg.formats.join(", ")} — {pkg.included_candidate_ids.length} candidates
                </div>
              ))}
            </div>
          </details>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add Export button and modal to SessionWorkspace**

In `frontend/src/views/SessionWorkspace.tsx`, add the export modal integration:

1. Import the modal and store:
```tsx
import ExportModal from "../components/ExportModal";
import { useExportStore } from "../stores/exportStore";
```

2. Add state for modal visibility:
```tsx
const [showExportModal, setShowExportModal] = useState(false);
const { fetchPackages } = useExportStore();
```

3. Add an "Export" button in the toolbar area (alongside existing controls):
```tsx
<button
  onClick={() => {
    fetchPackages(sessionId);
    setShowExportModal(true);
  }}
  className="rounded border border-[var(--border)] px-3 py-1 text-sm hover:bg-[var(--surface-2)]"
>
  Export
</button>
```

4. Render the modal conditionally:
```tsx
{showExportModal && (
  <ExportModal
    sessionId={sessionId}
    candidates={/* map arrangement candidates to {id, label, role, chords} */}
    onClose={() => setShowExportModal(false)}
  />
)}
```

The exact integration depends on the current SessionWorkspace layout — the implementer should read the file and place the button in the toolbar section and the modal at the component root level.

- [ ] **Step 3: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ExportModal.tsx frontend/src/views/SessionWorkspace.tsx
git commit -m "feat: ExportModal component with batch export and zip download"
```

---

### Task 10: Integration test — full export flow

**Files:**
- Create: `backend/tests/integration/test_export_flow.py`

- [ ] **Step 1: Write the integration test**

Create `backend/tests/integration/test_export_flow.py`:

```python
"""Integration test — full export flow from Neo4j data to files on disk."""

import json
import os
import shutil
import tempfile

import pretty_midi
import pytest

from explorator.domain.export.json_renderer import JsonRenderContext, render_json
from explorator.domain.export.midi_renderer import render_combined_midi, render_separate_midi
from explorator.domain.export.orchestrator import ExportRequest, render_and_write_artifacts
from explorator.models.realization import (
    ArrangementCandidate,
    BassLine,
    BassNoteEvent,
    VoicingEvent,
    VoicingPlan,
)
from explorator.models.session import CreativeBrief, Session
from explorator.models.harmony import ProgressionCandidate


@pytest.fixture
def export_dir(tmp_path):
    return str(tmp_path / "exports")


def test_full_export_produces_valid_files(export_dir):
    """Export combined MIDI + JSON for one candidate, verify both files."""
    vp = VoicingPlan(
        id="vp-int", type="VoicingPlan", status="active",
        voicing_events=[
            VoicingEvent(bar=0, beat=1.0, duration_beats=4.0, pitches=["C3", "E3", "G3", "B3"], chord_symbol="Cmaj7"),
            VoicingEvent(bar=1, beat=1.0, duration_beats=4.0, pitches=["A2", "C3", "E3", "G3"], chord_symbol="Am7"),
        ],
    )
    bl = BassLine(
        id="bl-int", type="BassLine", status="active",
        note_events=[
            BassNoteEvent(bar=0, beat=1.0, duration_beats=2.0, pitch="C2", velocity=90),
            BassNoteEvent(bar=0, beat=3.0, duration_beats=2.0, pitch="G2", velocity=80),
            BassNoteEvent(bar=1, beat=1.0, duration_beats=4.0, pitch="A1", velocity=85),
        ],
    )
    session = Session(id="sess-int", type="Session", status="active", metadata={"prompt": "test export"})
    brief = CreativeBrief(
        id="cb-int", type="CreativeBrief", status="active",
        genre="synthwave", key_center="C", mode="major", tempo_hint_bpm=118,
    )
    candidate = ProgressionCandidate(
        id="pc-int", type="ProgressionCandidate", status="active",
        session_id="sess-int", rationale="test",
        chord_symbols=["Cmaj7", "Am7"],
        roman_numerals=["Imaj7", "vim7"],
        metadata={"label": "C", "role": "best", "origin_round": 1},
    )
    arrangement = ArrangementCandidate(
        id="ac-int", type="ArrangementCandidate", status="active",
        session_id="sess-int", rationale="test", progression_candidate_id="pc-int",
    )

    json_ctx = JsonRenderContext(
        session=session, creative_brief=brief, candidate=candidate,
        arrangement=arrangement, voicing_plan=vp, bass_line=bl,
        scores={"tension_curve": 0.82, "voice_leading": 0.91},
        mutation_summaries=[],
    )

    req = ExportRequest(
        label="C", short_id="a3f2b1",
        voicing_plan=vp, bass_line=bl,
        bpm=118.0, beats_per_bar=4,
        formats=["midi_combined", "json"],
        output_dir=export_dir,
        json_context=json_ctx,
    )
    artifacts = render_and_write_artifacts(req)

    assert len(artifacts) == 2

    # Verify MIDI
    midi_art = [a for a in artifacts if a["artifact_type"] == "midi_combined"][0]
    assert os.path.exists(midi_art["path"])
    import io
    with open(midi_art["path"], "rb") as f:
        midi = pretty_midi.PrettyMIDI(io.BytesIO(f.read()))
    assert len(midi.instruments) == 2
    assert len(midi.instruments[0].notes) == 8  # 2 chords * 4 pitches
    assert len(midi.instruments[1].notes) == 3

    # Verify JSON
    json_art = [a for a in artifacts if a["artifact_type"] == "json"][0]
    assert os.path.exists(json_art["path"])
    with open(json_art["path"]) as f:
        doc = json.load(f)
    assert doc["session"]["genre"] == "synthwave"
    assert doc["candidate"]["chords"] == ["Cmaj7", "Am7"]
    assert "vp-int" not in json.dumps(doc)  # no internal IDs


def test_cascade_cleanup(export_dir):
    """Verify shutil.rmtree can clean up export directory."""
    os.makedirs(os.path.join(export_dir, "test-session", "test-pkg"), exist_ok=True)
    with open(os.path.join(export_dir, "test-session", "test-pkg", "test.mid"), "wb") as f:
        f.write(b"fake midi")

    session_dir = os.path.join(export_dir, "test-session")
    assert os.path.isdir(session_dir)
    shutil.rmtree(session_dir)
    assert not os.path.isdir(session_dir)
```

- [ ] **Step 2: Run the integration test**

Run: `cd backend && python -m pytest tests/integration/test_export_flow.py -v`
Expected: Both tests PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/integration/test_export_flow.py
git commit -m "test: integration test for full MIDI/JSON export flow"
```

---

### Task 11: E2E test — export modal

**Files:**
- Modify: `e2e/tests/m3-features.spec.ts` or create `e2e/tests/export.spec.ts`

- [ ] **Step 1: Create E2E test for export modal**

Create `e2e/tests/export.spec.ts`:

```typescript
import { test, expect } from "@playwright/test";

test.describe("Export Modal", () => {
  test("export button opens modal", async ({ page }) => {
    // Navigate to a session that has arrangement candidates
    // (relies on existing test fixtures or FakeGeminiClient mock)
    await page.goto("/");
    // Wait for session to load and generate
    await page.waitForSelector('[data-testid="session-workspace"]', { timeout: 30000 });

    // Click Export button
    const exportBtn = page.locator("button", { hasText: "Export" });
    await expect(exportBtn).toBeVisible();
    await exportBtn.click();

    // Verify modal opens
    await expect(page.locator("text=Export Session")).toBeVisible();
    await expect(page.locator("text=Select candidates")).toBeVisible();
    await expect(page.locator("text=Combined MIDI")).toBeVisible();
  });

  test("modal close button works", async ({ page }) => {
    await page.goto("/");
    await page.waitForSelector('[data-testid="session-workspace"]', { timeout: 30000 });
    await page.locator("button", { hasText: "Export" }).click();
    await expect(page.locator("text=Export Session")).toBeVisible();

    await page.locator("button", { hasText: "✕" }).click();
    await expect(page.locator("text=Export Session")).not.toBeVisible();
  });
});
```

- [ ] **Step 2: Run E2E tests**

Run: `cd e2e && npx playwright test tests/export.spec.ts --headed`
Expected: Tests pass (may need `GEMINI_MOCK=true` env var for the backend).

- [ ] **Step 3: Commit**

```bash
git add e2e/tests/export.spec.ts
git commit -m "test: E2E tests for export modal open/close"
```

---

## File Map Summary

| # | File | Action | Task |
|---|------|--------|------|
| 1 | `backend/pyproject.toml` | Modify | 1 |
| 2 | `backend/src/explorator/config.py` | Modify | 1 |
| 3 | `.gitignore` | Modify | 1 |
| 4 | `backend/src/explorator/utils.py` | Modify | 2 |
| 5 | `backend/tests/unit/test_pitch_utils.py` | Create | 2 |
| 6 | `backend/src/explorator/domain/evaluation/register_density.py` | Modify | 2 |
| 7 | `backend/src/explorator/domain/export/__init__.py` | Create | 3 |
| 8 | `backend/src/explorator/domain/export/midi_renderer.py` | Create | 3 |
| 9 | `backend/tests/unit/domain/test_midi_renderer.py` | Create | 3 |
| 10 | `backend/src/explorator/domain/export/json_renderer.py` | Create | 4 |
| 11 | `backend/tests/unit/domain/test_json_renderer.py` | Create | 4 |
| 12 | `backend/src/explorator/models/export.py` | Modify | 5 |
| 13 | `backend/src/explorator/graph/render_artifact_repo.py` | Create | 5 |
| 14 | `backend/src/explorator/graph/export_package_repo.py` | Create | 5 |
| 15 | `backend/src/explorator/domain/export/orchestrator.py` | Create | 6 |
| 16 | `backend/tests/unit/domain/test_export_orchestrator.py` | Create | 6 |
| 17 | `backend/src/explorator/api/routes/exports.py` | Create | 7 |
| 18 | `backend/src/explorator/api/app.py` | Modify | 7 |
| 19 | `backend/src/explorator/api/routes/sessions.py` | Modify | 7 |
| 20 | `frontend/src/services/api.ts` | Modify | 8 |
| 21 | `frontend/src/stores/exportStore.ts` | Create | 8 |
| 22 | `frontend/src/components/ExportModal.tsx` | Create | 9 |
| 23 | `frontend/src/views/SessionWorkspace.tsx` | Modify | 9 |
| 24 | `backend/tests/integration/test_export_flow.py` | Create | 10 |
| 25 | `e2e/tests/export.spec.ts` | Create | 11 |
