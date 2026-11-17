
"""Read-only planning for program-wide adaptive progression.

A previously approved single-workout adjustment can be
projected onto later prescriptions in the same program.

This module never writes to the database.

Future workout classifications (normal training, deload,
assessment) are not yet persisted. Every candidate therefore
requires explicit review before it can be applied.
"""

from decimal import Decimal
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

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


AdjustmentType = Literal["reps", "duration", "weight"]

TARGET_FIELDS = {
    "reps": "target_reps",
    "duration": "target_duration_seconds",
    "weight": "target_weight_kg",
}


def _decimal(value: object) -> Decimal:
    try:
        result = Decimal(str(value))
    except (ValueError, TypeError, ArithmeticError) as exc:
        raise ValidationFailed(
            "Invalid numeric adjustment."
        ) from exc

    if not result.is_finite():
        raise ValidationFailed(
            "Adjustment values must be finite."
        )

    return result


def _valid_target(
    value: Decimal,
    adjustment_type: AdjustmentType,
) -> bool:
    if value <= 0:
        return False

    if adjustment_type in {"reps", "duration"}:
        return (
            value == value.to_integral_value()
            and value <= Decimal("2147483647")
        )

    return (
        value <= Decimal("9999.99")
        and value.as_tuple().exponent >= -2
    )


def _target_value(
    prescribed_set: PrescriptionSet,
    adjustment_type: AdjustmentType,
):
    return getattr(
        prescribed_set,
        TARGET_FIELDS[adjustment_type],
    )


def _workout_key(
    prescription: WorkoutPrescription,
) -> tuple[int, int, int]:
    return (
        prescription.user_id,
        prescription.program_week,
        prescription.program_day,
    )


