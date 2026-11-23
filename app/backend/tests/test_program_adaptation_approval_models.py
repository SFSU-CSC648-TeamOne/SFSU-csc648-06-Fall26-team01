"""PostgreSQL tests for program-wide adaptation audit models.

Run from app/backend:
    python -m pytest \
        tests/test_program_adaptation_approval_models.py -v

Requires ASCENDA_TEST_DATABASE_URL.

Only allows the dedicated local PostgreSQL test database.
Each test runs within an outer transaction that is rolled
back afterward. Constraint failures use nested savepoints.
"""

import os
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import (
    create_engine,
    delete,
    inspect,
    select,
)
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import app.models

from app.models.adaptation_approval import AdaptationApproval
from app.models.catalog import Exercise
from app.models.prescription import (
    PrescriptionSet,
    WorkoutPrescription,
)
from app.models.program_instance import ProgramInstance
from app.models.program_adaptation_approval import (
    ProgramAdaptationApproval,
    ProgramAdaptationApprovalItem,
)
from app.models.users import User

REQUIRED_TABLES = {
    "users",
    "exercises",
    "program_instances",
    "workout_prescriptions",
    "prescription_sets",
    "adaptation_approvals",
    "program_adaptation_approvals",
    "program_adaptation_approval_items",
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
        pytest.fail(
            "Refusing to use a database other than "
            "local 127.0.0.1:5433/ascenda_test."
        )

    engine = create_engine(url)

    try:
        with engine.connect() as connection:
            database_name = connection.exec_driver_sql(
                "SELECT current_database()"
            ).scalar_one()

            if database_name != "ascenda_test":
                pytest.fail("Unexpected database.")

            available = set(inspect(connection).get_table_names())

            missing = REQUIRED_TABLES - available

            if missing:
                pytest.fail(f"Missing audit tables: {sorted(missing)}")

            # Inspection triggered SQLAlchemy autobegin.
            # Close that transaction before beginning
            # the isolated test transaction.
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


@pytest.fixture
def data(db):
    user = User(
        email=f"audit-{uuid4().hex}@example.com",
        password_hash="test-hash",
    )

    exercise = Exercise(name=f"Audit Exercise {uuid4().hex[:8]}")

    db.add_all([user, exercise])
    db.flush()

    instance = ProgramInstance(
        user_id=user.id,
        program_slug="bw",
        status="active",
    )

    db.add(instance)
    db.flush()

    source = WorkoutPrescription(
        user_id=user.id,
        program_instance_id=instance.id,
        program_slug="bw",
        program_week=1,
        program_day=1,
        status="planned",
        engine_version="test-v1",
    )

    source_set = PrescriptionSet(
        exercise_id=exercise.id,
        set_number=1,
        target_reps=16,
        load_basis="bodyweight",
    )

    source.sets.append(source_set)
    db.add(source)
    db.flush()

    individual_approval = AdaptationApproval(
        user_id=user.id,
        workout_prescription_id=source.id,
        prescription_set_id=source_set.id,
        adjustment_type="reps",
        previous_value=Decimal("15"),
        approved_value=Decimal("16"),
        proposal_engine_version="test-v1",
    )

    future = WorkoutPrescription(
        user_id=user.id,
        program_instance_id=instance.id,
        program_slug="bw",
        program_week=2,
        program_day=1,
        status="planned",
        engine_version="test-v1",
    )

    future_set = PrescriptionSet(
        exercise_id=exercise.id,
        set_number=1,
        target_reps=18,
        load_basis="bodyweight",
    )

    future.sets.append(future_set)

    db.add_all([individual_approval, future])
    db.flush()

    return {
        "user_id": user.id,
        "instance_id": instance.id,
        "source_approval_id": individual_approval.id,
        "future_prescription_id": future.id,
        "future_set_id": future_set.id,
    }


def make_approval(db, data, *, request_key=None):
    approval = ProgramAdaptationApproval(
        user_id=data["user_id"],
        program_instance_id=data["instance_id"],
        source_approval_id=data["source_approval_id"],
        request_key=request_key or uuid4().hex,
        proposal_engine_version="test-v1",
    )

    db.add(approval)
    db.flush()

    return approval


def make_item(
    db,
    data,
    approval,
    *,
    previous=Decimal("18"),
    approved=Decimal("19"),
    adjustment_type="reps",
    prescription_set_id=None,
    workout_prescription_id=None,
):
    item = ProgramAdaptationApprovalItem(
        program_adaptation_approval_id=approval.id,
        workout_prescription_id=(
            workout_prescription_id
            if workout_prescription_id is not None
            else data["future_prescription_id"]
        ),
        prescription_set_id=(
            prescription_set_id
            if prescription_set_id is not None
            else data["future_set_id"]
        ),
        adjustment_type=adjustment_type,
        previous_value=previous,
        approved_value=approved,
    )

    db.add(item)
    db.flush()

    return item


# --------------------------------------------------
# Successful persistence and relationships
# --------------------------------------------------


def test_audit_event_and_item_persist(db, data):
    approval = make_approval(db, data)
    item = make_item(db, data, approval)

    approval_id = approval.id
    item_id = item.id

    db.expire_all()

    stored = db.get(
        ProgramAdaptationApproval,
        approval_id,
    )

    assert stored is not None
    assert stored.user_id == data["user_id"]
    assert stored.program_instance_id == data["instance_id"]
    assert stored.source_approval_id == data["source_approval_id"]
    assert stored.approved_at is not None

    assert len(stored.items) == 1
    assert stored.items[0].id == item_id
    assert stored.items[0].previous_value == Decimal("18")
    assert stored.items[0].approved_value == Decimal("19")


def test_audit_relationships(db, data):
    approval = make_approval(db, data)
    item = make_item(db, data, approval)

    assert approval.program_instance.id == data["instance_id"]
    assert approval.source_approval.id == (data["source_approval_id"])
    assert item.approval.id == approval.id
    assert item.prescription_set.id == data["future_set_id"]
    assert item.prescription.id == (data["future_prescription_id"])


def test_audit_creation_does_not_change_target(db, data):
    approval = make_approval(db, data)
    make_item(db, data, approval)

    db.expire_all()

    future_set = db.get(
        PrescriptionSet,
        data["future_set_id"],
    )

    # Audit models do not themselves apply changes.
    assert future_set.target_reps == 18


# --------------------------------------------------
# Uniqueness constraints
# --------------------------------------------------


def test_duplicate_idempotency_key_rejected(db, data):
    key = uuid4().hex

    make_approval(db, data, request_key=key)

    with pytest.raises(IntegrityError):
        with db.begin_nested():
            make_approval(
                db,
                data,
                request_key=key,
            )

    # Original record remains accessible.
    stored = db.scalar(
        select(ProgramAdaptationApproval).where(
            ProgramAdaptationApproval.request_key == key
        )
    )

    assert stored is not None


def test_duplicate_selected_set_rejected(db, data):
    approval = make_approval(db, data)
    make_item(db, data, approval)

    with pytest.raises(IntegrityError):
        with db.begin_nested():
            make_item(db, data, approval)


# --------------------------------------------------
# CHECK constraints
# --------------------------------------------------


@pytest.mark.parametrize(
    "previous,approved",
    [
        (Decimal("0"), Decimal("1")),
        (Decimal("-1"), Decimal("1")),
        (Decimal("18"), Decimal("18")),
        (Decimal("19"), Decimal("18")),
    ],
)
def test_invalid_progression_rejected(db, data, previous, approved):
    approval = make_approval(db, data)

    with pytest.raises(IntegrityError):
        with db.begin_nested():
            make_item(
                db,
                data,
                approval,
                previous=previous,
                approved=approved,
            )


def test_invalid_adjustment_type_rejected(db, data):
    approval = make_approval(db, data)

    with pytest.raises(IntegrityError):
        with db.begin_nested():
            make_item(
                db,
                data,
                approval,
                adjustment_type="assistance",
            )


# --------------------------------------------------
# Foreign-key enforcement
# --------------------------------------------------


def test_invalid_enrollment_reference_rejected(db, data):
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            approval = ProgramAdaptationApproval(
                user_id=data["user_id"],
                program_instance_id=999999999,
                source_approval_id=data["source_approval_id"],
                request_key=uuid4().hex,
                proposal_engine_version="test-v1",
            )
            db.add(approval)
            db.flush()


def test_invalid_prescription_set_reference_rejected(db, data):
    approval = make_approval(db, data)

    with pytest.raises(IntegrityError):
        with db.begin_nested():
            make_item(
                db,
                data,
                approval,
                prescription_set_id=999999999,
            )


# --------------------------------------------------
# Historical audit protection
# --------------------------------------------------


def test_source_approval_cannot_be_deleted(db, data):
    approval = make_approval(db, data)
    make_item(db, data, approval)

    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.execute(
                delete(AdaptationApproval).where(
                    AdaptationApproval.id == data["source_approval_id"]
                )
            )


def test_approval_with_items_cannot_be_deleted(db, data):
    approval = make_approval(db, data)
    make_item(db, data, approval)

    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.execute(
                delete(ProgramAdaptationApproval).where(
                    ProgramAdaptationApproval.id == approval.id
                )
            )
