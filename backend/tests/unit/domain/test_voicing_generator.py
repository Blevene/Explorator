# backend/tests/unit/domain/test_voicing_generator.py

from explorator.domain.realization.voicing import VoicingGenerator
from explorator.models.realization import (
    ChordVoicingInstruction,
    VariantConfig,
    VoicingEvent,
    VoicingPlan,
    VoicingPreferences,
    VoicingStrategyResponse,
)


def _make_strategy() -> VoicingStrategyResponse:
    return VoicingStrategyResponse(
        global_strategy="open spacing, favor 7ths",
        density_level="medium",
        voice_count=4,
        per_chord=[
            ChordVoicingInstruction(
                chord_symbol="Cmaj7",
                voicing_type="open",
                target_register="mid_high",
                extensions_to_include=[],
            ),
            ChordVoicingInstruction(
                chord_symbol="Am7",
                voicing_type="open",
                target_register="mid_high",
                extensions_to_include=[],
            ),
        ],
    )


class TestVoicingGeneratorRealize:
    def test_produces_voicing_plan(self):
        gen = VoicingGenerator()
        plan = gen.realize(
            _make_strategy(),
            ["Cmaj7", "Am7"],
            VoicingPreferences(default_register="mid_high"),
            VariantConfig(voicing_type="open"),
        )
        assert isinstance(plan, VoicingPlan)
        assert len(plan.voicing_events) == 2
        assert plan.voicing_events[0].chord_symbol == "Cmaj7"
        assert plan.voicing_events[1].chord_symbol == "Am7"

    def test_events_have_correct_pitches(self):
        gen = VoicingGenerator()
        plan = gen.realize(
            _make_strategy(),
            ["Cmaj7", "Am7"],
            VoicingPreferences(default_register="mid_high"),
            VariantConfig(voicing_type="close"),
        )
        for event in plan.voicing_events:
            assert isinstance(event, VoicingEvent)
            assert len(event.pitches) == 4
            for p in event.pitches:
                assert any(c.isdigit() for c in p)

    def test_variant_overrides_voicing_type(self):
        gen = VoicingGenerator()
        prefs = VoicingPreferences()
        plan_open = gen.realize(
            _make_strategy(), ["Cmaj7", "Am7"], prefs, VariantConfig(voicing_type="open")
        )
        plan_close = gen.realize(
            _make_strategy(), ["Cmaj7", "Am7"], prefs, VariantConfig(voicing_type="close")
        )
        assert plan_open.voicing_events[0].pitches != plan_close.voicing_events[0].pitches

    def test_generate_variants_produces_multiple(self):
        gen = VoicingGenerator()
        prefs = VoicingPreferences(variant_voicing_types=["open", "drop2", "close"])
        plans = gen.generate_variants(_make_strategy(), ["Cmaj7", "Am7"], prefs)
        assert len(plans) == 3
        for plan in plans:
            assert isinstance(plan, VoicingPlan)
            assert plan.global_strategy == "open spacing, favor 7ths"

    def test_entity_fields(self):
        gen = VoicingGenerator()
        plan = gen.realize(
            _make_strategy(),
            ["Cmaj7"],
            VoicingPreferences(),
            VariantConfig(voicing_type="open"),
        )
        assert plan.id.startswith("vp_")
        assert plan.type == "voicing_plan"
        assert plan.status == "draft"

    def test_fallback_when_strategy_has_fewer_chords(self):
        """Strategy has 2 per_chord entries but we pass 3 chord symbols."""
        gen = VoicingGenerator()
        plan = gen.realize(
            _make_strategy(),
            ["Cmaj7", "Am7", "Fmaj7"],
            VoicingPreferences(default_register="mid_high", default_voicing_type="open"),
            VariantConfig(voicing_type="open"),
        )
        assert len(plan.voicing_events) == 3  # fallback for 3rd chord
