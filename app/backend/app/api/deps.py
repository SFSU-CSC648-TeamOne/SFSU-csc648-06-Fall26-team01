# checks who is logged in for the database session

from typing import Annotated, Optional

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import AuthenticationError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User
from app.repositories import users as users_repo

DbSession = Annotated[Session, Depends(get_db)]
_bearer = HTTPBearer(auto_error=False)

def get_current_user(
    db: DbSession,
    creds: Annotated[Optional[HTTPAuthorizationCredentials], Depends(_bearer)],
) -> User:
    if creds is None:
        raise AuthenticationError("Not authenticated.")
    user_id = decode_access_token(creds.credentials)
    user = users_repo.get_user(db, user_id) if user_id else None
    if user is None:
        raise AuthenticationError("Invalid or expired token.")
    return user

CurrentUser = Annotated[User, Depends(get_current_user)]