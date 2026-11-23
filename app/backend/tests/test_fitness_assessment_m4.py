
    
  
"""P1-03 fitness baseline tests for Ascenda.

Run from app/backend: python -m unittest discover -s tests -p 'test_fitness_assessment_m4.py' -v
This uses a disposable, in-memory SQLite database. Never uses Supabase.
"""
import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

# IMPORTANT: Configure before importing app.db.session/app.main.
os.environ["DATABASE_URL"] = "sqlite:///./ascenda_m4_test_bootstrap.db"
os.environ["JWT_SECRET"] = "ascenda-m4-test-only-secret-0123456789"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.models  # register all ORM mappings
from app.api.routes.program_baselines import (
    BaselineIn,
    create_baseline,
    get_tests,
)
from app.core.errors import ValidationFailed
from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import User
from app.models.program_baseline import ProgramBaseline

BW = [
    {"exercise_id": "push-up", "value": 20, "load_kg": None},
    {"exercise_id": "bodyweight-squat", "value": 30, "load_kg": None},
    {"exercise_id": "plank", "value": 45, "load_kg": None},
]
LDW = [
    {"exercise_id": "barbell-bench-press", "value": 8, "load_kg": 40.0},
    {"exercise_id": "barbell-back-squat", "value": 10, "load_kg": 60.0},
    {"exercise_id": "romanian-deadlift", "value": 10, "load_kg": 50.0},
]


def payload(program="bw", results=None):
    return {"program_slug": program, "results": results if results is not None else BW}


