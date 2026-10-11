from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, selectinload
from app.models import (Equipment, Exercise, ExerciseMuscle, MuscleGroup, SessionExercise,
                        TrainingProgram, WorkoutSession)

def _exercise_loads():
    return (selectinload(Exercise.equipment),
            selectinload(Exercise.muscle_links).selectinload(ExerciseMuscle.muscle))

def search_exercises(
        db: Session, *, q: Optional[str], muscle: Optional[str], equipment: Optional[str],
        difficulty: Optional[str], limit: int, offset: int,
) -> tuple[list[Exercise], int]:
    stmt = select(Exercise)
    if q:
        stmt = stmt.where(Exercise.name.icontains(q, autoescape=True))
    if muscle:
        stmt = stmt.where(Exercise.muscle_links.any(
            ExerciseMuscle.muscle.has(func.lower(MuscleGroup.name) == muscle.lower())))
    if equipment:
        stmt = stmt.where(Exercise.equipment.any(func.lower(Equipment.name) == equipment.lower()))
    if difficulty:
        stmt = stmt.where(Exercise.difficulty == difficulty)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.options(*_exercise_loads()).order_by(Exercise.name, Exercise.id)
                      .limit(limit).offset(offset)).all()
    return list(rows), total

def get_exercise(db: Session, exercise_id: int) -> Optional[Exercise]:
    return db.scalar(select(Exercise).options(*_exercise_loads()).where(Exercise.id == exercise_id))

def list_equipment(db: Session) -> list[Equipment]:
    return list(db.scalars(select(Equipment).order_by(Equipment.name)))

def list_muscle_groups(db: Session) -> list[MuscleGroup]:
    return list(db.scalars(select(MuscleGroup).order_by(MuscleGroup.name)))

def search_programs(
        db: Session, *, goal: Optional[str], max_weeks: Optional[int], limit: int, offset: int,
) -> tuple[list[TrainingProgram], int]:
    stmt = select(TrainingProgram)
    if goal: 
        stmt = stmt.where(TrainingProgram.goal.icontains(goal, autoescape=True))
    if max_weeks is not None:
        stmt = stmt.where(TrainingProgram.length_weeks <= max_weeks)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(TrainingProgram.name, TrainingProgram.id).limit(limit).offset(offset))
    return list(rows), total

def _session_loads():
    """Everything needed to describe a Workout Session without extra queries per row."""
    items_exercise = selectinload(WorkoutSession.items).selectinload(SessionExercise.exercise)
    return (
        selectinload(WorkoutSession.program),
        items_exercise.selectinload(Exercise.equipment),
        items_exercise.selectinload(Exercise.muscle_links).selectinload(ExerciseMuscle.muscle),
    )

def existing_exercise_ids(db: Session, ids: set) -> set:
    if not ids:
        return set()
    return set(db.scalars(select(Exercise.id).where(Exercise.id.in_(ids))))

def list_workout_sessions(db: Session, *, muscle: Optional[str], difficulty: Optional[str]) -> list:
    """Filters that SQL does well (muscle group, difficulty). Length is computed in the
    service because it is a sum over the session's exercises."""
    stmt = select(WorkoutSession).join(TrainingProgram, WorkoutSession.program_id == TrainingProgram.id)
    if difficulty:
        stmt = stmt.where(TrainingProgram.experience_level == difficulty)
    if muscle:
        # "targets this muscle" = at least one exercise in the session works it as a primary muscle
        stmt = stmt.where(WorkoutSession.items.any(SessionExercise.exercise.has(
            Exercise.muscle_links.any(and_(
                ExerciseMuscle.is_primary.is_(True),
                ExerciseMuscle.muscle.has(func.lower(MuscleGroup.name) == muscle.lower()))))))
    stmt = stmt.options(*_session_loads()).order_by(TrainingProgram.name, WorkoutSession.position)
    return list(db.scalars(stmt).all())

def get_workout_session(db: Session, session_id: int) -> Optional[WorkoutSession]:
    return db.scalar(select(WorkoutSession).options(*_session_loads()).where(WorkoutSession.id == session_id))