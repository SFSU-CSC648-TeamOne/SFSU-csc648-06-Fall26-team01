
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

type ApprovalRequest = {
  approvals: Array<{
    prescription_set_id: number;
    adjustment_type: "reps" | "duration" | "weight";
    expected_previous_value: number;
    expected_proposed_value: number;
  }>;
};

type ApprovalResponse = {
  prescription_id: number;
  status: "updated";
  updated_set_count: number;
  updated_sets: Array<{
    prescription_set_id: number;
    adjustment_type: string;
    applied_value: number;
  }>;
};

type Props = {
  prescriptionId: number;
  exerciseNames?: Record<number, string>;
  onApplied?: () => void;
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

function isApprovable(item: SetAdaptation): boolean {
  const { decision, proposal } = item;

  return (
    decision.action === "progress" &&
    decision.confidence === "robust" &&
    proposal.requires_approval &&
    ["reps", "duration", "weight"].includes(
      proposal.adjustment_type
    ) &&
    proposal.previous_value !== null &&
    Number.isFinite(proposal.previous_value) &&
    proposal.proposed_value !== null &&
    Number.isFinite(proposal.proposed_value)
  );
}

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
  selected,
  disabled,
  onToggle,
}: {
  item: SetAdaptation;
  exerciseName: string;
  selected: boolean;
  disabled: boolean;
  onToggle: (setId: number, checked: boolean) => void;
}) {
  const { decision, proposal } = item;
  const approvable = isApprovable(item);

  const hasAdjustment =
    proposal.adjustment_type !== "none" &&
    proposal.previous_value !== null &&
    proposal.proposed_value !== null;

  const color = ACTION_COLORS[decision.action];

  return (
    <article
      style={{
        padding: 20,
        border: selected
          ? "1px solid var(--lime, #a7d46f)"
          : "1px solid rgba(244,241,234,0.12)",
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
                marginBottom: 8,
              }}
            >
              CURRENT TARGET
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
                marginBottom: 8,
              }}
            >
              PROPOSED TARGET
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
        <span>Evidence: {decision.confidence}</span>

        <span>
          {decision.observation_count} observations
        </span>

        <span>
          Trend: {formatChange(decision.change_pct)}
        </span>
      </div>

      <div
        style={{
          marginTop: 18,
          fontSize: 13,
          lineHeight: 1.6,
        }}
      >
        <p>{decision.reason}</p>

        <p
          style={{
            marginTop: 10,
            color: "var(--slate, #8490a5)",
          }}
        >
          {proposal.reason}
        </p>
      </div>

      {approvable && (
        <label
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            marginTop: 20,
            padding: 14,
            border: "1px solid rgba(167,212,111,0.3)",
            cursor: disabled ? "not-allowed" : "pointer",
            fontSize: 13,
          }}
        >
          <input
            type="checkbox"
            checked={selected}
            disabled={disabled}
            onChange={(event) =>
              onToggle(
                item.prescription_set_id,
                event.target.checked
              )
            }
            style={{
              width: 18,
              height: 18,
              accentColor: "var(--lime, #a7d46f)",
            }}
          />

          <span>
            Select this adjustment for approval
          </span>
        </label>
      )}

      {proposal.requires_approval && !approvable && (
        <p
          style={{
            marginTop: 16,
            fontSize: 12,
            color: "var(--slate, #8490a5)",
          }}
        >
          This adjustment cannot currently be applied.
        </p>
      )}
    </article>
  );
}

