"""Tests for movement-group progress aggregation.

Run independently:
    python -m pytest tests/test_movement_group_progress.py -v
"""

import os
import tempfile
from datetime import datetime, timedelta, timezone

os.environ["DATABASE_URL"] = (
    f"sqlite:///{tempfile.mkdtemp(prefix='ascenda_groups_')}/test.db"
)
os.environ["JWT_SECRET"] = "test-secret-" + ("x" * 40)

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.models
from app.db.base import Base
from app.models import (
    Exercise,
    ExerciseMovementGroup,
    MovementGroup,
    PerformanceEntry,
    User,
    WorkoutRecord,
)
from app.services.progress_analysis import (
    analyze_movement_group_progress,
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
def data(db):
    user = User(
        email="group-user@example.com",
        password_hash="test-hash",
    )
    other = User(
        email="other-group-user@example.com",
        password_hash="test-hash",
    )

    pushup = Exercise(name="Push-Up")
    bench = Exercise(name="Bench Press")
    squat = Exercise(name="Squat")

    pushing = MovementGroup(name="Horizontal Push")
    squatting = MovementGroup(name="Squat Pattern")

    db.add_all(
        [
            user,
            other,
            pushup,
            bench,
            squat,
            pushing,
            squatting,
        ]
    )
    db.flush()

    db.add_all(
        [
            ExerciseMovementGroup(
                exercise_id=pushup.id,
                movement_group_id=pushing.id,
                relationship_type="primary",
                relevance_weight=1.0,
            ),
            ExerciseMovementGroup(
                exercise_id=bench.id,
                movement_group_id=pushing.id,
                relationship_type="primary",
                relevance_weight=0.5,
            ),
            ExerciseMovementGroup(
                exercise_id=squat.id,
                movement_group_id=squatting.id,
                relationship_type="primary",
                relevance_weight=1.0,
            ),
        ]
    )

    db.commit()

    return {
        "user": user,
        "other": other,
        "pushup": pushup,
        "bench": bench,
        "squat": squat,
        "pushing": pushing,
        "squatting": squatting,
    }


def add_history(
    db,
    user,
    exercise,
    reps,
    *,
    start_day=0,
    set_number=1,
    observation_type="training",
    load_basis="bodyweight",
    weight_kg=None,
    status="completed",
):
    """Insert one workout record per observation."""

    for index, value in enumerate(reps):
        record = WorkoutRecord(
            user_id=user.id,
            performed_at=(
                datetime(2026, 1, 1, tzinfo=timezone.utc)
                + timedelta(days=start_day + index)
            ),
        )

        entry = PerformanceEntry(
            exercise_id=exercise.id,
            set_number=set_number,
            reps=value if status == "completed" else None,
            status=status,
            observation_type=observation_type,
            load_basis=load_basis,
            weight_kg=weight_kg,
        )

        record.entries.append(entry)
        db.add(record)

    db.commit()


def analyze(db, data):
    return analyze_movement_group_progress(
        db=db,
        user_id=data["user"].id,
    )


def test_no_history_returns_empty(db, data):
    assert analyze(db, data) == []


def test_insufficient_history_excluded(db, data):
    add_history(
        db,
        data["user"],
        data["pushup"],
        [10, 12],
    )

    assert analyze(db, data) == []


def test_single_exercise_preliminary(db, data):
    add_history(
        db,
        data["user"],
        data["pushup"],
        [10, 12, 14],
    )

    results = analyze(db, data)

    assert len(results) == 1

    group = results[0]

    assert group["id"] == data["pushing"].id
    assert group["name"] == "Horizontal Push"
    assert group["exercise_count"] == 1
    assert group["observation_count"] == 3
    assert group["confidence"] == "preliminary"
    assert group["change_pct"] == pytest.approx(40.0)


def test_single_exercise_robust(db, data):
    add_history(
        db,
        data["user"],
        data["pushup"],
        [10, 12, 14, 16, 18],
    )

    group = analyze(db, data)[0]

    assert group["exercise_count"] == 1
    assert group["observation_count"] == 5
    assert group["confidence"] == "robust"
    assert group["change_pct"] == pytest.approx(80.0)


def test_relevance_weighted_average(db, data):
    # Push-ups: 10 -> 14 = +40%, weight 1.0
    add_history(
        db,
        data["user"],
        data["pushup"],
        [10, 12, 14],
    )

    # Bench press: 10 -> 12 = +20%, weight 0.5
    add_history(
        db,
        data["user"],
        data["bench"],
        [10, 11, 12],
        load_basis="external",
        weight_kg=20,
    )

    group = analyze(db, data)[0]

    # (40 * 1.0 + 20 * 0.5) / 1.5 = 33.33%
    assert group["change_pct"] == pytest.approx(
        33.33,
        abs=0.01,
    )

    assert group["exercise_count"] == 2
    assert group["observation_count"] == 6
    assert group["confidence"] == "preliminary"


def test_mixed_confidence_is_preliminary(db, data):
    add_history(
        db,
        data["user"],
        data["pushup"],
        [10, 12, 14, 16, 18],
    )

    add_history(
        db,
        data["user"],
        data["bench"],
        [10, 11, 12],
        load_basis="external",
        weight_kg=20,
    )

    group = analyze(db, data)[0]

    assert group["exercise_count"] == 2
    assert group["observation_count"] == 8
    assert group["confidence"] == "preliminary"


def test_all_robust_exercises_make_robust_group(db, data):
    add_history(
        db,
        data["user"],
        data["pushup"],
        [10, 12, 14, 16, 18],
    )

    add_history(
        db,
        data["user"],
        data["bench"],
        [10, 11, 12, 13, 14],
        load_basis="external",
        weight_kg=20,
    )

    group = analyze(db, data)[0]

    assert group["exercise_count"] == 2
    assert group["observation_count"] == 10
    assert group["confidence"] == "robust"


def test_unrelated_movements_remain_separate(db, data):
    add_history(
        db,
        data["user"],
        data["pushup"],
        [10, 12, 14],
    )

    add_history(
        db,
        data["user"],
        data["squat"],
        [20, 22, 24],
    )

    results = analyze(db, data)

    assert len(results) == 2

    by_name = {group["name"]: group for group in results}

    assert by_name["Horizontal Push"]["change_pct"] == 40
    assert by_name["Squat Pattern"]["change_pct"] == 20


def test_secondary_relationship_excluded(db, data):
    # Make bench press a secondary squat-pattern exercise.
    db.add(
        ExerciseMovementGroup(
            exercise_id=data["bench"].id,
            movement_group_id=data["squatting"].id,
            relationship_type="secondary",
            relevance_weight=0.5,
        )
    )
    db.commit()

    add_history(
        db,
        data["user"],
        data["bench"],
        [10, 11, 12],
    )

    results = analyze(db, data)

    assert len(results) == 1
    assert results[0]["name"] == "Horizontal Push"


def test_zero_relevance_weight_excluded(db, data):
    relationship = db.get(
        ExerciseMovementGroup,
        (
            data["bench"].id,
            data["pushing"].id,
        ),
    )

    relationship.relevance_weight = 0
    db.commit()

    add_history(
        db,
        data["user"],
        data["bench"],
        [10, 11, 12],
    )

    assert analyze(db, data) == []


def test_user_isolation(db, data):
    add_history(
        db,
        data["user"],
        data["pushup"],
        [10, 12, 14],
    )

    add_history(
        db,
        data["other"],
        data["pushup"],
        [10, 20, 30, 40, 50],
    )

    group = analyze(db, data)[0]

    assert group["observation_count"] == 3
    assert group["change_pct"] == 40
    assert group["confidence"] == "preliminary"


def test_benchmarks_do_not_enter_training_group(db, data):
    add_history(
        db,
        data["user"],
        data["pushup"],
        [10, 12, 14],
        observation_type="benchmark",
    )

    assert analyze(db, data) == []


def test_one_series_per_exercise(db, data):
    # Two independently comparable set positions.
    add_history(
        db,
        data["user"],
        data["pushup"],
        [10, 12, 14, 16, 18],
        set_number=1,
    )

    add_history(
        db,
        data["user"],
        data["pushup"],
        [8, 9, 10],
        start_day=10,
        set_number=2,
    )

    group = analyze(db, data)[0]

    # Only the longest eligible series is selected.
    assert group["exercise_count"] == 1
    assert group["observation_count"] == 5
    assert group["change_pct"] == 80
