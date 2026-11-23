"""Tests for transactional program enrollment creation.

Run from app/backend:
    python -m pytest tests/test_program_enrollment.py -v

Uses an isolated in-memory SQLite database.
Does not connect to PostgreSQL or Supabase.
"""

from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.models

from app.core.errors import NotFoundError, ValidationFailed
from app.db.base import Base
from app.models import (
    Exercise,
    ProgramBaseline,
    ProgramPhase,
    User,
    WorkoutPrescription,
    PrescriptionSet,
)
from app.models.program_instance import ProgramInstance
from app.services.program_enrollment import (
    EnrollmentSet,
    EnrollmentWorkout,
    create_program_enrollment,
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
    exercise = Exercise(name="Enrollment Push-Up")

    db.add_all([owner, other, exercise])
    db.flush()

    baseline = ProgramBaseline(
        user_id=owner.id,
        program_slug="bw",
        attempt_id=str(uuid4()),
        results=[],
    )

    db.add(baseline)
    db.commit()

    return {
        "owner": owner.id,
        "other": other.id,
        "exercise": exercise.id,
        "baseline": baseline.id,
    }


def schedule(exercise_id):
    return (
        EnrollmentWorkout(
            program_week=1,
            program_day=1,
            phase_type="training",
            sets=(
                EnrollmentSet(
                    exercise_id=exercise_id,
                    set_number=1,
                    load_basis="bodyweight",
                    target_reps=10,
                ),
            ),
        ),
        EnrollmentWorkout(
            program_week=2,
            program_day=1,
            phase_type="deload",
            sets=(
                EnrollmentSet(
                    exercise_id=exercise_id,
                    set_number=1,
                    load_basis="bodyweight",
                    target_reps=7,
                ),
            ),
        ),
        EnrollmentWorkout(
            program_week=3,
            program_day=1,
            phase_type="assessment",
            sets=(
                EnrollmentSet(
                    exercise_id=exercise_id,
                    set_number=1,
                    load_basis="bodyweight",
                    target_reps=12,
                ),
            ),
        ),
    )


def enroll(db, data, **changes):
    args = {
        "user_id": data["owner"],
        "program_slug": "bw",
        "source_baseline_id": data["baseline"],
        "workouts": schedule(data["exercise"]),
    }
    args.update(changes)

    return create_program_enrollment(db, **args)


def count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def test_creates_instance_and_all_prescriptions(db, data):
    instance = enroll(db, data)

    assert instance.id is not None
    assert instance.user_id == data["owner"]
    assert instance.program_slug == "bw"
    assert instance.source_baseline_id == data["baseline"]
    assert instance.status == "active"

    prescriptions = db.scalars(
        select(WorkoutPrescription)
        .where(WorkoutPrescription.program_instance_id == instance.id)
        .order_by(WorkoutPrescription.program_week)
    ).all()

    assert len(prescriptions) == 3
    assert [p.program_week for p in prescriptions] == [1, 2, 3]

    for prescription in prescriptions:
        assert prescription.user_id == data["owner"]
        assert prescription.program_slug == "bw"
        assert prescription.source_baseline_id == data["baseline"]
        assert prescription.status == "planned"
        assert prescription.engine_version == "adaptive-v1"
        assert len(prescription.sets) == 1

    assert [p.sets[0].target_reps for p in prescriptions] == [10, 7, 12]


def test_persists_explicit_program_phases(db, data):
    instance = enroll(db, data)

    rows = db.execute(
        select(
            WorkoutPrescription.program_week,
            ProgramPhase.phase_type,
        )
        .join(
            ProgramPhase,
            ProgramPhase.workout_prescription_id == WorkoutPrescription.id,
        )
        .where(WorkoutPrescription.program_instance_id == instance.id)
        .order_by(WorkoutPrescription.program_week)
    ).all()

    assert rows == [
        (1, "training"),
        (2, "deload"),
        (3, "assessment"),
    ]


def test_repeat_enrollment_creates_distinct_instances(db, data):
    first = enroll(db, data)
    second = enroll(db, data)

    assert first.id != second.id
    assert first.source_baseline_id == second.source_baseline_id

    first_ids = set(
        db.scalars(
            select(WorkoutPrescription.id).where(
                WorkoutPrescription.program_instance_id == first.id
            )
        )
    )

    second_ids = set(
        db.scalars(
            select(WorkoutPrescription.id).where(
                WorkoutPrescription.program_instance_id == second.id
            )
        )
    )

    assert len(first_ids) == 3
    assert len(second_ids) == 3
    assert first_ids.isdisjoint(second_ids)


def test_rejects_baseline_from_another_user(db, data):
    with pytest.raises(ValidationFailed):
        enroll(
            db,
            data,
            user_id=data["other"],
        )

    assert count(db, ProgramInstance) == 0


def test_rejects_baseline_from_another_program(db, data):
    with pytest.raises(ValidationFailed):
        enroll(
            db,
            data,
            program_slug="ldw",
        )

    assert count(db, ProgramInstance) == 0


def test_rejects_unknown_baseline(db, data):
    with pytest.raises(NotFoundError):
        enroll(
            db,
            data,
            source_baseline_id=999999,
        )

    assert count(db, ProgramInstance) == 0


def test_rejects_unknown_exercise(db, data):
    invalid = (
        EnrollmentWorkout(
            program_week=1,
            program_day=1,
            phase_type="training",
            sets=(
                EnrollmentSet(
                    exercise_id=999999,
                    set_number=1,
                    load_basis="bodyweight",
                    target_reps=10,
                ),
            ),
        ),
    )

    with pytest.raises(ValidationFailed):
        enroll(db, data, workouts=invalid)

    assert count(db, ProgramInstance) == 0


def test_rejects_duplicate_program_day(db, data):
    first = schedule(data["exercise"])[0]

    with pytest.raises(ValidationFailed):
        enroll(
            db,
            data,
            workouts=(first, first),
        )

    assert count(db, ProgramInstance) == 0


def test_rejects_unclassified_workout(db, data):
    invalid = (
        EnrollmentWorkout(
            program_week=1,
            program_day=1,
            phase_type="unknown",
            sets=(
                EnrollmentSet(
                    exercise_id=data["exercise"],
                    set_number=1,
                    load_basis="bodyweight",
                    target_reps=10,
                ),
            ),
        ),
    )

    with pytest.raises(ValidationFailed):
        enroll(db, data, workouts=invalid)

    assert count(db, ProgramInstance) == 0


def test_rejects_unsupported_assistance(db, data):
    invalid = (
        EnrollmentWorkout(
            program_week=1,
            program_day=1,
            phase_type="training",
            sets=(
                EnrollmentSet(
                    exercise_id=data["exercise"],
                    set_number=1,
                    load_basis="assisted",
                    target_reps=10,
                ),
            ),
        ),
    )

    with pytest.raises(ValidationFailed):
        enroll(db, data, workouts=invalid)

    assert count(db, ProgramInstance) == 0


def test_database_failure_rolls_back_entire_enrollment(db, data):
    """Simulate failure while inserting a program phase."""

    def fail_phase_insert(mapper, connection, target):
        raise RuntimeError("Simulated phase insert failure")

    event.listen(
        ProgramPhase,
        "before_insert",
        fail_phase_insert,
    )

    try:
        with pytest.raises(
            RuntimeError,
            match="Simulated phase insert failure",
        ):
            enroll(db, data)
    finally:
        event.remove(
            ProgramPhase,
            "before_insert",
            fail_phase_insert,
        )

    db.expire_all()

    assert count(db, ProgramInstance) == 0
    assert count(db, WorkoutPrescription) == 0
    assert count(db, PrescriptionSet) == 0
    assert count(db, ProgramPhase) == 0
