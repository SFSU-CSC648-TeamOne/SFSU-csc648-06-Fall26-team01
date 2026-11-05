# saved chatbot conversations (floating widget and the full chat page share these)

from fastapi import APIRouter, Response, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.chat import ConversationOut, ConversationSummary, MessageIn, ReplyOut
from app.services import chat as service

router = APIRouter(prefix="/chat", tags=["chat"])

@router.get("/conversations", response_model=list[ConversationSummary])
def list_conversations(db: DbSession, user: CurrentUser):
    return service.list_conversations(db, user)

@router.post("/conversations", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def create_conversation(db: DbSession, user: CurrentUser):
    return service.create_conversation(db, user)

@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
def get_conversation(conversation_id: int, db: DbSession, user: CurrentUser):
    return service.get_conversation(db, user, conversation_id)

@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: int, db: DbSession, user: CurrentUser):
    service.delete_conversation(db, user, conversation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.post("/conversations/{conversation_id}/messages", response_model=ReplyOut)
def send_message(conversation_id: int, data: MessageIn, db: DbSession, user: CurrentUser):
    conv, user_msg, reply = service.send_message(db, user, conversation_id, data.content)
    return ReplyOut(conversation=conv, user_message=user_msg, reply=reply)
