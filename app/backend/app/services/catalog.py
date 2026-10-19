# rules for searching exercises by listing the filter options, 
# and searching programs by goal and length, returning a response

from typing import Optional
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models import Exercise, SessionExercise, WorkoutSession
from app.repositories import catalog as repo
from app.schemas.catalog import (ExerciseOut, NamedOut, ProgramOut, WorkoutDetailOut,
                                 WorkoutExerciseOut, WorkoutSummaryOut)

# returns correct id for each wger api call
def exercise_to_out(ex: Exercise) -> ExerciseOut:
    primary = sorted(l.muscle.name for l in ex.muscle_links if l.is_primary)
    secondary = sorted(l.muscle.name for l in ex.muscle_links if not l.is_primary)
    return ExerciseOut(
        id=ex.id, name=ex.name, category=ex.category, description=ex.description,
        difficulty=ex.difficulty, default_role=ex.default_role, default_minutes=ex.default_minutes,
        primary_muscles=primary, secondary_muscles=secondary,
        equipment=sorted(e.name for e in ex.equipment), source=ex.source,
        license_name=ex.license_name, license_author=ex.license_author
    )

def search_exercises(db: Session, **filters) -> tuple[list[ExerciseOut], int]:
    rows, total = repo.search_exercises(db, **filters)
    return [exercise_to_out(r) for r in rows], total

def get_exercise(db: Session, exercise_id: int) -> ExerciseOut:
    ex = repo.get_exercise(db, exercise_id)
    if ex is None:
        raise NotFoundError("Exercise not found.")
    return exercise_to_out(ex)

def list_equipment(db: Session) -> list[NamedOut]:
    return [NamedOut.model_validate(e) for e in repo.list_equipment(db)]

def list_muscle_groups(db: Session) -> list[NamedOut]:
    return [NamedOut.model_validate(m) for m in repo.list_muscle_groups(db)]

def search_programs(db: Session, **filters) -> tuple[list[ProgramOut], int]:
    rows, total = repo.search_programs(db, **filters)
    return [ProgramOut.model_validate(r) for r in rows], total

def _item_minutes(item: SessionExercise) -> int:
# a session may override an exercise's default duration
    return item.minutes if item.minutes is not None else item.exercise.default_minutes


def _primary_muscles(exercise: Exercise) -> list:
    return sorted({l.muscle.name for l in exercise.muscle_links if l.is_primary})

def _summary(ws: WorkoutSession) -> WorkoutSummaryOut:
    muscles = sorted({m for item in ws.items for m in _primary_muscles(item.exercise)})
    return WorkoutSummaryOut(
        id=ws.id, name=ws.name, program_id=ws.program_id, program_name=ws.program.name,
        goal=ws.program.goal, difficulty=ws.program.experience_level,
        total_minutes=sum(_item_minutes(i) for i in ws.items),
        exercise_count=len(ws.items), muscle_groups=muscles)

def search_workout_sessions(
    db: Session, *, muscle: Optional[str], difficulty: Optional[str],
    max_minutes: Optional[int], limit: int, offset: int,
) -> tuple:
    rows = repo.list_workout_sessions(db, muscle=muscle, difficulty=difficulty)
    summaries = [_summary(r) for r in rows]
    if max_minutes is not None:  # length filter
        summaries = [s for s in summaries if s.total_minutes <= max_minutes]
    return summaries[offset:offset + limit], len(summaries)

def get_workout_session(db: Session, session_id: int) -> WorkoutDetailOut:
    ws = repo.get_workout_session(db, session_id)
    if ws is None:
        raise NotFoundError("Workout session not found.")
    summary = _summary(ws)
    demos = repo.models_for_exercises(db, {i.exercise_id for i in ws.items})
    return WorkoutDetailOut(
        **summary.model_dump(), guidance=ws.guidance,
        exercises=[
            WorkoutExerciseOut(
                id=i.id, exercise_id=i.exercise_id, name=i.exercise.name, position=i.position,
                role=i.role, droppable=(i.role == "accessory"), sets=i.sets, reps=i.reps,
                minutes=_item_minutes(i), equipment=sorted(e.name for e in i.exercise.equipment),
                primary_muscles=_primary_muscles(i.exercise),
                model_url=demos[i.exercise_id].model_url if i.exercise_id in demos else None,
                video_url=demos[i.exercise_id].video_url if i.exercise_id in demos else None)
            for i in ws.items])