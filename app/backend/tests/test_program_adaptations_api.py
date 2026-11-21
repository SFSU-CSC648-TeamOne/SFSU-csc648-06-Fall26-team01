
"""HTTP integration tests for enrollment-scoped adaptation previews.

Run from app/backend:
    python -m pytest tests/test_program_adaptations_api.py -v

Uses isolated in-memory SQLite and overrides FastAPI dependencies.
No Supabase or PostgreSQL connections are made by these tests.
"""

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
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
from app.models.users import User


ENDPOINT = (
    "/api/adaptations/program-instances/"
    "{instance_id}/preview"
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
        email=f"preview-owner-{uuid4().hex}@example.com",
        password_hash="test-hash",
    )
    other = User(
        email=f"preview-other-{uuid4().hex}@example.com",
        password_hash="test-hash",
    )
    exercise = Exercise(name="API Preview Push-Up")

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
    db.commit()

    return {
        "owner": owner,
        "other": other,
        "exercise_id": exercise.id,
        "baseline_id": baseline.id,
        "first_id": first.id,
        "second_id": second.id,
    }


def authenticate(user):
    """Override identity for HTTP authorization tests."""
    app.dependency_overrides[get_current_user] = (
        lambda: user
    )


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
        user_id=data["owner"].id,
        program_instance_id=instance_id,
        program_slug="bw",
        program_week=week,
        program_day=day,
        source_baseline_id=data["baseline_id"],
        status=status,
        engine_version="test-v1",
    )

    prescription.sets.append(
        PrescriptionSet(
            exercise_id=data["exercise_id"],
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
        data["first_id"],
        week=2,
        reps=16,
    )

    db.add(
        AdaptationApproval(
            user_id=data["owner"].id,
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


def request_body(source_id, set_id):
    return {
        "prescription_id": source_id,
        "prescription_set_id": set_id,
        "adjustment_type": "reps",
        "previous_value": 15,
        "approved_value": 16,
    }


def post_preview(client, instance_id, body):
    return client.post(
        ENDPOINT.format(instance_id=instance_id),
        json=body,
    )


# --------------------------------------------------
# Route registration and authentication
# --------------------------------------------------

def test_route_is_registered():
    paths = {route.path for route in app.routes}

    assert (
        "/api/adaptations/program-instances/"
        "{program_instance_id}/preview"
    ) in paths


def test_authentication_required(client, data):
    response = post_preview(
        client,
        data["first_id"],
        request_body(1, 1),
    )

    assert response.status_code == 401


def test_invalid_enrollment_id_returns_422(
    client, data
):
    authenticate(data["owner"])

    response = post_preview(
        client,
        0,
        request_body(1, 1),
    )

    assert response.status_code == 422


def test_invalid_request_returns_422(client, data):
    authenticate(data["owner"])

    response = post_preview(
        client,
        data["first_id"],
        {
            "prescription_id": 1,
            "prescription_set_id": 1,
            "adjustment_type": "reps",
            "previous_value": 16,
            "approved_value": 15,
        },
    )

    assert response.status_code == 422


def test_extra_request_fields_rejected(client, data):
    authenticate(data["owner"])

    body = request_body(1, 1)
    body["user_id"] = data["other"].id

    response = post_preview(
        client,
        data["first_id"],
        body,
    )

    assert response.status_code == 422


# --------------------------------------------------
# Successful HTTP preview
# --------------------------------------------------

def test_valid_preview_returns_200(client, db, data):
    source_id, set_id = make_source(db, data)

    future_id, future_set_id = make_prescription(
        db,
        data,
        data["first_id"],
        week=3,
        reps=18,
    )

    authenticate(data["owner"])

    response = post_preview(
        client,
        data["first_id"],
        request_body(source_id, set_id),
    )

    assert response.status_code == 200, response.text

    result = response.json()

    assert result["user_id"] == data["owner"].id
    assert result["program_instance_id"] == (
        data["first_id"]
    )
    assert result["program_slug"] == "bw"
    assert result["source_prescription_id"] == source_id
    assert result["source_prescription_set_id"] == set_id
    assert result["adjustment_type"] == "reps"
    assert result["original_value"] == 15
    assert result["approved_value"] == 16
    assert result["delta"] == 1
    assert result["status"] == "review_required"
    assert result["database_modified"] is False

    assert len(result["candidates"]) == 1

    candidate = result["candidates"][0]

    assert candidate["prescription_id"] == future_id
    assert candidate["prescription_set_id"] == future_set_id
    assert candidate["current_value"] == 18
    assert candidate["proposed_value"] == 19
    assert candidate["phase_type"] == "training"
    assert candidate["requires_program_phase_review"] is True
    assert candidate["status"] == "review_required"


def test_other_enrollment_is_excluded(
    client, db, data
):
    source_id, set_id = make_source(db, data)

    included_id, _ = make_prescription(
        db, data, data["first_id"], week=3
    )

    excluded_id, _ = make_prescription(
        db, data, data["second_id"], week=3
    )

    authenticate(data["owner"])

    response = post_preview(
        client,
        data["first_id"],
        request_body(source_id, set_id),
    )

    assert response.status_code == 200, response.text

    candidates = {
        item["prescription_id"]
        for item in response.json()["candidates"]
    }

    assert candidates == {included_id}
    assert excluded_id not in candidates


def test_protected_phases_are_excluded(
    client, db, data
):
    source_id, set_id = make_source(db, data)

    make_prescription(
        db,
        data,
        data["first_id"],
        week=3,
        phase="deload",
    )

    make_prescription(
        db,
        data,
        data["first_id"],
        week=4,
        phase="assessment",
    )

    make_prescription(
        db,
        data,
        data["first_id"],
        week=5,
        phase=None,
    )

    authenticate(data["owner"])

    response = post_preview(
        client,
        data["first_id"],
        request_body(source_id, set_id),
    )

    assert response.status_code == 200, response.text

    result = response.json()

    assert result["candidates"] == []

    assert {
        item["reason"]
        for item in result["excluded"]
    } == {
        "deload_protected",
        "assessment_protected",
        "phase_unclassified",
    }


# --------------------------------------------------
# Enrollment access and lifecycle
# --------------------------------------------------

def test_other_user_returns_404(client, db, data):
    source_id, set_id = make_source(db, data)

    authenticate(data["other"])

    response = post_preview(
        client,
        data["first_id"],
        request_body(source_id, set_id),
    )

    assert response.status_code == 404


def test_wrong_source_enrollment_returns_404(
    client, db, data
):
    source_id, set_id = make_source(db, data)

    authenticate(data["owner"])

    response = post_preview(
        client,
        data["second_id"],
        request_body(source_id, set_id),
    )

    assert response.status_code == 404


@pytest.mark.parametrize(
    "status",
    ["completed", "abandoned"],
)
def test_inactive_enrollment_returns_409(
    client, db, data, status
):
    source_id, set_id = make_source(db, data)

    instance = db.get(
        ProgramInstance,
        data["first_id"],
    )
    instance.status = status
    db.commit()

    authenticate(data["owner"])

    response = post_preview(
        client,
        data["first_id"],
        request_body(source_id, set_id),
    )

    assert response.status_code == 409


def test_missing_approval_returns_409(
    client, db, data
):
    source_id, set_id = make_prescription(
        db,
        data,
        data["first_id"],
        week=2,
        reps=16,
    )

    authenticate(data["owner"])

    response = post_preview(
        client,
        data["first_id"],
        request_body(source_id, set_id),
    )

    assert response.status_code == 409


# --------------------------------------------------
# Read-only behavior
# --------------------------------------------------

def test_preview_does_not_modify_targets(
    client, db, data
):
    source_id, set_id = make_source(db, data)

    _, future_set_id = make_prescription(
        db,
        data,
        data["first_id"],
        week=3,
        reps=18,
    )

    authenticate(data["owner"])

    first = post_preview(
        client,
        data["first_id"],
        request_body(source_id, set_id),
    )

    second = post_preview(
        client,
        data["first_id"],
        request_body(source_id, set_id),
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json() == second.json()

    db.expire_all()

    stored = db.scalar(
        select(PrescriptionSet).where(
            PrescriptionSet.id == future_set_id
        )
    )

    assert stored.target_reps == 18
    assert not db.new
    assert not db.dirty
    assert not db.deleted