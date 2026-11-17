
export type SetStatus = "completed" | "skipped";

export type PerformanceSet = {
  exercise_id: number;
  set_number: number;
  reps: number | null;
  weight_kg?: number | null;
  duration_seconds?: number | null;
  distance_m?: number | null;
  status: SetStatus;
  substituted_for_exercise_id?: number | null;
};

export type WorkoutSubmission = {
  workout_session_id?: number | null;
  program_slug?: string | null;
  program_week?: number | null;
  program_day?: number | null;
  duration_minutes?: number | null;
  entries: PerformanceSet[];
};

export type PrescriptionTarget = {
  exercise_id: number;
  set_number: number;
  target_reps: number | null;
  target_weight_kg: number | null;
  target_duration_seconds: number | null;
};
