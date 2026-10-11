# user queries
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User

def get_user(db: Session, user_id: int) -> Optional[User]:
    return db.get(User, user_id)

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.scalar(select(User).where(User.email == email))

def add_user(db: Session, *, email: str, password_hash: str, display_name: Optional[str]) -> User:
    user = User(email=email, password_hash=password_hash, display_name=display_name)
    db.add(user)
    db.flush()
    return user