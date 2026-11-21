
"""Add program instances and prescription enrollment links.

Revision ID: 04
Revises: 0198097820da

Creates:
- program_instances
- workout_prescriptions.program_instance_id

Existing prescriptions remain valid with NULL
program_instance_id.

No historical prescription records are modified
or automatically assigned to an enrollment.
"""

from alembic import op
import sqlalchemy as sa


revision = "04"
down_revision = "0198097820da"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ----------------------------------------------
    # 1. Create program enrollment table
    # ----------------------------------------------

    op.create_table(
        "program_instances",

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
            "program_slug",
            sa.String(length=20),
            nullable=False,
        ),

        sa.Column(
            "source_baseline_id",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "status",
            sa.String(length=20),
            server_default="active",
            nullable=False,
        ),

        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),

        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_program_instances_user",
            ondelete="RESTRICT",
        ),

        sa.ForeignKeyConstraint(
            ["source_baseline_id"],
            ["program_baselines.id"],
            name="fk_program_instances_baseline",
            ondelete="RESTRICT",
        ),

        sa.CheckConstraint(
            "status IN ('active', 'completed', 'abandoned')",
            name="ck_program_instance_status",
        ),
    )

    op.create_index(
        "ix_program_instances_user_program",
        "program_instances",
        ["user_id", "program_slug"],
    )

    # ----------------------------------------------
    # 2. Link prescriptions to enrollments
    # ----------------------------------------------

    op.add_column(
        "workout_prescriptions",
        sa.Column(
            "program_instance_id",
            sa.BigInteger(),
            nullable=True,
        ),
    )

    op.create_foreign_key(
        "fk_workout_prescriptions_program_instance",
        "workout_prescriptions",
        "program_instances",
        ["program_instance_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.create_index(
        "ix_workout_prescriptions_program_instance_id",
        "workout_prescriptions",
        ["program_instance_id"],
    )


def downgrade() -> None:
    # ----------------------------------------------
    # 1. Remove prescription enrollment references
    # ----------------------------------------------

    op.drop_index(
        "ix_workout_prescriptions_program_instance_id",
        table_name="workout_prescriptions",
    )

    op.drop_constraint(
        "fk_workout_prescriptions_program_instance",
        "workout_prescriptions",
        type_="foreignkey",
    )

    op.drop_column(
        "workout_prescriptions",
        "program_instance_id",
    )

    # ----------------------------------------------
    # 2. Remove enrollment table
    # ----------------------------------------------

    op.drop_index(
        "ix_program_instances_user_program",
        table_name="program_instances",
    )

    op.drop_table("program_instances")
