"""Tests for the validate node (deterministic validation)."""

from explorator.engine.nodes.genre_research.validate import _validate_draft_yamls


class TestValidateDraftYamls:
    def test_valid_draft_returns_no_errors(self):
        draft = {
            "profile": {
                "genre": "test",
                "display_name": "Test",
                "version": 1,
                "harmonic_vocabulary": ["maj7"],
                "experimentation_envelope": {"harmonic_deviation_tolerance": 0.5},
            },
            "rules": {"rules": [], "anti_patterns": []},
            "grammar": {
                "genre_profile_id": "genre_test_01",
                "preferred_chord_qualities": [],
                "allowed_borrowed_chords": [],
                "cadence_archetypes": [],
            },
        }
        errors = _validate_draft_yamls(draft)
        assert errors == []

    def test_missing_profile_genre_field(self):
        draft = {
            "profile": {"display_name": "Test", "version": 1},
            "rules": {"rules": [], "anti_patterns": []},
            "grammar": {"genre_profile_id": "x"},
        }
        errors = _validate_draft_yamls(draft)
        assert any("profile" in e.lower() for e in errors)

    def test_envelope_out_of_range(self):
        draft = {
            "profile": {
                "genre": "test",
                "display_name": "Test",
                "version": 1,
                "experimentation_envelope": {"harmonic_deviation_tolerance": 1.5},
            },
            "rules": {"rules": [], "anti_patterns": []},
            "grammar": {"genre_profile_id": "genre_test_01"},
        }
        errors = _validate_draft_yamls(draft)
        assert any("range" in e.lower() or "envelope" in e.lower() for e in errors)

    def test_missing_top_level_key(self):
        draft = {
            "profile": {"genre": "test", "display_name": "Test", "version": 1},
            "grammar": {"genre_profile_id": "genre_test_01"},
        }
        errors = _validate_draft_yamls(draft)
        assert any("rules" in e.lower() for e in errors)
