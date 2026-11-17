
"use client";

type ProgressPoint = {
  date: string;
  prescribed: number | null;
  actual: number | null;
};

type ExerciseProgressChartProps = {
  exerciseName: string;
  points: ProgressPoint[];
  unit?: "reps" | "seconds";
};

export default function ExerciseProgressChart({
  exerciseName,
  points,
  unit = "reps",
}: ExerciseProgressChartProps) {
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

  const formatDate = (date: string) =>
    new Date(date).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    });

  const barWidth = (value: number | null) =>
    `${Math.max(0, ((value ?? 0) / maximum) * 100)}%`;

  return (
    <section aria-label={`${exerciseName} progress`}>
      <h2>{exerciseName}</h2>

      <p style={{ opacity: 0.7 }}>
        Actual versus prescribed {unit}
      </p>

      {sorted.length === 0 ? (
        <p>No workout history available.</p>
      ) : (
        <>
          <div
            style={{
              display: "flex",
              gap: 20,
              margin: "16px 0",
              fontSize: 13,
            }}
          >
            <span>■ Prescribed</span>
            <span style={{ color: "var(--lime, #a3e635)" }}>
              ■ Actual
            </span>
          </div>

          <div style={{ display: "grid", gap: 20 }}>
            {sorted.map((point, index) => (
              <div key={`${point.date}-${index}`}>
                <strong>{formatDate(point.date)}</strong>

                <div style={{ marginTop: 8 }}>
                  <small>
                    Prescribed: {point.prescribed ?? "N/A"} {unit}
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
                    Actual: {point.actual ?? "N/A"} {unit}
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
        </>
      )}

      <p style={{ marginTop: 20, opacity: 0.65, fontSize: 13 }}>
        Training performance reflects completed workout
        targets, not necessarily maximum exercise capacity.
      </p>
    </section>
  );
}
