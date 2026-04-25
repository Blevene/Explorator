"""Integration test — full export flow from arrangement data to files on disk."""

import json
import os
import shutil

import pretty_midi
import pytest

from explorator.domain.export.json_renderer import JsonRenderContext
from explorator.domain.export.orchestrator import ExportRequest, render_and_write_artifacts
from explorator.models.harmony import ProgressionCandidate
from explorator.models.realization import (
    ArrangementCandidate,
    BassLine,
    BassNoteEvent,
    VoicingEvent,
    VoicingPlan,
)
from explorator.models.session import CreativeBrief, Session


@pytest.fixture
def export_dir(tmp_path):
    return str(tmp_path / "exports")


def test_full_export_produces_valid_files(export_dir):
    """Export combined MIDI + JSON for one candidate, verify both files."""
    vp = VoicingPlan(
        id="vp-int",
        type="VoicingPlan",
        status="active",
        voicing_events=[
            VoicingEvent(
                bar=0,
                beat=1.0,
                duration_beats=4.0,
                pitches=["C3", "E3", "G3", "B3"],
                chord_symbol="Cmaj7",
            ),
            VoicingEvent(
                bar=1,
                beat=1.0,
                duration_beats=4.0,
                pitches=["A2", "C3", "E3", "G3"],
                chord_symbol="Am7",
            ),
        ],
    )
    bl = BassLine(
        id="bl-int",
        type="BassLine",
        status="active",
        note_events=[
            BassNoteEvent(bar=0, beat=1.0, duration_beats=2.0, pitch="C2", velocity=90),
            BassNoteEvent(bar=0, beat=3.0, duration_beats=2.0, pitch="G2", velocity=80),
            BassNoteEvent(bar=1, beat=1.0, duration_beats=4.0, pitch="A1", velocity=85),
        ],
    )
    session = Session(
        id="sess-int", type="Session", status="active", metadata={"prompt": "test export"}
    )
    brief = CreativeBrief(
        id="cb-int",
        type="CreativeBrief",
        status="active",
        genre="synthwave",
        key_center="C",
        mode="major",
        tempo_hint_bpm=118,
    )
    candidate = ProgressionCandidate(
        id="pc-int",
        type="ProgressionCandidate",
        status="active",
        session_id="sess-int",
        rationale="test",
        chord_symbols=["Cmaj7", "Am7"],
        roman_numerals=["Imaj7", "vim7"],
        key_center="C",
        metadata={"label": "C", "role": "best", "origin_round": 1},
    )
    arrangement = ArrangementCandidate(
        id="ac-int",
        type="ArrangementCandidate",
        status="active",
        session_id="sess-int",
        rationale="test",
        progression_candidate_id="pc-int",
    )

    json_ctx = JsonRenderContext(
        session=session,
        creative_brief=brief,
        candidate=candidate,
        arrangement=arrangement,
        voicing_plan=vp,
        bass_line=bl,
        melodic_complement=None,
        scores={"tension_curve": 0.82, "voice_leading": 0.91},
        mutation_summaries=[],
    )

    req = ExportRequest(
        label="C",
        short_id="a3f2b1",
        voicing_plan=vp,
        bass_line=bl,
        melodic_complement=None,
        bpm=118.0,
        beats_per_bar=4,
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
