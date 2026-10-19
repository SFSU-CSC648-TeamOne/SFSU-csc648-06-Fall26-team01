# hashes user passwords and checks with corresponding tokens
# to verify the user

from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt

from app.core.config import get_settings

_BCRYPT_MAX_BYTES = 72  # ignores anything past 72 bytes

def hash_password(password: str) -> str:
    raw = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("utf-8")

def verify_password(password: str, password_hash: str) -> bool:
    raw = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    try:
        return bcrypt.checkpw(raw, password_hash.encode("utf-8"))
    except ValueError:
        return False

def create_access_token(user_id: int) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=s.access_token_minutes)}
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_access_token(token: str) -> Optional[int]:
    s = get_settings()
    try:
        data = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
        return int(data["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None