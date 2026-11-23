"""Tests for approving adaptive prescription adjustments.

Run from app/backend:
    python -m pytest tests/test_approve_adaptation.py -v

Uses an isolated SQLite database.
Proposal generation is mocked to test approval safeguards.
"""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event, select
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
    User,
    WorkoutPrescription,
    WorkoutRecord,
)
from app.models.adaptation_approval import AdaptationApproval
from app.services import approve_adaptation as service
from app.services.approve_adaptation import ApprovedAdjustment
from app.services.prescription_adaptation import ENGINE_VERSION


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
        email="approval-owner@example.com",
        password_hash="test-hash",
    )
    other = User(
        email="approval-other@example.com",
        password_hash="test-hash",
    )
    exercise = Exercise(name="Approval Test Push-Up")

    db.add_all([owner, other, exercise])
    db.commit()

    return {
        "owner": owner,
        "other": other,
        "exercise": exercise,
    }


def create_prescription(
    db,
    user,
    exercise,
    *,
    status="planned",
    reps=15,
    weight=None,
    load_basis="bodyweight",
):
    prescription = WorkoutPrescription(
        user_id=user.id,
        program_slug="bw",
        program_week=3,
        program_day=1,
        status=status,
        engine_version="baseline-v1",
    )

    prescription.sets.append(
        PrescriptionSet(
            exercise_id=exercise.id,
            set_number=1,
            target_reps=reps,
            target_weight_kg=(Decimal(str(weight)) if weight is not None else None),
            load_basis=load_basis,
        )
    )

    db.add(prescription)
    db.commit()

    return prescription


def approval(
    set_id,
    *,
    adjustment_type="reps",
    previous=15,
    proposed=16,
):
    return ApprovedAdjustment(
        prescription_set_id=set_id,
        adjustment_type=adjustment_type,
        expected_previous_value=Decimal(str(previous)),
        expected_proposed_value=Decimal(str(proposed)),
    )


def mock_recommendations(
    monkeypatch,
    proposals,
):
    """Mock the analysis result, not the approval service."""

    def fake_analysis(
        db,
        user_id,
        prescription_id,
    ):
        return {
            "prescription_id": prescription_id,
            "user_id": user_id,
            "status": "proposed",
            "proposal_engine_version": ENGINE_VERSION,
            "sets": [
                {
                    "prescription_set_id": item["set_id"],
                    "decision": {
                        "action": item.get("action", "progress"),
                    },
                    "proposal": {
                        "adjustment_type": item.get("type", "reps"),
                        "previous_value": item["previous"],
                        "proposed_value": item["proposed"],
                        "requires_approval": item.get("requires_approval", True),
                    },
                }
                for item in proposals
            ],
        }

    monkeypatch.setattr(
        service,
        "analyze_prescription_adaptations",
        fake_analysis,
    )


def standard_proposal(set_id):
    return {
        "set_id": set_id,
        "previous": 15,
        "proposed": 16,
    }


def apply(db, user_id, prescription_id, approvals):
    return service.apply_approved_adaptations(
        db=db,
        user_id=user_id,
        prescription_id=prescription_id,
        approvals=approvals,
    )


# --------------------------------------------------
# Successful approvals
# --------------------------------------------------


def test_valid_approval_updates_reps(db, data, monkeypatch):
    prescription = create_prescription(db, data["owner"], data["exercise"])
    set_id = prescription.sets[0].id

    mock_recommendations(
        monkeypatch,
        [standard_proposal(set_id)],
    )

    result = apply(
        db,
        data["owner"].id,
        prescription.id,
        [approval(set_id)],
    )

    db.expire_all()
    stored = db.get(PrescriptionSet, set_id)

    assert stored.target_reps == 16
    assert result["status"] == "updated"
    assert result["updated_set_count"] == 1
    assert result["updated_sets"][0]["applied_value"] == 16


