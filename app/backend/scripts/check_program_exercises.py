# attempt to match every WGER exercise in the database for
# each BW and LDW program exercises

from sqlalchemy import func, or_, select

import app.models
from app.db.session import SessionLocal
from app.models import Exercise

# searches for program's exercise name if there isn't an exact match
PROGRAM_EXERCISES = {
    "BW": [
        ("Push-Up", ["push-up", "push up"]),
        ("Bodyweight Squat", ["squat"]),
        ("Reverse Lunge", ["lunge"]),
        ("Glute Bridge", ["glute bridge", "bridge"]),
        ("Plank", ["plank"]),
        ("Pike Push-Up", ["pike"]),
        ("Mountain Climbers", ["mountain"]),
        ("Bird Dog", ["bird"]),
        ("Bench Dip", ["dip"]),
        ("Burpee", ["burpee"]),
    ],
    "LDW": [
        ("Barbell Bench Press", ["bench press"]),
        ("Barbell Back Squat", ["squat"]),
        ("Romanian Deadlift", ["romanian", "deadlift"]),
        ("Lat Pulldown", ["pulldown"]),
        ("Dumbbell Shoulder Press", ["shoulder press"]),
        ("Dumbbell Row", ["row"]),
        ("Dumbbell Lunge", ["lunge"]),
        ("Dumbbell Biceps Curl", ["curl"]),
        ("Triceps Pushdown", ["pushdown", "push down"]),
        ("Cable Fly", ["fly", "flye"]),
    ],
}

def main() -> None:
    with SessionLocal() as db:
        for program, items in PROGRAM_EXERCISES.items():
            print(f"\n=== {program} ===")
            for name, words in items:
                exact = db.scalar(select(Exercise).where(func.lower(Exercise.name) == name.lower()))
                if exact is not None:
                    print(f"OK: {name} -> id {exact.id}: {exact.name}")
                    continue
                like = or_(*[Exercise.name.ilike(f"%{w}%") for w in words])
                found = list(db.scalars(select(Exercise).where(like).order_by(Exercise.name).limit(5)))
                if found:
                    options = "; ".join(f"id {e.id}: {e.name}" for e in found)
                    print(f"CHECK: {name} -> close matches: {options}")
                else:
                    print(f"MISSING: {name} -> no matches found")

if __name__ == "__main__":
    main()