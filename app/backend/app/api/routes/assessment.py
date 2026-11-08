from typing import Annotated, Optional

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.schemas.assessment import ProgramAssessmentOut
from app.services import assessment as service

router = APIRouter(prefix="/assessment", tags=["assessment"])


@router.get("/program", response_model=ProgramAssessmentOut)
def program_assessment(user: CurrentUser, db: DbSession,
                       program: Annotated[Optional[str], Query(max_length=20)] = None,
                       days_total: Annotated[Optional[int], Query(ge=1, le=200)] = None):
    """End-of-program assessment. `program` = program slug (bw / ldw); `days_total` = training days in it."""
    return service.program_assessment(db, user, program, days_total)