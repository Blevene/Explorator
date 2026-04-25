"""Tests for genre research models."""

from datetime import UTC, datetime

import pytest

from explorator.models.genre_research import (
    CritiqueIssue,
    GenreDraftResponse,
    GenreResearchJob,
    step_number,
)


class TestStepNumber:
    def test_researching_is_step_1(self):
        assert step_number("researching") == 1

    def test_pending_review_is_step_6(self):
        assert step_number("pending_review") == 6

    def test_approved_returns_0(self):
        assert step_number("approved") == 0

    def test_failed_returns_0(self):
        assert step_number("failed") == 0

    def test_unknown_returns_0(self):
        assert step_number("bogus") == 0


class TestCritiqueIssue:
    def test_valid_major_issue(self):
        issue = CritiqueIssue(
            severity="major", field="harmonic_vocabulary", suggestion="Add more chord types"
        )
        assert issue.severity == "major"

    def test_invalid_severity_rejected(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CritiqueIssue(severity="critical", field="x", suggestion="y")


class TestGenreResearchJob:
    def test_minimal_job(self):
        job = GenreResearchJob(
            id="grj_01JTEST",
            genre_name="lo_fi_hip_hop",
            reference_artists=["Nujabes"],
            status="researching",
            research_log="",
            critique_trail=[],
            draft_yamls={},
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        assert job.genre_name == "lo_fi_hip_hop"
        assert job.error_message is None

    def test_failed_job_with_error(self):
        job = GenreResearchJob(
            id="grj_01JTEST",
            genre_name="test",
            reference_artists=[],
            status="failed",
            research_log="",
            critique_trail=[],
            draft_yamls={},
            error_message="LLM timeout",
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        assert job.status == "failed"
        assert job.error_message == "LLM timeout"


class TestGenreDraftResponse:
    def test_validates_with_typed_schemas(self):
        resp = GenreDraftResponse(
            profile={"genre": "test", "display_name": "Test", "version": 1},
            rules={"rules": [], "anti_patterns": []},
            grammar={
                "genre_profile_id": "genre_test_01",
                "preferred_chord_qualities": [],
                "allowed_borrowed_chords": [],
                "cadence_archetypes": [],
            },
        )
        assert resp.profile.genre == "test"
        assert resp.rules.rules == []
