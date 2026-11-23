# logs the workout (workout_records) and the entries (sets, reps, weights)

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, BigIntPK
from app.models.catalog import Exercise, WorkoutSession
from app.models.enums import (
    CheckpointType,
    EntryStatus,
    LoadBasis,
    ObservationType,
    sql_in,
)


class WorkoutRecord(Base):
    __tablename__ = "workout_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    workout_session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("workout_sessions.id", ondelete="SET NULL")
    )
    performed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    available_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    program_slug: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    program_week: Mapped[Optional[int]] = mapped_column(Integer)
    program_day: Mapped[Optional[int]] = mapped_column(Integer)

    session: Mapped[Optional[WorkoutSession]] = relationship()
    entries: Mapped[List["PerformanceEntry"]] = relationship(
        back_populates="record",
        cascade="all, delete-orphan",
        order_by="PerformanceEntry.id",
    )


class PerformanceEntry(Base):
    __tablename__ = "performance_entries"

    __table_args__ = (
        CheckConstraint(f"status IN ({sql_in(EntryStatus)})", name="ck_entries_status"),
        CheckConstraint(
            f"observation_type IN ({sql_in(ObservationType)})",
            name="ck_entries_observation_type",
        ),
        CheckConstraint(
            f"load_basis IS NULL OR load_basis IN ({sql_in(LoadBasis)})",
            name="ck_entries_load_basis",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workout_record_id: Mapped[int] = mapped_column(
        ForeignKey("workout_records.id", ondelete="CASCADE"), index=True
    )
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id"))
    set_number: Mapped[Optional[int]] = mapped_column(Integer)
    reps: Mapped[Optional[int]] = mapped_column(Integer)
    weight_kg: Mapped[Optional[float]] = mapped_column(Float)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    distance_m: Mapped[Optional[float]] = mapped_column(Float)
    status: Mapped[str] = mapped_column(
        String(20),
        default=EntryStatus.completed.value,
        server_default=EntryStatus.completed.value,
    )
    substituted_for_exercise_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("exercises.id")
    )

    # newly added on 11-16-26
    prescription_set_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("prescription_sets.id", ondelete="SET NULL"), index=True
    )
    observation_type: Mapped[str] = mapped_column(
        String(20),
        default=ObservationType.training.value,
        server_default=ObservationType.training.value,
    )
    load_basis: Mapped[Optional[str]] = mapped_column(String(30))
    assistance_kg: Mapped[Optional[float]] = mapped_column(Float)
    is_user_modified: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )

    record: Mapped[WorkoutRecord] = relationship(back_populates="entries")
    exercise: Mapped[Exercise] = relationship(foreign_keys=[exercise_id])


class BodyweightMeasurement(Base):
    __tablename__ = "bodyweight_measurements"
    __table_args__ = (CheckConstraint("weight_kg > 0", name="ck_bodyweight_positive"),)

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    measurement_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    measured_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ProgressCheckpoint(Base):
    __tablename__ = "progress_checkpoints"
    __table_args__ = (
        CheckConstraint(
            f"checkpoint_type IN ({sql_in(CheckpointType)})", name="ck_checkpoints_type"
        ),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    checkpoint_type: Mapped[str] = mapped_column(String(20))
    metrics_json: Mapped[dict] = mapped_column(JSON)
    calculation_version: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
