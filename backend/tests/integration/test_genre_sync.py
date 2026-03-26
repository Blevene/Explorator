"""Integration tests for genre YAML → Neo4j sync."""

from pathlib import Path

from neo4j import AsyncDriver

from explorator.domain.style.loader import load_genre_from_yaml
from explorator.graph.style_repo import StyleRepository


async def test_sync_dream_pop_to_neo4j(neo4j_driver: AsyncDriver) -> None:
    genres_dir = Path(__file__).parents[2] / "src" / "explorator" / "domain" / "style" / "genres"
    profile = load_genre_from_yaml(genres_dir / "dream_pop.yaml")
    repo = StyleRepository(neo4j_driver)

    genre_id = f"genre_{profile.genre}_01"
    data = profile.model_dump(mode="json")
    data["id"] = genre_id
    data["type"] = "genre_profile"
    data["status"] = "active"

    await repo.upsert_genre_profile(genre_id, data)

    result = await repo.get_genre_profile("dream_pop")
    assert result is not None
    assert result["genre"] == "dream_pop"
    assert result["display_name"] == "Dream Pop"


async def test_list_genres_after_sync(neo4j_driver: AsyncDriver) -> None:
    genres_dir = Path(__file__).parents[2] / "src" / "explorator" / "domain" / "style" / "genres"
    repo = StyleRepository(neo4j_driver)

    for genre_name in ["dream_pop", "synthwave", "cinematic"]:
        profile = load_genre_from_yaml(genres_dir / f"{genre_name}.yaml")
        genre_id = f"genre_{profile.genre}_01"
        data = profile.model_dump(mode="json")
        data["id"] = genre_id
        data["type"] = "genre_profile"
        data["status"] = "active"
        await repo.upsert_genre_profile(genre_id, data)

    results = await repo.list_genre_profiles()
    assert len(results) == 3
    genres = [r["genre"] for r in results]
    assert "dream_pop" in genres
    assert "synthwave" in genres
    assert "cinematic" in genres
