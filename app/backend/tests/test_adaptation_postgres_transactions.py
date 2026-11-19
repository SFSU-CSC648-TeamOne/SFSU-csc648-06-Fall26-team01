
"""PostgreSQL integration tests for adaptation approval transactions.

Run from app/backend:
    python -m pytest tests/test_adaptation_postgres_transactions.py -v

Requires ASCENDA_TEST_DATABASE_URL pointing to a dedicated
LOCAL PostgreSQL database whose name starts with ascenda_test.

Never uses the application's DATABASE_URL.
Never runs against hosted Supabase.
"""

import os
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import (
    create_engine,
    event,
    select,
    text,
)
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

import app.models

from app.db.base import Base
from app.models import (
    Exercise,
    PrescriptionSet,
    User,
    WorkoutPrescription,
)
from app.models.adaptation_approval import AdaptationApproval
from app.services import approve_adaptation as service
from app.services.approve_adaptation import ApprovedAdjustment
from app.services.prescription_adaptation import ENGINE_VERSION


@pytest.fixture
def pg_engine():
    """Build isolated tables in a disposable PostgreSQL schema."""

    raw_url = os.getenv("ASCENDA_TEST_DATABASE_URL")

    if not raw_url:
        pytest.skip(
            "Set ASCENDA_TEST_DATABASE_URL to run "
            "PostgreSQL integration tests."
        )

    url = make_url(raw_url)

    if url.get_backend_name() != "postgresql":
        pytest.fail("Test database must be PostgreSQL.")

    if url.host not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail(
            "Remote databases are not allowed for these tests."
        )

    if not (url.database or "").startswith("ascenda_test"):
        pytest.fail(
            "Database name must start with ascenda_test."
        )

    schema = f"adapt_test_{uuid4().hex}"

    admin_engine = create_engine(raw_url)

    with admin_engine.begin() as connection:
        connection.execute(
            text(f'CREATE SCHEMA "{schema}"')
        )

    engine = None

    try:
        engine = create_engine(
            raw_url,
            connect_args={
                "options": f"-csearch_path={schema}"
            },
        )

        Base.metadata.create_all(engine)

        yield engine

    finally:
        if engine is not None:
            engine.dispose()

        with admin_engine.begin() as connection:
            connection.execute(
                text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            )

        admin_engine.dispose()


@pytest.fixture
def db(pg_engine):
    with Session(pg_engine) as session:
        yield session


@pytest.fixture
def sample(db):
    """Create one user, exercise and planned prescription."""

    user = User(
        email=f"pg-adapt-{uuid4().hex}@example.com",
        password_hash="test-hash",
    )

    exercise = Exercise(
        name=f"PostgreSQL Push-Up {uuid4().hex[:8]}"
    )

    db.add_all([user, exercise])
    db.commit()

    prescription = WorkoutPrescription(
        user_id=user.id,
        program_slug="bw",
        program_week=3,
        program_day=1,
        status="planned",
        engine_version="baseline-v1",
    )

    prescription.sets.append(
        PrescriptionSet(
            exercise_id=exercise.id,
            set_number=1,
            target_reps=15,
            load_basis="bodyweight",
        )
    )

    db.add(prescription)
    db.commit()

    return {
        "user_id": user.id,
        "prescription_id": prescription.id,
        "set_id": prescription.sets[0].id,
    }


def mock_progression(monkeypatch, set_id):
    """Return a valid, server-side progression recommendation."""

    def fake_analysis(db, user_id, prescription_id):
        return {
            "prescription_id": prescription_id,
            "user_id": user_id,
            "status": "proposed",
            "proposal_engine_version": ENGINE_VERSION,
            "sets": [
                {
                    "prescription_set_id": set_id,
                    "decision": {
                        "action": "progress",
                    },
                    "proposal": {
                        "adjustment_type": "reps",
                        "previous_value": 15,
                        "proposed_value": 16,
                        "requires_approval": True,
                    },
                }
            ],
        }

    monkeypatch.setattr(
        service,
        "analyze_prescription_adaptations",
        fake_analysis,
    )


