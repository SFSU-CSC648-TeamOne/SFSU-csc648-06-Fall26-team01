"""HTTP integration tests for program-wide adaptation approval.

Run from app/backend:
    python -m pytest tests/test_program_adaptation_approval_api.py -v

Uses isolated in-memory SQLite.
Does not connect to Supabase or local PostgreSQL.
"""

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.models

from app.api.deps import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.main import app
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

ENDPOINT = "/api/adaptations/program-instances/" "{instance_id}/approve"


# --------------------------------------------------
# Isolated database and HTTP client
# --------------------------------------------------


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
def client(db):
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def data(db):
    owner = User(
        email=f"bulk-owner-{uuid4().hex}@example.com",
        password_hash="test-hash",
    )
    other = User(
        email=f"bulk-other-{uuid4().hex}@example.com",
        password_hash="test-hash",
    )
    exercise = Exercise(name=f"Bulk API Push-Up {uuid4().hex[:8]}")

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

    db.add_all([first, second])
    db.flush()

    def add_workout(instance_id, week, reps, phase):
        prescription = WorkoutPrescription(
            user_id=owner.id,
            program_instance_id=instance_id,
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

        if phase is not None:
            db.add(
                ProgramPhase(
                    workout_prescription_id=prescription.id,
                    phase_type=phase,
                )
            )

        db.flush()

        return (
            prescription.id,
            prescription.sets[0].id,
        )

    source_id, source_set = add_workout(first.id, 2, 16, "training")

    source_approval = AdaptationApproval(
        user_id=owner.id,
        workout_prescription_id=source_id,
        prescription_set_id=source_set,
        adjustment_type="reps",
        previous_value=Decimal("15"),
        approved_value=Decimal("16"),
        proposal_engine_version="test-v1",
    )

    db.add(source_approval)
    db.flush()

    future_id, future_set = add_workout(first.id, 3, 18, "training")

    later_id, later_set = add_workout(first.id, 4, 20, "training")

    deload_id, deload_set = add_workout(first.id, 5, 12, "deload")

    other_id, other_set = add_workout(second.id, 3, 18, "training")

    db.commit()

    return {
        "owner": owner,
        "other": other,
        "instance_id": first.id,
        "other_instance_id": second.id,
        "source_approval_id": source_approval.id,
        "future_id": future_id,
        "future_set": future_set,
        "later_id": later_id,
        "later_set": later_set,
        "deload_id": deload_id,
        "deload_set": deload_set,
        "other_id": other_id,
        "other_set": other_set,
    }


def authenticate(user):
    """Simulate an authenticated identity in HTTP tests."""
    app.dependency_overrides[get_current_user] = lambda: user


def selection(set_id, previous, proposed):
    return {
        "prescription_set_id": set_id,
        "expected_previous_value": previous,
        "expected_proposed_value": proposed,
    }


def request_body(data, *, key=None, selections=None):
    return {
        "source_approval_id": data["source_approval_id"],
        "request_key": key or uuid4().hex,
        "selections": (
            [
                selection(data["future_set"], 18, 19),
                selection(data["later_set"], 20, 21),
            ]
            if selections is None
            else selections
        ),
    }


def post_approval(client, instance_id, body):
    return client.post(
        ENDPOINT.format(instance_id=instance_id),
        json=body,
    )


def target(db, set_id):
    db.expire_all()
    return db.get(PrescriptionSet, set_id).target_reps


def count(db, model):
    return db.scalar(select(func.count()).select_from(model))


# --------------------------------------------------
# Route and request validation
# --------------------------------------------------


def test_approval_route_registered():
    routes = {
        (route.path, method)
        for route in app.routes
        for method in getattr(route, "methods", set())
    }

    assert (
        "/api/adaptations/program-instances/" "{program_instance_id}/approve",
        "POST",
    ) in routes


def test_authentication_required(client, data):
    response = post_approval(
        client,
        data["instance_id"],
        request_body(data),
    )

    assert response.status_code == 401


def test_invalid_enrollment_id_returns_422(client, data):
    authenticate(data["owner"])

    response = post_approval(
        client,
        0,
        request_body(data),
    )

    assert response.status_code == 422


def test_empty_selection_returns_422(client, data):
    authenticate(data["owner"])

    response = post_approval(
        client,
        data["instance_id"],
        request_body(data, selections=[]),
    )

    assert response.status_code == 422


def test_duplicate_selection_returns_422(client, data):
    authenticate(data["owner"])

    item = selection(data["future_set"], 18, 19)

    response = post_approval(
        client,
        data["instance_id"],
        request_body(
            data,
            selections=[item, item],
        ),
    )

    assert response.status_code == 422


def test_invalid_progression_returns_422(client, data):
    authenticate(data["owner"])

    response = post_approval(
        client,
        data["instance_id"],
        request_body(
            data,
            selections=[
                selection(data["future_set"], 18, 17),
            ],
        ),
    )

    assert response.status_code == 422


def test_client_cannot_override_user_id(client, data):
    authenticate(data["owner"])

    body = request_body(data)
    body["user_id"] = data["other"].id

    response = post_approval(
        client,
        data["instance_id"],
        body,
    )

    assert response.status_code == 422


# --------------------------------------------------
# Successful approval
# --------------------------------------------------


def test_valid_approval_updates_selected_sets(client, db, data):
    authenticate(data["owner"])

    response = post_approval(
        client,
        data["instance_id"],
        request_body(data),
    )

    assert response.status_code == 200, response.text

    result = response.json()

    assert result["status"] == "updated"
    assert result["program_instance_id"] == (data["instance_id"])
    assert result["source_approval_id"] == (data["source_approval_id"])
    assert result["updated_set_count"] == 2
    assert result["program_adaptation_approval_id"] > 0

    assert {item["prescription_set_id"] for item in result["updated_sets"]} == {
        data["future_set"],
        data["later_set"],
    }

    assert target(db, data["future_set"]) == 19
    assert target(db, data["later_set"]) == 21


def test_only_selected_sets_change(client, db, data):
    authenticate(data["owner"])

    response = post_approval(
        client,
        data["instance_id"],
        request_body(
            data,
            selections=[
                selection(data["future_set"], 18, 19),
            ],
        ),
    )

    assert response.status_code == 200, response.text

    assert target(db, data["future_set"]) == 19
    assert target(db, data["later_set"]) == 20
    assert target(db, data["deload_set"]) == 12
    assert target(db, data["other_set"]) == 18


def test_approval_creates_complete_audit(client, db, data):
    authenticate(data["owner"])

    response = post_approval(
        client,
        data["instance_id"],
        request_body(data),
    )

    assert response.status_code == 200, response.text

    result = response.json()

    approval = db.get(
        ProgramAdaptationApproval,
        result["program_adaptation_approval_id"],
    )

    assert approval is not None
    assert approval.user_id == data["owner"].id
    assert approval.program_instance_id == (data["instance_id"])
    assert approval.source_approval_id == (data["source_approval_id"])

    items = db.scalars(
        select(ProgramAdaptationApprovalItem).where(
            ProgramAdaptationApprovalItem.program_adaptation_approval_id == approval.id
        )
    ).all()

    assert len(items) == 2

    assert {item.prescription_set_id for item in items} == {
        data["future_set"],
        data["later_set"],
    }


# --------------------------------------------------
# Idempotency
# --------------------------------------------------


def test_identical_retry_does_not_apply_twice(client, db, data):
    authenticate(data["owner"])

    body = request_body(data, key=uuid4().hex)

    first = post_approval(client, data["instance_id"], body)

    second = post_approval(client, data["instance_id"], body)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text

    assert first.json()["status"] == "updated"
    assert second.json()["status"] == "already_applied"

    assert (
        first.json()["program_adaptation_approval_id"]
        == second.json()["program_adaptation_approval_id"]
    )

    assert count(db, ProgramAdaptationApproval) == 1
    assert count(db, ProgramAdaptationApprovalItem) == 2

    assert target(db, data["future_set"]) == 19
    assert target(db, data["later_set"]) == 21


def test_reused_key_with_different_values_returns_409(client, db, data):
    authenticate(data["owner"])

    key = uuid4().hex

    first = post_approval(
        client,
        data["instance_id"],
        request_body(data, key=key),
    )

    assert first.status_code == 200, first.text

    changed = request_body(
        data,
        key=key,
        selections=[
            selection(data["future_set"], 18, 20),
            selection(data["later_set"], 20, 21),
        ],
    )

    second = post_approval(
        client,
        data["instance_id"],
        changed,
    )

    assert second.status_code == 409
    assert target(db, data["future_set"]) == 19
    assert count(db, ProgramAdaptationApproval) == 1


# --------------------------------------------------
# Enrollment security
# --------------------------------------------------


def test_other_user_returns_404(client, db, data):
    authenticate(data["other"])

    response = post_approval(
        client,
        data["instance_id"],
        request_body(data),
    )

    assert response.status_code == 404

    assert target(db, data["future_set"]) == 18


def test_wrong_enrollment_returns_404(client, db, data):
    authenticate(data["owner"])

    response = post_approval(
        client,
        data["other_instance_id"],
        request_body(data),
    )

    assert response.status_code == 404


def test_unknown_enrollment_returns_404(client, db, data):
    authenticate(data["owner"])

    response = post_approval(
        client,
        999999999,
        request_body(data),
    )

    assert response.status_code == 404


# --------------------------------------------------
# Protected workouts and stale proposals
# --------------------------------------------------


def test_deload_selection_returns_409(client, db, data):
    authenticate(data["owner"])

    response = post_approval(
        client,
        data["instance_id"],
        request_body(
            data,
            selections=[
                selection(data["deload_set"], 12, 13),
            ],
        ),
    )

    assert response.status_code == 409
    assert target(db, data["deload_set"]) == 12


def test_stale_selection_returns_409(client, db, data):
    prescribed_set = db.get(
        PrescriptionSet,
        data["future_set"],
    )

    prescribed_set.target_reps = 22
    db.commit()

    authenticate(data["owner"])

    response = post_approval(
        client,
        data["instance_id"],
        request_body(data),
    )

    assert response.status_code == 409

    # No changes to the other selected set.
    assert target(db, data["future_set"]) == 22
    assert target(db, data["later_set"]) == 20

    assert count(db, ProgramAdaptationApproval) == 0


def test_recorded_workout_returns_409(client, db, data):
    db.add(
        WorkoutRecord(
            user_id=data["owner"].id,
            program_slug="bw",
            program_week=3,
            program_day=1,
        )
    )
    db.commit()

    authenticate(data["owner"])

    response = post_approval(
        client,
        data["instance_id"],
        request_body(
            data,
            selections=[
                selection(data["future_set"], 18, 19),
            ],
        ),
    )

    assert response.status_code == 409
    assert target(db, data["future_set"]) == 18


# --------------------------------------------------
# Atomicity through the HTTP route
# --------------------------------------------------


def test_partial_invalid_selection_changes_nothing(client, db, data):
    authenticate(data["owner"])

    response = post_approval(
        client,
        data["instance_id"],
        request_body(
            data,
            selections=[
                selection(data["future_set"], 18, 19),
                selection(data["later_set"], 20, 25),
            ],
        ),
    )

    assert response.status_code == 409

    assert target(db, data["future_set"]) == 18
    assert target(db, data["later_set"]) == 20

    assert count(db, ProgramAdaptationApproval) == 0
    assert count(db, ProgramAdaptationApprovalItem) == 0
