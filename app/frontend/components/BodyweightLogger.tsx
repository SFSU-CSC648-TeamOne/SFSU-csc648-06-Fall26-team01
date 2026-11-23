
"use client";

import { useState, type FormEvent } from "react";
import { api } from "../lib/auth";

type WeightUnit = "kg" | "lb";
type MeasurementMode = "now" | "historical";

type BodyweightMeasurement = {
  id: number;
  weight_kg: number;
  measured_at: string | null;
  measurement_date: string;
  timezone: string;
};

type Props = {
  onSaved?: (measurement: BodyweightMeasurement) => void;
};

const KG_PER_LB = 0.45359237;

function localDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");

  return `${year}-${month}-${day}`;
}

function getTimezone(): string {
  return (
    Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"
  );
}

function validDate(value: string): boolean {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);

  if (!match) return false;

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);

  const parsed = new Date(year, month - 1, day);

  return (
    parsed.getFullYear() === year &&
    parsed.getMonth() === month - 1 &&
    parsed.getDate() === day
  );
}

export default function BodyweightLogger({ onSaved }: Props) {
  const [weight, setWeight] = useState("");
  const [unit, setUnit] = useState<WeightUnit>("lb");
  const [mode, setMode] = useState<MeasurementMode>("now");
  const [date, setDate] = useState(() => localDate(new Date()));

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  // Convert the displayed number when changing units.
  function changeUnit(nextUnit: WeightUnit) {
    if (nextUnit === unit) return;

    const value = Number(weight);

    if (weight.trim() && Number.isFinite(value) && value > 0) {
      const converted =
        nextUnit === "kg"
          ? value * KG_PER_LB
          : value / KG_PER_LB;

      setWeight(String(Number(converted.toFixed(2))));
    }

    setUnit(nextUnit);
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();

    const value = Number(weight);
    const weightKg = unit === "lb" ? value * KG_PER_LB : value;

    if (
      !weight.trim() ||
      !Number.isFinite(weightKg) ||
      weightKg <= 0 ||
      weightKg > 600
    ) {
      setError("Enter a valid bodyweight.");
      return;
    }

    const now = new Date();
    const measurementDate =
      mode === "now" ? localDate(now) : date;

    if (
      !validDate(measurementDate) ||
      measurementDate > localDate(now)
    ) {
      setError("Enter a valid measurement date.");
      return;
    }

    const payload = {
      weight_kg: Number(weightKg.toFixed(2)),
      timezone: getTimezone(),
      measurement_date: measurementDate,

      // For historical date-only measurements, the exact
      // measurement time is unknown.
      measured_at: mode === "now" ? now.toISOString() : null,
    };

    setSaving(true);
    setError("");
    setSuccess(false);

    try {
      const saved = await api<BodyweightMeasurement>(
        "/bodyweight-measurements",
        {
          method: "POST",
          body: JSON.stringify(payload),
        }
      );

      setSuccess(true);
      setWeight("");
      onSaved?.(saved);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to save bodyweight."
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <h2>Log Bodyweight</h2>

      <div>
        <label htmlFor="measurement-mode">
          Measurement timing
        </label>

        <select
          id="measurement-mode"
          value={mode}
          onChange={(e) =>
            setMode(e.target.value as MeasurementMode)
          }
        >
          <option value="now">Current measurement</option>
          <option value="historical">Previous measurement</option>
        </select>
      </div>

      {mode === "historical" && (
        <div>
          <label htmlFor="measurement-date">
            Measurement date
          </label>

          <input
            id="measurement-date"
            type="date"
            value={date}
            max={localDate(new Date())}
            onChange={(e) => setDate(e.target.value)}
            required
          />
        </div>
      )}

      <div>
        <label htmlFor="bodyweight">
          Bodyweight
        </label>

        <input
          id="bodyweight"
          type="number"
          inputMode="decimal"
          min="0.01"
          max={unit === "kg" ? 600 : 1322.77}
          step="any"
          value={weight}
          onChange={(e) => setWeight(e.target.value)}
          placeholder={unit === "lb" ? "180" : "81.65"}
          required
        />
      </div>

      <div>
        <label htmlFor="weight-unit">
          Unit
        </label>

        <select
          id="weight-unit"
          value={unit}
          onChange={(e) =>
            changeUnit(e.target.value as WeightUnit)
          }
        >
          <option value="lb">Pounds (lb)</option>
          <option value="kg">Kilograms (kg)</option>
        </select>
      </div>

      <p>
        Timezone: {getTimezone()}
      </p>

      <p>
        Measurements are stored in kilograms.
      </p>

      {error && <p role="alert">{error}</p>}

      {success && (
        <p role="status">
          Bodyweight saved successfully.
        </p>
      )}

      <button type="submit" disabled={saving}>
        {saving ? "Saving..." : "Save Bodyweight"}
      </button>
    </form>
  );
}