def approve(db, sample):
    return service.apply_approved_adaptations(
        db=db,
        user_id=sample["user_id"],
        prescription_id=sample["prescription_id"],
        approvals=[
            ApprovedAdjustment(
                prescription_set_id=sample["set_id"],
                adjustment_type="reps",
                expected_previous_value=Decimal("15"),
                expected_proposed_value=Decimal("16"),
            )
        ],
    )


def read_audits(db, prescription_id):
    return db.scalars(
        select(AdaptationApproval).where(
            AdaptationApproval.workout_prescription_id
            == prescription_id
        )
    ).all()


# --------------------------------------------------
# Test 1: Successful PostgreSQL transaction
# --------------------------------------------------

def test_postgres_approval_commits_target_and_audit(
    db, sample, monkeypatch
):
    mock_progression(monkeypatch, sample["set_id"])

    result = approve(db, sample)

    assert result["status"] == "updated"
    assert result["updated_set_count"] == 1

    # Check using a separate session after commit.
    with Session(db.bind) as verifier:
        prescribed_set = verifier.get(
            PrescriptionSet,
            sample["set_id"],
        )

        records = read_audits(
            verifier,
            sample["prescription_id"],
        )

        assert prescribed_set.target_reps == 16
        assert len(records) == 1

        audit = records[0]

        assert audit.user_id == sample["user_id"]
        assert audit.prescription_set_id == sample["set_id"]
        assert audit.adjustment_type == "reps"
        assert audit.previous_value == Decimal("15.00")
        assert audit.approved_value == Decimal("16.00")
        assert audit.proposal_engine_version == ENGINE_VERSION
        assert audit.approved_at is not None


# --------------------------------------------------
# Test 2: PostgreSQL rollback on audit failure
# --------------------------------------------------

def test_postgres_audit_failure_rolls_back_target(
    db, sample, monkeypatch
):
    mock_progression(monkeypatch, sample["set_id"])

    def reject_insert(mapper, connection, target):
        raise RuntimeError(
            "Simulated PostgreSQL audit failure"
        )

    event.listen(
        AdaptationApproval,
        "before_insert",
        reject_insert,
    )

    try:
        with pytest.raises(
            RuntimeError,
            match="Simulated PostgreSQL audit failure",
        ):
            approve(db, sample)

    finally:
        event.remove(
            AdaptationApproval,
            "before_insert",
            reject_insert,
        )

    # Check persisted state from a new transaction.
    with Session(db.bind) as verifier:
        prescribed_set = verifier.get(
            PrescriptionSet,
            sample["set_id"],
        )

        records = read_audits(
            verifier,
            sample["prescription_id"],
        )

        assert prescribed_set.target_reps == 15
        assert records == []


# --------------------------------------------------
# Test 3: PostgreSQL row locking
# --------------------------------------------------

def test_postgres_prescription_row_lock(pg_engine):
    """Concurrent transactions cannot acquire conflicting locks."""

    with Session(pg_engine) as setup:
        user = User(
            email=f"pg-lock-{uuid4().hex}@example.com",
            password_hash="test-hash",
        )
        setup.add(user)
        setup.commit()

        prescription = WorkoutPrescription(
            user_id=user.id,
            program_slug="bw",
            program_week=1,
            program_day=1,
            status="planned",
            engine_version="baseline-v1",
        )

        setup.add(prescription)
        setup.commit()

        prescription_id = prescription.id

    with Session(pg_engine) as first:
        with Session(pg_engine) as second:

            # Transaction 1 obtains the row lock.
            locked = first.scalar(
                select(WorkoutPrescription)
                .where(
                    WorkoutPrescription.id
                    == prescription_id
                )
                .with_for_update()
            )

            assert locked is not None

            # Transaction 2 must not acquire that lock.
            with pytest.raises(OperationalError):
                second.scalar(
                    select(WorkoutPrescription)
                    .where(
                        WorkoutPrescription.id
                        == prescription_id
                    )
                    .with_for_update(nowait=True)
                )

            second.rollback()

            # Release Transaction 1's lock.
            first.commit()

            # Transaction 2 can now acquire it.
            acquired = second.scalar(
                select(WorkoutPrescription)
                .where(
                    WorkoutPrescription.id
                    == prescription_id
                )
                .with_for_update(nowait=True)
            )

            assert acquired is not None

            second.rollback()
