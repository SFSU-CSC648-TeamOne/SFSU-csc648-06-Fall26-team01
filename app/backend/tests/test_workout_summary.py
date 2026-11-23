"""Regression tests for workout program summaries.

Run independently:
    python -m pytest tests/test_workout_summary.py -v
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.models
from app.db.base import Base
from app.models import (
    Exercise,
    PerformanceEntry,
    User,
    WorkoutRecord,
)
from app.services.workouts import program_summary


@pytest.fixture
def db():
    """Fresh in-memory database for each test."""
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
def fixture_data(db):
    user = User(
        email="summary-user@example.com",
        password_hash="test-hash",
    )

    other_user = User(
        email="other-user@example.com",
        password_hash="test-hash",
    )

    exercise = Exercise(name="Test Squat")
    alternative = Exercise(name="Test Push-Up")

    db.add_all([user, other_user, exercise, alternative])
    db.commit()

    return {
        "user": user,
        "other_user": other_user,
        "exercise": exercise,
        "alternative": alternative,
    }


def add_workout(
    db,
    user,
    exercise,
    *,
    day=1,
    week=1,
    reps=10,
    weight_kg=None,
    status="completed",
    attempt=1,
    additional_entries=None,
):
    """Create one recorded workout with deterministic ordering."""

    record = WorkoutRecord(
        user_id=user.id,
        program_slug="test",
        program_week=week,
        program_day=day,
        performed_at=datetime(
            2026,
            11,
            min(attempt, 28),
            12,
            0,
            tzinfo=timezone.utc,
        ),
    )

    entries = [
        PerformanceEntry(
            exercise_id=exercise.id,
            set_number=1,
            reps=reps if status == "completed" else None,
            weight_kg=(weight_kg if status == "completed" else None),
            status=status,
            observation_type="training",
        )
    ]

    if additional_entries:
        entries.extend(additional_entries)

    record.entries = entries
    db.add(record)
    db.commit()

    return record


def test_completed_set_counts_as_completed_day(db, fixture_data):
    user = fixture_data["user"]
    exercise = fixture_data["exercise"]

    add_workout(
        db,
        user,
        exercise,
        day=1,
        reps=10,
        weight_kg=20,
    )

    summary = program_summary(db, user, "test")

    assert summary.days_completed == 1
    assert summary.totals.sets == 1
    assert summary.totals.reps == 10
    assert summary.totals.volume_kg == 200


def test_skipped_only_day_not_completed(db, fixture_data):
    user = fixture_data["user"]
    exercise = fixture_data["exercise"]

    add_workout(
        db,
        user,
        exercise,
        day=1,
        status="skipped",
    )

    summary = program_summary(db, user, "test")

    assert summary.days_completed == 0
    assert summary.totals.sets == 0
    assert summary.totals.reps == 0
    assert summary.totals.volume_kg == 0


def test_mixed_completed_and_skipped_sets(db, fixture_data):
    user = fixture_data["user"]
    exercise = fixture_data["exercise"]

    skipped = PerformanceEntry(
        exercise_id=exercise.id,
        set_number=2,
        reps=None,
        status="skipped",
        observation_type="training",
    )

    add_workout(
        db,
        user,
        exercise,
        reps=8,
        additional_entries=[skipped],
    )

    summary = program_summary(db, user, "test")

    assert summary.days_completed == 1
    assert summary.totals.sets == 1
    assert summary.totals.reps == 8


def test_latest_attempt_replaces_earlier_attempt(db, fixture_data):
    user = fixture_data["user"]
    exercise = fixture_data["exercise"]

    add_workout(
        db,
        user,
        exercise,
        day=1,
        reps=10,
        attempt=1,
    )

    add_workout(
        db,
        user,
        exercise,
        day=1,
        reps=6,
        attempt=2,
    )

    summary = program_summary(db, user, "test")

    assert summary.days_completed == 1
    assert summary.totals.sets == 1
    assert summary.totals.reps == 6


def test_latest_skipped_attempt_replaces_completion(db, fixture_data):
    user = fixture_data["user"]
    exercise = fixture_data["exercise"]

    add_workout(
        db,
        user,
        exercise,
        day=1,
        reps=10,
        attempt=1,
    )

    add_workout(
        db,
        user,
        exercise,
        day=1,
        status="skipped",
        attempt=2,
    )

    summary = program_summary(db, user, "test")

    assert summary.days_completed == 0
    assert summary.totals.sets == 0
    assert summary.totals.reps == 0


def test_multiple_exercises_same_day_count_once(db, fixture_data):
    user = fixture_data["user"]

    add_workout(
        db,
        user,
        fixture_data["exercise"],
        day=1,
        reps=10,
    )

    add_workout(
        db,
        user,
        fixture_data["alternative"],
        day=1,
        reps=15,
        attempt=2,
    )

    summary = program_summary(db, user, "test")

    assert summary.days_completed == 1
    assert summary.totals.sets == 2
    assert summary.totals.reps == 25


def test_multiple_weeks_count_correctly(db, fixture_data):
    user = fixture_data["user"]
    exercise = fixture_data["exercise"]

    add_workout(
        db,
        user,
        exercise,
        week=1,
        day=1,
    )

    add_workout(
        db,
        user,
        exercise,
        week=1,
        day=2,
        attempt=2,
    )

    add_workout(
        db,
        user,
        exercise,
        week=2,
        day=1,
        attempt=3,
    )

    summary = program_summary(db, user, "test")

    assert summary.days_completed == 3

    week_counts = {week.week: week.days_completed for week in summary.weeks}

    assert week_counts == {1: 2, 2: 1}


def test_summary_isolated_by_user(db, fixture_data):
    user = fixture_data["user"]
    other_user = fixture_data["other_user"]
    exercise = fixture_data["exercise"]

    add_workout(
        db,
        user,
        exercise,
        reps=10,
    )

    add_workout(
        db,
        other_user,
        exercise,
        reps=50,
    )

    summary = program_summary(db, user, "test")

    assert summary.days_completed == 1
    assert summary.totals.reps == 10


def test_summary_isolated_by_program(db, fixture_data):
    user = fixture_data["user"]
    exercise = fixture_data["exercise"]

    add_workout(
        db,
        user,
        exercise,
        reps=10,
    )

    other_record = add_workout(
        db,
        user,
        exercise,
        day=2,
        reps=20,
        attempt=2,
    )

    other_record.program_slug = "another"
    db.commit()

    summary = program_summary(db, user, "test")

    assert summary.days_completed == 1
    assert summary.totals.reps == 10
