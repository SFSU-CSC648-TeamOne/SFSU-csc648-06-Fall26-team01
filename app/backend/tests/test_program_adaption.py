
"""Tests for read-only program adaptation previews.

Run from app/backend:
    python -m pytest tests/test_program_adaptation.py -v

All tests use an isolated SQLite database.
"""

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.models

from app.core.errors import (
    ConflictError,
    NotFoundError,
    ValidationFailed,
)
from app.db.base import Base
from app.models import (
    Exercise,
    PerformanceEntry,
    PrescriptionSet,
    ProgramBaseline,
    User,
    WorkoutPrescription,
    WorkoutRecord,
)
from app.services.program_adaptation import (
    preview_program_propagation,
)


@pytest.fixture
def db():
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
        email="propagation-owner@example.com",
        password_hash="test-hash",
    )
    other = User(
        email="propagation-other@example.com",
        password_hash="test-hash",
    )
    exercise = Exercise(
        name="Propagation Test Push-Up"
    )
    alternate = Exercise(
        name="Propagation Test Squat"
    )

    db.add_all([owner, other, exercise, alternate])
    db.flush()

    baseline = ProgramBaseline(
        user_id=owner.id,
        program_slug="bw",
        attempt_id=str(uuid4()),
        results=[],
    )

    other_baseline = ProgramBaseline(
        user_id=owner.id,
        program_slug="bw",
        attempt_id=str(uuid4()),
        results=[],
    )

    db.add_all([baseline, other_baseline])
    db.commit()

    return {
        "owner_id": owner.id,
        "other_id": other.id,
        "exercise_id": exercise.id,
        "alternate_exercise_id": alternate.id,
        "baseline_id": baseline.id,
        "other_baseline_id": other_baseline.id,
    }


def make_prescription(
    db,
    data,
    *,
    week,
    day=1,
    reps=15,
    duration=None,
    weight=None,
    exercise_id=None,
    user_id=None,
    program="bw",
    baseline_id=None,
    status="planned",
    load_basis="bodyweight",
    optional=False,
):
    """Create a prescription with one set."""

    if baseline_id is None:
        baseline_id = data["baseline_id"]

    prescription = WorkoutPrescription(
        user_id=user_id or data["owner_id"],
        program_slug=program,
        program_week=week,
        program_day=day,
        status=status,
        engine_version="baseline-v1",
        source_baseline_id=baseline_id,
    )

    prescription.sets.append(
        PrescriptionSet(
            exercise_id=(
                exercise_id or data["exercise_id"]
            ),
            set_number=1,
            target_reps=reps,
            target_duration_seconds=duration,
            target_weight_kg=(
                Decimal(str(weight))
                if weight is not None
                else None
            ),
            load_basis=load_basis,
            is_optional=optional,
        )
    )

    db.add(prescription)
    db.commit()

    return prescription.id, prescription.sets[0].id


def preview(
    db,
    data,
    source_id,
    source_set_id,
    *,
    adjustment_type="reps",
    previous=15,
    approved=16,
):
    return preview_program_propagation(
        db=db,
        user_id=data["owner_id"],
        prescription_id=source_id,
        prescription_set_id=source_set_id,
        adjustment_type=adjustment_type,
        previous_value=Decimal(str(previous)),
        approved_value=Decimal(str(approved)),
    )


def make_source(db, data):
    """Create the already-approved source prescription."""

    return make_prescription(
        db,
        data,
        week=3,
        reps=16,
    )


# --------------------------------------------------
# Basic progression previews
# --------------------------------------------------

def test_progression_preserves_future_structure(
    db, data
):
    source_id, source_set_id = make_source(db, data)

    future_1, set_1 = make_prescription(
        db, data, week=4, reps=16
    )
    future_2, set_2 = make_prescription(
        db, data, week=5, reps=18
    )

    result = preview(
        db, data, source_id, source_set_id
    )

    assert result["status"] == "review_required"
    assert result["delta"] == 1
    assert result["database_modified"] is False

    assert len(result["candidates"]) == 2

    by_id = {
        item["prescription_set_id"]: item
        for item in result["candidates"]
    }

    assert by_id[set_1]["current_value"] == 16
    assert by_id[set_1]["proposed_value"] == 17

    assert by_id[set_2]["current_value"] == 18
    assert by_id[set_2]["proposed_value"] == 19

    assert all(
        item["requires_program_phase_review"]
        for item in result["candidates"]
    )


