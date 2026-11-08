# responses for users after completion of assessment

from typing import List, Optional
from pydantic import BaseModel

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