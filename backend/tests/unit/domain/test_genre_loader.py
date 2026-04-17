"""Tests for genre YAML loader."""

from pathlib import Path

from explorator.domain.style.loader import load_genre_from_yaml
from explorator.domain.style.schema import GenreProfileYAML


def test_load_dream_pop_profile() -> None:
    genres_dir = Path(__file__).parents[3] / "src" / "explorator" / "domain" / "style" / "genres"
    profile = load_genre_from_yaml(genres_dir / "dream_pop.yaml")
    assert isinstance(profile, GenreProfileYAML)
    assert profile.genre == "dream_pop"
    assert profile.display_name == "Dream Pop"
    assert "maj7" in profile.harmonic_vocabulary
    assert profile.version == 1


def test_load_synthwave_profile() -> None:
    genres_dir = Path(__file__).parents[3] / "src" / "explorator" / "domain" / "style" / "genres"
    profile = load_genre_from_yaml(genres_dir / "synthwave.yaml")
    assert profile.genre == "synthwave"


def test_load_cinematic_profile() -> None:
    genres_dir = Path(__file__).parents[3] / "src" / "explorator" / "domain" / "style" / "genres"
    profile = load_genre_from_yaml(genres_dir / "cinematic.yaml")
    assert profile.genre == "cinematic"


def test_genre_profile_accepts_melodic_tendencies():
    data = {
        "genre": "test_genre",
        "display_name": "Test Genre",
        "version": 1,
        "melodic_tendencies": {
            "motion_preference": "stepwise",
            "range_placement": "above_voicing",
            "density": "sparse",
        },
    }
    from explorator.domain.style.schema import GenreProfileYAML
    profile = GenreProfileYAML.model_validate(data)
    assert profile.melodic_tendencies["motion_preference"] == "stepwise"


def test_genre_profile_works_without_melodic_tendencies():
    data = {
        "genre": "test_genre",
        "display_name": "Test Genre",
        "version": 1,
    }
    from explorator.domain.style.schema import GenreProfileYAML
    profile = GenreProfileYAML.model_validate(data)
    assert profile.melodic_tendencies == {}
