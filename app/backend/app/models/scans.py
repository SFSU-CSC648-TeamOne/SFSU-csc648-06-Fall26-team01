# Niantic posture scans (.glb) for an exercise: one row per key position (e.g. push-up top / bottom)

from typing import Optional

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

class ExerciseScan(Base):
    __tablename__ = "exercise_scans"
    __table_args__ = (UniqueConstraint("exercise_id", "position", name="uq_exercise_scans_position"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(default=1)      # 1 = first key position, 2 = second
    label: Mapped[str] = mapped_column(String(120))
    description: Mapped[Optional[str]] = mapped_column(Text)
    model_url: Mapped[str] = mapped_column(String(500))
    credit: Mapped[Optional[str]] = mapped_column(String(255))
