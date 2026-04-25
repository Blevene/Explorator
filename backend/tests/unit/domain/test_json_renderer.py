"""Tests for JSON sidecar renderer."""

import json

from explorator.domain.export.json_renderer import JsonRenderContext, render_json
from explorator.models.harmony import ProgressionCandidate
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
        id="sess-1",
        type="Session",
        status="active",
        metadata={"prompt": "dreamy synthwave, 4 bars"},
    )
    brief = CreativeBrief(
        id="cb-1",
        type="CreativeBrief",
        status="active",
        genre="synthwave",
        key_center="C",
        mode="major",
        tempo_hint_bpm=118,
        meter="4/4",
    )
    candidate = ProgressionCandidate(
        id="pc-1",
        type="ProgressionCandidate",
        status="active",
        session_id="sess-1",
        rationale="test",
        key_center="C",
        chord_symbols=["Cmaj7", "Am7", "Fmaj7", "G7"],
        roman_numerals=["Imaj7", "vim7", "IVmaj7", "V7"],
        metadata={"label": "C", "role": "best"},
    )
    arrangement = ArrangementCandidate(
        id="ac-1",
        type="ArrangementCandidate",
        status="active",
        session_id="sess-1",
        rationale="test",
        progression_candidate_id="pc-1",
    )
    voicing_plan = VoicingPlan(
        id="vp-1",
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
        ],
    )
    bass_line = BassLine(
        id="bl-1",
        type="BassLine",
        status="active",
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
        melodic_complement=None,
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
