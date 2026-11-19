
"""Unit tests for the adaptive decision engine.

Run independently:
    python -m pytest tests/test_adaptive_engine.py -v

These tests use no database and modify no prescriptions.
"""

import pytest

from app.services import adaptive_engine
from app.services.adaptive_engine import decide_adaptation


def make_trend(
    values=None,
    *,
    confidence="robust",
    prescribed=10,
    change_pct=10.0,
):
    """Build a representative progress-analysis result."""

    if values is None:
        values = [8, 9, 10, 11, 12]

    points = [
        {
            "date": f"2026-11-{day:02d}",
            "actual": actual,
            "prescribed": prescribed,
        }
        for day, actual in enumerate(values, start=1)
    ]

    return {
        "exercise_id": 101,
        "set_number": 1,
        "metric": "reps",
        "load_basis": "bodyweight",
        "observation_type": "training",
        "observation_count": len(points),
        "confidence": confidence,
        "change_pct": change_pct,
        "points": points,
    }


@pytest.mark.parametrize("values", [
    [10],
    [10, 12],
])
def test_insufficient_observations(values):
    trend = make_trend(
        values,
        confidence="insufficient",
    )

    decision = decide_adaptation(trend)

    assert decision["action"] == "insufficient_data"
    assert decision["observation_count"] == len(values)


@pytest.mark.parametrize("count", [3, 4])
def test_preliminary_evidence_maintains(count):
    trend = make_trend(
        [12] * count,
        confidence="preliminary",
        change_pct=20.0,
    )

    decision = decide_adaptation(trend)

    assert decision["action"] == "maintain"
    assert "Preliminary" in decision["reason"]


def test_robust_positive_trend_progresses():
    trend = make_trend(
        [8, 9, 10, 11, 12],
        change_pct=10.0,
    )

    decision = decide_adaptation(trend)

    assert decision["action"] == "progress"
    assert decision["confidence"] == "robust"
    assert decision["exercise_id"] == 101
    assert decision["set_number"] == 1


def test_progression_at_exact_threshold():
    trend = make_trend(change_pct=5.0)

    decision = decide_adaptation(trend)

    assert decision["action"] == "progress"


def test_below_progression_threshold_maintains():
    trend = make_trend(change_pct=4.99)

    decision = decide_adaptation(trend)

    assert decision["action"] == "maintain"


def test_stable_performance_maintains():
    trend = make_trend(
        [10, 10, 10, 10, 10],
        change_pct=0.0,
    )

    decision = decide_adaptation(trend)

    assert decision["action"] == "maintain"


def test_negative_trend_requests_review():
    trend = make_trend(
        [12, 11, 10, 9, 8],
        change_pct=-10.0,
    )

    decision = decide_adaptation(trend)

    assert decision["action"] == "review_regression"
    assert "Review" in decision["reason"]


def test_regression_at_exact_threshold():
    trend = make_trend(
        change_pct=-5.0,
    )

    decision = decide_adaptation(trend)

    assert decision["action"] == "review_regression"


def test_above_regression_threshold_maintains():
    trend = make_trend(
        change_pct=-4.99,
    )

    decision = decide_adaptation(trend)

    assert decision["action"] == "maintain"


def test_positive_trend_but_targets_not_met():
    trend = make_trend(
        [8, 9, 10, 11, 12],
        prescribed=15,
        change_pct=20.0,
    )

    decision = decide_adaptation(trend)

    assert decision["action"] == "maintain"
    assert "target" in decision["reason"].lower()


def test_missing_targets_prevent_progression():
    trend = make_trend(
        prescribed=None,
        change_pct=15.0,
    )

    decision = decide_adaptation(trend)

    assert decision["action"] == "maintain"


def test_partial_target_history_prevents_progression():
    trend = make_trend(
        change_pct=15.0,
    )

    trend["points"][-2]["prescribed"] = None

    decision = decide_adaptation(trend)

    assert decision["action"] == "maintain"


def test_only_latest_three_targets_matter():
    trend = make_trend(
        [5, 6, 10, 11, 12],
        prescribed=10,
        change_pct=20.0,
    )

    decision = decide_adaptation(trend)

    assert decision["action"] == "progress"


def test_missing_trend_percentage_maintains():
    trend = make_trend(change_pct=None)

    decision = decide_adaptation(trend)

    assert decision["action"] == "maintain"


def test_inconsistent_confidence_does_not_progress():
    trend = make_trend(
        [10, 11, 12, 13],
        confidence="robust",
        change_pct=20.0,
    )

    decision = decide_adaptation(trend)

    assert decision["action"] == "maintain"


def test_decision_preserves_source_metadata():
    trend = make_trend(change_pct=8.0)

    decision = decide_adaptation(trend)

    assert decision["exercise_id"] == trend["exercise_id"]
    assert decision["set_number"] == trend["set_number"]
    assert decision["confidence"] == trend["confidence"]
    assert decision["observation_count"] == 5
    assert decision["change_pct"] == 8.0
    assert isinstance(decision["reason"], str)


def test_service_uses_training_history_and_user_scope(
    monkeypatch,
):
    """Ensure recommendations query only the requested user."""

    captured = {}
    expected_trend = make_trend()

    def fake_analysis(
        db,
        user_id,
        exercise_id,
        observation_type,
    ):
        captured.update({
            "db": db,
            "user_id": user_id,
            "exercise_id": exercise_id,
            "observation_type": observation_type,
        })

        return [expected_trend]

    monkeypatch.setattr(
        adaptive_engine,
        "analyze_exercise_progress",
        fake_analysis,
    )

    db = object()

    decisions = (
        adaptive_engine.recommend_exercise_adaptations(
            db=db,
            user_id=42,
            exercise_id=101,
        )
    )

    assert captured == {
        "db": db,
        "user_id": 42,
        "exercise_id": 101,
        "observation_type": "training",
    }

    assert len(decisions) == 1
    assert decisions[0]["action"] == "progress"


def test_empty_history_returns_no_decisions(monkeypatch):
    monkeypatch.setattr(
        adaptive_engine,
        "analyze_exercise_progress",
        lambda **kwargs: [],
    )

    decisions = (
        adaptive_engine.recommend_exercise_adaptations(
            db=object(),
            user_id=42,
            exercise_id=101,
        )
    )

    assert decisions == []


def test_recommendation_does_not_mutate_trend():
    trend = make_trend()

    original_points = [
        point.copy()
        for point in trend["points"]
    ]

    decide_adaptation(trend)

    assert trend["points"] == original_points
