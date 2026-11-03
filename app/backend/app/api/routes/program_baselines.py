
from datetime import datetime
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.errors import ValidationFailed
from app.models.program_baseline import ProgramBaseline

router = APIRouter(
    prefix="/program-baselines",
    tags=["program-baselines"],
)

TESTS = {
    "bw": [
        {
            "id": "push-up",
            "name": "Push-Up",
            "metric": "reps",
            "weighted": False,
        },
        {
            "id": "bodyweight-squat",
            "name": "Bodyweight Squat",
            "metric": "reps",
            "weighted": False,
        },
        {
            "id": "plank",
            "name": "Plank",
            "metric": "seconds",
            "weighted": False,
        },
    ],
    "ldw": [
        {
            "id": "barbell-bench-press",
            "name": "Barbell Bench Press",
            "metric": "reps",
            "weighted": True,
        },
        {
            "id": "barbell-back-squat",
            "name": "Barbell Back Squat",
            "metric": "reps",
            "weighted": True,
        },
        {
            "id": "romanian-deadlift",
            "name": "Romanian Deadlift",
            "metric": "reps",
            "weighted": True,
        },
    ],
}


class TestOut(BaseModel):
    id: str
    name: str
    metric: Literal["reps", "seconds"]
    weighted: bool


class ResultIn(BaseModel):
    exercise_id: str
    value: int = Field(ge=0, le=10000)
    load_kg: float | None = Field(default=None, ge=0, le=1000)


class BaselineIn(BaseModel):
    program_slug: Literal["bw", "ldw"]
    results: list[ResultIn]


class BaselineOut(BaseModel):
    id: int
    program_slug: str
    attempt_id: str
    results: list[ResultIn]
    created_at: datetime


@router.get("/tests", response_model=list[TestOut])
def get_tests(program: Literal["bw", "ldw"] = Query(...)):
    return TESTS[program]


@router.get("/latest", response_model=BaselineOut | None)
def latest_baseline(
    program: Literal["bw", "ldw"],
    user: CurrentUser,
    db: DbSession,
):
    return db.scalar(
        select(ProgramBaseline)
        .where(
            ProgramBaseline.user_id == user.id,
            ProgramBaseline.program_slug == program,
        )
        .order_by(
            ProgramBaseline.created_at.desc(),
            ProgramBaseline.id.desc(),
        )
        .limit(1)
    )


@router.post(
    "",
    response_model=BaselineOut,
    status_code=status.HTTP_201_CREATED,
)
def create_baseline(
    body: BaselineIn,
    user: CurrentUser,
    db: DbSession,
):
    expected = {test["id"]: test for test in TESTS[body.program_slug]}

    received = [result.exercise_id for result in body.results]

    if len(received) != len(expected) or set(received) != set(expected):
        raise ValidationFailed(
            "Submit exactly one result for each required exercise."
        )

    for result in body.results:
        test = expected[result.exercise_id]

        if test["weighted"]:
            if result.load_kg is None:
                raise ValidationFailed(
                    f"{test['name']} requires a recorded load."
                )
        elif result.load_kg is not None:
            raise ValidationFailed(
                f"{test['name']} does not require a load."
            )

    record = ProgramBaseline(
        user_id=user.id,
        program_slug=body.program_slug,
        attempt_id=str(uuid4()),
        results=[result.model_dump() for result in body.results],
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return record
