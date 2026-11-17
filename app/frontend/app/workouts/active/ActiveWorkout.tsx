
"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import Navbar from "../../../components/Navbar";
import { api, useRequireAuth } from "../../../lib/auth";
import type {
  PerformanceSet,
  WorkoutSubmission,
} from "../../../lib/workoutTypes";

import s from "../../screens.module.css";

type Exercise = {
  id: number;
  name: string;
  role: string;
  sets: number | null;
  reps: number | null;
};

type Detail = {
  id: number;
  name: string;
  exercises: Exercise[];
};

function clock(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;

  return `${String(minutes).padStart(2, "0")}:${String(
    remaining
  ).padStart(2, "0")}`;
}

export default function ActiveWorkout() {
  useRequireAuth();

  const router = useRouter();
  const sessionId = useSearchParams().get("session");

  const [workout, setWorkout] = useState<Detail | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const [exerciseIndex, setExerciseIndex] = useState(0);

  // Each exercise maintains its own recorded sets.
  // Keys are session-exercise positions, not exercise IDs.
  const [results, setResults] = useState<
    Record<number, PerformanceSet[]>
  >({});

  // Current unsaved set.
  const [reps, setReps] = useState("");
  const [weight, setWeight] = useState("");

  const [seconds, setSeconds] = useState(0);
  const [saving, setSaving] = useState(false);

  const started = useRef(new Date());

  useEffect(() => {
    let active = true;

    setWorkout(null);
    setResults({});
    setExerciseIndex(0);
    setReps("");
    setWeight("");
    setError("");
    setLoading(true);
    setSeconds(0);
    started.current = new Date();

    if (!sessionId) {
      setError("No workout selected. Pick one from Programs.");
      setLoading(false);
      return;
    }

    api<Detail>(`/workout-sessions/${sessionId}`)
      .then((data) => {
        if (active) setWorkout(data);
      })
      .catch((err) => {
        if (active) {
          setError(
            err instanceof Error
              ? err.message
              : "Could not load workout."
          );
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [sessionId]);

  useEffect(() => {
    const timer = setInterval(() => {
      setSeconds(
        Math.max(
          0,
          Math.floor(
            (Date.now() - started.current.getTime()) / 1000
          )
        )
      );
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  const current = workout?.exercises[exerciseIndex];
  const savedSets = results[exerciseIndex] ?? [];

  const targetSets = Math.max(1, current?.sets ?? 1);
  const currentSetNumber = savedSets.length + 1;
  const exerciseComplete = savedSets.length >= targetSets;

  const allEntries = workout
    ? workout.exercises.flatMap((_, index) => results[index] ?? [])
    : [];

  const completedCount = allEntries.filter(
    (entry) => entry.status === "completed"
  ).length;

  function moveToExercise(index: number) {
    if (!workout) return;

    if (index < 0 || index >= workout.exercises.length) {
      return;
    }

    setExerciseIndex(index);
    setReps("");
    setWeight("");
    setError("");
  }

  function saveSet(status: "completed" | "skipped") {
    if (!current || exerciseComplete || saving) return;

    let actualReps: number | null = null;
    let actualWeight: number | null = null;

    if (status === "completed") {
      if (reps.trim() === "") {
        setError("Enter the actual repetitions completed.");
        return;
      }

      const parsedReps = Number(reps);

      if (
        !Number.isInteger(parsedReps) ||
        parsedReps < 0 ||
        parsedReps > 1000
      ) {
        setError("Repetitions must be between 0 and 1000.");
        return;
      }

      actualReps = parsedReps;

      if (weight.trim() !== "") {
        const parsedWeight = Number(weight);

        if (
          !Number.isFinite(parsedWeight) ||
          parsedWeight < 0 ||
          parsedWeight > 2000
        ) {
          setError("Enter a valid weight in kilograms.");
          return;
        }

        actualWeight = parsedWeight;
      }
    }

    const entry: PerformanceSet = {
      exercise_id: current.id,
      set_number: currentSetNumber,
      reps: actualReps,
      weight_kg: actualWeight,
      status,
    };

    setResults((previous) => ({
      ...previous,
      [exerciseIndex]: [
        ...(previous[exerciseIndex] ?? []),
        entry,
      ],
    }));

    setReps("");
    setError("");

    // Retain the weight as a convenience for the next set.
    // Skipping a set does not change the entered weight.
  }

  function undoLastSet() {
    if (savedSets.length === 0 || saving) return;

    const last = savedSets[savedSets.length - 1];

    setResults((previous) => ({
      ...previous,
      [exerciseIndex]: savedSets.slice(0, -1),
    }));

    setReps(
      last.status === "completed" && last.reps !== null
        ? String(last.reps)
        : ""
    );

    setWeight(
      last.weight_kg !== null && last.weight_kg !== undefined
        ? String(last.weight_kg)
        : ""
    );

    setError("");
  }

  async function finishWorkout() {
    if (!workout || saving) return;

    if (allEntries.length === 0) {
      setError("Record at least one set before saving.");
      return;
    }

    if (reps.trim() !== "") {
      setError(
        "You have unsaved repetitions. Save or clear the current set first."
      );
      return;
    }

    setSaving(true);
    setError("");

    const payload: WorkoutSubmission & {
      performed_at: string;
    } = {
      workout_session_id: workout.id,
      performed_at: started.current.toISOString(),
      duration_minutes: Math.min(
        600,
        Math.max(1, Math.round(seconds / 60))
      ),
      entries: allEntries,
    };

    try {
      await api("/workout-records", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      router.push("/history");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not save workout."
      );
      setSaving(false);
    }
  }

  return (
    <main className={s.page}>
      <Navbar />

      <div className={s.wrap}>
        <p className={s.kicker}>Active workout</p>

        {loading && (
          <p className={s.muted}>Loading workout...</p>
        )}

        {error && (
          <p className={s.error} role="alert">
            {error}
          </p>
        )}

        {workout && (
          <>
            <h1 className={s.h1}>{workout.name}</h1>

            <p className={s.timer} aria-label="Elapsed time">
              {clock(seconds)}
            </p>

            <p className={s.muted}>
              {completedCount} completed sets recorded
            </p>
          </>
        )}

        {current && (
          <section className={s.card}>
            <p className={s.kicker}>
              Exercise {exerciseIndex + 1} of{" "}
              {workout?.exercises.length}
            </p>

            <h2>{current.name}</h2>

            <p className={s.muted}>
              Prescribed: {targetSets} sets
              {current.reps !== null
                ? ` × ${current.reps} reps`
                : ""}
              {" · "}
              {current.role.toUpperCase()}
            </p>

            <p className={s.muted}>
              Recorded: {savedSets.length} / {targetSets} sets
            </p>

            {!exerciseComplete ? (
              <>
                <h3>Set {currentSetNumber}</h3>

                <div className={s.field}>
                  <label htmlFor="actual-reps">
                    Actual repetitions
                  </label>

                  <input
                    id="actual-reps"
                    className={s.input}
                    type="number"
                    inputMode="numeric"
                    min={0}
                    max={1000}
                    step={1}
                    value={reps}
                    disabled={saving}
                    onChange={(event) =>
                      setReps(event.target.value)
                    }
                    placeholder={
                      current.reps !== null
                        ? `Target: ${current.reps}`
                        : "Repetitions"
                    }
                  />
                </div>

                <div className={s.field}>
                  <label htmlFor="actual-weight">
                    Weight used (kg, optional)
                  </label>

                  <input
                    id="actual-weight"
                    className={s.input}
                    type="number"
                    inputMode="decimal"
                    min={0}
                    max={2000}
                    step="any"
                    value={weight}
                    disabled={saving}
                    onChange={(event) =>
                      setWeight(event.target.value)
                    }
                    placeholder="0"
                  />
                </div>

                <div className={s.actions}>
                  <button
                    type="button"
                    className={s.btn}
                    onClick={() => saveSet("completed")}
                    disabled={saving}
                  >
                    Save set
                  </button>

                  <button
                    type="button"
                    className={`${s.btn} ${s.btnGhost}`}
                    onClick={() => saveSet("skipped")}
                    disabled={saving}
                  >
                    Skip set
                  </button>
                </div>
              </>
            ) : (
              <p className={s.muted} role="status">
                All prescribed sets have been recorded.
              </p>
            )}

            {savedSets.length > 0 && (
              <div style={{ marginTop: 24 }}>
                <h3>Recorded sets</h3>

                {savedSets.map((entry) => (
                  <p
                    key={entry.set_number}
                    className={s.muted}
                  >
                    Set {entry.set_number}:{" "}
                    {entry.status === "skipped"
                      ? "Skipped"
                      : `${entry.reps} reps`}
                    {entry.status === "completed" &&
                    entry.weight_kg !== null &&
                    entry.weight_kg !== undefined
                      ? ` · ${entry.weight_kg} kg`
                      : ""}
                  </p>
                ))}

                <button
                  type="button"
                  className={`${s.btn} ${s.btnGhost}`}
                  onClick={undoLastSet}
                  disabled={saving}
                >
                  Undo last set
                </button>
              </div>
            )}

            <div
              className={s.actions}
              style={{ marginTop: 24 }}
            >
              <Link
                href={`/exercises/${current.id}`}
                target="_blank"
                className={`${s.btn} ${s.btnGhost}`}
              >
                Watch demo
              </Link>
            </div>
          </section>
        )}

        {workout && (
          <>
            <div
              className={s.actions}
              style={{ marginTop: 24 }}
            >
              <button
                type="button"
                className={`${s.btn} ${s.btnGhost}`}
                disabled={exerciseIndex === 0 || saving}
                onClick={() =>
                  moveToExercise(exerciseIndex - 1)
                }
              >
                Previous exercise
              </button>

              <button
                type="button"
                className={s.btn}
                disabled={
                  exerciseIndex >=
                    workout.exercises.length - 1 ||
                  saving
                }
                onClick={() =>
                  moveToExercise(exerciseIndex + 1)
                }
              >
                Next exercise
              </button>
            </div>

            <div
              className={s.actions}
              style={{ marginTop: 32 }}
            >
              <button
                type="button"
                className={`${s.btn} ${s.btnGreen}`}
                onClick={finishWorkout}
                disabled={saving || allEntries.length === 0}
              >
                {saving
                  ? "Saving..."
                  : "Finish and save"}
              </button>
            </div>
          </>
        )}
      </div>
    </main>
  );
}
