"""Authenticated program-wide adaptation endpoints.

Endpoints:
- Preview eligible future prescription adjustments.
- Apply explicitly selected program-wide adjustments.

Preview requests never modify prescriptions.

Approval requests use the existing atomic application
service, which revalidates selections, persists audit
records, and commits all changes together.
"""

from typing import Annotated

from fastapi import APIRouter, Path

from app.api.deps import CurrentUser, DbSession

from app.schemas.program_adaptation import (
    ProgramAdaptationPreviewIn,
    ProgramAdaptationPreviewOut,
)

from app.schemas.program_adaptation_approval import (
    ApplyProgramAdaptationsIn,
    ApplyProgramAdaptationsOut,
)

from app.services.program_adaptation import (
    preview_program_propagation,
)

from app.services.apply_program_adaptations import (
    SelectedProgramAdjustment,
    apply_program_adaptations,
)

router = APIRouter(
    prefix="/adaptations",
    tags=["adaptations"],
)


# --------------------------------------------------
# Read-only program-wide adaptation preview
# --------------------------------------------------


@router.post(
    "/program-instances/{program_instance_id}/preview",
    response_model=ProgramAdaptationPreviewOut,
)
def preview_program_adaptations(
    body: ProgramAdaptationPreviewIn,
    user: CurrentUser,
    db: DbSession,
    program_instance_id: Annotated[int, Path(gt=0)],
):
    """Preview eligible future changes for one enrollment.

    Requires an existing individual adaptation approval.

    The service verifies enrollment ownership, source
    approval, workout phases, historical performance,
    and target compatibility.

    This endpoint never applies changes.
    """

    return preview_program_propagation(
        db=db,
        user_id=user.id,
        prescription_id=body.prescription_id,
        prescription_set_id=body.prescription_set_id,
        adjustment_type=body.adjustment_type,
        previous_value=body.previous_value,
        approved_value=body.approved_value,
        program_instance_id=program_instance_id,
    )


# --------------------------------------------------
# Atomic program-wide adaptation approval
# --------------------------------------------------


@router.post(
    "/program-instances/{program_instance_id}/approve",
    response_model=ApplyProgramAdaptationsOut,
)
def approve_program_adaptations(
    body: ApplyProgramAdaptationsIn,
    user: CurrentUser,
    db: DbSession,
    program_instance_id: Annotated[int, Path(gt=0)],
):
    """Apply explicitly approved future prescription changes.

    The authenticated user is the approval authority.

    Each selected set must match a current server-side
    recommendation. The client cannot independently
    choose an adjustment type or invent a new target.

    The service:
    - Locks the program enrollment and prescriptions.
    - Verifies the original individual approval.
    - Recalculates eligibility.
    - Rejects stale or protected targets.
    - Applies only selected sets.
    - Records all audit entries atomically.
    - Handles idempotent request retries.

    The route does not commit independently.
    """

    selections = [
        SelectedProgramAdjustment(
            prescription_set_id=item.prescription_set_id,
            expected_previous_value=(item.expected_previous_value),
            expected_proposed_value=(item.expected_proposed_value),
        )
        for item in body.selections
    ]

    return apply_program_adaptations(
        db=db,
        user_id=user.id,
        program_instance_id=program_instance_id,
        source_approval_id=body.source_approval_id,
        request_key=body.request_key,
        selections=selections,
    )
