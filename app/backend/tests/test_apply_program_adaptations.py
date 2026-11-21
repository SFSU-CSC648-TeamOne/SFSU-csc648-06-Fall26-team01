
"""PostgreSQL integration tests for atomic bulk adaptations.

Run from app/backend with ASCENDA_TEST_DATABASE_URL set:

    python -m pytest tests/test_apply_program_adaptations.py -v

Uses only local 127.0.0.1:5433/ascenda_test.
All fixture changes are rolled back by an outer transaction.
"""

import os
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import (
    create_engine,
    event,
    func,
    inspect,
    select,
)
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import app.models

from app.core.errors import (
    ConflictError,
    NotFoundError,
    ValidationFailed,
)
from app.models.adaptation_approval import AdaptationApproval
from app.models.catalog import Exercise
from app.models.prescription import (
    PrescriptionSet,
    WorkoutPrescription,
)
from app.models.program_baseline import ProgramBaseline
from app.models.program_instance import ProgramInstance
from app.models.program_phase import ProgramPhase
from app.models.program_adaptation_approval import (
    ProgramAdaptationApproval,
    ProgramAdaptationApprovalItem,
)
from app.models.tracking import WorkoutRecord
from app.models.users import User
from app.services.apply_program_adaptations import (
    SelectedProgramAdjustment,
    apply_program_adaptations,
)


REQUIRED_TABLES = {
    "users",
    "exercises",
    "program_baselines",
    "program_instances",
    "workout_prescriptions",
    "prescription_sets",
    "program_phases",
    "adaptation_approvals",
    "program_adaptation_approvals",
    "program_adaptation_approval_items",
    "workout_records",
}


@pytest.fixture
def db():
    raw_url = os.environ.get("ASCENDA_TEST_DATABASE_URL")

    if not raw_url:
        pytest.fail("ASCENDA_TEST_DATABASE_URL is required.")

    url = make_url(raw_url)

    if (
        url.get_backend_name() != "postgresql"
        or url.get_driver_name() != "psycopg"
        or url.host != "127.0.0.1"
        or url.port != 5433
        or url.database != "ascenda_test"
        or url.username != "devuser"
    ):
        pytest.fail("Refusing to access a non-test database.")

    engine = create_engine(url)

    try:
        with engine.connect() as connection:
            actual = connection.exec_driver_sql(
                "SELECT current_database()"
            ).scalar_one()

            if actual != "ascenda_test":
                pytest.fail("Unexpected database.")

            available = set(
                inspect(connection).get_table_names()
            )
            missing = REQUIRED_TABLES - available

            if missing:
                pytest.fail(
                    f"Missing tables: {sorted(missing)}"
                )

            # Database inspection started an implicit
            # SQLAlchemy transaction.
            connection.rollback()

            outer = connection.begin()

            try:
                with Session(
                    bind=connection,
                    join_transaction_mode="create_savepoint",
                ) as session:
                    yield session
            finally:
                if outer.is_active:
                    outer.rollback()
    finally:
        engine.dispose()


