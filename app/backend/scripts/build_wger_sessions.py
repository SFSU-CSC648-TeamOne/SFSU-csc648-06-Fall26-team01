# builds workout sessions out of the exercises imported from WGER, so the workout
# selection page has exercises to filter by muscle group, difficulty and length.
# WGER only provides single exercises, not workouts, so the grouping rules are ours (can change if needed)

import argparse
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

import app.models
from app.db.session import SessionLocal
from app.models import (Exercise, ExerciseMuscle, SessionExercise, TrainingProgram,
                        WorkoutSession)

# difficulty levels that get sessions. WGER data is only rated beginner/intermediate by
# our import rules, I don't see advanced rules yet
LEVELS = ["beginner", "intermediate"]

# size name - core exercises wanted, accessory exercises wanted, fewest exercises allowed
SIZES = {
    "Short": (2, 1, 3),
    "Full": (3, 3, 4),
}

# level - role - sets, reps
PRESCRIPTION = {
    "beginner": {"core": (3, 10), "accessory": (2, 12)},
    "intermediate": {"core": (4, 8), "accessory": (3, 12)},
}

PROGRAM_GOAL = "general fitness"
PROGRAM_WEEKS = 4

# choosing the exercise (no database required)
def eligible(difficulty: Optional[str], level: str) -> bool:
    if level == "beginner":
        return difficulty == "beginner"
    return difficulty in ("beginner", "intermediate")

def choose(exercises: list, level: str, size: str) -> list:
    """Returns [(exercise, role)] with core exercises first, or [] if there are too few."""
    core_wanted, accessory_wanted, minimum = SIZES[size]

    pool = [e for e in exercises if eligible(e.difficulty, level)]
    # prefer exercises rated exactly at this level, then alphabetical 
    pool.sort(key=lambda e: (0 if e.difficulty == level else 1, e.name.lower()))

    core = [e for e in pool if e.default_role == "core"]
    accessory = [e for e in pool if e.default_role != "core"]

    picked = core[:core_wanted] + accessory[:accessory_wanted]
    if len(picked) < core_wanted + accessory_wanted:  # one group ran short, fill from the other
        leftovers = [e for e in core[core_wanted:] + accessory[accessory_wanted:] if e not in picked]
        picked += leftovers[: core_wanted + accessory_wanted - len(picked)]

    if len(picked) < minimum:
        return []
    picked.sort(key=lambda e: 0 if e.default_role == "core" else 1)
    return [(e, "core" if e.default_role == "core" else "accessory") for e in picked]


def plan_sessions(by_muscle: dict) -> list:
    """[(level, session name, [(exercise, role)])] for every muscle/level/size that has enough."""
    plan = []
    for level in LEVELS:
        for muscle in sorted(by_muscle):
            for size in SIZES:
                items = choose(by_muscle[muscle], level, size)
                if items:
                    plan.append((level, f"{muscle} Focus - {size}", items))
    return plan

def minutes_of(items: list) -> int:
    return sum(e.default_minutes for e, _ in items)

# database
def load_by_muscle(db) -> dict:
    """wger exercises grouped by their primary muscle group's name."""
    exercises = db.scalars(
        select(Exercise).where(Exercise.source == "wger")
        .options(selectinload(Exercise.muscle_links).selectinload(ExerciseMuscle.muscle))
    ).all()
    by_muscle: dict = {}
    for exercise in exercises:
        for link in exercise.muscle_links:
            if link.is_primary:
                by_muscle.setdefault(link.muscle.name, []).append(exercise)
    return by_muscle

def get_or_create_program(db, level: str) -> TrainingProgram:
    name = f"wger {level.title()} Sessions"
    program = db.scalar(select(TrainingProgram).where(TrainingProgram.name == name))
    if program is None:
        program = TrainingProgram(
            name=name, goal=PROGRAM_GOAL, experience_level=level, length_weeks=PROGRAM_WEEKS,
            description="Sessions generated from wger exercises, one set per muscle group.")
        db.add(program)
        db.flush()
    return program

def write_plan(db, plan: list) -> dict:
    counts = {"created": 0, "existing": 0}
    programs: dict = {}
    for level, name, items in plan:
        if level not in programs:
            programs[level] = get_or_create_program(db, level)
        program = programs[level]

        if name in {s.name for s in program.sessions}:
            counts["existing"] += 1
            continue

        position = max([s.position for s in program.sessions], default=0) + 1
        session = WorkoutSession(
            name=name, position=position,
            guidance="Generated from wger exercises. Rest 60-90 seconds between sets.")
        session.items = [
            SessionExercise(exercise=exercise, position=i, role=role,
                            sets=PRESCRIPTION[level][role][0], reps=PRESCRIPTION[level][role][1])
            for i, (exercise, role) in enumerate(items, start=1)
        ]
        program.sessions.append(session)
        counts["created"] += 1
    return counts

def main() -> None:
    parser = argparse.ArgumentParser(description="Build workout sessions from wger exercises.")
    parser.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    args = parser.parse_args()

    with SessionLocal() as db:
        by_muscle = load_by_muscle(db)
        if not by_muscle:
            print("No wger exercises found. Run  python -m scripts.import_wger  first.")
            return

        plan = plan_sessions(by_muscle)
        for level, name, items in plan:
            print(f"  {level:<12} {name:<28} {len(items)} exercises  ~{minutes_of(items)} min")
        print(f"{len(plan)} sessions possible from {len(by_muscle)} muscle groups.")

        if args.dry_run:
            print("Dry run: nothing written.")
            return

        try:
            counts = write_plan(db, plan)
            db.commit()
        except Exception:
            db.rollback()
            raise

    print(f"Done. created={counts['created']} already_existed={counts['existing']}")

if __name__ == "__main__":
    main()