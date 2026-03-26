"""Search plan, rounds, mutation, and selection models."""


from pydantic import BaseModel, Field

from explorator.models.base import BaseEntity


class StopConditions(BaseModel):
    """Configurable stop conditions."""

    target_score: float = 8.5
    max_rounds: int = 4


class SearchPlan(BaseEntity):
    """Exploration strategy for the session."""

    session_id: str
    search_strategy: str = "beam_plus_mutation"
    initial_generation_count: int = 12
    progression_selection_count: int = 4
    arrangement_selection_count: int = 4
    max_rounds: int = 4
    mutation_budget_per_round: int = 6
    diversity_target: float = 0.65
    stop_conditions: StopConditions = Field(default_factory=StopConditions)
    random_seed: int | None = None


class SearchRound(BaseEntity):
    """One iteration of exploration."""

    session_id: str
    round_number: int
    input_candidate_ids: list[str] = Field(default_factory=list)
    generated_candidate_ids: list[str] = Field(default_factory=list)
    selected_candidate_ids: list[str] = Field(default_factory=list)
    eliminated_candidate_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class MutationChange(BaseModel):
    """One change within a mutation."""

    field: str
    operation: str
    description: str


class MutationRecord(BaseEntity):
    """Tracks a concrete transformation."""

    source_candidate_id: str
    source_candidate_type: str
    result_candidate_id: str
    result_candidate_type: str
    mutation_scope: str
    changes: list[MutationChange] = Field(default_factory=list)
    reason: str = ""
    predicted_effects: list[str] = Field(default_factory=list)
    actual_score_delta: dict[str, float] = Field(default_factory=dict)


class ParetoFrontSnapshot(BaseEntity):
    """Non-dominated candidates for a round."""

    session_id: str
    round_number: int
    candidate_ids: list[str] = Field(default_factory=list)
    axes: list[str] = Field(default_factory=list)


class FinalSelection(BaseEntity):
    """Chosen outputs."""

    session_id: str
    selected_candidate_ids: list[str] = Field(default_factory=list)
    selection_roles: dict[str, str] = Field(default_factory=dict)
    selection_notes: list[str] = Field(default_factory=list)
