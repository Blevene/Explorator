import pytest


async def _seed(driver, arr_id, session_id="sess_curation_api"):
    async with driver.session() as s:
        await s.run(
            "MERGE (s:Session {id: $sid}) "
            "MERGE (a:ArrangementCandidate {id: $aid}) SET a.session_id = $sid",
            sid=session_id, aid=arr_id,
        )


@pytest.mark.asyncio
async def test_post_curation_curate_happy_path(client, neo4j_driver):
    from explorator.graph.pattern_library_repo import PatternLibraryRepo
    from explorator.models.memory import PatternLibraryEntry
    await _seed(neo4j_driver, "arr_api_curate")
    pl = PatternLibraryRepo(neo4j_driver)
    await pl.upsert(PatternLibraryEntry(
        id="pl_api_curate_prog",
        type="pattern_library_entry",
        status="active",
        pattern_type="progression", genre="jazz",
        source_candidate_id="arr_api_curate",
        success_metrics={"weighted_total": 0.7},
    ))

    response = await client.post(
        "/v1/arrangements/arr_api_curate/curation",
        json={"curated": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["arrangement_id"] == "arr_api_curate"
    assert body["is_curated"] is True
    assert body["curated_at"] is not None
    assert len(body["affected_pattern_ids"]) == 1


@pytest.mark.asyncio
async def test_post_curation_uncurate(client, neo4j_driver):
    from explorator.graph.pattern_library_repo import PatternLibraryRepo
    from explorator.models.memory import PatternLibraryEntry
    from explorator.utils import utc_now
    await _seed(neo4j_driver, "arr_api_uncurate")
    pl = PatternLibraryRepo(neo4j_driver)
    await pl.upsert(PatternLibraryEntry(
        id="pl_api_uncurate_prog",
        type="pattern_library_entry",
        status="active",
        pattern_type="progression", genre="jazz",
        source_candidate_id="arr_api_uncurate",
        success_metrics={"weighted_total": 0.7},
    ))
    await pl.toggle_curation(
        arrangement_id="arr_api_uncurate", is_curated=True, now=utc_now(),
    )

    response = await client.post(
        "/v1/arrangements/arr_api_uncurate/curation",
        json={"curated": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_curated"] is False
    assert body["curated_at"] is None


@pytest.mark.asyncio
async def test_post_curation_404_unknown_arrangement(client):
    response = await client.post(
        "/v1/arrangements/arr_does_not_exist/curation",
        json={"curated": True},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_post_curation_409_no_harvested_patterns(client, neo4j_driver):
    await _seed(neo4j_driver, "arr_api_noharv")
    # No PatternLibraryEntry seeded.

    response = await client.post(
        "/v1/arrangements/arr_api_noharv/curation",
        json={"curated": True},
    )
    assert response.status_code == 409

    # Confirm no event was written.
    from explorator.graph.feedback_repo import FeedbackEventRepo
    fb = FeedbackEventRepo(neo4j_driver)
    events = await fb.list_by_session("sess_curation_api")
    curation_events = [
        e for e in events
        if e.get("feedback_type") == "pattern_curation"
        and e.get("candidate_id") == "arr_api_noharv"
    ]
    assert curation_events == []


@pytest.mark.asyncio
async def test_post_curation_422_missing_body(client, neo4j_driver):
    await _seed(neo4j_driver, "arr_api_badbody")
    response = await client.post(
        "/v1/arrangements/arr_api_badbody/curation",
        json={},
    )
    assert response.status_code == 422
