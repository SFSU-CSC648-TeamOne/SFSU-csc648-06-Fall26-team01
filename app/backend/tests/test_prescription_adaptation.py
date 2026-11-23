"""Tests for read-only workout prescription adaptation.

Run from app/backend:
    python -m pytest tests/test_prescription_adaptation.py -v
"""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.models
from app.db.base import Base
from app.models import (
    Exercise,
    PrescriptionSet,
    User,
    WorkoutPrescription,
)
from app.services import prescription_adaptation as service


@pytest.fixture
def db():
    """Fresh isolated SQLite database per test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


@pytest.fixture
def data(db):
    owner = User(
        email="adapt-owner@example.com",
        password_hash="test-hash",
    )
    other = User(
        email="adapt-other@example.com",
        password_hash="test-hash",
    )
    pushup = Exercise(name="Adaptation Test Push-Up")
    bench = Exercise(name="Adaptation Test Bench Press")

    db.add_all([owner, other, pushup, bench])
    db.commit()

    return {
        "owner": owner,
        "other": other,
        "pushup": pushup,
        "bench": bench,
    }


def create_prescription(
    db,
    user_id,
    exercise_id,
    *,
    status="planned",
    set_number=1,
    reps=15,
    duration=None,
    load_basis="bodyweight",
    weight=None,
):
    prescription = WorkoutPrescription(
        user_id=user_id,
        program_slug="strong",
        program_week=3,
        program_day=1,
        status=status,
        engine_version="baseline-v1",
    )

    prescribed_set = PrescriptionSet(
        exercise_id=exercise_id,
        set_number=set_number,
        target_reps=reps,
        target_duration_seconds=duration,
        target_weight_kg=(Decimal(str(weight)) if weight is not None else None),
        load_basis=load_basis,
    )

    prescription.sets.append(prescribed_set)
    db.add(prescription)
    db.commit()

    return prescription


def make_trend(
    exercise_id,
    *,
    set_number=1,
    metric="reps",
    load_basis="bodyweight",
    weight=None,
    assistance=None,
    count=5,
    confidence="robust",
    change_pct=15.0,
    prescribed=15,
):
    return {
        "exercise_id": exercise_id,
        "set_number": set_number,
        "metric": metric,
        "load_basis": load_basis,
        "weight_kg": weight,
        "assistance_kg": assistance,
        "observation_count": count,
        "confidence": confidence,
        "change_pct": change_pct,
        "points": [
            {
                "date": f"2026-11-{i + 1:02d}",
                "actual": prescribed + i,
                "prescribed": prescribed,
            }
            for i in range(count)
        ],
    }


def mock_history(monkeypatch, trends):
    def fake_analysis(
        db,
        user_id,
        exercise_id,
        observation_type,
    ):
        assert observation_type == "training"
        return [trend for trend in trends if trend["exercise_id"] == exercise_id]

    monkeypatch.setattr(
        service,
        "analyze_exercise_progress",
        fake_analysis,
    )


def analyze(db, user_id, prescription):
    return service.analyze_prescription_adaptations(
        db=db,
        user_id=user_id,
        prescription_id=prescription.id,
    )


def test_no_history_returns_insufficient_data(db, data, monkeypatch):
    prescription = create_prescription(
        db,
        data["owner"].id,
        data["pushup"].id,
    )

    mock_history(monkeypatch, [])

    result = analyze(db, data["owner"].id, prescription)
    item = result["sets"][0]

    assert item["decision"]["action"] == "insufficient_data"
    assert item["proposal"]["adjustment_type"] == "none"
    assert item["proposal"]["requires_approval"] is False


def test_robust_bodyweight_progression(db, data, monkeypatch):
    prescription = create_prescription(
        db,
        data["owner"].id,
        data["pushup"].id,
        reps=15,
    )

    mock_history(monkeypatch, [make_trend(data["pushup"].id)])

    result = analyze(db, data["owner"].id, prescription)
    item = result["sets"][0]

    assert result["status"] == "proposed"
    assert result["prescription_id"] == prescription.id
    assert result["user_id"] == data["owner"].id
    assert result["proposal_engine_version"] == ("adaptive-v1-proposal")

    assert item["decision"]["action"] == "progress"
    assert item["proposal"]["adjustment_type"] == "reps"
    assert item["proposal"]["previous_value"] == 15
    assert item["proposal"]["proposed_value"] == 16
    assert item["proposal"]["requires_approval"] is True


def test_duration_progression(db, data, monkeypatch):
    prescription = create_prescription(
        db,
        data["owner"].id,
        data["pushup"].id,
        reps=None,
        duration=120,
    )

    mock_history(
        monkeypatch,
        [
            make_trend(
                data["pushup"].id,
                metric="seconds",
                prescribed=120,
            )
        ],
    )

    result = analyze(db, data["owner"].id, prescription)
    proposal = result["sets"][0]["proposal"]

    assert proposal["adjustment_type"] == "duration"
    assert proposal["previous_value"] == 120
    assert proposal["proposed_value"] == 125


def test_external_weight_progression(db, data, monkeypatch):
    prescription = create_prescription(
        db,
        data["owner"].id,
        data["bench"].id,
        reps=10,
        load_basis="external",
        weight="60",
    )

    mock_history(
        monkeypatch,
        [
            make_trend(
                data["bench"].id,
                load_basis="external",
                weight=60.0,
                prescribed=10,
            )
        ],
    )

    result = analyze(db, data["owner"].id, prescription)
    proposal = result["sets"][0]["proposal"]

    assert proposal["adjustment_type"] == "weight"
    assert proposal["previous_value"] == 60.0
    assert proposal["proposed_value"] == 61.5
    assert proposal["requires_approval"] is True


def test_different_resistance_is_not_comparable(db, data, monkeypatch):
    prescription = create_prescription(
        db,
        data["owner"].id,
        data["bench"].id,
        reps=10,
        load_basis="external",
        weight="60",
    )

    mock_history(
        monkeypatch,
        [
            make_trend(
                data["bench"].id,
                load_basis="external",
                weight=50.0,
                prescribed=10,
            )
        ],
    )

    result = analyze(db, data["owner"].id, prescription)

    assert result["sets"][0]["decision"]["action"] == ("insufficient_data")
    assert result["sets"][0]["proposal"]["adjustment_type"] == ("none")


def test_mismatched_set_number_excluded(db, data, monkeypatch):
    prescription = create_prescription(
        db,
        data["owner"].id,
        data["pushup"].id,
        set_number=2,
    )

    mock_history(monkeypatch, [make_trend(data["pushup"].id, set_number=1)])

    result = analyze(db, data["owner"].id, prescription)

    assert result["sets"][0]["decision"]["action"] == ("insufficient_data")


def test_incompatible_metric_excluded(db, data, monkeypatch):
    prescription = create_prescription(
        db,
        data["owner"].id,
        data["pushup"].id,
        reps=15,
    )

    mock_history(
        monkeypatch,
        [
            make_trend(
                data["pushup"].id,
                metric="seconds",
            )
        ],
    )

    result = analyze(db, data["owner"].id, prescription)

    assert result["sets"][0]["proposal"]["adjustment_type"] == ("none")


def test_assisted_prescription_not_adjusted(db, data, monkeypatch):
    prescription = create_prescription(
        db,
        data["owner"].id,
        data["pushup"].id,
        load_basis="assisted",
    )

    mock_history(
        monkeypatch,
        [
            make_trend(
                data["pushup"].id,
                load_basis="assisted",
                assistance=20.0,
            )
        ],
    )

    result = analyze(db, data["owner"].id, prescription)

    assert result["sets"][0]["proposal"]["adjustment_type"] == ("none")


@pytest.mark.parametrize(
    "status",
    [
        "completed",
        "skipped",
    ],
)
def test_non_planned_prescription_rejected(db, data, monkeypatch, status):
    prescription = create_prescription(
        db,
        data["owner"].id,
        data["pushup"].id,
        status=status,
    )

    mock_history(monkeypatch, [])

    with pytest.raises(ValueError):
        analyze(db, data["owner"].id, prescription)


def test_other_user_cannot_access_prescription(db, data, monkeypatch):
    prescription = create_prescription(
        db,
        data["owner"].id,
        data["pushup"].id,
    )

    mock_history(monkeypatch, [])

    with pytest.raises(LookupError):
        analyze(db, data["other"].id, prescription)


def test_unknown_prescription_rejected(db, data, monkeypatch):
    mock_history(monkeypatch, [])

    with pytest.raises(LookupError):
        service.analyze_prescription_adaptations(
            db=db,
            user_id=data["owner"].id,
            prescription_id=999999,
        )


def test_preliminary_evidence_does_not_progress(db, data, monkeypatch):
    prescription = create_prescription(
        db,
        data["owner"].id,
        data["pushup"].id,
    )

    mock_history(
        monkeypatch,
        [
            make_trend(
                data["pushup"].id,
                count=3,
                confidence="preliminary",
                change_pct=30.0,
            )
        ],
    )

    result = analyze(db, data["owner"].id, prescription)
    item = result["sets"][0]

    assert item["decision"]["action"] == "maintain"
    assert item["proposal"]["adjustment_type"] == "none"


def test_negative_trend_requests_review(db, data, monkeypatch):
    prescription = create_prescription(
        db,
        data["owner"].id,
        data["pushup"].id,
    )

    mock_history(
        monkeypatch,
        [
            make_trend(
                data["pushup"].id,
                change_pct=-12.0,
            )
        ],
    )

    result = analyze(db, data["owner"].id, prescription)
    item = result["sets"][0]

    assert item["decision"]["action"] == "review_regression"
    assert item["proposal"]["adjustment_type"] == "none"


def test_multiple_sets_are_evaluated(db, data, monkeypatch):
    prescription = create_prescription(
        db,
        data["owner"].id,
        data["pushup"].id,
        set_number=1,
    )

    second = PrescriptionSet(
        workout_prescription_id=prescription.id,
        exercise_id=data["pushup"].id,
        set_number=2,
        target_reps=12,
        load_basis="bodyweight",
    )

    db.add(second)
    db.commit()

    mock_history(
        monkeypatch,
        [
            make_trend(data["pushup"].id, set_number=1),
            make_trend(
                data["pushup"].id,
                set_number=2,
                prescribed=12,
            ),
        ],
    )

    result = analyze(db, data["owner"].id, prescription)

    assert len(result["sets"]) == 2
    assert {item["set_number"] for item in result["sets"]} == {1, 2}

    assert all(item["proposal"]["adjustment_type"] == "reps" for item in result["sets"])


def test_exercise_analysis_is_cached(db, data, monkeypatch):
    prescription = create_prescription(
        db,
        data["owner"].id,
        data["pushup"].id,
    )

    db.add(
        PrescriptionSet(
            workout_prescription_id=prescription.id,
            exercise_id=data["pushup"].id,
            set_number=2,
            target_reps=12,
            load_basis="bodyweight",
        )
    )
    db.commit()

    calls = []

    def fake_analysis(
        db,
        user_id,
        exercise_id,
        observation_type,
    ):
        calls.append((user_id, exercise_id, observation_type))
        return []

    monkeypatch.setattr(
        service,
        "analyze_exercise_progress",
        fake_analysis,
    )

    analyze(db, data["owner"].id, prescription)

    assert calls == [
        (
            data["owner"].id,
            data["pushup"].id,
            "training",
        )
    ]


def test_service_is_read_only(db, data, monkeypatch):
    prescription = create_prescription(
        db,
        data["owner"].id,
        data["pushup"].id,
        reps=15,
    )

    prescribed_set_id = prescription.sets[0].id

    mock_history(monkeypatch, [make_trend(data["pushup"].id)])

    result = analyze(db, data["owner"].id, prescription)

    assert result["sets"][0]["proposal"]["proposed_value"] == 16

    # Re-read the stored prescription. A proposal must
    # not alter its actual target.
    db.expire_all()

    stored_set = db.scalar(
        select(PrescriptionSet).where(PrescriptionSet.id == prescribed_set_id)
    )

    assert stored_set.target_reps == 15
    assert stored_set.target_weight_kg is None

    assert not db.new
    assert not db.dirty
    assert not db.deleted
