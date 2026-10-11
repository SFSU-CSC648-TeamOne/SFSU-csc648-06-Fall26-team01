# logs the workout (workout_records) and the entries (sets, reps, weights)

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (CheckConstraint, DateTime, Float, ForeignKey, Integer, String,
                        Text, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.catalog import Exercise, WorkoutSession
from app.models.enums import EntryStatus, sql_in

class WorkoutRecord(Base):
    __tablename__ = "workout_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    workout_session_id: Mapped[Optional[int]] = mapped_column(ForeignKey("workout_sessions.id", ondelete="SET NULL"))
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    available_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    session: Mapped[Optional[WorkoutSession]] = relationship()
    entries: Mapped[List["PerformanceEntry"]] = relationship(
        back_populates="record", cascade="all, delete-orphan", order_by="PerformanceEntry.id")

class PerformanceEntry(Base):
    __tablename__ = "performance_entries"
    __table_args__ = (CheckConstraint(f"status IN ({sql_in(EntryStatus)})", name="ck_entries_status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    workout_record_id: Mapped[int] = mapped_column(ForeignKey("workout_records.id", ondelete="CASCADE"), index=True)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id"))
    set_number: Mapped[Optional[int]] = mapped_column(Integer)
    reps: Mapped[Optional[int]] = mapped_column(Integer)
    weight_kg: Mapped[Optional[float]] = mapped_column(Float)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    distance_m: Mapped[Optional[float]] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default=EntryStatus.completed.value,
                                        server_default=EntryStatus.completed.value)
    substituted_for_exercise_id: Mapped[Optional[int]] = mapped_column(ForeignKey("exercises.id"))

    record: Mapped[WorkoutRecord] = relationship(back_populates="entries")
    exercise: Mapped[Exercise] = relationship(foreign_keys=[exercise_id])