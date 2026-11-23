"""Integration tests for the movement-group progress API.

Run independently:
    python -m pytest tests/test_movement_group_api.py -v
"""

import os
import tempfile
from datetime import datetime, timedelta, timezone
from uuid import uuid4

# Configure test database before importing the app.
_test_dir = tempfile.mkdtemp(prefix="ascenda_group_api_")
os.environ["DATABASE_URL"] = f"sqlite:///{_test_dir}/test.db"
os.environ["JWT_SECRET"] = "test-secret-" + ("x" * 40)

import pytest
from fastapi.testclient import TestClient

import app.models
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app
from app.models import (
    Exercise,
    ExerciseMovementGroup,
    MovementGroup,
    PerformanceEntry,
    WorkoutRecord,
)

Base.metadata.create_all(engine)

client = TestClient(app)
ENDPOINT = "/api/progress/movement-groups"


def register_user():
    response = client.post(
        "/api/auth/register",
        json={
            "email": f"group-{uuid4().hex}@example.com",
            "password": "password123",
            "display_name": "Group Tester",
        },
    )
    assert response.status_code == 201, response.text

    headers = {"Authorization": (f"Bearer {response.json()['access_token']}")}

    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200, me.text

    return headers, me.json()["id"]


def create_group(
    *,
    group_name=None,
    exercise_name=None,
    relationship_type="primary",
    relevance_weight=1.0,
):
    """Create one movement group and linked exercise."""
    with SessionLocal() as db:
        group = MovementGroup(name=group_name or f"Group {uuid4().hex[:8]}")
        exercise = Exercise(name=exercise_name or f"Exercise {uuid4().hex[:8]}")

        db.add_all([group, exercise])
        db.flush()

        db.add(
            ExerciseMovementGroup(
                exercise_id=exercise.id,
                movement_group_id=group.id,
                relationship_type=relationship_type,
                relevance_weight=relevance_weight,
            )
        )

        group_id = group.id
        exercise_id = exercise.id
        db.commit()

        return group_id, exercise_id


def add_history(
    user_id,
    exercise_id,
    reps,
    *,
    start_day=0,
    observation_type="training",
    load_basis="bodyweight",
    weight_kg=None,
):
    """Create one workout record per observation."""
    with SessionLocal() as db:
        for index, value in enumerate(reps):
            record = WorkoutRecord(
                user_id=user_id,
                performed_at=(
                    datetime(
                        2026,
                        1,
                        1,
                        tzinfo=timezone.utc,
                    )
                    + timedelta(days=start_day + index)
                ),
            )

            record.entries.append(
                PerformanceEntry(
                    exercise_id=exercise_id,
                    set_number=1,
                    reps=value,
                    status="completed",
                    observation_type=observation_type,
                    load_basis=load_basis,
                    weight_kg=weight_kg,
                )
            )

            db.add(record)

        db.commit()


def get_groups(headers):
    return client.get(ENDPOINT, headers=headers)


def test_route_registered():
    paths = {route.path for route in app.routes}

    assert ENDPOINT in paths


def test_authentication_required():
    response = client.get(ENDPOINT)

    assert response.status_code == 401


def test_invalid_token_rejected():
    response = get_groups({"Authorization": "Bearer invalid-token"})

    assert response.status_code == 401


def test_no_history_returns_empty():
    headers, _ = register_user()

    response = get_groups(headers)

    assert response.status_code == 200, response.text
    assert response.json() == []


def test_insufficient_history_excluded():
    headers, user_id = register_user()
    _, exercise_id = create_group()

    add_history(
        user_id,
        exercise_id,
        [10, 12],
    )

    response = get_groups(headers)

    assert response.status_code == 200, response.text
    assert response.json() == []


def test_preliminary_group_response():
    headers, user_id = register_user()
    group_id, exercise_id = create_group(group_name=f"Push {uuid4().hex[:8]}")

    add_history(
        user_id,
        exercise_id,
        [10, 12, 14],
    )

    response = get_groups(headers)

    assert response.status_code == 200, response.text

    groups = response.json()
    group = next(item for item in groups if item["id"] == group_id)

    assert group["exercise_count"] == 1
    assert group["observation_count"] == 3
    assert group["confidence"] == "preliminary"
    assert group["change_pct"] == pytest.approx(40.0)
    assert isinstance(group["name"], str)
    assert isinstance(group["explanation"], str)


