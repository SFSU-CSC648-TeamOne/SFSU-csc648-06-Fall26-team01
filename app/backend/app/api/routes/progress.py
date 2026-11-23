"""Authenticated progress-analysis endpoints."""

from typing import Annotated, Literal

from fastapi import APIRouter, Path, Query
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, DbSession
from app.services.progress_analysis import (
    analyze_exercise_progress,
    analyze_movement_group_progress,
)

router = APIRouter(
    prefix="/progress",
    tags=["progress"],
)


class ProgressPoint(BaseModel):
    date: str
    prescribed: float | None
    actual: float


class ExerciseTrend(BaseModel):
    exercise_id: int
    observation_type: Literal["training", "benchmark"]
    set_number: int
    metric: Literal["reps", "seconds"]
    load_basis: str

    weight_kg: float | None
    assistance_kg: float | None

    observation_count: int

    confidence: Literal[
        "insufficient",
        "preliminary",
        "robust",
    ]

    change_pct: float | None
    slope_per_observation: float | None

    points: list[ProgressPoint]


class ExerciseProgressResponse(BaseModel):
    exercise_id: int
    observation_type: Literal["training", "benchmark"]
    trends: list[ExerciseTrend]


class MovementGroupProgress(BaseModel):
    id: int
    name: str

    change_pct: float | None

    exercise_count: int = Field(ge=0)
    observation_count: int = Field(ge=0)

    confidence: Literal[
        "insufficient",
        "preliminary",
        "robust",
    ]

    explanation: str | None = None


@router.get(
    "/movement-groups",
    response_model=list[MovementGroupProgress],
)
def get_movement_group_progress(
    user: CurrentUser,
    db: DbSession,
):
    """
    Return movement-group progress for the current user.

    Only completed, comparable training observations
    contribute to movement-group trends.

    Results are descriptive and do not change
    exercise prescriptions.
    """

    return analyze_movement_group_progress(
        db=db,
        user_id=user.id,
    )


@router.get(
    "/exercises/{exercise_id}",
    response_model=ExerciseProgressResponse,
)
def get_exercise_progress(
    user: CurrentUser,
    db: DbSession,
    exercise_id: Annotated[int, Path(gt=0)],
    observation_type: Annotated[
        Literal["training", "benchmark"],
        Query(),
    ] = "training",
):
    """
    Return comparable exercise-performance trends.

    Only the authenticated user's history is analyzed.
    Training and benchmark observations remain separate.
    """

    trends = analyze_exercise_progress(
        db=db,
        user_id=user.id,
        exercise_id=exercise_id,
        observation_type=observation_type,
    )

    return ExerciseProgressResponse(
        exercise_id=exercise_id,
        observation_type=observation_type,
        trends=trends,
    )
