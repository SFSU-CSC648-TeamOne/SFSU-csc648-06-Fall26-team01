# Unit tests for the exercise, program and workout-session catalog

import pytest

from app.models import (
    Equipment,
    Exercise,
    ExerciseModel,
    ExerciseMuscle,
    MuscleGroup,
    SessionExercise,
    TrainingProgram,
    WorkoutSession,
)

@pytest.fixture()
def catalog(db_session):
    """Seed a small catalog and return the ids the tests need."""
    barbell = Equipment(name="Barbell")
    dumbbell = Equipment(name="Dumbbell")
    chest = MuscleGroup(name="Chest")
    quads = MuscleGroup(name="Quads")
    triceps = MuscleGroup(name="Triceps")

    push_up = Exercise(
        name="Push-Up", category="Chest", difficulty="beginner",
        default_role="core", default_minutes=6,
    )
    squat = Exercise(
        name="Barbell Back Squat", difficulty="intermediate",
        default_role="accessory", default_minutes=8,
    )
    bench = Exercise(
        name="Dumbbell Bench Press", difficulty="intermediate",
        default_role="core", default_minutes=10,
    )

    push_up.muscle_links.append(ExerciseMuscle(muscle=chest, is_primary=True))
    squat.muscle_links.append(ExerciseMuscle(muscle=quads, is_primary=True))
    squat.equipment.append(barbell)
    bench.muscle_links.append(ExerciseMuscle(muscle=chest, is_primary=True))
    bench.muscle_links.append(ExerciseMuscle(muscle=triceps, is_primary=False))
    bench.equipment.append(dumbbell)

    starter = TrainingProgram(
        name="Strength Starter", goal="strength", experience_level="beginner",
        length_weeks=4, description="Start here.",
        sessions=[
            WorkoutSession(
                name="Day 1", position=1, guidance="Warm up first.",
                items=[
                    SessionExercise(exercise=push_up, position=1, role="core",
                                    sets=3, reps=10, minutes=None),
                    SessionExercise(exercise=squat, position=2, role="accessory",
                                    sets=3, reps=8, minutes=10),
                ],
            )
        ],
    )
    builder = TrainingProgram(
        name="Muscle Builder", goal="hypertrophy",
        experience_level="intermediate", length_weeks=8, description=None,
        sessions=[
            WorkoutSession(
                name="Chest Day", position=1, guidance=None,
                items=[
                    SessionExercise(exercise=bench, position=1, role="core",
                                    sets=4, reps=8, minutes=20),
                ],
            )
        ],
    )

    db_session.add_all([barbell, dumbbell, chest, quads, triceps,
                        push_up, squat, bench, starter, builder])
    db_session.flush()
    db_session.add(ExerciseModel(
        exercise_id=push_up.id,
        model_url="/about/Push_up.glb",
        video_url="/about/demo.mp4",
    ))
    db_session.commit()

    return {
        "push_up_id": push_up.id,
        "squat_id": squat.id,
        "bench_id": bench.id,
        "day1_id": starter.sessions[0].id,
        "chest_day_id": builder.sessions[0].id,
    }

def names(response):
    return [item["name"] for item in response.json()["items"]]

# exercises: list, search, filters

def test_list_exercises_returns_page_sorted_by_name(client, catalog):
    response = client.get("/api/exercises")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["limit"] == 20
    assert body["offset"] == 0
    assert names(response) == [
        "Barbell Back Squat", "Dumbbell Bench Press", "Push-Up",
    ]

def test_search_ignores_hyphens_and_matches_every_word(client, catalog):
    response = client.get("/api/exercises", params={"q": "push up"})

    assert names(response) == ["Push-Up"]

def test_search_is_case_insensitive(client, catalog):
    response = client.get("/api/exercises", params={"q": "BENCH"})

    assert names(response) == ["Dumbbell Bench Press"]

def test_search_with_no_match_returns_empty_page(client, catalog):
    response = client.get("/api/exercises", params={"q": "deadlift"})

    assert response.json()["total"] == 0
    assert response.json()["items"] == []

def test_search_treats_percent_as_plain_text(client, catalog):
    response = client.get("/api/exercises", params={"q": "%"})

    assert response.json()["total"] == 0

def test_filter_by_muscle_is_case_insensitive(client, catalog):
    response = client.get("/api/exercises", params={"muscle": "CHEST"})

    assert names(response) == ["Dumbbell Bench Press", "Push-Up"]

def test_filter_by_equipment(client, catalog):
    response = client.get("/api/exercises", params={"equipment": "barbell"})

    assert names(response) == ["Barbell Back Squat"]


def test_filter_by_difficulty(client, catalog):
    response = client.get("/api/exercises", params={"difficulty": "beginner"})

    assert names(response) == ["Push-Up"]


def test_invalid_difficulty_is_rejected(client, catalog):
    response = client.get("/api/exercises", params={"difficulty": "expert"})

    assert response.status_code == 422


def test_filters_combine(client, catalog):
    response = client.get(
        "/api/exercises",
        params={"muscle": "chest", "difficulty": "intermediate"},
    )

    assert names(response) == ["Dumbbell Bench Press"]


