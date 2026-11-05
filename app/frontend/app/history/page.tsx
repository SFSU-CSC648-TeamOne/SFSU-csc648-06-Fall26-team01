"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import Navbar from "../../components/Navbar";
import { api, useRequireAuth } from "../../lib/auth";
import { fmtDate, type Page, type RecordSummary } from "../../lib/records";
import s from "../screens.module.css";

export default function TrainingHistoryPage() {
  useRequireAuth();
  const [records, setRecords] = useState<RecordSummary[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Page<RecordSummary>>("/workout-records?limit=100")
      .then((r) => setRecords(r.items))
      .catch((e) => setError(e.message));
  }, []);

  const sorted = [...(records ?? [])].sort((a, b) => +new Date(b.performed_at) - +new Date(a.performed_at));

  return (
    <main className={s.page}>
      <Navbar />
      <div className={s.wrap}>
        <p className={s.kicker}>Saved automatically when you finish a workout</p>
        <h1 className={s.h1}>Training <span>history.</span></h1>
        {error && <p className={s.error}>{error}</p>}
        {records && sorted.length === 0 && (
          <p className={s.muted}>No workouts yet. <Link href="/programs" style={{ color: "#9fb0ff" }}>Start one from Programs</Link>.</p>
        )}
        <div className={s.list}>
          {sorted.map((r, i) => {
            const total = r.entry_count;
            return (
              <div className={s.row} key={r.id}>
                <span className={s.rowIdx}>{String(i + 1).padStart(2, "0")}</span>
                <span className={s.rowTitle}>
                  <strong>{r.session_name || "Workout"}</strong>
                  <small>{fmtDate(r.performed_at)}{total ? ` · ${total} ENTRIES` : ""}{(r.duration_minutes ?? r.available_minutes) ? ` · ${r.duration_minutes ?? r.available_minutes} MIN` : ""}</small>
                </span>
                <span className={s.tag}>LOGGED</span>
                <span />
              </div>
            );
          })}
        </div>
        {sorted.length > 0 && <div className={s.actions}><Link href="/progress" className={s.btn}>See progress trend ↗</Link></div>}
      </div>
    </main>
  );
}
