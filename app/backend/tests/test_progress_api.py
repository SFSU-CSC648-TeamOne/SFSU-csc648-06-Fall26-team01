
"""Integration tests for the authenticated progress API.

Run independently:
    python -m pytest tests/test_progress_api.py -v
"""

import os
import tempfile
from datetime import datetime, timedelta, timezone
from uuid import uuid4

# Configure an isolated test database before app imports.
_test_dir = tempfile.mkdtemp(prefix="ascenda_progress_api_")
os.environ["DATABASE_URL"] = f"sqlite:///{_test_dir}/test.db"
os.environ["JWT_SECRET"] = "test-secret-" + ("x" * 40)

import pytest
from fastapi.testclient import TestClient

import app.models
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app
from app.models import Exercise, PerformanceEntry, WorkoutRecord

Base.metadata.create_all(engine)

client = TestClient(app)
ENDPOINT = "/api/progress/exercises"


def register_user():
    response = client.post(
        "/api/auth/register",
        json={
            "email": f"progress-{uuid4().hex}@example.com",
            "password": "password123",
            "display_name": "Progress Tester",
        },
    )

    assert response.status_code == 201, response.text

    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200, me.text

    return headers, me.json()["id"]


def create_exercise():
    with SessionLocal() as db:
        exercise = Exercise(
            name=f"Progress Test {uuid4().hex[:8]}"
        )

        db.add(exercise)
        db.commit()

        return exercise.id


def add_workout(
    user_id,
    exercise_id,
    *,
    day=0,
    reps=10,
    set_number=1,
    status="completed",
    observation_type="training",
    load_basis="bodyweight",
    weight_kg=None,
):
    with SessionLocal() as db:
        record = WorkoutRecord(
            user_id=user_id,
            performed_at=(
                datetime(2026, 1, 1, tzinfo=timezone.utc)
                + timedelta(days=day)
            ),
        )

        entry = PerformanceEntry(
            exercise_id=exercise_id,
            set_number=set_number,
            reps=reps if status == "completed" else None,
            weight_kg=(
                weight_kg if status == "completed" else None
            ),
            status=status,
            observation_type=observation_type,
            load_basis=load_basis,
        )

        record.entries.append(entry)
        db.add(record)
        db.commit()


def get_progress(headers, exercise_id, **params):
    return client.get(
        f"{ENDPOINT}/{exercise_id}",
        headers=headers,
        params=params,
    )


def test_route_registered():
    paths = {route.path for route in app.routes}

    assert (
        "/api/progress/exercises/{exercise_id}"
        in paths
    )


def test_authentication_required():
    exercise_id = create_exercise()

    response = client.get(
        f"{ENDPOINT}/{exercise_id}"
    )

    assert response.status_code == 401


def test_invalid_token_rejected():
    exercise_id = create_exercise()

    response = get_progress(
        {"Authorization": "Bearer invalid-token"},
        exercise_id,
    )

    assert response.status_code == 401


def test_empty_progress_history():
    headers, _ = register_user()
    exercise_id = create_exercise()

    response = get_progress(headers, exercise_id)

    assert response.status_code == 200, response.text
    assert response.json() == {
        "exercise_id": exercise_id,
        "observation_type": "training",
        "trends": [],
    }


def test_invalid_exercise_id():
    headers, _ = register_user()

    response = get_progress(headers, 0)

    assert response.status_code == 422


def test_invalid_observation_type():
    headers, _ = register_user()
    exercise_id = create_exercise()

    response = get_progress(
        headers,
        exercise_id,
        observation_type="invalid",
    )

    assert response.status_code == 422


def test_preliminary_progress_response():
    headers, user_id = register_user()
    exercise_id = create_exercise()

    for day, reps in enumerate([8, 10, 12]):
        add_workout(
            user_id,
            exercise_id,
            day=day,
            reps=reps,
        )

    response = get_progress(headers, exercise_id)

    assert response.status_code == 200, response.text

    body = response.json()

    assert body["exercise_id"] == exercise_id
    assert body["observation_type"] == "training"
    assert len(body["trends"]) == 1

    trend = body["trends"][0]

    assert trend["observation_count"] == 3
    assert trend["confidence"] == "preliminary"
    assert trend["metric"] == "reps"
    assert trend["load_basis"] == "bodyweight"
    assert trend["change_pct"] == 50.0

    assert [
        point["actual"]
        for point in trend["points"]
    ] == [8, 10, 12]


