"""Verify Ascenda Alembic upgrade 04 -> 05.

From app/backend:
    python scripts/verify_adaptive_migrations.py

Safety:
- Uses only local 127.0.0.1:5433/ascenda_test.
- Creates a uniquely named disposable PostgreSQL schema.
- Runs the real Alembic migrations in that schema.
- Inserts representative legacy data at revision 04.
- Upgrades to revision 05.
- Verifies legacy data survives unchanged.
- Deletes only the temporary schema.
- Never downgrades or modifies shared databases.
"""

import os
import subprocess
import sys
from getpass import getpass
from pathlib import Path
from uuid import uuid4

from sqlalchemy import (
    URL,
    create_engine,
    inspect,
    text,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import app.models
from app.db.base import Base

OLD_REVISION = "04"
NEW_REVISION = "05"


def database_url() -> URL:
    url = URL.create(
        "postgresql+psycopg",
        username="devuser",
        password=getpass("Local PostgreSQL password: "),
        host="127.0.0.1",
        port=5433,
        database="ascenda_test",
    )

    if (
        url.host != "127.0.0.1"
        or url.port != 5433
        or url.database != "ascenda_test"
        or url.username != "devuser"
    ):
        raise RuntimeError("Refusing non-test database.")

    return url


def run_alembic(
    url: URL,
    revision: str,
    *,
    operation: str = "upgrade",
) -> None:
    """Run Alembic against the disposable schema only."""

    if operation not in {"upgrade", "stamp"}:
        raise ValueError("Unsupported Alembic operation.")

    env = os.environ.copy()

    env["DATABASE_URL"] = url.render_as_string(hide_password=False)

    print(
        f"\nAlembic {operation} {revision}",
        flush=True,
    )

    subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            operation,
            revision,
        ],
        cwd=ROOT,
        env=env,
        check=True,
    )


def check_revision(engine, expected: str) -> None:
    with engine.connect() as connection:
        actual = connection.scalar(text("SELECT version_num FROM alembic_version"))

    if actual != expected:
        raise AssertionError(f"Expected revision {expected}; found {actual}")


def insert_legacy_records(engine) -> dict:
    """Create realistic records before revision 05 exists."""

    with engine.begin() as connection:
        user_id = connection.scalar(
            text("""
                INSERT INTO users (email, password_hash)
                VALUES (:email, 'migration-test')
                RETURNING id
                """),
            {"email": f"migration-{uuid4().hex}@example.com"},
        )

        exercise_id = connection.scalar(text("""
                INSERT INTO exercises (name)
                VALUES ('Migration Test Push-Up')
                RETURNING id
                """))

        baseline_id = connection.scalar(
            text("""
                INSERT INTO program_baselines
                    (user_id, program_slug, attempt_id, results)
                VALUES
                    (:user_id, 'bw', :attempt_id, '[]'::json)
                RETURNING id
                """),
            {
                "user_id": user_id,
                "attempt_id": str(uuid4()),
            },
        )

        instance_id = connection.scalar(
            text("""
                INSERT INTO program_instances
                    (user_id, program_slug, source_baseline_id)
                VALUES
                    (:user_id, 'bw', :baseline_id)
                RETURNING id
                """),
            {
                "user_id": user_id,
                "baseline_id": baseline_id,
            },
        )

        prescription_id = connection.scalar(
            text("""
                INSERT INTO workout_prescriptions
                    (
                        user_id,
                        program_instance_id,
                        program_slug,
                        program_week,
                        program_day,
                        status,
                        engine_version,
                        source_baseline_id
                    )
                VALUES
                    (
                        :user_id,
                        :instance_id,
                        'bw',
                        2,
                        1,
                        'planned',
                        'migration-test-v1',
                        :baseline_id
                    )
                RETURNING id
                """),
            {
                "user_id": user_id,
                "instance_id": instance_id,
                "baseline_id": baseline_id,
            },
        )

        set_id = connection.scalar(
            text("""
                INSERT INTO prescription_sets
                    (
                        workout_prescription_id,
                        exercise_id,
                        set_number,
                        target_reps,
                        load_basis,
                        is_optional
                    )
                VALUES
                    (
                        :prescription_id,
                        :exercise_id,
                        1,
                        16,
                        'bodyweight',
                        false
                    )
                RETURNING id
                """),
            {
                "prescription_id": prescription_id,
                "exercise_id": exercise_id,
            },
        )

        approval_id = connection.scalar(
            text("""
                INSERT INTO adaptation_approvals
                    (
                        user_id,
                        workout_prescription_id,
                        prescription_set_id,
                        adjustment_type,
                        previous_value,
                        approved_value,
                        proposal_engine_version
                    )
                VALUES
                    (
                        :user_id,
                        :prescription_id,
                        :set_id,
                        'reps',
                        15,
                        16,
                        'migration-test-v1'
                    )
                RETURNING id
                """),
            {
                "user_id": user_id,
                "prescription_id": prescription_id,
                "set_id": set_id,
            },
        )

        workout_id = connection.scalar(
            text("""
                INSERT INTO workout_records
                    (
                        user_id,
                        program_slug,
                        program_week,
                        program_day
                    )
                VALUES
                    (:user_id, 'bw', 1, 1)
                RETURNING id
                """),
            {"user_id": user_id},
        )

        entry_id = connection.scalar(
            text("""
                INSERT INTO performance_entries
                    (
                        workout_record_id,
                        exercise_id,
                        set_number,
                        reps,
                        status
                    )
                VALUES
                    (
                        :workout_id,
                        :exercise_id,
                        1,
                        15,
                        'completed'
                    )
                RETURNING id
                """),
            {
                "workout_id": workout_id,
                "exercise_id": exercise_id,
            },
        )

    return {
        "user_id": user_id,
        "exercise_id": exercise_id,
        "baseline_id": baseline_id,
        "instance_id": instance_id,
        "prescription_id": prescription_id,
        "set_id": set_id,
        "approval_id": approval_id,
        "workout_id": workout_id,
        "entry_id": entry_id,
    }


