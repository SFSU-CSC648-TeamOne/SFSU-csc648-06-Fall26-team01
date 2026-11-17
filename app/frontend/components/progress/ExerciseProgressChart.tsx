
"use client";

import { useEffect, useState } from "react";
import { api } from "../../lib/auth";

type Metric = "reps" | "seconds";
type ObservationType = "training" | "benchmark";

export type ProgressPoint = {
  date: string;
  prescribed: number | null;
  actual: number | null;
};

type ExerciseTrend = {
  exercise_id: number;
  observation_type: ObservationType;
  set_number: number;
  metric: Metric;
  load_basis: string;
  weight_kg: number | null;
  assistance_kg: number | null;
  observation_count: number;
  confidence: "insufficient" | "preliminary" | "robust";
  change_pct: number | null;
  slope_per_observation: number | null;
  points: ProgressPoint[];
};

type ExerciseProgressResponse = {
  exercise_id: number;
  observation_type: ObservationType;
  trends: ExerciseTrend[];
};

type Props = {
  exerciseName: string;
  exerciseId?: number;

  // Existing callers can still provide points directly.
  points?: ProgressPoint[];
  unit?: Metric;
};

function formatDate(date: string) {
  return new Date(date).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

function formatValue(value: number | null) {
  return value === null ? "N/A" : String(value);
}

function describeLoad(trend: ExerciseTrend) {
  const parts = [
    `Set ${trend.set_number}`,
    trend.load_basis,
  ];

  if (trend.weight_kg !== null) {
    parts.push(`${trend.weight_kg} kg`);
  }

  if (trend.assistance_kg !== null) {
    parts.push(`${trend.assistance_kg} kg assistance`);
  }

  return parts.join(" · ");
}

function PerformanceBars({
  points,
  unit,
}: {
  points: ProgressPoint[];
  unit: Metric;
}) {
  const sorted = [...points].sort(
    (a, b) =>
      new Date(a.date).getTime() -
      new Date(b.date).getTime()
  );

  const values = sorted.flatMap((point) =>
    [point.prescribed, point.actual].filter(
      (value): value is number =>
        value !== null &&
        Number.isFinite(value) &&
        value >= 0
    )
  );

  const maximum = Math.max(1, ...values);

  const barWidth = (value: number | null) =>
    `${Math.max(0, ((value ?? 0) / maximum) * 100)}%`;

  if (sorted.length === 0) {
    return <p>No comparable workout observations yet.</p>;
  }

  return (
    <div style={{ display: "grid", gap: 20 }}>
      {sorted.map((point, index) => (
        <div key={`${point.date}-${index}`}>
          <strong>{formatDate(point.date)}</strong>

          <div style={{ marginTop: 8 }}>
            <small>
              Prescribed: {formatValue(point.prescribed)} {unit}
            </small>

            <div
              style={{
                height: 12,
                background: "rgba(128,128,128,0.15)",
                borderRadius: 6,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: barWidth(point.prescribed),
                  height: "100%",
                  background: "#8490a5",
                }}
              />
            </div>
          </div>

          <div style={{ marginTop: 8 }}>
            <small>
              Actual: {formatValue(point.actual)} {unit}
            </small>

            <div
              style={{
                height: 12,
                background: "rgba(128,128,128,0.15)",
                borderRadius: 6,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: barWidth(point.actual),
                  height: "100%",
                  background: "var(--lime, #a3e635)",
                }}
              />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function ExerciseProgressChart({
  exerciseName,
  exerciseId,
  points,
  unit = "reps",
}: Props) {
  const [observationType, setObservationType] =
    useState<ObservationType>("training");

  const [trends, setTrends] = useState<ExerciseTrend[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (exerciseId === undefined) {
      setTrends([]);
      setError("");
      setLoading(false);
      return;
    }

    if (!Number.isInteger(exerciseId) || exerciseId <= 0) {
      setTrends([]);
      setError("Invalid exercise ID.");
      setLoading(false);
      return;
    }

    let active = true;

    async function loadProgress() {
      setLoading(true);
      setError("");
      setTrends([]);
      setSelectedIndex(0);

      try {
        const response = await api<ExerciseProgressResponse>(
          `/progress/exercises/${exerciseId}` +
          `?observation_type=${observationType}`
        );

        if (!active) return;

        setTrends(response.trends);
      } catch (err) {
        if (!active) return;

        setError(
          err instanceof Error
            ? err.message
            : "Failed to load exercise progress."
        );
      } finally {
        if (active) setLoading(false);
      }
    }

    void loadProgress();

    return () => {
      active = false;
    };
  }, [exerciseId, observationType]);

  const usesApi = exerciseId !== undefined;
  const selectedTrend = trends[selectedIndex] ?? null;

  return (
    <section aria-label={`${exerciseName} progress`}>
      <h2>{exerciseName}</h2>

      {usesApi && (
        <div style={{ margin: "16px 0" }}>
          <label htmlFor={`observation-${exerciseId}`}>
            Observation type
          </label>

          <select
            id={`observation-${exerciseId}`}
            value={observationType}
            onChange={(event) =>
              setObservationType(
                event.target.value as ObservationType
              )
            }
            style={{
              display: "block",
              marginTop: 8,
              padding: 8,
            }}
          >
            <option value="training">Training</option>
            <option value="benchmark">Benchmark</option>
          </select>
        </div>
      )}

      {loading ? (
        <p role="status">Loading exercise progress...</p>
      ) : error ? (
        <p role="alert">{error}</p>
      ) : usesApi ? (
        trends.length === 0 ? (
          <p>
            No comparable {observationType} history available.
          </p>
        ) : (
          <>
            <div style={{ margin: "16px 0" }}>
              <label htmlFor={`trend-${exerciseId}`}>
                Performance comparison
              </label>

              <select
                id={`trend-${exerciseId}`}
                value={selectedIndex}
                onChange={(event) =>
                  setSelectedIndex(Number(event.target.value))
                }
                style={{
                  display: "block",
                  marginTop: 8,
                  padding: 8,
                  maxWidth: "100%",
                }}
              >
                {trends.map((trend, index) => (
                  <option key={index} value={index}>
                    {describeLoad(trend)} · {trend.metric}
                  </option>
                ))}
              </select>
            </div>

            {selectedTrend && (
              <>
                <p style={{ opacity: 0.7 }}>
                  Actual versus prescribed{" "}
                  {selectedTrend.metric}
                </p>

                <div style={{ margin: "16px 0" }}>
                  <strong>
                    {selectedTrend.observation_count} comparable
                    {" "}observations
                  </strong>

                  <p>
                    Evidence: {selectedTrend.confidence}
                  </p>

                  {selectedTrend.change_pct !== null && (
                    <p>
                      Observed trend:{" "}
                      {selectedTrend.change_pct > 0 ? "+" : ""}
                      {selectedTrend.change_pct}%
                    </p>
                  )}
                </div>

                <div
                  style={{
                    display: "flex",
                    gap: 20,
                    margin: "16px 0",
                    fontSize: 13,
                  }}
                >
                  <span style={{ color: "#8490a5" }}>
                    ■ Prescribed
                  </span>

                  <span
                    style={{
                      color: "var(--lime, #a3e635)",
                    }}
                  >
                    ■ Actual
                  </span>
                </div>

                <PerformanceBars
                  points={selectedTrend.points}
                  unit={selectedTrend.metric}
                />
              </>
            )}
          </>
        )
      ) : (
        <>
          <p style={{ opacity: 0.7 }}>
            Actual versus prescribed {unit}
          </p>

          <PerformanceBars
            points={points ?? []}
            unit={unit}
          />
        </>
      )}

      <p
        style={{
          marginTop: 20,
          opacity: 0.65,
          fontSize: 13,
        }}
      >
        Training performance reflects completed sets,
        not necessarily maximum exercise capacity.
        Evidence levels describe the quantity of comparable
        observations, not statistical certainty.
      </p>
    </section>
  );
}
