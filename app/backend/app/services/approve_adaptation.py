
"""Apply user-approved adaptive training adjustments.

Security and consistency:
- Only the prescription owner can approve adjustments.
- Only planned workouts can be modified.
- Recommendations are recalculated on the server.
- Stale or altered proposals are rejected.
- Workouts with recorded performance are protected.
- All approved set changes succeed or fail together.

Scope: one workout prescription per approval request.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import (
    ConflictError,
    NotFoundError,
    ValidationFailed,
)
from app.models.enums import PrescriptionStatus
from app.models.prescription import (
    PrescriptionSet,
    WorkoutPrescription,
)
from app.models.tracking import (
    PerformanceEntry,
    WorkoutRecord,
)
from app.services.prescription_adaptation import (
    analyze_prescription_adaptations,
)


@dataclass(frozen=True)
class ApprovedAdjustment:
    prescription_set_id: int
    adjustment_type: str
    expected_previous_value: Decimal
    expected_proposed_value: Decimal


def _number(value) -> Decimal:
    """Normalize numerical values for exact comparison."""
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationFailed(
            "Adjustment values must be valid numbers."
        ) from exc

    if not result.is_finite():
        raise ValidationFailed(
            "Adjustment values must be finite."
        )

    return result


def _current_value(
    prescribed_set: PrescriptionSet,
    adjustment_type: str,
):
    if adjustment_type == "reps":
        return prescribed_set.target_reps

    if adjustment_type == "duration":
        return prescribed_set.target_duration_seconds

    if adjustment_type == "weight":
        return prescribed_set.target_weight_kg

    # Assistance targets are not yet stored by
    # the current PrescriptionSet model.
    raise ValidationFailed(
        "This adjustment type cannot currently be applied."
    )


def _apply_value(
    prescribed_set: PrescriptionSet,
    adjustment_type: str,
    value: Decimal,
):
    if adjustment_type == "reps":
        if value != value.to_integral_value() or value <= 0:
            raise ValidationFailed(
                "Repetition targets must be positive integers."
            )
        prescribed_set.target_reps = int(value)

    elif adjustment_type == "duration":
        if value != value.to_integral_value() or value <= 0:
            raise ValidationFailed(
                "Duration targets must be positive integers."
            )
        prescribed_set.target_duration_seconds = int(value)

    elif adjustment_type == "weight":
        if (
            value <= 0
            or value > Decimal("9999.99")
            or value.as_tuple().exponent < -2
        ):
            raise ValidationFailed(
                "Weight targets must be positive values "
                "with no more than two decimal places."
            )
        prescribed_set.target_weight_kg = value

    else:
        raise ValidationFailed(
            "Unsupported adjustment type."
        )


def apply_approved_adaptations(
    db: Session,
    user_id: int,
    prescription_id: int,
    approvals: list[ApprovedAdjustment],
) -> dict:
    """Apply selected, freshly validated progression proposals.

    Call only after an explicit user approval action.

    Raises application errors for invalid ownership,
    stale proposals, and unsafe prescription changes.
    """

    if not approvals:
        raise ValidationFailed(
            "Select at least one adjustment to approve."
        )

    requested_ids = [
        item.prescription_set_id
        for item in approvals
    ]

    if (
        any(item_id <= 0 for item_id in requested_ids)
        or len(requested_ids) != len(set(requested_ids))
    ):
        raise ValidationFailed(
            "Adjustment set IDs must be positive and unique."
        )

    # Lock the prescription while validating and updating.
    # PostgreSQL holds this row lock until commit/rollback.
    prescription = db.scalar(
        select(WorkoutPrescription)
        .where(
            WorkoutPrescription.id == prescription_id,
            WorkoutPrescription.user_id == user_id,
        )
        .with_for_update()
    )

    if prescription is None:
        raise NotFoundError(
            "Workout prescription not found."
        )

    if prescription.status != PrescriptionStatus.planned.value:
        raise ConflictError(
            "Only planned prescriptions can be modified."
        )

    # Protect the entire workout if performance has already
    # been recorded for this program/week/day.
    existing_workout = db.scalar(
        select(WorkoutRecord.id)
        .where(
            WorkoutRecord.user_id == user_id,
            WorkoutRecord.program_slug
            == prescription.program_slug,
            WorkoutRecord.program_week
            == prescription.program_week,
            WorkoutRecord.program_day
            == prescription.program_day,
        )
        .limit(1)
    )

    if existing_workout is not None:
        raise ConflictError(
            "This workout already has recorded history "
            "and cannot be adapted."
        )

    # Lock selected set rows as well.
    selected_sets = db.scalars(
        select(PrescriptionSet)
        .where(
            PrescriptionSet.workout_prescription_id
            == prescription.id,
            PrescriptionSet.id.in_(requested_ids),
        )
        .with_for_update()
    ).all()

    sets_by_id = {
        item.id: item
        for item in selected_sets
    }

    if len(sets_by_id) != len(requested_ids):
        raise ValidationFailed(
            "One or more selected sets do not belong "
            "to this prescription."
        )

    # Never rewrite a prescription set already referenced
    # by a historical performance entry.
    historical_entry = db.scalar(
        select(PerformanceEntry.id)
        .where(
            PerformanceEntry.prescription_set_id.in_(
                requested_ids
            )
        )
        .limit(1)
    )

    if historical_entry is not None:
        raise ConflictError(
            "A selected set has recorded performance "
            "and cannot be changed."
        )

    # Recalculate all recommendations using current
    # historical performance and prescription targets.
    analysis = analyze_prescription_adaptations(
        db=db,
        user_id=user_id,
        prescription_id=prescription_id,
    )

    available = {
        item["prescription_set_id"]: item
        for item in analysis["sets"]
    }

    validated_changes = []

    for approval in approvals:
        item = available.get(
            approval.prescription_set_id
        )

        if item is None:
            raise ConflictError(
                "The selected recommendation is no longer available."
            )

        proposal = item["proposal"]
        prescribed_set = sets_by_id[
            approval.prescription_set_id
        ]

        if (
            item["decision"]["action"] != "progress"
            or not proposal["requires_approval"]
            or proposal["adjustment_type"]
            != approval.adjustment_type
        ):
            raise ConflictError(
                "The recommendation is no longer eligible "
                "for approval."
            )

        if approval.adjustment_type not in {
            "reps",
            "duration",
            "weight",
        }:
            raise ValidationFailed(
                "This adjustment type is not supported "
                "by the current prescription schema."
            )

        previous = proposal["previous_value"]
        proposed = proposal["proposed_value"]

        if previous is None or proposed is None:
            raise ConflictError(
                "Recommendation values are incomplete."
            )

        current = _current_value(
            prescribed_set,
            approval.adjustment_type,
        )

        if current is None:
            raise ConflictError(
                "The current prescription target is missing."
            )

        # Compare both the submitted proposal and the
        # original target against freshly calculated data.
        if (
            _number(previous)
            != approval.expected_previous_value
            or _number(proposed)
            != approval.expected_proposed_value
            or _number(current)
            != approval.expected_previous_value
        ):
            raise ConflictError(
                "The recommendation has changed. "
                "Refresh the progress page and review it again."
            )

        # Validate all changes before modifying any rows.
        validated_changes.append((
            prescribed_set,
            approval.adjustment_type,
            _number(proposed),
        ))

    # Validate target compatibility before persistence.
    for prescribed_set, adjustment_type, value in validated_changes:
        if adjustment_type in {"reps", "duration"}:
            if value <= 0 or value != value.to_integral_value():
                raise ValidationFailed(
                    "Repetition and duration targets must "
                    "be positive integers."
                )
        elif adjustment_type == "weight":
            if (
                value <= 0
                or value > Decimal("9999.99")
                or value.as_tuple().exponent < -2
            ):
                raise ValidationFailed(
                    "Invalid proposed weight target."
                )

    # All validation has succeeded.
    for prescribed_set, adjustment_type, value in validated_changes:
        _apply_value(
            prescribed_set,
            adjustment_type,
            value,
        )

    # One transaction persists all selected changes.
    db.commit()

    return {
        "prescription_id": prescription.id,
        "status": "updated",
        "updated_set_count": len(validated_changes),
        "updated_sets": [
            {
                "prescription_set_id": item.id,
                "adjustment_type": adjustment_type,
                "applied_value": (
                    int(value)
                    if adjustment_type in {"reps", "duration"}
                    else float(value)
                ),
            }
            for item, adjustment_type, value in validated_changes
        ],
    }
