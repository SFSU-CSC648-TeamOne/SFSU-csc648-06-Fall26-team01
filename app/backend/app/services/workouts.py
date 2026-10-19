# rules that validate, save, and keeps private records of teh user

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationFailed
from app.models import PerformanceEntry, User, WorkoutRecord
from app.repositories import catalog as catalog_repo
from app.repositories import workouts as repo
from app.schemas.workouts import (EntryOut, WorkoutRecordIn, WorkoutRecordOut,
                                  WorkoutRecordSummary)

def _summary(r: WorkoutRecord, entry_count: int) -> dict:
    return dict(
        id=r.id, workout_session_id=r.workout_session_id,
        session_name=r.session.name if r.session else None, performed_at=r.performed_at,
        available_minutes=r.available_minutes, duration_minutes=r.duration_minutes,
        entry_count=entry_count)

def create_record(db: Session, user: User, data: WorkoutRecordIn) -> WorkoutRecordOut:
    if data.workout_session_id is not None and catalog_repo.get_workout_session(db, data.workout_session_id) is None:
        raise ValidationFailed("workout_session_id does not exist.")

    wanted = {e.exercise_id for e in data.entries}
    wanted |= {e.substituted_for_exercise_id for e in data.entries if e.substituted_for_exercise_id}
    missing = wanted - catalog_repo.existing_exercise_ids(db, wanted)
    if missing:
        raise ValidationFailed("Unknown exercise ids: " + ", ".join(str(m) for m in sorted(missing)))

    record = WorkoutRecord(
        user_id=user.id, workout_session_id=data.workout_session_id,
        performed_at=data.performed_at or datetime.now(timezone.utc),
        available_minutes=data.available_minutes, duration_minutes=data.duration_minutes,
        notes=data.notes,
        entries=[PerformanceEntry(**{**e.model_dump(), "status": e.status.value}) for e in data.entries])
    repo.add_record(db, record)
    db.commit()
    return get_record(db, user, record.id)

def list_history(db: Session, user: User, limit: int, offset: int) -> tuple:
    rows, counts, total = repo.list_records(db, user.id, limit, offset)
    return [WorkoutRecordSummary(**_summary(r, counts.get(r.id, 0))) for r in rows], total

def get_record(db: Session, user: User, record_id: int) -> WorkoutRecordOut:
    r = repo.get_record(db, record_id, user.id)
    if r is None:  # also 404 for other people's records, so ids can't be looked at
        raise NotFoundError("Workout record not found.")
    return WorkoutRecordOut(
        **_summary(r, len(r.entries)), notes=r.notes,
        entries=[EntryOut(
            id=e.id, exercise_id=e.exercise_id, exercise_name=e.exercise.name, set_number=e.set_number,
            reps=e.reps, weight_kg=e.weight_kg, duration_seconds=e.duration_seconds,
            distance_m=e.distance_m, status=e.status,
            substituted_for_exercise_id=e.substituted_for_exercise_id) for e in r.entries])