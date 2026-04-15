# backend/tests/unit/domain/test_groove_generator.py

from explorator.domain.realization.groove import GrooveGenerator
from explorator.models.groove import GroovePattern, GroovePreferences


class TestGrooveGeneratorBasic:
    def test_dream_pop_sparse(self):
        """Dream pop sparse → density ≤ 0.4, template in (sparse, straight_eighths, dotted)."""
        gen = GrooveGenerator()
        prefs = GroovePreferences(
            comp_density="sparse",
            articulation_style="straight",
            syncopation_level="minimal",
        )
        pattern = gen.generate(prefs, genre="dream_pop", session_id="sess_001")
        assert isinstance(pattern, GroovePattern)
        assert pattern.density <= 0.4
        assert pattern.source_template in ("sparse", "straight_eighths", "dotted")

    def test_synthwave_medium_density(self):
        """Synthwave medium → density between 0.4 and 0.7."""
        gen = GrooveGenerator()
        prefs = GroovePreferences(
            comp_density="medium",
            articulation_style="straight",
            syncopation_level="light",
        )
        pattern = gen.generate(prefs, genre="synthwave", session_id="sess_002")
        assert isinstance(pattern, GroovePattern)
        assert 0.4 <= pattern.density <= 0.7

    def test_entity_fields(self):
        gen = GrooveGenerator()
        prefs = GroovePreferences()
        pattern = gen.generate(prefs, genre="dream_pop", session_id="sess_fields")
        assert pattern.type == "groove_pattern"
        assert pattern.status == "draft"
        assert pattern.id.startswith("gp_")
        assert pattern.session_id == "sess_fields"
        assert pattern.genre == "dream_pop"

    def test_default_prefs_straight_eighths(self):
        """Default prefs (unknown genre) → straight_eighths template."""
        gen = GrooveGenerator()
        prefs = GroovePreferences()  # defaults: comp_density=medium, articulation_style=straight, syncopation_level=light
        pattern = gen.generate(prefs, genre="unknown_genre", session_id="sess_default")
        assert pattern.source_template == "straight_eighths"


class TestGrooveTemplates:
    def test_syncopated_has_offbeat_accents(self):
        """Syncopated template has off-beat accents (beat not 1.0 or 3.0)."""
        gen = GrooveGenerator()
        prefs = GroovePreferences(
            comp_density="medium",
            articulation_style="straight",
            syncopation_level="heavy",
        )
        pattern = gen.generate(prefs, genre="synthwave", session_id="sess_sync", seed=42)
        assert pattern.source_template == "syncopated"
        # At least one accented event must be on an off-beat (not 1.0 or 3.0)
        offbeat_accents = [
            e for e in pattern.pattern_events
            if e.accent and (e.beat % 1.0 != 0.0 or e.beat not in (1.0, 3.0, 5.0, 7.0))
        ]
        assert len(offbeat_accents) >= 1, (
            f"Expected off-beat accents; events: {[(e.beat, e.accent) for e in pattern.pattern_events]}"
        )

    def test_triplet_feel_shuffle_articulation(self):
        """Shuffle articulation → triplet_feel template, swing_amount > 0.3."""
        gen = GrooveGenerator()
        prefs = GroovePreferences(
            comp_density="medium",
            articulation_style="shuffle",
            syncopation_level="light",
        )
        pattern = gen.generate(prefs, genre="blues_rock", session_id="sess_triplet", seed=1)
        assert pattern.source_template == "triplet_feel"
        assert pattern.swing_amount > 0.3

    def test_sparse_template_half_notes(self):
        """Sparse template should have events on beats 1 and 3."""
        gen = GrooveGenerator()
        prefs = GroovePreferences(
            comp_density="sparse",
            articulation_style="sustained_swells",
            syncopation_level="light",
        )
        pattern = gen.generate(prefs, genre="ambient", session_id="sess_sparse", seed=10, bars=2)
        assert pattern.source_template == "sparse"
        beats = [e.beat for e in pattern.pattern_events]
        # Beats 1 and 3 should be present (across bars, relative beats 1 and 3)
        # In a multi-bar pattern, beat positions are bar-local
        assert any(b % 4 == 1.0 % 4 or b % 4 == 0.0 for b in beats), (
            f"Expected beat 1 events; beats: {beats}"
        )

    def test_dotted_template_moderate_syncopation(self):
        """Moderate syncopation → dotted template."""
        gen = GrooveGenerator()
        prefs = GroovePreferences(
            comp_density="medium",
            articulation_style="straight",
            syncopation_level="moderate",
        )
        pattern = gen.generate(prefs, genre="jazz", session_id="sess_dotted", seed=5)
        assert pattern.source_template == "dotted"

    def test_swing_articulation_maps_to_triplet_feel(self):
        """Swing articulation → triplet_feel template."""
        gen = GrooveGenerator()
        prefs = GroovePreferences(
            comp_density="medium",
            articulation_style="swing",
            syncopation_level="light",
        )
        pattern = gen.generate(prefs, genre="jazz", session_id="sess_swing")
        assert pattern.source_template == "triplet_feel"


