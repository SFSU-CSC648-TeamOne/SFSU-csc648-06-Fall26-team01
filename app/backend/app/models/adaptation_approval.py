"""Audit records for user-approved training adaptations.

Each record represents one approved change to a
prescription set.

Records preserve:
- Who approved the adjustment
- Which prescription and set were modified
- Original and approved targets
- Adjustment type and approval timestamp
- Recommendation engine version

Approval records must be written in the same
transaction as the prescription update.
"""

from datetime import datetime
from enum import Enum
from decimal import Decimal
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, BigIntPK


class AdaptationAdjustmentType(str, Enum):
    reps = "reps"
    duration = "duration"
    weight = "weight"


class AdaptationApproval(Base):
    __tablename__ = "adaptation_approvals"

    __table_args__ = (
        CheckConstraint(
            "adjustment_type IN " "('reps', 'duration', 'weight')",
            name="ck_adaptation_approval_type",
        ),
        CheckConstraint(
            "previous_value > 0",
            name="ck_adaptation_approval_previous_positive",
        ),
        CheckConstraint(
            "approved_value > 0",
            name="ck_adaptation_approval_approved_positive",
        ),
        CheckConstraint(
            "approved_value <> previous_value",
            name="ck_adaptation_approval_value_changed",
        ),
        Index(
            "ix_adaptation_approvals_user_approved",
            "user_id",
            "approved_at",
        ),
        Index(
            "ix_adaptation_approvals_set_approved",
            "prescription_set_id",
            "approved_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigIntPK,
        primary_key=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    workout_prescription_id: Mapped[int] = mapped_column(
        ForeignKey(
            "workout_prescriptions.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    prescription_set_id: Mapped[int] = mapped_column(
        ForeignKey(
            "prescription_sets.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    adjustment_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    previous_value: Mapped[Decimal] = mapped_column(
        Numeric(12, 2, asdecimal=True),
        nullable=False,
    )

    approved_value: Mapped[Decimal] = mapped_column(
        Numeric(12, 2, asdecimal=True),
        nullable=False,
    )

    proposal_engine_version: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user = relationship(
        "User",
    )

    prescription = relationship(
        "WorkoutPrescription",
    )

    prescription_set = relationship(
        "PrescriptionSet",
    )