def test_weight_approval_updates_resistance(db, data, monkeypatch):
    prescription = create_prescription(
        db,
        data["owner"],
        data["exercise"],
        reps=10,
        weight="60",
        load_basis="external",
    )
    set_id = prescription.sets[0].id

    mock_recommendations(
        monkeypatch,
        [
            {
                "set_id": set_id,
                "type": "weight",
                "previous": 60,
                "proposed": 61.5,
            }
        ],
    )

    apply(
        db,
        data["owner"].id,
        prescription.id,
        [
            approval(
                set_id,
                adjustment_type="weight",
                previous="60",
                proposed="61.5",
            )
        ],
    )

    db.expire_all()

    assert db.get(PrescriptionSet, set_id).target_weight_kg == Decimal("61.50")


def test_multiple_sets_update_together(db, data, monkeypatch):
    prescription = create_prescription(db, data["owner"], data["exercise"])
    first_id = prescription.sets[0].id

    second = PrescriptionSet(
        workout_prescription_id=prescription.id,
        exercise_id=data["exercise"].id,
        set_number=2,
        target_reps=12,
        load_basis="bodyweight",
    )
    db.add(second)
    db.commit()

    mock_recommendations(
        monkeypatch,
        [
            standard_proposal(first_id),
            {
                "set_id": second.id,
                "previous": 12,
                "proposed": 13,
            },
        ],
    )

    result = apply(
        db,
        data["owner"].id,
        prescription.id,
        [
            approval(first_id),
            approval(
                second.id,
                previous=12,
                proposed=13,
            ),
        ],
    )

    db.expire_all()

    assert db.get(PrescriptionSet, first_id).target_reps == 16

    assert db.get(PrescriptionSet, second.id).target_reps == 13

    assert result["updated_set_count"] == 2


# --------------------------------------------------
# Authentication and ownership safeguards
# --------------------------------------------------


def test_other_user_cannot_approve(db, data, monkeypatch):
    prescription = create_prescription(db, data["owner"], data["exercise"])
    set_id = prescription.sets[0].id

    mock_recommendations(
        monkeypatch,
        [standard_proposal(set_id)],
    )

    with pytest.raises(NotFoundError):
        apply(
            db,
            data["other"].id,
            prescription.id,
            [approval(set_id)],
        )

    db.expire_all()
    assert db.get(PrescriptionSet, set_id).target_reps == 15


def test_unknown_prescription_rejected(db, data):
    with pytest.raises(NotFoundError):
        apply(
            db,
            data["owner"].id,
            999999,
            [approval(1)],
        )


@pytest.mark.parametrize(
    "status",
    ["completed", "skipped"],
)
def test_non_planned_prescription_rejected(db, data, status):
    prescription = create_prescription(
        db,
        data["owner"],
        data["exercise"],
        status=status,
    )

    with pytest.raises(ConflictError):
        apply(
            db,
            data["owner"].id,
            prescription.id,
            [approval(prescription.sets[0].id)],
        )


# --------------------------------------------------
# Request validation
# --------------------------------------------------


def test_empty_approval_list_rejected(db, data):
    prescription = create_prescription(db, data["owner"], data["exercise"])

    with pytest.raises(ValidationFailed):
        apply(
            db,
            data["owner"].id,
            prescription.id,
            [],
        )


def test_duplicate_set_approval_rejected(db, data):
    prescription = create_prescription(db, data["owner"], data["exercise"])
    set_id = prescription.sets[0].id

    with pytest.raises(ValidationFailed):
        apply(
            db,
            data["owner"].id,
            prescription.id,
            [
                approval(set_id),
                approval(set_id),
            ],
        )


def test_set_from_another_prescription_rejected(db, data):
    first = create_prescription(db, data["owner"], data["exercise"])
    second = create_prescription(db, data["other"], data["exercise"])

    with pytest.raises(ValidationFailed):
        apply(
            db,
            data["owner"].id,
            first.id,
            [approval(second.sets[0].id)],
        )


# --------------------------------------------------
# Stale and invalid recommendations
# --------------------------------------------------


def test_stale_previous_value_rejected(db, data, monkeypatch):
    prescription = create_prescription(db, data["owner"], data["exercise"])
    set_id = prescription.sets[0].id

    mock_recommendations(
        monkeypatch,
        [standard_proposal(set_id)],
    )

    with pytest.raises(ConflictError):
        apply(
            db,
            data["owner"].id,
            prescription.id,
            [
                approval(
                    set_id,
                    previous=14,
                    proposed=16,
                )
            ],
        )

    db.expire_all()
    assert db.get(PrescriptionSet, set_id).target_reps == 15


