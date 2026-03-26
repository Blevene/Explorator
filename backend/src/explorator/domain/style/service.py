"""Genre profile retrieval and rule lookup service."""

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
from explorator.models.style import GenreProfile, HarmonicGrammar


STYLE_DIR = Path(__file__).parent


class StyleService:
    """Retrieves genre profiles, rules, and grammars from Neo4j."""

    def __init__(self, driver: AsyncDriver) -> None:
        self.repo = StyleRepository(driver)

    async def get_genre_profile(self, genre: str) -> dict[str, Any] | None:
        """Get a genre profile by genre name."""
        return await self.repo.get_genre_profile(genre)

    async def list_genres(self) -> list[dict[str, Any]]:
        """List all available genre profiles."""
        return await self.repo.list_genre_profiles()

    async def sync_genres_to_neo4j(self) -> int:
        """Load all genre YAML files and sync to Neo4j. Returns count synced."""
        genre_names = discover_genres(STYLE_DIR)
        count = 0

        for genre_name in genre_names:
            genre_id = f"genre_{genre_name}_01"

            # Load and sync profile
            profile = load_genre_from_yaml(STYLE_DIR / "genres" / f"{genre_name}.yaml")
            profile_data = profile.model_dump(mode="json")
            profile_data["id"] = genre_id
            profile_data["type"] = "genre_profile"
            profile_data["status"] = "active"
            await self.repo.upsert_genre_profile(genre_id, profile_data)

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
                    await self.repo.upsert_genre_rule(rule_id, genre_id, rule_data)

                for i, ap in enumerate(rules.anti_patterns):
                    ap_id = f"anti_{genre_name}_{i:03d}"
                    ap_data = ap.model_dump(mode="json")
                    ap_data["id"] = ap_id
                    ap_data["type"] = "anti_pattern"
                    ap_data["status"] = "active"
                    ap_data["genre"] = genre_name
                    await self.repo.upsert_anti_pattern(ap_id, genre_id, ap_data)

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
                await self.repo.upsert_harmonic_grammar(grammar_id, genre_id, grammar_data)

            count += 1

        return count
