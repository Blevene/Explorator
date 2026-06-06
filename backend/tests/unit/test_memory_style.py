"""Unit tests for YAML-backed genre profiles in memory mode."""

from explorator.domain.style.service import (
    StyleService,
    load_genre_profiles_from_yaml,
)
from explorator.persistence.memory_repos import MemoryStyleRepo

# Keys every genre profile carries: the GenreProfileYAML fields plus the
# id/type/status stamped by sync_genres_to_neo4j (the StyleRepository shape).
_EXPECTED_KEYS = {
    "genre",
    "display_name",
    "version",
    "harmonic_vocabulary",
    "harmonic_tendencies",
    "id",
    "type",
    "status",
}


def test_loader_returns_profiles() -> None:
    profiles = load_genre_profiles_from_yaml()
    assert profiles, "expected at least one genre profile from YAML"
    genres = {p["genre"] for p in profiles}
    assert "dream_pop" in genres
    dp = next(p for p in profiles if p["genre"] == "dream_pop")
    assert set(dp.keys()) >= _EXPECTED_KEYS
    assert dp["id"] == "genre_dream_pop_01"
    assert dp["type"] == "genre_profile"
    assert dp["status"] == "active"


async def test_memory_style_repo_get_genre_profile() -> None:
    repo = MemoryStyleRepo()
    profile = await repo.get_genre_profile("dream_pop")
    assert profile is not None
    assert profile["genre"] == "dream_pop"
    assert set(profile.keys()) >= _EXPECTED_KEYS
    # nested fields stay real dicts/lists in memory mode
    assert isinstance(profile["harmonic_tendencies"], dict)
    assert isinstance(profile["harmonic_vocabulary"], list)


async def test_memory_style_repo_unknown_genre_returns_none() -> None:
    repo = MemoryStyleRepo()
    assert await repo.get_genre_profile("not_a_real_genre") is None


async def test_memory_style_repo_list_genre_profiles() -> None:
    repo = MemoryStyleRepo()
    profiles = await repo.list_genre_profiles()
    assert {p["genre"] for p in profiles} >= {"dream_pop"}


async def test_style_service_memory_mode() -> None:
    service = StyleService(driver=None)
    profile = await service.get_genre_profile("dream_pop")
    assert profile is not None and profile["genre"] == "dream_pop"
    genres = await service.list_genres()
    assert {p["genre"] for p in genres} >= {"dream_pop"}
    # sync is a no-op without a driver
    assert await service.sync_genres_to_neo4j() == 0
