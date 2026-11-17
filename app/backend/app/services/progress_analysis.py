
"""Exercise performance analysis for the adaptive engine.

This service describes observed performance.
It does not generate or modify prescriptions.
"""

from collections import defaultdict
from itertools import combinations
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import EntryStatus, ObservationType
from app.models.catalog import (Exercise, ExerciseMovementGroup, MovementGroup)
from app.models.prescription import PrescriptionSet
from app.models.tracking import PerformanceEntry, WorkoutRecord


PRELIMINARY_MIN = 3
ROBUST_MIN = 5


def _confidence(count: int) -> str:
    if count >= ROBUST_MIN:
        return "robust"
    if count >= PRELIMINARY_MIN:
        return "preliminary"
    return "insufficient"


def _theil_sen(values: list[float]) -> float:
    """Median pairwise slope per workout observation."""
    slopes = [
        (values[j] - values[i]) / (j - i)
        for i, j in combinations(range(len(values)), 2)
    ]
    return float(median(slopes)) if slopes else 0.0


def _metric(entry: PerformanceEntry):
    """Return the actual measured performance metric."""
    if entry.reps is not None:
        return "reps", float(entry.reps)

    if entry.duration_seconds is not None:
        return "seconds", float(entry.duration_seconds)

    # Distance is stored but not included in Phase 1 trends.
    return None


def _target(prescription: PrescriptionSet | None, metric: str):
    if prescription is None:
        return None

    if metric == "reps":
        return prescription.target_reps

    return prescription.target_duration_seconds


def analyze_exercise_progress(
    db: Session,
    user_id: int,
    exercise_id: int,
    observation_type: str = ObservationType.training.value,
) -> list[dict]:
    """Analyze comparable historical sets for one exercise.

    Comparison groups are separated by:
      - exercise
      - observation type
      - set position
      - repetitions versus duration
      - load basis
      - external/added load
      - assistance amount

    Only one observation per workout per group is counted.
    """

    if observation_type not in {
        ObservationType.training.value,
        ObservationType.benchmark.value,
    }:
        raise ValueError("Unsupported observation type.")

    statement = (
        select(
            PerformanceEntry,
            WorkoutRecord,
            PrescriptionSet,
        )
        .join(
            WorkoutRecord,
            PerformanceEntry.workout_record_id
            == WorkoutRecord.id,
        )
        .outerjoin(
            PrescriptionSet,
            PerformanceEntry.prescription_set_id
            == PrescriptionSet.id,
        )
        .where(
            WorkoutRecord.user_id == user_id,
            PerformanceEntry.exercise_id == exercise_id,
            PerformanceEntry.status == EntryStatus.completed.value,
            PerformanceEntry.observation_type == observation_type,
        )
        .order_by(
            WorkoutRecord.performed_at,
            WorkoutRecord.id,
            PerformanceEntry.id,
        )
    )

    groups = defaultdict(dict)

    for entry, record, prescription in db.execute(statement):
        # A substituted exercise is not directly comparable
        # to the original prescribed movement.
        if entry.substituted_for_exercise_id is not None:
            continue

        if entry.set_number is None:
            continue

        measured = _metric(entry)
        if measured is None:
            continue

        metric, actual = measured

        # A missing load classification is "unknown", not
        # automatically bodyweight.
        load_basis = entry.load_basis or "unknown"

        # Don't mix different external loads or assistance.
        load_kg = (
            round(entry.weight_kg, 2)
            if entry.weight_kg is not None
            else None
        )
        assistance_kg = (
            round(entry.assistance_kg, 2)
            if entry.assistance_kg is not None
            else None
        )

        key = (
            entry.set_number,
            metric,
            load_basis,
            load_kg,
            assistance_kg,
        )

        # Deduplicate within each workout record.
        # The query's ordering retains the latest entry
        # for an equivalent set position.
        groups[key][record.id] = {
            "date": record.performed_at.isoformat(),
            "record_id": record.id,
            "prescribed": _target(prescription, metric),
            "actual": actual,
        }

    result = []

    for key, observations_by_record in groups.items():
        (
            set_number,
            metric,
            load_basis,
            load_kg,
            assistance_kg,
        ) = key

        points = sorted(
            observations_by_record.values(),
            key=lambda point: (
                point["date"],
                point["record_id"],
            ),
        )

        count = len(points)
        confidence = _confidence(count)
        values = [point["actual"] for point in points]

        change_pct = None
        slope = None

        if count >= PRELIMINARY_MIN:
            first = values[0]

            if count >= ROBUST_MIN:
                slope = _theil_sen(values)

                # Estimate relative trend across the observed
                # number of workout sessions.
                if first > 0:
                    change_pct = round(
                        (slope * (count - 1) / first) * 100,
                        2,
                    )
            elif first > 0:
                change_pct = round(
                    ((values[-1] - first) / first) * 100,
                    2,
                )

        result.append(
            {
                "exercise_id": exercise_id,
                "observation_type": observation_type,
                "set_number": set_number,
                "metric": metric,
                "load_basis": load_basis,
                "weight_kg": load_kg,
                "assistance_kg": assistance_kg,
                "observation_count": count,
                "confidence": confidence,
                "change_pct": change_pct,
                "slope_per_observation": slope,
                "points": [
                    {
                        "date": point["date"],
                        "prescribed": point["prescribed"],
                        "actual": point["actual"],
                    }
                    for point in points
                ],
            }
        )

    return sorted(
        result,
        key=lambda item: (
            item["set_number"],
            item["metric"],
            item["load_basis"],
            item["weight_kg"]
            if item["weight_kg"] is not None
            else -1,
            item["assistance_kg"]
            if item["assistance_kg"] is not None
            else -1,
        ),
    )

