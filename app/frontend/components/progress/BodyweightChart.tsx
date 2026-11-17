
"use client";

type WeightUnit = "kg" | "lb";

export type BodyweightPoint = {
  id: number;
  measurement_date: string;
  measured_at: string | null;
  weight_kg: number;
};

type Props = {
  points: BodyweightPoint[];
  unit?: WeightUnit;
};

const KG_TO_LB = 2.2046226218;

function convertWeight(kg: number, unit: WeightUnit) {
  return unit === "lb" ? kg * KG_TO_LB : kg;
}

function formatDate(value: string) {
  // Parse YYYY-MM-DD without shifting the local date.
  const [year, month, day] = value.split("-").map(Number);

  return new Date(year, month - 1, day).toLocaleDateString(
    undefined,
    { month: "short", day: "numeric" }
  );
}

export default function BodyweightChart({
  points,
  unit = "lb",
}: Props) {
  const sorted = [...points]
    .filter(
      (point) =>
        Number.isFinite(point.weight_kg) &&
        point.weight_kg > 0
    )
    .sort(
      (a, b) =>
        a.measurement_date.localeCompare(b.measurement_date) ||
        (a.measured_at ?? "").localeCompare(b.measured_at ?? "") ||
        a.id - b.id
    );

  if (sorted.length === 0) {
    return (
      <section aria-label="Bodyweight history">
        <h2>Bodyweight History</h2>
        <p>No bodyweight measurements recorded yet.</p>
      </section>
    );
  }

  const weights = sorted.map((point) =>
    convertWeight(point.weight_kg, unit)
  );

  const latest = weights[weights.length - 1];
  const first = weights[0];
  const change = latest - first;

  const minimum = Math.min(...weights);
  const maximum = Math.max(...weights);

  // Include some vertical padding around the plotted values.
  const padding = Math.max(1, (maximum - minimum) * 0.2);
  const chartMin = minimum - padding;
  const chartMax = maximum + padding;

  const width = 600;
  const height = 220;
  const left = 42;
  const right = 16;
  const top = 16;
  const bottom = 34;

  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;

  const x = (index: number) =>
    left +
    (sorted.length === 1
      ? plotWidth / 2
      : (index / (sorted.length - 1)) * plotWidth);

  const y = (value: number) =>
    top +
    ((chartMax - value) / (chartMax - chartMin)) *
      plotHeight;

  const path = weights
    .map(
      (value, index) =>
        `${index === 0 ? "M" : "L"} ${x(index)} ${y(value)}`
    )
    .join(" ");

  const formatWeight = (value: number) =>
    value.toFixed(1);

  return (
    <section aria-label="Bodyweight history">
      <h2>Bodyweight History</h2>

      <div style={{ margin: "16px 0" }}>
        <strong style={{ fontSize: 28 }}>
          {formatWeight(latest)} {unit}
        </strong>

        <p>
          Change: {change > 0 ? "+" : ""}
          {formatWeight(change)} {unit}
        </p>
      </div>

      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`Bodyweight history from ${formatDate(
          sorted[0].measurement_date
        )} to ${formatDate(
          sorted[sorted.length - 1].measurement_date
        )}`}
        style={{ width: "100%", height: "auto" }}
      >
        {[0, 1, 2, 3, 4].map((step) => {
          const value =
            chartMin + ((chartMax - chartMin) * step) / 4;
          const lineY = y(value);

          return (
            <g key={step}>
              <line
                x1={left}
                y1={lineY}
                x2={width - right}
                y2={lineY}
                stroke="currentColor"
                opacity={0.12}
              />

              <text
                x={left - 8}
                y={lineY + 4}
                textAnchor="end"
                fontSize={11}
                fill="currentColor"
              >
                {formatWeight(value)}
              </text>
            </g>
          );
        })}

        {sorted.length > 1 && (
          <path
            d={path}
            fill="none"
            stroke="var(--lime, #a3e635)"
            strokeWidth={3}
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        )}

        {weights.map((value, index) => (
          <circle
            key={sorted[index].id}
            cx={x(index)}
            cy={y(value)}
            r={4}
            fill="var(--lime, #a3e635)"
          >
            <title>
              {formatDate(sorted[index].measurement_date)}
              {": "}
              {formatWeight(value)} {unit}
            </title>
          </circle>
        ))}

        <text
          x={left}
          y={height - 8}
          fontSize={12}
          fill="currentColor"
        >
          {formatDate(sorted[0].measurement_date)}
        </text>

        <text
          x={width - right}
          y={height - 8}
          fontSize={12}
          fill="currentColor"
          textAnchor="end"
        >
          {formatDate(
            sorted[sorted.length - 1].measurement_date
          )}
        </text>
      </svg>

      <p style={{ opacity: 0.65, fontSize: 13 }}>
        Bodyweight changes provide context for training
        performance but do not independently measure strength.
      </p>
    </section>
  );
}
