from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    display_name: Optional[str] = Field(default=None, max_length=100)

    @field_validator("email")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.lower()

class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=72)

    @field_validator("email")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.lower()

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    display_name: Optional[str]
    role: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut