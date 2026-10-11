# collects route files into a single router, 
# add auth or workouts later when needed

from fastapi import APIRouter

from app.api.routes import auth, catalog, health, workouts

api_router = APIRouter()
for module in (health, auth, catalog, workouts):
    api_router.include_router(module.router)
    