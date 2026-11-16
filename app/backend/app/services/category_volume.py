# set exercises into training categories and show
# prescribed vs actual per program day (no database/frameowrk)

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# from the exercise slug -> wger exercise id (using same id as CATALOG_ID)
WGER_IDS = {
    "push-up": 930, "bodyweight-squat": 431, "reverse-lunge": 286, "glute-bridge": 85, "plank": 928,
    "pike-push-up": 141, "bench-dip": 434, "burpee": 38,
    "barbell-bench-press": 927, "barbell-back-squat": 704, "romanian-deadlift": 157,
    "lat-pulldown": 229, "dumbbell-shoulder-press": 175, "dumbbell-row": 934, "dumbbell-lunge": 68,
    "dumbbell-curl": 906, "triceps-pushdown": 929, "cable-fly": 636,
}

# category section (baseline test exercise): label, unit, member exercises
# some exercises are in no category, such as mountain-climber/bird-dog
CATEGORIES = {
    "bw": {
        "push-up": {"label": "Upper-body push", "unit": "reps",
                    "exercises": ["push-up", "pike-push-up", "bench-dip"]},
        "bodyweight-squat": {"label": "Lower body", "unit": "reps",
                             "exercises": ["bodyweight-squat", "reverse-lunge", "glute-bridge", "burpee"]},
        "plank": {"label": "Core", "unit": "seconds", "exercises": ["plank"]},
    },
    "ldw": {
        "barbell-bench-press": {"label": "Upper-body push", "unit": "reps",
                                "exercises": ["barbell-bench-press", "dumbbell-shoulder-press",
                                              "cable-fly", "triceps-pushdown"]},
        "barbell-back-squat": {"label": "Lower body", "unit": "reps",
                               "exercises": ["barbell-back-squat", "dumbbell-lunge"]},
        "romanian-deadlift": {"label": "Hinge and pull", "unit": "reps",
                              "exercises": ["romanian-deadlift", "lat-pulldown", "dumbbell-row", "dumbbell-curl"]},
    },
}

def category_of(program: str, wger_id: int) -> Optional[int]:
    for key, cat in CATEGORIES.get(program, {}).items():
        if any(WGER_IDS.get(slug) == wger_id for slug in cat["exercises"]):
            return key
        return None

@dataclass
class SetRow:
    exercise_id: int
    record_id: int
    performed_at: datetime
    week: int
    day: int
    reps: Optional[int]
    seconds: Optional[int]
    status: str # completed / skipped/ etc
    target_sets: Optional[int]
    target_value: Optional[int] # prescried reps or seconds for exercises

@dataclass
class DayPoint:
    week: int
    day: int
    prescribed: int
    actual: int

def category_programs(program: str, rows: List[SetRow]) -> Dict[str, List[DayPoint]]:
    # each category is named after it's baseline test
    # prescribed = target_sets * target_value, sum over the categories exercises
    # actual reps (or seconds) of the finished exercises
    newest: Dict[Tuple[int, int, int], Tuple[datetime, int]] = {}
    for r in rows:
        k = (r.week, r.day, r.exercise_id)
        if k not in newest or (r.performed_at, r.record_id) > newest[k]:
            newest[k] = (r.performed_at, r.record_id)

    groups: Dict[Tuple[int, int, int], List[SetRow]] = {}
    for r in rows:
        k = (r.week, r.day, r.exercise_id)
        if(r. performed_at, r.record_id) == newest[k]:
            groups.setdefault(k, []).append(r)

    totals: Dict[Tuple[str, int, int], List[int]] = {}
    for (week, day, ex_id), rs in groups.items():
        cat = category_of(program, ex_id)
        if cat is None:
            continue
        prescribed = next((r.target_sets * r.target_value for r in rs
                           if r.target_sets is not None and r.target_value is not None), None)
        if prescribed is None:
            continue
        timed = CATEGORIES[program][cat]["unit"] == "seconds"
        actual = sum(((r.seconds or r.reps or 0) if timed else (r.reps or 0))
                     for r in rs if r.status == "completed")
        t = totals.setdefault((cat, week, day), [0, 0])
        t[0] += prescribed
        t[1] += actual

    out: Dict[str, List[DayPoint]] = {key: [] for key in CATEGORIES.get(program, {})}
    for (cat, week, day), (p, a) in sorted(totals.items(), key=lambda kv: (kv[0][1], kv[0][2], kv[0][0])):
        out[cat].append(DayPoint(week, day, p, a))
    return out