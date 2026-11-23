"""Tests for the exercise progress-analysis service.

Run independently:
    python -m pytest tests/test_progress_analysis.py -v
"""

import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

# Set environment before importing app modules.
_test_dir = tempfile.mkdtemp(prefix="ascenda_progress_")
os.environ["DATABASE_URL"] = f"sqlite:///{_test_dir}/test.db"
os.environ["JWT_SECRET"] = "test-secret-" + ("x" * 40)

import app.models
from app.db.base import Base
from app.models import (
    Exercise,
    PerformanceEntry,
    User,
    WorkoutRecord,
)
from app.services.progress_analysis import (
    _theil_sen,
    analyze_exercise_progress,
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
        email="progress-user@example.com",
        password_hash="test-hash",
    )
    other = User(
        email="other-progress-user@example.com",
        password_hash="test-hash",
    )
    exercise = Exercise(name="Test Push-Up")
    alternative = Exercise(name="Test Squat")

    db.add_all([user, other, exercise, alternative])
    db.commit()

    return {
        "user": user,
        "other": other,
        "exercise": exercise,
        "alternative": alternative,
    }


def add_observation(
    db,
    user,
    exercise,
    *,
    day=0,
    reps=10,
    seconds=None,
    set_number=1,
    weight_kg=None,
    load_basis="bodyweight",
    assistance_kg=None,
    status="completed",
    observation_type="training",
    substituted_for_exercise_id=None,
):
    record = WorkoutRecord(
        user_id=user.id,
        performed_at=(datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=day)),
    )

    entry = PerformanceEntry(
        exercise_id=exercise.id,
        set_number=set_number,
        reps=reps if status == "completed" else None,
        duration_seconds=(seconds if status == "completed" else None),
        weight_kg=(weight_kg if status == "completed" else None),
        load_basis=load_basis,
        assistance_kg=(assistance_kg if status == "completed" else None),
        status=status,
        observation_type=observation_type,
        substituted_for_exercise_id=(substituted_for_exercise_id),
    )

    record.entries.append(entry)
    db.add(record)
    db.commit()

    return record


def analyze(db, data, **kwargs):
    return analyze_exercise_progress(
        db,
        user_id=data["user"].id,
        exercise_id=data["exercise"].id,
        **kwargs,
    )


def test_insufficient_observations(db, data):
    for day, reps in enumerate([8, 10]):
        add_observation(
            db,
            data["user"],
            data["exercise"],
            day=day,
            reps=reps,
        )

    result = analyze(db, data)

    assert len(result) == 1
    assert result[0]["observation_count"] == 2
    assert result[0]["confidence"] == "insufficient"
    assert result[0]["change_pct"] is None


def test_preliminary_at_three_observations(db, data):
    for day, reps in enumerate([8, 10, 12]):
        add_observation(
            db,
            data["user"],
            data["exercise"],
            day=day,
            reps=reps,
        )

    result = analyze(db, data)[0]

    assert result["observation_count"] == 3
    assert result["confidence"] == "preliminary"
    assert result["change_pct"] == 50.0
    assert result["slope_per_observation"] is None


def test_four_observations_remain_preliminary(db, data):
    for day, reps in enumerate([8, 9, 10, 12]):
        add_observation(
            db,
            data["user"],
            data["exercise"],
            day=day,
            reps=reps,
        )

    result = analyze(db, data)[0]

    assert result["observation_count"] == 4
    assert result["confidence"] == "preliminary"


def test_robust_at_five_observations(db, data):
    values = [8, 9, 9, 11, 12]

    for day, reps in enumerate(values):
        add_observation(
            db,
            data["user"],
            data["exercise"],
            day=day,
            reps=reps,
        )

    result = analyze(db, data)[0]

    assert result["observation_count"] == 5
    assert result["confidence"] == "robust"
    assert result["slope_per_observation"] == pytest.approx(1.0)
    assert result["change_pct"] == pytest.approx(50.0)


