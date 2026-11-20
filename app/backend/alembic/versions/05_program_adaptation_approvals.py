
"""Add program-wide adaptation approval audit tables.

Revision ID: 05
Revises: 04

Creates:
- program_adaptation_approvals
- program_adaptation_approval_items

No existing prescription or approval data is modified.
"""

from alembic import op
import sqlalchemy as sa


revision = "05"
down_revision = "04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --------------------------------------------------
    # 1. Program-wide approval events
    # --------------------------------------------------

    op.create_table(
        "program_adaptation_approvals",

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
            "program_instance_id",
            sa.BigInteger(),
            nullable=False,
        ),

        sa.Column(
            "source_approval_id",
            sa.BigInteger(),
            nullable=False,
        ),

        sa.Column(
            "request_key",
            sa.String(length=64),
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

        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_program_adaptation_user",
            ondelete="RESTRICT",
        ),

        sa.ForeignKeyConstraint(
            ["program_instance_id"],
            ["program_instances.id"],
            name="fk_program_adaptation_instance",
            ondelete="RESTRICT",
        ),

        sa.ForeignKeyConstraint(
            ["source_approval_id"],
            ["adaptation_approvals.id"],
            name="fk_program_adaptation_source_approval",
            ondelete="RESTRICT",
        ),

        sa.UniqueConstraint(
            "user_id",
            "request_key",
            name="uq_program_adaptation_request",
        ),
    )

    op.create_index(
        "ix_program_adaptation_instance_approved",
        "program_adaptation_approvals",
        ["program_instance_id", "approved_at"],
    )

    op.create_index(
        "ix_program_adaptation_source_approval",
        "program_adaptation_approvals",
        ["source_approval_id"],
    )

    # --------------------------------------------------
    # 2. Individually approved target changes
    # --------------------------------------------------

    op.create_table(
        "program_adaptation_approval_items",

        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),

        sa.Column(
            "program_adaptation_approval_id",
            sa.BigInteger(),
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
            sa.Numeric(12, 2, asdecimal=True),
            nullable=False,
        ),

        sa.Column(
            "approved_value",
            sa.Numeric(12, 2, asdecimal=True),
            nullable=False,
        ),

        sa.ForeignKeyConstraint(
            ["program_adaptation_approval_id"],
            ["program_adaptation_approvals.id"],
            name="fk_program_adaptation_item_approval",
            ondelete="RESTRICT",
        ),

        sa.ForeignKeyConstraint(
            ["workout_prescription_id"],
            ["workout_prescriptions.id"],
            name="fk_program_adaptation_item_prescription",
            ondelete="RESTRICT",
        ),

        sa.ForeignKeyConstraint(
            ["prescription_set_id"],
            ["prescription_sets.id"],
            name="fk_program_adaptation_item_set",
            ondelete="RESTRICT",
        ),

        sa.UniqueConstraint(
            "program_adaptation_approval_id",
            "prescription_set_id",
            name="uq_program_adaptation_item_set",
        ),

        sa.CheckConstraint(
            "adjustment_type IN "
            "('reps', 'duration', 'weight')",
            name="ck_program_adaptation_item_type",
        ),

        sa.CheckConstraint(
            "previous_value > 0",
            name="ck_program_adaptation_item_previous",
        ),

        sa.CheckConstraint(
            "approved_value > previous_value",
            name="ck_program_adaptation_item_progression",
        ),
    )

    op.create_index(
        "ix_program_adaptation_item_set",
        "program_adaptation_approval_items",
        ["prescription_set_id"],
    )


def downgrade() -> None:
    # Destructive: removes program-wide audit history.
    # Never run against a shared or production database.

    op.drop_index(
        "ix_program_adaptation_item_set",
        table_name="program_adaptation_approval_items",
    )

    op.drop_table(
        "program_adaptation_approval_items"
    )

    op.drop_index(
        "ix_program_adaptation_source_approval",
        table_name="program_adaptation_approvals",
    )

    op.drop_index(
        "ix_program_adaptation_instance_approved",
        table_name="program_adaptation_approvals",
    )

    op.drop_table(
        "program_adaptation_approvals"
    )
