"""Tests for explorator.domain.style.service.STYLE_DIR resolution."""

from pathlib import Path

import pytest

from explorator.domain.style.service import _resolve_style_dir


def test_resolve_style_dir_uses_env_override(tmp_path, monkeypatch):
    """EXPLORATOR_STYLE_DIR is honored when set."""
    monkeypatch.setenv("EXPLORATOR_STYLE_DIR", str(tmp_path))
    result = _resolve_style_dir()
    assert result == tmp_path.resolve()


def test_resolve_style_dir_default(monkeypatch):
    """Without override, resolves to the bundled style/ directory."""
    monkeypatch.delenv("EXPLORATOR_STYLE_DIR", raising=False)
    result = _resolve_style_dir()
    assert result.name == "style"
    # Sanity: the bundled dir should have the canonical subdirs we depend on.
    assert (result / "genres").is_dir()
    assert (result / "rules").is_dir()
    assert (result / "grammars").is_dir()


def test_resolve_style_dir_resolves_relative_paths(tmp_path, monkeypatch):
    """A relative env-var path is resolved to absolute."""
    rel = Path(tmp_path).relative_to(Path.cwd()) if str(tmp_path).startswith(str(Path.cwd())) else None
    if rel is None:
        pytest.skip("tmp_path is not under cwd; can't test relative resolution")
    monkeypatch.setenv("EXPLORATOR_STYLE_DIR", str(rel))
    result = _resolve_style_dir()
    assert result.is_absolute()
