"""Isolated PostgreSQL integration tests for program enrollment.

Run only against the dedicated local ascenda_test database.
All test data is rolled back after each test.
"""

import os
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import (
    create_engine,
    event,
    func,
    inspect,
    select,
)
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

import app.models

from app.models.catalog import Exercise
from app.models.program_baseline import ProgramBaseline
from app.models.program_instance import ProgramInstance
from app.models.program_phase import ProgramPhase
from app.models.prescription import (
    PrescriptionSet,
    WorkoutPrescription,
)
from app.models.users import User

from app.services.program_definitions import (
    get_program_definition,
    required_exercise_slugs,
)
from app.services.program_template_resolver import (
    ExerciseTarget,
    resolve_program_template,
)
from app.services.program_enrollment import (
    create_program_enrollment,
)

REQUIRED_TABLES = {
    "users",
    "exercises",
    "program_baselines",
    "program_instances",
    "workout_prescriptions",
    "prescription_sets",
    "program_phases",
}


@pytest.fixture
def db():
    raw_url = os.environ.get("ASCENDA_TEST_DATABASE_URL")

    if not raw_url:
        pytest.fail("ASCENDA_TEST_DATABASE_URL is required.")

    url = make_url(raw_url)

    if (
        url.host != "127.0.0.1"
        or url.port != 5433
        or url.database != "ascenda_test"
        or url.username != "devuser"
        or url.get_backend_name() != "postgresql"
        or url.get_driver_name() != "psycopg"
    ):
        pytest.fail(
            "Refusing to run outside the dedicated " "local PostgreSQL test database."
        )

    engine = create_engine(url)

    try:
        with engine.connect() as connection:
            if connection.dialect.name != "postgresql":
                pytest.fail("PostgreSQL is required.")

            actual_database = connection.exec_driver_sql(
                "SELECT current_database()"
            ).scalar_one()

            if actual_database != "ascenda_test":
                pytest.fail("Wrong database.")

            available = set(inspect(connection).get_table_names())

            missing = REQUIRED_TABLES - available

            if missing:
                pytest.fail(f"Missing tables: {sorted(missing)}")

            # End the read-only inspection-transaction.
            # SQLAlchemy automatically began it on the first query.
            connection.rollback()

            # Begin outer transaction for test isolation.
            # Service commits use nested savepoints.
            outer = connection.begin()

            try:
                with Session(
                    bind=connection,
                    join_transaction_mode="create_savepoint",
                ) as session:
                    yield session
            finally:
                if outer.is_active:
                    outer.rollback()
    finally:
        engine.dispose()


@pytest.fixture(params=["bw", "ldw"])
def data(db, request):
    slug = request.param
    program = get_program_definition(slug)

    assert program is not None

    user = User(
        email=f"integration-{uuid4().hex}@example.com",
        password_hash="integration-test",
    )

    db.add(user)
    db.flush()

    baseline = ProgramBaseline(
        user_id=user.id,
        program_slug=slug,
        attempt_id=str(uuid4()),
        results=[],
    )

    db.add(baseline)

    mappings = {}

    for exercise_slug in sorted(required_exercise_slugs(program)):
        exercise = Exercise(name=f"Integration {exercise_slug}")
        db.add(exercise)
        db.flush()
        mappings[exercise_slug] = exercise.id

    db.commit()

    phases = {(week, day): "training" for week in range(1, 5) for day in range(1, 6)}

    phases[(2, 1)] = "deload"
    phases[(4, 5)] = "assessment"

    targets = {}

    for week in range(1, 5):
        for day, template in enumerate(program.days, start=1):
            for item in template.exercises:
                key = (week, day, item.slug)

                if item.slug == "plank":
                    targets[key] = ExerciseTarget(
                        load_basis="bodyweight",
                        target_duration_seconds=30,
                    )
                elif slug == "ldw":
                    targets[key] = ExerciseTarget(
                        load_basis="external",
                        target_reps=8,
                        target_weight_kg=Decimal("40.00"),
                    )
                else:
                    targets[key] = ExerciseTarget(
                        load_basis="bodyweight",
                        target_reps=10,
                    )

    return {
        "slug": slug,
        "user_id": user.id,
        "baseline_id": baseline.id,
        "mappings": mappings,
        "phases": phases,
        "targets": targets,
    }


