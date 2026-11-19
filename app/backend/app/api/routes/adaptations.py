
"""Authenticated adaptive training endpoints.

Supports:
- Discovering planned workout prescriptions.
- Reviewing recommended adjustments.
- Applying explicitly approved adjustments.
"""

from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Path, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.core.errors import (
    ConflictError,
    NotFoundError,
)
from app.models.enums import PrescriptionStatus
from app.models.prescription import WorkoutPrescription
from app.services.approve_adaptation import (
    ApprovedAdjustment,
    apply_approved_adaptations,
)
from app.services.prescription_adaptation import (
    analyze_prescription_adaptations,
)


router = APIRouter(
    prefix="/adaptations",
    tags=["adaptations"],
)


# --------------------------------------------------
# Response models
# --------------------------------------------------

class PlannedPrescriptionOut(BaseModel):
    id: int
    program_slug: str
    program_week: int
    program_day: int
    set_count: int
    engine_version: str


class AdaptationDecisionOut(BaseModel):
    action: Literal[
        "insufficient_data",
        "maintain",
        "progress",
        "review_regression",
        "reassess",
    ]

    confidence: Literal[
        "insufficient",
        "preliminary",
        "robust",
    ]

    observation_count: int = Field(ge=0)
    change_pct: float | None
    reason: str


class ProgressionProposalOut(BaseModel):
    adjustment_type: Literal[
        "reps",
        "duration",
        "weight",
        "assistance",
        "none",
    ]

    previous_value: int | float | None
    proposed_value: int | float | None
    requires_approval: bool
    reason: str


class PrescriptionSetAdaptationOut(BaseModel):
    prescription_set_id: int = Field(gt=0)
    exercise_id: int = Field(gt=0)
    set_number: int = Field(gt=0)

    decision: AdaptationDecisionOut
    proposal: ProgressionProposalOut


class PrescriptionAdaptationResponse(BaseModel):
    prescription_id: int = Field(gt=0)
    user_id: int = Field(gt=0)

    program_slug: str
    program_week: int
    program_day: int

    source_engine_version: str
    proposal_engine_version: str

    status: Literal["proposed"]
    sets: list[PrescriptionSetAdaptationOut]


# --------------------------------------------------
# Approval request and response models
# --------------------------------------------------

class ApprovedAdjustmentIn(BaseModel):
    prescription_set_id: int = Field(gt=0)

    adjustment_type: Literal[
        "reps",
        "duration",
        "weight",
    ]

    expected_previous_value: Decimal
    expected_proposed_value: Decimal

    @field_validator(
        "expected_previous_value",
        "expected_proposed_value",
    )
    @classmethod
    def validate_finite_number(
        cls,
        value: Decimal,
    ) -> Decimal:
        if not value.is_finite():
            raise ValueError(
                "Adjustment values must be finite numbers."
            )

        return value


class ApproveAdaptationsIn(BaseModel):
    approvals: list[ApprovedAdjustmentIn] = Field(
        min_length=1,
        max_length=100,
    )


class AppliedAdjustmentOut(BaseModel):
    prescription_set_id: int
    adjustment_type: Literal[
        "reps",
        "duration",
        "weight",
    ]
    applied_value: int | float


class ApproveAdaptationsOut(BaseModel):
    prescription_id: int
    status: Literal["updated"]
    updated_set_count: int
    updated_sets: list[AppliedAdjustmentOut]


# --------------------------------------------------
# Planned prescription discovery
# --------------------------------------------------

@router.get(
    "/planned-prescriptions",
    response_model=list[PlannedPrescriptionOut],
)
def get_planned_prescriptions(
    user: CurrentUser,
    db: DbSession,
    program: Annotated[
        str | None,
        Query(min_length=1, max_length=20),
    ] = None,
):
    """List the current user's planned workout prescriptions."""

    statement = (
        select(WorkoutPrescription)
        .options(
            selectinload(WorkoutPrescription.sets)
        )
        .where(
            WorkoutPrescription.user_id == user.id,
            WorkoutPrescription.status
            == PrescriptionStatus.planned.value,
        )
    )

    if program is not None:
        statement = statement.where(
            WorkoutPrescription.program_slug == program
        )

    statement = statement.order_by(
        WorkoutPrescription.program_slug,
        WorkoutPrescription.program_week,
        WorkoutPrescription.program_day,
        WorkoutPrescription.id,
    ).limit(100)

    prescriptions = db.scalars(statement).all()

    return [
        PlannedPrescriptionOut(
            id=prescription.id,
            program_slug=prescription.program_slug,
            program_week=prescription.program_week,
            program_day=prescription.program_day,
            set_count=len(prescription.sets),
            engine_version=prescription.engine_version,
        )
        for prescription in prescriptions
    ]


# --------------------------------------------------
# Read-only recommendations
# --------------------------------------------------

@router.get(
    "/prescriptions/{prescription_id}",
    response_model=PrescriptionAdaptationResponse,
)
def get_prescription_adaptations(
    user: CurrentUser,
    db: DbSession,
    prescription_id: Annotated[int, Path(gt=0)],
):
    """Generate recommendations without changing prescriptions."""

    try:
        return analyze_prescription_adaptations(
            db=db,
            user_id=user.id,
            prescription_id=prescription_id,
        )

    except LookupError as exc:
        raise NotFoundError(
            "Workout prescription not found."
        ) from exc

    except ValueError as exc:
        raise ConflictError(str(exc)) from exc


# --------------------------------------------------
# Apply approved adaptations
# --------------------------------------------------

@router.post(
    "/prescriptions/{prescription_id}/approve",
    response_model=ApproveAdaptationsOut,
)
def approve_prescription_adaptations(
    body: ApproveAdaptationsIn,
    user: CurrentUser,
    db: DbSession,
    prescription_id: Annotated[int, Path(gt=0)],
):
    """Apply explicitly selected, server-validated adjustments.

    The client supplies the targets it reviewed.
    The approval service recalculates recommendations
    before modifying the planned prescription.

    Completed workouts and historical performance
    entries cannot be modified through this endpoint.
    """

    approvals = [
        ApprovedAdjustment(
            prescription_set_id=item.prescription_set_id,
            adjustment_type=item.adjustment_type,
            expected_previous_value=(
                item.expected_previous_value
            ),
            expected_proposed_value=(
                item.expected_proposed_value
            ),
        )
        for item in body.approvals
    ]

    return apply_approved_adaptations(
        db=db,
        user_id=user.id,
        prescription_id=prescription_id,
        approvals=approvals,
    )
