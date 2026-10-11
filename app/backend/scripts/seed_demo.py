# auto fills the database with 10 sample exercises and 2 training
# programs so endpoints return something. only used for demo purposes

from sqlalchemy import select

import app.models
from app.db.session import SessionLocal
from app.models import (Equipment, Exercise, ExerciseMuscle, MuscleGroup, SessionExercise,
                        TrainingProgram, WorkoutSession)

# name, primary muscle, secondary muscles, equipment, difficulty, role, minutes, instructions
EXERCISES = [
    ("Barbell Back Squat", "Quadriceps", ["Glutes"], ["Barbell"], "intermediate", "core", 10,
     "Bar on upper back, feet shoulder width. Sit hips back and down until thighs are parallel, then drive up."),
    ("Bench Press", "Chest", ["Triceps"], ["Barbell", "Bench"], "intermediate", "core", 10,
     "Lie on the bench, lower the bar to mid-chest under control, press back to lockout."),
    ("Bodyweight Squat", "Quadriceps", ["Glutes"], [], "beginner", "core", 6,
     "Feet shoulder width, sit hips back and down, keep chest up, stand tall."),
    ("Push-Up", "Chest", ["Triceps", "Shoulders"], [], "beginner", "core", 6,
     "Hands under shoulders, body in a straight line, lower chest to the floor and press up."),
    ("Dumbbell Row", "Back", ["Biceps"], ["Dumbbell", "Bench"], "beginner", "core", 8,
     "One hand and knee on the bench, pull the dumbbell to your hip, lower slowly."),
    ("Dumbbell Shoulder Press", "Shoulders", ["Triceps"], ["Dumbbell"], "beginner", "accessory", 6,
     "Dumbbells at shoulder height, press overhead, lower under control."),
    ("Dumbbell Bicep Curl", "Biceps", [], ["Dumbbell"], "beginner", "accessory", 5,
     "Elbows pinned to your sides, curl the dumbbells up, lower slowly."),
    ("Triceps Pushdown", "Triceps", [], ["Cable Machine"], "beginner", "accessory", 5,
     "Elbows at your sides, press the handle down to full extension, return slowly."),
    ("Plank", "Abs", [], [], "beginner", "accessory", 4,
     "Forearms on the floor, body in one line from head to heels, hold without sagging."),
    ("Resistance Band Pull-Apart", "Back", ["Shoulders"], ["Resistance Band"], "beginner", "accessory", 4,
     "Arms straight in front, pull the band apart to chest level, return with control."),
]

# program name, goal, level, weeks, [(session name, [(exercise name, role, sets, reps)])]
PROGRAMS = [
    ("Beginner Full Body Starter", "general health", "beginner", 4, [
        ("Full Body A", [("Bodyweight Squat", "core", 3, 12), ("Push-Up", "core", 3, 8),
                         ("Dumbbell Row", "core", 3, 10), ("Dumbbell Shoulder Press", "accessory", 2, 10),
                         ("Plank", "accessory", 2, 30)]),
        ("Full Body B", [("Bodyweight Squat", "core", 3, 15), ("Dumbbell Row", "core", 3, 10),
                         ("Dumbbell Bicep Curl", "accessory", 2, 12), ("Plank", "accessory", 2, 40)]),
    ]),
    ("Strength Foundations", "strength", "intermediate", 8, [
        ("Lower Body", [("Barbell Back Squat", "core", 4, 6), ("Plank", "accessory", 3, 45)]),
        ("Upper Body", [("Bench Press", "core", 4, 6), ("Dumbbell Row", "core", 4, 8),
                        ("Triceps Pushdown", "accessory", 3, 12), ("Resistance Band Pull-Apart", "accessory", 3, 15)]),
    ]),
]

def get_or_create(db, model, **kw):
    obj = db.scalar(select(model).filter_by(**kw))
    if obj is None:
        obj = model(**kw)
        db.add(obj)
        db.flush()
    return obj

def main() -> None:
    with SessionLocal() as db:
        by_name: dict[str, Exercise] = {}
        for name, primary, secondary, equipment, diff, role, minutes, text in EXERCISES:
            ex = db.scalar(select(Exercise).where(Exercise.name == name, Exercise.source == "manual"))
            if ex is None:
                ex = Exercise(name=name, description=text, difficulty=diff, default_role=role,
                              default_minutes=minutes, source="manual", category="Demo")
                ex.equipment = [get_or_create(db, Equipment, name=e) for e in equipment]
                ex.muscle_links = [ExerciseMuscle(muscle=get_or_create(db, MuscleGroup, name=primary), is_primary=True)] + [
                    ExerciseMuscle(muscle=get_or_create(db, MuscleGroup, name=m), is_primary=False) for m in secondary]
                db.add(ex)
                db.flush()
            by_name[name] = ex

        for pname, goal, level, weeks, sessions in PROGRAMS:
            if db.scalar(select(TrainingProgram).where(TrainingProgram.name == pname)):
                continue
            program = TrainingProgram(name=pname, goal=goal, experience_level=level, length_weeks=weeks)
            for pos, (sname, items) in enumerate(sessions, start=1):
                ws = WorkoutSession(name=sname, position=pos)
                ws.items = [SessionExercise(exercise=by_name[en], position=i, role=role, sets=sets, reps=reps)
                            for i, (en, role, sets, reps) in enumerate(items, start=1)]
                program.sessions.append(ws)
            db.add(program)
        db.commit()
        print("Seeded demo exercises and programs.")

if __name__ == "__main__":
    main()