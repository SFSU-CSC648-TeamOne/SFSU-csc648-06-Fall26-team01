# workout queries
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from app.models import PerformanceEntry, WorkoutRecord

def add_record(db: Session, record: WorkoutRecord) -> WorkoutRecord:
    db.add(record)
    db.flush()
    return record

def list_records(db: Session, user_id: int, limit: int, offset: int) -> tuple:
    """Returns (records, {record_id: entry_count}, total) for one user, newest first."""
    base = select(WorkoutRecord).where(WorkoutRecord.user_id == user_id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = list(db.scalars(base.options(selectinload(WorkoutRecord.session))
                           .order_by(WorkoutRecord.performed_at.desc(), WorkoutRecord.id.desc())
                           .limit(limit).offset(offset)))
    counts: dict = {}
    if rows:
        counts = dict(db.execute(
            select(PerformanceEntry.workout_record_id, func.count())
            .where(PerformanceEntry.workout_record_id.in_([r.id for r in rows]))
            .group_by(PerformanceEntry.workout_record_id)).all())
    return rows, counts, total

def get_record(db: Session, record_id: int, user_id: int) -> Optional[WorkoutRecord]:
    return db.scalar(
        select(WorkoutRecord)
        .options(selectinload(WorkoutRecord.session),
                 selectinload(WorkoutRecord.entries).selectinload(PerformanceEntry.exercise))
        .where(WorkoutRecord.id == record_id, WorkoutRecord.user_id == user_id))