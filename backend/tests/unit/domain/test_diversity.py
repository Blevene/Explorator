"""Tests for diversity distance functions."""

import math

from explorator.domain.evaluation.ranking import (
    chord_edit_distance,
    score_space_distance,
)


def test_chord_edit_distance_identical() -> None:
    assert chord_edit_distance(["C", "G", "Am", "F"], ["C", "G", "Am", "F"]) == 0


def test_chord_edit_distance_one_diff() -> None:
    assert chord_edit_distance(["C", "G", "Am", "F"], ["C", "G", "Am", "E"]) == 1


def test_chord_edit_distance_all_different() -> None:
    assert chord_edit_distance(["C", "G"], ["Am", "F"]) == 2


def test_chord_edit_distance_different_lengths() -> None:
    assert chord_edit_distance(["C", "G"], ["C", "G", "Am", "F"]) == 2


def test_chord_edit_distance_empty() -> None:
    assert chord_edit_distance([], []) == 0
    assert chord_edit_distance(["C"], []) == 1


def test_score_space_distance_identical() -> None:
    scores = {"a": 5.0, "b": 5.0}
    assert score_space_distance(scores, scores) == 0.0


def test_score_space_distance_basic() -> None:
    a = {"x": 3.0, "y": 0.0}
    b = {"x": 0.0, "y": 4.0}
    assert abs(score_space_distance(a, b) - 5.0) < 0.01


def test_score_space_distance_missing_dims() -> None:
    a = {"x": 5.0}
    b = {"x": 5.0, "y": 3.0}
    assert abs(score_space_distance(a, b) - 3.0) < 0.01
