# validates, saves, and keeps private records of teh user

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationFailed
from app.models.enums import EntryStatus
from app.models import PerformanceEntry, User, WorkoutRecord
from app.repositories import catalog as catalog_repo
from app.repositories import workouts as repo
from app.schemas.workouts import (EntryOut, ExerciseTotals, ProgramSummaryOut, Totals, WeekTotals, 
                                WorkoutRecordIn, WorkoutRecordOut, WorkoutRecordSummary)

def _summary(r: WorkoutRecord, entry_count: int) -> dict:
    return dict(
        id=r.id, workout_session_id=r.workout_session_id,
        session_name=r.session.name if r.session else None, performed_at=r.performed_at,
        available_minutes=r.available_minutes, duration_minutes=r.duration_minutes,
        entry_count=entry_count,
        program_slug=r.program_slug, program_week=r.program_week, program_day=r.program_day
        )

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
        available_minutes=data.available_minutes, duration_minutes=data.duration_minutes, notes=data.notes,
        program_slug=data.program_slug, program_week=data.program_week, program_day=data.program_day,
        entries=[PerformanceEntry(**{**e.model_dump(), "status": e.status.value}) for e in data.entries])
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
            substituted_for_exercise_id=e.substituted_for_exercise_id) for e in r.entries])

TOTAL_DAYS = 20   # 4 weeks x 5 training days (see programsData.ts)

def _blank() -> dict:
    return {"sets": 0, "reps": 0, "volume_kg": 0.0, "seconds": 0}

def _add(bucket: dict, e) -> None:
    bucket["sets"] += 1
    bucket["reps"] += e.reps or 0
    bucket["volume_kg"] += (e.reps or 0) * (e.weight_kg or 0)
    bucket["seconds"] += e.duration_seconds or 0

def program_summary(db: Session, user: User, slug: str) -> ProgramSummaryOut:
    # doing an exercise again creates a newer record, so keep only the latest per (week, day, exercise)
    latest: dict = {}
    for r in repo.program_records(db, user.id, slug):
        for ex_id in {e.exercise_id for e in r.entries}:
            latest[(r.program_week or 0, r.program_day or 0, ex_id)] = r

    totals, weeks, week_days, exercises, days = _blank(), {}, {}, {}, set()
    for (week, day, ex_id), r in latest.items():
        days.add((week, day))
        week_days.setdefault(week, set()).add(day)
        wk = weeks.setdefault(week, _blank())
        for e in r.entries:
            if e.exercise_id != ex_id or e.status != EntryStatus.completed.value:
                continue
            ex = exercises.setdefault(ex_id, {"name": e.exercise.name, **_blank()})
            for bucket in (totals, wk, ex):
                _add(bucket, e)

    return ProgramSummaryOut(
        program=slug, days_completed=len(days), days_total=TOTAL_DAYS,
        totals=Totals(**totals),
        weeks=[WeekTotals(week=w, days_completed=len(week_days[w]), **v) for w, v in sorted(weeks.items())],
        exercises=[ExerciseTotals(exercise_id=i, **v) for i, v in sorted(exercises.items())])