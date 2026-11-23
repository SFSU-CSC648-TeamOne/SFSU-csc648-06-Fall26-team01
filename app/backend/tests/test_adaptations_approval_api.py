"""HTTP integration tests for adaptation approvals.

Run from app/backend:
    python -m pytest tests/test_adaptations_approval_api.py -v

Uses an isolated SQLite database.
Does not connect to Supabase.
"""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.models

from app.api.deps import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.main import app

from app.models import (
    Exercise,
    PrescriptionSet,
    User,
    WorkoutPrescription,
    WorkoutRecord,
)
from app.services import approve_adaptation as service
from app.services.prescription_adaptation import ENGINE_VERSION

API = "/api/adaptations/prescriptions"


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
        email="approval-api-owner@example.com",
        password_hash="test-hash",
    )
    other = User(
        email="approval-api-other@example.com",
        password_hash="test-hash",
    )
    exercise = Exercise(name="Approval API Push-Up")

    db.add_all([owner, other, exercise])
    db.commit()

    return {
        "owner": owner,
        "other": other,
        "exercise": exercise,
    }


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


def authenticate(user):
    app.dependency_overrides[get_current_user] = lambda: user


def create_prescription(
    db,
    user,
    exercise,
    *,
    status="planned",
    reps=15,
    load_basis="bodyweight",
    weight=None,
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


def mock_recommendation(
    monkeypatch,
    set_id,
    *,
    previous=15,
    proposed=16,
    adjustment_type="reps",
    action="progress",
):
    """Mock recalculated proposals, not the approval service."""

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
                        "action": action,
                    },
                    "proposal": {
                        "adjustment_type": adjustment_type,
                        "previous_value": previous,
                        "proposed_value": proposed,
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


def approval_body(
    set_id,
    *,
    previous=15,
    proposed=16,
    adjustment_type="reps",
):
    return {
        "approvals": [
            {
                "prescription_set_id": set_id,
                "adjustment_type": adjustment_type,
                "expected_previous_value": previous,
                "expected_proposed_value": proposed,
            }
        ]
    }


def post_approval(client, prescription_id, body):
    return client.post(
        f"{API}/{prescription_id}/approve",
        json=body,
    )


# --------------------------------------------------
# Route and authentication
# --------------------------------------------------


def test_approval_route_registered():
    routes = {route.path: route.methods for route in app.routes}

    path = "/api/adaptations/prescriptions/" "{prescription_id}/approve"

    assert path in routes
    assert "POST" in routes[path]


def test_authentication_required(client):
    response = post_approval(
        client,
        1,
        approval_body(1),
    )

    assert response.status_code == 401


def test_invalid_prescription_id(client, data):
    authenticate(data["owner"])

    response = post_approval(
        client,
        0,
        approval_body(1),
    )

    assert response.status_code == 422


def test_non_numeric_prescription_id(client, data):
    authenticate(data["owner"])

    response = post_approval(
        client,
        "invalid",
        approval_body(1),
    )

    assert response.status_code == 422


# --------------------------------------------------
# Successful approval
# --------------------------------------------------


def test_valid_approval_updates_prescription(client, db, data, monkeypatch):
    prescription = create_prescription(
        db,
        data["owner"],
        data["exercise"],
    )

    set_id = prescription.sets[0].id

    mock_recommendation(
        monkeypatch,
        set_id,
    )

    authenticate(data["owner"])

    response = post_approval(
        client,
        prescription.id,
        approval_body(set_id),
    )

    assert response.status_code == 200, response.text

    result = response.json()

    assert result["prescription_id"] == prescription.id
    assert result["status"] == "updated"
    assert result["updated_set_count"] == 1

    assert result["updated_sets"] == [
        {
            "prescription_set_id": set_id,
            "adjustment_type": "reps",
            "applied_value": 16,
        }
    ]

    db.expire_all()

    stored = db.get(PrescriptionSet, set_id)

    assert stored.target_reps == 16


def test_weight_approval_updates_resistance(client, db, data, monkeypatch):
    prescription = create_prescription(
        db,
        data["owner"],
        data["exercise"],
        reps=10,
        load_basis="external",
        weight="60",
    )

    set_id = prescription.sets[0].id

    mock_recommendation(
        monkeypatch,
        set_id,
        previous=60,
        proposed=61.5,
        adjustment_type="weight",
    )

    authenticate(data["owner"])

    response = post_approval(
        client,
        prescription.id,
        approval_body(
            set_id,
            previous=60,
            proposed=61.5,
            adjustment_type="weight",
        ),
    )

    assert response.status_code == 200, response.text

    db.expire_all()

    stored = db.get(PrescriptionSet, set_id)

    assert stored.target_weight_kg == Decimal("61.50")


# --------------------------------------------------
# Ownership and prescription status
# --------------------------------------------------


def test_other_user_cannot_approve(client, db, data, monkeypatch):
    prescription = create_prescription(
        db,
        data["owner"],
        data["exercise"],
    )

    set_id = prescription.sets[0].id

    mock_recommendation(
        monkeypatch,
        set_id,
    )

    authenticate(data["other"])

    response = post_approval(
        client,
        prescription.id,
        approval_body(set_id),
    )

    assert response.status_code == 404

    db.expire_all()

    assert (
        db.get(
            PrescriptionSet,
            set_id,
        ).target_reps
        == 15
    )


def test_unknown_prescription_returns_404(client, data):
    authenticate(data["owner"])

    response = post_approval(
        client,
        999999,
        approval_body(1),
    )

    assert response.status_code == 404


@pytest.mark.parametrize(
    "status",
    ["completed", "skipped"],
)
def test_non_planned_prescription_returns_409(client, db, data, status):
    prescription = create_prescription(
        db,
        data["owner"],
        data["exercise"],
        status=status,
    )

    authenticate(data["owner"])

    response = post_approval(
        client,
        prescription.id,
        approval_body(prescription.sets[0].id),
    )

    assert response.status_code == 409


# --------------------------------------------------
# Input validation
# --------------------------------------------------


def test_empty_approvals_rejected(client, data):
    authenticate(data["owner"])

    response = post_approval(
        client,
        1,
        {"approvals": []},
    )

    assert response.status_code == 422


def test_missing_approvals_rejected(client, data):
    authenticate(data["owner"])

    response = post_approval(
        client,
        1,
        {},
    )

    assert response.status_code == 422


def test_invalid_adjustment_type_rejected(client, data):
    authenticate(data["owner"])

    response = post_approval(
        client,
        1,
        approval_body(
            1,
            adjustment_type="assistance",
        ),
    )

    assert response.status_code == 422


def test_negative_set_id_rejected(client, data):
    authenticate(data["owner"])

    response = post_approval(
        client,
        1,
        approval_body(-1),
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "invalid_value",
    ["NaN", "Infinity", "-Infinity"],
)
def test_non_finite_values_rejected(client, data, invalid_value):
    authenticate(data["owner"])

    response = post_approval(
        client,
        1,
        approval_body(
            1,
            proposed=invalid_value,
        ),
    )

    assert response.status_code == 422


def test_duplicate_set_approvals_rejected(client, db, data):
    prescription = create_prescription(
        db,
        data["owner"],
        data["exercise"],
    )

    set_id = prescription.sets[0].id

    authenticate(data["owner"])

    item = approval_body(set_id)["approvals"][0]

    response = post_approval(
        client,
        prescription.id,
        {
            "approvals": [
                item,
                item,
            ]
        },
    )

    assert response.status_code == 422


# --------------------------------------------------
# Stale proposals
# --------------------------------------------------


def test_stale_proposal_returns_409(client, db, data, monkeypatch):
    prescription = create_prescription(
        db,
        data["owner"],
        data["exercise"],
    )

    set_id = prescription.sets[0].id

    mock_recommendation(
        monkeypatch,
        set_id,
        previous=15,
        proposed=16,
    )

    authenticate(data["owner"])

    response = post_approval(
        client,
        prescription.id,
        approval_body(
            set_id,
            previous=15,
            proposed=25,
        ),
    )

    assert response.status_code == 409

    db.expire_all()

    assert (
        db.get(
            PrescriptionSet,
            set_id,
        ).target_reps
        == 15
    )


def test_repeated_approval_returns_409(client, db, data, monkeypatch):
    prescription = create_prescription(
        db,
        data["owner"],
        data["exercise"],
    )

    set_id = prescription.sets[0].id

    mock_recommendation(
        monkeypatch,
        set_id,
    )

    authenticate(data["owner"])

    body = approval_body(set_id)

    first = post_approval(
        client,
        prescription.id,
        body,
    )

    second = post_approval(
        client,
        prescription.id,
        body,
    )

    assert first.status_code == 200
    assert second.status_code == 409

    db.expire_all()

    assert (
        db.get(
            PrescriptionSet,
            set_id,
        ).target_reps
        == 16
    )


# --------------------------------------------------
# Recorded workout protection
# --------------------------------------------------


def test_existing_workout_blocks_approval(client, db, data, monkeypatch):
    prescription = create_prescription(
        db,
        data["owner"],
        data["exercise"],
    )

    set_id = prescription.sets[0].id

    record = WorkoutRecord(
        user_id=data["owner"].id,
        program_slug="bw",
        program_week=3,
        program_day=1,
    )

    db.add(record)
    db.commit()

    mock_recommendation(
        monkeypatch,
        set_id,
    )

    authenticate(data["owner"])

    response = post_approval(
        client,
        prescription.id,
        approval_body(set_id),
    )

    assert response.status_code == 409

    db.expire_all()

    assert (
        db.get(
            PrescriptionSet,
            set_id,
        ).target_reps
        == 15
    )


# --------------------------------------------------
# Persistence and metadata integrity
# --------------------------------------------------


def test_approval_preserves_program_metadata(client, db, data, monkeypatch):
    prescription = create_prescription(
        db,
        data["owner"],
        data["exercise"],
    )

    set_id = prescription.sets[0].id

    mock_recommendation(
        monkeypatch,
        set_id,
    )

    authenticate(data["owner"])

    response = post_approval(
        client,
        prescription.id,
        approval_body(set_id),
    )

    assert response.status_code == 200, response.text

    db.expire_all()

    stored = db.get(
        WorkoutPrescription,
        prescription.id,
    )

    assert stored.program_slug == "bw"
    assert stored.program_week == 3
    assert stored.program_day == 1
    assert stored.status == "planned"
    assert stored.engine_version == "baseline-v1"


def test_approval_does_not_change_other_prescriptions(client, db, data, monkeypatch):
    first = create_prescription(
        db,
        data["owner"],
        data["exercise"],
    )

    second = create_prescription(
        db,
        data["other"],
        data["exercise"],
    )

    first_set_id = first.sets[0].id
    second_set_id = second.sets[0].id

    mock_recommendation(
        monkeypatch,
        first_set_id,
    )

    authenticate(data["owner"])

    response = post_approval(
        client,
        first.id,
        approval_body(first_set_id),
    )

    assert response.status_code == 200, response.text

    db.expire_all()

    assert (
        db.get(
            PrescriptionSet,
            first_set_id,
        ).target_reps
        == 16
    )

    assert (
        db.get(
            PrescriptionSet,
            second_set_id,
        ).target_reps
        == 15
    )
