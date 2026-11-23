"""Create an enrollment and its persisted training schedule.

The caller must supply a trusted, explicitly classified
program schedule. This service does not determine program
phases or calculate assessment-based prescriptions.

All enrollment records, prescriptions, sets, and phases
are committed together or rolled back together.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationFailed
from app.models.catalog import Exercise, WorkoutSession
from app.models.enums import LoadBasis, PrescriptionStatus
from app.models.program_baseline import ProgramBaseline
from app.models.program_instance import ProgramInstance
from app.models.program_phase import ProgramPhase, ProgramPhaseType
from app.models.prescription import PrescriptionSet, WorkoutPrescription
from app.models.users import User

ENGINE_VERSION = "adaptive-v1"


@dataclass(frozen=True)
class EnrollmentSet:
    exercise_id: int
    set_number: int
    load_basis: str
    target_reps: int | None = None
    target_duration_seconds: int | None = None
    target_weight_kg: Decimal | None = None
    is_optional: bool = False


@dataclass(frozen=True)
class EnrollmentWorkout:
    program_week: int
    program_day: int
    phase_type: str
    sets: tuple[EnrollmentSet, ...]
    workout_session_id: int | None = None
    phase_reason: str | None = None


def _validate_set(item: EnrollmentSet) -> None:
    if item.exercise_id <= 0 or item.set_number <= 0:
        raise ValidationFailed("Exercise IDs and set numbers must be positive.")

    allowed = {basis.value for basis in LoadBasis}
    if item.load_basis not in allowed:
        raise ValidationFailed("Invalid load basis.")

    if item.target_reps is not None:
        if isinstance(item.target_reps, bool) or item.target_reps <= 0:
            raise ValidationFailed("Target repetitions must be positive.")

    if item.target_duration_seconds is not None:
        if (
            isinstance(item.target_duration_seconds, bool)
            or item.target_duration_seconds <= 0
        ):
            raise ValidationFailed("Target duration must be positive.")

    if item.target_reps is not None and item.target_duration_seconds is not None:
        raise ValidationFailed("A set cannot prescribe both repetitions and duration.")

    if item.target_reps is None and item.target_duration_seconds is None:
        raise ValidationFailed("Each set requires repetitions or duration.")

    if item.target_weight_kg is not None:
        try:
            weight = Decimal(str(item.target_weight_kg))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValidationFailed("Invalid target weight.") from exc

        if (
            not weight.is_finite()
            or weight <= 0
            or weight > Decimal("9999.99")
            or weight != weight.quantize(Decimal("0.01"))
        ):
            raise ValidationFailed(
                "Target weight must be positive and fit Numeric(6,2)."
            )

        if item.load_basis not in {
            LoadBasis.external.value,
            LoadBasis.added.value,
        }:
            raise ValidationFailed(
                "Only external or added loading may have a weight target."
            )

    if (
        item.load_basis
        in {
            LoadBasis.external.value,
            LoadBasis.added.value,
        }
        and item.target_weight_kg is None
    ):
        raise ValidationFailed("External and added loading require a weight target.")

    if item.load_basis == LoadBasis.assisted.value:
        raise ValidationFailed("Assisted targets are deferred in the current schema.")


def _validate_schedule(
    workouts: tuple[EnrollmentWorkout, ...],
) -> None:
    if not workouts:
        raise ValidationFailed("An enrollment requires at least one workout.")

    valid_phases = {phase.value for phase in ProgramPhaseType}
    seen_days = set()

    for workout in workouts:
        if workout.program_week <= 0 or workout.program_day <= 0:
            raise ValidationFailed("Program week and day must be positive.")

        day_key = (
            workout.program_week,
            workout.program_day,
        )

        if day_key in seen_days:
            raise ValidationFailed("Duplicate program week and day.")

        seen_days.add(day_key)

        if workout.phase_type not in valid_phases:
            raise ValidationFailed(
                "Every workout requires a valid phase classification."
            )

        if workout.workout_session_id is not None and workout.workout_session_id <= 0:
            raise ValidationFailed("Workout session ID must be positive.")

        if not workout.sets:
            raise ValidationFailed("Every scheduled workout requires prescribed sets.")

        seen_sets = set()

        for item in workout.sets:
            _validate_set(item)

            set_key = (item.exercise_id, item.set_number)

            if set_key in seen_sets:
                raise ValidationFailed("Duplicate exercise and set number in workout.")

            seen_sets.add(set_key)


def create_program_enrollment(
    db: Session,
    *,
    user_id: int,
    program_slug: str,
    workouts: tuple[EnrollmentWorkout, ...],
    source_baseline_id: int | None = None,
    engine_version: str = ENGINE_VERSION,
) -> ProgramInstance:
    """Persist one program run and its complete schedule.

    Caller responsibilities:
    - Supply a trusted schedule generated from program metadata.
    - Handle enrollment request idempotency at the API boundary.

    This operation owns its commit/rollback boundary.
    """

    if user_id <= 0:
        raise ValidationFailed("Invalid user ID.")

    if not program_slug or len(program_slug) > 20:
        raise ValidationFailed("Invalid program slug.")

    if not engine_version or len(engine_version) > 30:
        raise ValidationFailed("Invalid engine version.")

    _validate_schedule(workouts)

    exercise_ids = {item.exercise_id for workout in workouts for item in workout.sets}

    session_ids = {
        workout.workout_session_id
        for workout in workouts
        if workout.workout_session_id is not None
    }

    try:
        user = db.get(User, user_id)

        if user is None:
            raise NotFoundError("User not found.")

        if source_baseline_id is not None:
            baseline = db.get(
                ProgramBaseline,
                source_baseline_id,
            )

            if baseline is None:
                raise NotFoundError("Program baseline not found.")

            if baseline.user_id != user_id or baseline.program_slug != program_slug:
                raise ValidationFailed(
                    "Baseline does not belong to this user and program."
                )

        found_exercises = set(
            db.scalars(select(Exercise.id).where(Exercise.id.in_(exercise_ids))).all()
        )

        if found_exercises != exercise_ids:
            raise ValidationFailed("Schedule contains unknown exercises.")

        if session_ids:
            found_sessions = set(
                db.scalars(
                    select(WorkoutSession.id).where(WorkoutSession.id.in_(session_ids))
                ).all()
            )

            if found_sessions != session_ids:
                raise ValidationFailed("Schedule contains unknown workout sessions.")

        instance = ProgramInstance(
            user_id=user_id,
            program_slug=program_slug,
            source_baseline_id=source_baseline_id,
        )

        db.add(instance)
        db.flush()

        for workout in workouts:
            prescription = WorkoutPrescription(
                user_id=user_id,
                program_instance_id=instance.id,
                workout_session_id=workout.workout_session_id,
                program_slug=program_slug,
                program_week=workout.program_week,
                program_day=workout.program_day,
                status=PrescriptionStatus.planned.value,
                engine_version=engine_version,
                source_baseline_id=source_baseline_id,
            )

            db.add(prescription)
            db.flush()

            db.add(
                ProgramPhase(
                    workout_prescription_id=prescription.id,
                    phase_type=workout.phase_type,
                    reason=workout.phase_reason,
                )
            )

            for item in workout.sets:
                db.add(
                    PrescriptionSet(
                        workout_prescription_id=prescription.id,
                        exercise_id=item.exercise_id,
                        set_number=item.set_number,
                        target_reps=item.target_reps,
                        target_duration_seconds=(item.target_duration_seconds),
                        target_weight_kg=item.target_weight_kg,
                        load_basis=item.load_basis,
                        is_optional=item.is_optional,
                    )
                )

        db.commit()
        db.refresh(instance)

        return instance

    except Exception:
        db.rollback()
        raise
