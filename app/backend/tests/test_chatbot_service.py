
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.services import chat


@pytest.fixture
def gemini_mock(monkeypatch):
    """Provide a fake Gemini client without making API calls."""
    settings = SimpleNamespace(
        gemini_api_key="test-api-key",
        gemini_model="test-gemini-model",
    )
    monkeypatch.setattr(chat, "get_settings", lambda: settings)

    generate = Mock(
        return_value=SimpleNamespace(text="  Try three sets.  ")
    )
    client = SimpleNamespace(
        models=SimpleNamespace(generate_content=generate)
    )
    constructor = Mock(return_value=client)
    monkeypatch.setattr(chat.genai, "Client", constructor)

    return constructor, generate


def test_generate_reply_success(gemini_mock):
    """A valid Gemini response becomes the chatbot reply."""
    constructor, generate = gemini_mock

    user = SimpleNamespace(display_name="Alex")
    history = [
        SimpleNamespace(role="user", content="How many sets?")
    ]

    result = chat.generate_reply(history, user, None)

    assert result == "Try three sets."
    constructor.assert_called_once_with(api_key="test-api-key")
    assert generate.call_count == 1
    assert generate.call_args.kwargs["model"] == "test-gemini-model"


def test_generate_reply_includes_profile(gemini_mock):
    """The prompt includes the user's fitness profile."""
    _, generate = gemini_mock

    user = SimpleNamespace(display_name="Alex")
    profile = SimpleNamespace(
        goals=["build muscle"],
        experience_level="beginner",
        days_per_week=3,
        session_minutes=45,
    )
    history = [
        SimpleNamespace(role="user", content="Plan my workout")
    ]

    chat.generate_reply(history, user, profile)

    prompt = generate.call_args.kwargs["contents"]

    assert "Alex" in prompt
    assert "build muscle" in prompt
    assert "beginner" in prompt
    assert "days per week=3" in prompt
    assert "session minutes=45" in prompt
    assert "Plan my workout" in prompt


def test_generate_reply_without_profile(gemini_mock):
    """A missing profile does not prevent generating a reply."""
    _, generate = gemini_mock

    user = SimpleNamespace(display_name=None)
    history = [
        SimpleNamespace(role="user", content="Hello")
    ]

    result = chat.generate_reply(history, user, None)

    assert result == "Try three sets."
    assert "User: there" in generate.call_args.kwargs["contents"]


def test_generate_reply_missing_api_key(monkeypatch):
    """Missing Gemini configuration produces a service error."""
    monkeypatch.setattr(
        chat,
        "get_settings",
        lambda: SimpleNamespace(gemini_api_key=""),
    )

    user = SimpleNamespace(display_name="Alex")

    with pytest.raises(
        chat.GeminiUnavailableError,
        match="Gemini is not configured",
    ):
        chat.generate_reply([], user, None)


@pytest.mark.parametrize("empty_text", ["", "   ", None])
def test_generate_reply_empty_response(gemini_mock, empty_text):
    """Empty Gemini responses are rejected."""
    _, generate = gemini_mock
    generate.return_value = SimpleNamespace(text=empty_text)

    user = SimpleNamespace(display_name="Alex")

    with pytest.raises(
        chat.GeminiUnavailableError,
        match="empty response",
    ):
        chat.generate_reply([], user, None)


def test_generate_reply_api_failure(gemini_mock, monkeypatch):
    """Gemini API failures are converted into service errors."""
    _, generate = gemini_mock

    class FakeAPIError(Exception):
        pass

    monkeypatch.setattr(
        chat.genai_errors, "APIError", FakeAPIError
    )
    generate.side_effect = FakeAPIError("API unavailable")

    user = SimpleNamespace(display_name="Alex")

    with pytest.raises(
        chat.GeminiUnavailableError,
        match="temporarily unavailable",
    ):
        chat.generate_reply([], user, None)


def test_missing_conversation_raises_not_found(monkeypatch):
    """Users cannot retrieve nonexistent conversations."""
    monkeypatch.setattr(
        chat.repo,
        "get_conversation",
        lambda db, conv_id, user_id: None,
    )

    user = SimpleNamespace(id=5)

    with pytest.raises(chat.NotFoundError):
        chat.get_conversation(Mock(), user, 999)
