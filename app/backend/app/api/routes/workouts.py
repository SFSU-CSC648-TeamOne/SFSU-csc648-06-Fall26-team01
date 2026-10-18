from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import Page
from app.schemas.workouts import WorkoutRecordIn, WorkoutRecordOut, WorkoutRecordSummary
from app.services import workouts as service

router = APIRouter(prefix="/workout-records", tags=["workouts"])

@router.post("", response_model=WorkoutRecordOut, status_code=status.HTTP_201_CREATED)
def log_workout(body: WorkoutRecordIn, user: CurrentUser, db: DbSession):
    return service.create_record(db, user, body)

@router.get("", response_model=Page[WorkoutRecordSummary])
def workout_history(
    user: CurrentUser, db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    items, total = service.list_history(db, user, limit, offset)
    return Page(items=items, total=total, limit=limit, offset=offset)

@router.get("/{record_id}", response_model=WorkoutRecordOut)
def workout_record(record_id: int, user: CurrentUser, db: DbSession):
    return service.get_record(db, user, record_id)