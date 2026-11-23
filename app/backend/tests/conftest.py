# must be named conftest.py or fail with fixture client not found

import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/unit.db"
os.environ["JWT_SECRET"] = "x" * 40

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

@pytest.fixture() 
def db_session():
    import app.models
    from app.db.base import Base

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with Session() as session:
        yield session

    engine.dispose()

@pytest.fixture()
def client(db_session):
    from app.db.session import get_db
    from app.main import app

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()

@pytest.fixture()
def make_user(client): # registers user and returns their detail
    def _make(email="user@example.com", password="password123",
              display_name="Test User"):
        response = client.post(
            "/api/auth/register",
            json={"email": email, "password": password,
                  "display_name": display_name},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        return {
            "headers": {"authorization": f"Bearer {body['access_token']}"},
            "user": body["user"], # failed tests here, had capitalization error
            "email": email,
            "password": password,
        }
    return _make
    