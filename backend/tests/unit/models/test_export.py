"""Tests for presentation and export models."""

import pytest
from pydantic import ValidationError

from explorator.models.export import (
    CandidateExplanation,
    ComparisonView,
    ExportPackage,
    ProvenanceTrace,
    RenderArtifact,
)

# ---------------------------------------------------------------------------
# ProvenanceTrace
# ---------------------------------------------------------------------------


def test_provenance_trace_minimal() -> None:
    trace = ProvenanceTrace(
        id="pt_01",
        type="provenance_trace",
        status="completed",
        session_id="sess_01",
    )
    assert trace.session_id == "sess_01"
    assert trace.events == []


def test_provenance_trace_with_events() -> None:
    events = [
        {"phase": "harmonic_generation", "action": "generated", "candidate_id": "prog_01"},
        {"phase": "evaluation", "action": "scored", "candidate_id": "prog_01"},
    ]
    trace = ProvenanceTrace(
        id="pt_02",
        type="provenance_trace",
        status="completed",
        session_id="sess_01",
        events=events,
    )
    assert len(trace.events) == 2
    assert trace.events[0]["phase"] == "harmonic_generation"


def test_provenance_trace_requires_session_id() -> None:
    with pytest.raises(ValidationError):
        ProvenanceTrace(
            id="pt_03",
            type="provenance_trace",
            status="completed",
        )  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# CandidateExplanation
# ---------------------------------------------------------------------------


def test_candidate_explanation_minimal() -> None:
    exp = CandidateExplanation(
        id="ce_01",
        type="candidate_explanation",
        status="completed",
        candidate_id="arr_01",
    )
    assert exp.candidate_id == "arr_01"
    assert exp.summary == ""
    assert exp.why_it_works == []
    assert exp.what_is_experimental == []
    assert exp.recommended_use_cases == []


def test_candidate_explanation_full() -> None:
    exp = CandidateExplanation(
        id="ce_02",
        type="candidate_explanation",
        status="completed",
        candidate_id="arr_01",
        summary="A dreamy, floating progression built on stacked fourths.",
        why_it_works=["Open voicings create space", "Plagal cadence fits genre"],
        what_is_experimental=["Non-functional bVII chord"],
        recommended_use_cases=["Intro", "Bridge"],
    )
    assert "floating" in exp.summary
    assert len(exp.why_it_works) == 2
    assert len(exp.recommended_use_cases) == 2


def test_candidate_explanation_requires_candidate_id() -> None:
    with pytest.raises(ValidationError):
        CandidateExplanation(
            id="ce_03",
            type="candidate_explanation",
            status="completed",
        )  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# ComparisonView
# ---------------------------------------------------------------------------


def test_comparison_view_minimal() -> None:
    cv = ComparisonView(
        id="cv_01",
        type="comparison_view",
        status="active",
        session_id="sess_01",
    )
    assert cv.session_id == "sess_01"
    assert cv.candidate_ids == []
    assert cv.comparison_axes == []
    assert cv.labels == {}


def test_comparison_view_with_data() -> None:
    cv = ComparisonView(
        id="cv_02",
        type="comparison_view",
        status="active",
        session_id="sess_01",
        candidate_ids=["arr_01", "arr_02", "arr_03"],
        comparison_axes=["theory_score", "playability", "novelty"],
        labels={"arr_01": "Safe choice", "arr_02": "Adventurous"},
    )
    assert len(cv.candidate_ids) == 3
    assert "playability" in cv.comparison_axes
    assert cv.labels["arr_01"] == "Safe choice"


def test_comparison_view_requires_session_id() -> None:
    with pytest.raises(ValidationError):
        ComparisonView(
            id="cv_03",
            type="comparison_view",
            status="active",
        )  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# RenderArtifact
# ---------------------------------------------------------------------------


def test_render_artifact_minimal() -> None:
    ra = RenderArtifact(
        id="ra_01",
        type="render_artifact",
        status="ready",
        candidate_id="arr_01",
        artifact_type="midi",
        path="/exports/sess_01/arr_01.mid",
    )
    assert ra.candidate_id == "arr_01"
    assert ra.artifact_type == "midi"
    assert ra.path == "/exports/sess_01/arr_01.mid"
    assert ra.render_metadata == {}


def test_render_artifact_with_metadata() -> None:
    ra = RenderArtifact(
        id="ra_02",
        type="render_artifact",
        status="ready",
        candidate_id="arr_01",
        artifact_type="audio",
        path="/exports/sess_01/arr_01.wav",
        render_metadata={"sample_rate": 44100, "bit_depth": 24, "duration_s": 32.0},
    )
    assert ra.render_metadata["sample_rate"] == 44100


def test_render_artifact_requires_candidate_id() -> None:
    with pytest.raises(ValidationError):
        RenderArtifact(
            id="ra_03",
            type="render_artifact",
            status="ready",
            artifact_type="midi",
            path="/exports/file.mid",
        )  # type: ignore[call-arg]


def test_render_artifact_requires_artifact_type() -> None:
    with pytest.raises(ValidationError):
        RenderArtifact(
            id="ra_04",
            type="render_artifact",
            status="ready",
            candidate_id="arr_01",
            path="/exports/file.mid",
        )  # type: ignore[call-arg]


def test_render_artifact_requires_path() -> None:
    with pytest.raises(ValidationError):
        RenderArtifact(
            id="ra_05",
            type="render_artifact",
            status="ready",
            candidate_id="arr_01",
            artifact_type="midi",
        )  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# ExportPackage
# ---------------------------------------------------------------------------


def test_export_package_minimal() -> None:
    pkg = ExportPackage(
        id="ep_01",
        type="export_package",
        status="ready",
        session_id="sess_01",
    )
    assert pkg.session_id == "sess_01"
    assert pkg.included_candidate_ids == []
    assert pkg.included_artifact_ids == []
    assert pkg.formats == []
    assert pkg.notes == []


def test_export_package_with_data() -> None:
    pkg = ExportPackage(
        id="ep_02",
        type="export_package",
        status="ready",
        session_id="sess_01",
        included_candidate_ids=["arr_01", "arr_02"],
        included_artifact_ids=["ra_01", "ra_02"],
        formats=["midi", "audio"],
        notes=["User approved both arrangements"],
    )
    assert len(pkg.included_candidate_ids) == 2
    assert "midi" in pkg.formats
    assert pkg.notes == ["User approved both arrangements"]


def test_export_package_requires_session_id() -> None:
    with pytest.raises(ValidationError):
        ExportPackage(
            id="ep_03",
            type="export_package",
            status="ready",
        )  # type: ignore[call-arg]
