"""Read genre YAML files and validate against Pydantic schemas."""

from pathlib import Path

import yaml

from explorator.domain.style.schema import (
    GenreProfileYAML,
    GenreRulesYAML,
    HarmonicGrammarYAML,
)


def load_genre_from_yaml(path: Path) -> GenreProfileYAML:
    """Load and validate a genre profile YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return GenreProfileYAML.model_validate(data)


def load_rules_from_yaml(path: Path) -> GenreRulesYAML:
    """Load and validate a genre rules YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return GenreRulesYAML.model_validate(data)


def load_grammar_from_yaml(path: Path) -> HarmonicGrammarYAML:
    """Load and validate a harmonic grammar YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return HarmonicGrammarYAML.model_validate(data)


def discover_genres(style_dir: Path) -> list[str]:
    """Discover available genre names from the genres/ directory."""
    genres_dir = style_dir / "genres"
    if not genres_dir.exists():
        return []
    return [p.stem for p in genres_dir.glob("*.yaml")]
