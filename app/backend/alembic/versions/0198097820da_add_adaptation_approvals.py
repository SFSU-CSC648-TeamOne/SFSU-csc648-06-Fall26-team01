"""add adaptation approvals

Revision ID: 0198097820da
Revises: 590867838351
Create Date: 2026-11-18 07:46:12.016064

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0198097820da'
down_revision: Union[str, None] = '590867838351'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "adaptation_approvals",

        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),

        sa.Column(
            "user_id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "workout_prescription_id",
            sa.BigInteger(),
            nullable=False,
        ),

        sa.Column(
            "prescription_set_id",
            sa.BigInteger(),
            nullable=False,
        ),

        sa.Column(
            "adjustment_type",
            sa.String(length=20),
            nullable=False,
        ),

        sa.Column(
            "previous_value",
            sa.Numeric(12, 2),
            nullable=False,
        ),

        sa.Column(
            "approved_value",
            sa.Numeric(12, 2),
            nullable=False,
        ),

        sa.Column(
            "proposal_engine_version",
            sa.String(length=40),
            nullable=False,
        ),

        sa.Column(
            "approved_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),

        # Foreign keys
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_adaptation_approval_user",
            ondelete="RESTRICT",
        ),

        sa.ForeignKeyConstraint(
            ["workout_prescription_id"],
            ["workout_prescriptions.id"],
            name="fk_adaptation_approval_prescription",
            ondelete="RESTRICT",
        ),

        sa.ForeignKeyConstraint(
            ["prescription_set_id"],
            ["prescription_sets.id"],
            name="fk_adaptation_approval_set",
            ondelete="RESTRICT",
        ),

        # Adjustment type validation
        sa.CheckConstraint(
            "adjustment_type IN "
            "('reps', 'duration', 'weight')",
            name="ck_adaptation_approval_type",
        ),

        # Target validation
        sa.CheckConstraint(
            "previous_value > 0",
            name="ck_adaptation_approval_previous_positive",
        ),

        sa.CheckConstraint(
            "approved_value > 0",
            name="ck_adaptation_approval_approved_positive",
        ),

        sa.CheckConstraint(
            "approved_value <> previous_value",
            name="ck_adaptation_approval_value_changed",
        ),
    )

    # Approval history by user
    op.create_index(
        "ix_adaptation_approvals_user_approved",
        "adaptation_approvals",
        ["user_id", "approved_at"],
    )

    # Approval history by prescription set
    op.create_index(
        "ix_adaptation_approvals_set_approved",
        "adaptation_approvals",
        ["prescription_set_id", "approved_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_adaptation_approvals_set_approved",
        table_name="adaptation_approvals",
    )

    op.drop_index(
        "ix_adaptation_approvals_user_approved",
        table_name="adaptation_approvals",
    )

    op.drop_table("adaptation_approvals")