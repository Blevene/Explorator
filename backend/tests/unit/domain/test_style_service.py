"""Tests for explorator.domain.style.service.STYLE_DIR resolution."""

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
    # Chdir into tmp_path's parent so the override can be a bare basename.
    monkeypatch.chdir(tmp_path.parent)
    monkeypatch.setenv("EXPLORATOR_STYLE_DIR", tmp_path.name)
    result = _resolve_style_dir()
    assert result.is_absolute()
    assert result == tmp_path.resolve()
