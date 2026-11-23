"""Training-phase metadata for workout prescriptions.

Classifies a prescribed workout as:
- training: normal progressive training
- deload: intentionally reduced training demands
- assessment: performance testing or reassessment

Unclassified prescriptions must not receive automatic
program-wide progression updates.
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, BigIntPK


class ProgramPhaseType(str, Enum):
    training = "training"
    deload = "deload"
    assessment = "assessment"


class ProgramPhase(Base):
    __tablename__ = "program_phases"

    __table_args__ = (
        UniqueConstraint(
            "workout_prescription_id",
            name="uq_program_phase_prescription",
        ),
        CheckConstraint(
            "phase_type IN " "('training', 'deload', 'assessment')",
            name="ck_program_phase_type",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigIntPK,
        primary_key=True,
    )

    workout_prescription_id: Mapped[int] = mapped_column(
        ForeignKey(
            "workout_prescriptions.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    phase_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    prescription: Mapped["WorkoutPrescription"] = relationship(
        "WorkoutPrescription",
    )

    @property
    def allows_automatic_progression(self) -> bool:
        """Only explicitly classified training can progress."""
        return self.phase_type == ProgramPhaseType.training.value
