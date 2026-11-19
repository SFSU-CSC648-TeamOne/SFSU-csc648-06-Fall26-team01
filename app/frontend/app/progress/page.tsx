
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import Navbar from "../../components/Navbar";
import BodyweightLogger from "../../components/BodyweightLogger";
import BodyweightChart, {
  type BodyweightPoint,
} from "../../components/progress/BodyweightChart";
import ExerciseProgressChart from "../../components/progress/ExerciseProgressChart";
import MovementGroupChart, {
  type MovementGroupProgress,
} from "../../components/progress/MovementGroupChart";
import AdaptationRecommendations from "../../components/AdaptationRecommendations";

import { api, useRequireAuth } from "../../lib/auth";
import {
  fmtDate,
  volume,
  type Page,
  type RecordDetail,
  type RecordSummary,
} from "../../lib/records";

import s from "../screens.module.css";


type ExerciseOption = {
  id: number;
  name: string;
};

type PlannedPrescription = {
  id: number;
  program_slug: string;
  program_week: number;
  program_day: number;
  set_count: number;
  engine_version: string;
};


export default function ProgressPage() {
  const { user, loading: authLoading } = useRequireAuth();

  // Workout history
  const [records, setRecords] = useState<RecordDetail[]>([]);
  const [recordsLoading, setRecordsLoading] = useState(true);
  const [error, setError] = useState("");

  const [selectedExerciseId, setSelectedExerciseId] =
    useState<number | null>(null);

  // Bodyweight
  const [bodyweight, setBodyweight] =
    useState<BodyweightPoint[]>([]);
  const [weightLoading, setWeightLoading] = useState(true);
  const [weightError, setWeightError] = useState("");
  const [weightRefresh, setWeightRefresh] = useState(0);

  // Movement groups
  const [movementGroups, setMovementGroups] =
    useState<MovementGroupProgress[]>([]);
  const [groupsLoading, setGroupsLoading] = useState(true);
  const [groupsError, setGroupsError] = useState("");

  // Adaptive recommendations
  const [plannedPrescriptions, setPlannedPrescriptions] =
    useState<PlannedPrescription[]>([]);
  const [selectedProgram, setSelectedProgram] = useState("");
  const [selectedPrescriptionId, setSelectedPrescriptionId] =
    useState<number | null>(null);
  const [adaptationsLoading, setAdaptationsLoading] =
    useState(true);
  const [adaptationsError, setAdaptationsError] = useState("");

  // --------------------------------------------------
  // Load workout history
  // --------------------------------------------------

  useEffect(() => {
    if (authLoading || !user) return;

    let active = true;

    async function loadRecords() {
      setRecordsLoading(true);
      setError("");

      try {
        const page = await api<Page<RecordSummary>>(
          "/workout-records?limit=100"
        );

        const details = await Promise.all(
          page.items.map((record) =>
            api<RecordDetail>(
              `/workout-records/${record.id}`
            )
          )
        );

        if (!active) return;

        setRecords(details);
      } catch (err) {
        if (!active) return;

        setError(
          err instanceof Error
            ? err.message
            : "Failed to load workout history."
        );
      } finally {
        if (active) setRecordsLoading(false);
      }
    }

    void loadRecords();

    return () => {
      active = false;
    };
  }, [authLoading, user?.id]);

  // --------------------------------------------------
  // Load bodyweight history
  // --------------------------------------------------

  useEffect(() => {
    if (authLoading || !user) return;

    let active = true;

    async function loadBodyweight() {
      setWeightLoading(true);
      setWeightError("");

      try {
        const data = await api<
          Array<
            Omit<BodyweightPoint, "weight_kg"> & {
              weight_kg: number | string;
            }
          >
        >("/bodyweight-measurements?limit=365");

        if (!active) return;

        setBodyweight(
          data.map((item) => ({
            ...item,
            weight_kg: Number(item.weight_kg),
          }))
        );
      } catch (err) {
        if (!active) return;

        setWeightError(
          err instanceof Error
            ? err.message
            : "Failed to load bodyweight history."
        );
      } finally {
        if (active) setWeightLoading(false);
      }
    }

    void loadBodyweight();

    return () => {
      active = false;
    };
  }, [authLoading, user?.id, weightRefresh]);

  // --------------------------------------------------
  // Load movement-group progress
  // --------------------------------------------------

  useEffect(() => {
    if (authLoading || !user) return;

    let active = true;

    async function loadMovementGroups() {
      setGroupsLoading(true);
      setGroupsError("");

      try {
        const data = await api<MovementGroupProgress[]>(
          "/progress/movement-groups"
        );

        if (!active) return;

        setMovementGroups(data);
      } catch (err) {
        if (!active) return;

        setGroupsError(
          err instanceof Error
            ? err.message
            : "Failed to load movement-group progress."
        );
      } finally {
        if (active) setGroupsLoading(false);
      }
    }

    void loadMovementGroups();

    return () => {
      active = false;
    };
  }, [authLoading, user?.id]);

  // --------------------------------------------------
  // Load planned workout prescriptions
  // --------------------------------------------------

  useEffect(() => {
    if (authLoading || !user) return;

    let active = true;

    async function loadPlannedPrescriptions() {
      setAdaptationsLoading(true);
      setAdaptationsError("");

      try {
        const data = await api<PlannedPrescription[]>(
          "/adaptations/planned-prescriptions"
        );

        if (!active) return;

        setPlannedPrescriptions(data);
      } catch (err) {
        if (!active) return;

        setAdaptationsError(
          err instanceof Error
            ? err.message
            : "Failed to load planned workouts."
        );
      } finally {
        if (active) setAdaptationsLoading(false);
      }
    }

    void loadPlannedPrescriptions();

    return () => {
      active = false;
    };
  }, [authLoading, user?.id]);

  // --------------------------------------------------
  // Derived exercise data
  // --------------------------------------------------

  const exerciseMap = new Map<number, ExerciseOption>();

  for (const record of records) {
    for (const entry of record.entries) {
      if (!exerciseMap.has(entry.exercise_id)) {
        exerciseMap.set(entry.exercise_id, {
          id: entry.exercise_id,
          name: entry.exercise_name,
        });
      }
    }
  }

  const exercises = [...exerciseMap.values()].sort(
    (a, b) => a.name.localeCompare(b.name)
  );

  const selectedExercise =
    exercises.find(
      (exercise) => exercise.id === selectedExerciseId
    ) ?? exercises[0] ?? null;

  const exerciseNames = Object.fromEntries(
    exercises.map((exercise) => [
      exercise.id,
      exercise.name,
    ])
  );

  // --------------------------------------------------
  // Training volume chart
  // --------------------------------------------------

  const points = [...records]
    .sort(
      (a, b) =>
        new Date(a.performed_at).getTime() -
        new Date(b.performed_at).getTime()
    )
    .slice(-10)
    .map((record) => ({
      label: fmtDate(record.performed_at).slice(0, 6),
      value: volume(record),
      id: record.id,
    }));

  const maxVolume = Math.max(
    1,
    ...points.map((point) => point.value)
  );

  const firstVolume = points[0]?.value ?? 0;
  const lastVolume = points[points.length - 1]?.value ?? 0;

  const volumeChange =
    firstVolume > 0
      ? Math.round(
          ((lastVolume - firstVolume) / firstVolume) * 100
        )
      : null;

  // --------------------------------------------------
  // Adaptive prescription selection
  // --------------------------------------------------

  const availablePrograms = [
    ...new Set(
      plannedPrescriptions.map(
        (prescription) => prescription.program_slug
      )
    ),
  ].sort();

  const programPrescriptions = plannedPrescriptions.filter(
    (prescription) =>
      prescription.program_slug === selectedProgram
  );

  const selectedPrescription =
    programPrescriptions.find(
      (prescription) =>
        prescription.id === selectedPrescriptionId
    ) ?? programPrescriptions[0] ?? null;

  // --------------------------------------------------
  // Render
  // --------------------------------------------------

  if (authLoading || !user) {
    return (
      <main className={s.page}>
        <Navbar />
        <div className={s.wrap}>
          <p role="status" className={s.muted}>
            Loading your training progress...
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className={s.page}>
      <Navbar />

      <div className={s.wrap}>
        <p className={s.kicker}>
          Training volume (reps × kg) per workout
        </p>

        <h1 className={s.h1}>
          Progress<span>trend.</span>
        </h1>

        {error && (
          <p role="alert" className={s.error}>
            {error}
          </p>
        )}

        {/* ---------------------------------------
            Training Volume
        --------------------------------------- */}

        {recordsLoading ? (
          <p className={s.muted}>
            Loading workout history...
          </p>
        ) : points.length === 0 ? (
          <p className={s.muted}>
            Finish a workout to see your trend.{" "}
            <Link
              href="/programs"
              style={{ color: "#9fb0ff" }}
            >
              Go to Programs
            </Link>
            .
          </p>
        ) : (
          <div className={s.card}>
            {volumeChange !== null &&
              points.length > 1 && (
                <p
                  className={s.mono}
                  style={{
                    color:
                      volumeChange >= 0
                        ? "var(--lime)"
                        : "var(--red)",
                  }}
                >
                  {volumeChange >= 0 ? "+" : ""}
                  {volumeChange}% SINCE {points[0].label}
                </p>
              )}

            <div
              className={s.bars}
              role="img"
              aria-label="Training volume per workout"
            >
              {points.map((point) => (
                <div
                  key={point.id}
                  className={s.bar}
                  style={{
                    height: `${
                      (point.value / maxVolume) * 100
                    }%`,
                  }}
                >
                  <span>
                    {Math.round(point.value)}
                  </span>
                </div>
              ))}
            </div>

            <div className={s.barLabels}>
              {points.map((point) => (
                <span key={point.id}>
                  {point.label}
                </span>
              ))}
            </div>

            <p
              className={s.muted}
              style={{ marginTop: 16 }}
            >
              Training volume measures recorded
              repetitions multiplied by external
              weight. Bodyweight-only work may
              contribute zero to this metric.
            </p>
          </div>
        )}

        {/* ---------------------------------------
            Exercise Progress
        --------------------------------------- */}

        <section
          className={s.card}
          style={{ marginTop: 24 }}
          aria-labelledby="exercise-progress-heading"
        >
          <h2 id="exercise-progress-heading">
            Exercise Progress
          </h2>

          <p className={s.muted}>
            Compare your completed performance against
            prescribed targets and review trends across
            comparable workouts.
          </p>

          {recordsLoading ? (
            <p className={s.muted}>
              Loading exercises...
            </p>
          ) : exercises.length === 0 ? (
            <p className={s.muted}>
              No recorded exercises available yet.
            </p>
          ) : selectedExercise ? (
            <>
              <div style={{ marginTop: 20 }}>
                <label
                  htmlFor="exercise-progress-selector"
                  style={{ display: "block" }}
                >
                  Select exercise
                </label>

                <select
                  id="exercise-progress-selector"
                  className={s.select}
                  value={selectedExercise.id}
                  onChange={(event) =>
                    setSelectedExerciseId(
                      Number(event.target.value)
                    )
                  }
                  style={{
                    display: "block",
                    marginTop: 8,
                    width: "100%",
                    maxWidth: 420,
                  }}
                >
                  {exercises.map((exercise) => (
                    <option
                      key={exercise.id}
                      value={exercise.id}
                    >
                      {exercise.name}
                    </option>
                  ))}
                </select>
              </div>

              <div style={{ marginTop: 28 }}>
                <ExerciseProgressChart
                  exerciseId={selectedExercise.id}
                  exerciseName={selectedExercise.name}
                />
              </div>
            </>
          ) : null}

          <p
            className={s.muted}
            style={{ marginTop: 16 }}
          >
            Exercise selection is based on your
            100 most recent workout records.
            Trend history is calculated separately
            by the backend.
          </p>
        </section>

        {/* ---------------------------------------
            Movement Pattern Analysis
        --------------------------------------- */}

        <section
          className={s.card}
          style={{ marginTop: 24 }}
          aria-labelledby="movement-group-heading"
        >
          <h2 id="movement-group-heading">
            Movement Pattern Analysis
          </h2>

          <p className={s.muted}>
            Track performance trends across related
            exercises. Movement-group results summarize
            comparable training observations.
          </p>

          <div style={{ marginTop: 24 }}>
            {groupsLoading ? (
              <p role="status" className={s.muted}>
                Loading movement-group progress...
              </p>
            ) : groupsError ? (
              <p role="alert" className={s.error}>
                {groupsError}
              </p>
            ) : (
              <MovementGroupChart
                groups={movementGroups}
              />
            )}
          </div>
        </section>

        {/* ---------------------------------------
            Adaptive Training Recommendations
        --------------------------------------- */}

        <section
          className={s.card}
          style={{ marginTop: 24 }}
          aria-labelledby="adaptive-heading"
        >
          <h2 id="adaptive-heading">
            Adaptive Training Recommendations
          </h2>

          <p className={s.muted}>
            Review recommended adjustments to upcoming
            workouts based on your recorded performance.
          </p>

          {adaptationsLoading ? (
            <p role="status" className={s.muted}>
              Loading planned workouts...
            </p>
          ) : adaptationsError ? (
            <p role="alert" className={s.error}>
              {adaptationsError}
            </p>
          ) : plannedPrescriptions.length === 0 ? (
            <p
              className={s.muted}
              style={{ marginTop: 20 }}
            >
              No planned workout prescriptions are available.
            </p>
          ) : (
            <>
              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  gap: 20,
                  marginTop: 24,
                  marginBottom: 24,
                }}
              >
                <div
                  className={s.field}
                  style={{ flex: "1 1 200px" }}
                >
                  <label htmlFor="adaptive-program">
                    Training Program
                  </label>

                  <select
                    id="adaptive-program"
                    className={s.select}
                    value={selectedProgram}
                    onChange={(event) => {
                      setSelectedProgram(event.target.value);
                      setSelectedPrescriptionId(null);
                    }}
                  >
                    <option value="">
                      Select program
                    </option>

                    {availablePrograms.map((program) => (
                      <option
                        key={program}
                        value={program}
                      >
                        {program.toUpperCase()}
                      </option>
                    ))}
                  </select>
                </div>

                <div
                  className={s.field}
                  style={{ flex: "1 1 200px" }}
                >
                  <label htmlFor="adaptive-workout">
                    Upcoming Workout
                  </label>

                  <select
                    id="adaptive-workout"
                    className={s.select}
                    value={selectedPrescription?.id ?? ""}
                    disabled={!selectedProgram}
                    onChange={(event) =>
                      setSelectedPrescriptionId(
                        Number(event.target.value)
                      )
                    }
                  >
                    {!selectedProgram && (
                      <option value="">
                        Select program first
                      </option>
                    )}

                    {programPrescriptions.map(
                      (prescription) => (
                        <option
                          key={prescription.id}
                          value={prescription.id}
                        >
                          Week {prescription.program_week}
                          {" · "}
                          Day {prescription.program_day}
                          {" · "}
                          {prescription.set_count} sets
                        </option>
                      )
                    )}
                  </select>
                </div>
              </div>

              {selectedPrescription ? (
                <AdaptationRecommendations
                  key={selectedPrescription.id}
                  prescriptionId={selectedPrescription.id}
                  exerciseNames={exerciseNames}
                />
              ) : (
                <p className={s.muted}>
                  Select your training program to review
                  upcoming workout recommendations.
                </p>
              )}
            </>
          )}
        </section>

        {/* ---------------------------------------
            Bodyweight Tracking
        --------------------------------------- */}

        <section
          className={s.card}
          style={{ marginTop: 24 }}
          aria-labelledby="bodyweight-heading"
        >
          <h2 id="bodyweight-heading">
            Bodyweight Tracking
          </h2>

          <p className={s.muted}>
            Monitor your bodyweight alongside
            training performance.
          </p>

          <div style={{ marginTop: 24 }}>
            <BodyweightLogger
              onSaved={() =>
                setWeightRefresh((count) => count + 1)
              }
            />
          </div>

          <div style={{ marginTop: 32 }}>
            {weightLoading ? (
              <p className={s.muted}>
                Loading bodyweight history...
              </p>
            ) : weightError ? (
              <p role="alert" className={s.error}>
                {weightError}
              </p>
            ) : (
              <BodyweightChart
                points={bodyweight}
                unit="lb"
              />
            )}
          </div>
        </section>

        <div className={s.actions}>
          <Link
            href="/history"
            className={`${s.btn} ${s.btnGhost}`}
          >
            Back to Training History
          </Link>
        </div>
      </div>
    </main>
  );
}
