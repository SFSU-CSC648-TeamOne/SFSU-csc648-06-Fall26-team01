from typing import Optional

from pydantic import BaseModel, ConfigDict

class ExerciseModelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    exercise_id: int
    exercise_name: str
    model_url: str
    video_url: Optional[str] = None
    animation_name: Optional[str] = None
    credit: Optional[str] = None