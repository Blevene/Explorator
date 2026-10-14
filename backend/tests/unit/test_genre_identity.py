"""A drafted or loaded genre can never claim another genre's identity."""
import shutil
from pathlib import Path

import pytest

from explorator.engine.nodes.genre_research.draft import _normalize_draft


def test_normalize_draft_pins_identity_to_validated_name():
    parsed = {
        "profile": {"genre": "jazz", "display_name": "Jazz"},
        "rules": {"rules": [], "anti_patterns": []},
        "grammar": {"genre_profile_id": "genre_jazz_01"},
    }
    _normalize_draft(parsed, "foo")
    assert parsed["profile"]["genre"] == "foo"
    assert parsed["grammar"]["genre_profile_id"] == "genre_foo_01"


def test_loaded_profile_genre_comes_from_filename(tmp_path, monkeypatch: pytest.MonkeyPatch):
    import explorator.domain.style.service as service

    src = service.STYLE_DIR / "genres" / "ambient.yaml"
    (tmp_path / "genres").mkdir()
    impostor = src.read_text().replace("genre: ambient", "genre: dream_pop", 1)
    assert impostor != src.read_text()
    (tmp_path / "genres" / "foo.yaml").write_text(impostor)
    monkeypatch.setattr(service, "STYLE_DIR", Path(tmp_path))

    [profile] = service.load_genre_profiles_from_yaml()
    assert profile["genre"] == "foo"
    assert profile["id"] == "genre_foo_01"
    shutil.rmtree(tmp_path / "genres")
