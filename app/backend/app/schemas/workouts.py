# logging the workouts from the user

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field
from app.models.enums import EntryStatus

class EntryIn(BaseModel):
    exercise_id: int
    set_number: Optional[int] = Field(default=None, ge=1, le=100)
    reps: Optional[int] = Field(default=None, ge=0, le=1000)
    weight_kg: Optional[float] = Field(default=None, ge=0, le=2000)
    duration_seconds: Optional[int] = Field(default=None, ge=0, le=86400)
    distance_m: Optional[float] = Field(default=None, ge=0)
    status: EntryStatus = EntryStatus.completed
    substituted_for_exercise_id: Optional[int] = None

class WorkoutRecordIn(BaseModel):
    workout_session_id: Optional[int] = None
    performed_at: Optional[datetime] = None
    available_minutes: Optional[int] = Field(default=None, ge=1, le=600)
    duration_minutes: Optional[int] = Field(default=None, ge=1, le=600)
    notes: Optional[str] = Field(default=None, max_length=2000)
    entries: list[EntryIn] = Field(min_length=1, max_length=500)

class EntryOut(BaseModel):
    id: int
    exercise_id: int
    exercise_name: str
    set_number: Optional[int]
    reps: Optional[int]
    weight_kg: Optional[float]
    duration_seconds: Optional[int]
    distance_m: Optional[float]
    status: str
    substituted_for_exercise_id: Optional[int]

class WorkoutRecordSummary(BaseModel):
    id: int
    workout_session_id: Optional[int]
    session_name: Optional[str]
    performed_at: datetime
    available_minutes: Optional[int]
    duration_minutes: Optional[int]
    entry_count: int

class WorkoutRecordOut(WorkoutRecordSummary):
    notes: Optional[str]
    entries: list[EntryOut]