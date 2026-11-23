"""add program phases

Revision ID: 5ccfa689be01
Revises: 02
Create Date: 2026-11-17 12:51:24.670921

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "5ccfa689be01"
down_revision: Union[str, None] = "02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "program_phases",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "workout_prescription_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "phase_type",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "reason",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workout_prescription_id"],
            ["workout_prescriptions.id"],
            name="fk_program_phase_prescription",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "workout_prescription_id",
            name="uq_program_phase_prescription",
        ),
        sa.CheckConstraint(
            "phase_type IN " "('training', 'deload', 'assessment')",
            name="ck_program_phase_type",
        ),
    )

    op.create_index(
        "ix_program_phases_workout_prescription_id",
        "program_phases",
        ["workout_prescription_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_program_phases_workout_prescription_id",
        table_name="program_phases",
    )

    op.drop_table("program_phases")
