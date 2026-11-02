from typing import Optional

from pydantic import BaseModel, Field

from app.models.enums import ExperienceLevel

class ProfileIn(BaseModel):
    goals: list[str] = Field(default_factory=list, max_length=10)
    experience_level: Optional[ExperienceLevel] = None
    days_per_week: Optional[int] = Field(default=None, ge=1, le=7)
    session_minutes: Optional[int] = Field(default=None, ge=5, le=300)
    physical_constraints: Optional[str] = Field(default=None, max_length=2000)
    equipment_ids: list[int] = Field(default_factory=list, max_length=100)

class ProfileOut(BaseModel):
    goals: list[str]
    experience_level: Optional[str]
    days_per_week: Optional[int]
    session_minutes: Optional[int]
    physical_constraints: Optional[str]
    equipment_ids: list[int]
