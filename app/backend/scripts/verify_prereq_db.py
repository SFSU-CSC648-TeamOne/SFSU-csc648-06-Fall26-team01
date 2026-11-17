
"""Read-only database verification for adaptive-engine prerequisites.

Run from app/backend:
    python scripts/verify_prereq_db.py

Uses the configured DATABASE_URL.
Does not create or modify database objects.
"""

import sys

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from app.db.session import engine


REQUIRED_COLUMNS = {
    "users": {
        "id",
    },
    "exercises": {
        "id",
        "name",
    },
    "workout_records": {
        "id",
        "user_id",
        "performed_at",
        "program_slug",
        "program_week",
        "program_day",
    },
    "performance_entries": {
        "id",
        "workout_record_id",
        "exercise_id",
        "set_number",
        "reps",
        "weight_kg",
        "duration_seconds",
        "status",
        "substituted_for_exercise_id",
        "prescription_set_id",
        "observation_type",
        "load_basis",
        "assistance_kg",
        "is_user_modified",
    },
    "workout_prescriptions": {
        "id",
        "user_id",
        "program_slug",
        "program_week",
        "program_day",
        "engine_version",
        "status",
    },
    "prescription_sets": {
        "id",
        "workout_prescription_id",
        "exercise_id",
        "set_number",
        "target_reps",
        "target_duration_seconds",
        "target_weight_kg",
        "load_basis",
    },
    "bodyweight_measurements": {
        "id",
        "user_id",
        "weight_kg",
        "measurement_date",
        "timezone",
        "measured_at",
    },
    "movement_groups": {
        "id",
        "name",
    },
    "exercise_movement_groups": {
        "exercise_id",
        "movement_group_id",
        "relationship_type",
        "relevance_weight",
    },
    "progress_checkpoints": {
        "id",
        "user_id",
        "period_start",
        "period_end",
        "checkpoint_type",
        "metrics_json",
        "calculation_version",
    },
}


REQUIRED_FOREIGN_KEYS = {
    ("performance_entries", "workout_record_id"):
        "workout_records",
    ("performance_entries", "exercise_id"):
        "exercises",
    ("performance_entries", "prescription_set_id"):
        "prescription_sets",
    ("workout_prescriptions", "user_id"):
        "users",
    ("prescription_sets", "workout_prescription_id"):
        "workout_prescriptions",
    ("bodyweight_measurements", "user_id"):
        "users",
    ("exercise_movement_groups", "exercise_id"):
        "exercises",
    ("exercise_movement_groups", "movement_group_id"):
        "movement_groups",
    ("progress_checkpoints", "user_id"):
        "users",
}


def verify_schema(connection):
    inspector = inspect(connection)
    existing_tables = set(inspector.get_table_names())
    problems = []

    print("\nDATABASE SCHEMA")
    print("-" * 50)

    for table, required in REQUIRED_COLUMNS.items():
        if table not in existing_tables:
            print(f"[FAIL] {table}: missing table")
            problems.append(f"Missing table: {table}")
            continue

        columns = {
            column["name"]
            for column in inspector.get_columns(table)
        }

        missing = sorted(required - columns)

        if missing:
            print(
                f"[FAIL] {table}: missing columns "
                + ", ".join(missing)
            )
            problems.append(
                f"{table}: missing {', '.join(missing)}"
            )
        else:
            print(f"[PASS] {table}")

    print("\nFOREIGN KEYS")
    print("-" * 50)

    for (table, column), target in REQUIRED_FOREIGN_KEYS.items():
        if table not in existing_tables:
            continue

        keys = inspector.get_foreign_keys(table)

        valid = any(
            column in key.get("constrained_columns", [])
            and key.get("referred_table") == target
            for key in keys
        )

        if valid:
            print(f"[PASS] {table}.{column} -> {target}")
        else:
            print(f"[FAIL] {table}.{column} -> {target}")
            problems.append(
                f"Missing foreign key: {table}.{column}"
            )

    return problems


def verify_migrations(connection):
    print("\nALEMBIC MIGRATIONS")
    print("-" * 50)

    config = Config("alembic.ini")
    scripts = ScriptDirectory.from_config(config)

    expected = set(scripts.get_heads())
    current = set(
        MigrationContext.configure(connection)
        .get_current_heads()
    )

    print("Expected heads:", sorted(expected))
    print("Database heads:", sorted(current))

    if current == expected:
        print("[PASS] Database is at Alembic head")
        return []

    print("[FAIL] Database migration state differs")
    return ["Database is not at the expected Alembic head"]


def main():
    problems = []

    # Open a transaction and roll it back on exit.
    # All inspection queries are read-only.
    with engine.connect() as connection:
        transaction = connection.begin()

        try:
            dialect = connection.dialect.name
            print("Database dialect:", dialect)

            if dialect != "postgresql":
                print(
                    "[WARN] This is not PostgreSQL. "
                    "Use your staging PostgreSQL database "
                    "for final verification."
                )

            problems.extend(
                verify_schema(connection)
            )

            problems.extend(
                verify_migrations(connection)
            )
        finally:
            transaction.rollback()

    print("\nVERIFICATION RESULT")
    print("=" * 50)

    if problems:
        print(f"FAILED: {len(problems)} issue(s) found.")

        for problem in problems:
            print(" -", problem)

        return 1

    print("PASSED: Schema and migration checks succeeded.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(
            f"Verification could not complete: "
            f"{type(exc).__name__}: {exc}"
        )
        sys.exit(1)
