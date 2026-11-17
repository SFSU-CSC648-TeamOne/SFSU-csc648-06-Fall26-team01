# validates, saves, and keeps private records of teh user

from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationFailed
from app.models.enums import EntryStatus, LoadBasis
from app.models.prescription import PrescriptionSet, WorkoutPrescription
from app.models import PerformanceEntry, User, WorkoutRecord
from app.repositories import catalog as catalog_repo
from app.repositories import workouts as repo
from app.schemas.workouts import (EntryOut, ExerciseTotals, ProgramSummaryOut, Totals, WeekTotals, 
                                WorkoutRecordIn, WorkoutRecordOut, WorkoutRecordSummary)

def _summary(r: WorkoutRecord, entry_count: int) -> dict:
    return dict( id=r.id, workout_session_id=r.workout_session_id,
        session_name=r.session.name if r.session else None, performed_at=r.performed_at,
        available_minutes=r.available_minutes, duration_minutes=r.duration_minutes,
        entry_count=entry_count,
        program_slug=r.program_slug, program_week=r.program_week, program_day=r.program_day
        )

def _validate_entries(db: Session, user: User, data: WorkoutRecordIn,
) -> None:
    """Validate recorded performance and prescription links."""

    prescription_ids = set()
    seen_prescriptions = set()

    for entry in data.entries:
        # Skipped sets must not contain performed measurements.
        if entry.status == EntryStatus.skipped:
            if any(value is not None
                for value in (entry.reps, entry.weight_kg, entry.duration_seconds, entry.distance_m,
                    entry.assistance_kg,
                )
            ):
                raise ValidationFailed("Skipped sets cannot contain performance values.")

        # Substitution must reference a different exercise.
        if entry.substituted_for_exercise_id is not None:
            if (entry.substituted_for_exercise_id
                == entry.exercise_id
            ):
                raise ValidationFailed("A substitution must use a different exercise.")

        if entry.status == EntryStatus.substituted:
            if entry.substituted_for_exercise_id is None:
                raise ValidationFailed("Substituted entries require the original exercise.")

        # Assistance only makes sense for assisted loading.
        if entry.assistance_kg is not None:
            if entry.load_basis != LoadBasis.assisted:
                raise ValidationFailed("Assistance requires load_basis='assisted'.")

        if (entry.load_basis == LoadBasis.assisted
            and entry.status != EntryStatus.skipped
            and entry.assistance_kg is None
        ):
            raise ValidationFailed("Assisted sets require assistance_kg.")

        if entry.prescription_set_id is not None:
            if entry.prescription_set_id in seen_prescriptions:
                raise ValidationFailed("A prescription set cannot be recorded twice "
                    "in the same workout."
                )

            seen_prescriptions.add(entry.prescription_set_id)
            prescription_ids.add(entry.prescription_set_id)

    if not prescription_ids:
        return

    # Prescription-linked entries need enough information to
    # establish which scheduled workout was performed.
    if (data.program_slug is None
        or data.program_week is None
        or data.program_day is None
    ):
        raise ValidationFailed("Prescription-linked entries require program, "
            "week, and day."
        )

    statement = (select(PrescriptionSet, WorkoutPrescription)
        .join(WorkoutPrescription, PrescriptionSet.workout_prescription_id
            == WorkoutPrescription.id,
        )
        .where(PrescriptionSet.id.in_(prescription_ids), WorkoutPrescription.user_id == user.id,)
    )

    rows = db.execute(statement).all()

    found = {prescription_set.id: (prescription_set, prescription,)
        for prescription_set, prescription in rows
    }

    if len(found) != len(prescription_ids):
        raise ValidationFailed("One or more prescription sets are invalid "
            "or do not belong to this user.")

    for entry in data.entries:
        if entry.prescription_set_id is None:
            continue

        prescribed_set, prescription = found[entry.prescription_set_id]

        if (prescription.program_slug != data.program_slug or prescription.program_week != data.program_week
            or prescription.program_day != data.program_day):
            raise ValidationFailed("Prescription does not match this program day.")
        if (prescription.workout_session_id is not None and prescription.workout_session_id
            != data.workout_session_id):
            raise ValidationFailed(
                "Prescription does not match this workout session.")
        
        if entry.set_number != prescribed_set.set_number:
            raise ValidationFailed("Set number does not match its prescription.")
        
        # The performed exercise may differ if substituted.
        original_exercise_id = (entry.substituted_for_exercise_id
            if entry.substituted_for_exercise_id is not None
            else entry.exercise_id)
        if original_exercise_id != prescribed_set.exercise_id:
            raise ValidationFailed("Exercise does not match its prescription.")


