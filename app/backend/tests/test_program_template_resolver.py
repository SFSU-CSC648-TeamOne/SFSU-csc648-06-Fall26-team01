
"""Tests for resolving program templates into enrollment schedules.

Run from app/backend:
    python -m pytest tests/test_program_template_resolver.py -v

Uses isolated in-memory SQLite.
No PostgreSQL or Supabase connection is required.
"""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.models
from app.models.program_instance import ProgramInstance

from app.core.errors import ValidationFailed
from app.db.base import Base
from app.models.catalog import Exercise
from app.models.prescription import (
    PrescriptionSet,
    WorkoutPrescription,
)
from app.models.program_phase import ProgramPhase
from app.services.program_definitions import (
    get_program_definition,
    required_exercise_slugs,
)
from app.services.program_template_resolver import (
    ExerciseTarget,
    resolve_program_template,
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


@pytest.fixture(params=["bw", "ldw"])
def setup(db, request):
    slug = request.param
    program = get_program_definition(slug)

    assert program is not None

    exercise_ids = {}

    for exercise_slug in sorted(
        required_exercise_slugs(program)
    ):
        exercise = Exercise(name=exercise_slug)
        db.add(exercise)
        db.flush()
        exercise_ids[exercise_slug] = exercise.id

    db.commit()

    phases = {
        (week, day): "training"
        for week in range(1, 5)
        for day in range(1, 6)
    }

    targets = {}

    for week in range(1, 5):
        for day, template in enumerate(
            program.days, start=1
        ):
            for item in template.exercises:
                key = (week, day, item.slug)

                if item.slug == "plank":
                    targets[key] = ExerciseTarget(
                        load_basis="bodyweight",
                        target_duration_seconds=30,
                    )
                elif slug == "ldw":
                    targets[key] = ExerciseTarget(
                        load_basis="external",
                        target_reps=8,
                        target_weight_kg=Decimal("40.00"),
                    )
                else:
                    targets[key] = ExerciseTarget(
                        load_basis="bodyweight",
                        target_reps=10,
                    )

    return {
        "slug": slug,
        "program": program,
        "exercise_ids": exercise_ids,
        "phases": phases,
        "targets": targets,
    }


def resolve(db, setup, **changes):
    arguments = {
        "program_slug": setup["slug"],
        "exercise_ids": setup["exercise_ids"],
        "phases": setup["phases"],
        "targets": setup["targets"],
    }
    arguments.update(changes)

    return resolve_program_template(db, **arguments)


def row_count(db, model):
    return db.scalar(
        select(func.count()).select_from(model)
    )


# --------------------------------------------------
# Successful resolution
# --------------------------------------------------

def test_resolves_complete_four_week_schedule(db, setup):
    result = resolve(db, setup)

    assert len(result) == 20

    assert {
        (workout.program_week, workout.program_day)
        for workout in result
    } == {
        (week, day)
        for week in range(1, 5)
        for day in range(1, 6)
    }


def test_uses_verified_exercise_ids(db, setup):
    result = resolve(db, setup)

    allowed_ids = set(setup["exercise_ids"].values())

    assert all(
        prescribed_set.exercise_id in allowed_ids
        for workout in result
        for prescribed_set in workout.sets
    )


def test_expands_weekly_set_counts(db, setup):
    result = resolve(db, setup)
    program = setup["program"]

    for workout in result:
        week = workout.program_week
        day = workout.program_day

        expected_count = (
            program.weeks[week - 1].sets
            * len(program.days[day - 1].exercises)
        )

        assert len(workout.sets) == expected_count


def test_preserves_accessory_flags(db, setup):
    result = resolve(db, setup)
    program = setup["program"]

    first_workout = result[0]
    template = program.days[0]
    sets_per_exercise = program.weeks[0].sets

    expected = [
        item.role == "accessory"
        for item in template.exercises
        for _ in range(sets_per_exercise)
    ]

    actual = [
        item.is_optional
        for item in first_workout.sets
    ]

    assert actual == expected


def test_preserves_explicit_phase_classifications(db, setup):
    phases = dict(setup["phases"])
    phases[(2, 1)] = "deload"
    phases[(4, 5)] = "assessment"

    result = resolve(db, setup, phases=phases)

    resolved = {
        (workout.program_week, workout.program_day):
            workout.phase_type
        for workout in result
    }

    assert resolved[(1, 1)] == "training"
    assert resolved[(2, 1)] == "deload"
    assert resolved[(4, 5)] == "assessment"


def test_preserves_explicit_targets(db, setup):
    result = resolve(db, setup)

    for workout in result:
        for item in workout.sets:
            if setup["slug"] == "ldw":
                assert item.target_reps == 8
                assert item.target_weight_kg == Decimal("40.00")
                assert item.load_basis == "external"

            elif item.exercise_id == setup["exercise_ids"].get(
                "plank"
            ):
                assert item.target_reps is None
                assert item.target_duration_seconds == 30


def test_explicit_set_count_overrides_week_scheme(db, setup):
    targets = dict(setup["targets"])
    key = (1, 1, setup["program"].days[0].exercises[0].slug)

    original = targets[key]

    targets[key] = ExerciseTarget(
        load_basis=original.load_basis,
        target_reps=original.target_reps,
        target_duration_seconds=(
            original.target_duration_seconds
        ),
        target_weight_kg=original.target_weight_kg,
        set_count=2,
    )

    result = resolve(db, setup, targets=targets)

    expected = (
        2
        + (
            len(setup["program"].days[0].exercises) - 1
        ) * setup["program"].weeks[0].sets
    )

    assert len(result[0].sets) == expected


# --------------------------------------------------
# Exercise mapping safeguards
# --------------------------------------------------

def test_rejects_missing_exercise_mapping(db, setup):
    mappings = dict(setup["exercise_ids"])
    mappings.pop(next(iter(mappings)))

    with pytest.raises(ValidationFailed):
        resolve(db, setup, exercise_ids=mappings)


def test_rejects_unknown_mapping_key(db, setup):
    mappings = dict(setup["exercise_ids"])
    mappings["unknown-exercise"] = 999999

    with pytest.raises(ValidationFailed):
        resolve(db, setup, exercise_ids=mappings)


def test_rejects_nonexistent_database_exercise(db, setup):
    mappings = dict(setup["exercise_ids"])
    first = next(iter(mappings))
    mappings[first] = 999999

    with pytest.raises(ValidationFailed):
        resolve(db, setup, exercise_ids=mappings)


def test_rejects_duplicate_database_exercise_ids(db, setup):
    mappings = dict(setup["exercise_ids"])
    keys = list(mappings)

    mappings[keys[1]] = mappings[keys[0]]

    with pytest.raises(ValidationFailed):
        resolve(db, setup, exercise_ids=mappings)


# --------------------------------------------------
# Phase safeguards
# --------------------------------------------------

def test_rejects_missing_phase(db, setup):
    phases = dict(setup["phases"])
    phases.pop((2, 3))

    with pytest.raises(ValidationFailed):
        resolve(db, setup, phases=phases)


def test_rejects_unknown_phase(db, setup):
    phases = dict(setup["phases"])
    phases[(2, 3)] = "recovery"

    with pytest.raises(ValidationFailed):
        resolve(db, setup, phases=phases)


def test_rejects_extra_phase(db, setup):
    phases = dict(setup["phases"])
    phases[(5, 1)] = "training"

    with pytest.raises(ValidationFailed):
        resolve(db, setup, phases=phases)


# --------------------------------------------------
# Prescription target safeguards
# --------------------------------------------------

def test_rejects_missing_target(db, setup):
    targets = dict(setup["targets"])
    targets.pop(next(iter(targets)))

    with pytest.raises(ValidationFailed):
        resolve(db, setup, targets=targets)


def test_rejects_extra_target(db, setup):
    targets = dict(setup["targets"])

    targets[(5, 1, "unknown")] = ExerciseTarget(
        load_basis="bodyweight",
        target_reps=10,
    )

    with pytest.raises(ValidationFailed):
        resolve(db, setup, targets=targets)


def test_rejects_invalid_set_count(db, setup):
    targets = dict(setup["targets"])
    key = next(iter(targets))

    original = targets[key]

    targets[key] = ExerciseTarget(
        load_basis=original.load_basis,
        target_reps=original.target_reps,
        target_duration_seconds=(
            original.target_duration_seconds
        ),
        target_weight_kg=original.target_weight_kg,
        set_count=0,
    )

    with pytest.raises(ValidationFailed):
        resolve(db, setup, targets=targets)


def test_rejects_unsupported_assistance(db, setup):
    targets = dict(setup["targets"])
    key = next(iter(targets))

    targets[key] = ExerciseTarget(
        load_basis="assisted",
        target_reps=10,
    )

    with pytest.raises(ValidationFailed):
        resolve(db, setup, targets=targets)


def test_rejects_unknown_program(db, setup):
    with pytest.raises(ValidationFailed):
        resolve(db, setup, program_slug="unknown")


# --------------------------------------------------
# Read-only guarantee
# --------------------------------------------------

def test_resolver_does_not_write_database(db, setup):
    before = {
        model: row_count(db, model)
        for model in (
            ProgramInstance,
            WorkoutPrescription,
            PrescriptionSet,
            ProgramPhase,
        )
    }

    resolve(db, setup)

    after = {
        model: row_count(db, model)
        for model in before
    }

    assert after == before

    assert all(value == 0 for value in after.values())