"""Memory, feedback, and user preference models."""

from typing import Any

from pydantic import Field

from explorator.models.base import BaseEntity


class UserPreferenceProfile(BaseEntity):
    """Persistent user taste model."""

    preferred_complexity_band: str = "medium"
    preferred_novelty_band: str = "moderate"
    voicing_preferences: dict[str, bool] = Field(default_factory=dict)
    bass_preferences: dict[str, bool] = Field(default_factory=dict)
    melodic_preferences: dict[str, bool] = Field(default_factory=dict)
    genre_biases: dict[str, float] = Field(default_factory=dict)
    disliked_patterns: list[str] = Field(default_factory=list)


class UserFeedbackEvent(BaseEntity):
    """Explicit user reaction."""

    session_id: str
    candidate_id: str
    feedback_type: str = "text_reaction"
    content: str = ""
    interpreted_adjustments: dict[str, Any] = Field(default_factory=dict)


class PatternLibraryEntry(BaseEntity):
    """Reusable discovered pattern. Deferred to M5."""

    pattern_type: str
    genre: str
    tags: list[str] = Field(default_factory=list)
    source_candidate_id: str | None = None
    abstracted_pattern: dict[str, Any] = Field(default_factory=dict)
    success_metrics: dict[str, float] = Field(default_factory=dict)
    notes: str = ""


class RetrievalQuery(BaseEntity):
    """Memory retrieval request. Deferred to M5."""

    session_id: str
    target_store: str = "pattern_library"
    query_tags: list[str] = Field(default_factory=list)
    top_k: int = 5


class RetrievalResult(BaseEntity):
    """Memory retrieval result. Deferred to M5."""

    retrieval_query_id: str
    matched_entry_ids: list[str] = Field(default_factory=list)
    scores: list[float] = Field(default_factory=list)