def test_pagination_offset_and_limit(client, catalog):
    response = client.get("/api/exercises", params={"limit": 1, "offset": 1})

    body = response.json()
    assert body["total"] == 3
    assert body["limit"] == 1
    assert body["offset"] == 1
    assert names(response) == ["Dumbbell Bench Press"]


@pytest.mark.parametrize(
    "params",
    [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"q": "x" * 101}],
)
def test_invalid_query_parameters_are_rejected(client, catalog, params):
    response = client.get("/api/exercises", params=params)

    assert response.status_code == 422


# ---------- exercises: detail, equipment, muscle groups ----------

def test_exercise_detail_lists_muscles_and_equipment(client, catalog):
    response = client.get(f"/api/exercises/{catalog['bench_id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Dumbbell Bench Press"
    assert body["primary_muscles"] == ["Chest"]
    assert body["secondary_muscles"] == ["Triceps"]
    assert body["equipment"] == ["Dumbbell"]
    assert body["source"] == "manual"


def test_exercise_detail_not_found(client, catalog):
    response = client.get("/api/exercises/999999")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_list_equipment_sorted_by_name(client, catalog):
    response = client.get("/api/equipment")

    assert response.status_code == 200
    assert [e["name"] for e in response.json()] == ["Barbell", "Dumbbell"]


def test_list_muscle_groups_sorted_by_name(client, catalog):
    response = client.get("/api/muscle-groups")

    assert response.status_code == 200
    assert [m["name"] for m in response.json()] == ["Chest", "Quads", "Triceps"]


def test_equipment_and_muscle_groups_empty_when_no_data(client):
    assert client.get("/api/equipment").json() == []
    assert client.get("/api/muscle-groups").json() == []


# ---------- programs ----------

def test_list_programs_sorted_by_name(client, catalog):
    response = client.get("/api/programs")

    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert names(response) == ["Muscle Builder", "Strength Starter"]


def test_filter_programs_by_goal_ignores_case(client, catalog):
    response = client.get("/api/programs", params={"goal": "STRENGTH"})

    assert names(response) == ["Strength Starter"]


def test_filter_programs_by_max_weeks(client, catalog):
    response = client.get("/api/programs", params={"max_weeks": 4})

    assert names(response) == ["Strength Starter"]


def test_programs_pagination(client, catalog):
    response = client.get("/api/programs", params={"limit": 1, "offset": 1})

    assert response.json()["total"] == 2
    assert names(response) == ["Strength Starter"]


def test_programs_reject_invalid_max_weeks(client, catalog):
    response = client.get("/api/programs", params={"max_weeks": 0})

    assert response.status_code == 422


# workout sessions

def test_list_workout_sessions_summaries(client, catalog):
    response = client.get("/api/workout-sessions")

    assert response.status_code == 200
    assert response.json()["total"] == 2
    # Ordered by program name, so Muscle Builder comes first.
    assert names(response) == ["Chest Day", "Day 1"]

    day1 = response.json()["items"][1]
    assert day1["program_name"] == "Strength Starter"
    assert day1["goal"] == "strength"
    assert day1["difficulty"] == "beginner"
    assert day1["exercise_count"] == 2
    assert day1["total_minutes"] == 16  # 6 (exercise default) + 10 (override)
    assert day1["muscle_groups"] == ["Chest", "Quads"]


def test_filter_workout_sessions_by_muscle(client, catalog):
    response = client.get("/api/workout-sessions", params={"muscle": "quads"})

    assert names(response) == ["Day 1"]


def test_filter_workout_sessions_by_difficulty(client, catalog):
    response = client.get(
        "/api/workout-sessions", params={"difficulty": "intermediate"})

    assert names(response) == ["Chest Day"]


def test_filter_workout_sessions_by_max_minutes(client, catalog):
    response = client.get("/api/workout-sessions", params={"max_minutes": 16})

    assert response.json()["total"] == 1
    assert names(response) == ["Day 1"]


def test_workout_sessions_pagination(client, catalog):
    response = client.get(
        "/api/workout-sessions", params={"limit": 1, "offset": 1})

    assert response.json()["total"] == 2
    assert names(response) == ["Day 1"]


def test_workout_sessions_reject_invalid_max_minutes(client, catalog):
    response = client.get("/api/workout-sessions", params={"max_minutes": 0})

    assert response.status_code == 422


def test_workout_session_detail(client, catalog):
    response = client.get(f"/api/workout-sessions/{catalog['day1_id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Day 1"
    assert body["guidance"] == "Warm up first."
    assert [e["name"] for e in body["exercises"]] == [
        "Push-Up", "Barbell Back Squat",
    ]

    push_up, squat = body["exercises"]
    assert push_up["role"] == "core"
    assert push_up["droppable"] is False
    assert push_up["minutes"] == 6          # falls back to the default
    assert push_up["model_url"] == "/about/Push_up.glb"
    assert push_up["video_url"] == "/about/demo.mp4"
    assert push_up["primary_muscles"] == ["Chest"]

    assert squat["role"] == "accessory"
    assert squat["droppable"] is True
    assert squat["minutes"] == 10           # the session's override
    assert squat["model_url"] is None
    assert squat["equipment"] == ["Barbell"]


def test_workout_session_detail_not_found(client, catalog):
    response = client.get("/api/workout-sessions/999999")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"