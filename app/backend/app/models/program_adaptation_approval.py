"""Audit models for explicitly approved program-wide adaptations.

A ProgramAdaptationApproval represents one user-authorized
bulk operation affecting a single program enrollment.

Each ProgramAdaptationApprovalItem records one selected
prescription set and its before/after target values.

The original individual approval remains separate.
A preview alone never creates either audit record.

The application service must write both audit levels and
all prescription changes in one atomic transaction.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.db.base import Base, BigIntPK


class ProgramAdaptationApproval(Base):
    """One explicit program-wide approval operation."""

    __tablename__ = "program_adaptation_approvals"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "request_key",
            name="uq_program_adaptation_request",
        ),
        Index(
            "ix_program_adaptation_instance_approved",
            "program_instance_id",
            "approved_at",
        ),
        Index(
            "ix_program_adaptation_source_approval",
            "source_approval_id",
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

    program_instance_id: Mapped[int] = mapped_column(
        ForeignKey(
            "program_instances.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    source_approval_id: Mapped[int] = mapped_column(
        ForeignKey(
            "adaptation_approvals.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    # Caller-supplied idempotency key.
    # Repeated submissions with this key must never
    # apply the same progression twice.
    #
    # The application service must verify that a reused
    # key references the same authorized request payload.
    request_key: Mapped[str] = mapped_column(
        String(64),
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

    program_instance = relationship(
        "ProgramInstance",
    )

    source_approval = relationship(
        "AdaptationApproval",
    )

    items: Mapped[list["ProgramAdaptationApprovalItem"]] = relationship(
        "ProgramAdaptationApprovalItem",
        back_populates="approval",
        cascade="save-update, merge",
        order_by="ProgramAdaptationApprovalItem.id",
    )


class ProgramAdaptationApprovalItem(Base):
    """Audit one explicitly selected future set adjustment."""

    __tablename__ = "program_adaptation_approval_items"

    __table_args__ = (
        UniqueConstraint(
            "program_adaptation_approval_id",
            "prescription_set_id",
            name="uq_program_adaptation_item_set",
        ),
        CheckConstraint(
            "adjustment_type IN " "('reps', 'duration', 'weight')",
            name="ck_program_adaptation_item_type",
        ),
        CheckConstraint(
            "previous_value > 0",
            name="ck_program_adaptation_item_previous",
        ),
        CheckConstraint(
            "approved_value > previous_value",
            name="ck_program_adaptation_item_progression",
        ),
        Index(
            "ix_program_adaptation_item_set",
            "prescription_set_id",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigIntPK,
        primary_key=True,
    )

    program_adaptation_approval_id: Mapped[int] = mapped_column(
        ForeignKey(
            "program_adaptation_approvals.id",
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

    approval: Mapped["ProgramAdaptationApproval"] = relationship(
        "ProgramAdaptationApproval",
        back_populates="items",
    )

    prescription = relationship(
        "WorkoutPrescription",
    )

    prescription_set = relationship(
        "PrescriptionSet",
    )
