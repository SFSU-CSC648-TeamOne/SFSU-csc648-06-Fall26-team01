
"""Tests for program schedule generation.

Run from app/backend:
    python -m pytest tests/test_program_schedule.py -v

No database connection is required.
"""

from decimal import Decimal

import pytest

from app.core.errors import ValidationFailed
from app.services.program_schedule import (
    ExerciseTemplate,
    WorkoutTemplate,
    ProgramSchedule,
    build_enrollment_schedule,
)


def exercise(
    exercise_id=1,
    *,
    sets=3,
    reps=10,
    duration=None,
    weight=None,
    load_basis="bodyweight",
    optional=False,
):
    return ExerciseTemplate(
        exercise_id=exercise_id,
        set_count=sets,
        load_basis=load_basis,
        target_reps=reps,
        target_duration_seconds=duration,
        target_weight_kg=weight,
        is_optional=optional,
    )


def workout(
    *,
    week=1,
    day=1,
    phase="training",
    exercises=None,
    session_id=None,
):
    return WorkoutTemplate(
        week=week,
        day=day,
        phase_type=phase,
        exercises=(
            tuple(exercises)
            if exercises is not None
            else (exercise(),)
        ),
        workout_session_id=session_id,
    )


def build(*workouts, slug="bw"):
    return build_enrollment_schedule(
        ProgramSchedule(
            program_slug=slug,
            workouts=tuple(workouts),
        )
    )


# --------------------------------------------------
# Successful schedule generation
# --------------------------------------------------

def test_generates_enrollment_workout():
    result = build(workout())

    assert len(result) == 1

    generated = result[0]

    assert generated.program_week == 1
    assert generated.program_day == 1
    assert generated.phase_type == "training"
    assert len(generated.sets) == 3


def test_expands_exercise_into_numbered_sets():
    result = build(
        workout(
            exercises=[
                exercise(1, sets=3, reps=10),
                exercise(2, sets=2, reps=15),
            ]
        )
    )

    prescribed_sets = result[0].sets

    assert len(prescribed_sets) == 5

    assert [
        (item.exercise_id, item.set_number)
        for item in prescribed_sets
    ] == [
        (1, 1),
        (1, 2),
        (1, 3),
        (2, 1),
        (2, 2),
    ]


def test_preserves_optional_accessories():
    result = build(
        workout(
            exercises=[
                exercise(1, optional=False),
                exercise(2, optional=True),
            ]
        )
    )

    sets = result[0].sets

    assert len(sets) == 6
    assert all(not item.is_optional for item in sets[:3])
    assert all(item.is_optional for item in sets[3:])


def test_preserves_duration_targets():
    result = build(
        workout(
            exercises=[
                exercise(
                    1,
                    sets=2,
                    reps=None,
                    duration=45,
                )
            ]
        )
    )

    for item in result[0].sets:
        assert item.target_reps is None
        assert item.target_duration_seconds == 45


def test_preserves_weight_targets():
    result = build(
        workout(
            exercises=[
                exercise(
                    1,
                    sets=3,
                    reps=8,
                    weight=Decimal("60.50"),
                    load_basis="external",
                )
            ]
        ),
        slug="ldw",
    )

    for item in result[0].sets:
        assert item.target_reps == 8
        assert item.target_weight_kg == Decimal("60.50")
        assert item.load_basis == "external"


def test_preserves_explicit_phases():
    result = build(
        workout(week=1, phase="training"),
        workout(week=2, phase="deload"),
        workout(week=3, phase="assessment"),
    )

    assert [
        item.phase_type for item in result
    ] == [
        "training",
        "deload",
        "assessment",
    ]


def test_preserves_workout_session_reference():
    result = build(
        workout(session_id=42)
    )

    assert result[0].workout_session_id == 42


# --------------------------------------------------
# Schedule validation
# --------------------------------------------------

def test_rejects_empty_schedule():
    with pytest.raises(ValidationFailed):
        build()


def test_rejects_unknown_phase():
    with pytest.raises(ValidationFailed):
        build(workout(phase="recovery"))


def test_rejects_empty_workout():
    with pytest.raises(ValidationFailed):
        build(workout(exercises=[]))


@pytest.mark.parametrize(
    "set_count",
    [0, -1, 1.5, True],
)
def test_rejects_invalid_set_count(set_count):
    with pytest.raises(ValidationFailed):
        build(
            workout(
                exercises=[
                    exercise(sets=set_count)
                ]
            )
        )


def test_rejects_duplicate_program_day():
    with pytest.raises(ValidationFailed):
        build(
            workout(week=1, day=1),
            workout(week=1, day=1),
        )


def test_rejects_duplicate_exercise_sets():
    with pytest.raises(ValidationFailed):
        build(
            workout(
                exercises=[
                    exercise(1, sets=2),
                    exercise(1, sets=2),
                ]
            )
        )


def test_rejects_invalid_repetition_target():
    with pytest.raises(ValidationFailed):
        build(
            workout(
                exercises=[
                    exercise(reps=0)
                ]
            )
        )


def test_rejects_invalid_weight_target():
    with pytest.raises(ValidationFailed):
        build(
            workout(
                exercises=[
                    exercise(
                        reps=8,
                        weight=Decimal("-5"),
                        load_basis="external",
                    )
                ]
            )
        )


def test_rejects_missing_weight_for_external_load():
    with pytest.raises(ValidationFailed):
        build(
            workout(
                exercises=[
                    exercise(
                        reps=8,
                        load_basis="external",
                        weight=None,
                    )
                ]
            )
        )


def test_rejects_unsupported_assistance():
    with pytest.raises(ValidationFailed):
        build(
            workout(
                exercises=[
                    exercise(
                        reps=10,
                        load_basis="assisted",
                    )
                ]
            )
        )


def test_rejects_invalid_program_slug():
    with pytest.raises(ValidationFailed):
        build(workout(), slug="")