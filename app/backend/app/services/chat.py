# chat rules: conversations belong to one user; every user message gets an assistant reply

import logging

from google import genai
from google.genai import errors as genai_errors
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError, NotFoundError
from app.models import User
from app.repositories import chat as repo
from app.repositories import profile as profile_repo

logger = logging.getLogger(__name__)


class GeminiUnavailableError(AppError):
    """Raised when Gemini cannot produce a reply (not configured, request failed or empty answer).

    Takes the error message to show the client. The API returns it as HTTP 503 with code "chat_unavailable".
    """
    status_code, code = 503, "chat_unavailable"


def generate_reply(history: list, user: User, profile) -> str:
    """Ask Gemini for the coach's next reply to a conversation.

    Takes the conversation's messages in order, the user (for their display name) and their
    profile, or None, whose goals, experience and schedule are added as context.
    Returns the reply text. Raises GeminiUnavailableError if Gemini is not configured,
    the request fails or the reply is empty.
    """
    settings = get_settings()
    if not settings.gemini_api_key:
        raise GeminiUnavailableError("Gemini is not configured.")

    profile_context = ""
    if profile:
        goals = ", ".join(profile.goals) if profile.goals else "not specified"
        profile_context = (
            f"\nUser profile: goals={goals}; "
            f"experience={profile.experience_level or 'not specified'}; "
            f"days per week={profile.days_per_week or 'not specified'}; "
            f"session minutes={profile.session_minutes or 'not specified'}."
        )

    transcript = "\n".join(
        f"{message.role.title()}: {message.content}" for message in history
    )
    prompt = (
        "You are Ascenda, a concise and encouraging fitness coach. Answer the "
        "user's latest message directly; do not repeat a greeting or introduce "
        "yourself when the conversation is already underway. Only greet the user "
        "if their latest message is itself a greeting. Give practical, safe "
        "guidance. Do not diagnose injuries or replace a qualified medical "
        "professional. Use the conversation and profile context below.\n"
        f"User: {user.display_name or 'there'}{profile_context}\n"
        f"Conversation:\n{transcript}"
    )

    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
        )
    except genai_errors.APIError:
        logger.exception("Gemini request failed")
        raise GeminiUnavailableError("The chat service is temporarily unavailable.")

    reply = (response.text or "").strip()
    if not reply:
        logger.error("Gemini returned an empty response")
        raise GeminiUnavailableError("The chat service returned an empty response.")
    return reply

def _own(db: Session, conv_id: int, user: User):
    conv = repo.get_conversation(db, conv_id, user.id)
    if conv is None:
        raise NotFoundError("Conversation not found.")
    return conv

def list_conversations(db: Session, user: User):
    """List the user's conversations.

    Takes the database session and the signed-in user.
    Returns a list of that user's ChatConversation rows.
    """
    return repo.list_conversations(db, user.id)

def create_conversation(db: Session, user: User):
    """Start a new, empty conversation for the user and save it.

    Takes the database session and the signed-in user.
    Returns the new ChatConversation.
    """
    conv = repo.add_conversation(db, user.id)
    db.commit()
    return conv

def get_conversation(db: Session, user: User, conv_id: int):
    """Get one of the user's conversations.

    Takes the database session, the signed-in user and the conversation id.
    Returns the ChatConversation. Raises NotFoundError if it does not exist or belongs to another user.
    """
    return _own(db, conv_id, user)

def delete_conversation(db: Session, user: User, conv_id: int) -> None:
    """Delete one of the user's conversations and save the change.

    Takes the database session, the signed-in user and the conversation id.
    Returns None. Raises NotFoundError if it does not exist or belongs to another user.
    """
    repo.delete_conversation(db, _own(db, conv_id, user))
    db.commit()

def send_message(db: Session, user: User, conv_id: int, content: str):
    """Add the user's message to a conversation, get the coach's reply and save both.

    The first message in a conversation also becomes its title (up to 60 characters).
    Takes the database session, the signed-in user, the conversation id and the message text.
    Returns a tuple (conversation, user message, assistant message).
    Raises NotFoundError if the conversation is not the user's, and GeminiUnavailableError
    if no reply can be generated.
    """
    conv = _own(db, conv_id, user)
    is_first = repo.count_messages(db, conv.id) == 0
    user_msg = repo.add_message(db, conv, "user", content.strip())
    if is_first:
        conv.title = content.strip()[:60]
    reply_text = generate_reply(repo.history(db, conv.id), user, profile_repo.get_profile(db, user.id))
    reply = repo.add_message(db, conv, "assistant", reply_text)
    conv.updated_at = reply.created_at if reply.created_at else conv.updated_at
    db.commit()
    db.refresh(conv)
    return conv, user_msg, reply
