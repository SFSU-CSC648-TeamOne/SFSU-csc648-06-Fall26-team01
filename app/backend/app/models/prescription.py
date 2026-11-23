"""Persisted workout prescriptions and their exercise-set targets.

WorkoutPrescription stores the user's planned workout.
PrescriptionSet stores each prescribed exercise target.

New prescriptions may belong to a ProgramInstance, identifying
one specific enrollment in a training program.

Legacy prescriptions may have no program_instance_id.
Existing prescription and performance relationships are preserved.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, BigIntPK
from app.models.enums import LoadBasis, PrescriptionStatus, sql_in


class WorkoutPrescription(Base):
    __tablename__ = "workout_prescriptions"

    __table_args__ = (
        CheckConstraint(
            f"status IN ({sql_in(PrescriptionStatus)})",
            name="ck_prescriptions_status",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigIntPK,
        primary_key=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    workout_session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey(
            "workout_sessions.id",
            ondelete="SET NULL",
        )
    )

    # Enrollment identity for new program prescriptions.
    #
    # Nullable for backward compatibility with historical
    # prescriptions created before ProgramInstance existed.
    #
    # Application-level enrollment creation must verify that
    # user_id and program_slug agree with the referenced instance.
    program_instance_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey(
            "program_instances.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )

    program_slug: Mapped[str] = mapped_column(
        String(20),
        index=True,
    )

    program_week: Mapped[int] = mapped_column(Integer)

    program_day: Mapped[int] = mapped_column(Integer)

    status: Mapped[str] = mapped_column(
        String(20),
        default=PrescriptionStatus.planned.value,
        server_default=PrescriptionStatus.planned.value,
    )

    engine_version: Mapped[str] = mapped_column(String(30))

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    source_baseline_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey(
            "program_baselines.id",
            ondelete="SET NULL",
        )
    )

    # The relationship does not require an enrollment for
    # legacy prescriptions.
    program_instance: Mapped[Optional["ProgramInstance"]] = relationship(
        "ProgramInstance",
        back_populates="prescriptions",
    )

    sets: Mapped[List["PrescriptionSet"]] = relationship(
        back_populates="prescription",
        cascade="all, delete-orphan",
        order_by="PrescriptionSet.set_number",
    )


class PrescriptionSet(Base):
    __tablename__ = "prescription_sets"

    __table_args__ = (
        CheckConstraint(
            f"load_basis IN ({sql_in(LoadBasis)})",
            name="ck_prescription_sets_load_basis",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigIntPK,
        primary_key=True,
    )

    workout_prescription_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "workout_prescriptions.id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id"))

    set_number: Mapped[int] = mapped_column(Integer)

    target_reps: Mapped[Optional[int]] = mapped_column(Integer)

    target_duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)

    target_weight_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))

    load_basis: Mapped[str] = mapped_column(
        String(30),
        default=LoadBasis.none.value,
        server_default=LoadBasis.none.value,
    )

    is_optional: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=false(),
    )

    prescription: Mapped[WorkoutPrescription] = relationship(back_populates="sets")
