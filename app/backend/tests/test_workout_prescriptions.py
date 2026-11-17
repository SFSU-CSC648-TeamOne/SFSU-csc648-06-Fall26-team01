
"""Tests for prescription-linked workout performance.

Run independently:
    python -m pytest tests/test_workout_prescriptions.py -v
"""

import os
import tempfile
from uuid import uuid4

# Configure testing before importing the application.
_test_dir = tempfile.mkdtemp(prefix="ascenda_prescription_")
os.environ["DATABASE_URL"] = f"sqlite:///{_test_dir}/test.db"
os.environ["JWT_SECRET"] = "test-secret-" + ("x" * 40)

import pytest
from fastapi.testclient import TestClient

import app.models
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app
from app.models import Exercise
from app.models.prescription import (
    PrescriptionSet,
    WorkoutPrescription,
)

Base.metadata.create_all(engine)

client = TestClient(app)
ENDPOINT = "/api/workout-records"


def register_user():
    response = client.post(
        "/api/auth/register",
        json={
            "email": f"training-{uuid4().hex}@example.com",
            "password": "password123",
            "display_name": "Training Tester",
        },
    )
    assert response.status_code == 201, response.text

    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_fixture(headers):
    """Create a prescription owned by the signed-in user."""
    user_response = client.get("/api/auth/me", headers=headers)
    assert user_response.status_code == 200
    user_id = user_response.json()["id"]

    with SessionLocal() as db:
        exercise = Exercise(
            name=f"Test Push-Up {uuid4().hex[:8]}"
        )
        alternative = Exercise(
            name=f"Test Incline Push-Up {uuid4().hex[:8]}"
        )
        db.add_all([exercise, alternative])
        db.flush()

        prescription = WorkoutPrescription(
            user_id=user_id,
            program_slug="bw",
            program_week=1,
            program_day=1,
            engine_version="test-1",
            status="planned",
        )
        db.add(prescription)
        db.flush()

        target = PrescriptionSet(
            workout_prescription_id=prescription.id,
            exercise_id=exercise.id,
            set_number=1,
            target_reps=10,
            load_basis="bodyweight",
            is_optional=False,
        )
        db.add(target)
        db.commit()

        return {
            "exercise_id": exercise.id,
            "alternative_id": alternative.id,
            "prescription_set_id": target.id,
        }


def entry(fixture, **changes):
    data = {
        "exercise_id": fixture["exercise_id"],
        "set_number": 1,
        "reps": 8,
        "weight_kg": None,
        "status": "completed",
        "prescription_set_id": fixture["prescription_set_id"],
        "observation_type": "training",
        "load_basis": "bodyweight",
        "assistance_kg": None,
        "is_user_modified": False,
    }
    data.update(changes)
    return data


def submit(headers, entries, **changes):
    payload = {
        "program_slug": "bw",
        "program_week": 1,
        "program_day": 1,
        "entries": entries,
    }
    payload.update(changes)

    return client.post(
        ENDPOINT,
        json=payload,
        headers=headers,
    )


def test_valid_prescription_submission():
    headers = register_user()
    fixture = create_fixture(headers)

    response = submit(headers, [entry(fixture)])

    assert response.status_code == 201, response.text

    saved = response.json()["entries"][0]

    assert saved["reps"] == 8
    assert saved["set_number"] == 1
    assert saved["prescription_set_id"] == (
        fixture["prescription_set_id"]
    )
    assert saved["observation_type"] == "training"
    assert saved["load_basis"] == "bodyweight"


def test_reject_other_users_prescription():
    owner = register_user()
    attacker = register_user()
    fixture = create_fixture(owner)

    response = submit(attacker, [entry(fixture)])

    assert response.status_code == 422, response.text


def test_reject_wrong_exercise():
    headers = register_user()
    fixture = create_fixture(headers)

    response = submit(
        headers,
        [
            entry(
                fixture,
                exercise_id=fixture["alternative_id"],
            )
        ],
    )

    assert response.status_code == 422, response.text


