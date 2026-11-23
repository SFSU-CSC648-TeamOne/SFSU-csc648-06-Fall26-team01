# Unit tests for workout logging, history and the program summary

import pytest

from app.models import Exercise, TrainingProgram, WorkoutSession
from app.models.prescription import PrescriptionSet, WorkoutPrescription

URL = "/api/workout-records"
PROGRAM_DAY = {"program_slug": "bw", "program_week": 1, "program_day": 1}


# helper and fixtures

def entry(exercise_id, **extra):
    data = {"exercise_id": exercise_id, "set_number": 1,
            "reps": 10, "weight_kg": 20.0}
    data.update(extra)
    return data


def skipped(exercise_id, set_number=1):
    return {"exercise_id": exercise_id, "set_number": set_number,
            "status": "skipped"}


def log(client, account, entries, **extra):
    body = {"entries": entries}
    body.update(extra)
    return client.post(URL, json=body, headers=account["headers"])


@pytest.fixture()
def account(make_user):
    return make_user()


@pytest.fixture()
def ids(db_session):
    squat = Exercise(name="Squat")
    push_up = Exercise(name="Push-Up")
    row = Exercise(name="Row")
    db_session.add_all([squat, push_up, row])
    db_session.commit()
    return {"squat": squat.id, "push_up": push_up.id, "row": row.id}


@pytest.fixture()
def session_id(db_session):
    program = TrainingProgram(
        name="Starter", goal="strength", experience_level="beginner",
        length_weeks=4,
        sessions=[WorkoutSession(name="Day 1", position=1)],
    )
    db_session.add(program)
    db_session.commit()
    return program.sessions[0].id


@pytest.fixture()
def make_prescription(db_session):
    """Create a planned prescription set and return the set's id."""

    def _make(user_id, exercise_id, *, week=1, day=1, set_number=1,
              slug="bw", workout_session_id=None):
        prescription = WorkoutPrescription(
            user_id=user_id,
            workout_session_id=workout_session_id,
            program_slug=slug,
            program_week=week,
            program_day=day,
            status="planned",
            engine_version="baseline-v1",
        )
        prescription.sets.append(PrescriptionSet(
            exercise_id=exercise_id, set_number=set_number,
            target_reps=10, load_basis="bodyweight",
        ))
        db_session.add(prescription)
        db_session.commit()
        return prescription.sets[0].id

    return _make


# logging workouts

def test_log_workout_creates_record(client, account, ids):
    response = log(client, account, [entry(ids["squat"])])

    assert response.status_code == 201
    body = response.json()
    assert body["id"]
    assert body["entry_count"] == 1
    assert body["performed_at"]

    saved = body["entries"][0]
    assert saved["exercise_name"] == "Squat"
    assert saved["reps"] == 10
    assert saved["weight_kg"] == 20.0
    assert saved["status"] == "completed"
    assert saved["observation_type"] == "training"
    assert saved["is_user_modified"] is False


def test_log_workout_requires_login(client, ids):
    response = client.post(URL, json={"entries": [entry(ids["squat"])]})

    assert response.status_code == 401


