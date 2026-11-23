"""PostgreSQL concurrency tests for program-wide adaptations.

Run from app/backend using ASCENDA_TEST_DATABASE_URL.

SAFETY:
- Refuses connections outside local ascenda_test.
- Creates a unique temporary test schema.
- Never modifies public-schema application records.
- Removes only its own temporary schema.
- Uses independent PostgreSQL connections.
"""

import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import (
    create_engine,
    func,
    inspect,
    select,
    text,
)
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

import app.models

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
from app.models.program_adaptation_approval import (
    ProgramAdaptationApproval,
    ProgramAdaptationApprovalItem,
)
from app.models.users import User
from app.services.apply_program_adaptations import (
    SelectedProgramAdjustment,
    apply_program_adaptations,
)


def validated_database_url():
    raw = os.environ.get("ASCENDA_TEST_DATABASE_URL")

    if not raw:
        pytest.fail("ASCENDA_TEST_DATABASE_URL is required.")

    url = make_url(raw)

    if (
        url.get_backend_name() != "postgresql"
        or url.get_driver_name() != "psycopg"
        or url.host != "127.0.0.1"
        or url.port != 5433
        or url.database != "ascenda_test"
        or url.username != "devuser"
    ):
        pytest.fail("Refusing to use a non-test database.")

    return url


@pytest.fixture
def engine():
    """Create an explicitly isolated PostgreSQL schema."""

    url = validated_database_url()

    schema = f"ascenda_concurrency_{uuid4().hex}"

    admin = create_engine(
        url,
        isolation_level="AUTOCOMMIT",
    )

    test_engine = None
    created = False

    try:
        with admin.connect() as connection:
            database_name = connection.scalar(text("SELECT current_database()"))

            if database_name != "ascenda_test":
                pytest.fail("Unexpected database.")

            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            created = True

        # Translate all unqualified SQLAlchemy model
        # tables explicitly into our temporary schema.
        #
        # Do not use a public-schema search_path
        # fallback: it may resolve existing tables.
        test_engine = create_engine(
            url,
            pool_size=5,
            max_overflow=2,
            connect_args={"options": "-cstatement_timeout=10000"},
        ).execution_options(schema_translate_map={None: schema})

        # Create every registered model table inside
        # our isolated test schema.
        Base.metadata.create_all(
            test_engine,
            checkfirst=False,
        )

        # Independently verify table placement and
        # that no pre-existing approvals are visible.
        with test_engine.connect() as connection:
            inspector = inspect(connection)

            for table_name in (
                "users",
                "program_instances",
                "workout_prescriptions",
                "prescription_sets",
                "adaptation_approvals",
                "program_adaptation_approvals",
                "program_adaptation_approval_items",
            ):
                if not inspector.has_table(
                    table_name,
                    schema=schema,
                ):
                    pytest.fail(f"Missing isolated table: {table_name}")

            approval_count = connection.scalar(
                select(func.count()).select_from(ProgramAdaptationApproval)
            )

            item_count = connection.scalar(
                select(func.count()).select_from(ProgramAdaptationApprovalItem)
            )

            assert approval_count == 0
            assert item_count == 0

        yield test_engine

    finally:
        if test_engine is not None:
            test_engine.dispose()

        if created:
            with admin.connect() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))

        admin.dispose()


