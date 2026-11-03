# the logged-in user's training profile (goals, level, days, equipment, limitations)

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.profile import ProfileIn, ProfileOut
from app.services import profile as service

router = APIRouter(tags=["profile"])

@router.get("/profile", response_model=ProfileOut)
def read_profile(db: DbSession, user: CurrentUser):
    return service.get_profile(db, user)

@router.put("/profile", response_model=ProfileOut)
def save_profile(data: ProfileIn, db: DbSession, user: CurrentUser):
    return service.save_profile(db, user, data)
