from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.scans import ExerciseScan

def list_scans(db: Session, exercise_id: int) -> list:
    return list(db.scalars(select(ExerciseScan).where(ExerciseScan.exercise_id == exercise_id)
                           .order_by(ExerciseScan.position)))
