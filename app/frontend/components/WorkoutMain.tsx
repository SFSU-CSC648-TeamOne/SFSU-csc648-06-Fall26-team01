"use client";

import { useEffect, useMemo, useState } from "react";
import styles from "./WorkoutMain.module.css";

type Named = { id: number; name: string };

type Workout = {
  id: number;
  name: string;
  program_name: string;
  difficulty: string;
  total_minutes: number;
  exercise_count: number;
  muscle_groups: string[];
};

type Exercise = {
  id: number;
  name: string;
  role: string;
  sets: number | null;
  reps: number | null;
  minutes?: number;
  equipment: string[];
  primary_muscles: string[];
};

type WorkoutDetail = Workout & { exercises: Exercise[] };

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`/api${path}`);
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return (await response.json()) as T;
}

export default function WorkoutMain() {
  const [muscles, setMuscles] = useState<Named[]>([]);
  const [muscle, setMuscle] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [maxMinutes, setMaxMinutes] = useState("");
  const [search, setSearch] = useState("");
  const [workouts, setWorkouts] = useState<Workout[]>([]);
  const [details, setDetails] = useState<Record<number, WorkoutDetail>>({});
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});
  const [loading, setLoading] = useState(false);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    get<Named[]>("/muscle-groups")
      .then(setMuscles)
      .catch((reason) => setError(String(reason)));
  }, []);

  useEffect(() => {
    const term = search.trim();
    if (!term) {
      setWorkouts([]);
      setDetails({});
      setExpanded({});
      setLoading(false);
      setLoadingDetails(false);
      setError("");
      return;
    }

    const params = new URLSearchParams({ limit: "100" });
    if (muscle) params.set("muscle", muscle);
    if (difficulty) params.set("difficulty", difficulty);
    if (maxMinutes) params.set("max_minutes", maxMinutes);

    const timeout = window.setTimeout(() => {
      setLoading(true);
      setLoadingDetails(true);
      setError("");

      get<{ items: Workout[]; total: number }>(`/workout-sessions?${params}`)
        .then(async (page) => {
          setWorkouts(page.items);
          const loadedDetails = await Promise.all(
            page.items.map((workout) =>
              get<WorkoutDetail>(`/workout-sessions/${workout.id}`),
            ),
          );
          setDetails(
            Object.fromEntries(
              loadedDetails.map((detail) => [detail.id, detail]),
            ),
          );
        })
        .catch((reason) => setError(String(reason)))
        .finally(() => {
          setLoading(false);
          setLoadingDetails(false);
        });
    }, 250);

    return () => window.clearTimeout(timeout);
  }, [difficulty, maxMinutes, muscle, search]);

  const filteredWorkouts = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return workouts;

    return workouts.filter((workout) => {
      const detail = details[workout.id];
      const searchableText = [
        workout.name,
        workout.program_name,
        ...workout.muscle_groups,
        ...(detail?.exercises.flatMap((exercise) => [
          exercise.name,
          ...exercise.primary_muscles,
          ...exercise.equipment,
        ]) ?? []),
      ]
        .join(" ")
        .toLowerCase();

      return searchableText.includes(term);
    });
  }, [details, search, workouts]);

  function toggleExpanded(id: number) {
    setExpanded((current) => ({ ...current, [id]: !current[id] }));
  }

  return (
    <>
      <div className={`catalog-top ${styles.catalogTop}`}>
        <label className="search">
          <span>⌕</span>
          <input
            className={styles.searchInput}
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search exercises..."
            aria-label="Search workouts and exercises"
          />
        </label>

        <label className={styles.catalogFilter}>
          <span className={styles.srOnly}>Muscle group</span>
          <select value={muscle} onChange={(event) => setMuscle(event.target.value)}>
            <option value="">MUSCLE GROUP</option>
            {muscles.map((item) => (
              <option key={item.id} value={item.name}>
                {item.name.toUpperCase()}
              </option>
            ))}
          </select>
          <span>⌄</span>
        </label>

        <label className={styles.catalogFilter}>
          <span className={styles.srOnly}>Difficulty</span>
          <select
            value={difficulty}
            onChange={(event) => setDifficulty(event.target.value)}
          >
            <option value="">DIFFICULTY</option>
            <option value="beginner">BEGINNER</option>
            <option value="intermediate">INTERMEDIATE</option>
          </select>
          <span>⌄</span>
        </label>

        <label className={styles.catalogFilter}>
          <span className={styles.srOnly}>Maximum duration</span>
          <select
            value={maxMinutes}
            onChange={(event) => setMaxMinutes(event.target.value)}
          >
            <option value="">LENGTH</option>
            <option value="15">UP TO 15 MIN</option>
            <option value="30">UP TO 30 MIN</option>
            <option value="45">UP TO 45 MIN</option>
            <option value="60">UP TO 60 MIN</option>
          </select>
          <span>⌄</span>
        </label>
      </div>

      {error && <p className={`${styles.message} ${styles.error}`}>{error}</p>}
      {loading && <p className={styles.message}>LOADING WORKOUTS...</p>}
      {!loading && !loadingDetails && filteredWorkouts.length === 0 && (
        <p className={styles.message}>NO MATCHING WORKOUTS.</p>
      )}

      <div className="exercise-table">
        {filteredWorkouts.map((workout, index) => {
          const detail = details[workout.id];
          const isExpanded = expanded[workout.id];

          return (
            <div className={styles.exerciseGroup} key={workout.id}>
              <button
                className={`exercise ${styles.exerciseWorkout}`}
                type="button"
                onClick={() => toggleExpanded(workout.id)}
                aria-expanded={isExpanded}
              >
                <span className="exercise-index">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span className="exercise-title">
                  <strong>{workout.name}</strong>
                  <small>{workout.muscle_groups.join(" · ") || "FULL BODY"}</small>
                </span>
                <span>{workout.difficulty.toUpperCase()}</span>
                <span>{String(workout.total_minutes).padStart(2, "0")} MIN</span>
                <b className="core">
                  {isExpanded ? "HIDE" : `${workout.exercise_count} EX`}
                </b>
              </button>

              {isExpanded && detail && (
                <div className={styles.exerciseSubitems}>
                  {detail.exercises.map((exercise, exerciseIndex) => (
                    <div className={styles.exerciseSubitem} key={exercise.id}>
                      <span>{`${index + 1}.${exerciseIndex + 1}`}</span>
                      <strong>{exercise.name}</strong>
                      <small>
                        {exercise.role.toUpperCase()} ·{" "}
                        {exercise.primary_muscles.join(", ") || "FULL BODY"}
                      </small>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className={`catalog-footer ${styles.catalogFooter}`}>
        <span>DATABASE / WORKOUTS</span>
        <span>{filteredWorkouts.length} WORKOUTS</span>
      </div>
    </>
  );
}
