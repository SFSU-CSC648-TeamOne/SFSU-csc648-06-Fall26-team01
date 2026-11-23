"""Read-only workout prescription adaptation service.

Connects exercise-performance analysis, adaptation decisions,
and progression rules.

Does not insert, update, or delete database records.
"""

from dataclasses import asdict
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.prescription import (
    PrescriptionSet,
    WorkoutPrescription,
)
from app.models.enums import PrescriptionStatus
from app.services.adaptive_engine import decide_adaptation
from app.services.progress_analysis import analyze_exercise_progress
from app.services.progression_rules import (
    ProgressionTarget,
    propose_progression,
)

ENGINE_VERSION = "adaptive-v1-proposal"


def _matches_prescription(
    trend: dict,
    prescribed_set: PrescriptionSet,
) -> bool:
    """Check whether a trend measures comparable conditions."""

    if trend["exercise_id"] != prescribed_set.exercise_id:
        return False

    if trend["set_number"] != prescribed_set.set_number:
        return False

    if trend["load_basis"] != prescribed_set.load_basis:
        return False

    # Avoid matching repetition data to duration targets.
    if prescribed_set.target_reps is not None:
        if trend["metric"] != "reps":
            return False
    elif prescribed_set.target_duration_seconds is not None:
        if trend["metric"] != "seconds":
            return False
    else:
        return False

    # Match the actual resistance used in observations
    # to the resistance in the current prescription.
    if prescribed_set.load_basis in {"external", "added"}:
        if prescribed_set.target_weight_kg is None:
            return False

        if trend["weight_kg"] is None:
            return False

        observed = Decimal(str(trend["weight_kg"]))
        prescribed = Decimal(str(prescribed_set.target_weight_kg))

        if observed != prescribed:
            return False

    # Do not treat observations involving added load
    # or assistance as unweighted bodyweight observations.
    elif prescribed_set.load_basis == "bodyweight":
        if trend["weight_kg"] is not None or trend["assistance_kg"] is not None:
            return False

    else:
        # Assisted prescriptions cannot currently be
        # matched to a stored assistance target.
        # Unknown/none loading is also not comparable.
        return False

    return True


def _select_trend(
    trends: list[dict],
    prescribed_set: PrescriptionSet,
) -> dict | None:
    """Select the strongest comparable observation series."""

    comparable = [
        trend for trend in trends if _matches_prescription(trend, prescribed_set)
    ]

    if not comparable:
        return None

    # Most observations first; prefer robust evidence
    # when observation counts are equal.
    comparable.sort(
        key=lambda trend: (
            -trend["observation_count"],
            0 if trend["confidence"] == "robust" else 1,
        )
    )

    return comparable[0]


def _target_from_set(
    prescribed_set: PrescriptionSet,
) -> ProgressionTarget:
    return ProgressionTarget(
        exercise_id=prescribed_set.exercise_id,
        set_number=prescribed_set.set_number,
        load_basis=prescribed_set.load_basis,
        target_reps=prescribed_set.target_reps,
        target_duration_seconds=(prescribed_set.target_duration_seconds),
        target_weight_kg=prescribed_set.target_weight_kg,
    )


def _no_history_result(
    prescribed_set: PrescriptionSet,
) -> dict:
    """Return an explicit result when comparison is unavailable."""

    return {
        "prescription_set_id": prescribed_set.id,
        "exercise_id": prescribed_set.exercise_id,
        "set_number": prescribed_set.set_number,
        "decision": {
            "action": "insufficient_data",
            "confidence": "insufficient",
            "observation_count": 0,
            "change_pct": None,
            "reason": (
                "No comparable training history exists "
                "for this exercise, set, and load."
            ),
        },
        "proposal": {
            "adjustment_type": "none",
            "previous_value": None,
            "proposed_value": None,
            "requires_approval": False,
            "reason": "Maintain the existing prescription.",
        },
    }


def analyze_prescription_adaptations(
    db: Session,
    user_id: int,
    prescription_id: int,
) -> dict[str, Any]:
    """Generate proposals for one user's planned workout.

    Returns:
        Prescription metadata and one result per prescribed set.

    Raises:
        LookupError: Prescription does not exist or belongs
                     to another user.
        ValueError: Prescription is not in planned status.
    """

    statement = (
        select(WorkoutPrescription)
        .options(selectinload(WorkoutPrescription.sets))
        .where(
            WorkoutPrescription.id == prescription_id,
            WorkoutPrescription.user_id == user_id,
        )
    )

    prescription = db.scalar(statement)

    if prescription is None:
        raise LookupError("Workout prescription not found.")

    if prescription.status != PrescriptionStatus.planned.value:
        raise ValueError(
            "Only planned prescriptions can receive " "adaptation proposals."
        )

    # Avoid reanalyzing the same exercise for each set.
    exercise_cache: dict[int, list[dict]] = {}

    results = []

    for prescribed_set in prescription.sets:
        exercise_id = prescribed_set.exercise_id

        if exercise_id not in exercise_cache:
            exercise_cache[exercise_id] = analyze_exercise_progress(
                db=db,
                user_id=user_id,
                exercise_id=exercise_id,
                observation_type="training",
            )

        trends = exercise_cache[exercise_id]

        trend = _select_trend(
            trends,
            prescribed_set,
        )

        if trend is None:
            results.append(_no_history_result(prescribed_set))
            continue

        decision = decide_adaptation(trend)

        # The historical trend provides the decision.
        # The current prescription provides the target
        # on which the proposed adjustment is calculated.
        target = _target_from_set(prescribed_set)

        proposal = propose_progression(
            decision=decision,
            target=target,
        )

        decision_data = {
            "action": decision["action"],
            "confidence": decision["confidence"],
            "observation_count": decision["observation_count"],
            "change_pct": decision["change_pct"],
            "reason": decision["reason"],
        }

        proposal_data = asdict(proposal)

        # A proposal may contain Decimal values.
        # Convert these to JSON-compatible numbers
        # while retaining the original calculation.
        for field in ("previous_value", "proposed_value"):
            value = proposal_data[field]

            if isinstance(value, Decimal):
                proposal_data[field] = float(value)

        results.append(
            {
                "prescription_set_id": prescribed_set.id,
                "exercise_id": exercise_id,
                "set_number": prescribed_set.set_number,
                "decision": decision_data,
                "proposal": {
                    "adjustment_type": proposal_data["adjustment_type"],
                    "previous_value": proposal_data["previous_value"],
                    "proposed_value": proposal_data["proposed_value"],
                    "requires_approval": proposal_data["requires_approval"],
                    "reason": proposal_data["reason"],
                },
            }
        )

    return {
        "prescription_id": prescription.id,
        "user_id": prescription.user_id,
        "program_slug": prescription.program_slug,
        "program_week": prescription.program_week,
        "program_day": prescription.program_day,
        "source_engine_version": prescription.engine_version,
        "proposal_engine_version": ENGINE_VERSION,
        "status": "proposed",
        "sets": results,
    }
