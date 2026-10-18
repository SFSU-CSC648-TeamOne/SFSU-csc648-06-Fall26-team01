from typing import Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

class ExerciseModel(Base):
    __tablename__ = "exercise_models"

    id: Mapped[int] = mapped_column(primary_key=True)
    exercise_id: Mapped[int] = mapped_column(
        ForeignKey("exercises.id", ondelete="CASCADE"), unique=True, index=True
    )
    model_url: Mapped[str] = mapped_column(String(500))
    video_url: Mapped[Optional[str]] = mapped_column(String(500))
    animation_name: Mapped[Optional[str]] = mapped_column(String(100))  # clip inside the .glb
    credit: Mapped[Optional[str]] = mapped_column(String(255))          # model owner / license