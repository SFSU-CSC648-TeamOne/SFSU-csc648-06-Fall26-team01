from typing import Optional

from pydantic import BaseModel, ConfigDict

class ExerciseModelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    exercise_id: int
    exercise_string: str
    model_url: str
    animation_name: Optional[str] = None
    credit: Optional[str] = None