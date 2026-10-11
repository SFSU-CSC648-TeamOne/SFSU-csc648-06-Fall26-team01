# Removes the sample data we wrote by hand (seed_demo.py) so only wger data is left:
#   - every training program that is not one of the generated "wger ..." programs
#     (their workout sessions and session exercises go with them)
#   - every exercise that did not come from wger
#   - muscle groups and equipment that are no longer used and did not come from wger
#
# Run from app/backend with the venv active:
#   python -m scripts.remove_demo_data            shows what WOULD be deleted, changes nothing
#   python -m scripts.remove_demo_data --yes      actually deletes it
#
# Do not run scripts.seed_demo again afterwards, it would put the sample data back.

import argparse

from sqlalchemy import select

import app.models
from app.db.session import SessionLocal
from app.models import (Equipment, Exercise, ExerciseMuscle, MuscleGroup, PerformanceEntry,
                        TrainingProgram, exercise_equipment)

WGER_PROGRAM_PREFIX = "wger "


def main() -> None:
    parser = argparse.ArgumentParser(description="Remove hand-written sample data, keep wger data.")
    parser.add_argument("--yes", action="store_true", help="really delete (default is a dry run)")
    parser.add_argument("--force", action="store_true",
                        help="continue even if no generated wger sessions exist yet")
    args = parser.parse_args()

    with SessionLocal() as db:
        programs = db.scalars(select(TrainingProgram)).all()
        wger_programs = [p for p in programs if p.name.startswith(WGER_PROGRAM_PREFIX)]
        demo_programs = [p for p in programs if not p.name.startswith(WGER_PROGRAM_PREFIX)]

        # Safety: without generated sessions the workout page would be empty afterwards.
        if sum(len(p.sessions) for p in wger_programs) == 0 and not args.force:
            print("No generated wger sessions exist yet, so deleting the samples would leave the")
            print("workout page empty. Run  python -m scripts.build_wger_sessions  first")
            print("(or add --force if you really want that).")
            return

        # Exercises that people have already logged cannot be deleted without losing their history.
        used_ids = set(db.scalars(select(PerformanceEntry.exercise_id)))
        used_ids |= {i for i in db.scalars(select(PerformanceEntry.substituted_for_exercise_id)) if i}
        not_wger = db.scalars(select(Exercise).where(Exercise.source != "wger")).all()
        deletable = [e for e in not_wger if e.id not in used_ids]
        kept = [e for e in not_wger if e.id in used_ids]

        print("Training programs to delete:")
        for p in demo_programs:
            print(f"  - {p.name} ({len(p.sessions)} sessions)")
        print(f"Exercises to delete: {len(deletable)}")
        for e in deletable:
            print(f"  - {e.name}")
        if kept:
            print("Exercises kept because a logged workout uses them:")
            for e in kept:
                print(f"  - {e.name}")
        print(f"Keeping {len(wger_programs)} wger program(s) and all wger exercises.")

        if not args.yes:
            print("\nDry run: nothing was deleted. Add --yes to delete.")
            return

        try:
            for program in demo_programs:
                db.delete(program)
            db.flush()
            for exercise in deletable:
                db.delete(exercise)
            db.flush()

            # muscle groups / equipment that came from our samples and nothing uses any more
            used_muscles = set(db.scalars(select(ExerciseMuscle.muscle_group_id)))
            muscles_removed = 0
            for muscle in db.scalars(select(MuscleGroup).where(MuscleGroup.wger_id.is_(None))):
                if muscle.id not in used_muscles:
                    db.delete(muscle)
                    muscles_removed += 1

            used_equipment = set(db.scalars(select(exercise_equipment.c.equipment_id)))
            equipment_removed = 0
            for item in db.scalars(select(Equipment).where(Equipment.wger_id.is_(None))):
                if item.id not in used_equipment:
                    db.delete(item)
                    equipment_removed += 1

            db.commit()
        except Exception:
            db.rollback()
            raise

    print(f"\nDeleted {len(demo_programs)} programs, {len(deletable)} exercises, "
          f"{muscles_removed} muscle groups, {equipment_removed} equipment items.")


if __name__ == "__main__":
    main()