def preview_program_propagation(
    db: Session,
    user_id: int,
    prescription_id: int,
    prescription_set_id: int,
    adjustment_type: AdjustmentType,
    previous_value: Decimal,
    approved_value: Decimal,
) -> dict:
    """Preview propagation from an already approved target.

    The source prescription must be planned and its stored
    target must match approved_value.

    Only later prescriptions with the same user, program,
    and non-null source baseline are considered.

    Returns a review-only plan. No changes are committed.
    """

    if adjustment_type not in TARGET_FIELDS:
        raise ValidationFailed(
            "Unsupported adjustment type."
        )

    previous = _decimal(previous_value)
    approved = _decimal(approved_value)

    if (
        not _valid_target(previous, adjustment_type)
        or not _valid_target(approved, adjustment_type)
        or approved <= previous
    ):
        raise ValidationFailed(
            "A valid positive progression is required."
        )

    source = db.scalar(
        select(WorkoutPrescription)
        .options(
            selectinload(WorkoutPrescription.sets)
        )
        .where(
            WorkoutPrescription.id == prescription_id,
            WorkoutPrescription.user_id == user_id,
        )
    )

    if source is None:
        raise NotFoundError(
            "Source workout prescription not found."
        )

    if source.status != PrescriptionStatus.planned.value:
        raise ConflictError(
            "Source prescription must still be planned."
        )

    if source.source_baseline_id is None:
        raise ConflictError(
            "Cannot identify a unique program attempt "
            "without a source baseline."
        )

    source_set = next(
        (
            item
            for item in source.sets
            if item.id == prescription_set_id
        ),
        None,
    )

    if source_set is None:
        raise NotFoundError(
            "Source prescription set not found."
        )

    stored_value = _target_value(
        source_set,
        adjustment_type,
    )

    if (
        stored_value is None
        or _decimal(stored_value) != approved
    ):
        raise ConflictError(
            "The source target no longer matches "
            "the approved adjustment."
        )

    delta = approved - previous

    # Read future prescriptions from the same
    # assessment baseline/program attempt.
    future_prescriptions = db.scalars(
        select(WorkoutPrescription)
        .options(
            selectinload(WorkoutPrescription.sets)
        )
        .where(
            WorkoutPrescription.user_id == user_id,
            WorkoutPrescription.program_slug
            == source.program_slug,
            WorkoutPrescription.source_baseline_id
            == source.source_baseline_id,
            WorkoutPrescription.status
            == PrescriptionStatus.planned.value,
        )
        .order_by(
            WorkoutPrescription.program_week,
            WorkoutPrescription.program_day,
            WorkoutPrescription.id,
        )
    ).all()

    source_position = (
        source.program_week,
        source.program_day,
    )

    future_prescriptions = [
        prescription
        for prescription in future_prescriptions
        if (
            prescription.program_week,
            prescription.program_day,
        ) > source_position
    ]

    # Identify existing workout history in one query.
    # History protects the entire corresponding workout.
    historical_keys = set()

    if future_prescriptions:
        records = db.scalars(
            select(WorkoutRecord)
            .where(
                WorkoutRecord.user_id == user_id,
                WorkoutRecord.program_slug
                == source.program_slug,
            )
        ).all()

        historical_keys = {
            (
                record.user_id,
                record.program_week,
                record.program_day,
            )
            for record in records
            if record.program_week is not None
            and record.program_day is not None
        }

    # Protect linked historical performance entries,
    # even if their workout record metadata differs.
    candidate_set_ids = [
        item.id
        for prescription in future_prescriptions
        for item in prescription.sets
    ]

    referenced_set_ids: set[int] = set()

    if candidate_set_ids:
        referenced_set_ids = set(
            db.scalars(
                select(PerformanceEntry.prescription_set_id)
                .where(
                    PerformanceEntry.prescription_set_id.in_(
                        candidate_set_ids
                    )
                )
            ).all()
        )

    candidates = []
    excluded = []

    for prescription in future_prescriptions:
        position = {
            "prescription_id": prescription.id,
            "program_week": prescription.program_week,
            "program_day": prescription.program_day,
        }

        if _workout_key(prescription) in historical_keys:
            excluded.append({
                **position,
                "reason": "workout_history_exists",
            })
            continue

        matching_sets = [
            item
            for item in prescription.sets
            if (
                item.exercise_id == source_set.exercise_id
                and item.set_number == source_set.set_number
                and item.load_basis == source_set.load_basis
                and item.is_optional == source_set.is_optional
            )
        ]

        if len(matching_sets) != 1:
            excluded.append({
                **position,
                "reason": (
                    "missing_matching_set"
                    if not matching_sets
                    else "ambiguous_matching_sets"
                ),
            })
            continue

        target_set = matching_sets[0]

        if target_set.id in referenced_set_ids:
            excluded.append({
                **position,
                "reason": "set_has_recorded_performance",
            })
            continue

        current_raw = _target_value(
            target_set,
            adjustment_type,
        )

        if current_raw is None:
            excluded.append({
                **position,
                "reason": "target_metric_missing",
            })
            continue

        current = _decimal(current_raw)
        proposed = current + delta

        if not _valid_target(proposed, adjustment_type):
            excluded.append({
                **position,
                "reason": "proposed_target_invalid",
            })
            continue

        candidates.append({
            **position,
            "prescription_set_id": target_set.id,
            "exercise_id": target_set.exercise_id,
            "set_number": target_set.set_number,
            "adjustment_type": adjustment_type,
            "current_value": (
                int(current)
                if adjustment_type != "weight"
                else float(current)
            ),
            "proposed_value": (
                int(proposed)
                if adjustment_type != "weight"
                else float(proposed)
            ),
            "requires_program_phase_review": True,
            "status": "review_required",
        })

    return {
        "user_id": user_id,
        "program_slug": source.program_slug,
        "source_baseline_id": source.source_baseline_id,
        "source_prescription_id": source.id,
        "source_prescription_set_id": source_set.id,
        "adjustment_type": adjustment_type,
        "original_value": (
            int(previous)
            if adjustment_type != "weight"
            else float(previous)
        ),
        "approved_value": (
            int(approved)
            if adjustment_type != "weight"
            else float(approved)
        ),
        "delta": (
            int(delta)
            if adjustment_type != "weight"
            else float(delta)
        ),
        "status": "review_required",
        "candidates": candidates,
        "excluded": excluded,
        "database_modified": False,
    }
