"""Request and response schemas for program-wide adaptation previews.

These schemas describe read-only proposals. They do not
authorize or apply any program-wide prescription changes.
"""

from decimal import Decimal
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

AdjustmentType = Literal[
    "reps",
    "duration",
    "weight",
]

ExclusionReason = Literal[
    "phase_unclassified",
    "deload_protected",
    "assessment_protected",
    "phase_not_eligible",
    "workout_history_exists",
    "missing_matching_set",
    "ambiguous_matching_sets",
    "set_has_recorded_performance",
    "target_metric_missing",
    "proposed_target_invalid",
]


class ProgramAdaptationPreviewIn(BaseModel):
    """Previously approved individual progression to propagate."""

    model_config = ConfigDict(extra="forbid")

    prescription_id: int = Field(gt=0)
    prescription_set_id: int = Field(gt=0)

    adjustment_type: AdjustmentType

    previous_value: Decimal
    approved_value: Decimal

    @field_validator(
        "previous_value",
        "approved_value",
    )
    @classmethod
    def validate_number(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value <= 0:
            raise ValueError("Adjustment values must be positive " "and finite.")

        return value

    @model_validator(mode="after")
    def validate_progression(self):
        if self.approved_value <= self.previous_value:
            raise ValueError("Approved value must exceed previous value.")

        if self.adjustment_type in {"reps", "duration"}:
            for value in (
                self.previous_value,
                self.approved_value,
            ):
                if value != value.to_integral_value() or value > Decimal("2147483647"):
                    raise ValueError(
                        "Repetition and duration targets "
                        "must be valid positive integers."
                    )

        if self.adjustment_type == "weight":
            for value in (
                self.previous_value,
                self.approved_value,
            ):
                if value > Decimal("9999.99") or value.as_tuple().exponent < -2:
                    raise ValueError("Weight targets must fit Numeric(6,2).")

        return self


class ProgramAdaptationCandidateOut(BaseModel):
    """One future set eligible for explicit user review."""

    prescription_id: int = Field(gt=0)
    prescription_set_id: int = Field(gt=0)

    program_week: int = Field(gt=0)
    program_day: int = Field(gt=0)

    exercise_id: int = Field(gt=0)
    set_number: int = Field(gt=0)

    adjustment_type: AdjustmentType
    phase_type: Literal["training"]

    current_value: int | float
    proposed_value: int | float

    requires_program_phase_review: Literal[True]
    status: Literal["review_required"]


class ProgramAdaptationExcludedOut(BaseModel):
    """Future workout excluded from propagation."""

    prescription_id: int = Field(gt=0)
    program_week: int = Field(gt=0)
    program_day: int = Field(gt=0)

    reason: ExclusionReason


class ProgramAdaptationPreviewOut(BaseModel):
    """Complete read-only program propagation preview."""

    user_id: int = Field(gt=0)
    program_instance_id: int | None = Field(
        default=None,
        gt=0,
    )

    source_approval_id: int = Field(gt=0)

    program_slug: str
    source_baseline_id: int | None = Field(
        default=None,
        gt=0,
    )

    source_prescription_id: int = Field(gt=0)
    source_prescription_set_id: int = Field(gt=0)

    adjustment_type: AdjustmentType

    original_value: int | float
    approved_value: int | float
    delta: int | float

    status: Literal["review_required"]

    candidates: list[ProgramAdaptationCandidateOut]
    excluded: list[ProgramAdaptationExcludedOut]

    database_modified: Literal[False]
