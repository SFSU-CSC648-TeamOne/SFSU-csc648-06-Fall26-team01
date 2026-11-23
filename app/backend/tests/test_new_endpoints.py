import os
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET", "x" * 40)
import app.models
from app.api.deps import get_db
from app.db.base import Base
from app.main import create_app
from app.models import Equipment, Exercise
from app.models.scans import ExerciseScan
from app.services import chat as chat_service


@pytest.fixture
def isolated_api():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        with SessionLocal() as db:
            yield db

    test_app = create_app()
    test_app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(test_app) as client:
            yield client, SessionLocal
    finally:
        test_app.dependency_overrides.clear()
        engine.dispose()


def auth(c, email=None):
    email = email or f"test-{uuid4().hex}@example.com"
    response = c.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "password1",
            "display_name": "Ali",
        },
    )
    assert response.status_code == 201, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_profile_roundtrip(isolated_api):
    c, SessionLocal = isolated_api
    h = auth(c)
    assert c.get("/api/profile", headers=h).status_code == 404
    with SessionLocal() as db:
        eq = Equipment(name="Dumbbell")
        db.add(eq)
        db.commit()
        eid = eq.id
    body = {
        "goals": ["build muscle"],
        "experience_level": "beginner",
        "days_per_week": 4,
        "session_minutes": 45,
        "physical_constraints": "bad knee",
        "equipment_ids": [eid],
    }
    r = c.put("/api/profile", json=body, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["equipment_ids"] == [eid]
    r = c.put(
        "/api/profile",
        json={**body, "experience_level": None, "equipment_ids": []},
        headers=h,
    )
    assert r.json()["experience_level"] is None and r.json()["equipment_ids"] == []
    assert (
        c.put(
            "/api/profile", json={**body, "equipment_ids": [9999]}, headers=h
        ).status_code
        == 422
    )
    assert c.get("/api/profile").status_code == 401


def test_chat_flow_and_isolation(isolated_api, monkeypatch):
    c, _ = isolated_api
    monkeypatch.setattr(
        chat_service,
        "generate_reply",
        lambda history, user, profile: f"Test reply to: {history[-1].content}",
    )
    h = auth(c)
    h2 = auth(c)
    cid = c.post("/api/chat/conversations", headers=h).json()["id"]
    r = c.post(
        f"/api/chat/conversations/{cid}/messages",
        json={"content": "How many sets?"},
        headers=h,
    )
    assert r.status_code == 200 and "How many sets?" in r.json()["reply"]["content"]
    d = c.get(f"/api/chat/conversations/{cid}", headers=h).json()
    assert d["title"] == "How many sets?" and [m["role"] for m in d["messages"]] == [
        "user",
        "assistant",
    ]
    assert len(c.get("/api/chat/conversations", headers=h).json()) == 1
    assert c.get(f"/api/chat/conversations/{cid}", headers=h2).status_code == 404
    assert c.delete(f"/api/chat/conversations/{cid}", headers=h2).status_code == 404
    assert c.delete(f"/api/chat/conversations/{cid}", headers=h).status_code == 204
    assert c.get("/api/chat/conversations", headers=h).json() == []


def test_scans(isolated_api):
    c, SessionLocal = isolated_api
    with SessionLocal() as db:
        ex = Exercise(name="Push-up")
        db.add(ex)
        db.flush()
        db.add_all(
            [
                ExerciseScan(
                    exercise_id=ex.id, position=2, label="Bottom", model_url="/b.glb"
                ),
                ExerciseScan(
                    exercise_id=ex.id, position=1, label="Top", model_url="/t.glb"
                ),
            ]
        )
        db.commit()
        xid = ex.id
    assert [s["label"] for s in c.get(f"/api/exercises/{xid}/scans").json()] == [
        "Top",
        "Bottom",
    ]
    assert c.get("/api/exercises/9999/scans").json() == []
