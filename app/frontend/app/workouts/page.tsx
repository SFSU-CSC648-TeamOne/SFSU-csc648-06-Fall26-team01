"use client";

// Bare-bones page: asks the backend for workouts built from wger data and prints them.
// No styling, no extra files. Calls /api/... (next.config.ts forwards it to FastAPI).

import { useEffect, useState } from "react";

type Named = { id: number; name: string };
type Workout = {
  id: number;
  name: string;
  program_name: string;
  difficulty: string;
  total_minutes: number;
  muscle_groups: string[];
};
type Exercise = {
  id: number;
  name: string;
  role: string;
  sets: number | null;
  reps: number | null;
  equipment: string[];
  primary_muscles: string[];
};
type Detail = Workout & { exercises: Exercise[] };

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`/api${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

export default function WorkoutsPage() {
  const [muscles, setMuscles] = useState<Named[]>([]);
  const [muscle, setMuscle] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [maxMinutes, setMaxMinutes] = useState("");

  const [workouts, setWorkouts] = useState<Workout[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [details, setDetails] = useState<Record<number, Detail>>({});

  useEffect(() => {
    get<Named[]>("/muscle-groups").then(setMuscles).catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    const params = new URLSearchParams({ limit: "100" });
    if (muscle) params.set("muscle", muscle);
    if (difficulty) params.set("difficulty", difficulty);
    if (maxMinutes) params.set("max_minutes", maxMinutes);

    setError("");
    get<{ items: Workout[]; total: number }>(`/workout-sessions?${params}`)
      .then((page) => {
        setWorkouts(page.items);
        setTotal(page.total);
      })
      .catch((e) => setError(String(e)));
  }, [muscle, difficulty, maxMinutes]);

  async function showExercises(id: number) {
    if (details[id]) return;
    const detail = await get<Detail>(`/workout-sessions/${id}`);
    setDetails((current) => ({ ...current, [id]: detail }));
  }

  return (
    <main style={{ padding: 40, maxWidth: 900, margin: "0 auto" }}>
      <h1>Workouts (from wger data)</h1>

      <p>
        Muscle:{" "}
        <select value={muscle} onChange={(e) => setMuscle(e.target.value)}>
          <option value="">Any</option>
          {muscles.map((m) => (
            <option key={m.id} value={m.name}>
              {m.name}
            </option>
          ))}
        </select>{" "}
        Difficulty:{" "}
        <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
          <option value="">Any</option>
          <option value="beginner">Beginner</option>
          <option value="intermediate">Intermediate</option>
        </select>{" "}
        Length:{" "}
        <select value={maxMinutes} onChange={(e) => setMaxMinutes(e.target.value)}>
          <option value="">Any</option>
          <option value="15">Up to 15 min</option>
          <option value="30">Up to 30 min</option>
          <option value="45">Up to 45 min</option>
          <option value="60">Up to 60 min</option>
        </select>
      </p>

      {error && <p style={{ color: "#e46a6a" }}>Error: {error}</p>}
      <p>{total} workouts found</p>

      <ul>
        {workouts.map((w) => (
          <li key={w.id} style={{ marginBottom: 16 }}>
            <strong>{w.name}</strong> — {w.difficulty}, {w.total_minutes} min, {w.muscle_groups.join(", ")}{" "}
            <button onClick={() => showExercises(w.id)}>show exercises</button>
            {details[w.id] && (
              <ul>
                {details[w.id].exercises.map((ex) => (
                  <li key={ex.id}>
                    {ex.name} ({ex.role}, {ex.sets}x{ex.reps}) — {ex.primary_muscles.join(", ") || "no muscle"} —{" "}
                    {ex.equipment.join(", ") || "no equipment"}
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </main>
  );
}