def test_skipped_sets_excluded(db, data):
    for day, reps in enumerate([8, 10]):
        add_observation(
            db,
            data["user"],
            data["exercise"],
            day=day,
            reps=reps,
        )

    add_observation(
        db,
        data["user"],
        data["exercise"],
        day=2,
        status="skipped",
    )

    result = analyze(db, data)[0]

    assert result["observation_count"] == 2
    assert result["confidence"] == "insufficient"


def test_loading_conditions_remain_separate(db, data):
    for day, reps in enumerate([8, 10, 12]):
        add_observation(
            db,
            data["user"],
            data["exercise"],
            day=day,
            reps=reps,
            load_basis="bodyweight",
        )

    for day, reps in enumerate([6, 7]):
        add_observation(
            db,
            data["user"],
            data["exercise"],
            day=day + 3,
            reps=reps,
            load_basis="external",
            weight_kg=20,
        )

    results = analyze(db, data)

    assert len(results) == 2

    by_basis = {result["load_basis"]: result for result in results}

    assert by_basis["bodyweight"]["observation_count"] == 3
    assert by_basis["external"]["observation_count"] == 2


def test_different_external_loads_not_mixed(db, data):
    for day in range(3):
        add_observation(
            db,
            data["user"],
            data["exercise"],
            day=day,
            reps=8 + day,
            load_basis="external",
            weight_kg=20,
        )

    add_observation(
        db,
        data["user"],
        data["exercise"],
        day=3,
        reps=6,
        load_basis="external",
        weight_kg=40,
    )

    results = analyze(db, data)

    assert len(results) == 2

    by_weight = {result["weight_kg"]: result for result in results}

    assert by_weight[20]["observation_count"] == 3
    assert by_weight[40]["observation_count"] == 1


def test_benchmark_separate_from_training(db, data):
    for day in range(3):
        add_observation(
            db,
            data["user"],
            data["exercise"],
            day=day,
            reps=10 + day,
        )

    add_observation(
        db,
        data["user"],
        data["exercise"],
        day=4,
        reps=20,
        observation_type="benchmark",
    )

    training = analyze(db, data)[0]
    benchmark = analyze(db, data, observation_type="benchmark")[0]

    assert training["observation_count"] == 3
    assert benchmark["observation_count"] == 1


def test_user_isolation(db, data):
    for day in range(3):
        add_observation(
            db,
            data["user"],
            data["exercise"],
            day=day,
            reps=8 + day,
        )

    add_observation(
        db,
        data["other"],
        data["exercise"],
        day=4,
        reps=100,
    )

    result = analyze(db, data)[0]

    assert result["observation_count"] == 3
    assert all(point["actual"] < 100 for point in result["points"])


def test_set_positions_not_mixed(db, data):
    for day in range(3):
        add_observation(
            db,
            data["user"],
            data["exercise"],
            day=day,
            reps=10,
            set_number=1,
        )

    add_observation(
        db,
        data["user"],
        data["exercise"],
        day=4,
        reps=5,
        set_number=2,
    )

    results = analyze(db, data)

    counts = {result["set_number"]: result["observation_count"] for result in results}

    assert counts == {1: 3, 2: 1}


def test_substituted_entries_excluded(db, data):
    for day in range(3):
        add_observation(
            db,
            data["user"],
            data["exercise"],
            day=day,
            reps=10,
        )

    add_observation(
        db,
        data["user"],
        data["exercise"],
        day=4,
        reps=20,
        substituted_for_exercise_id=data["alternative"].id,
    )

    result = analyze(db, data)[0]

    assert result["observation_count"] == 3


def test_invalid_observation_type(db, data):
    with pytest.raises(ValueError):
        analyze(
            db,
            data,
            observation_type="invalid",
        )


def test_theil_sen_slope():
    assert _theil_sen([8, 9, 9, 11, 12]) == pytest.approx(1.0)
    assert _theil_sen([10, 10, 10, 10, 10]) == 0
