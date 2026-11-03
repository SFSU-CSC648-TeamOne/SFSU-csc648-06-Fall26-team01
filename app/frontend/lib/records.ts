// Shapes of GET /api/workout-records (Page of summaries, no entries) and GET /api/workout-records/{id} (with entries).
export type Page<T> = { items: T[]; total: number; limit: number; offset: number };

export type RecordSummary = {
  id: number;
  workout_session_id: number | null;
  session_name: string | null;
  performed_at: string;
  available_minutes: number | null;
  duration_minutes: number | null;
  entry_count: number;
};
export type RecordEntry = { id: number; exercise_id: number; exercise_name: string; reps: number | null; weight_kg: number | null; status: string };
export type RecordDetail = RecordSummary & { notes: string | null; entries: RecordEntry[] };

export const fmtDate = (iso: string) =>
  new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }).toUpperCase();

/** Total kg lifted (reps x weight) over the entries that were completed. */
export const volume = (r: RecordDetail) =>
  r.entries.reduce((sum, e) => sum + (e.status === "skipped" ? 0 : (e.reps ?? 0) * (e.weight_kg ?? 0)), 0);
