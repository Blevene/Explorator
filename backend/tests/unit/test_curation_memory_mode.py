"""Curation service degradation in memory mode (Neo4j absent)."""
import pytest

from explorator.services.pattern_library.curation_service import (
    PatternsNotHarvested,
    curate_arrangement,
)


async def test_curate_arrangement_raises_when_driver_none():
    """With no driver there is nothing to curate → PatternsNotHarvested (→ 409)."""
    with pytest.raises(PatternsNotHarvested):
        await curate_arrangement(
            driver=None, arrangement_id="arr_x", is_curated=True
        )
