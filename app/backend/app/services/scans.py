from sqlalchemy.orm import Session

from app.repositories import scans as repo

def list_scans(db: Session, exercise_id: int) -> list:
    return repo.list_scans(db, exercise_id)   # empty list when nothing is uploaded yet
