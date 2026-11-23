"""Tests for authenticated bodyweight measurements.

Run independently:
    python -m pytest tests/test_bodyweight.py -v
"""

import os
import tempfile
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

# Configure an isolated test database before importing the app.
_test_dir = tempfile.mkdtemp(prefix="ascenda_bodyweight_")

os.environ["DATABASE_URL"] = f"sqlite:///{_test_dir}/test.db"
os.environ["JWT_SECRET"] = "test-secret-" + ("x" * 40)

from fastapi.testclient import TestClient

import app.models
from app.db.base import Base
from app.db.session import engine
from app.main import app

Base.metadata.create_all(engine)

client = TestClient(app)

ENDPOINT = "/api/bodyweight-measurements"
LA = ZoneInfo("America/Los_Angeles")


def register_user():
    email = f"bodyweight-{uuid4().hex}@example.com"

    response = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "password123",
            "display_name": "Test User",
        },
    )

    assert response.status_code == 201, response.text

    token = response.json()["access_token"]

    return {"Authorization": f"Bearer {token}"}


def test_create_current_measurement():
    headers = register_user()

    now = datetime.now(timezone.utc)
    local_date = now.astimezone(LA).date().isoformat()

    response = client.post(
        ENDPOINT,
        headers=headers,
        json={
            "weight_kg": 82.5,
            "measurement_date": local_date,
            "timezone": "America/Los_Angeles",
            "measured_at": now.isoformat(),
        },
    )

    assert response.status_code == 201, response.text

    result = response.json()

    assert float(result["weight_kg"]) == 82.5
    assert result["measurement_date"] == local_date
    assert result["timezone"] == "America/Los_Angeles"
    assert result["measured_at"] is not None
    assert result["id"] > 0


def test_historical_measurement_without_time():
    headers = register_user()

    historical_date = (datetime.now(LA).date() - timedelta(days=7)).isoformat()

    response = client.post(
        ENDPOINT,
        headers=headers,
        json={
            "weight_kg": 80.25,
            "measurement_date": historical_date,
            "timezone": "America/Los_Angeles",
            "measured_at": None,
        },
    )

    assert response.status_code == 201, response.text

    result = response.json()

    assert result["measurement_date"] == historical_date
    assert result["measured_at"] is None


def test_reject_invalid_weight():
    headers = register_user()

    today = datetime.now(LA).date().isoformat()

    for weight in [-5, 0, 601]:
        response = client.post(
            ENDPOINT,
            headers=headers,
            json={
                "weight_kg": weight,
                "measurement_date": today,
                "timezone": "America/Los_Angeles",
                "measured_at": None,
            },
        )

        assert response.status_code == 422, response.text


def test_reject_invalid_timezone():
    headers = register_user()

    response = client.post(
        ENDPOINT,
        headers=headers,
        json={
            "weight_kg": 80,
            "measurement_date": (datetime.now(LA).date().isoformat()),
            "timezone": "Not/A_Timezone",
            "measured_at": None,
        },
    )

    assert response.status_code == 422, response.text


def test_reject_future_date():
    headers = register_user()

    tomorrow = (datetime.now(LA).date() + timedelta(days=1)).isoformat()

    response = client.post(
        ENDPOINT,
        headers=headers,
        json={
            "weight_kg": 80,
            "measurement_date": tomorrow,
            "timezone": "America/Los_Angeles",
            "measured_at": None,
        },
    )

    assert response.status_code == 422, response.text


def test_reject_timestamp_date_mismatch():
    headers = register_user()

    now = datetime.now(timezone.utc)
    wrong_date = (now.astimezone(LA).date() - timedelta(days=1)).isoformat()

    response = client.post(
        ENDPOINT,
        headers=headers,
        json={
            "weight_kg": 80,
            "measurement_date": wrong_date,
            "timezone": "America/Los_Angeles",
            "measured_at": now.isoformat(),
        },
    )

    assert response.status_code == 422, response.text


def test_user_isolation():
    user_a = register_user()
    user_b = register_user()

    today = datetime.now(LA).date().isoformat()

    created = client.post(
        ENDPOINT,
        headers=user_a,
        json={
            "weight_kg": 85,
            "measurement_date": today,
            "timezone": "America/Los_Angeles",
            "measured_at": None,
        },
    )

    assert created.status_code == 201, created.text

    measurement_id = created.json()["id"]

    history_a = client.get(ENDPOINT, headers=user_a)
    history_b = client.get(ENDPOINT, headers=user_b)

    assert history_a.status_code == 200
    assert history_b.status_code == 200

    assert measurement_id in [item["id"] for item in history_a.json()]

    assert measurement_id not in [item["id"] for item in history_b.json()]


def test_authentication_required():
    post_response = client.post(
        ENDPOINT,
        json={
            "weight_kg": 80,
            "measurement_date": (datetime.now(LA).date().isoformat()),
            "timezone": "America/Los_Angeles",
            "measured_at": None,
        },
    )

    get_response = client.get(ENDPOINT)

    assert post_response.status_code == 401
    assert get_response.status_code == 401