@pytest.mark.parametrize(
    "change",
    [
        {"program_slug": "ldw"},
        {"program_week": 2},
        {"program_day": 2},
    ],
)
def test_reject_wrong_program_day(change):
    headers = register_user()
    fixture = create_fixture(headers)

    response = submit(
        headers,
        [entry(fixture)],
        **change,
    )

    assert response.status_code == 422, response.text


def test_reject_wrong_set_number():
    headers = register_user()
    fixture = create_fixture(headers)

    response = submit(
        headers,
        [entry(fixture, set_number=2)],
    )

    assert response.status_code == 422, response.text


def test_reject_skipped_set_with_reps():
    headers = register_user()
    fixture = create_fixture(headers)

    response = submit(
        headers,
        [
            entry(
                fixture,
                status="skipped",
                reps=5,
            )
        ],
    )

    assert response.status_code == 422, response.text


def test_accept_skipped_set_without_performance():
    headers = register_user()
    fixture = create_fixture(headers)

    response = submit(
        headers,
        [
            entry(
                fixture,
                status="skipped",
                reps=None,
                weight_kg=None,
            )
        ],
    )

    assert response.status_code == 201, response.text

    saved = response.json()["entries"][0]
    assert saved["status"] == "skipped"
    assert saved["reps"] is None


def test_reject_assistance_without_assisted_basis():
    headers = register_user()
    fixture = create_fixture(headers)

    response = submit(
        headers,
        [entry(fixture, assistance_kg=10)],
    )

    assert response.status_code == 422, response.text


def test_accept_assisted_loading():
    headers = register_user()
    fixture = create_fixture(headers)

    response = submit(
        headers,
        [
            entry(
                fixture,
                load_basis="assisted",
                assistance_kg=10,
            )
        ],
    )

    assert response.status_code == 201, response.text

    saved = response.json()["entries"][0]
    assert saved["assistance_kg"] == 10
    assert saved["load_basis"] == "assisted"


def test_substitution_preserves_original():
    headers = register_user()
    fixture = create_fixture(headers)

    response = submit(
        headers,
        [
            entry(
                fixture,
                exercise_id=fixture["alternative_id"],
                substituted_for_exercise_id=(
                    fixture["exercise_id"]
                ),
                is_user_modified=True,
            )
        ],
    )

    assert response.status_code == 201, response.text

    saved = response.json()["entries"][0]

    assert saved["exercise_id"] == fixture["alternative_id"]
    assert saved["substituted_for_exercise_id"] == (
        fixture["exercise_id"]
    )
    assert saved["is_user_modified"] is True


def test_reject_duplicate_prescription_in_one_workout():
    headers = register_user()
    fixture = create_fixture(headers)

    response = submit(
        headers,
        [entry(fixture), entry(fixture)],
    )

    assert response.status_code == 422, response.text


def test_unlinked_workout_remains_supported():
    headers = register_user()
    fixture = create_fixture(headers)

    response = submit(
        headers,
        [
            {
                "exercise_id": fixture["exercise_id"],
                "set_number": 1,
                "reps": 7,
                "status": "completed",
            }
        ],
    )

    assert response.status_code == 201, response.text
    assert response.json()["entries"][0]["reps"] == 7


def test_history_returns_saved_metadata():
    headers = register_user()
    fixture = create_fixture(headers)

    created = submit(headers, [entry(fixture)])

    assert created.status_code == 201, created.text

    record_id = created.json()["id"]

    history = client.get(
        f"{ENDPOINT}/{record_id}",
        headers=headers,
    )

    assert history.status_code == 200, history.text

    saved = history.json()["entries"][0]

    assert saved["prescription_set_id"] == (
        fixture["prescription_set_id"]
    )
    assert saved["observation_type"] == "training"
    assert saved["load_basis"] == "bodyweight"
    assert saved["is_user_modified"] is False
