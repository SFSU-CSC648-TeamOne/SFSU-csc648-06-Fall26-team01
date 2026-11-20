
"""Request and response schemas for program-wide adaptations.

The client explicitly selects future prescription sets.

The backend must independently:
- Authenticate the user.
- Verify enrollment ownership.
- Validate the source individual approval.
- Recalculate current eligible candidates.
- Reject stale or altered proposals.
- Apply changes and audit records atomically.

Request validation alone does not authorize modifications.
"""

from decimal import Decimal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from typing import Literal


class SelectedProgramAdjustmentIn(BaseModel):
    """One future prescription set selected by the user."""

    model_config = ConfigDict(extra="forbid")

    prescription_set_id: int = Field(gt=0)

    expected_previous_value: Decimal
    expected_proposed_value: Decimal

    @field_validator(
        "expected_previous_value",
        "expected_proposed_value",
    )
    @classmethod
    def validate_finite_positive(
        cls,
        value: Decimal,
    ) -> Decimal:
        if not value.is_finite() or value <= 0:
            raise ValueError(
                "Adjustment values must be positive "
                "and finite."
            )

        return value

    @model_validator(mode="after")
    def validate_progression(self):
        if (
            self.expected_proposed_value
            <= self.expected_previous_value
        ):
            raise ValueError(
                "Proposed value must exceed "
                "the previous value."
            )

        return self


class ApplyProgramAdaptationsIn(BaseModel):
    """Explicit bulk approval request."""

    model_config = ConfigDict(extra="forbid")

    source_approval_id: int = Field(gt=0)

    # Stable key generated once for this approval action.
    # Retries must reuse the same key and payload.
    request_key: str = Field(
        min_length=1,
        max_length=64,
    )

    selections: list[SelectedProgramAdjustmentIn] = Field(
        min_length=1,
        max_length=100,
    )

    @field_validator("request_key")
    @classmethod
    def validate_request_key(cls, value: str) -> str:
        if not value.strip():
            raise ValueError(
                "Idempotency key cannot be blank."
            )

        return value

    @model_validator(mode="after")
    def validate_unique_selections(self):
        ids = [
            item.prescription_set_id
            for item in self.selections
        ]

        if len(ids) != len(set(ids)):
            raise ValueError(
                "Each prescription set may only "
                "be selected once."
            )

        return self


class AppliedProgramAdjustmentOut(BaseModel):
    """One successfully applied prescription change."""

    prescription_set_id: int = Field(gt=0)

    adjustment_type: Literal[
        "reps",
        "duration",
        "weight",
    ]

    previous_value: int | float
    applied_value: int | float


class ApplyProgramAdaptationsOut(BaseModel):
    """Result of an atomic program-wide approval."""

    program_instance_id: int = Field(gt=0)

    program_adaptation_approval_id: int = Field(gt=0)

    source_approval_id: int = Field(gt=0)

    status: Literal[
        "updated",
        "already_applied",
    ]

    updated_set_count: int = Field(ge=1)

    updated_sets: list[AppliedProgramAdjustmentOut]
