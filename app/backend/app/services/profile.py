# read / save the logged-in user's training profile (uses the existing user_profiles table)

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationFailed
from app.models import User
from app.repositories import profile as repo
from app.schemas.profile import ProfileIn, ProfileOut

def _out(p) -> ProfileOut:
    return ProfileOut(goals=list(p.goals or []), experience_level=p.experience_level,
                      days_per_week=p.days_per_week, session_minutes=p.session_minutes,
                      physical_constraints=p.physical_constraints,
                      equipment_ids=sorted(e.id for e in p.equipment))

def get_profile(db: Session, user: User) -> ProfileOut:
    p = repo.get_profile(db, user.id)
    if p is None:
        raise NotFoundError("Profile not set up yet.")
    return _out(p)

def save_profile(db: Session, user: User, data: ProfileIn) -> ProfileOut:
    equipment = repo.equipment_by_ids(db, data.equipment_ids)
    if len(equipment) != len(set(data.equipment_ids)):
        raise ValidationFailed("One or more equipment ids do not exist.")
    p = repo.get_profile(db, user.id) or repo.create_profile(db, user.id)
    p.goals = [g.strip() for g in data.goals if g.strip()]
    p.experience_level = data.experience_level.value if data.experience_level else None
    p.days_per_week = data.days_per_week
    p.session_minutes = data.session_minutes
    p.physical_constraints = (data.physical_constraints or "").strip() or None
    p.equipment = equipment
    db.commit()
    db.refresh(p)
    return _out(p)