# Creates a relevance-weighted percentage to determine progress in a movement group.
# Exercises are given a relevance weight which are totally not based on science and 
# and could be adjusted much later. But much of effective training is bro science anyway sooo...
def analyze_movement_group_progress(
    db: Session,
    user_id: int,
) -> list[dict]:
    """
    Summarize exercise trends by primary movement group.

    Only comparable exercise trends with at least three
    observations contribute to percentage calculations.

    Each exercise contributes at most one trend series.
    """

    statement = (
        select(
            MovementGroup,
            ExerciseMovementGroup,
            Exercise,
        )
        .join(
            ExerciseMovementGroup,
            ExerciseMovementGroup.movement_group_id
            == MovementGroup.id,
        )
        .join(
            Exercise,
            Exercise.id
            == ExerciseMovementGroup.exercise_id,
        )
        .where(
            ExerciseMovementGroup.relationship_type
            == "primary",
            ExerciseMovementGroup.relevance_weight > 0,
        )
        .order_by(
            MovementGroup.name,
            Exercise.id,
        )
    )

    rows = db.execute(statement).all()

    # Cache analysis results because an exercise could
    # belong to multiple movement groups.
    exercise_cache = {}
    groups = {}

    for group, relationship, exercise in rows:
        if exercise.id not in exercise_cache:
            exercise_cache[exercise.id] = (
                analyze_exercise_progress(
                    db=db,
                    user_id=user_id,
                    exercise_id=exercise.id,
                    observation_type="training",
                )
            )

        trends = exercise_cache[exercise.id]

        # Select one comparable series per exercise.
        # Prioritize the series with the most observations,
        # breaking ties by set position.
        eligible = [
            trend
            for trend in trends
            if (
                trend["observation_count"] >= PRELIMINARY_MIN
                and trend["change_pct"] is not None
            )
        ]

        if not eligible:
            continue

        selected = sorted(
            eligible,
            key=lambda trend: (
                -trend["observation_count"],
                trend["set_number"],
                trend["metric"],
                trend["load_basis"],
            ),
        )[0]

        bucket = groups.setdefault(
            group.id,
            {
                "id": group.id,
                "name": group.name,
                "contributions": [],
            },
        )

        bucket["contributions"].append(
            {
                "exercise_id": exercise.id,
                "exercise_name": exercise.name,
                "change_pct": selected["change_pct"],
                "observation_count": selected[
                    "observation_count"
                ],
                "confidence": selected["confidence"],
                "weight": float(
                    relationship.relevance_weight
                ),
            }
        )

    results = []

    for bucket in groups.values():
        contributions = bucket["contributions"]

        total_weight = sum(
            item["weight"]
            for item in contributions
        )

        if total_weight <= 0:
            continue

        # Percentages are dimensionless, allowing
        # exercise-specific changes to be summarized
        # without combining raw reps, seconds, or kg.
        change_pct = sum(
            item["change_pct"] * item["weight"]
            for item in contributions
        ) / total_weight

        observation_count = sum(
            item["observation_count"]
            for item in contributions
        )

        # Conservative confidence:
        # every contributing exercise must have robust
        # evidence before the group is called robust.
        robust = all(
            item["confidence"] == "robust"
            for item in contributions
        )

        confidence = (
            "robust" if robust else "preliminary"
        )

        results.append(
            {
                "id": bucket["id"],
                "name": bucket["name"],
                "change_pct": round(change_pct, 2),
                "exercise_count": len(contributions),
                "observation_count": observation_count,
                "confidence": confidence,
                "explanation": (
                    "Relevance-weighted average of "
                    "exercise-specific performance changes. "
                    "Only primary movement relationships "
                    "with at least three comparable "
                    "observations per exercise are included."
                ),
            }
        )

    return sorted(
        results,
        key=lambda item: item["name"],
    )