def test_altered_proposed_value_rejected(db, data, monkeypatch):
    prescription = create_prescription(db, data["owner"], data["exercise"])
    set_id = prescription.sets[0].id

    mock_recommendations(
        monkeypatch,
        [standard_proposal(set_id)],
    )

    with pytest.raises(ConflictError):
        apply(
            db,
            data["owner"].id,
            prescription.id,
            [
                approval(
                    set_id,
                    previous=15,
                    proposed=25,
                )
            ],
        )


def test_non_progress_decision_rejected(db, data, monkeypatch):
    prescription = create_prescription(db, data["owner"], data["exercise"])
    set_id = prescription.sets[0].id

    mock_recommendations(
        monkeypatch,
        [
            {
                **standard_proposal(set_id),
                "action": "maintain",
            }
        ],
    )

    with pytest.raises(ConflictError):
        apply(
            db,
            data["owner"].id,
            prescription.id,
            [approval(set_id)],
        )


def test_non_approvable_proposal_rejected(db, data, monkeypatch):
    prescription = create_prescription(db, data["owner"], data["exercise"])
    set_id = prescription.sets[0].id

    mock_recommendations(
        monkeypatch,
        [
            {
                **standard_proposal(set_id),
                "requires_approval": False,
            }
        ],
    )

    with pytest.raises(ConflictError):
        apply(
            db,
            data["owner"].id,
            prescription.id,
            [approval(set_id)],
        )


def test_assistance_adjustment_rejected(db, data, monkeypatch):
    prescription = create_prescription(db, data["owner"], data["exercise"])
    set_id = prescription.sets[0].id

    mock_recommendations(
        monkeypatch,
        [
            {
                "set_id": set_id,
                "type": "assistance",
                "previous": 20,
                "proposed": 19,
            }
        ],
    )

    with pytest.raises(ValidationFailed):
        apply(
            db,
            data["owner"].id,
            prescription.id,
            [
                approval(
                    set_id,
                    adjustment_type="assistance",
                    previous=20,
                    proposed=19,
                )
            ],
        )


def test_repeated_approval_rejected(db, data, monkeypatch):
    prescription = create_prescription(db, data["owner"], data["exercise"])
    set_id = prescription.sets[0].id

    mock_recommendations(
        monkeypatch,
        [standard_proposal(set_id)],
    )

    request = [approval(set_id)]

    apply(
        db,
        data["owner"].id,
        prescription.id,
        request,
    )

    # A second request still expects the original
    # value of 15, but the database now stores 16.
    with pytest.raises(ConflictError):
        apply(
            db,
            data["owner"].id,
            prescription.id,
            request,
        )

    db.expire_all()
    assert db.get(PrescriptionSet, set_id).target_reps == 16


# --------------------------------------------------
# Historical data protection
# --------------------------------------------------


def test_workout_history_prevents_approval(db, data, monkeypatch):
    prescription = create_prescription(db, data["owner"], data["exercise"])
    set_id = prescription.sets[0].id

    # Same user, program, week and day.
    record = WorkoutRecord(
        user_id=data["owner"].id,
        program_slug="bw",
        program_week=3,
        program_day=1,
    )
    db.add(record)
    db.commit()

    mock_recommendations(
        monkeypatch,
        [standard_proposal(set_id)],
    )

    with pytest.raises(ConflictError):
        apply(
            db,
            data["owner"].id,
            prescription.id,
            [approval(set_id)],
        )

    db.expire_all()
    assert db.get(PrescriptionSet, set_id).target_reps == 15


def test_linked_performance_entry_prevents_approval(db, data, monkeypatch):
    prescription = create_prescription(db, data["owner"], data["exercise"])
    set_id = prescription.sets[0].id

    # Different workout date, but a performance
    # entry explicitly references this prescription set.
    record = WorkoutRecord(
        user_id=data["owner"].id,
        program_slug="other",
        program_week=1,
        program_day=1,
    )

    record.entries.append(
        PerformanceEntry(
            exercise_id=data["exercise"].id,
            prescription_set_id=set_id,
            set_number=1,
            reps=15,
            status="completed",
            observation_type="training",
            load_basis="bodyweight",
        )
    )

    db.add(record)
    db.commit()

    mock_recommendations(
        monkeypatch,
        [standard_proposal(set_id)],
    )

    with pytest.raises(ConflictError):
        apply(
            db,
            data["owner"].id,
            prescription.id,
            [approval(set_id)],
        )


