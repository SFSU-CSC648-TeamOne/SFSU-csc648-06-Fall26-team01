"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import Navbar from "../../../components/Navbar";
import { api, useRequireAuth } from "../../../lib/auth";
import s from "../../screens.module.css";

type Exercise = { id: number; name: string; role: string; sets: number | null; reps: number | null; minutes?: number; equipment: string[]; primary_muscles: string[] };
type Detail = { id: number; name: string; program_name: string; difficulty: string; total_minutes: number; exercise_count: number; exercises: Exercise[] };

export default function WorkoutDetailsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  useRequireAuth();
  const [w, setW] = useState<Detail | null>(null);
  const [error, setError] = useState("");

  useEffect(() => { api<Detail>(`/workout-sessions/${id}`).then(setW).catch((e) => setError(e.message)); }, [id]);

  return (
    <main className={s.page}>
      <Navbar />
      <div className={s.wrap}>
        <p className={s.kicker}>Session{w ? ` · ${w.program_name}` : ""}</p>
        <h1 className={s.h1}>{w?.name ?? "Workout"}<span>details.</span></h1>
        {error && <p className={s.error}>{error}</p>}
        {w && (
          <>
            <div className={s.stats}>
              <div><span>DURATION</span><strong>{w.total_minutes} MIN</strong></div>
              <div><span>EXERCISES</span><strong>{String(w.exercise_count).padStart(2, "0")}</strong></div>
              <div><span>LEVEL</span><strong>{w.difficulty.toUpperCase()}</strong></div>
            </div>
            <div className={s.list}>
              {w.exercises.map((e, i) => (
                <div className={s.row} key={e.id}>
                  <span className={s.rowIdx}>{String(i + 1).padStart(2, "0")}</span>
                  <span className={s.rowTitle}>
                    <strong>{e.name}</strong>
                    <small>{e.sets && e.reps ? `${e.sets} × ${e.reps} · ` : ""}{e.primary_muscles.join(", ") || "FULL BODY"}{e.minutes ? ` · ${e.minutes} MIN` : ""}</small>
                  </span>
                  <span className={`${s.tag} ${e.role === "core" ? "" : s.tagAcc}`}>{e.role.toUpperCase()}</span>
                  <Link href={`/exercises/${e.id}`} className={s.mono} aria-label={`Exercise info for ${e.name}`}>INFO ↗</Link>
                </div>
              ))}
            </div>
            <div className={s.actions}>
              <Link href={`/workouts/active?session=${w.id}`} className={s.btn}>Start workout ↗</Link>
              <Link href="/programs" className={`${s.btn} ${s.btnGhost}`}>Back to programs</Link>
            </div>
          </>
        )}
      </div>
    </main>
  );
}