def test_log_workout_keeps_supplied_fields(client, account, ids, session_id):
    response = log(
        client, account, [entry(ids["squat"])],
        performed_at="2026-03-01T09:30:00Z",
        workout_session_id=session_id,
        available_minutes=45, duration_minutes=40, notes="Felt strong",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["performed_at"].startswith("2026-03-01T09:30:00")
    assert body["workout_session_id"] == session_id
    assert body["session_name"] == "Day 1"
    assert body["available_minutes"] == 45
    assert body["duration_minutes"] == 40
    assert body["notes"] == "Felt strong"


def test_log_workout_with_program_day(client, account, ids):
    response = log(client, account, [entry(ids["squat"])], **PROGRAM_DAY)

    assert response.status_code == 201
    body = response.json()
    assert body["program_slug"] == "bw"
    assert body["program_week"] == 1
    assert body["program_day"] == 1


def test_log_workout_rejects_empty_entries(client, account):
    response = log(client, account, [])

    assert response.status_code == 422


@pytest.mark.parametrize(
    "bad_entry",
    [
        {"set_number": 0},
        {"reps": 1001},
        {"reps": -1},
        {"weight_kg": -1.0},
        {"status": "weird"},
        {"load_basis": "weird"},
    ],
)
def test_log_workout_rejects_out_of_range_values(
        client, account, ids, bad_entry):
    response = log(client, account, [entry(ids["squat"], **bad_entry)])

    assert response.status_code == 422


def test_log_workout_rejects_unknown_exercise(client, account):
    response = log(client, account, [entry(999999)])

    assert response.status_code == 422
    assert response.json()["code"] == "invalid"
    assert "999999" in response.json()["detail"]


def test_log_workout_rejects_unknown_workout_session(client, account, ids):
    response = log(client, account, [entry(ids["squat"])],
                   workout_session_id=999999)

    assert response.status_code == 422
    assert "workout_session_id" in response.json()["detail"]


def test_failed_log_saves_nothing(client, account, ids):
    log(client, account, [entry(ids["squat"]), entry(999999)])

    history = client.get(URL, headers=account["headers"]).json()
    assert history["total"] == 0


# ---------- skipped sets ----------

def test_skipped_set_without_values_is_saved(client, account, ids):
    response = log(client, account, [skipped(ids["squat"])])

    assert response.status_code == 201
    assert response.json()["entries"][0]["status"] == "skipped"


@pytest.mark.parametrize(
    "field,value",
    [("reps", 5), ("weight_kg", 20.0), ("duration_seconds", 30),
     ("distance_m", 100.0), ("assistance_kg", 10.0)],
)
def test_skipped_set_cannot_have_performance_values(
        client, account, ids, field, value):
    bad = skipped(ids["squat"])
    bad[field] = value

    response = log(client, account, [bad])

    assert response.status_code == 422


# alternative/substitutions

def test_substitution_is_saved_and_marked_user_modified(
        client, account, ids):
    response = log(client, account, [entry(
        ids["push_up"], status="substituted",
        substituted_for_exercise_id=ids["squat"])])

    assert response.status_code == 201
    saved = response.json()["entries"][0]
    assert saved["status"] == "substituted"
    assert saved["substituted_for_exercise_id"] == ids["squat"]
    assert saved["is_user_modified"] is True


def test_substitution_must_use_a_different_exercise(client, account, ids):
    response = log(client, account, [entry(
        ids["squat"], status="substituted",
        substituted_for_exercise_id=ids["squat"])])

    assert response.status_code == 422


def test_substituted_status_requires_original_exercise(
        client, account, ids):
    response = log(client, account, [entry(
        ids["squat"], status="substituted")])

    assert response.status_code == 422


def test_substituting_an_unknown_exercise_is_rejected(
        client, account, ids):
    response = log(client, account, [entry(
        ids["squat"], status="substituted",
        substituted_for_exercise_id=999999)])

    assert response.status_code == 422


# ---------- assisted loading ----------

def test_assisted_set_with_assistance_is_saved(client, account, ids):
    response = log(client, account, [entry(
        ids["push_up"], weight_kg=None, load_basis="assisted",
        assistance_kg=15.0)])

    assert response.status_code == 201
    saved = response.json()["entries"][0]
    assert saved["load_basis"] == "assisted"
    assert saved["assistance_kg"] == 15.0


def test_assistance_requires_assisted_load_basis(client, account, ids):
    response = log(client, account, [entry(
        ids["push_up"], load_basis="bodyweight", assistance_kg=15.0)])

    assert response.status_code == 422


def test_assisted_set_requires_assistance(client, account, ids):
    response = log(client, account, [entry(
        ids["push_up"], load_basis="assisted")])

    assert response.status_code == 422


def test_skipped_assisted_set_needs_no_assistance(client, account, ids):
    bad = skipped(ids["push_up"])
    bad["load_basis"] = "assisted"

    response = log(client, account, [bad])

    assert response.status_code == 201


# links for prescription

def test_prescription_link_is_saved(
        client, account, ids, make_prescription):
    set_id = make_prescription(account["user"]["id"], ids["squat"])

    response = log(client, account,
                   [entry(ids["squat"], prescription_set_id=set_id)],
                   **PROGRAM_DAY)

    assert response.status_code == 201
    assert response.json()["entries"][0]["prescription_set_id"] == set_id


def test_prescription_link_requires_program_day(
        client, account, ids, make_prescription):
    set_id = make_prescription(account["user"]["id"], ids["squat"])

    response = log(client, account,
                   [entry(ids["squat"], prescription_set_id=set_id)])

    assert response.status_code == 422
    assert "program" in response.json()["detail"]


def test_unknown_prescription_set_is_rejected(client, account, ids):
    response = log(client, account,
                   [entry(ids["squat"], prescription_set_id=999999)],
                   **PROGRAM_DAY)

    assert response.status_code == 422


def test_other_users_prescription_is_rejected(
        client, make_user, ids, make_prescription):
    owner = make_user(email="owner@example.com")
    intruder = make_user(email="intruder@example.com")
    set_id = make_prescription(owner["user"]["id"], ids["squat"])

    response = log(client, intruder,
                   [entry(ids["squat"], prescription_set_id=set_id)],
                   **PROGRAM_DAY)

    assert response.status_code == 422


def test_same_prescription_cannot_be_logged_twice(
        client, account, ids, make_prescription):
    set_id = make_prescription(account["user"]["id"], ids["squat"])

    response = log(client, account, [
        entry(ids["squat"], prescription_set_id=set_id),
        entry(ids["squat"], prescription_set_id=set_id),
    ], **PROGRAM_DAY)

    assert response.status_code == 422


@pytest.mark.parametrize(
    "program_day",
    [
        {"program_slug": "ldw", "program_week": 1, "program_day": 1},
        {"program_slug": "bw", "program_week": 2, "program_day": 1},
        {"program_slug": "bw", "program_week": 1, "program_day": 2},
    ],
)
def test_prescription_must_match_program_day(
        client, account, ids, make_prescription, program_day):
    set_id = make_prescription(account["user"]["id"], ids["squat"])

    response = log(client, account,
                   [entry(ids["squat"], prescription_set_id=set_id)],
                   **program_day)

    assert response.status_code == 422


def test_prescription_must_match_workout_session(
        client, account, ids, make_prescription, session_id):
    set_id = make_prescription(
        account["user"]["id"], ids["squat"], workout_session_id=session_id)

    response = log(client, account,
                   [entry(ids["squat"], prescription_set_id=set_id)],
                   **PROGRAM_DAY)

    assert response.status_code == 422


def test_set_number_must_match_prescription(
        client, account, ids, make_prescription):
    set_id = make_prescription(
        account["user"]["id"], ids["squat"], set_number=2)

    response = log(client, account,
                   [entry(ids["squat"], set_number=1,
                          prescription_set_id=set_id)],
                   **PROGRAM_DAY)

    assert response.status_code == 422


def test_exercise_must_match_prescription(
        client, account, ids, make_prescription):
    set_id = make_prescription(account["user"]["id"], ids["squat"])

    response = log(client, account,
                   [entry(ids["row"], prescription_set_id=set_id)],
                   **PROGRAM_DAY)

    assert response.status_code == 422


def test_substituted_exercise_may_fill_a_prescription(
        client, account, ids, make_prescription):
    set_id = make_prescription(account["user"]["id"], ids["squat"])

    response = log(client, account, [entry(
        ids["row"], status="substituted",
        substituted_for_exercise_id=ids["squat"],
        prescription_set_id=set_id)], **PROGRAM_DAY)

    assert response.status_code == 201


# workout history

def test_history_is_empty_for_new_user(client, account):
    response = client.get(URL, headers=account["headers"])

    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["items"] == []


def test_history_lists_newest_first_with_entry_counts(
        client, account, ids):
    older = log(client, account,
                [entry(ids["squat"], set_number=1),
                 entry(ids["squat"], set_number=2)],
                performed_at="2026-01-01T10:00:00Z").json()
    newer = log(client, account, [entry(ids["squat"])],
                performed_at="2026-02-01T10:00:00Z").json()

    response = client.get(URL, headers=account["headers"])

    body = response.json()
    assert body["total"] == 2
    assert [i["id"] for i in body["items"]] == [newer["id"], older["id"]]
    assert [i["entry_count"] for i in body["items"]] == [1, 2]


def test_history_pagination(client, account, ids):
    for day in (1, 2, 3):
        log(client, account, [entry(ids["squat"])],
            performed_at=f"2026-01-0{day}T10:00:00Z")

    response = client.get(
        URL, params={"limit": 2, "offset": 2}, headers=account["headers"])

    body = response.json()
    assert body["total"] == 3
    assert body["limit"] == 2
    assert body["offset"] == 2
    assert len(body["items"]) == 1


@pytest.mark.parametrize(
    "params", [{"limit": 0}, {"limit": 101}, {"offset": -1}])
def test_history_rejects_invalid_paging(client, account, params):
    response = client.get(URL, params=params, headers=account["headers"])

    assert response.status_code == 422


def test_history_requires_login(client):
    assert client.get(URL).status_code == 401


def test_history_only_shows_own_records(client, make_user, ids):
    first = make_user(email="first@example.com")
    second = make_user(email="second@example.com")
    log(client, first, [entry(ids["squat"])])

    response = client.get(URL, headers=second["headers"])

    assert response.json()["total"] == 0


# one record

def test_get_record_returns_entries_in_order(client, account, ids):
    created = log(client, account, [
        entry(ids["squat"], set_number=1),
        entry(ids["push_up"], set_number=1),
    ]).json()

    response = client.get(f"{URL}/{created['id']}", headers=account["headers"])

    assert response.status_code == 200
    names = [e["exercise_name"] for e in response.json()["entries"]]
    assert names == ["Squat", "Push-Up"]


def test_get_record_not_found(client, account):
    response = client.get(f"{URL}/999999", headers=account["headers"])

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_get_record_of_another_user_is_not_found(client, make_user, ids):
    owner = make_user(email="owner@example.com")
    other = make_user(email="other@example.com")
    created = log(client, owner, [entry(ids["squat"])]).json()

    response = client.get(f"{URL}/{created['id']}", headers=other["headers"])

    assert response.status_code == 404


def test_get_record_requires_login(client):
    assert client.get(f"{URL}/1").status_code == 401


# ---------- program summary ----------

def test_program_summary_is_empty_without_records(client, account):
    response = client.get(
        f"{URL}/program-summary", params={"program": "bw"},
        headers=account["headers"])

    assert response.status_code == 200
    body = response.json()
    assert body["program"] == "bw"
    assert body["days_completed"] == 0
    assert body["days_total"] == 20
    assert body["totals"] == {
        "sets": 0, "reps": 0, "volume_kg": 0.0, "seconds": 0}
    assert body["weeks"] == []
    assert body["exercises"] == []


def test_program_summary_totals(client, account, ids):
    squat, push_up = ids["squat"], ids["push_up"]

    # Week 1, day 1: 2 completed squat sets, 1 skipped, 1 push-up set.
    assert log(client, account, [
        entry(squat, set_number=1, reps=10, weight_kg=20.0),
        entry(squat, set_number=2, reps=8, weight_kg=20.0),
        skipped(squat, 3),
        {"exercise_id": push_up, "set_number": 1, "reps": 15},
    ], program_slug="bw", program_week=1, program_day=1).status_code == 201

    # Week 1, day 2: one completed squat set.
    assert log(client, account, [entry(squat, reps=5, weight_kg=10.0)],
               program_slug="bw", program_week=1,
               program_day=2).status_code == 201

    # Week 2, day 1: only a skipped set, so the day does not count.
    assert log(client, account, [skipped(squat)],
               program_slug="bw", program_week=2,
               program_day=1).status_code == 201

    # Another program is ignored.
    assert log(client, account, [entry(squat)],
               program_slug="ldw", program_week=1,
               program_day=1).status_code == 201

    response = client.get(
        f"{URL}/program-summary", params={"program": "bw"},
        headers=account["headers"])

    body = response.json()
    assert body["days_completed"] == 2
    assert body["totals"] == {
        "sets": 4, "reps": 38, "volume_kg": 410.0, "seconds": 0}

    assert len(body["weeks"]) == 1
    week = body["weeks"][0]
    assert week["week"] == 1
    assert week["days_completed"] == 2
    assert week["sets"] == 4

    squat_totals, push_up_totals = body["exercises"]
    assert squat_totals["exercise_id"] == squat
    assert squat_totals["name"] == "Squat"
    assert squat_totals["sets"] == 3
    assert squat_totals["reps"] == 23
    assert squat_totals["volume_kg"] == 410.0
    assert push_up_totals["exercise_id"] == push_up
    assert push_up_totals["reps"] == 15
    assert push_up_totals["volume_kg"] == 0.0


def test_program_summary_uses_latest_attempt(client, account, ids):
    squat = ids["squat"]
    log(client, account, [entry(squat, reps=10, weight_kg=20.0)],
        performed_at="2026-01-01T10:00:00Z", **PROGRAM_DAY)
    log(client, account, [entry(squat, reps=12, weight_kg=20.0)],
        performed_at="2026-01-02T10:00:00Z", **PROGRAM_DAY)

    response = client.get(
        f"{URL}/program-summary", params={"program": "bw"},
        headers=account["headers"])

    body = response.json()
    assert body["days_completed"] == 1
    assert body["totals"]["sets"] == 1
    assert body["totals"]["reps"] == 12
    assert body["totals"]["volume_kg"] == 240.0


def test_program_summary_adds_timed_sets(client, account, ids):
    log(client, account,
        [{"exercise_id": ids["push_up"], "set_number": 1,
          "duration_seconds": 45}],
        **PROGRAM_DAY)

    response = client.get(
        f"{URL}/program-summary", params={"program": "bw"},
        headers=account["headers"])

    assert response.json()["totals"]["seconds"] == 45


def test_program_summary_requires_program_parameter(client, account):
    response = client.get(
        f"{URL}/program-summary", headers=account["headers"])

    assert response.status_code == 422


def test_program_summary_rejects_long_program_name(client, account):
    response = client.get(
        f"{URL}/program-summary", params={"program": "x" * 21},
        headers=account["headers"])

    assert response.status_code == 422


def test_program_summary_requires_login(client):
    response = client.get(f"{URL}/program-summary", params={"program": "bw"})

    assert response.status_code == 401