def test_robust_group_response():
    headers, user_id = register_user()
    group_id, exercise_id = create_group()

    add_history(
        user_id,
        exercise_id,
        [10, 12, 14, 16, 18],
    )

    response = get_groups(headers)

    assert response.status_code == 200, response.text

    group = next(item for item in response.json() if item["id"] == group_id)

    assert group["exercise_count"] == 1
    assert group["observation_count"] == 5
    assert group["confidence"] == "robust"
    assert group["change_pct"] == pytest.approx(80.0)


def test_relevance_weighted_aggregation():
    headers, user_id = register_user()

    with SessionLocal() as db:
        group = MovementGroup(name=f"Weighted Group {uuid4().hex[:8]}")

        first = Exercise(name=f"Push-Up {uuid4().hex[:8]}")
        second = Exercise(name=f"Press {uuid4().hex[:8]}")

        db.add_all([group, first, second])
        db.flush()

        db.add_all(
            [
                ExerciseMovementGroup(
                    exercise_id=first.id,
                    movement_group_id=group.id,
                    relationship_type="primary",
                    relevance_weight=1.0,
                ),
                ExerciseMovementGroup(
                    exercise_id=second.id,
                    movement_group_id=group.id,
                    relationship_type="primary",
                    relevance_weight=0.5,
                ),
            ]
        )

        group_id = group.id
        first_id = first.id
        second_id = second.id
        db.commit()

    # First: +40%, relevance weight 1.0
    add_history(user_id, first_id, [10, 12, 14])

    # Second: +20%, relevance weight 0.5
    add_history(
        user_id,
        second_id,
        [10, 11, 12],
        load_basis="external",
        weight_kg=20,
    )

    response = get_groups(headers)

    assert response.status_code == 200, response.text

    group = next(item for item in response.json() if item["id"] == group_id)

    # (40 * 1.0 + 20 * 0.5) / 1.5
    assert group["change_pct"] == pytest.approx(
        33.33,
        abs=0.01,
    )
    assert group["exercise_count"] == 2
    assert group["observation_count"] == 6
    assert group["confidence"] == "preliminary"


def test_user_isolation():
    owner_headers, owner_id = register_user()
    other_headers, other_id = register_user()

    group_id, exercise_id = create_group()

    add_history(
        owner_id,
        exercise_id,
        [10, 12, 14],
    )

    add_history(
        other_id,
        exercise_id,
        [10, 20, 30, 40, 50],
        start_day=10,
    )

    owner_response = get_groups(owner_headers)
    other_response = get_groups(other_headers)

    assert owner_response.status_code == 200
    assert other_response.status_code == 200

    owner_group = next(
        group for group in owner_response.json() if group["id"] == group_id
    )

    other_group = next(
        group for group in other_response.json() if group["id"] == group_id
    )

    assert owner_group["observation_count"] == 3
    assert owner_group["change_pct"] == pytest.approx(40.0)
    assert owner_group["confidence"] == "preliminary"

    assert other_group["observation_count"] == 5
    assert other_group["change_pct"] == pytest.approx(400.0)
    assert other_group["confidence"] == "robust"


def test_benchmarks_excluded():
    headers, user_id = register_user()
    _, exercise_id = create_group()

    add_history(
        user_id,
        exercise_id,
        [10, 12, 14],
        observation_type="benchmark",
    )

    response = get_groups(headers)

    assert response.status_code == 200, response.text
    assert response.json() == []


def test_secondary_relationship_excluded():
    headers, user_id = register_user()

    _, exercise_id = create_group(
        relationship_type="secondary",
        relevance_weight=0.5,
    )

    add_history(
        user_id,
        exercise_id,
        [10, 12, 14],
    )

    response = get_groups(headers)

    assert response.status_code == 200, response.text
    assert response.json() == []


def test_unrelated_groups_remain_separate():
    headers, user_id = register_user()

    first_group_id, first_exercise_id = create_group()
    second_group_id, second_exercise_id = create_group()

    add_history(
        user_id,
        first_exercise_id,
        [10, 12, 14],
    )

    add_history(
        user_id,
        second_exercise_id,
        [20, 22, 24],
        start_day=10,
    )

    response = get_groups(headers)

    assert response.status_code == 200, response.text

    groups = {item["id"]: item for item in response.json()}

    assert first_group_id in groups
    assert second_group_id in groups

    assert groups[first_group_id]["change_pct"] == (pytest.approx(40.0))

    assert groups[second_group_id]["change_pct"] == (pytest.approx(20.0))
