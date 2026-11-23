"""Tests for enrollment-scoped program adaptation previews.

Run from app/backend:
    python -m pytest tests/test_program_adaptation_enrollment.py -v

Uses isolated, in-memory SQLite.
No Supabase or PostgreSQL connection is required.
"""

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.models

from app.core.errors import ConflictError, NotFoundError
from app.db.base import Base
from app.models.adaptation_approval import AdaptationApproval
from app.models.catalog import Exercise
from app.models.prescription import (
    PrescriptionSet,
    WorkoutPrescription,
)
from app.models.program_baseline import ProgramBaseline
from app.models.program_instance import ProgramInstance
from app.models.program_phase import ProgramPhase
from app.models.tracking import WorkoutRecord
from app.models.users import User
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
        email=f"owner-{uuid4().hex}@example.com",
        password_hash="test-hash",
    )
    other = User(
        email=f"other-{uuid4().hex}@example.com",
        password_hash="test-hash",
    )
    exercise = Exercise(name="Enrollment Test Push-Up")

    db.add_all([owner, other, exercise])
    db.flush()

    baseline = ProgramBaseline(
        user_id=owner.id,
        program_slug="bw",
        attempt_id=str(uuid4()),
        results=[],
    )
    db.add(baseline)
    db.flush()

    first = ProgramInstance(
        user_id=owner.id,
        program_slug="bw",
        source_baseline_id=baseline.id,
        status="active",
    )
    second = ProgramInstance(
        user_id=owner.id,
        program_slug="bw",
        source_baseline_id=baseline.id,
        status="active",
    )
    foreign = ProgramInstance(
        user_id=other.id,
        program_slug="bw",
        status="active",
    )

    db.add_all([first, second, foreign])
    db.commit()

    return {
        "owner": owner.id,
        "other": other.id,
        "exercise": exercise.id,
        "baseline": baseline.id,
        "first": first.id,
        "second": second.id,
        "foreign": foreign.id,
    }


def make_prescription(
    db,
    data,
    instance_id,
    *,
    week,
    day=1,
    reps=15,
    phase="training",
    status="planned",
):
    prescription = WorkoutPrescription(
        user_id=data["owner"],
        program_instance_id=instance_id,
        program_slug="bw",
        program_week=week,
        program_day=day,
        status=status,
        engine_version="test-v1",
        source_baseline_id=data["baseline"],
    )

    prescription.sets.append(
        PrescriptionSet(
            exercise_id=data["exercise"],
            set_number=1,
            target_reps=reps,
            load_basis="bodyweight",
            is_optional=False,
        )
    )

    db.add(prescription)
    db.flush()

    if phase is not None:
        db.add(
            ProgramPhase(
                workout_prescription_id=prescription.id,
                phase_type=phase,
            )
        )

    db.commit()
    return prescription.id, prescription.sets[0].id


def make_source(db, data):
    source_id, set_id = make_prescription(
        db,
        data,
        data["first"],
        week=2,
        reps=16,
    )

    db.add(
        AdaptationApproval(
            user_id=data["owner"],
            workout_prescription_id=source_id,
            prescription_set_id=set_id,
            adjustment_type="reps",
            previous_value=Decimal("15"),
            approved_value=Decimal("16"),
            proposal_engine_version="test-v1",
        )
    )
    db.commit()

    return source_id, set_id


def preview(
    db,
    data,
    source_id,
    set_id,
    *,
    instance_id=None,
    user_id=None,
):
    return preview_program_propagation(
        db=db,
        user_id=(data["owner"] if user_id is None else user_id),
        prescription_id=source_id,
        prescription_set_id=set_id,
        adjustment_type="reps",
        previous_value=Decimal("15"),
        approved_value=Decimal("16"),
        program_instance_id=(data["first"] if instance_id is None else instance_id),
    )


# --------------------------------------------------
# Enrollment isolation
# --------------------------------------------------


def test_only_selected_enrollment_is_considered(db, data):
    source_id, set_id = make_source(db, data)

    included_id, _ = make_prescription(db, data, data["first"], week=3, reps=18)

    excluded_id, _ = make_prescription(db, data, data["second"], week=3, reps=20)

    result = preview(db, data, source_id, set_id)

    candidate_ids = {item["prescription_id"] for item in result["candidates"]}

    assert result["program_instance_id"] == data["first"]
    assert candidate_ids == {included_id}
    assert excluded_id not in candidate_ids
    assert result["candidates"][0]["proposed_value"] == 19