def snapshot_legacy_data(engine, ids: dict) -> dict:
    """Capture important persisted values for comparison."""

    checks = {
        "user": (
            "SELECT email FROM users WHERE id = :id",
            ids["user_id"],
        ),
        "baseline": (
            """
            SELECT program_slug, results
            FROM program_baselines WHERE id = :id
            """,
            ids["baseline_id"],
        ),
        "enrollment": (
            """
            SELECT user_id, program_slug, status,
                   source_baseline_id
            FROM program_instances WHERE id = :id
            """,
            ids["instance_id"],
        ),
        "prescription": (
            """
            SELECT user_id, program_instance_id,
                   program_slug, program_week,
                   program_day, status, engine_version
            FROM workout_prescriptions WHERE id = :id
            """,
            ids["prescription_id"],
        ),
        "prescription_set": (
            """
            SELECT workout_prescription_id,
                   exercise_id, set_number, target_reps,
                   load_basis, is_optional
            FROM prescription_sets WHERE id = :id
            """,
            ids["set_id"],
        ),
        "individual_approval": (
            """
            SELECT user_id, workout_prescription_id,
                   prescription_set_id, adjustment_type,
                   previous_value, approved_value,
                   proposal_engine_version
            FROM adaptation_approvals WHERE id = :id
            """,
            ids["approval_id"],
        ),
        "workout": (
            """
            SELECT user_id, program_slug,
                   program_week, program_day
            FROM workout_records WHERE id = :id
            """,
            ids["workout_id"],
        ),
        "performance": (
            """
            SELECT workout_record_id, exercise_id,
                   set_number, reps, status
            FROM performance_entries WHERE id = :id
            """,
            ids["entry_id"],
        ),
    }

    result = {}

    with engine.connect() as connection:
        for name, (query, row_id) in checks.items():
            row = connection.execute(
                text(query),
                {"id": row_id},
            ).first()

            if row is None:
                raise AssertionError(f"Legacy record missing: {name}")

            result[name] = tuple(row)

    return result


def verify_new_tables(engine) -> None:
    """Check revision 05 audit tables and constraints."""

    expected = {
        "program_adaptation_approvals",
        "program_adaptation_approval_items",
    }

    with engine.connect() as connection:
        inspector = inspect(connection)

        available = set(inspector.get_table_names())

        if not expected.issubset(available):
            raise AssertionError(f"Missing audit tables: {expected - available}")

        for table_name in expected:
            count = connection.scalar(text(f"SELECT COUNT(*) FROM {table_name}"))

            if count != 0:
                raise AssertionError(
                    f"Unexpected pre-existing audit data: " f"{table_name}"
                )

        approval_constraints = {
            item["name"]
            for item in inspector.get_unique_constraints("program_adaptation_approvals")
        }

        item_constraints = {
            item["name"]
            for item in inspector.get_unique_constraints(
                "program_adaptation_approval_items"
            )
        }

        if "uq_program_adaptation_request" not in approval_constraints:
            raise AssertionError("Missing approval idempotency constraint.")

        if "uq_program_adaptation_item_set" not in item_constraints:
            raise AssertionError("Missing selected-set uniqueness constraint.")


