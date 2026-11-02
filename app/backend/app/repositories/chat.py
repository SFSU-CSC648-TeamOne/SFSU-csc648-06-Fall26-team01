from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chat import ChatConversation, ChatMessage

def list_conversations(db: Session, user_id: int) -> list:
    return list(db.scalars(select(ChatConversation).where(ChatConversation.user_id == user_id)
                           .order_by(ChatConversation.updated_at.desc(), ChatConversation.id.desc())))

def get_conversation(db: Session, conv_id: int, user_id: int) -> Optional[ChatConversation]:
    conv = db.get(ChatConversation, conv_id)
    return conv if conv and conv.user_id == user_id else None

def add_conversation(db: Session, user_id: int, title: str = "New chat") -> ChatConversation:
    conv = ChatConversation(user_id=user_id, title=title)
    db.add(conv); db.flush()
    return conv

def add_message(db: Session, conv: ChatConversation, role: str, content: str) -> ChatMessage:
    msg = ChatMessage(conversation_id=conv.id, role=role, content=content)
    db.add(msg); db.flush()
    return msg

def count_messages(db: Session, conv_id: int) -> int:
    return len(list(db.scalars(select(ChatMessage.id).where(ChatMessage.conversation_id == conv_id))))

def history(db: Session, conv_id: int) -> list:
    return list(db.scalars(select(ChatMessage).where(ChatMessage.conversation_id == conv_id)
                           .order_by(ChatMessage.id)))

def delete_conversation(db: Session, conv: ChatConversation) -> None:
    db.delete(conv); db.flush()
