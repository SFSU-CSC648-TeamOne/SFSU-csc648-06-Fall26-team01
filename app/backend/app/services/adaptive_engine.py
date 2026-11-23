"""Conservative adaptive training decision engine.

Consumes exercise-progress analysis results and produces
recommendations. Does not modify prescriptions.
"""

from typing import Literal, TypedDict

from sqlalchemy.orm import Session

from app.services.progress_analysis import (
    analyze_exercise_progress,
)

Action = Literal[
    "insufficient_data",
    "maintain",
    "progress",
    "review_regression",
    "reassess",
]


class AdaptationDecision(TypedDict):
    exercise_id: int
    set_number: int
    action: Action
    confidence: str
    observation_count: int
    change_pct: float | None
    reason: str


# Initial policy constants. These are product heuristics,
# not scientifically validated progression thresholds.
PROGRESS_THRESHOLD_PCT = 5.0
REGRESSION_THRESHOLD_PCT = -5.0


def decide_adaptation(trend: dict) -> AdaptationDecision:
    """Evaluate one comparable exercise-performance series."""

    exercise_id = trend["exercise_id"]
    set_number = trend["set_number"]
    confidence = trend["confidence"]
    count = trend["observation_count"]
    change = trend["change_pct"]
    points = trend["points"]

    def result(
        action: Action,
        reason: str,
    ) -> AdaptationDecision:
        return {
            "exercise_id": exercise_id,
            "set_number": set_number,
            "action": action,
            "confidence": confidence,
            "observation_count": count,
            "change_pct": change,
            "reason": reason,
        }

    # Insufficient evidence never triggers adaptation.
    if confidence == "insufficient" or count < 3:
        return result(
            "insufficient_data",
            "At least three comparable observations are required.",
        )

    # Missing or undefined trend cannot guide changes.
    if change is None:
        return result(
            "maintain",
            "Trend cannot be calculated reliably.",
        )

    # Preliminary trends are informational only.
    if confidence == "preliminary":
        return result(
            "maintain",
            "Preliminary trend detected. Maintain the current "
            "prescription until at least five comparable "
            "observations are available.",
        )

    # A robust trend must have at least five observations.
    if confidence != "robust" or count < 5:
        return result(
            "maintain",
            "Evidence is not sufficient for a robust decision.",
        )

    # Prescribed targets, where available, provide useful
    # context for assessing whether training is manageable.
    recent = points[-3:]

    known_targets = [point for point in recent if point["prescribed"] is not None]

    # Only compare actual and prescribed values when
    # every recent observation has a known target.
    targets_met = len(known_targets) == len(recent) and all(
        point["actual"] >= point["prescribed"] for point in recent
    )

    if change >= PROGRESS_THRESHOLD_PCT:
        if targets_met:
            return result(
                "progress",
                "Robust positive trend and the last three "
                "comparable prescribed targets were achieved.",
            )

        return result(
            "maintain",
            "Performance is improving, but recent target "
            "achievement is not established.",
        )

    if change <= REGRESSION_THRESHOLD_PCT:
        return result(
            "review_regression",
            "Robust negative trend detected. Review recovery, "
            "exercise difficulty, technique, and training "
            "conditions before reducing the prescription.",
        )

    return result(
        "maintain",
        "Performance is relatively stable within the " "current comparison conditions.",
    )


def recommend_exercise_adaptations(
    db: Session,
    user_id: int,
    exercise_id: int,
) -> list[AdaptationDecision]:
    """Generate decisions from the user's training history."""

    trends = analyze_exercise_progress(
        db=db,
        user_id=user_id,
        exercise_id=exercise_id,
        observation_type="training",
    )

    return [decide_adaptation(trend) for trend in trends]
