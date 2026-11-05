from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=4000)

class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    role: str
    content: str
    created_at: datetime

class ConversationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    updated_at: datetime

class ConversationOut(ConversationSummary):
    messages: list[MessageOut]

class ReplyOut(BaseModel):
    conversation: ConversationSummary
    user_message: MessageOut
    reply: MessageOut
