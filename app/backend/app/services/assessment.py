# final assessment: for each exercise, say whether to add 0, 1 or 2 sets.
# exercise names and muscles come from wger (the exercises table).

from typing import Optional
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models import User
from app.repositories import assessment as repo
from app.schemas.assessment import ExerciseAdvice, ProgramAssessmentOut

MAX_SETS = 6 # max amount of set recommended for safety

def total(sets: list) -> int:
    """Total reps, or total seconds for timed exercises like plank."""
    return sum(s.reps or 0 for s in sets) or sum(s.duration_seconds or 0 for s in sets)

def program_assessment(db: Session, user: User, program: Optional[str],
                       days_total: Optional[int]) -> ProgramAssessmentOut:
    pairs = sorted(repo.program_entries(db, user.id, program), key=lambda p: (p[0].performed_at, p[0].id))
    if not pairs:
        raise NotFoundError("No saved workouts for this program yet.")

    # looks up each exercise for each program day. if user redid same exercise
    # the newer one will replace the old one.
    sessions = {}
    for rec, e in pairs:
        day = (rec.program_week or 0, rec.program_day or 0)
        s = sessions.setdefault(e.exercise_id, {}).get(day)
        if s is None or s["rec"] != rec.id:
            s = sessions[e.exercise_id][day] = {"rec": rec.id, "done": [], "skipped": 0}
        if e.status == "completed":
            s["done"].append(e)
        elif e.status == "skipped":
            s["skipped"] += 1

    wger = repo.exercises_by_ids(db, set(sessions)) # query fetch of wger exercises for every exercise user did
    exercises, done, skipped = [], 0, 0
    for ex_id, by_day in sessions.items():
        runs = [by_day[d] for d in sorted(by_day)]
        first, last = total(runs[0]["done"]), total(runs[-1]["done"])
        pct = round((last - first) / first * 100, 1) if len(runs) > 1 and first else None
        done += sum(len(r["done"]) for r in runs)
        skipped += sum(r["skipped"] for r in runs)
        sets_now = len(runs[-1]["done"])

        # decides how many sets to add if any based on final assessment from program
        if runs[-1]["skipped"] or (pct is not None and pct <= -10) or sets_now >= MAX_SETS:
            add, text = 0, "Keep the same number of sets."
        # percet of change from the first and latest assessment (i.e 10%, will adjust if too high)
        elif pct is not None and pct >= 10:
            add, text = min(2, MAX_SETS - sets_now), "You improved and finished every set. Add 2 sets."
        else:
            add, text = 1, "You finished every set. Add 1 set."

        w = wger.get(ex_id)
        exercises.append(ExerciseAdvice(
            exercise_id=ex_id, name=w.name if w else "Exercise %d" % ex_id,
            muscles=[l.muscle.name for l in w.muscle_links if l.is_primary] if w else [],
            sessions=len(runs), sets_now=sets_now, change_pct=pct,
            sets_skipped=sum(r["skipped"] for r in runs),
            add_sets=add, suggested_sets=sets_now + add, advice=text))

    days = {d for by_day in sessions.values() for d in by_day}
    completion = done / (done + skipped) if done + skipped else 0.0
    consistency = min(len(days) / days_total, 1.0) if days_total else 1.0
    score = round(100 * (consistency + completion) / 2)
    adding = sum(1 for x in exercises if x.add_sets)
    
    adding = sum(1 for x in exercises if x.add_sets)

    return ProgramAssessmentOut(
        program=program, score=score,
        summary="You trained on %d days and finished %d%% of your sets. Add sets to %d of %d exercises."
                % (len(days), round(completion * 100), adding, len(exercises)),
        days_completed=len(days), days_total=days_total,
        completion_pct=round(completion * 100, 1), exercises=exercises)