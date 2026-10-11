# endpoint to check server is running (looking for {"status": "healthy"})

from fastapi import APIRouter
router = APIRouter(tags=["health"])

@router.get("/health")
def health():
    return {"status": "healthy"}