import pytest

from explorator.graph.feedback_repo import FeedbackEventRepo
from explorator.graph.pattern_library_repo import PatternLibraryRepo
from explorator.models.memory import PatternLibraryEntry
from explorator.services.pattern_library.curation_service import (
    ArrangementNotFound,
    PatternsNotHarvested,
    curate_arrangement,
)


async def _seed(driver, arr_id, session_id="sess_curate"):
    async with driver.session() as s:
        await s.run(
            "MERGE (s:Session {id: $sid}) "
            "MERGE (a:ArrangementCandidate {id: $aid}) SET a.session_id = $sid",
            sid=session_id, aid=arr_id,
        )


async def _seed_pattern(pl, arr_id, entry_id, ptype="progression"):
    await pl.upsert(PatternLibraryEntry(
        id=entry_id,
        type="pattern_library_entry",
        status="active",
        pattern_type=ptype, genre="jazz",
        source_candidate_id=arr_id,
        success_metrics={"weighted_total": 0.7},
    ))


@pytest.mark.asyncio
async def test_curate_arrangement_writes_event_and_flips_patterns(neo4j_driver):
    pl = PatternLibraryRepo(neo4j_driver)
    await _seed(neo4j_driver, "arr_svc_ok")
    await _seed_pattern(pl, "arr_svc_ok", "pl_svc_ok_prog")

    result = await curate_arrangement(
        driver=neo4j_driver,
        arrangement_id="arr_svc_ok",
        is_curated=True,
    )

    assert result.is_curated is True
    assert result.curated_at is not None
    assert len(result.affected_pattern_ids) == 1

    # Event was written.
    fb_repo = FeedbackEventRepo(neo4j_driver)
    events = await fb_repo.list_by_session("sess_curate")
    curation_events = [e for e in events if e.get("feedback_type") == "pattern_curation"]
    assert len(curation_events) == 1
    assert curation_events[0]["content"] == "curated"
    assert curation_events[0]["candidate_id"] == "arr_svc_ok"


@pytest.mark.asyncio
async def test_curate_arrangement_404_on_missing_arrangement(neo4j_driver):
    with pytest.raises(ArrangementNotFound):
        await curate_arrangement(
            driver=neo4j_driver,
            arrangement_id="arr_does_not_exist",
            is_curated=True,
        )


@pytest.mark.asyncio
async def test_curate_arrangement_409_when_no_patterns_and_no_event(neo4j_driver, caplog):
    import logging
    await _seed(neo4j_driver, "arr_svc_noharv")
    # No PatternLibraryEntry seeded.

    caplog.set_level(logging.WARNING)
    with pytest.raises(PatternsNotHarvested):
        await curate_arrangement(
            driver=neo4j_driver,
            arrangement_id="arr_svc_noharv",
            is_curated=True,
        )
    # No event should have been written.
    fb_repo = FeedbackEventRepo(neo4j_driver)
    events = await fb_repo.list_by_session("sess_curate")
    curation_events = [
        e for e in events
        if e.get("feedback_type") == "pattern_curation"
        and e.get("candidate_id") == "arr_svc_noharv"
    ]
    assert curation_events == []
    # WARN log mentions the arrangement and session.
    assert any("arr_svc_noharv" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_curate_then_uncurate_two_events_final_state_uncurated(neo4j_driver):
    pl = PatternLibraryRepo(neo4j_driver)
    await _seed(neo4j_driver, "arr_svc_flip")
    await _seed_pattern(pl, "arr_svc_flip", "pl_svc_flip_prog")

    await curate_arrangement(
        driver=neo4j_driver, arrangement_id="arr_svc_flip", is_curated=True,
    )
    result = await curate_arrangement(
        driver=neo4j_driver, arrangement_id="arr_svc_flip", is_curated=False,
    )
    assert result.is_curated is False
    assert result.curated_at is None
    fb_repo = FeedbackEventRepo(neo4j_driver)
    events = await fb_repo.list_by_session("sess_curate")
    flip_events = [
        e for e in events
        if e.get("feedback_type") == "pattern_curation"
        and e.get("candidate_id") == "arr_svc_flip"
    ]
    assert len(flip_events) == 2
    assert {e["content"] for e in flip_events} == {"curated", "uncurated"}