def test_unrelated_workout_does_not_block_approval(db, data, monkeypatch):
    prescription = create_prescription(db, data["owner"], data["exercise"])
    set_id = prescription.sets[0].id

    db.add(
        WorkoutRecord(
            user_id=data["owner"].id,
            program_slug="other",
            program_week=1,
            program_day=1,
        )
    )
    db.commit()

    mock_recommendations(
        monkeypatch,
        [standard_proposal(set_id)],
    )

    result = apply(
        db,
        data["owner"].id,
        prescription.id,
        [approval(set_id)],
    )

    assert result["updated_set_count"] == 1


# --------------------------------------------------
# Atomicity and data integrity
# --------------------------------------------------


def test_invalid_second_adjustment_changes_nothing(db, data, monkeypatch):
    prescription = create_prescription(db, data["owner"], data["exercise"])
    first_id = prescription.sets[0].id

    second = PrescriptionSet(
        workout_prescription_id=prescription.id,
        exercise_id=data["exercise"].id,
        set_number=2,
        target_reps=12,
        load_basis="bodyweight",
    )
    db.add(second)
    db.commit()
    second_id = second.id

    mock_recommendations(
        monkeypatch,
        [
            standard_proposal(first_id),
            {
                "set_id": second_id,
                "previous": 12,
                "proposed": 13,
            },
        ],
    )

    with pytest.raises(ConflictError):
        apply(
            db,
            data["owner"].id,
            prescription.id,
            [
                approval(first_id),
                approval(
                    second_id,
                    previous=12,
                    proposed=99,
                ),
            ],
        )

    db.expire_all()

    assert db.get(PrescriptionSet, first_id).target_reps == 15

    assert db.get(PrescriptionSet, second_id).target_reps == 12


def test_approval_preserves_workout_metadata(db, data, monkeypatch):
    prescription = create_prescription(db, data["owner"], data["exercise"])
    set_id = prescription.sets[0].id

    mock_recommendations(
        monkeypatch,
        [standard_proposal(set_id)],
    )

    apply(
        db,
        data["owner"].id,
        prescription.id,
        [approval(set_id)],
    )

    db.expire_all()
    stored = db.get(
        WorkoutPrescription,
        prescription.id,
    )

    assert stored.user_id == data["owner"].id
    assert stored.program_slug == "bw"
    assert stored.program_week == 3
    assert stored.program_day == 1
    assert stored.status == "planned"
    assert stored.engine_version == "baseline-v1"


# --------------------------------------------------
# Approval audit persistence
# --------------------------------------------------


def test_approval_creates_audit_record(db, data, monkeypatch):
    """Successful approval records the original and new targets."""

    prescription = create_prescription(db, data["owner"], data["exercise"])
    prescription_id = prescription.id
    set_id = prescription.sets[0].id
    user_id = data["owner"].id

    mock_recommendations(
        monkeypatch,
        [standard_proposal(set_id)],
    )

    apply(
        db,
        user_id,
        prescription_id,
        [approval(set_id)],
    )

    db.expire_all()

    records = db.scalars(
        select(AdaptationApproval).where(
            AdaptationApproval.prescription_set_id == set_id
        )
    ).all()

    assert len(records) == 1

    audit = records[0]

    assert audit.user_id == user_id
    assert audit.workout_prescription_id == prescription_id
    assert audit.prescription_set_id == set_id
    assert audit.adjustment_type == "reps"
    assert audit.previous_value == Decimal("15.00")
    assert audit.approved_value == Decimal("16.00")
    assert audit.proposal_engine_version == ENGINE_VERSION
    assert audit.approved_at is not None

    assert db.get(PrescriptionSet, set_id).target_reps == 16


