"""Forward-compatibility stub models. Not active until v1.5/M5."""

from typing import Any

from pydantic import Field

from explorator.models.base import BaseEntity


class Melody(BaseEntity):
    """User-supplied or generated primary melody. Deferred to v1.5."""

    session_id: str
    source_type: str = "user_supplied"
    note_events_json: list[dict[str, Any]] = Field(default_factory=list)
    range_low: str | None = None
    range_high: str | None = None


class InstrumentRealizationPlan(BaseEntity):
    """Instrument role assignments. Deferred to M5."""

    arrangement_candidate_id: str
    instrument_roles: list[dict[str, str]] = Field(default_factory=list)
    orchestration_notes: list[str] = Field(default_factory=list)
