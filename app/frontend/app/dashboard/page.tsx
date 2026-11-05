"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import Navbar from "../../components/Navbar";
import { api, displayName, useRequireAuth } from "../../lib/auth";
import s from "../screens.module.css";

type Session = { id: number; name: string; program_name: string; difficulty: string; total_minutes: number; exercise_count: number; muscle_groups: string[] };

export default function DashboardPage() {
  const { user } = useRequireAuth();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api<{ items: Session[] }>("/workout-sessions?limit=3").then((r) => setSessions(r.items)).catch((e) => setError(String(e.message ?? e)));
  }, []);

  const today = sessions[0];
  return (
    <main className={s.page}>
      <Navbar />
      <div className={s.wrap}>
        <p className={s.kicker}>Hi, {displayName(user)}</p>
        <h1 className={s.h1}>Today&apos;s <span>session.</span></h1>

        {error && <p className={s.error}>{error}</p>}
        {today ? (
          <div className={s.card}>
            <p className={s.kicker}>{today.program_name}</p>
            <h2 style={{ fontSize: 34, margin: "8px 0", textTransform: "uppercase" }}>{today.name}</h2>
            <div className={s.stats}>
              <div><span>DURATION</span><strong>{today.total_minutes} MIN</strong></div>
              <div><span>EXERCISES</span><strong>{String(today.exercise_count).padStart(2, "0")}</strong></div>
              <div><span>FOCUS</span><strong>{today.muscle_groups.slice(0, 2).join(" · ") || "FULL BODY"}</strong></div>
            </div>
            <div className={s.actions}>
              <Link href={`/workouts/${today.id}`} className={s.btn}>View workout ↗</Link>
              <Link href={`/workouts/active?session=${today.id}`} className={`${s.btn} ${s.btnGhost}`}>Start now</Link>
            </div>
          </div>
        ) : !error && <p className={s.muted}>No sessions found yet.</p>}

        <div className={s.actions} style={{ marginTop: 40 }}>
          <Link href="/programs" className={`${s.btn} ${s.btnGhost}`}>Programs</Link>
          <Link href="/search" className={`${s.btn} ${s.btnGhost}`}>Exercises</Link>
          <Link href="/history" className={`${s.btn} ${s.btnGhost}`}>Training history</Link>
        </div>
      </div>
    </main>
  );
}
