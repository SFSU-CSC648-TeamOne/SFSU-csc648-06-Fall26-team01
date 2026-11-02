# chat rules: conversations belong to one user; every user message gets an assistant reply

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models import User
from app.repositories import chat as repo
from app.repositories import profile as profile_repo

def generate_reply(history: list, user: User, profile) -> str:
    """PLACEHOLDER - the single place to plug in the real model / RAG call.
    history: ChatMessage list (oldest first, includes the new user message)."""
    last = history[-1].content
    name = user.display_name or "there"
    goal = f" Your goal: {', '.join(profile.goals)}." if profile and profile.goals else ""
    return f"Hi {name}! You asked: \"{last}\".{goal} (The Ascenda coach is not connected yet.)"

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
