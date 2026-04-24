from explorator.services.pattern_library.filters import PatternFilters


def test_pattern_filters_curated_only_default_false():
    f = PatternFilters()
    assert f.curated_only is False


def test_pattern_filters_curated_only_opt_in():
    f = PatternFilters(curated_only=True)
    assert f.curated_only is True
    assert f.genre is None
    assert f.pattern_type is None
