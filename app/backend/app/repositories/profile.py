from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Equipment
from app.models.users import UserProfile

def get_profile(db: Session, user_id: int) -> Optional[UserProfile]:
    return db.scalar(select(UserProfile).where(UserProfile.user_id == user_id))

def create_profile(db: Session, user_id: int) -> UserProfile:
    p = UserProfile(user_id=user_id, goals=[])
    db.add(p); db.flush()
    return p

def equipment_by_ids(db: Session, ids: list) -> list:
    if not ids:
        return []
    return list(db.scalars(select(Equipment).where(Equipment.id.in_(ids))))