def bootstrap_revision_04(engine) -> None:
    """Build an isolated approximation of revision 04.

    Start with the current SQLAlchemy model schema,
    excluding the two tables introduced by revision 05.

    This is a targeted revision-05 verification fixture,
    not a reconstruction of the original production schema.
    """

    revision_05_tables = {
        "program_adaptation_approvals",
        "program_adaptation_approval_items",
    }

    legacy_tables = [
        table
        for table in Base.metadata.sorted_tables
        if table.name not in revision_05_tables
    ]

    Base.metadata.create_all(
        engine,
        tables=legacy_tables,
        checkfirst=False,
    )

    with engine.connect() as connection:
        inspector = inspect(connection)
        available = set(inspector.get_table_names())

        if not revision_05_tables.isdisjoint(available):
            raise AssertionError(
                "Revision 05 tables must not exist " "before the upgrade."
            )

        required = {
            "users",
            "program_baselines",
            "program_instances",
            "workout_prescriptions",
            "prescription_sets",
            "adaptation_approvals",
            "workout_records",
            "performance_entries",
        }

        missing = required - available

        if missing:
            raise AssertionError(f"Missing prerequisite tables: {missing}")


def main() -> int:
    url = database_url()

    schema = f"ascenda_migration_{uuid4().hex}"

    admin = create_engine(
        url,
        isolation_level="AUTOCOMMIT",
    )

    created = False
    engine = None

    try:
        with admin.connect() as connection:
            actual_database = connection.scalar(text("SELECT current_database()"))

            if actual_database != "ascenda_test":
                raise RuntimeError("Unexpected database.")

            connection.execute(text(f'CREATE SCHEMA "{schema}"'))

            created = True

        # Search only this schema, not public.
        # Alembic will create its version table and
        # application tables inside this schema.
        isolated_url = url.update_query_dict(
            {
                "options": f"-csearch_path={schema}",
            }
        )

        engine = create_engine(isolated_url)

        with engine.connect() as connection:
            active_schema = connection.scalar(text("SELECT current_schema()"))

            if active_schema != schema:
                raise RuntimeError("Schema isolation failed.")

        print(f"Using disposable schema: {schema}")

        # 1. Build an isolated approximation of revision 04.
        bootstrap_revision_04(engine)

        # The original baseline schema predates Alembic.
        # Stamp only the disposable schema.
        run_alembic(
            isolated_url,
            OLD_REVISION,
            operation="stamp",
        )

        check_revision(engine, OLD_REVISION)

        # 2. Existing records must predate revision 05.
        with engine.connect() as connection:
            available = set(inspect(connection).get_table_names())

            if (
                "program_adaptation_approvals" in available
                or "program_adaptation_approval_items" in available
            ):
                raise AssertionError("Revision 05 tables already exist at 04.")

        # 3. Seed realistic historical data.
        ids = insert_legacy_records(engine)

        before = snapshot_legacy_data(engine, ids)

        # 4. Perform the real incremental upgrade.
        run_alembic(isolated_url, NEW_REVISION)
        check_revision(engine, NEW_REVISION)

        # 5. Compare records before and after.
        after = snapshot_legacy_data(engine, ids)

        if before != after:
            differing = [name for name in before if before[name] != after[name]]

            raise AssertionError(
                "Migration modified legacy records: " + ", ".join(differing)
            )

        # 6. Verify new schema objects.
        verify_new_tables(engine)

        print("\nPASS: Revision 04 -> 05")
        print("PASS: Existing records preserved")
        print("PASS: New approval tables created")
        print("PASS: Idempotency constraints present")

        return 0

    except Exception as exc:
        print(f"\nMIGRATION VERIFICATION FAILED: {exc}")
        return 1

    finally:
        if engine is not None:
            engine.dispose()

        if created:
            with admin.connect() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))

        admin.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