def test_only_future_workouts_considered(db, data):
    make_prescription(
        db, data, week=2, reps=14
    )

    source_id, source_set_id = make_source(db, data)

    make_prescription(
        db, data, week=3, day=2, reps=16
    )
    make_prescription(
        db, data, week=4, reps=17
    )

    result = preview(
        db, data, source_id, source_set_id
    )

    assert [
        (
            item["program_week"],
            item["program_day"],
        )
        for item in result["candidates"]
    ] == [(3, 2), (4, 1)]


def test_no_future_workouts_returns_empty_preview(
    db, data
):
    source_id, source_set_id = make_source(db, data)

    result = preview(
        db, data, source_id, source_set_id
    )

    assert result["candidates"] == []
    assert result["excluded"] == []
    assert result["database_modified"] is False


def test_preview_never_modifies_database(db, data):
    source_id, source_set_id = make_source(db, data)

    _, future_set_id = make_prescription(
        db, data, week=4, reps=18
    )

    result = preview(
        db, data, source_id, source_set_id
    )

    assert result["candidates"][0][
        "proposed_value"
    ] == 19

    db.expire_all()

    assert db.get(
        PrescriptionSet,
        future_set_id,
    ).target_reps == 18


# --------------------------------------------------
# Program and user isolation
# --------------------------------------------------

def test_different_program_excluded(db, data):
    source_id, source_set_id = make_source(db, data)

    make_prescription(
        db,
        data,
        week=4,
        program="ldw",
        reps=16,
    )

    result = preview(
        db, data, source_id, source_set_id
    )

    assert result["candidates"] == []


def test_different_baseline_excluded(db, data):
    source_id, source_set_id = make_source(db, data)

    make_prescription(
        db,
        data,
        week=4,
        baseline_id=data["other_baseline_id"],
    )

    result = preview(
        db, data, source_id, source_set_id
    )

    assert result["candidates"] == []


def test_other_user_prescriptions_excluded(db, data):
    source_id, source_set_id = make_source(db, data)

    make_prescription(
        db,
        data,
        week=4,
        user_id=data["other_id"],
    )

    result = preview(
        db, data, source_id, source_set_id
    )

    assert result["candidates"] == []


def test_other_user_cannot_preview_source(db, data):
    source_id, source_set_id = make_source(db, data)

    with pytest.raises(NotFoundError):
        preview_program_propagation(
            db=db,
            user_id=data["other_id"],
            prescription_id=source_id,
            prescription_set_id=source_set_id,
            adjustment_type="reps",
            previous_value=Decimal("15"),
            approved_value=Decimal("16"),
        )


# --------------------------------------------------
# Exercise compatibility
# --------------------------------------------------

def test_different_exercise_excluded(db, data):
    source_id, source_set_id = make_source(db, data)

    future_id, _ = make_prescription(
        db,
        data,
        week=4,
        exercise_id=data["alternate_exercise_id"],
    )

    result = preview(
        db, data, source_id, source_set_id
    )

    assert result["candidates"] == []

    assert result["excluded"] == [{
        "prescription_id": future_id,
        "program_week": 4,
        "program_day": 1,
        "reason": "missing_matching_set",
    }]


def test_different_load_basis_excluded(db, data):
    source_id, source_set_id = make_source(db, data)

    make_prescription(
        db,
        data,
        week=4,
        load_basis="external",
        weight=20,
    )

    result = preview(
        db, data, source_id, source_set_id
    )

    assert result["candidates"] == []
    assert result["excluded"][0]["reason"] == (
        "missing_matching_set"
    )


def test_optional_set_mismatch_excluded(db, data):
    source_id, source_set_id = make_source(db, data)

    make_prescription(
        db,
        data,
        week=4,
        optional=True,
    )

    result = preview(
        db, data, source_id, source_set_id
    )

    assert result["candidates"] == []


def test_ambiguous_matching_sets_excluded(db, data):
    source_id, source_set_id = make_source(db, data)

    future_id, _ = make_prescription(
        db, data, week=4
    )

    db.add(
        PrescriptionSet(
            workout_prescription_id=future_id,
            exercise_id=data["exercise_id"],
            set_number=1,
            target_reps=15,
            load_basis="bodyweight",
            is_optional=False,
        )
    )
    db.commit()

    result = preview(
        db, data, source_id, source_set_id
    )

    assert result["candidates"] == []
    assert result["excluded"][0]["reason"] == (
        "ambiguous_matching_sets"
    )


# --------------------------------------------------
# Historical data protection
# --------------------------------------------------

