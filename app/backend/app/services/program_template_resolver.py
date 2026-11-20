
"""Resolve Ascenda program definitions into enrollment schedules.

Requires:
- Database-verified exercise mappings
- Explicit phase classification for every workout
- Explicit prescription targets for every exercise

No guessed phases, loads, or personalized targets.
No database writes.
"""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ValidationFailed
from app.models.catalog import Exercise
from app.models.enums import LoadBasis
from app.models.program_phase import ProgramPhaseType
from app.services.program_definitions import (
    ProgramDefinition,
    get_program_definition,
    required_exercise_slugs,
)
from app.services.program_schedule import (
    ExerciseTemplate,
    ProgramSchedule,
    WorkoutTemplate,
    build_enrollment_schedule,
)
from app.services.program_enrollment import EnrollmentWorkout


# (week, day) -> phase type
PhaseMap = dict[tuple[int, int], str]

# (week, day, exercise slug) -> prescribed target
TargetKey = tuple[int, int, str]


@dataclass(frozen=True)
class ExerciseTarget:
    """Explicit target for one exercise on one scheduled day."""

    load_basis: str
    target_reps: int | None = None
    target_duration_seconds: int | None = None
    target_weight_kg: Decimal | None = None

    # Optional override; otherwise use the week scheme.
    set_count: int | None = None


def resolve_program_template(
    db: Session,
    *,
    program_slug: str,
    exercise_ids: dict[str, int],
    phases: PhaseMap,
    targets: dict[TargetKey, ExerciseTarget],
) -> tuple[EnrollmentWorkout, ...]:
    """Build a validated, read-only enrollment schedule.

    All exercise IDs must exist in the local catalog.
    The supplied mapping must also be semantically verified
    against the expected exercise before calling this service.

    Returns a complete schedule for create_program_enrollment().
    """

    program = get_program_definition(program_slug)

    if program is None:
        raise ValidationFailed(
            f"Unsupported program: {program_slug}"
        )

    return _resolve(
        db=db,
        program=program,
        exercise_ids=exercise_ids,
        phases=phases,
        targets=targets,
    )


def _resolve(
    *,
    db: Session,
    program: ProgramDefinition,
    exercise_ids: dict[str, int],
    phases: PhaseMap,
    targets: dict[TargetKey, ExerciseTarget],
) -> tuple[EnrollmentWorkout, ...]:

    # 1. Require exact mapping coverage.
    required_slugs = required_exercise_slugs(program)

    if set(exercise_ids) != required_slugs:
        raise ValidationFailed(
            "Exercise mapping must contain exactly the "
            "program's required exercise slugs."
        )

    if any(
        not isinstance(exercise_id, int)
        or isinstance(exercise_id, bool)
        or exercise_id <= 0
        for exercise_id in exercise_ids.values()
    ):
        raise ValidationFailed("Invalid database exercise ID.")

    # Distinct exercise slugs must not silently resolve
    # to the same catalog exercise.
    if len(set(exercise_ids.values())) != len(exercise_ids):
        raise ValidationFailed(
            "Multiple exercise slugs map to the same database ID."
        )

    # 2. Verify referenced database rows exist.
    ids = set(exercise_ids.values())

    found = set(
        db.scalars(
            select(Exercise.id).where(
                Exercise.id.in_(ids)
            )
        ).all()
    )

    if found != ids:
        raise ValidationFailed(
            "One or more mapped exercises do not exist."
        )

    # 3. Require phases for every scheduled workout.
    required_days = {
        (week, day)
        for week in range(1, program.week_count + 1)
        for day in range(
            1,
            program.workout_days_per_week + 1,
        )
    }

    if set(phases) != required_days:
        raise ValidationFailed(
            "Phase map must classify every scheduled workout "
            "exactly once, with no additional dates."
        )

    valid_phases = {
        phase.value for phase in ProgramPhaseType
    }

    if any(
        phase not in valid_phases
        for phase in phases.values()
    ):
        raise ValidationFailed(
            "Phase map contains an invalid classification."
        )

    # 4. Require a target for every scheduled exercise.
    required_targets = {
        (week, day, exercise.slug)
        for week in range(1, program.week_count + 1)
        for day, template in enumerate(program.days, start=1)
        for exercise in template.exercises
    }

    if set(targets) != required_targets:
        raise ValidationFailed(
            "Targets must cover every scheduled exercise "
            "exactly, without unknown entries."
        )

    # 5. Construct explicit workout templates.
    workouts = []

    for week, scheme in enumerate(program.weeks, start=1):
        for day, template in enumerate(program.days, start=1):
            exercises = []

            for item in template.exercises:
                target = targets[(week, day, item.slug)]

                if not isinstance(target, ExerciseTarget):
                    raise ValidationFailed(
                        "Invalid exercise target specification."
                    )

                set_count = (
                    target.set_count
                    if target.set_count is not None
                    else scheme.sets
                )

                exercises.append(
                    ExerciseTemplate(
                        exercise_id=exercise_ids[item.slug],
                        set_count=set_count,
                        load_basis=target.load_basis,
                        target_reps=target.target_reps,
                        target_duration_seconds=(
                            target.target_duration_seconds
                        ),
                        target_weight_kg=target.target_weight_kg,
                        is_optional=(
                            item.role == "accessory"
                        ),
                    )
                )

            workouts.append(
                WorkoutTemplate(
                    week=week,
                    day=day,
                    phase_type=phases[(week, day)],
                    exercises=tuple(exercises),
                )
            )

    # 6. Reuse schedule validation and set expansion.
    return build_enrollment_schedule(
        ProgramSchedule(
            program_slug=program.slug,
            workouts=tuple(workouts),
        )
    )