def add_workout(
    db,
    *,
    user_id,
    instance_id,
    baseline_id,
    exercise_id,
    week,
    reps,
    phase="training",
    status="planned",
):
    prescription = WorkoutPrescription(
        user_id=user_id,
        program_instance_id=instance_id,
        program_slug="bw",
        program_week=week,
        program_day=1,
        source_baseline_id=baseline_id,
        status=status,
        engine_version="test-v1",
    )

    prescription.sets.append(
        PrescriptionSet(
            exercise_id=exercise_id,
            set_number=1,
            load_basis="bodyweight",
            target_reps=reps,
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

    db.flush()

    return prescription.id, prescription.sets[0].id


@pytest.fixture
def data(db):
    user = User(
        email=f"bulk-{uuid4().hex}@example.com",
        password_hash="test-hash",
    )

    exercise = Exercise(
        name=f"Bulk Test Push-Up {uuid4().hex[:8]}"
    )

    db.add_all([user, exercise])
    db.flush()

    baseline = ProgramBaseline(
        user_id=user.id,
        program_slug="bw",
        attempt_id=str(uuid4()),
        results=[],
    )

    db.add(baseline)
    db.flush()

    first = ProgramInstance(
        user_id=user.id,
        program_slug="bw",
        source_baseline_id=baseline.id,
        status="active",
    )

    second = ProgramInstance(
        user_id=user.id,
        program_slug="bw",
        source_baseline_id=baseline.id,
        status="active",
    )

    db.add_all([first, second])
    db.flush()

    source_id, source_set_id = add_workout(
        db,
        user_id=user.id,
        instance_id=first.id,
        baseline_id=baseline.id,
        exercise_id=exercise.id,
        week=2,
        reps=16,
    )

    source_approval = AdaptationApproval(
        user_id=user.id,
        workout_prescription_id=source_id,
        prescription_set_id=source_set_id,
        adjustment_type="reps",
        previous_value=Decimal("15"),
        approved_value=Decimal("16"),
        proposal_engine_version="test-v1",
    )

    db.add(source_approval)
    db.flush()

    first_future, first_set = add_workout(
        db,
        user_id=user.id,
        instance_id=first.id,
        baseline_id=baseline.id,
        exercise_id=exercise.id,
        week=3,
        reps=18,
    )

    second_future, second_set = add_workout(
        db,
        user_id=user.id,
        instance_id=first.id,
        baseline_id=baseline.id,
        exercise_id=exercise.id,
        week=4,
        reps=20,
    )

    protected_future, protected_set = add_workout(
        db,
        user_id=user.id,
        instance_id=first.id,
        baseline_id=baseline.id,
        exercise_id=exercise.id,
        week=5,
        reps=12,
        phase="deload",
    )

    foreign_future, foreign_set = add_workout(
        db,
        user_id=user.id,
        instance_id=second.id,
        baseline_id=baseline.id,
        exercise_id=exercise.id,
        week=3,
        reps=18,
    )

    db.commit()

    return {
        "user_id": user.id,
        "instance_id": first.id,
        "other_instance_id": second.id,
        "source_approval_id": source_approval.id,
        "source_id": source_id,
        "source_set_id": source_set_id,
        "first_future": first_future,
        "first_set": first_set,
        "second_future": second_future,
        "second_set": second_set,
        "protected_future": protected_future,
        "protected_set": protected_set,
        "foreign_future": foreign_future,
        "foreign_set": foreign_set,
    }


def selected(set_id, before, after):
    return SelectedProgramAdjustment(
        prescription_set_id=set_id,
        expected_previous_value=Decimal(str(before)),
        expected_proposed_value=Decimal(str(after)),
    )


def selections(data):
    return [
        selected(data["first_set"], 18, 19),
        selected(data["second_set"], 20, 21),
    ]


def apply(db, data, *, chosen=None, key=None, **overrides):
    arguments = {
        "user_id": data["user_id"],
        "program_instance_id": data["instance_id"],
        "source_approval_id": data["source_approval_id"],
        "request_key": key or uuid4().hex,
        "selections": (
            selections(data) if chosen is None else chosen
        ),
    }

    arguments.update(overrides)

    return apply_program_adaptations(db, **arguments)


def target(db, set_id):
    db.expire_all()
    return db.get(PrescriptionSet, set_id).target_reps



def audit_count(db, model, user_id):
    """Count only bulk approval records for this test user."""

    if model is ProgramAdaptationApproval:
        statement = (
            select(func.count())
            .select_from(ProgramAdaptationApproval)
            .where(
                ProgramAdaptationApproval.user_id
                == user_id
            )
        )

    elif model is ProgramAdaptationApprovalItem:
        statement = (
            select(func.count())
            .select_from(ProgramAdaptationApprovalItem)
            .join(
                ProgramAdaptationApproval,
                ProgramAdaptationApprovalItem
                .program_adaptation_approval_id
                == ProgramAdaptationApproval.id,
            )
            .where(
                ProgramAdaptationApproval.user_id
                == user_id
            )
        )

    else:
        raise ValueError(
            f"Unsupported audit model: {model}"
        )

    return db.scalar(statement)



# --------------------------------------------------
# Successful atomic application
# --------------------------------------------------

def test_selected_sets_are_updated(db, data):
    result = apply(db, data)

    assert result["status"] == "updated"
    assert result["program_instance_id"] == data["instance_id"]
    assert result["updated_set_count"] == 2

    assert target(db, data["first_set"]) == 19
    assert target(db, data["second_set"]) == 21


def test_unselected_sets_are_unchanged(db, data):
    apply(
        db,
        data,
        chosen=[
            selected(data["first_set"], 18, 19),
        ],
    )

    assert target(db, data["first_set"]) == 19
    assert target(db, data["second_set"]) == 20
    assert target(db, data["protected_set"]) == 12
    assert target(db, data["foreign_set"]) == 18


def test_complete_audit_records_created(db, data):
    result = apply(db, data)

    approval = db.get(
        ProgramAdaptationApproval,
        result["program_adaptation_approval_id"],
    )

    assert approval is not None
    assert approval.user_id == data["user_id"]
    assert approval.program_instance_id == data["instance_id"]
    assert approval.source_approval_id == (
        data["source_approval_id"]
    )

    items = db.scalars(
        select(ProgramAdaptationApprovalItem)
        .where(
            ProgramAdaptationApprovalItem
            .program_adaptation_approval_id == approval.id
        )
    ).all()

    assert len(items) == 2

    by_set = {
        item.prescription_set_id: item
        for item in items
    }

    assert by_set[data["first_set"]].previous_value == 18
    assert by_set[data["first_set"]].approved_value == 19
    assert by_set[data["second_set"]].previous_value == 20
    assert by_set[data["second_set"]].approved_value == 21


# --------------------------------------------------
# Idempotency
# --------------------------------------------------

def test_identical_retry_does_not_apply_twice(db, data):
    key = uuid4().hex

    first = apply(db, data, key=key)
    second = apply(db, data, key=key)

    assert first["status"] == "updated"
    assert second["status"] == "already_applied"

    assert (
        first["program_adaptation_approval_id"]
        == second["program_adaptation_approval_id"]
    )

    assert target(db, data["first_set"]) == 19
    assert target(db, data["second_set"]) == 21

    assert audit_count(
        db, ProgramAdaptationApproval, data["user_id"],
    ) == 1

    assert audit_count(
        db, ProgramAdaptationApprovalItem, data["user_id"],
    ) == 2


def test_reused_key_with_different_values_rejected(
    db, data
):
    key = uuid4().hex

    apply(db, data, key=key)

    with pytest.raises(ConflictError):
        apply(
            db,
            data,
            key=key,
            chosen=[
                selected(data["first_set"], 18, 20),
                selected(data["second_set"], 20, 21),
            ],
        )

    assert target(db, data["first_set"]) == 19


def test_reused_key_with_different_selection_rejected(
    db, data
):
    key = uuid4().hex

    apply(db, data, key=key)

    with pytest.raises(ConflictError):
        apply(
            db,
            data,
            key=key,
            chosen=[
                selected(data["first_set"], 18, 19),
            ],
        )


# --------------------------------------------------
# Enrollment isolation and authorization
# --------------------------------------------------

def test_other_enrollment_set_rejected(db, data):
    with pytest.raises(ConflictError):
        apply(
            db,
            data,
            chosen=[
                selected(data["foreign_set"], 18, 19),
            ],
        )

    assert target(db, data["foreign_set"]) == 18
    assert audit_count(
        db, ProgramAdaptationApproval, data["user_id"],
    ) == 0


def test_source_approval_must_belong_to_enrollment(
    db, data
):
    with pytest.raises(NotFoundError):
        apply(
            db,
            data,
            program_instance_id=data["other_instance_id"],
        )

    assert target(db, data["foreign_set"]) == 18


def test_nonexistent_enrollment_rejected(db, data):
    with pytest.raises(NotFoundError):
        apply(
            db,
            data,
            program_instance_id=999999999,
        )


@pytest.mark.parametrize(
    "status",
    ["completed", "abandoned"],
)
def test_inactive_enrollment_rejected(
    db, data, status
):
    instance = db.get(
        ProgramInstance,
        data["instance_id"],
    )
    instance.status = status
    db.commit()

    with pytest.raises(ConflictError):
        apply(db, data)

    assert target(db, data["first_set"]) == 18


# --------------------------------------------------
# Stale targets and protected workouts
# --------------------------------------------------

def test_stale_target_rejected(db, data):
    future_set = db.get(
        PrescriptionSet,
        data["first_set"],
    )

    future_set.target_reps = 22
    db.commit()

    with pytest.raises(ConflictError):
        apply(db, data)

    assert target(db, data["first_set"]) == 22
    assert target(db, data["second_set"]) == 20


def test_deload_selection_rejected(db, data):
    with pytest.raises(ConflictError):
        apply(
            db,
            data,
            chosen=[
                selected(data["protected_set"], 12, 13),
            ],
        )

    assert target(db, data["protected_set"]) == 12


def test_completed_future_workout_rejected(db, data):
    prescription = db.get(
        WorkoutPrescription,
        data["first_future"],
    )
    prescription.status = "completed"
    db.commit()

    with pytest.raises(ConflictError):
        apply(
            db,
            data,
            chosen=[
                selected(data["first_set"], 18, 19),
            ],
        )

    assert target(db, data["first_set"]) == 18


def test_recorded_workout_rejected(db, data):
    db.add(
        WorkoutRecord(
            user_id=data["user_id"],
            program_slug="bw",
            program_week=3,
            program_day=1,
        )
    )
    db.commit()

    with pytest.raises(ConflictError):
        apply(
            db,
            data,
            chosen=[
                selected(data["first_set"], 18, 19),
            ],
        )

    assert target(db, data["first_set"]) == 18


# --------------------------------------------------
# Input validation
# --------------------------------------------------

def test_duplicate_selection_rejected(db, data):
    with pytest.raises(ValidationFailed):
        apply(
            db,
            data,
            chosen=[
                selected(data["first_set"], 18, 19),
                selected(data["first_set"], 18, 19),
            ],
        )


def test_empty_selection_rejected(db, data):
    with pytest.raises(ValidationFailed):
        apply(db, data, chosen=[])


def test_invalid_idempotency_key_rejected(db, data):
    with pytest.raises(ValidationFailed):
        apply(db, data, request_key="   ")


# --------------------------------------------------
# Atomic rollback
# --------------------------------------------------

def test_audit_insertion_failure_rolls_back_all(
    db, data
):
    before_approvals = audit_count(
        db, ProgramAdaptationApproval, data["user_id"],
    )
    before_items = audit_count(
        db, ProgramAdaptationApprovalItem, data["user_id"],
    )

    def fail_insert(mapper, connection, target):
        raise RuntimeError(
            "Simulated audit insertion failure"
        )

    event.listen(
        ProgramAdaptationApprovalItem,
        "before_insert",
        fail_insert,
    )

    try:
        with pytest.raises(
            RuntimeError,
            match="Simulated audit insertion failure",
        ):
            apply(db, data)
    finally:
        event.remove(
            ProgramAdaptationApprovalItem,
            "before_insert",
            fail_insert,
        )

    assert target(db, data["first_set"]) == 18
    assert target(db, data["second_set"]) == 20

    assert audit_count(
        db, ProgramAdaptationApproval, data["user_id"],
    ) == before_approvals

    assert audit_count(
        db, ProgramAdaptationApprovalItem, data["user_id"],
    ) == before_items


def test_partial_validation_failure_is_atomic(db, data):
    with pytest.raises(ConflictError):
        apply(
            db,
            data,
            chosen=[
                selected(data["first_set"], 18, 19),
                selected(data["second_set"], 20, 25),
            ],
        )

    assert target(db, data["first_set"]) == 18
    assert target(db, data["second_set"]) == 20

    assert audit_count(
        db, ProgramAdaptationApproval, data["user_id"],
    ) == 0
