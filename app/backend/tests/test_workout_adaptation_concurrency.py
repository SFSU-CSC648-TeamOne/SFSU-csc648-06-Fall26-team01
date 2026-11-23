
"""Cross-service PostgreSQL concurrency tests.

Run from app/backend with ASCENDA_TEST_DATABASE_URL set:

    python -m pytest \
        tests/test_workout_adaptation_concurrency.py -v

Safety:
- Only local 127.0.0.1:5433/ascenda_test is accepted.
- Creates a unique temporary schema.
- Runs real workout logging and bulk approval services.
- Never touches public-schema application data.
"""

import os
from concurrent.futures import (
    ThreadPoolExecutor,
    TimeoutError as FutureTimeout,
)
from decimal import Decimal
from threading import Event
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
from sqlalchemy.orm import Session

import app.models
import app.services.apply_program_adaptations as approval_service
import app.services.workouts as workout_service

from app.core.errors import ConflictError
from app.db.base import Base
from app.models.adaptation_approval import AdaptationApproval
from app.models.catalog import Exercise
from app.models.prescription import (
    PrescriptionSet,
    WorkoutPrescription,
)
from app.models.program_adaptation_approval import (
    ProgramAdaptationApproval,
)
from app.models.program_baseline import ProgramBaseline
from app.models.program_instance import ProgramInstance
from app.models.program_phase import ProgramPhase
from app.models.tracking import (
    PerformanceEntry,
    WorkoutRecord,
)
from app.models.users import User
from app.schemas.workouts import WorkoutRecordIn
from app.services.apply_program_adaptations import (
    SelectedProgramAdjustment,
    apply_program_adaptations,
)
from app.services.workouts import create_record


def validated_database_url():
    raw = os.environ.get("ASCENDA_TEST_DATABASE_URL")

    if not raw:
        pytest.fail(
            "ASCENDA_TEST_DATABASE_URL is required."
        )

    url = make_url(raw)

    if (
        url.get_backend_name() != "postgresql"
        or url.get_driver_name() != "psycopg"
        or url.host != "127.0.0.1"
        or url.port != 5433
        or url.database != "ascenda_test"
        or url.username != "devuser"
    ):
        pytest.fail(
            "Refusing to connect to a non-test database."
        )

    return url


@pytest.fixture
def engine():
    """Provide a private schema shared by worker connections."""

    url = validated_database_url()
    schema = f"ascenda_cross_service_{uuid4().hex}"

    admin = create_engine(
        url,
        isolation_level="AUTOCOMMIT",
    )

    test_engine = None
    created = False

    try:
        with admin.connect() as connection:
            assert connection.scalar(
                text("SELECT current_database()")
            ) == "ascenda_test"

            connection.execute(
                text(f'CREATE SCHEMA "{schema}"')
            )
            created = True

        test_engine = create_engine(
            url,
            pool_size=5,
            max_overflow=2,
            connect_args={
                "options": "-cstatement_timeout=15000"
            },
        ).execution_options(
            schema_translate_map={None: schema}
        )

        Base.metadata.create_all(
            test_engine,
            checkfirst=False,
        )

        with test_engine.connect() as connection:
            inspector = inspect(connection)

            for table_name in (
                "users",
                "program_instances",
                "workout_prescriptions",
                "prescription_sets",
                "workout_records",
                "performance_entries",
                "program_adaptation_approvals",
            ):
                assert inspector.has_table(
                    table_name,
                    schema=schema,
                )

            assert connection.scalar(
                select(func.count()).select_from(
                    ProgramAdaptationApproval
                )
            ) == 0

        yield test_engine

    finally:
        if test_engine is not None:
            test_engine.dispose()

        if created:
            with admin.connect() as connection:
                connection.execute(
                    text(
                        f'DROP SCHEMA "{schema}" CASCADE'
                    )
                )

        admin.dispose()


