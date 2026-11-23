
"""HTTP integration tests for the adaptive recommendations API.

Run from app/backend:
    python -m pytest tests/test_adaptations_api.py -v

Uses isolated SQLite, not Supabase.
No production data is modified.
"""

from decimal import Decimal

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
from app.models import (
    Exercise,
    PrescriptionSet,
    User,
    WorkoutPrescription,
)
from app.services import prescription_adaptation as service


ENDPOINT = "/api/adaptations/prescriptions"


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
        email="api-adapt-owner@example.com",
        password_hash="test-hash",
    )

    other = User(
        email="api-adapt-other@example.com",
        password_hash="test-hash",
    )

    exercise = Exercise(name="API Adaptation Push-Up")

    db.add_all([owner, other, exercise])
    db.commit()

    return {
        "owner": owner,
        "other": other,
        "exercise": exercise,
    }


@pytest.fixture
def client(db):
    """Override the database dependency for every request."""

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def authenticate(user):
    """Simulate an authenticated user for API integration tests."""

    app.dependency_overrides[get_current_user] = (
        lambda: user
    )


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
        program_week=2,
        program_day=1,
        status=status,
        engine_version="baseline-v1",
    )

    prescription.sets.append(
        PrescriptionSet(
            exercise_id=exercise.id,
            set_number=1,
            target_reps=reps,
            target_weight_kg=(
                Decimal(str(weight))
                if weight is not None
                else None
            ),
            load_basis=load_basis,
        )
    )

    db.add(prescription)
    db.commit()

    return prescription


def make_trend(exercise_id, *, change_pct=15.0):
    """Create a robust comparable training trend."""

    return {
        "exercise_id": exercise_id,
        "observation_type": "training",
        "set_number": 1,
        "metric": "reps",
        "load_basis": "bodyweight",
        "weight_kg": None,
        "assistance_kg": None,
        "observation_count": 5,
        "confidence": "robust",
        "change_pct": change_pct,
        "points": [
            {
                "date": f"2026-11-{i + 1:02d}",
                "prescribed": 15,
                "actual": 15 + i,
            }
            for i in range(5)
        ],
    }


def mock_history(monkeypatch, trends):
    """Replace historical analysis, not the API or decision engine."""

    def fake_analysis(
        db,
        user_id,
        exercise_id,
        observation_type,
    ):
        assert observation_type == "training"

        return [
            trend
            for trend in trends
            if trend["exercise_id"] == exercise_id
        ]

    monkeypatch.setattr(
        service,
        "analyze_exercise_progress",
        fake_analysis,
    )


def get_adaptations(client, prescription_id):
    return client.get(
        f"{ENDPOINT}/{prescription_id}"
    )


# --------------------------------------------------
# Route and authentication
# --------------------------------------------------

def test_route_is_registered():
    routes = {
        route.path
        for route in app.routes
    }

    assert (
        "/api/adaptations/prescriptions/{prescription_id}"
        in routes
    )


def test_authentication_required(client):
    response = get_adaptations(client, 1)

    assert response.status_code == 401


def test_invalid_prescription_id_rejected(
    client, data
):
    authenticate(data["owner"])

    response = get_adaptations(client, 0)

    assert response.status_code == 422


def test_non_numeric_prescription_id_rejected(
    client, data
):
    authenticate(data["owner"])

    response = get_adaptations(client, "invalid")

    assert response.status_code == 422


# --------------------------------------------------
# Successful adaptation responses
# --------------------------------------------------

def test_valid_prescription_returns_200(
    client, db, data, monkeypatch
):
    prescription = create_prescription(
        db,
        data["owner"],
        data["exercise"],
    )

    mock_history(monkeypatch, [
        make_trend(data["exercise"].id)
    ])

    authenticate(data["owner"])

    response = get_adaptations(
        client,
        prescription.id,
    )

    assert response.status_code == 200, response.text

    result = response.json()

    assert result["prescription_id"] == prescription.id
    assert result["user_id"] == data["owner"].id
    assert result["program_slug"] == "bw"
    assert result["program_week"] == 2
    assert result["program_day"] == 1
    assert result["status"] == "proposed"

    assert result["source_engine_version"] == (
        "baseline-v1"
    )

    assert result["proposal_engine_version"] == (
        "adaptive-v1-proposal"
    )


