# responses for users after completion of assessment

from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime 

class ExerciseAdvice(BaseModel):
    exercise_id: int
    name: str
    muscles: List[str]
    sessions: int
    sets_now: int
    change_pct: Optional[float]
    sets_skipped: int
    add_sets: int
    suggested_sets: int
    advice: str

class ProgramAssessmentOut(BaseModel):
    program: Optional[str]
    score: int
    summary: str
    days_completed: int
    days_total: Optional[int]
    completion_pct: float
    exercises: List[ExerciseAdvice]

# progress for each category (prescribed, actual, trend, baseline)
class BaselineOut(BaseModel):
    value: int
    load_kg: Optional[float]
    taken_at: datetime

class PointOut(BaseModel):
    session: int
    week: int
    day: int
    prescribed: int
    actual: int

class TrendOut(BaseModel):
    m_prescribed: float
    m_actual: float
    m_next: float

class CategoryProgressOut(BaseModel):
    key: str # the exercise baseline (aka push-up, etc)
    label: str
    unit: str # reps / seconds
    baseline: Optional[BaselineOut]
    current_best: Optional[int] # best set in latest session
    change_pct: Optional[float] # current_best vs baseline
    points: List[PointOut]
    trend: Optional[TrendOut] # no trends until there are 2 or more sessions
    note: str

class ProgramProgressOut(BaseModel):
    program: str
    categories: List[CategoryProgressOut]