export default function AdaptationRecommendations({
  prescriptionId,
  exerciseNames = {},
  onApplied,
}: Props) {
  const [data, setData] =
    useState<PrescriptionAdaptationResponse | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [selectedIds, setSelectedIds] =
    useState<Set<number>>(new Set());

  const [applying, setApplying] = useState(false);
  const [approvalError, setApprovalError] = useState("");
  const [success, setSuccess] = useState("");

  const [refreshVersion, setRefreshVersion] = useState(0);

  useEffect(() => {
    let active = true;

    async function loadRecommendations() {
      setLoading(true);
      setError("");
      setData(null);
      setSelectedIds(new Set());

      if (
        !Number.isSafeInteger(prescriptionId) ||
        prescriptionId <= 0
      ) {
        setError("Invalid prescription ID.");
        setLoading(false);
        return;
      }

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
        if (active) setLoading(false);
      }
    }

    void loadRecommendations();

    return () => {
      active = false;
    };
  }, [prescriptionId, refreshVersion]);

  function toggleSelection(
    setId: number,
    checked: boolean
  ) {
    if (applying) return;

    setSelectedIds((previous) => {
      const next = new Set(previous);

      if (checked) {
        next.add(setId);
      } else {
        next.delete(setId);
      }

      return next;
    });

    setApprovalError("");
    setSuccess("");
  }

  async function applySelected() {
    if (!data || applying || loading) return;

    const selected = data.sets.filter(
      (item) =>
        selectedIds.has(item.prescription_set_id) &&
        isApprovable(item)
    );

    if (selected.length === 0) {
      setApprovalError(
        "Select at least one eligible adjustment."
      );
      return;
    }

    const approvals: ApprovalRequest["approvals"] =
      selected.map((item) => ({
        prescription_set_id: item.prescription_set_id,
        adjustment_type: item.proposal.adjustment_type as
          "reps" | "duration" | "weight",
        expected_previous_value:
          item.proposal.previous_value as number,
        expected_proposed_value:
          item.proposal.proposed_value as number,
      }));

    const confirmed = window.confirm(
      `Apply ${approvals.length} selected adjustment` +
      `${approvals.length === 1 ? "" : "s"} ` +
      "to this planned workout?\n\n" +
      "This will update the prescribed targets."
    );

    if (!confirmed) return;

    setApplying(true);
    setApprovalError("");
    setSuccess("");

    try {
      const response = await api<ApprovalResponse>(
        `/adaptations/prescriptions/${prescriptionId}/approve`,
        {
          method: "POST",
          body: JSON.stringify({ approvals }),
        }
      );

      setSelectedIds(new Set());

      setSuccess(
        `${response.updated_set_count} adjustment` +
        `${response.updated_set_count === 1 ? "" : "s"}` +
        " applied to your planned workout."
      );

      // Fetch newly calculated recommendations and targets.
      setRefreshVersion((version) => version + 1);

      onApplied?.();
    } catch (err) {
      setApprovalError(
        err instanceof Error
          ? err.message
          : "Failed to apply adjustments."
      );
    } finally {
      setApplying(false);
    }
  }

  const eligibleCount =
    data?.sets.filter(isApprovable).length ?? 0;

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
          Recommendations are based on comparable
          workout history and your prescribed targets.
          Select the adjustments you want to apply.
        </p>
      </div>

      {success && (
        <p
          role="status"
          style={{
            marginBottom: 20,
            color: "var(--lime, #a7d46f)",
          }}
        >
          {success}
        </p>
      )}

      {approvalError && (
        <p
          role="alert"
          style={{
            marginBottom: 20,
            color: "var(--red, #ef4444)",
          }}
        >
          {approvalError}
        </p>
      )}

      {loading ? (
        <p role="status">
          Analyzing workout recommendations...
        </p>
      ) : error ? (
        <p
          role="alert"
          style={{ color: "var(--red, #ef4444)" }}
        >
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
            <span>
              Week {data.program_week}
            </span>

            <span>
              Day {data.program_day}
            </span>

            <span>
              {data.sets.length} prescribed sets
            </span>
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
                  selected={selectedIds.has(
                    item.prescription_set_id
                  )}
                  disabled={applying}
                  onToggle={toggleSelection}
                />
              ))}
            </div>
          )}

          {eligibleCount > 0 && (
            <div
              style={{
                marginTop: 24,
                padding: 20,
                borderTop:
                  "1px solid rgba(244,241,234,0.12)",
              }}
            >
              <p
                style={{
                  fontSize: 12,
                  color: "var(--slate, #8490a5)",
                  marginBottom: 14,
                }}
              >
                {selectedIds.size} of {eligibleCount}{" "}
                eligible adjustments selected
              </p>

              <button
                type="button"
                disabled={
                  selectedIds.size === 0 ||
                  applying ||
                  loading
                }
                onClick={() => void applySelected()}
                style={{
                  padding: "14px 20px",
                  border: 0,
                  background: "var(--lime, #a7d46f)",
                  color: "#14180e",
                  fontSize: 12,
                  fontWeight: 700,
                  cursor:
                    selectedIds.size === 0 || applying
                      ? "not-allowed"
                      : "pointer",
                  opacity:
                    selectedIds.size === 0 || applying
                      ? 0.5
                      : 1,
                }}
              >
                {applying
                  ? "Applying Adjustments..."
                  : `Apply ${selectedIds.size} Selected ` +
                    `Adjustment${selectedIds.size === 1 ? "" : "s"}`}
              </button>
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
            Only selected, eligible changes will be applied.
            The backend revalidates each recommendation
            before updating the planned workout.
            Completed workout history remains unchanged.
          </p>
        </>
      )}
    </section>
  );
}
