
"""Step 8: Ascenda adaptive backend verification.

Run from app/backend:

    python scripts/verify_adaptive_backend.py

Runs SQLite regression tests, isolated PostgreSQL tests,
migration-version inspection, and FastAPI registration checks.

Never applies migrations or resets a database.
"""

import os
import subprocess
import sys
from getpass import getpass
from pathlib import Path

from sqlalchemy import URL, create_engine, text


BACKEND_ROOT = Path(__file__).resolve().parents[1]

SQLITE_TESTS = [
    # Existing adaptive-engine regressions
    "test_progress_analysis.py",
    "test_adaptive_engine.py",
    "test_progression_rules.py",
    "test_prescription_adaptation.py",
    "test_approve_adaptation.py",
    "test_adaptations_approval_api.py",
    "test_adaptation_workflow.py",
    "test_program_adaptation.py",
    "test_adaptations_api.py",

    # Enrollment and program-wide adaptation
    "test_program_enrollment.py",
    "test_program_schedule.py",
    "test_program_template_resolver.py",
    "test_program_adaptation_enrollment.py",
    "test_program_adaptations_api.py",
    "test_program_adaptation_approval_api.py",
]

POSTGRES_TESTS = [
    "test_program_enrollment_postgres.py",
    "test_program_adaptation_approval_models.py",
    "test_apply_program_adaptations.py",
    "test_apply_program_adaptations_concurrency.py",
    "test_workout_adaptation_concurrency.py"
]

EXPECTED_REVISION = "05"

PREVIEW_PATH = (
    "/api/adaptations/program-instances/"
    "{program_instance_id}/preview"
)

APPROVAL_PATH = (
    "/api/adaptations/program-instances/"
    "{program_instance_id}/approve"
)


def local_database_url() -> URL:
    """Construct the dedicated local test connection."""

    return URL.create(
        "postgresql+psycopg",
        username="devuser",
        password=getpass(
            "Local PostgreSQL password: "
        ),
        host="127.0.0.1",
        port=5433,
        database="ascenda_test",
    )


def verify_database(url: URL) -> None:
    """Fail before tests if this is not the test DB."""

    if (
        url.get_backend_name() != "postgresql"
        or url.get_driver_name() != "psycopg"
        or url.host != "127.0.0.1"
        or url.port != 5433
        or url.database != "ascenda_test"
        or url.username != "devuser"
    ):
        raise RuntimeError(
            "Refusing to use a non-test database."
        )

    engine = create_engine(url)

    try:
        with engine.connect() as connection:
            database = connection.scalar(
                text("SELECT current_database()")
            )

            user = connection.scalar(
                text("SELECT current_user")
            )

            if (
                database != "ascenda_test"
                or user != "devuser"
            ):
                raise RuntimeError(
                    "Database identity verification failed."
                )

            revision = connection.scalar(
                text(
                    "SELECT version_num "
                    "FROM public.alembic_version"
                )
            )

            if revision != EXPECTED_REVISION:
                raise RuntimeError(
                    f"Expected Alembic revision "
                    f"{EXPECTED_REVISION}, found {revision}."
                )

            print(
                f"Database verified: "
                f"{database}, revision {revision}"
            )

    finally:
        engine.dispose()


def test_paths(filenames: list[str]) -> list[str]:
    """Require every expected test file to exist."""

    missing = [
        name
        for name in filenames
        if not (
            BACKEND_ROOT / "tests" / name
        ).is_file()
    ]

    if missing:
        raise RuntimeError(
            "Expected test files are missing:\n"
            + "\n".join(missing)
        )

    return [
        str(Path("tests") / name)
        for name in filenames
    ]


def run_command(
    label: str,
    arguments: list[str],
    environment: dict[str, str],
) -> bool:
    print(f"\n{'=' * 60}")
    print(label)
    print(f"{'=' * 60}", flush=True)

    result = subprocess.run(
        arguments,
        cwd=BACKEND_ROOT,
        env=environment,
        check=False,
    )

    passed = result.returncode == 0

    print(
        f"\n{label}: "
        f"{'PASSED' if passed else 'FAILED'}",
        flush=True,
    )

    return passed


def verify_routes(environment: dict[str, str]) -> bool:
    """Import FastAPI and inspect registered endpoints."""

    code = f"""
from app.main import app

routes = {{
    (route.path, method)
    for route in app.routes
    for method in getattr(route, "methods", set())
}}

required = {{
    ({PREVIEW_PATH!r}, "POST"),
    ({APPROVAL_PATH!r}, "POST"),
}}

missing = required - routes

if missing:
    raise AssertionError(
        f"Missing API endpoints: {{sorted(missing)}}"
    )

print("Both program adaptation endpoints registered.")
"""

    return run_command(
        "FastAPI startup and route registration",
        [sys.executable, "-c", code],
        environment,
    )


def main() -> int:
    os.chdir(BACKEND_ROOT)

    try:
        url = local_database_url()
        verify_database(url)

        sqlite_paths = test_paths(SQLITE_TESTS)
        postgres_paths = test_paths(POSTGRES_TESTS)

    except Exception as exc:
        print(f"\nPreflight failed: {exc}")
        return 1

    # Override application configuration for child
    # processes, preventing accidental Supabase access.
    environment = os.environ.copy()

    connection_url = url.render_as_string(
        hide_password=False
    )

    environment["DATABASE_URL"] = connection_url
    environment["ASCENDA_TEST_DATABASE_URL"] = (
        connection_url
    )

    results = {}

    results["SQLite regressions"] = run_command(
        "SQLite regressions",
        [
            sys.executable,
            "-m",
            "pytest",
            *sqlite_paths,
            "-q",
        ],
        environment,
    )

    results["PostgreSQL integration"] = run_command(
        "PostgreSQL integration",
        [
            sys.executable,
            "-m",
            "pytest",
            *postgres_paths,
            "-q",
        ],
        environment,
    )

    results["FastAPI registration"] = verify_routes(
        environment
    )

    print(f"\n{'=' * 60}")
    print("ASCENDA BACKEND VERIFICATION SUMMARY")
    print(f"{'=' * 60}")

    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"{name}: {status}")

    if all(results.values()):
        print(
            "\nAll selected backend verification "
            "checks passed."
        )
        return 0

    print(
        "\nOne or more verification checks failed. "
        "Review the test output above."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
