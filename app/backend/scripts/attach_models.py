# links .glb files to exercises (if any)

from sqlalchemy import select

import app.models
from app.db.session import SessionLocal
from app.models import Exercise
from app.models.media import ExerciseModel

# exercise names (must match wger id names)
MODELS = {
    "Squats": dict(             # haven't found hercules squat in wger
        model_url="/about/Scaniverse%202026-10-15%20121405.glb",
        video_url="/about/demo_one.mp4",
        animation_name=None,
        credit="Scan by our team",
    ),
    "Pistol Squat": dict(       # exercise id 142 - pistol squat
        model_url="/about/Scaniverse%202026-10-15%20121405.glb",
        video_url="/about/demo_two.mp4",
        animation_name=None,
        credit="Scan by our team",
    ),
}

def main() -> None:
    with SessionLocal() as db:
        try:
            for name, fields in MODELS.items():
                exercise = db.scalar(select(Exercise).where(Exercise.name.ilike(name)))
                if exercise is None:
                    print(f"NOT FOUND: {name}  (check the real name in /api/exercises?search=...)")
                    continue

                row = db.scalar(
                    select(ExerciseModel).where(ExerciseModel.exercise_id == exercise.id)
                )
                if row is None:
                    db.add(ExerciseModel(exercise_id=exercise.id, **fields))
                else:
                    for key, value in fields.items():
                        setattr(row, key, value)
                print(f"linked {exercise.name} -> {fields['model_url']}")
            db.commit()
        except Exception:
            db.rollback()
            raise

if __name__ == "__main__":
    main()