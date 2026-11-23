
"""Apply and audit user-approved adaptive adjustments.

Rules:
- Only the prescription owner may approve changes.
- Only planned prescriptions may be modified.
- Historical workout performance is protected.
- Recommendations are recalculated server-side.
- Stale and altered proposals are rejected.
- Each approved change creates an audit record.
- All updates and audit records commit atomically.

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
from app.models.adaptation_approval import (
    AdaptationApproval,
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


SUPPORTED_ADJUSTMENTS = {
    "reps",
    "duration",
    "weight",
}


@dataclass(frozen=True)
class ApprovedAdjustment:
    prescription_set_id: int
    adjustment_type: str
    expected_previous_value: Decimal
    expected_proposed_value: Decimal


def _number(value: object) -> Decimal:
    """Normalize numeric inputs without binary float arithmetic."""
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
    """Read the applicable stored prescription target."""

    if adjustment_type == "reps":
        return prescribed_set.target_reps

    if adjustment_type == "duration":
        return prescribed_set.target_duration_seconds

    if adjustment_type == "weight":
        return prescribed_set.target_weight_kg

    raise ValidationFailed(
        "Unsupported adjustment type."
    )


def _validate_target(
    adjustment_type: str,
    value: Decimal,
) -> None:
    """Validate a proposed target before persistence."""

    if adjustment_type not in SUPPORTED_ADJUSTMENTS:
        raise ValidationFailed(
            "Unsupported adjustment type."
        )

    if not value.is_finite() or value <= 0:
        raise ValidationFailed(
            "Prescription targets must be positive."
        )

    if adjustment_type in {"reps", "duration"}:
        if (
            value != value.to_integral_value()
            or value > Decimal("2147483647")
        ):
            raise ValidationFailed(
                "Repetition and duration targets must "
                "be valid positive integers."
            )

    elif adjustment_type == "weight":
        if (
            value > Decimal("9999.99")
            or value.as_tuple().exponent < -2
        ):
            raise ValidationFailed(
                "Weight targets must be positive values "
                "with no more than two decimal places."
            )


def _apply_value(
    prescribed_set: PrescriptionSet,
    adjustment_type: str,
    value: Decimal,
) -> None:
    """Assign a validated target to a prescription set."""

    _validate_target(adjustment_type, value)

    if adjustment_type == "reps":
        prescribed_set.target_reps = int(value)

    elif adjustment_type == "duration":
        prescribed_set.target_duration_seconds = int(value)

    elif adjustment_type == "weight":
        prescribed_set.target_weight_kg = value


def _serialize_value(
    adjustment_type: str,
    value: Decimal,
) -> int | float:
    if adjustment_type in {"reps", "duration"}:
        return int(value)

    return float(value)


def apply_approved_adaptations(
    db: Session,
    user_id: int,
    prescription_id: int,
    approvals: list[ApprovedAdjustment],
) -> dict:
    """Validate, apply, and audit selected adjustments.

    Uses the caller's SQLAlchemy session and commits
    one transaction for all selected adjustments.

    Any failure rolls back the entire transaction.
    """

    try:
        # ----------------------------------------------
        # Validate request structure
        # ----------------------------------------------

        if not approvals:
            raise ValidationFailed(
                "Select at least one adjustment to approve."
            )

        requested_ids = [
            item.prescription_set_id
            for item in approvals
        ]

        if (
            any(
                not isinstance(item_id, int)
                or item_id <= 0
                for item_id in requested_ids
            )
            or len(requested_ids) != len(set(requested_ids))
        ):
            raise ValidationFailed(
                "Adjustment set IDs must be positive and unique."
            )

        for approval in approvals:
            if approval.adjustment_type not in SUPPORTED_ADJUSTMENTS:
                raise ValidationFailed(
                    "Unsupported adjustment type."
                )

            _validate_target(
                approval.adjustment_type,
                _number(approval.expected_previous_value),
            )

            _validate_target(
                approval.adjustment_type,
                _number(approval.expected_proposed_value),
            )

        # ----------------------------------------------
        # Lock and validate source prescription
        # ----------------------------------------------

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

        if (
            prescription.status
            != PrescriptionStatus.planned.value
        ):
            raise ConflictError(
                "Only planned prescriptions can be modified."
            )

        # Prevent changes to workouts with history.
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

        # ----------------------------------------------
        # Lock and validate selected sets
        # ----------------------------------------------

        selected_sets = db.scalars(
            select(PrescriptionSet)
            .where(
                PrescriptionSet.workout_prescription_id
                == prescription.id,
                PrescriptionSet.id.in_(requested_ids),
            )
            .order_by(PrescriptionSet.id)
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

        # ----------------------------------------------
        # Recalculate recommendations
        # ----------------------------------------------

        analysis = analyze_prescription_adaptations(
            db=db,
            user_id=user_id,
            prescription_id=prescription_id,
        )

        engine_version = analysis[
            "proposal_engine_version"
        ]

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
                    "The selected recommendation "
                    "is no longer available."
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
                    "The recommendation is no longer "
                    "eligible for approval."
                )

            previous_raw = proposal["previous_value"]
            proposed_raw = proposal["proposed_value"]

            if (
                previous_raw is None
                or proposed_raw is None
            ):
                raise ConflictError(
                    "Recommendation values are incomplete."
                )

            previous = _number(previous_raw)
            proposed = _number(proposed_raw)

            expected_previous = _number(
                approval.expected_previous_value
            )
            expected_proposed = _number(
                approval.expected_proposed_value
            )

            current_raw = _current_value(
                prescribed_set,
                approval.adjustment_type,
            )

            if current_raw is None:
                raise ConflictError(
                    "The current prescription target "
                    "is missing."
                )

            current = _number(current_raw)

            if (
                previous != expected_previous
                or proposed != expected_proposed
                or current != expected_previous
            ):
                raise ConflictError(
                    "The recommendation has changed. "
                    "Refresh the progress page "
                    "and review it again."
                )

            _validate_target(
                approval.adjustment_type,
                proposed,
            )

            if proposed == current:
                raise ConflictError(
                    "The adjustment has already been applied."
                )

            validated_changes.append(
                (
                    prescribed_set,
                    approval.adjustment_type,
                    current,
                    proposed,
                )
            )

        # ----------------------------------------------
        # Apply changes and create audit records
        # ----------------------------------------------

        updated_sets = []

        for (
            prescribed_set,
            adjustment_type,
            previous,
            proposed,
        ) in validated_changes:

            _apply_value(
                prescribed_set,
                adjustment_type,
                proposed,
            )

            audit = AdaptationApproval(
                user_id=user_id,
                workout_prescription_id=prescription.id,
                prescription_set_id=prescribed_set.id,
                adjustment_type=adjustment_type,
                previous_value=previous,
                approved_value=proposed,
                proposal_engine_version=engine_version,
            )

            db.add(audit)

            updated_sets.append({
                "prescription_set_id": prescribed_set.id,
                "adjustment_type": adjustment_type,
                "applied_value": _serialize_value(
                    adjustment_type,
                    proposed,
                ),
            })

        # ----------------------------------------------
        # Atomic persistence
        # ----------------------------------------------

        # Flush sends both the target updates and audit
        # inserts to PostgreSQL within this transaction.
        # It does not commit them.
        db.flush()

        # Exactly one commit for the complete operation.
        db.commit()

        return {
            "prescription_id": prescription_id,
            "status": "updated",
            "updated_set_count": len(updated_sets),
            "updated_sets": updated_sets,
        }

    except Exception:
        # Discard ALL target updates and audit inserts
        # if validation, flushing, or committing fails.
        db.rollback()
        raise
