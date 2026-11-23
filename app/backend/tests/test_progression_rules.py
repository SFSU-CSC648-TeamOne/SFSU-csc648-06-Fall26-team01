"""Unit tests for adaptive progression rules.

Run:
    python -m pytest tests/test_progression_rules.py -v

These tests do not require a database.
"""

from decimal import Decimal

import pytest

from app.services.progression_rules import (
    ProgressionTarget,
    propose_progression,
)


def make_decision(
    *,
    action="progress",
    confidence="robust",
    observation_count=5,
    exercise_id=101,
    set_number=1,
):
    return {
        "exercise_id": exercise_id,
        "set_number": set_number,
        "action": action,
        "confidence": confidence,
        "observation_count": observation_count,
        "change_pct": 10.0,
        "reason": "Test decision.",
    }


def make_target(
    *,
    exercise_id=101,
    set_number=1,
    load_basis="bodyweight",
    reps=None,
    duration=None,
    weight=None,
    assistance=None,
):
    return ProgressionTarget(
        exercise_id=exercise_id,
        set_number=set_number,
        load_basis=load_basis,
        target_reps=reps,
        target_duration_seconds=duration,
        target_weight_kg=(Decimal(str(weight)) if weight is not None else None),
        target_assistance_kg=(
            Decimal(str(assistance)) if assistance is not None else None
        ),
    )


# --------------------------------------------------
# Repetition progression
# --------------------------------------------------


def test_bodyweight_reps_increase_by_one():
    proposal = propose_progression(
        make_decision(),
        make_target(reps=15),
    )

    assert proposal.adjustment_type == "reps"
    assert proposal.previous_value == 15
    assert proposal.proposed_value == 16
    assert proposal.requires_approval is True


def test_bodyweight_reps_take_priority_over_duration():
    proposal = propose_progression(
        make_decision(),
        make_target(reps=10, duration=60),
    )

    assert proposal.adjustment_type == "reps"
    assert proposal.proposed_value == 11


@pytest.mark.parametrize("reps", [0, -1])
def test_invalid_reps_do_not_progress(reps):
    proposal = propose_progression(
        make_decision(),
        make_target(reps=reps),
    )

    assert proposal.adjustment_type == "none"
    assert proposal.requires_approval is False


# --------------------------------------------------
# Duration progression
# --------------------------------------------------


def test_duration_increases_by_five_seconds():
    proposal = propose_progression(
        make_decision(),
        make_target(duration=120),
    )

    assert proposal.adjustment_type == "duration"
    assert proposal.previous_value == 120
    assert proposal.proposed_value == 125


def test_duration_respects_five_percent_cap():
    proposal = propose_progression(
        make_decision(),
        make_target(duration=60),
    )

    assert proposal.proposed_value == 63


def test_short_duration_without_safe_increment():
    proposal = propose_progression(
        make_decision(),
        make_target(duration=10),
    )

    assert proposal.adjustment_type == "none"


def test_invalid_duration_does_not_progress():
    proposal = propose_progression(
        make_decision(),
        make_target(duration=0),
    )

    assert proposal.adjustment_type == "none"


# --------------------------------------------------
# Resistance progression
# --------------------------------------------------


def test_external_weight_increases_by_2_5_percent():
    proposal = propose_progression(
        make_decision(),
        make_target(
            load_basis="external",
            weight="60",
        ),
    )

    assert proposal.adjustment_type == "weight"
    assert proposal.previous_value == Decimal("60")
    assert proposal.proposed_value == Decimal("61.50")


def test_weight_increase_capped_at_2_5_kg():
    proposal = propose_progression(
        make_decision(),
        make_target(
            load_basis="external",
            weight="200",
        ),
    )

    assert proposal.proposed_value == Decimal("202.50")


def test_added_load_uses_weight_progression():
    proposal = propose_progression(
        make_decision(),
        make_target(
            load_basis="added",
            weight="20",
        ),
    )

    assert proposal.adjustment_type == "weight"
    assert proposal.proposed_value == Decimal("20.50")


