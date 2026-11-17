# collects route files into a single router,
# add auth or workouts later when needed

from fastapi import APIRouter

from app.api.routes import (auth, catalog, chat, health, bodyweight, media, profile, 
                            progress, scans, workouts, program_baselines, assessment)

api_router = APIRouter()
for module in (auth, catalog, chat, health, bodyweight, media, profile, 
                progress, scans, workouts, program_baselines, assessment):
    api_router.include_router(module.router)
