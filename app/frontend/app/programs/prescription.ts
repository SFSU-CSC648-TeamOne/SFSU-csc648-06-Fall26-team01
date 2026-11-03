
import type { Program, ScheduledDay } from "./programsData";

export type BaselineResult = {
  exercise_id: string;
  value: number;
  load_kg: number | null;
};

export type ProgramBaseline = {
  id: number;
  program_slug: string;
  attempt_id: string;
  results: BaselineResult[];
  created_at: string;
};

// Related movements share a small adjustment.
// This is NOT an assertion that their strength is identical.
// Hard coded here for now, but could be moved to the backend in the future.
const MOVEMENT_GROUPS: Record<string, Record<string, string[]>> = {
  bw: {
    "push-up": ["push-up", "pike-push-up", "bench-dip"],
    "bodyweight-squat": [
      "bodyweight-squat",
      "reverse-lunge",
      "glute-bridge",
      "burpee",
    ],
    "plank": ["plank"],
  },
  ldw: {
    "barbell-bench-press": [
      "barbell-bench-press",
      "dumbbell-shoulder-press",
      "cable-fly",
      "triceps-pushdown",
    ],
    "barbell-back-squat": [
      "barbell-back-squat",
      "dumbbell-lunge",
    ],
    "romanian-deadlift": [
      "romanian-deadlift",
      "lat-pulldown",
      "dumbbell-row",
      "dumbbell-curl",
    ],
  },
};

const clamp = (value: number, min: number, max: number) =>
  Math.max(min, Math.min(max, value));

function findAnchor(program: Program, exerciseId: string) {
  const groups = MOVEMENT_GROUPS[program.slug] ?? {};

  return Object.keys(groups).find((anchor) =>
    groups[anchor].includes(exerciseId)
  );
}

export function personalizeSchedule(
  program: Program,
  days: ScheduledDay[],
  baseline: ProgramBaseline | null
): ScheduledDay[] {
  if (!baseline || baseline.program_slug !== program.slug) {
    return days;
  }

  const measurements = new Map(
    baseline.results.map((r) => [r.exercise_id, r])
  );

  const firstWeek = program.weekSchemes[0];
  const maxReps = program.slug === "bw" ? 20 : 15;

  return days.map((day) => {
    if (day.rest) return day;

    return {
      ...day,
      exercises: day.exercises.map((item) => {
        const anchor = findAnchor(program, item.exercise.id);
        const test = anchor ? measurements.get(anchor) : undefined;

        if (!test) return item;

        // Plank is recorded in seconds, not repetitions.
        if (item.exercise.id === "plank") {
          const targetSeconds =
            test.value === 0
              ? 0
              : clamp(Math.floor(test.value * 0.5), 5, 120);

          return {
            ...item,
            sets: 2,
            reps: targetSeconds,
          };
        }

        // Use a portion of the measured repetitions as a
        // starting training target.
        const startingReps =
          test.value === 0
            ? 0
            : clamp(Math.floor(test.value * 0.5), 1, maxReps);

        const sets = test.value < 6 ? 2 : item.sets;

        if (item.exercise.id === anchor) {
          const weekRatio = item.reps / firstWeek.reps;

          return {
            ...item,
            sets,
            reps:
              startingReps === 0
                ? 0
                : clamp(
                    Math.round(startingReps * weekRatio),
                    1,
                    maxReps
                  ),
          };
        }

        // Related exercises receive a limited adjustment.
        // We do not equate a bench press score to a cable fly
        // repetition maximum, for example.
        const ratio =
          startingReps === 0
            ? 0.75
            : clamp(startingReps / firstWeek.reps, 0.75, 1.25);

        return {
          ...item,
          sets,
          reps: clamp(
            Math.round(item.reps * ratio),
            1,
            maxReps
          ),
        };
      }),
    };
  });
}
