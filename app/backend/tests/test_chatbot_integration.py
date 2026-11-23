
"""P1-07 integration tests for the Ascenda chatbot."""

import os
import tempfile
from uuid import uuid4

import pytest

# Use an isolated local SQLite database.
# Set configuration before importing the application.
_test_dir = tempfile.mkdtemp(prefix="ascenda_chat_test_")
os.environ["DATABASE_URL"] = (
    f"sqlite:///{_test_dir}/chat_integration.db"
)
os.environ["JWT_SECRET"] = "x" * 40

from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import engine
import app.models
from app.main import app
from app.services import chat as chat_service


Base.metadata.create_all(engine)
client = TestClient(app)


def register_user():
    """Register a unique user and return authentication headers."""
    email = f"chat-test-{uuid4().hex}@example.com"

    response = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "password1",
            "display_name": "Chat Tester",
        },
    )

    assert response.status_code == 201, response.text

    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_chat(headers):
    """Create a conversation for an authenticated user."""
    response = client.post(
        "/api/chat/conversations",
        headers=headers,
    )
    assert response.status_code in (200, 201), response.text
    return response.json()["id"]


@pytest.fixture
def mock_gemini(monkeypatch):
    """Replace Gemini generation with a predictable reply."""

    def fake_reply(history, user, profile):
        return f"Coach reply: {history[-1].content}"

    monkeypatch.setattr(
        chat_service,
        "generate_reply",
        fake_reply,
    )


def test_p1_07_create_conversation():
    """Authenticated users can create conversations."""
    headers = register_user()
    conversation_id = create_chat(headers)

    response = client.get(
        f"/api/chat/conversations/{conversation_id}",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["id"] == conversation_id


def test_p1_07_send_message(mock_gemini):
    """A message receives a generated assistant response."""
    headers = register_user()
    conversation_id = create_chat(headers)

    response = client.post(
        f"/api/chat/conversations/{conversation_id}/messages",
        json={"content": "How many sets should I do?"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert (
        response.json()["reply"]["content"]
        == "Coach reply: How many sets should I do?"
    )


def test_p1_07_conversation_history(mock_gemini):
    """User and assistant messages persist in the database."""
    headers = register_user()
    conversation_id = create_chat(headers)

    client.post(
        f"/api/chat/conversations/{conversation_id}/messages",
        json={"content": "What workout should I do?"},
        headers=headers,
    )

    response = client.get(
        f"/api/chat/conversations/{conversation_id}",
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()
    assert data["title"] == "What workout should I do?"
    assert [m["role"] for m in data["messages"]] == [
        "user",
        "assistant",
    ]


def test_p1_07_user_isolation():
    """Users cannot access another user's conversations."""
    user_one = register_user()
    user_two = register_user()

    conversation_id = create_chat(user_one)

    response = client.get(
        f"/api/chat/conversations/{conversation_id}",
        headers=user_two,
    )

    assert response.status_code == 404

    delete_response = client.delete(
        f"/api/chat/conversations/{conversation_id}",
        headers=user_two,
    )

    assert delete_response.status_code == 404


def test_p1_07_authentication_required():
    """Unauthenticated clients cannot list conversations."""
    response = client.get("/api/chat/conversations")
    assert response.status_code == 401


def test_p1_07_chat_service_failure(monkeypatch):
    """The API reports chatbot service unavailability."""

    def unavailable(history, user, profile):
        raise chat_service.GeminiUnavailableError(
            "Chat temporarily unavailable."
        )

    monkeypatch.setattr(
        chat_service,
        "generate_reply",
        unavailable,
    )

    headers = register_user()
    conversation_id = create_chat(headers)

    response = client.post(
        f"/api/chat/conversations/{conversation_id}/messages",
        json={"content": "Hello"},
        headers=headers,
    )

    assert response.status_code == 503
