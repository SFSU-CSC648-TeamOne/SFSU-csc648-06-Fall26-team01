from typing import Optional

from pydantic import BaseModel, ConfigDict

class ExerciseScanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    exercise_id: int
    position: int
    label: str
    description: Optional[str]
    model_url: str
    credit: Optional[str]
