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
    status_code, code = 503, "chat_unavailable"


def generate_reply(history: list, user: User, profile) -> str:
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
    return repo.list_conversations(db, user.id)

def create_conversation(db: Session, user: User):
    conv = repo.add_conversation(db, user.id)
    db.commit()
    return conv

def get_conversation(db: Session, user: User, conv_id: int):
    return _own(db, conv_id, user)

def delete_conversation(db: Session, user: User, conv_id: int) -> None:
    repo.delete_conversation(db, _own(db, conv_id, user))
    db.commit()

def send_message(db: Session, user: User, conv_id: int, content: str):
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
