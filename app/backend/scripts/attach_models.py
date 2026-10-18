# links .glb files to exercises
from sqlalchemy import select

import app.models
from app.db.session import SessionLocal
from app.models import Exercise
from app.models.media import ExerciseModel

# exercise names (must match wger id names)
MODELS = {
    "Squats": ("https://<project>.supabase.co/storage/v1/object/public/models/squat.glb",
               "Squat", "Model by <author>, CC-BY"),
    # "Push-ups": ("/models/pushup.glb", "PushUp", "..."), etc etc
}

def main() -> None:
    with SessionLocal() as db:
        for name, (url, clip, credit) in MODELS.items():
            exercise = db.scalar(select(Exercise).where(Exercise.name.ilike(name)))
            if exercise is None:
                print(f"NOT FOUND: {name}  (check the real name in /api/exercises?search=...)")
                continue
            row = db.scalar(select(ExerciseModel).where(ExerciseModel.exercise_id == exercise.id))
            if row is None:
                db.add(ExerciseModel(exercise_id=exercise.id, model_url=url,
                                     animation_name=clip, credit=credit))
            else:
                row.model_url, row.animation_name, row.credit = url, clip, credit
            print(f"linked {exercise.name} -> {url}")
        db.commit()

if __name__ == "__main__":
    main()