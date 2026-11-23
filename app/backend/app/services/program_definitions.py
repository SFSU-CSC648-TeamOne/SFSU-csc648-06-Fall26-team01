"""Backend definitions for Ascenda's BW and LDW programs.

Source: existing frontend programsData.ts templates.

These definitions preserve workout organization and
weekly set/rep schemes without assigning database IDs,
training phases, or personalized loading targets.

In other words: Frontend catalog IDs need to be verified
against the backend DB.
This is also subject to be updated with our excel sheet
of demonstrated exercises. So exercise content is due
to be changed later.

No database writes occur in this module.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProgramExercise:
    slug: str
    role: str  # "core" or "accessory"


@dataclass(frozen=True)
class ProgramDay:
    title: str
    exercises: tuple[ProgramExercise, ...]


@dataclass(frozen=True)
class WeekScheme:
    sets: int
    reps: int


@dataclass(frozen=True)
class ProgramDefinition:
    slug: str
    name: str
    weeks: tuple[WeekScheme, ...]
    days: tuple[ProgramDay, ...]

    @property
    def week_count(self) -> int:
        return len(self.weeks)

    @property
    def workout_days_per_week(self) -> int:
        return len(self.days)


def core(*slugs: str) -> tuple[ProgramExercise, ...]:
    return tuple(ProgramExercise(slug, "core") for slug in slugs)


def accessory(*slugs: str) -> tuple[ProgramExercise, ...]:
    return tuple(ProgramExercise(slug, "accessory") for slug in slugs)


BODYWEIGHT = ProgramDefinition(
    slug="bw",
    name="Body-Weight Program",
    weeks=(
        WeekScheme(3, 10),
        WeekScheme(3, 12),
        WeekScheme(4, 10),
        WeekScheme(4, 12),
    ),
    days=(
        ProgramDay(
            "Upper Body Push",
            core("push-up", "pike-push-up", "bench-dip")
            + accessory("plank", "mountain-climbers"),
        ),
        ProgramDay(
            "Lower Body",
            core(
                "bodyweight-squat",
                "reverse-lunge",
                "glute-bridge",
            )
            + accessory("burpee", "plank"),
        ),
        ProgramDay(
            "Core and Back",
            core("plank", "bird-dog", "glute-bridge")
            + accessory(
                "mountain-climbers",
                "bodyweight-squat",
            ),
        ),
        ProgramDay(
            "Full Body",
            core(
                "burpee",
                "push-up",
                "bodyweight-squat",
            )
            + accessory(
                "reverse-lunge",
                "bird-dog",
                "bench-dip",
            ),
        ),
        ProgramDay(
            "Conditioning",
            core(
                "mountain-climbers",
                "burpee",
                "pike-push-up",
            )
            + accessory(
                "bodyweight-squat",
                "plank",
                "glute-bridge",
            ),
        ),
    ),
)


LOADED = ProgramDefinition(
    slug="ldw",
    name="Loaded / Weights Program",
    weeks=(
        WeekScheme(3, 10),
        WeekScheme(3, 8),
        WeekScheme(4, 8),
        WeekScheme(4, 6),
    ),
    days=(
        ProgramDay(
            "Push",
            core(
                "barbell-bench-press",
                "dumbbell-shoulder-press",
            )
            + accessory(
                "cable-fly",
                "triceps-pushdown",
            ),
        ),
        ProgramDay(
            "Pull",
            core(
                "lat-pulldown",
                "dumbbell-row",
            )
            + accessory(
                "romanian-deadlift",
                "dumbbell-curl",
            ),
        ),
        ProgramDay(
            "Legs",
            core(
                "barbell-back-squat",
                "romanian-deadlift",
                "dumbbell-lunge",
            )
            + accessory("dumbbell-curl"),
        ),
        ProgramDay(
            "Upper Body",
            core(
                "barbell-bench-press",
                "lat-pulldown",
            )
            + accessory(
                "dumbbell-shoulder-press",
                "dumbbell-curl",
                "triceps-pushdown",
            ),
        ),
        ProgramDay(
            "Lower and Pull",
            core(
                "barbell-back-squat",
                "dumbbell-lunge",
                "dumbbell-row",
            )
            + accessory(
                "romanian-deadlift",
                "cable-fly",
            ),
        ),
    ),
)


PROGRAM_DEFINITIONS: dict[str, ProgramDefinition] = {
    BODYWEIGHT.slug: BODYWEIGHT,
    LOADED.slug: LOADED,
}


def get_program_definition(
    slug: str,
) -> ProgramDefinition | None:
    """Return a supported program definition."""
    return PROGRAM_DEFINITIONS.get(slug)


def required_exercise_slugs(
    program: ProgramDefinition,
) -> frozenset[str]:
    """Return exercise identifiers requiring DB resolution."""
    return frozenset(
        exercise.slug for day in program.days for exercise in day.exercises
    )