def create_schedule(db, data):
    return resolve_program_template(
        db,
        program_slug=data["slug"],
        exercise_ids=data["mappings"],
        phases=data["phases"],
        targets=data["targets"],
    )


def enroll(db, data, workouts):
    return create_program_enrollment(
        db,
        user_id=data["user_id"],
        program_slug=data["slug"],
        source_baseline_id=data["baseline_id"],
        workouts=workouts,
    )


def count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def test_complete_enrollment_persists(db, data):
    workouts = create_schedule(db, data)
    instance = enroll(db, data, workouts)

    db.expire_all()

    stored = db.get(ProgramInstance, instance.id)

    assert stored is not None
    assert stored.user_id == data["user_id"]
    assert stored.program_slug == data["slug"]
    assert stored.source_baseline_id == data["baseline_id"]

    prescriptions = db.scalars(
        select(WorkoutPrescription)
        .where(WorkoutPrescription.program_instance_id == instance.id)
        .order_by(
            WorkoutPrescription.program_week,
            WorkoutPrescription.program_day,
        )
    ).all()

    assert len(prescriptions) == 20
    assert all(p.status == "planned" for p in prescriptions)

    phases = db.execute(
        select(
            WorkoutPrescription.program_week,
            WorkoutPrescription.program_day,
            ProgramPhase.phase_type,
        )
        .join(
            ProgramPhase,
            ProgramPhase.workout_prescription_id == WorkoutPrescription.id,
        )
        .where(WorkoutPrescription.program_instance_id == instance.id)
    ).all()

    phase_lookup = {(week, day): phase for week, day, phase in phases}

    assert len(phase_lookup) == 20
    assert phase_lookup[(2, 1)] == "deload"
    assert phase_lookup[(4, 5)] == "assessment"
    assert phase_lookup[(1, 1)] == "training"

    actual_sets = sum(len(p.sets) for p in prescriptions)

    expected_sets = sum(len(workout.sets) for workout in workouts)

    assert actual_sets == expected_sets

    if data["slug"] == "ldw":
        assert all(
            item.target_weight_kg == Decimal("40.00")
            for prescription in prescriptions
            for item in prescription.sets
        )


def test_repeated_enrollment_is_isolated(db, data):
    workouts = create_schedule(db, data)

    first = enroll(db, data, workouts)
    first_id = first.id

    second = enroll(db, data, workouts)
    second_id = second.id

    assert first_id != second_id

    first_prescriptions = set(
        db.scalars(
            select(WorkoutPrescription.id).where(
                WorkoutPrescription.program_instance_id == first_id
            )
        )
    )

    second_prescriptions = set(
        db.scalars(
            select(WorkoutPrescription.id).where(
                WorkoutPrescription.program_instance_id == second_id
            )
        )
    )

    assert len(first_prescriptions) == 20
    assert len(second_prescriptions) == 20
    assert first_prescriptions.isdisjoint(second_prescriptions)


def test_database_failure_rolls_back_plan(db, data):
    workouts = create_schedule(db, data)

    before = {
        model: count(db, model)
        for model in (
            ProgramInstance,
            WorkoutPrescription,
            PrescriptionSet,
            ProgramPhase,
        )
    }

    def fail_phase(mapper, connection, target):
        raise RuntimeError("Simulated PostgreSQL insertion failure")

    event.listen(
        ProgramPhase,
        "before_insert",
        fail_phase,
    )

    try:
        with pytest.raises(
            RuntimeError,
            match="Simulated PostgreSQL insertion failure",
        ):
            enroll(db, data, workouts)
    finally:
        event.remove(
            ProgramPhase,
            "before_insert",
            fail_phase,
        )

    after = {model: count(db, model) for model in before}

    assert after == before