@pytest.mark.parametrize(
    "weight",
    [
        None,
        "0",
        "-10",
    ],
)
def test_invalid_weight_does_not_progress(weight):
    proposal = propose_progression(
        make_decision(),
        make_target(
            load_basis="external",
            weight=weight,
        ),
    )

    assert proposal.adjustment_type == "none"


# --------------------------------------------------
# Assistance progression
# --------------------------------------------------


def test_assistance_decreases_by_five_percent():
    proposal = propose_progression(
        make_decision(),
        make_target(
            load_basis="assisted",
            assistance="20",
        ),
    )

    assert proposal.adjustment_type == "assistance"
    assert proposal.previous_value == Decimal("20")
    assert proposal.proposed_value == Decimal("19.00")


def test_assistance_reduction_capped():
    proposal = propose_progression(
        make_decision(),
        make_target(
            load_basis="assisted",
            assistance="100",
        ),
    )

    assert proposal.proposed_value == Decimal("97.50")


def test_missing_assistance_target():
    proposal = propose_progression(
        make_decision(),
        make_target(
            load_basis="assisted",
        ),
    )

    assert proposal.adjustment_type == "none"


def test_zero_assistance_does_not_progress():
    proposal = propose_progression(
        make_decision(),
        make_target(
            load_basis="assisted",
            assistance="0",
        ),
    )

    assert proposal.adjustment_type == "none"


# --------------------------------------------------
# Decision safeguards
# --------------------------------------------------


@pytest.mark.parametrize(
    "action",
    [
        "maintain",
        "review_regression",
        "insufficient_data",
        "reassess",
    ],
)
def test_non_progress_decisions_do_not_adjust(action):
    proposal = propose_progression(
        make_decision(action=action),
        make_target(reps=15),
    )

    assert proposal.adjustment_type == "none"
    assert proposal.requires_approval is False


@pytest.mark.parametrize(
    "confidence",
    [
        "insufficient",
        "preliminary",
    ],
)
def test_non_robust_evidence_blocks_progression(
    confidence,
):
    proposal = propose_progression(
        make_decision(confidence=confidence),
        make_target(reps=15),
    )

    assert proposal.adjustment_type == "none"


def test_fewer_than_five_observations_blocks_progression():
    proposal = propose_progression(
        make_decision(observation_count=4),
        make_target(reps=15),
    )

    assert proposal.adjustment_type == "none"


def test_mismatched_exercise_rejected():
    with pytest.raises(ValueError):
        propose_progression(
            make_decision(exercise_id=101),
            make_target(exercise_id=202, reps=15),
        )


def test_mismatched_set_rejected():
    with pytest.raises(ValueError):
        propose_progression(
            make_decision(set_number=1),
            make_target(set_number=2, reps=15),
        )


def test_unknown_loading_does_not_progress():
    proposal = propose_progression(
        make_decision(),
        make_target(
            load_basis="unknown",
            reps=15,
        ),
    )

    assert proposal.adjustment_type == "none"


def test_none_loading_does_not_progress():
    proposal = propose_progression(
        make_decision(),
        make_target(
            load_basis="none",
            reps=15,
        ),
    )

    assert proposal.adjustment_type == "none"


# --------------------------------------------------
# Proposal integrity
# --------------------------------------------------


def test_proposal_preserves_exercise_and_set():
    proposal = propose_progression(
        make_decision(exercise_id=101, set_number=2),
        make_target(
            exercise_id=101,
            set_number=2,
            reps=15,
        ),
    )

    assert proposal.exercise_id == 101
    assert proposal.set_number == 2


def test_proposal_contains_explanation():
    proposal = propose_progression(
        make_decision(),
        make_target(reps=15),
    )

    assert isinstance(proposal.reason, str)
    assert len(proposal.reason) > 0


def test_proposal_does_not_modify_target():
    target = make_target(reps=15)

    propose_progression(
        make_decision(),
        target,
    )

    assert target.target_reps == 15


def test_all_actual_adjustments_require_approval():
    targets = [
        make_target(reps=15),
        make_target(duration=120),
        make_target(load_basis="external", weight="60"),
        make_target(load_basis="assisted", assistance="20"),
    ]

    for target in targets:
        proposal = propose_progression(
            make_decision(),
            target,
        )

        assert proposal.adjustment_type != "none"
        assert proposal.requires_approval is True