@pytest.fixture
def data(engine):
    """One active enrollment with an approved source target."""

    with Session(engine) as db:
        user = User(
            email=f"cross-service-{uuid4().hex}@example.com",
            password_hash="test-hash",
        )

        exercise = Exercise(
            name=f"Concurrency Push-Up {uuid4().hex[:8]}"
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

        instance = ProgramInstance(
            user_id=user.id,
            program_slug="bw",
            source_baseline_id=baseline.id,
            status="active",
        )

        db.add(instance)
        db.flush()

        def add_prescription(week, reps):
            prescription = WorkoutPrescription(
                user_id=user.id,
                program_instance_id=instance.id,
                program_slug="bw",
                program_week=week,
                program_day=1,
                source_baseline_id=baseline.id,
                status="planned",
                engine_version="test-v1",
            )

            prescription.sets.append(
                PrescriptionSet(
                    exercise_id=exercise.id,
                    set_number=1,
                    target_reps=reps,
                    load_basis="bodyweight",
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

            return (
                prescription.id,
                prescription.sets[0].id,
            )

        source_id, source_set_id = add_prescription(
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

        _, future_set_id = add_prescription(
            week=3,
            reps=18,
        )

        result = {
            "user_id": user.id,
            "exercise_id": exercise.id,
            "instance_id": instance.id,
            "source_approval_id": source_approval.id,
            "future_set_id": future_set_id,
        }

        db.commit()

        return result


def log_workout(engine, data, *, linked):
    """Invoke the real workout-logging service."""

    with Session(engine) as db:
        user = db.get(User, data["user_id"])

        entry = {
            "exercise_id": data["exercise_id"],
            "set_number": 1,
            "reps": 18,
            "load_basis": "bodyweight",
        }

        if linked:
            entry["prescription_set_id"] = (
                data["future_set_id"]
            )

        body = WorkoutRecordIn(
            program_slug="bw",
            program_week=3,
            program_day=1,
            entries=[entry],
        )

        return create_record(
            db=db,
            user=user,
            data=body,
        )


def approve(engine, data):
    """Invoke the real bulk-approval service."""

    with Session(engine) as db:
        return apply_program_adaptations(
            db=db,
            user_id=data["user_id"],
            program_instance_id=data["instance_id"],
            source_approval_id=data["source_approval_id"],
            request_key=uuid4().hex,
            selections=[
                SelectedProgramAdjustment(
                    prescription_set_id=(
                        data["future_set_id"]
                    ),
                    expected_previous_value=Decimal("18"),
                    expected_proposed_value=Decimal("19"),
                )
            ],
        )


def stored_state(engine, data):
    """Read committed results using a fresh connection."""

    with Session(engine) as db:
        target = db.get(
            PrescriptionSet,
            data["future_set_id"],
        ).target_reps

        workouts = db.scalar(
            select(func.count())
            .select_from(WorkoutRecord)
            .where(
                WorkoutRecord.user_id == data["user_id"],
                WorkoutRecord.program_slug == "bw",
                WorkoutRecord.program_week == 3,
                WorkoutRecord.program_day == 1,
            )
        )

        bulk_approvals = db.scalar(
            select(func.count())
            .select_from(ProgramAdaptationApproval)
            .where(
                ProgramAdaptationApproval.user_id
                == data["user_id"]
            )
        )

        linked_entries = db.scalar(
            select(func.count())
            .select_from(PerformanceEntry)
            .where(
                PerformanceEntry.prescription_set_id
                == data["future_set_id"]
            )
        )

        return {
            "target": target,
            "workouts": workouts,
            "bulk_approvals": bulk_approvals,
            "linked_entries": linked_entries,
        }


def assert_waiting(future):
    """Check a competing request hasn't completed yet."""

    with pytest.raises(FutureTimeout):
        future.result(timeout=0.3)


# --------------------------------------------------
# Logging first: linked and unlinked history
# --------------------------------------------------

@pytest.mark.parametrize("linked", [True, False])
def test_logging_first_blocks_and_invalidates_approval(
    engine,
    data,
    monkeypatch,
    linked,
):
    """Approval waits, then rejects newly recorded history."""

    logged_but_uncommitted = Event()
    allow_log_commit = Event()

    original_add = workout_service.repo.add_record

    def pause_after_insert(db, record):
        result = original_add(db, record)

        # Record has been flushed, but the transaction
        # still holds its enrollment row lock.
        logged_but_uncommitted.set()

        if not allow_log_commit.wait(timeout=10):
            raise RuntimeError(
                "Timed out waiting to commit workout."
            )

        return result

    monkeypatch.setattr(
        workout_service.repo,
        "add_record",
        pause_after_insert,
    )

    with ThreadPoolExecutor(max_workers=2) as pool:
        logging_future = pool.submit(
            log_workout,
            engine,
            data,
            linked=linked,
        )

        try:
            assert logged_but_uncommitted.wait(timeout=10)

            approval_future = pool.submit(
                approve,
                engine,
                data,
            )

            # Approval should be blocked by the
            # uncommitted workout's enrollment lock.
            assert_waiting(approval_future)

        finally:
            allow_log_commit.set()

        logged = logging_future.result(timeout=15)
        assert logged.id > 0

        with pytest.raises(ConflictError):
            approval_future.result(timeout=15)

    state = stored_state(engine, data)

    assert state["target"] == 18
    assert state["workouts"] == 1
    assert state["bulk_approvals"] == 0
    assert state["linked_entries"] == int(linked)


# --------------------------------------------------
# Approval first: workout waits for adapted targets
# --------------------------------------------------

def test_approval_first_serializes_workout_logging(
    engine,
    data,
    monkeypatch,
):
    """Logging waits until approval commits."""

    approval_has_locks = Event()
    allow_approval = Event()
    logging_reached_lock = Event()

    original_preview = (
        approval_service.preview_program_propagation
    )

    def pause_approval_preview(*args, **kwargs):
        # The approval service has already locked
        # the enrollment, prescriptions, and sets.
        approval_has_locks.set()

        if not allow_approval.wait(timeout=10):
            raise RuntimeError(
                "Timed out waiting to finish approval."
            )

        return original_preview(*args, **kwargs)

    monkeypatch.setattr(
        approval_service,
        "preview_program_propagation",
        pause_approval_preview,
    )

    original_lock = (
        workout_service._lock_program_enrollments
    )

    def observe_logging_lock(db, user, body):
        logging_reached_lock.set()
        return original_lock(db, user, body)

    monkeypatch.setattr(
        workout_service,
        "_lock_program_enrollments",
        observe_logging_lock,
    )

    with ThreadPoolExecutor(max_workers=2) as pool:
        approval_future = pool.submit(
            approve,
            engine,
            data,
        )

        try:
            assert approval_has_locks.wait(timeout=10)

            logging_future = pool.submit(
                log_workout,
                engine,
                data,
                linked=True,
            )

            assert logging_reached_lock.wait(timeout=10)

            # Logging cannot proceed past the same
            # enrollment lock held by approval.
            assert_waiting(logging_future)

        finally:
            allow_approval.set()

        approved = approval_future.result(timeout=15)
        logged = logging_future.result(timeout=15)

    assert approved["status"] == "updated"
    assert logged.id > 0

    state = stored_state(engine, data)

    assert state == {
        "target": 19,
        "workouts": 1,
        "bulk_approvals": 1,
        "linked_entries": 1,
    }
