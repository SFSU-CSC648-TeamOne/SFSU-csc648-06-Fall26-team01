from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db # use routes from other imports
from app.models import Exercise
from app.models.media import ExerciseModel
from app.schemas.media import ExerciseModelOut

router = APIRouter(tag=["3d models"])

def _out(model: ExerciseModel, name: str) -> ExerciseModelOut:
    return ExerciseModelOut(
        exercise_id=model.exercise_id, exercise_name=name, model_url=model.model_url,
        animation_name=model.animation_name, credit=model.credit,
    )

@router.get("/exercise-models", response_model=List[ExerciseModelOut])
def list_models(db: Session = Depends(get_db)):
    # exercises have a 3D demo (maybe, use to fill demo-day picker)
    rows = db.execute(
        select(ExerciseModel, Exercise.name)
        .join(Exercise, Exercise.id == ExerciseModel.exercise_id)
        .order_by(Exercise.name)
    ).all()
    return [_out(m, n) for m, in rows]

@router.get("/exercises/{exercise_id}/model", response_model=ExerciseModelOut)
def get_model(exercise_id: int, db: Session = Depends(get_db)):
    row = db.execute(
        select(ExerciseModel, Exercise.name)
        .join(Exercise, Exercise.id == ExerciseModel.exercise_id)
        .where(ExerciseModel.exercise_id == exercise_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="No 3D model for this exercise")
    return _out(*row)