# prescriptions, bodyweight, movement groups, checkpoints

# version: 02

import sqlalchemy as sa
from alembic import op

revision = "02"
down_revision = "01"
branch_labels = None
depends_on = None

LOAD_BASES = ("none", "bodyweight", "added", "external", "assisted")


def _in(values) -> str:
    return ", ".join("'%s'" % v for v in values)


def upgrade() -> None:
    # 1. bodyweight values
    op.create_table(
        "bodyweight_measurements",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("weight_kg", sa.Numeric(6, 2), nullable=False),
        sa.Column(
            "measured_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_bodyweight_measurements_user_id", "bodyweight_measurements", ["user_id"]
    )
    op.create_index(
        "ix_bodyweight_measurements_measured_at",
        "bodyweight_measurements",
        ["measured_at"],
    )

    # 2. movement group values
    op.create_table(
        "movement_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column(
            "parent_group_id",
            sa.Integer(),
            sa.ForeignKey("movement_groups.id", ondelete="SET NULL"),
        ),
    )
    op.create_index(
        "ix_movement_groups_parent_group_id", "movement_groups", ["parent_group_id"]
    )
    op.create_table(
        "exercise_movement_groups",
        sa.Column(
            "exercise_id",
            sa.Integer(),
            sa.ForeignKey("exercises.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "movement_group_id",
            sa.Integer(),
            sa.ForeignKey("movement_groups.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "relationship_type", sa.String(20), nullable=False, server_default="primary"
        ),
        sa.Column("relevance_weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.CheckConstraint(
            "relationship_type IN ('primary', 'secondary')", name="ck_emg_relationship"
        ),
        sa.CheckConstraint(
            "relevance_weight >= 0 AND relevance_weight <= 1", name="ck_emg_weight"
        ),
    )

    # 3. prescriptions values
    op.create_table(
        "workout_prescriptions",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workout_session_id",
            sa.Integer(),
            sa.ForeignKey("workout_sessions.id", ondelete="SET NULL"),
        ),
        sa.Column("program_slug", sa.String(20), nullable=False),
        sa.Column("program_week", sa.Integer(), nullable=False),
        sa.Column("program_day", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="planned"),
        sa.Column("engine_version", sa.String(30), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "source_baseline_id",
            sa.Integer(),
            sa.ForeignKey("program_baselines.id", ondelete="SET NULL"),
        ),
        sa.CheckConstraint(
            "status IN ('planned', 'completed', 'skipped', 'superseded')",
            name="ck_prescriptions_status",
        ),
    )
    op.create_index(
        "ix_workout_prescriptions_user_id", "workout_prescriptions", ["user_id"]
    )
    op.create_index(
        "ix_workout_prescriptions_program_slug",
        "workout_prescriptions",
        ["program_slug"],
    )
    op.create_table(
        "prescription_sets",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "workout_prescription_id",
            sa.BigInteger(),
            sa.ForeignKey("workout_prescriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "exercise_id", sa.Integer(), sa.ForeignKey("exercises.id"), nullable=False
        ),
        sa.Column("set_number", sa.Integer(), nullable=False),
        sa.Column("target_reps", sa.Integer()),
        sa.Column("target_duration_seconds", sa.Integer()),
        sa.Column("target_weight_kg", sa.Numeric(6, 2)),
        sa.Column("load_basis", sa.String(30), nullable=False, server_default="none"),
        sa.Column(
            "is_optional", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.CheckConstraint(
            "load_basis IN (%s)" % _in(LOAD_BASES),
            name="ck_prescription_sets_load_basis",
        ),
    )
    op.create_index(
        "ix_prescription_sets_workout_prescription_id",
        "prescription_sets",
        ["workout_prescription_id"],
    )

    # 4. performance_entries: new columns are nullable or defaulted, so existing rows stay valid
    op.add_column(
        "performance_entries",
        sa.Column(
            "prescription_set_id",
            sa.BigInteger(),
            sa.ForeignKey("prescription_sets.id", ondelete="SET NULL"),
        ),
    )
    op.add_column(
        "performance_entries",
        sa.Column(
            "observation_type", sa.String(20), nullable=False, server_default="training"
        ),
    )
    op.add_column("performance_entries", sa.Column("load_basis", sa.String(30)))
    op.add_column("performance_entries", sa.Column("assistance_kg", sa.Float()))
    op.add_column(
        "performance_entries",
        sa.Column(
            "is_user_modified", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.create_check_constraint(
        "ck_entries_observation_type",
        "performance_entries",
        "observation_type IN ('training', 'benchmark')",
    )
    op.create_check_constraint(
        "ck_entries_load_basis",
        "performance_entries",
        "load_basis IS NULL OR load_basis IN (%s)" % _in(LOAD_BASES),
    )
    op.create_index(
        "ix_performance_entries_prescription_set_id",
        "performance_entries",
        ["prescription_set_id"],
    )

    # 5. checkpoints values
    op.create_table(
        "progress_checkpoints",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("checkpoint_type", sa.String(20), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("calculation_version", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "checkpoint_type IN ('weekly', 'program_end')", name="ck_checkpoints_type"
        ),
    )
    op.create_index(
        "ix_progress_checkpoints_user_id", "progress_checkpoints", ["user_id"]
    )

    # 6. baselines: existing rows become schema_version 1
    op.add_column(
        "program_baselines",
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column("program_baselines", sa.Column("bodyweight_kg", sa.Numeric(6, 2)))


def downgrade() -> None:
    op.drop_column("program_baselines", "bodyweight_kg")
    op.drop_column("program_baselines", "schema_version")
    op.drop_index("ix_progress_checkpoints_user_id", table_name="progress_checkpoints")
    op.drop_table("progress_checkpoints")
    op.drop_index(
        "ix_performance_entries_prescription_set_id", table_name="performance_entries"
    )
    op.drop_constraint("ck_entries_load_basis", "performance_entries", type_="check")
    op.drop_constraint(
        "ck_entries_observation_type", "performance_entries", type_="check"
    )
    for col in (
        "is_user_modified",
        "assistance_kg",
        "load_basis",
        "observation_type",
        "prescription_set_id",
    ):
        op.drop_column("performance_entries", col)
    op.drop_index(
        "ix_prescription_sets_workout_prescription_id", table_name="prescription_sets"
    )
    op.drop_table("prescription_sets")
    op.drop_index(
        "ix_workout_prescriptions_program_slug", table_name="workout_prescriptions"
    )
    op.drop_index(
        "ix_workout_prescriptions_user_id", table_name="workout_prescriptions"
    )
    op.drop_table("workout_prescriptions")
    op.drop_table("exercise_movement_groups")
    op.drop_index("ix_movement_groups_parent_group_id", table_name="movement_groups")
    op.drop_table("movement_groups")
    op.drop_index(
        "ix_bodyweight_measurements_measured_at", table_name="bodyweight_measurements"
    )
    op.drop_index(
        "ix_bodyweight_measurements_user_id", table_name="bodyweight_measurements"
    )
    op.drop_table("bodyweight_measurements")