def test_multiple_approvals_create_distinct_audit_records(db, data, monkeypatch):
    """Each approved adjustment produces its own audit entry."""

    prescription = create_prescription(db, data["owner"], data["exercise"])
    prescription_id = prescription.id
    first_id = prescription.sets[0].id

    second = PrescriptionSet(
        workout_prescription_id=prescription_id,
        exercise_id=data["exercise"].id,
        set_number=2,
        target_reps=12,
        load_basis="bodyweight",
    )
    db.add(second)
    db.commit()

    second_id = second.id

    mock_recommendations(
        monkeypatch,
        [
            standard_proposal(first_id),
            {
                "set_id": second_id,
                "previous": 12,
                "proposed": 13,
            },
        ],
    )

    apply(
        db,
        data["owner"].id,
        prescription_id,
        [
            approval(first_id),
            approval(
                second_id,
                previous=12,
                proposed=13,
            ),
        ],
    )

    db.expire_all()

    records = db.scalars(
        select(AdaptationApproval).where(
            AdaptationApproval.workout_prescription_id == prescription_id
        )
    ).all()

    assert len(records) == 2

    audits = {record.prescription_set_id: record for record in records}

    assert set(audits) == {first_id, second_id}

    assert audits[first_id].previous_value == Decimal("15.00")
    assert audits[first_id].approved_value == Decimal("16.00")

    assert audits[second_id].previous_value == Decimal("12.00")
    assert audits[second_id].approved_value == Decimal("13.00")

    assert db.get(PrescriptionSet, first_id).target_reps == 16

    assert db.get(PrescriptionSet, second_id).target_reps == 13


# --------------------------------------------------
# Transaction rollback
# --------------------------------------------------


def test_audit_insert_failure_rolls_back_all_changes(db, data, monkeypatch):
    """Audit persistence failure must undo prescription changes."""

    prescription = create_prescription(db, data["owner"], data["exercise"])
    prescription_id = prescription.id
    first_id = prescription.sets[0].id

    second = PrescriptionSet(
        workout_prescription_id=prescription_id,
        exercise_id=data["exercise"].id,
        set_number=2,
        target_reps=12,
        load_basis="bodyweight",
    )

    db.add(second)
    db.commit()

    second_id = second.id

    mock_recommendations(
        monkeypatch,
        [
            standard_proposal(first_id),
            {
                "set_id": second_id,
                "previous": 12,
                "proposed": 13,
            },
        ],
    )

    def reject_audit_insert(mapper, connection, target):
        raise RuntimeError("Simulated audit insert failure")

    event.listen(
        AdaptationApproval,
        "before_insert",
        reject_audit_insert,
    )

    try:
        with pytest.raises(
            RuntimeError,
            match="Simulated audit insert failure",
        ):
            apply(
                db,
                data["owner"].id,
                prescription_id,
                [
                    approval(first_id),
                    approval(
                        second_id,
                        previous=12,
                        proposed=13,
                    ),
                ],
            )
    finally:
        event.remove(
            AdaptationApproval,
            "before_insert",
            reject_audit_insert,
        )

    db.expire_all()

    # Neither target update may survive.
    assert db.get(PrescriptionSet, first_id).target_reps == 15

    assert db.get(PrescriptionSet, second_id).target_reps == 12

    # Neither approval record may survive.
    records = db.scalars(
        select(AdaptationApproval).where(
            AdaptationApproval.workout_prescription_id == prescription_id
        )
    ).all()

    assert records == []


def test_rejected_approval_creates_no_audit_record(db, data, monkeypatch):
    """A stale recommendation must not create approval history."""

    prescription = create_prescription(db, data["owner"], data["exercise"])
    prescription_id = prescription.id
    set_id = prescription.sets[0].id

    mock_recommendations(
        monkeypatch,
        [standard_proposal(set_id)],
    )

    with pytest.raises(ConflictError):
        apply(
            db,
            data["owner"].id,
            prescription_id,
            [
                approval(
                    set_id,
                    previous=14,
                    proposed=16,
                ),
            ],
        )

    db.expire_all()

    assert db.get(PrescriptionSet, set_id).target_reps == 15

    records = db.scalars(
        select(AdaptationApproval).where(
            AdaptationApproval.workout_prescription_id == prescription_id
        )
    ).all()

    assert records == []
