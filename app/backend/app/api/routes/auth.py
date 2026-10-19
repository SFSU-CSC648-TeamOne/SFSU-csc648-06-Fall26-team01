# URL endpoints for handling user registration, login, 
# and who arecurrently logged in

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.auth import LoginIn, RegisterIn, TokenOut, UserOut
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, db: DbSession):
    user, token = auth_service.register(db, email=body.email, password=body.password,
                                        display_name=body.display_name)
    return TokenOut(access_token=token, user=UserOut.model_validate(user))

@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: DbSession):
    user, token = auth_service.login(db, email=body.email, password=body.password)
    return TokenOut(access_token=token, user=UserOut.model_validate(user))

@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user