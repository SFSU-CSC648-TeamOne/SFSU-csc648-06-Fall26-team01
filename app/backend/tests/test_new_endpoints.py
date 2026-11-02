import os, tempfile
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/t.db"
os.environ["JWT_SECRET"] = "x" * 40
from fastapi.testclient import TestClient
from app.db.base import Base
from app.db.session import SessionLocal, engine
import app.models
from app.main import app
from app.models import Equipment, Exercise
from app.models.scans import ExerciseScan

Base.metadata.create_all(engine)
c = TestClient(app)

def auth(email="a@x.com"):
    r = c.post("/api/auth/register", json={"email": email, "password": "password1", "display_name": "Ali"})
    assert r.status_code == 201, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}

def test_profile_roundtrip():
    h = auth()
    assert c.get("/api/profile", headers=h).status_code == 404
    with SessionLocal() as db:
        eq = Equipment(name="Dumbbell"); db.add(eq); db.commit(); eid = eq.id
    body = {"goals": ["build muscle"], "experience_level": "beginner", "days_per_week": 4,
            "session_minutes": 45, "physical_constraints": "bad knee", "equipment_ids": [eid]}
    r = c.put("/api/profile", json=body, headers=h); assert r.status_code == 200, r.text
    assert r.json()["equipment_ids"] == [eid]
    r = c.put("/api/profile", json={**body, "experience_level": None, "equipment_ids": []}, headers=h)
    assert r.json()["experience_level"] is None and r.json()["equipment_ids"] == []
    assert c.put("/api/profile", json={**body, "equipment_ids": [9999]}, headers=h).status_code == 422
    assert c.get("/api/profile").status_code == 401

def test_chat_flow_and_isolation():
    h = auth("b@x.com"); h2 = auth("c@x.com")
    cid = c.post("/api/chat/conversations", headers=h).json()["id"]
    r = c.post(f"/api/chat/conversations/{cid}/messages", json={"content": "How many sets?"}, headers=h)
    assert r.status_code == 200 and "How many sets?" in r.json()["reply"]["content"]
    d = c.get(f"/api/chat/conversations/{cid}", headers=h).json()
    assert d["title"] == "How many sets?" and [m["role"] for m in d["messages"]] == ["user", "assistant"]
    assert len(c.get("/api/chat/conversations", headers=h).json()) == 1
    assert c.get(f"/api/chat/conversations/{cid}", headers=h2).status_code == 404
    assert c.delete(f"/api/chat/conversations/{cid}", headers=h2).status_code == 404
    assert c.delete(f"/api/chat/conversations/{cid}", headers=h).status_code == 204
    assert c.get("/api/chat/conversations", headers=h).json() == []

def test_scans():
    with SessionLocal() as db:
        ex = Exercise(name="Push-up"); db.add(ex); db.flush()
        db.add_all([ExerciseScan(exercise_id=ex.id, position=2, label="Bottom", model_url="/b.glb"),
                    ExerciseScan(exercise_id=ex.id, position=1, label="Top", model_url="/t.glb")])
        db.commit(); xid = ex.id
    assert [s["label"] for s in c.get(f"/api/exercises/{xid}/scans").json()] == ["Top", "Bottom"]
    assert c.get("/api/exercises/9999/scans").json() == []
