# collects route files into a single router, 
# add auth or workouts later when needed

from fastapi import APIRouter

# from app.api.routes import auth, catalog, health, workouts
from app.api.routes import media
api_router.include_router(media.router)

api_router = APIRouter()
for module in (health, auth, catalog, workouts):
    api_router.include_router(module.router)
    