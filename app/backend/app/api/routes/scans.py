# Niantic posture scans shown on the exercise page

from fastapi import APIRouter

from app.api.deps import DbSession
from app.schemas.scans import ExerciseScanOut
from app.services import scans as service

router = APIRouter(tags=["scans"])

@router.get("/exercises/{exercise_id}/scans", response_model=list[ExerciseScanOut])
def exercise_scans(exercise_id: int, db: DbSession):
    return service.list_scans(db, exercise_id)