def add_workout(
    db,
    *,
    user_id,
    instance_id,
    baseline_id,
    exercise_id,
    week,
    reps,
):
    prescription = WorkoutPrescription(
        user_id=user_id,
        program_instance_id=instance_id,
        program_slug="bw",
        program_week=week,
        program_day=1,
        source_baseline_id=baseline_id,
        status="planned",
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

    db.add(
        ProgramPhase(
            workout_prescription_id=prescription.id,
            phase_type="training",
        )
    )

    db.flush()

    return prescription.id, prescription.sets[0].id


@pytest.fixture
def data(engine):
    with Session(engine) as db:
        user = User(
            email=f"concurrency-{uuid4().hex}@example.com",
            password_hash="test-hash",
        )
        exercise = Exercise(name="Concurrency Test Push-Up")

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

        instance = ProgramInstance(
            user_id=user.id,
            program_slug="bw",
            source_baseline_id=baseline.id,
            status="active",
        )

        db.add(instance)
        db.flush()

        source_id, source_set_id = add_workout(
            db,
            user_id=user.id,
            instance_id=instance.id,
            baseline_id=baseline.id,
            exercise_id=exercise.id,
            week=2,
            reps=16,
        )

        approval = AdaptationApproval(
            user_id=user.id,
            workout_prescription_id=source_id,
            prescription_set_id=source_set_id,
            adjustment_type="reps",
            previous_value=Decimal("15"),
            approved_value=Decimal("16"),
            proposal_engine_version="test-v1",
        )

        db.add(approval)
        db.flush()

        _, future_set_id = add_workout(
            db,
            user_id=user.id,
            instance_id=instance.id,
            baseline_id=baseline.id,
            exercise_id=exercise.id,
            week=3,
            reps=18,
        )

        result = {
            "user_id": user.id,
            "instance_id": instance.id,
            "approval_id": approval.id,
            "set_id": future_set_id,
        }

        db.commit()

        return result


def run_approval(engine, data, key):
    with Session(engine) as db:
        return apply_program_adaptations(
            db=db,
            user_id=data["user_id"],
            program_instance_id=data["instance_id"],
            source_approval_id=data["approval_id"],
            request_key=key,
            selections=[
                SelectedProgramAdjustment(
                    prescription_set_id=data["set_id"],
                    expected_previous_value=Decimal("18"),
                    expected_proposed_value=Decimal("19"),
                )
            ],
        )


def stored_state(engine, data):
    with Session(engine) as db:
        current = db.get(
            PrescriptionSet,
            data["set_id"],
        ).target_reps

        approvals = db.scalar(
            select(func.count()).select_from(ProgramAdaptationApproval)
        )

        items = db.scalar(
            select(func.count()).select_from(ProgramAdaptationApprovalItem)
        )

        return current, approvals, items


# --------------------------------------------------
# Competing requests with the same idempotency key
# --------------------------------------------------


def test_concurrent_identical_requests_apply_once(engine, data):
    key = uuid4().hex
    barrier = Barrier(2)

    def worker():
        barrier.wait(timeout=5)
        return run_approval(engine, data, key)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(worker)
        second = pool.submit(worker)

        results = [
            first.result(timeout=15),
            second.result(timeout=15),
        ]

    statuses = sorted(result["status"] for result in results)

    assert statuses == [
        "already_applied",
        "updated",
    ]

    assert (
        results[0]["program_adaptation_approval_id"]
        == results[1]["program_adaptation_approval_id"]
    )

    assert stored_state(engine, data) == (19, 1, 1)


# --------------------------------------------------
# Competing requests with different idempotency keys
# --------------------------------------------------


def test_concurrent_distinct_requests_cannot_apply_twice(engine, data):
    barrier = Barrier(2)

    def worker(key):
        barrier.wait(timeout=5)

        try:
            return run_approval(engine, data, key)
        except Exception as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(worker, uuid4().hex)
        second = pool.submit(worker, uuid4().hex)

        results = [
            first.result(timeout=15),
            second.result(timeout=15),
        ]

    successful = [
        item
        for item in results
        if isinstance(item, dict) and item.get("status") == "updated"
    ]

    failed = [item for item in results if isinstance(item, Exception)]

    assert len(successful) == 1
    assert len(failed) == 1

    # The second operation must not commit another
    # adjustment or audit event.
    assert stored_state(engine, data) == (19, 1, 1)


# --------------------------------------------------
# Verify PostgreSQL row-lock protection
# --------------------------------------------------


def test_enrollment_row_lock_blocks_competing_approval(engine, data):
    # Lock the enrollment in one transaction.
    with engine.connect() as connection:
        transaction = connection.begin()

        try:
            connection.execute(
                select(ProgramInstance.id)
                .where(ProgramInstance.id == data["instance_id"])
                .with_for_update()
            ).scalar_one()

            # A second connection must not bypass
            # the locked enrollment row.
            with engine.connect() as second:
                second.execute(text("SET LOCAL lock_timeout = '250ms'"))

                with pytest.raises(OperationalError):
                    second.execute(
                        select(ProgramInstance.id)
                        .where(ProgramInstance.id == data["instance_id"])
                        .with_for_update()
                    ).scalar_one()

                second.rollback()

        finally:
            transaction.rollback()

    assert stored_state(engine, data) == (18, 0, 0)
