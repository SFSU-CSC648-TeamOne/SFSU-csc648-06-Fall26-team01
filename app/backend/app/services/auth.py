# register and login rules

from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AuthenticationError, ConflictError
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User
from app.repositories import users as users_repo

# Verifying against a dummy hash keeps login timing similar for unknown emails.
_DUMMY_HASH = hash_password("not-a-real-password")

def register(db: Session, *, email: str, password: str, display_name: Optional[str]) -> tuple:
    if users_repo.get_user_by_email(db, email):
        raise ConflictError("An account with that email already exists.")
    try:
        user = users_repo.add_user(db, email=email, password_hash=hash_password(password),
                                   display_name=display_name)
        db.commit()
    except IntegrityError:  # two simultaneous sign-ups
        db.rollback()
        raise ConflictError("An account with that email already exists.")
    return user, create_access_token(user.id)

def login(db: Session, *, email: str, password: str) -> tuple:
    user = users_repo.get_user_by_email(db, email)
    ok = verify_password(password, user.password_hash if user else _DUMMY_HASH)
    if not user or not ok:
        raise AuthenticationError("Incorrect email or password.")
    return user, create_access_token(user.id)