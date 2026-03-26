"""Integration test: JSON serialization round-trip for ProgressionCandidate."""

import json

from neo4j import AsyncDriver

from explorator.graph.repository import BaseRepository
from explorator.models.harmony import ChordEvent, ProgressionCandidate


class ProgressionCandidateRepository(BaseRepository):
    """Minimal repository for ProgressionCandidate nodes."""

    label = "ProgressionCandidate"


async def test_progression_candidate_chord_events_round_trip(neo4j_driver: AsyncDriver) -> None:
    """Create a ProgressionCandidate with ChordEvents, persist to Neo4j, read back,
    and verify chord_events are stored and retrievable as a JSON string.
    """
    chord_events = [
        ChordEvent(bar=1, beat=1.0, duration_beats=4.0, symbol="Cmaj7", function_label="I"),
        ChordEvent(bar=2, beat=1.0, duration_beats=4.0, symbol="Am7", function_label="vi"),
        ChordEvent(bar=3, beat=1.0, duration_beats=4.0, symbol="Fmaj7", function_label="IV"),
        ChordEvent(bar=4, beat=1.0, duration_beats=4.0, symbol="G7", function_label="V"),
    ]
    candidate = ProgressionCandidate(
        id="prog_rt_01",
        type="progression_candidate",
        status="candidate",
        session_id="sess_rt_01",
        rationale="Round-trip serialization test",
        key_center="C",
        mode="major",
        phrase_length_bars=4,
        chord_events=chord_events,
    )

    repo = ProgressionCandidateRepository(neo4j_driver)
    await repo.create(candidate)

    result = await repo.get_by_id("prog_rt_01")

    assert result is not None
    assert result["id"] == "prog_rt_01"
    assert result["key_center"] == "C"
    assert result["status"] == "candidate"

    # chord_events is a list of dicts (non-primitive), so the BaseRepository
    # serialises it to a JSON string when storing in Neo4j.
    raw_events = result["chord_events"]
    assert isinstance(raw_events, str), (
        f"Expected chord_events to be stored as JSON string, got {type(raw_events)}"
    )

    parsed_events = json.loads(raw_events)
    assert isinstance(parsed_events, list)
    assert len(parsed_events) == 4

    first = parsed_events[0]
    assert first["bar"] == 1
    assert first["symbol"] == "Cmaj7"
    assert first["function_label"] == "I"
    assert first["beat"] == 1.0
    assert first["duration_beats"] == 4.0

    # Verify all four chords are present in order
    symbols = [e["symbol"] for e in parsed_events]
    assert symbols == ["Cmaj7", "Am7", "Fmaj7", "G7"]
