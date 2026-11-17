
"""End-to-end service tests for adaptive training.

Uses real workout records, performance analysis,
adaptive decisions, progression rules, and approvals.

Run:
    python -m pytest tests/test_adaptation_workflow.py -v

SQLite is used for isolation. PostgreSQL concurrency
behavior is not tested here.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.models
from app.core.errors import ConflictError
from app.db.base import Base
from app.models import (
    Exercise,
    PerformanceEntry,
    PrescriptionSet,
    User,
    WorkoutPrescription,
    WorkoutRecord,
)
from app.services.approve_adaptation import (
    ApprovedAdjustment,
    apply_approved_adaptations,
)
from app.services.prescription_adaptation import (
    analyze_prescription_adaptations,
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
        email="workflow-owner@example.com",
        password_hash="test-hash",
    )

    other = User(
        email="workflow-other@example.com",
        password_hash="test-hash",
    )

    exercise = Exercise(
        name="Workflow Test Push-Up"
    )

    db.add_all([owner, other, exercise])
    db.commit()

    return {
        "owner_id": owner.id,
        "other_id": other.id,
        "exercise_id": exercise.id,
    }


def create_prescription(
    db,
    user_id,
    exercise_id,
    *,
    week,
    day=1,
    reps=15,
    status="planned",
):
    prescription = WorkoutPrescription(
        user_id=user_id,
        program_slug="bw",
        program_week=week,
        program_day=day,
        status=status,
        engine_version="baseline-v1",
    )

    prescription.sets.append(
        PrescriptionSet(
            exercise_id=exercise_id,
            set_number=1,
            target_reps=reps,
            load_basis="bodyweight",
        )
    )

    db.add(prescription)
    db.commit()

    return prescription.id, prescription.sets[0].id


def add_history(
    db,
    user_id,
    exercise_id,
    values,
    *,
    prescribed=15,
    link_targets=True,
    load_basis="bodyweight",
):
    """Insert real completed workout observations.

    History is from week 1, so it does not block
    adaptations to a planned week 3 workout.
    """

    historical_prescription_id, historical_set_id = (
        create_prescription(
            db,
            user_id,
            exercise_id,
            week=1,
            reps=prescribed,
            status="completed",
        )
    )

    entry_ids = []

    for index, value in enumerate(values):
        record = WorkoutRecord(
            user_id=user_id,
            program_slug="bw",
            program_week=1,
            program_day=1,
            performed_at=(
                datetime(
                    2026, 10, 1, 12, 0,
                    tzinfo=timezone.utc,
                )
                + timedelta(days=index)
            ),
        )

        entry = PerformanceEntry(
            exercise_id=exercise_id,
            set_number=1,
            reps=value,
            status="completed",
            observation_type="training",
            load_basis=load_basis,
            prescription_set_id=(
                historical_set_id
                if link_targets
                else None
            ),
        )

        record.entries.append(entry)
        db.add(record)
        db.flush()

        entry_ids.append(entry.id)

    db.commit()

    return {
        "prescription_id": historical_prescription_id,
        "set_id": historical_set_id,
        "entry_ids": entry_ids,
    }


def get_recommendation(
    db,
    user_id,
    prescription_id,
):
    return analyze_prescription_adaptations(
        db=db,
        user_id=user_id,
        prescription_id=prescription_id,
    )


def approve_recommendation(
    db,
    user_id,
    prescription_id,
    item,
):
    proposal = item["proposal"]

    return apply_approved_adaptations(
        db=db,
        user_id=user_id,
        prescription_id=prescription_id,
        approvals=[
            ApprovedAdjustment(
                prescription_set_id=item[
                    "prescription_set_id"
                ],
                adjustment_type=proposal[
                    "adjustment_type"
                ],
                expected_previous_value=Decimal(
                    str(proposal["previous_value"])
                ),
                expected_proposed_value=Decimal(
                    str(proposal["proposed_value"])
                ),
            )
        ],
    )


# --------------------------------------------------
# Complete progression workflow
# --------------------------------------------------

def test_real_history_generates_progression(
    db, data
):
    add_history(
        db,
        data["owner_id"],
        data["exercise_id"],
        [15, 16, 17, 18, 19],
    )

    prescription_id, set_id = create_prescription(
        db,
        data["owner_id"],
        data["exercise_id"],
        week=3,
        reps=15,
    )

    result = get_recommendation(
        db,
        data["owner_id"],
        prescription_id,
    )

    assert len(result["sets"]) == 1

    item = result["sets"][0]

    assert item["prescription_set_id"] == set_id
    assert item["decision"]["confidence"] == "robust"
    assert item["decision"]["observation_count"] == 5
    assert item["decision"]["change_pct"] > 5
    assert item["decision"]["action"] == "progress"

    assert item["proposal"]["adjustment_type"] == "reps"
    assert item["proposal"]["previous_value"] == 15
    assert item["proposal"]["proposed_value"] == 16
    assert item["proposal"]["requires_approval"] is True


def test_approval_updates_future_prescription_only(
    db, data
):
    history = add_history(
        db,
        data["owner_id"],
        data["exercise_id"],
        [15, 16, 17, 18, 19],
    )

    prescription_id, set_id = create_prescription(
        db,
        data["owner_id"],
        data["exercise_id"],
        week=3,
    )

    recommendation = get_recommendation(
        db,
        data["owner_id"],
        prescription_id,
    )

    result = approve_recommendation(
        db,
        data["owner_id"],
        prescription_id,
        recommendation["sets"][0],
    )

    assert result["status"] == "updated"
    assert result["updated_set_count"] == 1

    db.expire_all()

    # Upcoming prescription changes.
    future_set = db.get(PrescriptionSet, set_id)
    assert future_set.target_reps == 16

    # Historical prescription remains unchanged.
    historical_set = db.get(
        PrescriptionSet,
        history["set_id"],
    )
    assert historical_set.target_reps == 15

    # Completed workout values remain unchanged.
    entries = db.scalars(
        select(PerformanceEntry)
        .where(
            PerformanceEntry.id.in_(
                history["entry_ids"]
            )
        )
        .order_by(PerformanceEntry.id)
    ).all()

    assert [entry.reps for entry in entries] == [
        15, 16, 17, 18, 19
    ]

    assert all(
        entry.prescription_set_id == history["set_id"]
        for entry in entries
    )


# --------------------------------------------------
# Evidence requirements
# --------------------------------------------------

def test_preliminary_history_maintains(
    db, data
):
    add_history(
        db,
        data["owner_id"],
        data["exercise_id"],
        [15, 17, 19],
    )

    prescription_id, _ = create_prescription(
        db,
        data["owner_id"],
        data["exercise_id"],
        week=3,
    )

    result = get_recommendation(
        db,
        data["owner_id"],
        prescription_id,
    )

    item = result["sets"][0]

    assert item["decision"]["confidence"] == (
        "preliminary"
    )
    assert item["decision"]["action"] == "maintain"
    assert item["proposal"]["adjustment_type"] == "none"


def test_insufficient_history_does_not_progress(
    db, data
):
    add_history(
        db,
        data["owner_id"],
        data["exercise_id"],
        [15, 17],
    )

    prescription_id, _ = create_prescription(
        db,
        data["owner_id"],
        data["exercise_id"],
        week=3,
    )

    result = get_recommendation(
        db,
        data["owner_id"],
        prescription_id,
    )

    item = result["sets"][0]

    assert item["decision"]["action"] == (
        "insufficient_data"
    )

    assert item["proposal"]["adjustment_type"] == "none"


def test_positive_trend_with_missed_targets_maintains(
    db, data
):
    add_history(
        db,
        data["owner_id"],
        data["exercise_id"],
        [9, 10, 11, 12, 13],
        prescribed=15,
    )

    prescription_id, _ = create_prescription(
        db,
        data["owner_id"],
        data["exercise_id"],
        week=3,
    )

    result = get_recommendation(
        db,
        data["owner_id"],
        prescription_id,
    )

    item = result["sets"][0]

    assert item["decision"]["change_pct"] > 5
    assert item["decision"]["action"] == "maintain"
    assert item["proposal"]["adjustment_type"] == "none"


def test_missing_prescribed_targets_blocks_progression(
    db, data
):
    add_history(
        db,
        data["owner_id"],
        data["exercise_id"],
        [15, 16, 17, 18, 19],
        link_targets=False,
    )

    prescription_id, _ = create_prescription(
        db,
        data["owner_id"],
        data["exercise_id"],
        week=3,
    )

    result = get_recommendation(
        db,
        data["owner_id"],
        prescription_id,
    )

    item = result["sets"][0]

    assert item["decision"]["confidence"] == "robust"
    assert item["decision"]["action"] == "maintain"
    assert item["proposal"]["adjustment_type"] == "none"


def test_negative_trend_requests_review(
    db, data
):
    add_history(
        db,
        data["owner_id"],
        data["exercise_id"],
        [19, 18, 17, 16, 15],
    )

    prescription_id, _ = create_prescription(
        db,
        data["owner_id"],
        data["exercise_id"],
        week=3,
    )

    result = get_recommendation(
        db,
        data["owner_id"],
        prescription_id,
    )

    item = result["sets"][0]

    assert item["decision"]["action"] == (
        "review_regression"
    )
    assert item["proposal"]["adjustment_type"] == "none"


# --------------------------------------------------
# Ownership and matching
# --------------------------------------------------

def test_other_users_history_does_not_contribute(
    db, data
):
    add_history(
        db,
        data["other_id"],
        data["exercise_id"],
        [15, 16, 17, 18, 19],
    )

    prescription_id, _ = create_prescription(
        db,
        data["owner_id"],
        data["exercise_id"],
        week=3,
    )

    result = get_recommendation(
        db,
        data["owner_id"],
        prescription_id,
    )

    item = result["sets"][0]

    assert item["decision"]["action"] == (
        "insufficient_data"
    )
    assert item["proposal"]["adjustment_type"] == "none"


def test_incompatible_loading_excluded(
    db, data
):
    add_history(
        db,
        data["owner_id"],
        data["exercise_id"],
        [15, 16, 17, 18, 19],
        load_basis="external",
    )

    prescription_id, _ = create_prescription(
        db,
        data["owner_id"],
        data["exercise_id"],
        week=3,
    )

    result = get_recommendation(
        db,
        data["owner_id"],
        prescription_id,
    )

    item = result["sets"][0]

    assert item["decision"]["action"] == (
        "insufficient_data"
    )
    assert item["proposal"]["adjustment_type"] == "none"


# --------------------------------------------------
# Approval safeguards
# --------------------------------------------------

def test_stale_approval_is_rejected(
    db, data
):
    add_history(
        db,
        data["owner_id"],
        data["exercise_id"],
        [15, 16, 17, 18, 19],
    )

    prescription_id, set_id = create_prescription(
        db,
        data["owner_id"],
        data["exercise_id"],
        week=3,
    )

    recommendation = get_recommendation(
        db,
        data["owner_id"],
        prescription_id,
    )

    item = recommendation["sets"][0]

    # Simulate another change to the upcoming target.
    prescribed_set = db.get(PrescriptionSet, set_id)
    prescribed_set.target_reps = 17
    db.commit()

    # Original 15 -> 16 proposal is now stale.
    with pytest.raises(ConflictError):
        approve_recommendation(
            db,
            data["owner_id"],
            prescription_id,
            item,
        )

    db.expire_all()
    assert db.get(PrescriptionSet, set_id).target_reps == 17


def test_recorded_upcoming_workout_blocks_approval(
    db, data
):
    add_history(
        db,
        data["owner_id"],
        data["exercise_id"],
        [15, 16, 17, 18, 19],
    )

    prescription_id, set_id = create_prescription(
        db,
        data["owner_id"],
        data["exercise_id"],
        week=3,
    )

    recommendation = get_recommendation(
        db,
        data["owner_id"],
        prescription_id,
    )

    # Workout has been started/logged since the
    # recommendation was generated.
    record = WorkoutRecord(
        user_id=data["owner_id"],
        program_slug="bw",
        program_week=3,
        program_day=1,
    )
    db.add(record)
    db.commit()

    with pytest.raises(ConflictError):
        approve_recommendation(
            db,
            data["owner_id"],
            prescription_id,
            recommendation["sets"][0],
        )

    db.expire_all()
    assert db.get(PrescriptionSet, set_id).target_reps == 15
