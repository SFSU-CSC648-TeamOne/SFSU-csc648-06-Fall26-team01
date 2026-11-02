# DEV ONLY - seeds a LOCAL SQLite database with a small catalog so the dashboard,
# workout details and active workout pages have something to show.
# Refuses to run against anything that is not SQLite, so it can never write to Supabase.
#
#   python -m scripts.create_tables
#   python -m scripts.seed_local_dev
#
# Safe to run again: rows that already exist are left alone.

from sqlalchemy import select
from sqlalchemy.engine import make_url

import app.models
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import (Equipment, Exercise, ExerciseModel, ExerciseMuscle, MuscleGroup,
                        SessionExercise, TrainingProgram, WorkoutSession)

PROGRAM_NAME = "Local Dev Starter"

EQUIPMENT = ["Bodyweight", "Dumbbell", "Bench", "Mat"]
MUSCLES = ["Chest", "Back", "Legs", "Shoulders", "Core"]

# name, category, difficulty, default role, minutes, primary muscle, secondary muscles, equipment
EXERCISES = [
    ("Push-Up", "Chest", "beginner", "core", 5, "Chest", ["Shoulders"], ["Bodyweight"]),
    ("Dumbbell Row", "Back", "beginner", "core", 6, "Back", [], ["Dumbbell", "Bench"]),
    ("Goblet Squat", "Legs", "beginner", "core", 6, "Legs", ["Core"], ["Dumbbell"]),
    ("Dumbbell Shoulder Press", "Shoulders", "beginner", "accessory", 5, "Shoulders", [], ["Dumbbell"]),
    ("Reverse Lunge", "Legs", "beginner", "accessory", 5, "Legs", [], ["Bodyweight"]),
    ("Plank", "Core", "beginner", "accessory", 3, "Core", [], ["Mat"]),
]

# session name, guidance, [(exercise name, role, sets, reps)]
SESSIONS = [
    ("Upper Body Basics", "Rest 60-90 seconds between sets.", [
        ("Push-Up", "core", 3, 10),
        ("Dumbbell Row", "core", 3, 10),
        ("Dumbbell Shoulder Press", "accessory", 2, 12),
        ("Plank", "accessory", 2, None),
    ]),
    ("Lower Body Basics", "Keep your knees in line with your toes.", [
        ("Goblet Squat", "core", 3, 10),
        ("Reverse Lunge", "core", 3, 10),
        ("Plank", "accessory", 2, None),
    ]),
]

# Demo videos shown on the program exercise pages (programsData.ts `demo` field) and the landing page.
# Files live in app/frontend/public/about/. Same scan .glb as scripts/attach_models.py.
SCAN_URL = "/about/Scaniverse%202026-10-15%20121405.glb"
DEMO_VIDEOS = [
    # name, primary muscle, video
    ("Hercules Squat", "Legs", "/about/demo_one.mp4"),
    ("Pistol Squat Jesus", "Legs", "/about/demo_two.mp4"),
]

def ensure_sqlite() -> None:
    url = make_url(get_settings().database_url)
    if url.get_backend_name() != "sqlite":
        raise SystemExit("Refusing to seed: DATABASE_URL is not SQLite. This script is for local dev only.")

def get_or_create(db, model, **fields):
    row = db.scalar(select(model).filter_by(**fields))
    if row is None:
        row = model(**fields)
        db.add(row)
        db.flush()
    return row

def seed(db) -> str:
    if db.scalar(select(TrainingProgram).where(TrainingProgram.name == PROGRAM_NAME)):
        return "Already seeded, nothing written."

    equipment = {name: get_or_create(db, Equipment, name=name) for name in EQUIPMENT}
    muscles = {name: get_or_create(db, MuscleGroup, name=name) for name in MUSCLES}

    exercises = {}
    for name, category, difficulty, role, minutes, primary, secondary, gear in EXERCISES:
        ex = db.scalar(select(Exercise).where(Exercise.name == name))
        if ex is None:
            ex = Exercise(name=name, category=category, difficulty=difficulty, default_role=role,
                          default_minutes=minutes, source="manual",
                          description=f"{name}: local dev sample exercise.",
                          equipment=[equipment[g] for g in gear])
            ex.muscle_links = [ExerciseMuscle(muscle=muscles[primary], is_primary=True)]
            ex.muscle_links += [ExerciseMuscle(muscle=muscles[m], is_primary=False) for m in secondary]
            db.add(ex)
            db.flush()
        exercises[name] = ex

    program = TrainingProgram(
        name=PROGRAM_NAME, goal="general fitness", experience_level="beginner", length_weeks=4,
        description="Local dev sample program with an upper and a lower body session.")
    for position, (name, guidance, items) in enumerate(SESSIONS, start=1):
        session = WorkoutSession(name=name, position=position, guidance=guidance)
        session.items = [
            SessionExercise(exercise=exercises[ex_name], position=i, role=role, sets=sets, reps=reps)
            for i, (ex_name, role, sets, reps) in enumerate(items, start=1)
        ]
        program.sessions.append(session)
    db.add(program)
    return (f"Seeded {len(EQUIPMENT)} equipment, {len(MUSCLES)} muscle groups, "
            f"{len(EXERCISES)} exercises, 1 program with {len(SESSIONS)} sessions.")

def seed_demo_videos(db) -> str:
    # runs separately from seed() so databases seeded before the videos were added get them too
    added = []
    for name, muscle, video_url in DEMO_VIDEOS:
        ex = db.scalar(select(Exercise).where(Exercise.name == name))
        if ex is None:
            ex = Exercise(name=name, category="Legs", difficulty="intermediate", default_role="core",
                          default_minutes=5, source="manual",
                          description=f"{name}: team demo video.",
                          equipment=[get_or_create(db, Equipment, name="Bodyweight")])
            ex.muscle_links = [ExerciseMuscle(muscle=get_or_create(db, MuscleGroup, name=muscle), is_primary=True)]
            db.add(ex)
            db.flush()
        if db.scalar(select(ExerciseModel).where(ExerciseModel.exercise_id == ex.id)) is None:
            db.add(ExerciseModel(exercise_id=ex.id, model_url=SCAN_URL, video_url=video_url,
                                 credit="Scan by our team"))
            added.append(name)
    return f"Demo videos linked: {', '.join(added)}." if added else "Demo videos already linked."

def main() -> None:
    ensure_sqlite()
    with SessionLocal() as db:
        try:
            message = seed(db) + " " + seed_demo_videos(db)
            db.commit()
        except Exception:
            db.rollback()
            raise
    print(message)

if __name__ == "__main__":
    main()
