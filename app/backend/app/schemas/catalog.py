from typing import Optional
from pydantic import BaseModel, ConfigDict

class NamedOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int                 # session_exercise id
    name: str

class ExerciseOut(BaseModel):
    id: int                # session_exercise id
    name: str
    category: Optional[str]
    description: Optional[str]
    difficulty: Optional[str]
    default_role: Optional[str]
    default_minutes: int
    primary_muscles: list[str]
    secondary_muscles: list[str]
    equipment: list[str]
    source: str
    license_name: Optional[str]
    license_author: Optional[str]

class ProgramOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int                 # session_exercise id
    name: str
    goal: str
    experience_level: str
    length_weeks: int
    description: Optional[str]

class WorkoutSummaryOut(BaseModel):
    """One planned Workout Session, as shown in the selection list."""
    id: int                 # session_exercise id
    name: str
    program_id: int
    program_name: str
    goal: str
    difficulty: str          # the Training Program's experience level
    total_minutes: int       # expected duration
    exercise_count: int
    muscle_groups: list[str]

class WorkoutExerciseOut(BaseModel):
    id: int                  # session_exercise id
    exercise_id: int
    name: str
    position: int
    role: str                # core | accessory
    droppable: bool          # accessory exercises may be dropped when short on time
    sets: Optional[int]
    reps: Optional[int]
    minutes: int
    equipment: list[str]
    primary_muscles: list[str]
    model_url: Optional[str] = None     # shows 3D model of exercise if available 
    video_url: Optional[str] = None     # demo video if available

class WorkoutDetailOut(WorkoutSummaryOut):
    guidance: Optional[str]
    exercises: list[WorkoutExerciseOut]