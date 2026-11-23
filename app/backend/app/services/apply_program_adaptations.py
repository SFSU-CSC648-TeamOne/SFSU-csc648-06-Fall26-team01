"""Atomically apply selected program-wide adaptation approvals.

Only explicitly selected, currently eligible future sets
may change. The server recalculates the read-only preview
inside the transaction.

The operation owns its commit/rollback boundary.

Concurrency contract:
Workout logging and other prescription writers must acquire
the relevant ProgramInstance / WorkoutPrescription locks
before inserting performance history or changing targets.
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
from app.models.adaptation_approval import AdaptationApproval
from app.models.program_adaptation_approval import (
    ProgramAdaptationApproval,
    ProgramAdaptationApprovalItem,
)
from app.models.program_instance import ProgramInstance
from app.models.program_phase import ProgramPhase
from app.models.prescription import (
    PrescriptionSet,
    WorkoutPrescription,
)
from app.services.program_adaptation import (
    preview_program_propagation,
)

TARGET_FIELDS = {
    "reps": "target_reps",
    "duration": "target_duration_seconds",
    "weight": "target_weight_kg",
}


@dataclass(frozen=True)
class SelectedProgramAdjustment:
    """One future target explicitly approved by the user."""

    prescription_set_id: int
    expected_previous_value: Decimal
    expected_proposed_value: Decimal


def _number(value: object) -> Decimal:
    try:
        result = Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise ValidationFailed("Invalid adjustment value.") from exc

    if not result.is_finite():
        raise ValidationFailed("Adjustment values must be finite.")

    return result


def _validate_selection(
    selections: list[SelectedProgramAdjustment],
) -> None:
    if not selections or len(selections) > 100:
        raise ValidationFailed("Select between 1 and 100 future sets.")

    ids = []

    for item in selections:
        if (
            not isinstance(item.prescription_set_id, int)
            or isinstance(item.prescription_set_id, bool)
            or item.prescription_set_id <= 0
        ):
            raise ValidationFailed("Invalid selected prescription set ID.")

        previous = _number(item.expected_previous_value)
        proposed = _number(item.expected_proposed_value)

        if previous <= 0 or proposed <= previous:
            raise ValidationFailed(
                "Selected targets must represent " "positive progression."
            )

        ids.append(item.prescription_set_id)

    if len(ids) != len(set(ids)):
        raise ValidationFailed("Duplicate prescription set selection.")


def _serialize(
    adjustment_type: str,
    value: Decimal,
) -> int | float:
    if adjustment_type in {"reps", "duration"}:
        return int(value)

    return float(value)


def _replay_result(
    db: Session,
    existing: ProgramAdaptationApproval,
    *,
    instance_id: int,
    source_approval_id: int,
    selections: list[SelectedProgramAdjustment],
) -> dict:
    """Return a prior result only for an identical request."""

    if (
        existing.program_instance_id != instance_id
        or existing.source_approval_id != source_approval_id
    ):
        raise ConflictError("Idempotency key belongs to another request.")

    stored_items = db.scalars(
        select(ProgramAdaptationApprovalItem)
        .where(
            ProgramAdaptationApprovalItem.program_adaptation_approval_id == existing.id
        )
        .order_by(ProgramAdaptationApprovalItem.prescription_set_id)
    ).all()

    expected = {
        item.prescription_set_id: (
            _number(item.expected_previous_value),
            _number(item.expected_proposed_value),
        )
        for item in selections
    }

    recorded = {
        item.prescription_set_id: (
            _number(item.previous_value),
            _number(item.approved_value),
        )
        for item in stored_items
    }

    if recorded != expected:
        raise ConflictError(
            "Idempotency key has different selections " "or target values."
        )

    return {
        "program_instance_id": instance_id,
        "program_adaptation_approval_id": existing.id,
        "source_approval_id": source_approval_id,
        "status": "already_applied",
        "updated_set_count": len(stored_items),
        "updated_sets": [
            {
                "prescription_set_id": item.prescription_set_id,
                "adjustment_type": item.adjustment_type,
                "previous_value": _serialize(
                    item.adjustment_type,
                    _number(item.previous_value),
                ),
                "applied_value": _serialize(
                    item.adjustment_type,
                    _number(item.approved_value),
                ),
            }
            for item in stored_items
        ],
    }


def apply_program_adaptations(
    db: Session,
    *,
    user_id: int,
    program_instance_id: int,
    source_approval_id: int,
    request_key: str,
    selections: list[SelectedProgramAdjustment],
) -> dict:
    """Revalidate and atomically apply selected future targets.

    Requires an existing individual AdaptationApproval.

    A successful application writes one bulk approval event
    plus one item for each changed prescription set.

    A retry with the same key and identical selections
    returns the original result without modifying targets.
    """

    if any(
        not isinstance(value, int) or isinstance(value, bool) or value <= 0
        for value in (
            user_id,
            program_instance_id,
            source_approval_id,
        )
    ):
        raise ValidationFailed("Invalid identifier.")

    if (
        not isinstance(request_key, str)
        or not 1 <= len(request_key) <= 64
        or not request_key.strip()
    ):
        raise ValidationFailed("A valid idempotency key is required.")

    _validate_selection(selections)

    try:
        # --------------------------------------------------
        # 1. Lock enrollment: serialization boundary
        # --------------------------------------------------

        instance = db.scalar(
            select(ProgramInstance)
            .where(
                ProgramInstance.id == program_instance_id,
                ProgramInstance.user_id == user_id,
            )
            .with_for_update()
        )

        if instance is None:
            raise NotFoundError("Program enrollment not found.")

        # --------------------------------------------------
        # 2. Handle idempotent retries
        # --------------------------------------------------

        existing = db.scalar(
            select(ProgramAdaptationApproval).where(
                ProgramAdaptationApproval.user_id == user_id,
                ProgramAdaptationApproval.request_key == request_key,
            )
        )

        if existing is not None:
            result = _replay_result(
                db,
                existing,
                instance_id=program_instance_id,
                source_approval_id=source_approval_id,
                selections=selections,
            )
            db.commit()
            return result

        if instance.status != "active":
            raise ConflictError("Program enrollment is not active.")

        # --------------------------------------------------
        # 3. Validate original individual approval
        # --------------------------------------------------

        source_approval = db.scalar(
            select(AdaptationApproval).where(
                AdaptationApproval.id == source_approval_id,
                AdaptationApproval.user_id == user_id,
            )
        )

        if source_approval is None:
            raise NotFoundError("Individual adaptation approval not found.")

        adjustment_type = source_approval.adjustment_type

        if adjustment_type not in TARGET_FIELDS:
            raise ValidationFailed("Unsupported adjustment type.")

        # --------------------------------------------------
        # 4. Lock prescriptions and sets consistently
        # --------------------------------------------------

        prescriptions = db.scalars(
            select(WorkoutPrescription)
            .where(
                WorkoutPrescription.program_instance_id == program_instance_id,
                WorkoutPrescription.user_id == user_id,
                WorkoutPrescription.program_slug == instance.program_slug,
            )
            .order_by(WorkoutPrescription.id)
            .with_for_update()
        ).all()

        prescription_ids = [item.id for item in prescriptions]

        if source_approval.workout_prescription_id not in prescription_ids:
            raise NotFoundError(
                "Source approval belongs to another " "program enrollment."
            )

        if not prescription_ids:
            raise ConflictError("Enrollment has no prescriptions.")

        # Lock every set within this enrollment, including
        # the source set and nonselected future sets.
        locked_sets = db.scalars(
            select(PrescriptionSet)
            .where(PrescriptionSet.workout_prescription_id.in_(prescription_ids))
            .order_by(PrescriptionSet.id)
            .with_for_update()
        ).all()

        sets_by_id = {item.id: item for item in locked_sets}

        # Lock existing phase metadata before revalidation.
        db.scalars(
            select(ProgramPhase)
            .where(ProgramPhase.workout_prescription_id.in_(prescription_ids))
            .order_by(ProgramPhase.id)
            .with_for_update()
        ).all()

        source_set = sets_by_id.get(source_approval.prescription_set_id)

        if (
            source_set is None
            or source_set.workout_prescription_id
            != source_approval.workout_prescription_id
        ):
            raise ConflictError(
                "Source approval no longer matches " "its prescription set."
            )

        # Discard previously cached ORM values so the
        # preview reads the database state after locking.
        db.expire_all()

        # --------------------------------------------------
        # 5. Recompute eligibility and progression
        # --------------------------------------------------

        preview = preview_program_propagation(
            db=db,
            user_id=user_id,
            prescription_id=(source_approval.workout_prescription_id),
            prescription_set_id=(source_approval.prescription_set_id),
            adjustment_type=adjustment_type,
            previous_value=source_approval.previous_value,
            approved_value=source_approval.approved_value,
            program_instance_id=program_instance_id,
        )

        if (
            preview["source_approval_id"] != source_approval_id
            or preview["program_instance_id"] != program_instance_id
        ):
            raise ConflictError(
                "Source approval or enrollment changed. " "Request a new preview."
            )

        candidates = {
            item["prescription_set_id"]: item for item in preview["candidates"]
        }

        # --------------------------------------------------
        # 6. Validate every explicitly selected target
        # --------------------------------------------------

        validated = []

        for selection in sorted(
            selections,
            key=lambda item: item.prescription_set_id,
        ):
            candidate = candidates.get(selection.prescription_set_id)

            if candidate is None:
                raise ConflictError(
                    "A selected set is no longer eligible. "
                    "Refresh the program preview."
                )

            prescribed_set = sets_by_id.get(selection.prescription_set_id)

            if prescribed_set is None:
                raise ConflictError("Selected set is not in this enrollment.")

            if prescribed_set.workout_prescription_id != candidate["prescription_id"]:
                raise ConflictError("Selected set changed prescriptions.")

            if candidate["adjustment_type"] != adjustment_type:
                raise ConflictError("Adjustment type no longer matches.")

            previous = _number(selection.expected_previous_value)
            proposed = _number(selection.expected_proposed_value)

            server_previous = _number(candidate["current_value"])
            server_proposed = _number(candidate["proposed_value"])

            current = getattr(
                prescribed_set,
                TARGET_FIELDS[adjustment_type],
            )

            if (
                current is None
                or previous != server_previous
                or proposed != server_proposed
                or _number(current) != previous
            ):
                raise ConflictError(
                    "Selected target is stale. " "Refresh the program preview."
                )

            validated.append(
                (
                    prescribed_set,
                    candidate["prescription_id"],
                    previous,
                    proposed,
                )
            )

        # --------------------------------------------------
        # 7. Create bulk approval and selected audit items
        # --------------------------------------------------

        bulk_approval = ProgramAdaptationApproval(
            user_id=user_id,
            program_instance_id=program_instance_id,
            source_approval_id=source_approval_id,
            request_key=request_key,
            proposal_engine_version=(source_approval.proposal_engine_version),
        )

        db.add(bulk_approval)
        db.flush()

        updated_sets = []

        for (
            prescribed_set,
            prescription_id,
            previous,
            proposed,
        ) in validated:

            if adjustment_type == "reps":
                prescribed_set.target_reps = int(proposed)

            elif adjustment_type == "duration":
                prescribed_set.target_duration_seconds = int(proposed)

            elif adjustment_type == "weight":
                prescribed_set.target_weight_kg = proposed

            db.add(
                ProgramAdaptationApprovalItem(
                    program_adaptation_approval_id=(bulk_approval.id),
                    workout_prescription_id=prescription_id,
                    prescription_set_id=prescribed_set.id,
                    adjustment_type=adjustment_type,
                    previous_value=previous,
                    approved_value=proposed,
                )
            )

            updated_sets.append(
                {
                    "prescription_set_id": prescribed_set.id,
                    "adjustment_type": adjustment_type,
                    "previous_value": _serialize(
                        adjustment_type,
                        previous,
                    ),
                    "applied_value": _serialize(
                        adjustment_type,
                        proposed,
                    ),
                }
            )

        # --------------------------------------------------
        # 8. Commit all updates and audits atomically
        # --------------------------------------------------

        approval_id = bulk_approval.id

        db.flush()
        db.commit()

        return {
            "program_instance_id": program_instance_id,
            "program_adaptation_approval_id": approval_id,
            "source_approval_id": source_approval_id,
            "status": "updated",
            "updated_set_count": len(updated_sets),
            "updated_sets": updated_sets,
        }

    except Exception:
        db.rollback()
        raise