def test_recorded_future_workout_excluded(db, data):
    source_id, source_set_id = make_source(db, data)

    future_id, _ = make_prescription(
        db, data, week=4
    )

    db.add(
        WorkoutRecord(
            user_id=data["owner_id"],
            program_slug="bw",
            program_week=4,
            program_day=1,
        )
    )
    db.commit()

    result = preview(
        db, data, source_id, source_set_id
    )

    assert result["candidates"] == []

    assert result["excluded"][0] == {
        "prescription_id": future_id,
        "program_week": 4,
        "program_day": 1,
        "reason": "workout_history_exists",
    }


def test_linked_performance_entry_excludes_set(
    db, data
):
    source_id, source_set_id = make_source(db, data)

    _, future_set_id = make_prescription(
        db, data, week=4
    )

    record = WorkoutRecord(
        user_id=data["owner_id"],
        program_slug="other",
        program_week=1,
        program_day=1,
    )

    record.entries.append(
        PerformanceEntry(
            exercise_id=data["exercise_id"],
            prescription_set_id=future_set_id,
            set_number=1,
            reps=15,
            status="completed",
            observation_type="training",
            load_basis="bodyweight",
        )
    )

    db.add(record)
    db.commit()

    result = preview(
        db, data, source_id, source_set_id
    )

    assert result["candidates"] == []
    assert result["excluded"][0]["reason"] == (
        "set_has_recorded_performance"
    )


def test_completed_future_prescription_not_considered(
    db, data
):
    source_id, source_set_id = make_source(db, data)

    make_prescription(
        db,
        data,
        week=4,
        status="completed",
    )

    result = preview(
        db, data, source_id, source_set_id
    )

    assert result["candidates"] == []


# --------------------------------------------------
# Validation and conflicts
# --------------------------------------------------

def test_missing_source_baseline_rejected(db, data):
    source_id, source_set_id = make_source(db, data)

    source = db.get(WorkoutPrescription, source_id)
    source.source_baseline_id = None
    db.commit()

    with pytest.raises(ConflictError):
        preview(
            db, data, source_id, source_set_id
        )


def test_unapproved_source_target_rejected(db, data):
    source_id, source_set_id = make_source(db, data)

    with pytest.raises(ConflictError):
        preview(
            db,
            data,
            source_id,
            source_set_id,
            previous=15,
            approved=17,
        )


def test_non_planned_source_rejected(db, data):
    source_id, source_set_id = make_source(db, data)

    source = db.get(WorkoutPrescription, source_id)
    source.status = "completed"
    db.commit()

    with pytest.raises(ConflictError):
        preview(
            db, data, source_id, source_set_id
        )


def test_non_positive_progression_rejected(db, data):
    source_id, source_set_id = make_source(db, data)

    with pytest.raises(ValidationFailed):
        preview(
            db,
            data,
            source_id,
            source_set_id,
            previous=16,
            approved=16,
        )


def test_missing_target_metric_excluded(db, data):
    source_id, source_set_id = make_source(db, data)

    future_id, _ = make_prescription(
        db,
        data,
        week=4,
        reps=None,
        duration=60,
    )

    result = preview(
        db, data, source_id, source_set_id
    )

    assert result["candidates"] == []
    assert result["excluded"][0] == {
        "prescription_id": future_id,
        "program_week": 4,
        "program_day": 1,
        "reason": "target_metric_missing",
    }


def test_duration_progression(db, data):
    source_id, source_set_id = make_prescription(
        db,
        data,
        week=3,
        reps=None,
        duration=65,
    )

    _, future_set_id = make_prescription(
        db,
        data,
        week=4,
        reps=None,
        duration=75,
    )

    result = preview(
        db,
        data,
        source_id,
        source_set_id,
        adjustment_type="duration",
        previous=60,
        approved=65,
    )

    assert len(result["candidates"]) == 1

    candidate = result["candidates"][0]

    assert candidate["prescription_set_id"] == future_set_id
    assert candidate["current_value"] == 75
    assert candidate["proposed_value"] == 80


def test_weight_progression(db, data):
    source_id, source_set_id = make_prescription(
        db,
        data,
        week=3,
        reps=8,
        weight="62.50",
        load_basis="external",
    )

    _, future_set_id = make_prescription(
        db,
        data,
        week=4,
        reps=8,
        weight="70.00",
        load_basis="external",
    )

    result = preview(
        db,
        data,
        source_id,
        source_set_id,
        adjustment_type="weight",
        previous="60.00",
        approved="62.50",
    )

    candidate = result["candidates"][0]

    assert candidate["prescription_set_id"] == future_set_id
    assert candidate["current_value"] == 70.0
    assert candidate["proposed_value"] == 72.5
    assert result["database_modified"] is False
