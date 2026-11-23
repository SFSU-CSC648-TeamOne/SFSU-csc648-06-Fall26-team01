# Unit tests for registration, login and token handling

from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

# register
def test_register_returns_token_and_user(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "new@example.com", "password": "password123",
              "display_name": "New User"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "new@example.com"
    assert body["user"]["display_name"] == "New User"
    assert "password" not in body["user"]
    assert "password_hash" not in body["user"]

def test_register_lowercases_email(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "MiXeD@Example.COM", "password": "password123"},
    )
    assert response.status_code == 201
    assert response.json()["user"]["email"] == "mixed@example.com"

def test_register_duplicate_email_conflicts(client, make_user):
    make_user(email="dup@example.com")

    response = client.post(
        "/api/auth/register",
        json={"email": "DUP@example.com", "password": "password123"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "conflict"

def test_register_handles_simultaneous_signup(client, monkeypatch):
    from app.services import auth as auth_service

    def fail_insert(*args, **kwargs):
        raise IntegrityError("INSERT", {}, Exception("duplicate"))

    monkeypatch.setattr(auth_service.users_repo, "add_user", fail_insert)

    response = client.post(
        "/api/auth/register",
        json={"email": "race@example.com", "password": "password123"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "conflict"

def test_register_rejects_short_password(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "short@example.com", "password": "1234567"},
    )
    assert response.status_code == 422

def test_register_rejects_too_long_password(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "long@example.com", "password": "a" * 73},
    )
    assert response.status_code == 422

def test_register_rejects_invalid_email(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "not-an-email", "password": "password123"},
    )
    assert response.status_code == 422

# login
def test_login_success(client, make_user):
    make_user(email="login@example.com", password="password123")

    response = client.post(
        "/api/auth/login",
        json={"email": "login@example.com", "password": "password123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["user"]["email"] == "login@example.com"

def test_login_ignores_email_case(client, make_user):
    make_user(email="case@example.com", password="password123")

    response = client.post(
        "/api/auth/login",
        json={"email": "CASE@Example.com", "password": "password123"},
    )
    assert response.status_code == 200

def test_login_wrong_password(client, make_user):
    make_user(email="wrong@example.com", password="password123")

    response = client.post(
        "/api/auth/login",
        json={"email": "wrong@example.com", "password": "not-the-password"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "unauthenticated"
    assert response.headers["www-authenticate"] == "Bearer"

def test_login_unknown_email_gives_same_error(client, make_user):
    make_user(email="known@example.com", password="password123")

    wrong_password = client.post(
        "/api/auth/login",
        json={"email": "known@example.com", "password": "bad-password"},
    )
    unknown_email = client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "password123"},
    )
    assert unknown_email.status_code == 401
    assert unknown_email.json()["detail"] == wrong_password.json()["detail"]

#/auth/me
def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401

def test_me_returns_current_user(client, make_user):
    account = make_user(email="me@example.com")

    response = client.get("/api/auth/me", headers=account["headers"])

    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"

def test_me_rejects_garbage_token(client):
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer not.a.real.token"},
    )
    assert response.status_code == 401

def test_me_rejects_expired_token(client, make_user):
    account = make_user()
    settings = get_settings()
    expired = jwt.encode(
        {
            "sub": str(account["user"]["id"]),
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {expired}"},
    )
    assert response.status_code == 401

def test_me_rejects_token_for_missing_user(client):
    token = create_access_token(999999)

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401

# security helpers
def test_hash_and_verify_password():
    hashed = hash_password("password123")

    assert hashed != "password123"
    assert verify_password("password123", hashed) is True
    assert verify_password("different", hashed) is False

def test_verify_password_with_invalid_hash_is_false():
    assert verify_password("password123", "not-a-bcrypt-hash") is False

def test_access_token_round_trip():
    token = create_access_token(42)

    assert decode_access_token(token) == 42

def test_decode_garbage_token_returns_none():
    assert decode_access_token("garbage") is None