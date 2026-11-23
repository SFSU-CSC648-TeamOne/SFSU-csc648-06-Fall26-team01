"""Individual user enrollments in training programs.

A ProgramInstance represents one distinct run of a training
program by a user.

A user may repeat the same program, including with the same
assessment baseline, without mixing workout prescriptions
between separate enrollments.

Program-wide adaptations must be scoped to one
ProgramInstance, not merely a program slug or baseline.
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, BigIntPK


class ProgramInstanceStatus(str, Enum):
    active = "active"
    completed = "completed"
    abandoned = "abandoned"


class ProgramInstance(Base):
    __tablename__ = "program_instances"

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'completed', 'abandoned')",
            name="ck_program_instance_status",
        ),
        Index(
            "ix_program_instances_user_program",
            "user_id",
            "program_slug",
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

    program_slug: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    prescriptions: Mapped[list["WorkoutPrescription"]] = relationship(
        "WorkoutPrescription",
        back_populates="program_instance",
    )

    source_baseline_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "program_baselines.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ProgramInstanceStatus.active.value,
        server_default=ProgramInstanceStatus.active.value,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user = relationship("User")
    source_baseline = relationship("ProgramBaseline")