def create_record(
    db: Session,
    user: User,
    data: WorkoutRecordIn
) -> WorkoutRecordOut:

    if (
        data.workout_session_id is not None
        and catalog_repo.get_workout_session(
            db, data.workout_session_id
        ) is None
    ):
        raise ValidationFailed(
            "workout_session_id does not exist."
        )

    wanted = {e.exercise_id for e in data.entries}

    wanted |= {
        e.substituted_for_exercise_id
        for e in data.entries
        if e.substituted_for_exercise_id is not None
    }

    missing = wanted - catalog_repo.existing_exercise_ids(
        db, wanted
    )

    if missing:
        raise ValidationFailed(
            "Unknown exercise ids: "
            + ", ".join(str(m) for m in sorted(missing))
        )

    _validate_entries(db, user, data)

    entries = []

    for e in data.entries:
        values = e.model_dump()

        # Convert enums to database-compatible strings.
        values["status"] = e.status.value
        values["observation_type"] = e.observation_type.value
        values["load_basis"] = (
            e.load_basis.value
            if e.load_basis is not None
            else None
        )

        if e.substituted_for_exercise_id is not None:
            values["is_user_modified"] = True

        entries.append(PerformanceEntry(**values))

    record = WorkoutRecord(
        user_id=user.id,
        workout_session_id=data.workout_session_id,
        performed_at=(
            data.performed_at
            or datetime.now(timezone.utc)
        ),
        available_minutes=data.available_minutes,
        duration_minutes=data.duration_minutes,
        notes=data.notes,
        program_slug=data.program_slug,
        program_week=data.program_week,
        program_day=data.program_day,
        entries=entries,
    )

    repo.add_record(db, record)
    db.commit()

    return get_record(db, user, record.id)


def list_history(db: Session, user: User, limit: int, offset: int) -> tuple:
    rows, counts, total = repo.list_records(db, user.id, limit, offset)
    return [WorkoutRecordSummary(**_summary(r, counts.get(r.id, 0))) for r in rows], total

def get_record(db: Session, user: User, record_id: int) -> WorkoutRecordOut:
    r = repo.get_record(db, record_id, user.id)
    if r is None:  # also 404 for other people's records, so ids can't be probed
        raise NotFoundError("Workout record not found.")
    return WorkoutRecordOut(
        **_summary(r, len(r.entries)), notes=r.notes,
        entries=[EntryOut(
            id=e.id, exercise_id=e.exercise_id, exercise_name=e.exercise.name, set_number=e.set_number,
            reps=e.reps, weight_kg=e.weight_kg, duration_seconds=e.duration_seconds,
            distance_m=e.distance_m, status=e.status,
            substituted_for_exercise_id=(e.substituted_for_exercise_id),
            prescription_set_id=e.prescription_set_id, observation_type=e.observation_type,
            load_basis=e.load_basis, assistance_kg=e.assistance_kg, is_user_modified=e.is_user_modified,)
            for e in r.entries
            ])

TOTAL_DAYS = 20   # 4 weeks x 5 training days (see programsData.ts)

def _blank() -> dict:
    return {"sets": 0, "reps": 0, "volume_kg": 0.0, "seconds": 0}

def _add(bucket: dict, e) -> None:
    bucket["sets"] += 1
    bucket["reps"] += e.reps or 0
    bucket["volume_kg"] += (e.reps or 0) * (e.weight_kg or 0)
    bucket["seconds"] += e.duration_seconds or 0


def program_summary(db: Session, user: User, slug: str,) -> ProgramSummaryOut:
    """
    Summarize the latest recorded attempt for each exercise
    within each program week and day.

    Only completed sets contribute to totals.
    A day counts as completed only if it has completed work.
    """

    latest = {}
    # Repository returns records in chronological order.
    # Later attempts replace earlier attempts of the same
    # exercise within the same program day.
    for record in repo.program_records(db, user.id, slug):
        for exercise_id in {entry.exercise_id for entry in record.entries}:
            key = (record.program_week or 0, record.program_day or 0, exercise_id,)
            latest[key] = record

    totals = _blank()
    weeks = {}
    week_days = {}
    exercises = {}
    completed_days = set()

    for (week, day, exercise_id), record in latest.items():
        completed_entries = [entry for entry in record.entries
            if (entry.exercise_id == exercise_id and entry.status == EntryStatus.completed.value)]
        # Skipped-only attempts contribute no training volume
        # and do not establish a completed training day.
        if not completed_entries: continue

        completed_days.add((week, day))
        week_days.setdefault(week, set()).add(day)
        week_totals = weeks.setdefault(week, _blank())
        exercise_totals = exercises.setdefault(exercise_id,
            {"name": completed_entries[0].exercise.name, **_blank(),},
        )

        for entry in completed_entries:
            for bucket in (totals, week_totals, exercise_totals,):
                _add(bucket, entry)

    return ProgramSummaryOut(
        program=slug,
        days_completed=len(completed_days),
        days_total=TOTAL_DAYS,
        totals=Totals(**totals),
        weeks=[WeekTotals(week=week, days_completed=len(week_days[week]), **values,)
            for week, values in sorted(weeks.items())],
        exercises=[ExerciseTotals(exercise_id=exercise_id, **values,)
            for exercise_id, values in sorted(exercises.items())
        ],
    )
