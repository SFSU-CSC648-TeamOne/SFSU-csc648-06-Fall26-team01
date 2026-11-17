
"use client";

export type TrendConfidence =
  | "insufficient"
  | "preliminary"
  | "robust";

export type MovementGroupProgress = {
  id: number;
  name: string;
  change_pct: number | null;
  exercise_count: number;
  observation_count: number;
  confidence: TrendConfidence;
  explanation?: string | null;
};

type Props = {
  groups: MovementGroupProgress[];
};

function confidenceLabel(value: TrendConfidence) {
  switch (value) {
    case "robust":
      return "Robust trend";
    case "preliminary":
      return "Preliminary trend";
    default:
      return "Insufficient data";
  }
}

export default function MovementGroupChart({
  groups,
}: Props) {
  const sorted = [...groups].sort(
    (a, b) => a.name.localeCompare(b.name)
  );

  // Scale all bars consistently, including negative values.
  const validChanges = sorted
    .map((group) => group.change_pct)
    .filter(
      (value): value is number =>
        value !== null && Number.isFinite(value)
    );

  const maximum = Math.max(
    1,
    ...validChanges.map((value) => Math.abs(value))
  );

  return (
    <section aria-label="Movement group progress">
      <h2>Movement Group Progress</h2>

      <p style={{ opacity: 0.7 }}>
        Normalized performance changes from baseline
      </p>

      {sorted.length === 0 ? (
        <p>No movement-group history available.</p>
      ) : (
        <div style={{ display: "grid", gap: 24 }}>
          {sorted.map((group) => {
            const valid =
              group.change_pct !== null &&
              Number.isFinite(group.change_pct);

            const change = valid
              ? (group.change_pct as number)
              : 0;

            const width =
              (Math.abs(change) / maximum) * 50;

            return (
              <article key={group.id}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    gap: 12,
                    alignItems: "center",
                  }}
                >
                  <strong>{group.name}</strong>

                  <span>
                    {valid
                      ? `${change > 0 ? "+" : ""}${change.toFixed(1)}%`
                      : "N/A"}
                  </span>
                </div>

                <div
                  style={{
                    height: 16,
                    position: "relative",
                    background: "rgba(128,128,128,0.12)",
                    borderRadius: 6,
                    marginTop: 10,
                  }}
                >
                  {/* Center line represents 0% change. */}
                  <div
                    style={{
                      position: "absolute",
                      left: "50%",
                      top: 0,
                      bottom: 0,
                      width: 1,
                      background: "currentColor",
                      opacity: 0.4,
                    }}
                  />

                  {valid && (
                    <div
                      style={{
                        position: "absolute",
                        left:
                          change >= 0
                            ? "50%"
                            : `${50 - width}%`,
                        width: `${width}%`,
                        height: "100%",
                        borderRadius: 6,
                        background:
                          change >= 0
                            ? "var(--lime, #a3e635)"
                            : "var(--red, #ef4444)",
                      }}
                    />
                  )}
                </div>

                <p style={{ marginTop: 8, fontSize: 13, opacity: 0.75 }}>
                  {group.exercise_count} contributing exercises
                  {" · "}
                  {group.observation_count} observations
                  {" · "}
                  {confidenceLabel(group.confidence)}
                </p>

                {group.explanation && (
                  <p style={{ fontSize: 13, opacity: 0.75 }}>
                    {group.explanation}
                  </p>
                )}
              </article>
            );
          })}
        </div>
      )}

      <p style={{ marginTop: 20, fontSize: 13, opacity: 0.65 }}>
        Group trends summarize comparable exercise performance.
        They do not directly measure strength or imply identical
        improvements across related exercises.
      </p>
    </section>
  );
}
