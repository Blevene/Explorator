"""_build_voicing_prefs tolerates the genre catalog's extended voicing vocabulary."""

from explorator.engine.nodes.plan_voicings import _build_voicing_prefs


def test_maps_catalog_vocabulary_to_supported_literals() -> None:
    profile = {
        "voicing_preferences": {
            "default_voicing_type": "closed",   # -> close
            "default_density": "sparse",        # -> thin
            "default_register": "high",         # supported
            "variant_voicing_types": ["cluster", "quartal", "drop2", "closed"],
        }
    }
    prefs = _build_voicing_prefs(profile)
    assert prefs.default_voicing_type == "close"
    assert prefs.default_density == "thin"
    assert prefs.default_register == "high"
    # cluster->close, quartal->open, drop2->drop2, closed->close (deduped)
    assert prefs.variant_voicing_types == ["close", "open", "drop2"]


def test_density_scale_maps_to_three_levels() -> None:
    for catalog, expected in [
        ("low", "thin"), ("low_medium", "medium"), ("medium", "medium"),
        ("high", "full"), ("dense", "full"), ("active", "full"),
    ]:
        prefs = _build_voicing_prefs({"voicing_preferences": {"default_density": catalog}})
        assert prefs.default_density == expected, catalog


def test_unknown_values_fall_back_to_defaults_without_raising() -> None:
    prefs = _build_voicing_prefs(
        {"voicing_preferences": {"default_voicing_type": "wat", "default_density": 42}}
    )
    assert prefs.default_voicing_type == "open"
    assert prefs.default_density == "medium"


def test_missing_or_non_dict_returns_defaults() -> None:
    assert _build_voicing_prefs({}).default_voicing_type == "open"
    assert _build_voicing_prefs({"voicing_preferences": "nope"}).default_density == "medium"
