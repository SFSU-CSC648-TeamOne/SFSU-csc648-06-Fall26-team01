"""Add local date and timezone to bodyweight measurements.

Revision ID: 03
Revises: 02
"""

from alembic import op
import sqlalchemy as sa

revision = "03"
down_revision = "02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add columns as nullable so existing rows remain valid.
    op.add_column(
        "bodyweight_measurements",
        sa.Column("measurement_date", sa.Date(), nullable=True),
    )

    op.add_column(
        "bodyweight_measurements",
        sa.Column("timezone", sa.String(64), nullable=True),
    )

    # 2. Preserve historical observations.
    # The original timezone is unknown, so use the
    # UTC calendar date of the existing timestamp.
    # Do not invent a timezone for legacy records.
    op.execute("""
        UPDATE bodyweight_measurements
        SET measurement_date =
            (measured_at AT TIME ZONE 'UTC')::date
        WHERE measurement_date IS NULL
        """)

    # 3. Require a measurement date going forward.
    op.alter_column(
        "bodyweight_measurements",
        "measurement_date",
        existing_type=sa.Date(),
        nullable=False,
    )

    # 4. Allow historical date-only observations
    # without inventing an exact measurement time.
    op.alter_column(
        "bodyweight_measurements",
        "measured_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        server_default=None,
    )

    # 5. Enforce positive bodyweight measurements.
    op.create_check_constraint(
        "ck_bodyweight_positive",
        "bodyweight_measurements",
        "weight_kg > 0",
    )

    op.create_index(
        "ix_bodyweight_measurements_measurement_date",
        "bodyweight_measurements",
        ["measurement_date"],
    )


def downgrade() -> None:
    connection = op.get_bind()

    # Previous schema requires measured_at for every row.
    # Refuse to invent timestamps for date-only records.
    missing = connection.execute(sa.text("""
            SELECT COUNT(*)
            FROM bodyweight_measurements
            WHERE measured_at IS NULL
            """)).scalar_one()

    if missing:
        raise RuntimeError(
            "Cannot downgrade: date-only bodyweight "
            "measurements exist without exact timestamps."
        )

    op.drop_index(
        "ix_bodyweight_measurements_measurement_date",
        table_name="bodyweight_measurements",
    )

    op.drop_constraint(
        "ck_bodyweight_positive",
        "bodyweight_measurements",
        type_="check",
    )

    op.alter_column(
        "bodyweight_measurements",
        "measured_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    )

    op.drop_column(
        "bodyweight_measurements",
        "timezone",
    )

    op.drop_column(
        "bodyweight_measurements",
        "measurement_date",
    )
