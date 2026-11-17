
"use client";

import { useEffect, useState } from "react";
import { api } from "../../lib/auth";

type AdaptationAction =
  | "insufficient_data"
  | "maintain"
  | "progress"
  | "review_regression"
  | "reassess";

type Confidence =
  | "insufficient"
  | "preliminary"
  | "robust";

type AdjustmentType =
  | "reps"
  | "duration"
  | "weight"
  | "assistance"
  | "none";

type AdaptationDecision = {
  action: AdaptationAction;
  confidence: Confidence;
  observation_count: number;
  change_pct: number | null;
  reason: string;
};

type ProgressionProposal = {
  adjustment_type: AdjustmentType;
  previous_value: number | null;
  proposed_value: number | null;
  requires_approval: boolean;
  reason: string;
};

type SetAdaptation = {
  prescription_set_id: number;
  exercise_id: number;
  set_number: number;
  decision: AdaptationDecision;
  proposal: ProgressionProposal;
};

export type PrescriptionAdaptationResponse = {
  prescription_id: number;
  user_id: number;
  program_slug: string;
  program_week: number;
  program_day: number;
  source_engine_version: string;
  proposal_engine_version: string;
  status: "proposed";
  sets: SetAdaptation[];
};

type Props = {
  prescriptionId: number;
  exerciseNames?: Record<number, string>;
};

const ACTION_LABELS: Record<AdaptationAction, string> = {
  insufficient_data: "More Data Needed",
  maintain: "Maintain",
  progress: "Progression Suggested",
  review_regression: "Review Performance",
  reassess: "Reassessment Suggested",
};

const ACTION_COLORS: Record<AdaptationAction, string> = {
  insufficient_data: "var(--slate, #8490a5)",
  maintain: "var(--blue, #4f7cff)",
  progress: "var(--lime, #a7d46f)",
  review_regression: "var(--red, #ef4444)",
  reassess: "var(--blue, #4f7cff)",
};

function formatTarget(
  value: number | null,
  adjustmentType: AdjustmentType
): string {
  if (value === null || !Number.isFinite(value)) {
    return "N/A";
  }

  const formatted = Number.isInteger(value)
    ? String(value)
    : value.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");

  switch (adjustmentType) {
    case "reps":
      return `${formatted} reps`;
    case "duration":
      return `${formatted} sec`;
    case "weight":
      return `${formatted} kg`;
    case "assistance":
      return `${formatted} kg assistance`;
    default:
      return formatted;
  }
}

