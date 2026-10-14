"""Genre profile retrieval and rule lookup service."""

import os
from pathlib import Path
from typing import Any

from neo4j import AsyncDriver

from explorator.domain.style.loader import (
    discover_genres,
    load_genre_from_yaml,
    load_grammar_from_yaml,
    load_rules_from_yaml,
)
from explorator.graph.style_repo import StyleRepository
from explorator.persistence.memory_repos import MemoryStyleRepo


def _resolve_style_dir() -> Path:
    """Source-of-truth for the genre catalog directory.

    Defaults to the bundled style/ folder, overridable via
    EXPLORATOR_STYLE_DIR. The override exists so e2e tests can point
    at a temp directory and the approve endpoint won't mutate
    source-controlled paths. Resolved once at import; the env var
    must be set before the process starts.
    """
    override = os.environ.get("EXPLORATOR_STYLE_DIR")
    if override:
        return Path(override).resolve()
    return Path(__file__).parent.resolve()


STYLE_DIR = _resolve_style_dir()


def load_genre_profiles_from_yaml() -> list[dict[str, Any]]:
    """Load every genre profile from the YAML catalog.

    Returns the same per-profile dict shape `sync_genres_to_neo4j` upserts and
    `StyleRepository.list_genre_profiles` yields: the `GenreProfileYAML` fields
    plus the stamped `id`/`type`/`status`. Pure (no I/O beyond reading YAML, no
    database); used by both the Neo4j sync and `MemoryStyleRepo`.
    """
    profiles: list[dict[str, Any]] = []
    for genre_name in discover_genres(STYLE_DIR):
        profile = load_genre_from_yaml(STYLE_DIR / "genres" / f"{genre_name}.yaml")
        profile_data = profile.model_dump(mode="json")
        profile_data["genre"] = genre_name  # the filename is the identity
        profile_data["id"] = f"genre_{genre_name}_01"
        profile_data["type"] = "genre_profile"
        profile_data["status"] = "active"
        profiles.append(profile_data)
    return profiles


class StyleService:
    """Retrieves genre profiles, rules, and grammars.

    With a driver it reads from Neo4j; with `driver=None` it serves genre
    profiles straight from YAML (memory mode) and `sync_genres_to_neo4j` no-ops.
    """

    def __init__(self, driver: AsyncDriver | None) -> None:
        self._driver = driver
        self.repo: StyleRepository | MemoryStyleRepo = (
            MemoryStyleRepo() if driver is None else StyleRepository(driver)
        )

    async def get_genre_profile(self, genre: str) -> dict[str, Any] | None:
        """Get a genre profile by genre name."""
        return await self.repo.get_genre_profile(genre)

    async def list_genres(self) -> list[dict[str, Any]]:
        """List all available genre profiles."""
        return await self.repo.list_genre_profiles()

    async def sync_genres_to_neo4j(self) -> int:
        """Load all genre YAML files and sync to Neo4j. Returns count synced.

        No-op returning 0 in memory mode (driver is None).
        """
        if self._driver is None:
            return 0
        repo = StyleRepository(self._driver)
        genre_names = discover_genres(STYLE_DIR)
        count = 0

        for genre_name in genre_names:
            genre_id = f"genre_{genre_name}_01"

            # Load and sync profile
            profile = load_genre_from_yaml(STYLE_DIR / "genres" / f"{genre_name}.yaml")
            profile_data = profile.model_dump(mode="json")
            profile_data["genre"] = genre_name  # the filename is the identity
            profile_data["id"] = genre_id
            profile_data["type"] = "genre_profile"
            profile_data["status"] = "active"
            await repo.upsert_genre_profile(genre_id, profile_data)

            # Load and sync rules
            rules_path = STYLE_DIR / "rules" / f"{genre_name}_rules.yaml"
            if rules_path.exists():
                rules = load_rules_from_yaml(rules_path)
                for i, rule in enumerate(rules.rules):
                    rule_id = f"rule_{genre_name}_{i:03d}"
                    rule_data = rule.model_dump(mode="json")
                    rule_data["id"] = rule_id
                    rule_data["type"] = "genre_rule"
                    rule_data["status"] = "active"
                    rule_data["genre"] = genre_name
                    await repo.upsert_genre_rule(rule_id, genre_id, rule_data)

                for i, ap in enumerate(rules.anti_patterns):
                    ap_id = f"anti_{genre_name}_{i:03d}"
                    ap_data = ap.model_dump(mode="json")
                    ap_data["id"] = ap_id
                    ap_data["type"] = "anti_pattern"
                    ap_data["status"] = "active"
                    ap_data["genre"] = genre_name
                    await repo.upsert_anti_pattern(ap_id, genre_id, ap_data)

            # Load and sync grammar
            grammar_path = STYLE_DIR / "grammars" / f"{genre_name}_grammar.yaml"
            if grammar_path.exists():
                grammar = load_grammar_from_yaml(grammar_path)
                grammar_id = f"grammar_{genre_name}_01"
                grammar_data = grammar.model_dump(mode="json")
                grammar_data["id"] = grammar_id
                grammar_data["type"] = "harmonic_grammar"
                grammar_data["status"] = "active"
                grammar_data["genre_profile_id"] = genre_id
                await repo.upsert_harmonic_grammar(grammar_id, genre_id, grammar_data)

            count += 1

        return count
