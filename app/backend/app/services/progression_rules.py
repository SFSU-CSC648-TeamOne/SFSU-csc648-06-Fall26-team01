"""Conservative progression rules for adaptive training.

Transforms an adaptation decision and a prescribed set into
a proposed adjustment.

Does not read or modify the database.

Initial progression policy:
- Bodyweight: increase repetitions or duration.
- External / added resistance: increase weight cautiously.
- Assisted: reduce assistance only when its current target
  is explicitly supplied.
- Unknown loading: do not generate an adjustment.

All adjustments are proposals requiring approval.
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

from app.models.enums import LoadBasis
from app.services.adaptive_engine import AdaptationDecision

AdjustmentType = Literal[
    "reps",
    "duration",
    "weight",
    "assistance",
    "none",
]


# Initial product heuristics, not validated training standards.
REP_INCREMENT = 1

DURATION_INCREMENT_SECONDS = 5
MAX_DURATION_INCREASE_PCT = Decimal("0.05")

MAX_WEIGHT_INCREASE_PCT = Decimal("0.025")
MAX_WEIGHT_INCREASE_KG = Decimal("2.5")

MAX_ASSISTANCE_REDUCTION_PCT = Decimal("0.05")
MAX_ASSISTANCE_REDUCTION_KG = Decimal("2.5")

WEIGHT_PRECISION = Decimal("0.01")


@dataclass(frozen=True)
class ProgressionTarget:
    """Current prescription values.

    Assistance is optional because the current PrescriptionSet
    model does not store a target_assistance_kg column.
    """

    exercise_id: int
    set_number: int
    load_basis: str

    target_reps: int | None = None
    target_duration_seconds: int | None = None
    target_weight_kg: Decimal | None = None

    target_assistance_kg: Decimal | None = None


@dataclass(frozen=True)
class ProgressionProposal:
    exercise_id: int
    set_number: int

    adjustment_type: AdjustmentType

    previous_value: int | Decimal | None
    proposed_value: int | Decimal | None

    requires_approval: bool
    reason: str


def _no_adjustment(
    target: ProgressionTarget,
    reason: str,
) -> ProgressionProposal:
    return ProgressionProposal(
        exercise_id=target.exercise_id,
        set_number=target.set_number,
        adjustment_type="none",
        previous_value=None,
        proposed_value=None,
        requires_approval=False,
        reason=reason,
    )


def _proposal(
    target: ProgressionTarget,
    adjustment_type: AdjustmentType,
    previous_value: int | Decimal,
    proposed_value: int | Decimal,
    reason: str,
) -> ProgressionProposal:
    return ProgressionProposal(
        exercise_id=target.exercise_id,
        set_number=target.set_number,
        adjustment_type=adjustment_type,
        previous_value=previous_value,
        proposed_value=proposed_value,
        requires_approval=True,
        reason=reason,
    )


def _decimal(value: Decimal | int | float | str) -> Decimal:
    """Convert numerical input without float precision artifacts."""
    return Decimal(str(value))


def _round_weight(value: Decimal) -> Decimal:
    return value.quantize(
        WEIGHT_PRECISION,
        rounding=ROUND_HALF_UP,
    )


def propose_progression(
    decision: AdaptationDecision,
    target: ProgressionTarget,
) -> ProgressionProposal:
    """Generate one conservative progression proposal.

    A proposal is produced only when the decision engine
    explicitly recommends progression with robust evidence.

    For loaded exercises, adjust weight rather than reps.
    For bodyweight exercises, adjust reps or duration.
    """

    if (
        decision["exercise_id"] != target.exercise_id
        or decision["set_number"] != target.set_number
    ):
        raise ValueError(
            "Adaptation decision and prescription target "
            "must refer to the same exercise and set."
        )

    if (
        decision["action"] != "progress"
        or decision["confidence"] != "robust"
        or decision["observation_count"] < 5
    ):
        return _no_adjustment(
            target,
            "No approved progression recommendation " "with sufficient evidence.",
        )

    basis = target.load_basis

    if basis == LoadBasis.bodyweight.value:
        if target.target_reps is not None and target.target_reps > 0:
            return _proposal(
                target,
                "reps",
                target.target_reps,
                target.target_reps + REP_INCREMENT,
                "Increase the bodyweight repetition target " "by one repetition.",
            )

        if (
            target.target_duration_seconds is not None
            and target.target_duration_seconds > 0
        ):
            current = target.target_duration_seconds

            # Never exceed a 5% increase. A minimum
            # whole-second increment is required.
            increase = min(
                DURATION_INCREMENT_SECONDS,
                int(_decimal(current) * MAX_DURATION_INCREASE_PCT),
            )

            if increase < 1:
                return _no_adjustment(
                    target,
                    "Duration is too short for a whole-second "
                    "increase within the current safety cap.",
                )

            return _proposal(
                target,
                "duration",
                current,
                current + increase,
                "Increase duration conservatively, " "without exceeding the 5% cap.",
            )

        return _no_adjustment(
            target,
            "No valid bodyweight repetition or duration " "target is available.",
        )

    if basis in {
        LoadBasis.external.value,
        LoadBasis.added.value,
    }:
        if target.target_weight_kg is None or target.target_weight_kg <= 0:
            return _no_adjustment(
                target,
                "A positive prescribed resistance is "
                "required before increasing weight.",
            )

        current = _decimal(target.target_weight_kg)

        increase = min(
            current * MAX_WEIGHT_INCREASE_PCT,
            MAX_WEIGHT_INCREASE_KG,
        )

        proposed = _round_weight(current + increase)

        if proposed <= current:
            return _no_adjustment(
                target,
                "The calculated increase is too small " "at the supported precision.",
            )

        return _proposal(
            target,
            "weight",
            current,
            proposed,
            "Increase prescribed resistance by no more "
            "than 2.5%, capped at 2.5 kg. Equipment "
            "availability must be checked before applying.",
        )

    if basis == LoadBasis.assisted.value:
        if target.target_assistance_kg is None:
            return _no_adjustment(
                target,
                "Assistance progression requires an explicit "
                "current assistance target. It cannot be "
                "inferred from the logged measurement.",
            )

        current = _decimal(target.target_assistance_kg)

        if current <= 0:
            return _no_adjustment(
                target,
                "No positive assistance remains to reduce.",
            )

        reduction = min(
            current * MAX_ASSISTANCE_REDUCTION_PCT,
            MAX_ASSISTANCE_REDUCTION_KG,
        )

        proposed = _round_weight(max(Decimal("0"), current - reduction))

        if proposed >= current:
            return _no_adjustment(
                target,
                "The assistance reduction is too small " "at the supported precision.",
            )

        return _proposal(
            target,
            "assistance",
            current,
            proposed,
            "Reduce assistance conservatively. "
            "This is a proposal only; the current "
            "PrescriptionSet schema does not yet store "
            "assistance targets.",
        )

    return _no_adjustment(
        target,
        "Unsupported or unspecified loading basis. "
        "Maintain the existing prescription.",
    )
