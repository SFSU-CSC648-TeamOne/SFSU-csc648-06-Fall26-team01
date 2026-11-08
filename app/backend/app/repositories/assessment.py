# user's logged in sets and wger exercises that
# correspond to the assessment's exercise type

from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Exercise, ExerciseMuscle, PerformanceEntry, WorkoutRecord

# workout records and performance entries for a user, optionally filtered by program slug
def program_entries(db: Session, user_id: int, slug: Optional[str]) -> list:
    stmt = (select(WorkoutRecord, PerformanceEntry)
            .join(PerformanceEntry, PerformanceEntry.workout_record_id == WorkoutRecord.id)
            .where(WorkoutRecord.user_id == user_id))
    if slug:
        stmt = stmt.where(WorkoutRecord.program_slug == slug)
    return list(db.execute(stmt).all())


def exercises_by_ids(db: Session, ids: set) -> Dict[int, Exercise]:
    if not ids:
        return {}
    rows = db.scalars(select(Exercise)
                      .options(selectinload(Exercise.muscle_links).selectinload(ExerciseMuscle.muscle))
                      .where(Exercise.id.in_(ids)))
    return {e.id: e for e in rows}