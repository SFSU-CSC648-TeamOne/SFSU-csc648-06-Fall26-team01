# endpoints for searching exercises by name, muscle, equipment and difficulty,
# listing the filter options, and searching programs by goal and length

from typing import Annotated, Optional

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.models.enums import ExperienceLevel
from app.schemas.catalog import (ExerciseOut, NamedOut, ProgramOut, 
                                WorkoutDetailOut, WorkoutSummaryOut)
from app.schemas.common import Page
from app.services import catalog as service

router = APIRouter(tags=["catalog"])

Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]

@router.get("/exercises", response_model=Page[ExerciseOut])
def list_exercises(
    db: DbSession,
    q: Optional[str] = Query(None, max_length=100, description="name contains"),
    muscle: Optional[str] = None,
    equipment: Optional[str] = None,
    difficulty: Optional[ExperienceLevel] = None,
    limit: Limit = 20,
    offset: Offset = 0,
):
    items, total = service.search_exercises(
        db, q=q, muscle=muscle, equipment=equipment,
        difficulty=difficulty.value if difficulty else None, limit=limit, offset=offset)
    return Page(items=items, total=total, limit=limit, offset=offset)

@router.get("/exercises/{exercise_id}", response_model=ExerciseOut)
def exercise_detail(exercise_id: int, db: DbSession):
    return service.get_exercise(db, exercise_id)

@router.get("/equipment", response_model=list[NamedOut])
def equipment(db: DbSession):
    return service.list_equipment(db)

@router.get("/muscle-groups", response_model=list[NamedOut])
def muscle_groups(db: DbSession):
    return service.list_muscle_groups(db)

@router.get("/programs", response_model=Page[ProgramOut])
def list_programs(
    db: DbSession,
    goal: Optional[str] = Query(None, max_length=100),
    max_weeks: Optional[int] = Query(None, ge=1),
    limit: Limit = 20,
    offset: Offset = 0,
):
    items, total = service.search_programs(
        db, goal=goal, max_weeks=max_weeks, limit=limit, offset=offset)
    return Page(items=items, total=total, limit=limit, offset=offset)

@router.get("/workout-sessions", response_model=Page[WorkoutSummaryOut])
def list_workout_sessions(
    db: DbSession,
    muscle: Optional[str] = Query(None, description="muscle group name"),
    difficulty: Optional[ExperienceLevel] = None,
    max_minutes: Optional[int] = Query(None, ge=1, le=600, description="expected length, up to"),
    limit: Limit = 20,
    offset: Offset = 0,
):
    items, total = service.search_workout_sessions(
        db, muscle=muscle, difficulty=difficulty.value if difficulty else None,
        max_minutes=max_minutes, limit=limit, offset=offset)
    return Page(items=items, total=total, limit=limit, offset=offset)

@router.get("/workout-sessions/{session_id}", response_model=WorkoutDetailOut)
def workout_session_detail(session_id: int, db: DbSession):
    return service.get_workout_session(db, session_id)