class BaselineUnitTests(unittest.TestCase):
    """White-box tests of the route's validation and catalog units."""

    def setUp(self):
        self.user = SimpleNamespace(id=1)
        self.db = Mock(spec=Session)

    def test_catalog_definitions_match_expected_programs(self):
        self.assertEqual([x["id"] for x in get_tests("bw")],
                         ["push-up", "bodyweight-squat", "plank"])
        self.assertTrue(all(x["weighted"] for x in get_tests("ldw")))

    def test_missing_required_exercise_rejected_without_write(self):
        with self.assertRaises(ValidationFailed):
            create_baseline(BaselineIn.model_validate(payload(results=BW[:2])), self.user, self.db)
        self.db.add.assert_not_called()

    def test_duplicate_exercise_rejected_without_write(self):
        results = BW[:2] + [BW[0]]
        with self.assertRaises(ValidationFailed):
            create_baseline(BaselineIn.model_validate(payload(results=results)), self.user, self.db)
        self.db.add.assert_not_called()

    def test_unknown_exercise_rejected_without_write(self):
        results = BW[:2] + [{"exercise_id": "unknown", "value": 10}]
        with self.assertRaises(ValidationFailed):
            create_baseline(BaselineIn.model_validate(payload(results=results)), self.user, self.db)
        self.db.add.assert_not_called()

    def test_weight_required_for_loaded_assessment(self):
        results = [dict(x) for x in LDW]
        results[0]["load_kg"] = None
        with self.assertRaises(ValidationFailed):
            create_baseline(BaselineIn.model_validate(payload("ldw", results)), self.user, self.db)
        self.db.add.assert_not_called()

    def test_bodyweight_assessment_rejects_external_load(self):
        results = [dict(x) for x in BW]
        results[0]["load_kg"] = 5
        with self.assertRaises(ValidationFailed):
            create_baseline(BaselineIn.model_validate(payload(results=results)), self.user, self.db)
        self.db.add.assert_not_called()

    def test_schema_accepts_value_boundaries(self):
        for value in (0, 10000):
            results = [dict(x, value=value) for x in BW]
            obj = BaselineIn.model_validate(payload(results=results))
            self.assertEqual(obj.results[0].value, value)

    def test_schema_rejects_negative_and_over_limit_values(self):
        from pydantic import ValidationError
        for value in (-1, 10001):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                BaselineIn.model_validate(payload(results=[dict(x, value=value) for x in BW]))

    def test_schema_rejects_weight_outside_limits(self):
        from pydantic import ValidationError
        for weight in (-0.1, 1000.1):
            with self.subTest(weight=weight), self.assertRaises(ValidationError):
                BaselineIn.model_validate(payload("ldw", [dict(x, load_kg=weight) for x in LDW]))

    def test_schema_rejects_invalid_program(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            BaselineIn.model_validate(payload("unsupported"))


class BaselineAPIIntegrationTests(unittest.TestCase):
    """Black-box FastAPI + authentication + SQLAlchemy persistence tests."""

    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)

        def isolated_db():
            with Session(self.engine) as session:
                yield session

        app.dependency_overrides[get_db] = isolated_db
        self.client = TestClient(app)
        with Session(self.engine) as db:
            db.add_all([
                User(email="qa-owner@example.test", password_hash="unused"),
                User(email="qa-other@example.test", password_hash="unused"),
            ])
            db.commit()
            self.owner_id = db.scalar(select(User.id).where(User.email == "qa-owner@example.test"))
            self.other_id = db.scalar(select(User.id).where(User.email == "qa-other@example.test"))
        self.owner_headers = {"Authorization": "Bearer " + create_access_token(self.owner_id)}
        self.other_headers = {"Authorization": "Bearer " + create_access_token(self.other_id)}

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def post(self, data, headers=None):
        return self.client.post("/api/program-baselines", json=data,
                                headers=self.owner_headers if headers is None else headers)

    def latest(self, program="bw", headers=None):
        return self.client.get("/api/program-baselines/latest", params={"program": program},
                               headers=self.owner_headers if headers is None else headers)

    def test_catalog_get_for_both_programs(self):
        for slug in ("bw", "ldw"):
            with self.subTest(program=slug):
                result = self.client.get("/api/program-baselines/tests", params={"program": slug})
                self.assertEqual(result.status_code, 200)
                self.assertEqual(len(result.json()), 3)

    def test_first_assessment_save_and_get_latest(self):
        self.assertEqual(self.latest().status_code, 200)
        self.assertIsNone(self.latest().json())
        saved = self.post(payload())
        self.assertEqual(saved.status_code, 201, saved.text)
        record = saved.json()
        self.assertEqual(record["program_slug"], "bw")
        self.assertEqual(record["results"], BW)
        self.assertTrue(record["attempt_id"])
        self.assertEqual(self.latest().json()["id"], record["id"])

    def test_loaded_assessment_persists_weights(self):
        r = self.post(payload("ldw", LDW))
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(self.latest("ldw").json()["results"], LDW)

    def test_reassessment_is_new_record_and_latest(self):
        first = self.post(payload()).json()
        second_data = [dict(x, value=x["value"] + 1) for x in BW]
        second = self.post(payload(results=second_data)).json()
        self.assertNotEqual(first["id"], second["id"])
        self.assertNotEqual(first["attempt_id"], second["attempt_id"])
        self.assertEqual(self.latest().json()["id"], second["id"])
        with Session(self.engine) as db:
            rows = db.scalars(select(ProgramBaseline).where(ProgramBaseline.user_id == self.owner_id)).all()
            self.assertEqual(len(rows), 2)

    def test_program_filter_keeps_assessments_separate(self):
        self.post(payload())
        self.assertIsNone(self.latest("ldw").json())
        self.post(payload("ldw", LDW))
        self.assertEqual(self.latest("bw").json()["program_slug"], "bw")
        self.assertEqual(self.latest("ldw").json()["program_slug"], "ldw")

    def test_users_cannot_read_each_others_baseline(self):
        self.post(payload())
        other = self.latest(headers=self.other_headers)
        self.assertEqual(other.status_code, 200)
        self.assertIsNone(other.json())

    def test_unauthenticated_save_and_read_are_rejected(self):
        self.assertEqual(self.post(payload(), headers={}).status_code, 401)
        self.assertEqual(self.latest(headers={}).status_code, 401)

    def test_invalid_submission_returns_422_and_writes_nothing(self):
        invalid_cases = [
            payload(results=BW[:2]),
            payload(results=BW[:2] + [BW[0]]),
            payload(results=[dict(BW[0], load_kg=5), BW[1], BW[2]]),
            payload("ldw", [dict(LDW[0], load_kg=None), *LDW[1:]]),
            payload(results=[dict(BW[0], value=-1), *BW[1:]]),
            payload("bogus"),
        ]
        for item in invalid_cases:
            with self.subTest(item=item):
                self.assertEqual(self.post(item).status_code, 422)
        with Session(self.engine) as db:
            self.assertEqual(len(db.scalars(select(ProgramBaseline)).all()), 0)


if __name__ == "__main__":
    unittest.main()
