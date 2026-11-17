"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import Navbar from "../../components/Navbar";
import BodyweightLogger from "../../components/BodyweightLogger";
import BodyweightChart, {type BodyweightPoint,} from "../../components/progress/BodyweightChart";
import { api, useRequireAuth } from "../../lib/auth";
import { fmtDate, volume, type Page, type RecordDetail, type RecordSummary } from "../../lib/records";
import s from "../screens.module.css";

export default function ProgressPage() {
  useRequireAuth();
  const [records, setRecords] = useState<RecordDetail[]>([]);
  const [error, setError] = useState("");
  const [bodyweight, setBodyweight] = useState<BodyweightPoint[]>([]);
  const [weightLoading, setWeightLoading] = useState(true);
  const [weightError, setWeightError] = useState("");
  const [weightRefresh, setWeightRefresh] = useState(0);


  useEffect(() => {
    // The list has no entries, so fetch the detail of the 10 latest records to compute volume.
    api<Page<RecordSummary>>("/workout-records?limit=10")
      .then((p) => Promise.all(p.items.map((r) => api<RecordDetail>(`/workout-records/${r.id}`))))
      .then(setRecords)
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    let active = true;

    async function loadBodyweight() {
      setWeightLoading(true);
      setWeightError("");

      try {
        const data = await api<
          Array<Omit<BodyweightPoint, "weight_kg"> & {
            weight_kg: number | string;
          }>
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
  }, [weightRefresh]);


  const points = [...records].sort((a, b) => +new Date(a.performed_at) - +new Date(b.performed_at)).slice(-10)
    .map((r) => ({ label: fmtDate(r.performed_at).slice(0, 6), v: volume(r), id: r.id }));
  const max = Math.max(1, ...points.map((p) => p.v));
  const first = points[0]?.v ?? 0, last = points[points.length - 1]?.v ?? 0;
  const change = first > 0 ? Math.round(((last - first) / first) * 100) : null;

  return (
    <main className={s.page}>
      <Navbar />
      <div className={s.wrap}>
        <p className={s.kicker}>Training volume (reps × kg) per workout</p>
        <h1 className={s.h1}>Progress<span>trend.</span></h1>
        {error && <p className={s.error}>{error}</p>}
        {points.length === 0 ? (
          <p className={s.muted}>Finish a workout to see your trend. <Link href="/programs" style={{ color: "#9fb0ff" }}>Go to Programs</Link>.</p>
        ) : (
          <div className={s.card}>
            {change !== null && points.length > 1 && <p className={s.mono} style={{ color: change >= 0 ? "var(--lime)" : "var(--red)" }}>{change >= 0 ? "+" : ""}{change}% SINCE {points[0].label}</p>}
            <div className={s.bars} role="img" aria-label="Bar chart of training volume per workout">
              {points.map((p) => <div key={p.id} className={s.bar} style={{ height: `${(p.v / max) * 100}%` }}><span>{Math.round(p.v)}</span></div>)}
            </div>
            <div className={s.barLabels}>{points.map((p) => <span key={p.id}>{p.label}</span>)}</div>
            <p className={s.muted} style={{ marginTop: 16 }}>Add the weight you used on the Active workout screen to see volume change.</p>
          </div>
        )}
          <section
            className={s.card}
            style={{ marginTop: 24 }}
            aria-labelledby="bodyweight-heading"
          >
            <div style={{ marginBottom: 20 }}>
              <h2 id="bodyweight-heading">
                Bodyweight Tracking
              </h2>

              <p className={s.muted}>
                Record your bodyweight to monitor changes
                alongside your training performance.
              </p>
            </div>

            <BodyweightLogger
              onSaved={(measurement) => {
                console.log(
                  "Bodyweight saved:",
                  measurement
                );
              }}
            />
          </section>
          <section
            className={s.card}
            style={{ marginTop: 24 }}
            aria-labelledby="bodyweight-heading"
          >
            <h2 id="bodyweight-heading">
              Bodyweight Tracking
            </h2>

            <p className={s.muted}>
              Monitor your bodyweight alongside training performance.
            </p>

            <div style={{ marginTop: 24 }}>
              <BodyweightLogger
                onSaved={() => {
                  setWeightRefresh((count) => count + 1);
                }}
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
        <div className={s.actions}><Link href="/history" className={`${s.btn} ${s.btnGhost}`}>Back to Training history</Link></div>
      </div>
    </main>
  );
}
