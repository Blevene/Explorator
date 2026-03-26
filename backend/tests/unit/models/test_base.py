"""Tests for base entity models."""

from datetime import UTC, datetime

from explorator.models.base import BaseEntity, CandidateBase, EvaluationBase


def test_base_entity_creation() -> None:
    entity = BaseEntity(
        id="test_01",
        type="test",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        status="active",
    )
    assert entity.id == "test_01"
    assert entity.type == "test"
    assert entity.version == 1
    assert entity.metadata == {}
    assert entity.status == "active"


def test_base_entity_requires_id() -> None:
    try:
        BaseEntity(
            type="test",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            status="active",
        )  # type: ignore[call-arg]
        raise AssertionError("Should have raised ValidationError")
    except Exception:
        pass


def test_candidate_base_extends_base_entity() -> None:
    candidate = CandidateBase(
        id="prog_01",
        type="progression_candidate",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        status="candidate",
        session_id="sess_01",
        family_id=None,
        rationale="Test progression",
    )
    assert candidate.session_id == "sess_01"
    assert candidate.intent_tags == []
    assert candidate.mutation_lineage_ids == []
    assert candidate.warnings == []


def test_evaluation_base_extends_base_entity() -> None:
    evaluation = EvaluationBase(
        id="eval_01",
        type="theory_evaluation",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        status="completed",
        candidate_id="prog_01",
        evaluation_type="theory",
    )
    assert evaluation.candidate_id == "prog_01"
    assert evaluation.evaluation_type == "theory"
    assert evaluation.notes == []
