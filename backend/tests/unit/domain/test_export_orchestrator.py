"""Tests for export orchestrator — file naming and package assembly."""

import os

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
