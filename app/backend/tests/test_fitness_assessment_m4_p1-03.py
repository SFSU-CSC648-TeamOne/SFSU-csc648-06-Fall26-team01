"""M4 / P1-03 Initial Fitness Assessment: unit and integration test.

Run from app/backend: python -m pytest tests/test_fitness_assessment_m4_p1-03.py -v

This uses the same standalone SQLite setup used by tests/test_progress_api.py.
Run in a fresh pytest process, because the database environment is set before
app imports. Do not run against the production database.
"""

import os
import tempfile
from unittest.mock import Mock
from uuid import uuid4

import pytest

# Initialize isolated database BEFORE importing application modules.
_test_dir = tempfile.mkdtemp(prefix="ascenda_m4_p103_")
os.environ["DATABASE_URL"] = f"sqlite:///{_test_dir}/test.db"
os.environ["JWT_SECRET"] = "test-secret-" + ("x" * 40)

from fastapi.testclient import TestClient

import app.models  # register mapped models with SQLAlchemy
from app.api.routes.program_baselines import BaselineIn, create_baseline
from app.core.errors import ValidationFailed
from app.db.base import Base
from app.db.session import engine
from app.main import app

Base.metadata.create_all(engine)
client = TestClient(app)


def test_p103_unit_rejects_duplicate_required_exercise():
    """UT-P103-01: reject invalid baseline before writing to DB."""
    body = BaselineIn(
        program_slug="bw",
        results=[
            {"exercise_id": "push-up", "value": 12},
            {"exercise_id": "push-up", "value": 15},
            {"exercise_id": "plank", "value": 30},
        ],
    )
    db = Mock()
    user = Mock(id=101)

    with pytest.raises(ValidationFailed, match="exactly one result"):
        create_baseline(body=body, user=user, db=db)

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_p103_integration_post_baseline_then_get_latest():
    """IT-P103-01: auth -> FastAPI -> validation -> SQLAlchemy -> retrieval."""
    registration = client.post(
        "/api/auth/register",
        json={
            "email": f"p103-{uuid4().hex}@example.com",
            "password": "password123",
            "display_name": "M4 Baseline Tester",
        },
    )
    assert registration.status_code == 201, registration.text
    headers = {"Authorization": f"Bearer {registration.json()['access_token']}"}

    results = [
        {"exercise_id": "push-up", "value": 12, "load_kg": None},
        {"exercise_id": "bodyweight-squat", "value": 20, "load_kg": None},
        {"exercise_id": "plank", "value": 45, "load_kg": None},
    ]
    saved = client.post(
        "/api/program-baselines",
        headers=headers,
        json={"program_slug": "bw", "results": results},
    )
    assert saved.status_code == 201, saved.text
    saved_body = saved.json()
    assert saved_body["program_slug"] == "bw"
    assert saved_body["results"] == results
    assert saved_body["id"] > 0
    assert saved_body["attempt_id"]

    latest = client.get(
        "/api/program-baselines/latest",
        headers=headers,
        params={"program": "bw"},
    )
    assert latest.status_code == 200, latest.text
    latest_body = latest.json()
    assert latest_body["id"] == saved_body["id"]
    assert latest_body["attempt_id"] == saved_body["attempt_id"]
    assert latest_body["results"] == results