function formatChange(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return "Not available";
  }

  return `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
}

function RecommendationCard({
  item,
  exerciseName,
}: {
  item: SetAdaptation;
  exerciseName: string;
}) {
  const { decision, proposal } = item;

  const hasAdjustment =
    proposal.adjustment_type !== "none" &&
    proposal.previous_value !== null &&
    proposal.proposed_value !== null;

  const color = ACTION_COLORS[decision.action];

  return (
    <article
      style={{
        padding: 20,
        border: "1px solid rgba(244,241,234,0.12)",
        background: "rgba(12,14,18,0.35)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div>
          <h3
            style={{
              fontSize: 16,
              margin: 0,
              fontWeight: 600,
            }}
          >
            {exerciseName}
          </h3>

          <p
            style={{
              marginTop: 6,
              fontSize: 12,
              color: "var(--slate, #8490a5)",
            }}
          >
            Set {item.set_number}
          </p>
        </div>

        <span
          style={{
            padding: "6px 10px",
            border: `1px solid ${color}`,
            color,
            fontSize: 10,
            fontWeight: 600,
            letterSpacing: "0.06em",
            textTransform: "uppercase",
          }}
        >
          {ACTION_LABELS[decision.action]}
        </span>
      </div>

      {hasAdjustment && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns:
              "repeat(auto-fit, minmax(120px, 1fr))",
            gap: 16,
            marginTop: 20,
            padding: 16,
            background: "rgba(128,128,128,0.08)",
          }}
        >
          <div>
            <p
              style={{
                fontSize: 10,
                color: "var(--slate, #8490a5)",
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                marginBottom: 8,
              }}
            >
              Current Target
            </p>

            <strong style={{ fontSize: 20 }}>
              {formatTarget(
                proposal.previous_value,
                proposal.adjustment_type
              )}
            </strong>
          </div>

          <div>
            <p
              style={{
                fontSize: 10,
                color: "var(--slate, #8490a5)",
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                marginBottom: 8,
              }}
            >
              Proposed Target
            </p>

            <strong
              style={{
                fontSize: 20,
                color: "var(--lime, #a7d46f)",
              }}
            >
              {formatTarget(
                proposal.proposed_value,
                proposal.adjustment_type
              )}
            </strong>
          </div>
        </div>
      )}

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 18,
          marginTop: 18,
          fontSize: 12,
          color: "var(--slate, #8490a5)",
        }}
      >
        <span>
          Evidence: <strong>{decision.confidence}</strong>
        </span>

        <span>
          Observations:{" "}
          <strong>{decision.observation_count}</strong>
        </span>

        <span>
          Trend:{" "}
          <strong>{formatChange(decision.change_pct)}</strong>
        </span>
      </div>

      <div style={{ marginTop: 18, fontSize: 13 }}>
        <p style={{ lineHeight: 1.6 }}>
          {decision.reason}
        </p>

        <p
          style={{
            marginTop: 10,
            color: "var(--slate, #8490a5)",
            lineHeight: 1.6,
          }}
        >
          {proposal.reason}
        </p>
      </div>

      {proposal.requires_approval && (
        <p
          style={{
            marginTop: 16,
            fontSize: 11,
            color: "var(--lime, #a7d46f)",
          }}
        >
          Recommendation only — user approval will be
          required before this change can be applied.
        </p>
      )}
    </article>
  );
}

export default function AdaptationRecommendations({
  prescriptionId,
  exerciseNames = {},
}: Props) {
  const [data, setData] =
    useState<PrescriptionAdaptationResponse | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (
      !Number.isInteger(prescriptionId) ||
      prescriptionId <= 0
    ) {
      setData(null);
      setError("Invalid prescription ID.");
      setLoading(false);
      return;
    }

    let active = true;

    async function loadRecommendations() {
      setLoading(true);
      setError("");
      setData(null);

      try {
        const response =
          await api<PrescriptionAdaptationResponse>(
            `/adaptations/prescriptions/${prescriptionId}`
          );

        if (!active) return;

        setData(response);
      } catch (err) {
        if (!active) return;

        setError(
          err instanceof Error
            ? err.message
            : "Failed to load adaptation recommendations."
        );
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void loadRecommendations();

    return () => {
      active = false;
    };
  }, [prescriptionId]);

  return (
    <section aria-label="Adaptive training recommendations">
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 22, marginBottom: 10 }}>
          Training Recommendations
        </h2>

        <p
          style={{
            color: "var(--slate, #8490a5)",
            fontSize: 13,
            lineHeight: 1.6,
          }}
        >
          Recommendations are based on comparable workout
          history and the current prescribed targets.
          No changes are applied automatically.
        </p>
      </div>

      {loading ? (
        <p role="status">
          Analyzing workout recommendations...
        </p>
      ) : error ? (
        <p role="alert" style={{ color: "var(--red, #ef4444)" }}>
          {error}
        </p>
      ) : !data ? (
        <p>No recommendation data available.</p>
      ) : (
        <>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 18,
              marginBottom: 24,
              fontSize: 12,
              color: "var(--slate, #8490a5)",
            }}
          >
            <span>Week {data.program_week}</span>
            <span>Day {data.program_day}</span>
            <span>{data.sets.length} prescribed sets</span>
          </div>

          {data.sets.length === 0 ? (
            <p>
              This prescription has no sets to evaluate.
            </p>
          ) : (
            <div style={{ display: "grid", gap: 16 }}>
              {data.sets.map((item) => (
                <RecommendationCard
                  key={item.prescription_set_id}
                  item={item}
                  exerciseName={
                    exerciseNames[item.exercise_id] ??
                    `Exercise #${item.exercise_id}`
                  }
                />
              ))}
            </div>
          )}

          <p
            style={{
              marginTop: 24,
              fontSize: 12,
              lineHeight: 1.6,
              color: "var(--slate, #8490a5)",
            }}
          >
            These recommendations summarize observed
            performance under comparable conditions.
            They are not guarantees of improved performance.
            Any proposed change must be reviewed before
            updating the training prescription.
          </p>
        </>
      )}
    </section>
  );
}