def test_repeated_enrollment_same_baseline_remains_isolated(db, data):
    source_id, set_id = make_source(db, data)

    # Same owner, program, baseline, and workout position.
    first_id, _ = make_prescription(db, data, data["first"], week=4)
    second_id, _ = make_prescription(db, data, data["second"], week=4)

    result = preview(db, data, source_id, set_id)

    assert [item["prescription_id"] for item in result["candidates"]] == [first_id]

    assert second_id not in {item["prescription_id"] for item in result["candidates"]}


def test_foreign_source_enrollment_is_rejected(db, data):
    source_id, set_id = make_source(db, data)

    with pytest.raises(NotFoundError):
        preview(
            db,
            data,
            source_id,
            set_id,
            instance_id=data["second"],
        )


def test_other_user_cannot_access_enrollment(db, data):
    source_id, set_id = make_source(db, data)

    with pytest.raises(NotFoundError):
        preview(
            db,
            data,
            source_id,
            set_id,
            user_id=data["other"],
        )


def test_foreign_owned_enrollment_is_rejected(db, data):
    source_id, set_id = make_source(db, data)

    with pytest.raises(NotFoundError):
        preview(
            db,
            data,
            source_id,
            set_id,
            instance_id=data["foreign"],
        )


# --------------------------------------------------
# Enrollment status
# --------------------------------------------------


@pytest.mark.parametrize(
    "status",
    ["completed", "abandoned"],
)
def test_inactive_enrollment_is_rejected(db, data, status):
    source_id, set_id = make_source(db, data)

    instance = db.get(
        ProgramInstance,
        data["first"],
    )
    instance.status = status
    db.commit()

    with pytest.raises(ConflictError):
        preview(db, data, source_id, set_id)


def test_unknown_enrollment_is_rejected(db, data):
    source_id, set_id = make_source(db, data)

    with pytest.raises(NotFoundError):
        preview(
            db,
            data,
            source_id,
            set_id,
            instance_id=999999,
        )


# --------------------------------------------------
# Phase and history protection
# --------------------------------------------------


def test_protected_phases_remain_excluded(db, data):
    source_id, set_id = make_source(db, data)

    training_id, _ = make_prescription(db, data, data["first"], week=3)

    make_prescription(db, data, data["first"], week=4, phase="deload")

    make_prescription(db, data, data["first"], week=5, phase="assessment")

    make_prescription(db, data, data["first"], week=6, phase=None)

    result = preview(db, data, source_id, set_id)

    assert [item["prescription_id"] for item in result["candidates"]] == [training_id]

    assert {item["reason"] for item in result["excluded"]} == {
        "deload_protected",
        "assessment_protected",
        "phase_unclassified",
    }


def test_recorded_workout_is_conservatively_excluded(db, data):
    source_id, set_id = make_source(db, data)

    future_id, _ = make_prescription(db, data, data["first"], week=3)

    # WorkoutRecord currently lacks program_instance_id.
    # History matching must remain conservative.
    db.add(
        WorkoutRecord(
            user_id=data["owner"],
            program_slug="bw",
            program_week=3,
            program_day=1,
        )
    )
    db.commit()

    result = preview(db, data, source_id, set_id)

    assert result["candidates"] == []
    assert result["excluded"][0] == {
        "prescription_id": future_id,
        "program_week": 3,
        "program_day": 1,
        "reason": "workout_history_exists",
    }


# --------------------------------------------------
# Read-only guarantee
# --------------------------------------------------


def test_preview_does_not_modify_prescriptions(db, data):
    source_id, set_id = make_source(db, data)

    future_id, future_set_id = make_prescription(
        db, data, data["first"], week=3, reps=18
    )

    result = preview(db, data, source_id, set_id)

    assert result["database_modified"] is False
    assert result["candidates"][0]["proposed_value"] == 19

    db.expire_all()

    stored = db.get(PrescriptionSet, future_set_id)

    assert stored.target_reps == 18
    assert stored.workout_prescription_id == future_id

    assert (
        db.scalar(
            select(AdaptationApproval).where(
                AdaptationApproval.prescription_set_id == future_set_id
            )
        )
        is None
    )
