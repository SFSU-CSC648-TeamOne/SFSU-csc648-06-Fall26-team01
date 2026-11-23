
"""Build enrollment schedules from explicit program metadata.

This module does not:
- Invent training, deload, or assessment phases.
- Infer database exercise IDs from frontend identifiers.
- Personalize prescriptions from assessment results.
- Write to the database.

The caller supplies verified exercise IDs, workout targets,
and program-defined phase classifications.
"""

from dataclasses import dataclass
from decimal import Decimal

from app.core.errors import ValidationFailed
from app.models.program_phase import ProgramPhaseType
from app.services.program_enrollment import (
    EnrollmentSet,
    EnrollmentWorkout,
    _validate_schedule,
)


@dataclass(frozen=True)
class ExerciseTemplate:
    """One exercise within a scheduled workout."""

    exercise_id: int
    set_count: int
    load_basis: str
    target_reps: int | None = None
    target_duration_seconds: int | None = None
    target_weight_kg: Decimal | None = None
    is_optional: bool = False


@dataclass(frozen=True)
class WorkoutTemplate:
    """One explicitly classified workout in a program."""

    week: int
    day: int
    phase_type: str
    exercises: tuple[ExerciseTemplate, ...]
    workout_session_id: int | None = None
    phase_reason: str | None = None


@dataclass(frozen=True)
class ProgramSchedule:
    """A fully specified program schedule.

    No implicit phases or progression formulas are applied.
    """

    program_slug: str
    workouts: tuple[WorkoutTemplate, ...]


def build_enrollment_schedule(
    program: ProgramSchedule,
) -> tuple[EnrollmentWorkout, ...]:
    """Convert validated templates to enrollment prescriptions.

    Returns:
        EnrollmentWorkout objects ready for the enrollment service.

    Raises:
        ValidationFailed if required metadata is missing or invalid.
    """

    if (
        not program.program_slug
        or len(program.program_slug) > 20
    ):
        raise ValidationFailed("Invalid program slug.")

    if not program.workouts:
        raise ValidationFailed(
            "Program schedule contains no workouts."
        )

    valid_phases = {
        phase.value for phase in ProgramPhaseType
    }

    generated = []

    for workout in program.workouts:
        if workout.phase_type not in valid_phases:
            raise ValidationFailed(
                "Workout phase must be explicitly classified."
            )

        if not workout.exercises:
            raise ValidationFailed(
                "Workout contains no exercises."
            )

        prescribed_sets = []

        for exercise in workout.exercises:
            if (
                isinstance(exercise.set_count, bool)
                or not isinstance(exercise.set_count, int)
                or exercise.set_count <= 0
            ):
                raise ValidationFailed(
                    "Exercise set count must be a positive integer."
                )

            for set_number in range(
                1,
                exercise.set_count + 1,
            ):
                prescribed_sets.append(
                    EnrollmentSet(
                        exercise_id=exercise.exercise_id,
                        set_number=set_number,
                        load_basis=exercise.load_basis,
                        target_reps=exercise.target_reps,
                        target_duration_seconds=(
                            exercise.target_duration_seconds
                        ),
                        target_weight_kg=(
                            exercise.target_weight_kg
                        ),
                        is_optional=exercise.is_optional,
                    )
                )

        generated.append(
            EnrollmentWorkout(
                program_week=workout.week,
                program_day=workout.day,
                phase_type=workout.phase_type,
                sets=tuple(prescribed_sets),
                workout_session_id=(
                    workout.workout_session_id
                ),
                phase_reason=workout.phase_reason,
            )
        )

    result = tuple(generated)

    # Reuse enrollment service validation instead of
    # maintaining a second set of prescription rules.
    _validate_schedule(result)

    return result
