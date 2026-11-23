"""Workout logging, history retrieval, and program summaries.

Concurrency protection:
- Acquire enrollment locks before validating prescription links
  and inserting workout history.
- Use the same ProgramInstance lock as bulk adaptation approval.
- Lock all matching user/program enrollments because historical
  WorkoutRecord rows are not enrollment-specific.
- Keep validation, record insertion, and commit in one transaction.

The adaptive progression algorithm is not modified here.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationFailed
from app.models.enums import EntryStatus, LoadBasis
from app.models.prescription import (
    PrescriptionSet,
    WorkoutPrescription,
)
from app.models.program_instance import ProgramInstance
from app.models import PerformanceEntry, User, WorkoutRecord
from app.repositories import catalog as catalog_repo
from app.repositories import workouts as repo
from app.schemas.workouts import (
    EntryOut,
    ExerciseTotals,
    ProgramSummaryOut,
    Totals,
    WeekTotals,
    WorkoutRecordIn,
    WorkoutRecordOut,
    WorkoutRecordSummary,
)


def _summary(r: WorkoutRecord, entry_count: int) -> dict:
    return dict(
        id=r.id,
        workout_session_id=r.workout_session_id,
        session_name=r.session.name if r.session else None,
        performed_at=r.performed_at,
        available_minutes=r.available_minutes,
        duration_minutes=r.duration_minutes,
        entry_count=entry_count,
        program_slug=r.program_slug,
        program_week=r.program_week,
        program_day=r.program_day,
    )


def _lock_program_enrollments(
    db: Session,
    user: User,
    data: WorkoutRecordIn,
) -> None:
    """Coordinate workout history with bulk adaptations.

    Bulk adaptation approval locks ProgramInstance first,
    then checks historical WorkoutRecord / PerformanceEntry
    rows before updating targets.

    Workout logging acquires matching ProgramInstance locks
    before checking prescription links or inserting history.

    This works even for workout entries without an explicit
    prescription_set_id, because the adaptation preview uses
    historical user/program/week/day matching.

    PostgreSQL SELECT FOR UPDATE locks persist until the
    transaction commits or rolls back.

    Multiple enrollments are locked in ascending ID order.
    """

    if data.program_slug is None:
        return

    db.scalars(
        select(ProgramInstance)
        .where(
            ProgramInstance.user_id == user.id,
            ProgramInstance.program_slug == data.program_slug,
        )
        .order_by(ProgramInstance.id)
        .with_for_update()
    ).all()


def _validate_entries(
    db: Session,
    user: User,
    data: WorkoutRecordIn,
) -> None:
    """Validate recorded performance and prescription links."""

    prescription_ids = set()
    seen_prescriptions = set()

    for entry in data.entries:
        # Skipped sets must not contain performed measurements.
        if entry.status == EntryStatus.skipped:
            if any(
                value is not None
                for value in (
                    entry.reps,
                    entry.weight_kg,
                    entry.duration_seconds,
                    entry.distance_m,
                    entry.assistance_kg,
                )
            ):
                raise ValidationFailed(
                    "Skipped sets cannot contain " "performance values."
                )

        # Substitution must reference a different exercise.
        if entry.substituted_for_exercise_id is not None:
            if entry.substituted_for_exercise_id == entry.exercise_id:
                raise ValidationFailed(
                    "A substitution must use a " "different exercise."
                )

        if entry.status == EntryStatus.substituted:
            if entry.substituted_for_exercise_id is None:
                raise ValidationFailed(
                    "Substituted entries require " "the original exercise."
                )

        # Assistance only makes sense for assisted loading.
        if entry.assistance_kg is not None:
            if entry.load_basis != LoadBasis.assisted:
                raise ValidationFailed("Assistance requires " "load_basis='assisted'.")

        if (
            entry.load_basis == LoadBasis.assisted
            and entry.status != EntryStatus.skipped
            and entry.assistance_kg is None
        ):
            raise ValidationFailed("Assisted sets require assistance_kg.")

        if entry.prescription_set_id is not None:
            if entry.prescription_set_id in seen_prescriptions:
                raise ValidationFailed(
                    "A prescription set cannot be recorded "
                    "twice in the same workout."
                )

            seen_prescriptions.add(entry.prescription_set_id)
            prescription_ids.add(entry.prescription_set_id)

    if not prescription_ids:
        return

    # Prescription-linked entries must identify their
    # scheduled program day.
    if (
        data.program_slug is None
        or data.program_week is None
        or data.program_day is None
    ):
        raise ValidationFailed(
            "Prescription-linked entries require " "program, week, and day."
        )

    statement = (
        select(PrescriptionSet, WorkoutPrescription)
        .join(
            WorkoutPrescription,
            PrescriptionSet.workout_prescription_id == WorkoutPrescription.id,
        )
        .where(
            PrescriptionSet.id.in_(prescription_ids),
            WorkoutPrescription.user_id == user.id,
        )
    )

    rows = db.execute(statement).all()

    found = {
        prescribed_set.id: (
            prescribed_set,
            prescription,
        )
        for prescribed_set, prescription in rows
    }

    if len(found) != len(prescription_ids):
        raise ValidationFailed(
            "One or more prescription sets are invalid "
            "or do not belong to this user."
        )

    for entry in data.entries:
        if entry.prescription_set_id is None:
            continue

        prescribed_set, prescription = found[entry.prescription_set_id]

        if (
            prescription.program_slug != data.program_slug
            or prescription.program_week != data.program_week
            or prescription.program_day != data.program_day
        ):
            raise ValidationFailed("Prescription does not match " "this program day.")

        if (
            prescription.workout_session_id is not None
            and prescription.workout_session_id != data.workout_session_id
        ):
            raise ValidationFailed(
                "Prescription does not match " "this workout session."
            )

        if entry.set_number != prescribed_set.set_number:
            raise ValidationFailed("Set number does not match its prescription.")

        # The performed exercise may differ if substituted.
        original_exercise_id = (
            entry.substituted_for_exercise_id
            if entry.substituted_for_exercise_id is not None
            else entry.exercise_id
        )

        if original_exercise_id != prescribed_set.exercise_id:
            raise ValidationFailed("Exercise does not match its prescription.")


def create_record(
    db: Session,
    user: User,
    data: WorkoutRecordIn,
) -> WorkoutRecordOut:
    """Validate and atomically persist workout history.

    Enrollment locks must be acquired before any
    prescription-linked validation or history insertion.

    All changes commit together. Failures roll back.
    """

    try:
        # ----------------------------------------------
        # 1. Acquire shared concurrency boundary
        # ----------------------------------------------

        _lock_program_enrollments(db, user, data)

        # ----------------------------------------------
        # 2. Validate workout session and exercise IDs
        # ----------------------------------------------

        if (
            data.workout_session_id is not None
            and catalog_repo.get_workout_session(
                db,
                data.workout_session_id,
            )
            is None
        ):
            raise ValidationFailed("workout_session_id does not exist.")

        wanted = {entry.exercise_id for entry in data.entries}

        wanted |= {
            entry.substituted_for_exercise_id
            for entry in data.entries
            if entry.substituted_for_exercise_id is not None
        }

        missing = wanted - catalog_repo.existing_exercise_ids(
            db,
            wanted,
        )

        if missing:
            raise ValidationFailed(
                "Unknown exercise ids: "
                + ", ".join(str(item) for item in sorted(missing))
            )

        # ----------------------------------------------
        # 3. Validate performance and prescription links
        # ----------------------------------------------

        _validate_entries(db, user, data)

        # ----------------------------------------------
        # 4. Build performance entries
        # ----------------------------------------------

        entries = []

        for entry in data.entries:
            values = entry.model_dump()

            values["status"] = entry.status.value
            values["observation_type"] = entry.observation_type.value
            values["load_basis"] = (
                entry.load_basis.value if entry.load_basis is not None else None
            )

            if entry.substituted_for_exercise_id is not None:
                values["is_user_modified"] = True

            entries.append(PerformanceEntry(**values))

        # ----------------------------------------------
        # 5. Create workout and its performed sets
        # ----------------------------------------------

        record = WorkoutRecord(
            user_id=user.id,
            workout_session_id=data.workout_session_id,
            performed_at=(data.performed_at or datetime.now(timezone.utc)),
            available_minutes=data.available_minutes,
            duration_minutes=data.duration_minutes,
            notes=data.notes,
            program_slug=data.program_slug,
            program_week=data.program_week,
            program_day=data.program_day,
            entries=entries,
        )

        repo.add_record(db, record)

        # ----------------------------------------------
        # 6. Atomic persistence
        # ----------------------------------------------

        db.flush()
        record_id = record.id
        db.commit()

    except Exception:
        db.rollback()
        raise

    return get_record(db, user, record_id)


def list_history(
    db: Session,
    user: User,
    limit: int,
    offset: int,
) -> tuple:
    rows, counts, total = repo.list_records(
        db,
        user.id,
        limit,
        offset,
    )

    return [
        WorkoutRecordSummary(
            **_summary(
                record,
                counts.get(record.id, 0),
            )
        )
        for record in rows
    ], total


def get_record(
    db: Session,
    user: User,
    record_id: int,
) -> WorkoutRecordOut:
    record = repo.get_record(
        db,
        record_id,
        user.id,
    )

    if record is None:
        raise NotFoundError("Workout record not found.")

    return WorkoutRecordOut(
        **_summary(
            record,
            len(record.entries),
        ),
        notes=record.notes,
        entries=[
            EntryOut(
                id=entry.id,
                exercise_id=entry.exercise_id,
                exercise_name=entry.exercise.name,
                set_number=entry.set_number,
                reps=entry.reps,
                weight_kg=entry.weight_kg,
                duration_seconds=entry.duration_seconds,
                distance_m=entry.distance_m,
                status=entry.status,
                substituted_for_exercise_id=(entry.substituted_for_exercise_id),
                prescription_set_id=(entry.prescription_set_id),
                observation_type=entry.observation_type,
                load_basis=entry.load_basis,
                assistance_kg=entry.assistance_kg,
                is_user_modified=entry.is_user_modified,
            )
            for entry in record.entries
        ],
    )


TOTAL_DAYS = 20


def _blank() -> dict:
    return {
        "sets": 0,
        "reps": 0,
        "volume_kg": 0.0,
        "seconds": 0,
    }


def _add(bucket: dict, entry) -> None:
    bucket["sets"] += 1
    bucket["reps"] += entry.reps or 0
    bucket["volume_kg"] += (entry.reps or 0) * (entry.weight_kg or 0)
    bucket["seconds"] += entry.duration_seconds or 0


def program_summary(
    db: Session,
    user: User,
    slug: str,
) -> ProgramSummaryOut:
    """Summarize latest performed exercise attempts.

    Only completed sets contribute to totals.
    A day counts as completed only with completed work.
    """

    latest = {}

    for record in repo.program_records(
        db,
        user.id,
        slug,
    ):
        exercise_ids = {entry.exercise_id for entry in record.entries}

        for exercise_id in exercise_ids:
            key = (
                record.program_week or 0,
                record.program_day or 0,
                exercise_id,
            )
            latest[key] = record

    totals = _blank()
    weeks = {}
    week_days = {}
    exercises = {}
    completed_days = set()

    for (
        week,
        day,
        exercise_id,
    ), record in latest.items():

        completed_entries = [
            entry
            for entry in record.entries
            if (
                entry.exercise_id == exercise_id
                and entry.status == EntryStatus.completed.value
            )
        ]

        if not completed_entries:
            continue

        completed_days.add((week, day))
        week_days.setdefault(week, set()).add(day)

        week_totals = weeks.setdefault(
            week,
            _blank(),
        )

        exercise_totals = exercises.setdefault(
            exercise_id,
            {
                "name": completed_entries[0].exercise.name,
                **_blank(),
            },
        )

        for entry in completed_entries:
            for bucket in (
                totals,
                week_totals,
                exercise_totals,
            ):
                _add(bucket, entry)

    return ProgramSummaryOut(
        program=slug,
        days_completed=len(completed_days),
        days_total=TOTAL_DAYS,
        totals=Totals(**totals),
        weeks=[
            WeekTotals(
                week=week,
                days_completed=len(week_days[week]),
                **values,
            )
            for week, values in sorted(weeks.items())
        ],
        exercises=[
            ExerciseTotals(
                exercise_id=exercise_id,
                **values,
            )
            for exercise_id, values in sorted(exercises.items())
        ],
    )