def test_response_contains_progression_proposal(
    client, db, data, monkeypatch
):
    prescription = create_prescription(
        db,
        data["owner"],
        data["exercise"],
        reps=15,
    )

    mock_history(monkeypatch, [
        make_trend(data["exercise"].id)
    ])

    authenticate(data["owner"])

    response = get_adaptations(
        client,
        prescription.id,
    )

    assert response.status_code == 200, response.text

    result = response.json()

    assert len(result["sets"]) == 1

    item = result["sets"][0]

    assert item["exercise_id"] == data["exercise"].id
    assert item["set_number"] == 1

    assert item["decision"]["action"] == "progress"
    assert item["decision"]["confidence"] == "robust"
    assert item["decision"]["observation_count"] == 5

    proposal = item["proposal"]

    assert proposal["adjustment_type"] == "reps"
    assert proposal["previous_value"] == 15
    assert proposal["proposed_value"] == 16
    assert proposal["requires_approval"] is True

    assert isinstance(proposal["reason"], str)
    assert len(proposal["reason"]) > 0


def test_no_history_returns_no_adjustment(
    client, db, data, monkeypatch
):
    prescription = create_prescription(
        db,
        data["owner"],
        data["exercise"],
    )

    mock_history(monkeypatch, [])
    authenticate(data["owner"])

    response = get_adaptations(
        client,
        prescription.id,
    )

    assert response.status_code == 200, response.text

    item = response.json()["sets"][0]

    assert item["decision"]["action"] == (
        "insufficient_data"
    )

    assert item["proposal"]["adjustment_type"] == "none"
    assert item["proposal"]["requires_approval"] is False


def test_negative_trend_never_reduces_target(
    client, db, data, monkeypatch
):
    prescription = create_prescription(
        db,
        data["owner"],
        data["exercise"],
        reps=15,
    )

    mock_history(monkeypatch, [
        make_trend(
            data["exercise"].id,
            change_pct=-10.0,
        )
    ])

    authenticate(data["owner"])

    response = get_adaptations(
        client,
        prescription.id,
    )

    assert response.status_code == 200, response.text

    item = response.json()["sets"][0]

    assert item["decision"]["action"] == (
        "review_regression"
    )

    assert item["proposal"]["adjustment_type"] == "none"
    assert item["proposal"]["proposed_value"] is None


# --------------------------------------------------
# Ownership and lifecycle protection
# --------------------------------------------------

def test_other_user_prescription_returns_404(
    client, db, data, monkeypatch
):
    prescription = create_prescription(
        db,
        data["owner"],
        data["exercise"],
    )

    mock_history(monkeypatch, [])

    authenticate(data["other"])

    response = get_adaptations(
        client,
        prescription.id,
    )

    assert response.status_code == 404


def test_unknown_prescription_returns_404(
    client, data, monkeypatch
):
    mock_history(monkeypatch, [])

    authenticate(data["owner"])

    response = get_adaptations(
        client,
        999999,
    )

    assert response.status_code == 404


@pytest.mark.parametrize("status", [
    "completed",
    "skipped",
])
def test_non_planned_prescription_returns_409(
    client, db, data, monkeypatch, status
):
    prescription = create_prescription(
        db,
        data["owner"],
        data["exercise"],
        status=status,
    )

    mock_history(monkeypatch, [])

    authenticate(data["owner"])

    response = get_adaptations(
        client,
        prescription.id,
    )

    assert response.status_code == 409


# --------------------------------------------------
# Read-only guarantees
# --------------------------------------------------

def test_api_does_not_modify_prescription(
    client, db, data, monkeypatch
):
    prescription = create_prescription(
        db,
        data["owner"],
        data["exercise"],
        reps=15,
    )

    set_id = prescription.sets[0].id

    mock_history(monkeypatch, [
        make_trend(data["exercise"].id)
    ])

    authenticate(data["owner"])

    response = get_adaptations(
        client,
        prescription.id,
    )

    assert response.status_code == 200, response.text
    assert (
        response.json()["sets"][0]["proposal"][
            "proposed_value"
        ]
        == 16
    )

    db.expire_all()

    stored_set = db.scalar(
        select(PrescriptionSet).where(
            PrescriptionSet.id == set_id
        )
    )

    stored_prescription = db.get(
        WorkoutPrescription,
        prescription.id,
    )

    assert stored_set.target_reps == 15
    assert stored_prescription.status == "planned"
    assert stored_prescription.engine_version == "baseline-v1"

    assert not db.new
    assert not db.dirty
    assert not db.deleted


def test_repeated_requests_are_read_only(
    client, db, data, monkeypatch
):
    prescription = create_prescription(
        db,
        data["owner"],
        data["exercise"],
    )

    mock_history(monkeypatch, [
        make_trend(data["exercise"].id)
    ])

    authenticate(data["owner"])

    first = get_adaptations(client, prescription.id)
    second = get_adaptations(client, prescription.id)

    assert first.status_code == 200
    assert second.status_code == 200

    assert first.json() == second.json()

    stored = db.get(
        WorkoutPrescription,
        prescription.id,
    )

    assert stored.status == "planned"
    assert stored.sets[0].target_reps == 15