def test_robust_progress_response():
    headers, user_id = register_user()
    exercise_id = create_exercise()

    for day, reps in enumerate([8, 9, 9, 11, 12]):
        add_workout(
            user_id,
            exercise_id,
            day=day,
            reps=reps,
        )

    response = get_progress(headers, exercise_id)

    assert response.status_code == 200, response.text

    trend = response.json()["trends"][0]

    assert trend["observation_count"] == 5
    assert trend["confidence"] == "robust"
    assert trend["slope_per_observation"] == pytest.approx(1.0)
    assert trend["change_pct"] == pytest.approx(50.0)


def test_user_isolation():
    owner_headers, owner_id = register_user()
    other_headers, other_id = register_user()

    exercise_id = create_exercise()

    for day, reps in enumerate([8, 10, 12]):
        add_workout(
            owner_id,
            exercise_id,
            day=day,
            reps=reps,
        )

    add_workout(
        other_id,
        exercise_id,
        day=4,
        reps=100,
    )

    owner_response = get_progress(
        owner_headers,
        exercise_id,
    )
    other_response = get_progress(
        other_headers,
        exercise_id,
    )

    assert owner_response.status_code == 200
    assert other_response.status_code == 200

    owner_trend = owner_response.json()["trends"][0]
    other_trend = other_response.json()["trends"][0]

    assert owner_trend["observation_count"] == 3
    assert other_trend["observation_count"] == 1

    assert [
        point["actual"]
        for point in owner_trend["points"]
    ] == [8, 10, 12]

    assert other_trend["points"][0]["actual"] == 100


def test_benchmarks_separate_from_training():
    headers, user_id = register_user()
    exercise_id = create_exercise()

    for day in range(3):
        add_workout(
            user_id,
            exercise_id,
            day=day,
            reps=10 + day,
        )

    add_workout(
        user_id,
        exercise_id,
        day=4,
        reps=20,
        observation_type="benchmark",
    )

    training = get_progress(
        headers,
        exercise_id,
        observation_type="training",
    )

    benchmark = get_progress(
        headers,
        exercise_id,
        observation_type="benchmark",
    )

    assert training.status_code == 200
    assert benchmark.status_code == 200

    training_trend = training.json()["trends"][0]
    benchmark_trend = benchmark.json()["trends"][0]

    assert training_trend["observation_count"] == 3
    assert benchmark_trend["observation_count"] == 1

    assert benchmark_trend["confidence"] == "insufficient"


def test_skipped_sets_excluded():
    headers, user_id = register_user()
    exercise_id = create_exercise()

    add_workout(
        user_id, exercise_id,
        day=0, reps=8,
    )

    add_workout(
        user_id, exercise_id,
        day=1, reps=10,
    )

    add_workout(
        user_id, exercise_id,
        day=2, status="skipped",
    )

    response = get_progress(headers, exercise_id)

    assert response.status_code == 200, response.text

    trend = response.json()["trends"][0]

    assert trend["observation_count"] == 2
    assert trend["confidence"] == "insufficient"


def test_external_loads_remain_separate():
    headers, user_id = register_user()
    exercise_id = create_exercise()

    for day in range(3):
        add_workout(
            user_id,
            exercise_id,
            day=day,
            reps=8 + day,
            load_basis="external",
            weight_kg=20,
        )

    add_workout(
        user_id,
        exercise_id,
        day=4,
        reps=6,
        load_basis="external",
        weight_kg=40,
    )

    response = get_progress(headers, exercise_id)

    assert response.status_code == 200, response.text

    trends = response.json()["trends"]

    assert len(trends) == 2

    by_weight = {
        trend["weight_kg"]: trend
        for trend in trends
    }

    assert by_weight[20]["observation_count"] == 3
    assert by_weight[40]["observation_count"] == 1