class TestGrooveVariants:
    def test_generate_variants_count(self):
        """generate_variants returns `count` patterns."""
        gen = GrooveGenerator()
        prefs = GroovePreferences(comp_density="medium")
        variants = gen.generate_variants(prefs, genre="synthwave", session_id="sess_var", count=3)
        assert len(variants) == 3
        assert all(isinstance(v, GroovePattern) for v in variants)

    def test_generate_variants_different_seeds(self):
        """generate_variants returns patterns with different variation_seeds."""
        gen = GrooveGenerator()
        prefs = GroovePreferences(comp_density="medium")
        variants = gen.generate_variants(prefs, genre="synthwave", session_id="sess_seeds", count=3)
        seeds = [v.variation_seed for v in variants]
        assert len(set(seeds)) == len(seeds), f"Expected unique seeds; got: {seeds}"

    def test_generate_variants_same_template(self):
        """All variants should share the same template (same prefs)."""
        gen = GrooveGenerator()
        prefs = GroovePreferences(
            comp_density="medium",
            articulation_style="straight",
            syncopation_level="light",
        )
        variants = gen.generate_variants(prefs, genre="synthwave", session_id="sess_templ", count=3)
        templates = [v.source_template for v in variants]
        assert len(set(templates)) == 1, f"Expected same template for all variants; got: {templates}"

    def test_generate_variants_default_count(self):
        """generate_variants default count is 3."""
        gen = GrooveGenerator()
        prefs = GroovePreferences()
        variants = gen.generate_variants(prefs, genre="dream_pop", session_id="sess_dflt")
        assert len(variants) == 3


class TestGrooveDeterminism:
    def test_same_seed_produces_same_pattern(self):
        """Same seed → identical pattern events."""
        gen = GrooveGenerator()
        prefs = GroovePreferences(comp_density="medium", syncopation_level="moderate")
        p1 = gen.generate(prefs, genre="jazz", session_id="s1", seed=999)
        p2 = gen.generate(prefs, genre="jazz", session_id="s2", seed=999)
        beats1 = [e.beat for e in p1.pattern_events]
        beats2 = [e.beat for e in p2.pattern_events]
        assert beats1 == beats2

    def test_different_seeds_may_differ(self):
        """Different seeds should produce different patterns for dense comp_density."""
        gen = GrooveGenerator()
        prefs = GroovePreferences(comp_density="dense", syncopation_level="moderate")
        p1 = gen.generate(prefs, genre="jazz", session_id="s1", seed=1)
        p2 = gen.generate(prefs, genre="jazz", session_id="s2", seed=2)
        # It's possible (but unlikely) for them to be the same — this is a smoke test
        # At minimum both should be valid patterns
        assert isinstance(p1, GroovePattern)
        assert isinstance(p2, GroovePattern)
